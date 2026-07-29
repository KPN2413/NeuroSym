from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from verilogic_ns_api.baselines.configuration import (
    file_sha256,
    resolve_repository_path,
)
from verilogic_ns_api.evaluation.metrics import compute_metrics
from verilogic_ns_api.reasoning.engine import ForwardChainingEngine
from verilogic_ns_api.reasoning.models import ReasoningStatus, Theory, sha256_payload
from verilogic_ns_api.reasoning.proofwriter import select_conformance_examples
from verilogic_ns_api.reasoning.verifier import ProofVerifier
from verilogic_ns_api.research.models import (
    BenchmarkExample,
    PredictionLabel,
    PredictionRecord,
    Split,
)
from verilogic_ns_api.semantic_parsing.cli import _service as phase5_service
from verilogic_ns_api.semantic_parsing.configuration import prepare_parser_experiment
from verilogic_ns_api.semantic_parsing.evaluation import run_parser_evaluation
from verilogic_ns_api.semantic_parsing.models import ParserExperimentConfig
from verilogic_ns_api.semantic_parsing.views import prepare_query_view
from verilogic_ns_api.validation_correction.configuration import (
    PreparedCorrectionExperiment,
    load_correction_config,
    prepare_correction_experiment,
)
from verilogic_ns_api.validation_correction.controller import ValidationCorrectionController
from verilogic_ns_api.validation_correction.evaluation import (
    _ast_metrics,
    _correction_metrics,
    _critic_metrics,
    _efficiency,
    _proof_payload,
    _write_traces,
)
from verilogic_ns_api.validation_correction.feedback import (
    validate_query_candidate,
    validate_theory_candidate,
)
from verilogic_ns_api.validation_correction.models import (
    ComponentDecision,
    CorrectionExperimentConfig,
    CriticDecision,
    TaskKind,
    TaskStatus,
)
from verilogic_ns_api.validation_correction.policy import apply_policy
from verilogic_ns_api.validation_correction.raw import load_raw_phase5_candidates
from verilogic_ns_api.validation_correction.service import CorrectionTaskService

EXPECTED_MODEL_DIGEST = "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd"
ORIGINAL_PARSER_CONFIG = "experiments/configs/ollama-semantic-parser-pilot.yaml"
ORIGINAL_CORRECTION_CONFIG = "experiments/configs/ollama-validation-correction-pilot.yaml"
ORIGINAL_BLOCKED_REPORT = "docs/PHASE6_PILOT_RESULTS.md"
RECOVERY_FREEZE_MANIFEST = "experiments/manifests/phase6-recovery-r2-1-freeze.v1.json"


class RecoveryR2Error(RuntimeError):
    pass


def prepare_recovery_r2(path: Path) -> PreparedCorrectionExperiment:
    prepared = prepare_correction_experiment(path)
    root = prepared.root
    original_parser = prepare_parser_experiment(root / ORIGINAL_PARSER_CONFIG)
    original_correction = load_correction_config(root / ORIGINAL_CORRECTION_CONFIG)
    assert_recovery_config_equivalent(
        original_parser.config,
        prepared.phase5.config,
        original_correction,
        prepared.config,
    )
    _assert_isolated_path(
        prepared.phase5.config.cache_directory, "results/cache/semantic-parser-phase6-r2"
    )
    _assert_isolated_path(
        prepared.phase5.config.output_directory, "results/semantic-parsing-phase6-r2"
    )
    _assert_isolated_path(
        prepared.config.cache_directory, "results/cache/validation-correction-phase6-r2"
    )
    _assert_isolated_path(
        prepared.config.output_directory, "results/validation-correction-phase6-r2"
    )
    if prepared.config.runtime.model_digest != EXPECTED_MODEL_DIGEST:
        raise RecoveryR2Error("Phase 6-R2 model digest differs from the frozen contract")
    verify_recovery_freeze(prepared)
    return prepared


def assert_recovery_config_equivalent(
    original_parser: ParserExperimentConfig,
    recovery_parser: ParserExperimentConfig,
    original_correction: CorrectionExperimentConfig,
    recovery_correction: CorrectionExperimentConfig,
) -> None:
    parser_ignored = {"name", "cache_directory", "output_directory"}
    original_parser_behavior = original_parser.model_dump(exclude=parser_ignored)
    recovery_parser_behavior = recovery_parser.model_dump(exclude=parser_ignored)
    if original_parser_behavior != recovery_parser_behavior:
        raise RecoveryR2Error("Phase 5-R2 changes a behavioral parser setting")

    correction_ignored = {
        "name",
        "phase5_config",
        "phase5_config_sha256",
        "cache_directory",
        "output_directory",
    }
    original_correction_behavior = original_correction.model_dump(exclude=correction_ignored)
    recovery_correction_behavior = recovery_correction.model_dump(exclude=correction_ignored)
    if original_correction_behavior != recovery_correction_behavior:
        raise RecoveryR2Error("Phase 6-R2 changes a behavioral correction setting")


def seal_recovery_predictions(
    *,
    prepared: PreparedCorrectionExperiment,
    service: CorrectionTaskService,
    output_directory: Path,
    run_id: str,
    experiment_version: str = "r2",
) -> dict[str, object]:
    """Execute gold-free decisions and durably seal them before evaluation."""
    if output_directory.exists():
        raise RecoveryR2Error(f"run directory already exists: {output_directory}")
    output_directory.mkdir(parents=True)
    _atomic_json(output_directory / "run-state.json", {"status": "incomplete", "run_id": run_id})
    started = perf_counter()
    examples = prepared.phase5.pilot_examples
    raw = load_raw_phase5_candidates(prepared.phase5, calibration=False)

    controller = ValidationCorrectionController(service)
    theory_decisions: dict[str, ComponentDecision] = {}
    final_bodies: dict[str, Theory] = {}
    for key, view in sorted(raw.theory_views.items()):
        decision = controller.run_theory(
            view=view,
            raw_candidate=raw.theories[key],
            theory_id=key,
        )
        theory_decisions[key] = decision
        if decision.final_candidate is not None:
            validated = validate_theory_candidate(decision.final_candidate, view, theory_id=key)
            if validated.valid and validated.converted is not None:
                final_bodies[key] = validated.converted

    query_decisions: dict[str, ComponentDecision] = {}
    for example in examples:
        key = example.theory_id or example.example_id
        query_decisions[example.example_id] = controller.run_query(
            view=prepare_query_view(example),
            raw_candidate=raw.queries[example.example_id],
            body=final_bodies.get(key),
        )
    if service.new_call_count > prepared.config.limits.maximum_new_pilot_calls:
        raise RecoveryR2Error("Phase 6-R2 local-call budget was exceeded")

    p0, p0_proof = _raw_policy(examples, raw, experiment_version=experiment_version)
    p1 = apply_policy(
        examples=examples,
        theory_views=raw.theory_views,
        theory_decisions=theory_decisions,
        query_decisions=query_decisions,
        selective=False,
    )
    p2 = apply_policy(
        examples=examples,
        theory_views=raw.theory_views,
        theory_decisions=theory_decisions,
        query_decisions=query_decisions,
        selective=True,
    )
    if not all(len(items) == 30 for items in (p0, p1.predictions, p2.predictions)):
        raise RecoveryR2Error("Phase 6-R2 did not produce 30 final states for every policy")

    policies = {
        "p0": _policy_payload(p0, {}, p0_proof[0], p0_proof[1], {}),
        "p1": _policy_payload(
            p1.predictions,
            p1.parsed_theories,
            p1.proof_attempted,
            p1.proof_verified,
            p1.abstention_reasons,
        ),
        "p2": _policy_payload(
            p2.predictions,
            p2.parsed_theories,
            p2.proof_attempted,
            p2.proof_verified,
            p2.abstention_reasons,
        ),
    }
    decisions = {
        "theories": {key: value.model_dump(mode="json") for key, value in theory_decisions.items()},
        "queries": {key: value.model_dump(mode="json") for key, value in query_decisions.items()},
    }
    audit = _audit_records(examples, theory_decisions, query_decisions, p0, p1, p2)
    prediction_fingerprints = {
        name: sha256_payload([_canonical_prediction(item) for item in result["predictions"]])
        for name, result in _loaded_policy_payloads(policies).items()
    }
    decision_fingerprint = sha256_payload(_canonical_decisions(theory_decisions, query_decisions))
    audit_fingerprint = sha256_payload(audit)
    request_ledger = _request_ledger(theory_decisions, query_decisions)
    seal_fingerprint = sha256_payload(
        {
            "predictions": prediction_fingerprints,
            "decisions": decision_fingerprint,
            "audit": audit_fingerprint,
            "requests": request_ledger["request_fingerprint"],
        }
    )
    seal = {
        "schema_version": "1.0",
        "status": "sealed",
        "experiment_version": experiment_version,
        "run_id": run_id,
        "sealed_at": datetime.now(UTC).isoformat(),
        "examples": 30,
        "theory_components": len(theory_decisions),
        "query_components": len(query_decisions),
        "pending_requests": 0,
        "prediction_fingerprints": prediction_fingerprints,
        "decision_fingerprint": decision_fingerprint,
        "audit_fingerprint": audit_fingerprint,
        "request_ledger_fingerprint": request_ledger["request_fingerprint"],
        "seal_fingerprint": seal_fingerprint,
        "proofs": {
            "p0": {"attempted": p0_proof[0], "verified": p0_proof[1]},
            "p1": _proof_payload(p1),
            "p2": _proof_payload(p2),
        },
        "new_local_calls_this_invocation": service.new_call_count,
        "wall_seconds_to_seal": perf_counter() - started,
        "gold_fields_accessed": False,
        "test_split": False,
        "hosted_provider_calls": 0,
        "external_transmissions": 0,
        "api_cost_usd": 0.0,
    }
    _atomic_json(output_directory / "component-decisions.json", decisions)
    _atomic_json(output_directory / "sealed-policies.json", policies)
    _atomic_json(output_directory / "audit-records.json", audit)
    _atomic_json(output_directory / "request-ledger.json", request_ledger)
    _write_traces(output_directory, theory_decisions, query_decisions)
    _atomic_json(output_directory / "prediction-seal.json", seal)
    _atomic_json(output_directory / "run-state.json", {"status": "sealed", "run_id": run_id})
    return seal


def evaluate_sealed_recovery(
    *,
    prepared: PreparedCorrectionExperiment,
    output_directory: Path,
    experiment_version: str = "r2",
) -> dict[str, object]:
    """Evaluate only after verifying the durable gold-free prediction seal."""
    seal = _read_json(output_directory / "prediction-seal.json")
    decisions_payload = _read_json(output_directory / "component-decisions.json")
    policies_payload = _read_json(output_directory / "sealed-policies.json")
    audit = _read_json(output_directory / "audit-records.json")
    request_ledger = _read_json(output_directory / "request-ledger.json")
    theory_decisions = {
        key: ComponentDecision.model_validate(value)
        for key, value in decisions_payload["theories"].items()
    }
    query_decisions = {
        key: ComponentDecision.model_validate(value)
        for key, value in decisions_payload["queries"].items()
    }
    policies = _loaded_policy_payloads(policies_payload)
    _verify_seal(seal, theory_decisions, query_decisions, policies, audit, request_ledger)

    examples = prepared.phase5.pilot_examples
    p0 = policies["p0"]
    p1 = policies["p1"]
    p2 = policies["p2"]
    p0_eval_directory = output_directory / "p0-evaluation"
    p0_report = run_parser_evaluation(
        examples=examples,
        data_source=resolve_repository_path(prepared.root, prepared.phase5.config.data_source),
        variant=prepared.phase5.config.variant,
        split=Split.DEVELOPMENT,
        parser=phase5_service(prepared.phase5, provider=None, replay_only=True),
        output_directory=p0_eval_directory,
        run_id=f"{seal['run_id']}-p0-evaluation",
    )
    evaluated_p0 = tuple(
        PredictionRecord.model_validate(item)
        for item in _read_json(p0_eval_directory / "predictions.json")
    )
    if [_canonical_label(item) for item in p0["predictions"]] != [
        _canonical_label(item) for item in evaluated_p0
    ]:
        raise RecoveryR2Error("sealed P0 predictions differ from cache-only evaluation")

    p0_metrics = compute_metrics(examples, p0["predictions"]).model_dump(mode="json")
    p1_metrics = compute_metrics(examples, p1["predictions"]).model_dump(mode="json")
    p2_metrics = compute_metrics(examples, p2["predictions"]).model_dump(mode="json")
    formal_examples = select_conformance_examples(
        resolve_repository_path(prepared.root, prepared.phase5.config.data_source),
        variant=prepared.phase5.config.variant,
        split=Split.DEVELOPMENT,
        example_ids={item.example_id for item in examples},
    )
    gold = {item.example_id: item.theory for item in formal_examples}
    raw = load_raw_phase5_candidates(prepared.phase5, calibration=False)
    correction_metrics = _extended_correction_metrics(
        theory_decisions, query_decisions, p0["predictions"], p1["predictions"]
    )
    critic_metrics = _critic_metrics(
        examples,
        gold,
        raw.theory_views,
        theory_decisions,
        query_decisions,
    )
    ast_metrics = _ast_metrics(examples, gold, p1["parsed_theories"])
    efficiency = _efficiency(theory_decisions, query_decisions, raw.cache_hits)
    abstention = _abstention_metrics(p1["predictions"], p2["predictions"])
    reasoning = {
        "p0": _reasoning_metrics(p0["predictions"], p0["proof_attempted"], p0["proof_verified"]),
        "p1": _reasoning_metrics(p1["predictions"], p1["proof_attempted"], p1["proof_verified"]),
        "p2": _reasoning_metrics(p2["predictions"], p2["proof_attempted"], p2["proof_verified"]),
    }
    report_fingerprint = sha256_payload(
        {
            "seal": seal["seal_fingerprint"],
            "p0": p0_metrics,
            "p1": p1_metrics,
            "p2": p2_metrics,
            "correction": correction_metrics,
            "critic": critic_metrics,
            "ast": ast_metrics,
            "abstention": abstention,
            "reasoning": reasoning,
        }
    )
    report = {
        "schema_version": "2.0",
        "status": "complete",
        "experiment": (
            "Phase 6 R3 Terminal-Failure Evaluation"
            if experiment_version == "r3"
            else "Phase 6 Recovery Replication v2"
        ),
        "run_id": seal["run_id"],
        "prediction_seal_fingerprint": seal["seal_fingerprint"],
        "report_fingerprint": report_fingerprint,
        f"p0_{experiment_version}": {"metrics": p0_metrics, "parser": p0_report},
        f"p1_{experiment_version}": {
            "metrics": p1_metrics,
            "proof_verification": {
                "attempted": p1["proof_attempted"],
                "verified": p1["proof_verified"],
                "failed": p1["proof_attempted"] - p1["proof_verified"],
            },
            "abstention_reasons": p1["abstention_reasons"],
        },
        f"p2_{experiment_version}": {
            "metrics": p2_metrics,
            "proof_verification": {
                "attempted": p2["proof_attempted"],
                "verified": p2["proof_verified"],
                "failed": p2["proof_attempted"] - p2["proof_verified"],
            },
            "abstention_reasons": p2["abstention_reasons"],
        },
        "correction_metrics": correction_metrics,
        "critic_metrics": critic_metrics,
        "ast_metrics": ast_metrics,
        "abstention_metrics": abstention,
        "reasoning_metrics": reasoning,
        "efficiency": efficiency,
        "request_ledger": request_ledger["summary"],
        "comparison_table": _comparison_table(p0_metrics, p1_metrics, p2_metrics),
        "historical_phase5_p0": {
            "correct": 3,
            "accuracy": 0.1,
            "coverage": 4 / 30,
            "answered_only_accuracy": 0.75,
            "macro_f1": 0.16317016317016317,
            "errors": 26,
        },
        "historical_p0_delta": {
            "accuracy": p0_metrics["accuracy"] - 0.1,
            "coverage": p0_metrics["coverage"] - 4 / 30,
            "errored_examples": p0_metrics["errored_examples"] - 26,
        },
        "api_cost_usd": 0.0,
        "hosted_provider_calls": 0,
        "external_transmissions": 0,
        "test_split": False,
    }
    _atomic_json(output_directory / "report.json", report)
    _atomic_json(
        output_directory / "run-state.json",
        {"status": "complete", "run_id": seal["run_id"]},
    )
    return report


def compare_recovery_replay(live: Path, replay: Path) -> dict[str, object]:
    live_seal = _read_json(live / "prediction-seal.json")
    replay_seal = _read_json(replay / "prediction-seal.json")
    live_report = _read_json(live / "report.json")
    replay_report = _read_json(replay / "report.json")
    replay_ledger = _read_json(replay / "request-ledger.json")
    result = {
        "prediction_seal_match": live_seal["seal_fingerprint"] == replay_seal["seal_fingerprint"],
        "report_fingerprint_match": live_report["report_fingerprint"]
        == replay_report["report_fingerprint"],
        "phase6_replay_cache_misses": replay_ledger["summary"]["cache_misses"],
        "phase6_replay_new_calls": replay_seal["new_local_calls_this_invocation"],
        "phase6_replay_cache_hits": replay_ledger["summary"]["cache_hits"],
    }
    result["passed"] = all(
        (
            result["prediction_seal_match"],
            result["report_fingerprint_match"],
            result["phase6_replay_cache_misses"] == 0,
            result["phase6_replay_new_calls"] == 0,
        )
    )
    if not result["passed"]:
        raise RecoveryR2Error("Phase 6-R2 replay differs from the sealed live run")
    return result


def recovery_freeze_facts(prepared: PreparedCorrectionExperiment) -> dict[str, object]:
    root = prepared.root
    return {
        "starting_checkpoint": "4270c83e2d5618939de9120bde307df966ce6ae3",
        "original_blocked_report_sha256": file_sha256(root / ORIGINAL_BLOCKED_REPORT),
        "phase5_r2_config_sha256": file_sha256(prepared.phase5.config_path),
        "phase6_r2_config_sha256": file_sha256(prepared.config_path),
        "ordered_record_ids": [item.example_id for item in prepared.phase5.pilot_examples],
        "ordered_record_ids_sha256": sha256_payload(
            [item.example_id for item in prepared.phase5.pilot_examples]
        ),
        "model": prepared.config.runtime.model,
        "model_digest": prepared.config.runtime.model_digest,
        "runtime": prepared.config.runtime.model_dump(mode="json"),
        "policy_hash": prepared.config.reliability_policy.policy_hash,
        "cache_paths": {
            "phase5_r2": prepared.phase5.config.cache_directory,
            "phase6_r2": prepared.config.cache_directory,
        },
        "output_paths": {
            "phase5_r2": prepared.phase5.config.output_directory,
            "phase6_r2": prepared.config.output_directory,
        },
    }


def verify_recovery_freeze(prepared: PreparedCorrectionExperiment) -> None:
    root = prepared.root
    manifest = _read_json(root / RECOVERY_FREEZE_MANIFEST)
    observed = recovery_freeze_facts(prepared)
    expected = {
        "starting_checkpoint": manifest["starting_checkpoint"],
        "original_blocked_report_sha256": manifest["original_blocked_report_sha256"],
        "phase5_r2_config_sha256": manifest["r2_artifacts"]["phase5_config_sha256"],
        "phase6_r2_config_sha256": manifest["r2_artifacts"]["phase6_config_sha256"],
        "ordered_record_ids": manifest["dataset"]["ordered_record_ids"],
        "ordered_record_ids_sha256": manifest["dataset"]["ordered_record_ids_sha256"],
        "model": manifest["model_contract"]["model"],
        "model_digest": manifest["model_contract"]["model_digest"],
        "policy_hash": manifest["original_artifacts"]["reliability_policy_sha256"],
        "cache_paths": {
            "phase5_r2": manifest["r2_artifacts"]["phase5_cache"],
            "phase6_r2": manifest["r2_artifacts"]["phase6_cache"],
        },
        "output_paths": {
            "phase5_r2": manifest["r2_artifacts"]["phase5_output"],
            "phase6_r2": manifest["r2_artifacts"]["phase6_output"],
        },
    }
    for key, value in expected.items():
        if observed[key] != value:
            raise RecoveryR2Error(f"Phase 6-R2 freeze mismatch: {key}")
    runtime = manifest["model_contract"]
    config = prepared.config.runtime
    runtime_checks = {
        "endpoint": config.endpoint,
        "ollama_version": config.provider_version,
        "context_length": config.num_ctx,
        "temperature": config.temperature,
        "seed": config.seed,
        "thinking": config.think,
    }
    if any(runtime[key] != value for key, value in runtime_checks.items()):
        raise RecoveryR2Error("Phase 6-R2 runtime differs from the preregistration")
    if manifest["dataset"]["split"] != "development" or manifest["dataset"]["test_split_used"]:
        raise RecoveryR2Error("Phase 6-R2 freeze does not preserve the development-only boundary")


def _raw_policy(
    examples,
    raw,
    *,
    experiment_version: str = "r2",
) -> tuple[tuple[PredictionRecord, ...], tuple[int, int]]:
    engine = ForwardChainingEngine()
    verifier = ProofVerifier()
    predictions: list[PredictionRecord] = []
    bodies: dict[str, Theory] = {}
    for key, view in raw.theory_views.items():
        result = validate_theory_candidate(raw.theories[key], view, theory_id=key)
        if result.valid and result.converted is not None:
            bodies[key] = result.converted
    attempted = verified = 0
    for example in examples:
        key = example.theory_id or example.example_id
        body = bodies.get(key)
        if body is None:
            error_type = (
                raw.theory_terminal_errors[key].error_type
                if key in raw.theory_terminal_errors
                else "RAW_THEORY_INVALID"
            )
            predictions.append(
                _prediction(
                    example,
                    PredictionLabel.ERROR,
                    error_type,
                    experiment_version=experiment_version,
                )
            )
            continue
        query = validate_query_candidate(
            raw.queries[example.example_id],
            prepare_query_view(example),
            body=body,
        )
        if not query.valid or query.theory is None:
            error_type = (
                raw.query_terminal_errors[example.example_id].error_type
                if example.example_id in raw.query_terminal_errors
                else "RAW_QUERY_INVALID"
            )
            predictions.append(
                _prediction(
                    example,
                    PredictionLabel.ERROR,
                    error_type,
                    experiment_version=experiment_version,
                )
            )
            continue
        reasoning = engine.reason(query.theory)
        if reasoning.result.status is ReasoningStatus.INCONSISTENT:
            predictions.append(
                _prediction(
                    example,
                    PredictionLabel.ERROR,
                    "INCONSISTENT",
                    experiment_version=experiment_version,
                )
            )
            continue
        attempted += 1
        try:
            verifier.verify_result(query.theory, reasoning.result)
            verified += 1
        except Exception as error:
            predictions.append(
                _prediction(
                    example,
                    PredictionLabel.ERROR,
                    f"PROOF_VERIFICATION_ERROR:{type(error).__name__}",
                    experiment_version=experiment_version,
                )
            )
            continue
        label = {
            ReasoningStatus.ENTAILED: PredictionLabel.ENTAILED,
            ReasoningStatus.CONTRADICTED: PredictionLabel.CONTRADICTED,
            ReasoningStatus.UNKNOWN: PredictionLabel.UNKNOWN,
        }[reasoning.result.status]
        predictions.append(_prediction(example, label, experiment_version=experiment_version))
    return tuple(predictions), (attempted, verified)


def _prediction(
    example: BenchmarkExample,
    label: PredictionLabel,
    error_type: str | None = None,
    *,
    experiment_version: str = "r2",
) -> PredictionRecord:
    return PredictionRecord(
        run_id=f"phase6-{experiment_version}-sealed",
        example_id=example.example_id,
        predicted_label=label,
        error_type=error_type,
        latency_ms=0,
        cache_hit=True,
        configured_model="qwen3.5:4b-q4_K_M",
        returned_model="qwen3.5:4b-q4_K_M",
        provider_version="0.32.1",
        model_digest=EXPECTED_MODEL_DIGEST,
        execution_device="cpu",
        estimated_cost_usd=0,
        predictor_name=f"phase6-{experiment_version}-raw",
        predictor_version="3.0" if experiment_version == "r3" else "2.0",
        timestamp=datetime.now(UTC),
    )


def _policy_payload(
    predictions,
    parsed_theories,
    proof_attempted,
    proof_verified,
    abstention_reasons,
) -> dict[str, object]:
    return {
        "predictions": [item.model_dump(mode="json") for item in predictions],
        "parsed_theories": {
            key: value.model_dump(mode="json") for key, value in parsed_theories.items()
        },
        "proof_attempted": proof_attempted,
        "proof_verified": proof_verified,
        "abstention_reasons": abstention_reasons,
    }


def _loaded_policy_payloads(payload) -> dict[str, dict[str, object]]:
    return {
        name: {
            "predictions": tuple(
                PredictionRecord.model_validate(item) for item in value["predictions"]
            ),
            "parsed_theories": {
                key: Theory.model_validate(item) for key, item in value["parsed_theories"].items()
            },
            "proof_attempted": int(value["proof_attempted"]),
            "proof_verified": int(value["proof_verified"]),
            "abstention_reasons": dict(value["abstention_reasons"]),
        }
        for name, value in payload.items()
    }


def _canonical_prediction(item: PredictionRecord) -> dict[str, object]:
    return {
        "example_id": item.example_id,
        "predicted_label": item.predicted_label,
        "abstention_reason": item.abstention_reason,
        "error_type": item.error_type,
    }


def _canonical_label(item: PredictionRecord) -> dict[str, object]:
    return {
        "example_id": item.example_id,
        "predicted_label": item.predicted_label,
    }


def _canonical_decisions(theories, queries) -> dict[str, object]:
    def canonical(item: ComponentDecision) -> dict[str, object]:
        return {
            "component_type": item.component_type,
            "input_hash": item.input_hash,
            "raw_candidate_hash": item.raw_candidate_hash,
            "final_candidate_hash": item.final_candidate_hash,
            "deterministic_accepted": item.deterministic_accepted,
            "selective_accepted": item.selective_accepted,
            "correction_attempts": item.correction_attempts,
            "critic_decision": item.critic_decision,
            "abstention_reason": item.abstention_reason,
            "error_type": item.error_type,
            "reliability": item.reliability.model_dump(mode="json"),
            "transitions": [value.model_dump(mode="json") for value in item.transitions],
            "operations": [
                {
                    "task_kind": value.task_kind,
                    "request_hash": value.request_hash,
                    "status": value.status,
                    "error_type": value.error_type,
                    "terminal": value.terminal,
                    "terminal_outcome_hash": value.terminal_outcome_hash,
                }
                for value in item.task_outcomes
            ],
        }

    return {
        "theories": {key: canonical(value) for key, value in sorted(theories.items())},
        "queries": {key: canonical(value) for key, value in sorted(queries.items())},
    }


def _audit_records(examples, theories, queries, p0, p1, p2) -> list[dict[str, object]]:
    answer_labels = {
        PredictionLabel.ENTAILED,
        PredictionLabel.CONTRADICTED,
        PredictionLabel.UNKNOWN,
    }
    records = []
    for example, raw, corrected, selective in zip(
        examples, p0, p1.predictions, p2.predictions, strict=True
    ):
        key = example.theory_id or example.example_id
        theory = theories[key]
        query = queries[example.example_id]
        records.append(
            {
                "record_ref": sha256_payload({"example_id": example.example_id}),
                "theory_ref": sha256_payload({"theory_id": key}),
                "raw_theory_candidate_hash": theory.raw_candidate_hash,
                "raw_query_candidate_hash": query.raw_candidate_hash,
                "final_theory_candidate_hash": theory.final_candidate_hash,
                "final_query_candidate_hash": query.final_candidate_hash,
                "theory_correction_attempted": bool(theory.correction_attempts),
                "query_correction_attempted": bool(query.correction_attempts),
                "theory_critic_decision": theory.critic_decision,
                "query_critic_decision": query.critic_decision,
                "theory_source_coverage": theory.reliability.source_coverage_complete,
                "query_source_coverage": query.reliability.source_coverage_complete,
                "theory_semantic_validation": theory.reliability.semantic_validation_passed,
                "query_semantic_validation": query.reliability.semantic_validation_passed,
                "p0_status": raw.predicted_label,
                "p1_status": corrected.predicted_label,
                "p2_status": selective.predicted_label,
                "p1_abstention_reason": corrected.abstention_reason,
                "p2_abstention_reason": selective.abstention_reason,
                "p1_error_type": corrected.error_type,
                "p2_error_type": selective.error_type,
                "p1_phase4_verified": corrected.predicted_label in answer_labels,
                "p2_phase4_verified": selective.predicted_label in answer_labels,
                "request_hashes": [
                    value.request_hash for value in (*theory.task_outcomes, *query.task_outcomes)
                ],
                "terminal_outcome_hashes": [
                    value.terminal_outcome_hash
                    for value in (*theory.task_outcomes, *query.task_outcomes)
                    if value.terminal_outcome_hash is not None
                ],
            }
        )
    return records


def _request_ledger(theories, queries) -> dict[str, object]:
    outcomes = [
        value
        for decision in [*theories.values(), *queries.values()]
        for value in decision.task_outcomes
    ]
    unique = {value.request_hash: value for value in outcomes}
    operations = [
        {
            "task_kind": value.task_kind,
            "request_hash": value.request_hash,
            "status": value.status,
            "cache_hit": value.cache_hit,
            "input_tokens": value.input_tokens,
            "output_tokens": value.output_tokens,
            "duration_ms": value.duration_ms,
            "error_type": value.error_type,
            "terminal": value.terminal,
            "terminal_outcome_hash": value.terminal_outcome_hash,
        }
        for value in unique.values()
    ]
    return {
        "schema_version": "1.0",
        "summary": {
            "logical_requests": len(outcomes),
            "unique_requests": len(unique),
            "new_local_calls": sum(not item.cache_hit for item in unique.values()),
            "cache_hits": sum(item.cache_hit for item in outcomes),
            "cache_misses": sum(
                item.status is not TaskStatus.SUCCESS and not item.cache_hit and not item.terminal
                for item in unique.values()
            ),
            "terminal_outcomes": sum(item.terminal for item in unique.values()),
            "critic_calls": sum(
                item.task_kind in {TaskKind.CRITIC_THEORY, TaskKind.CRITIC_QUERY}
                for item in unique.values()
            ),
            "correction_calls": sum(
                item.task_kind in {TaskKind.CORRECTION_THEORY, TaskKind.CORRECTION_QUERY}
                for item in unique.values()
            ),
            "input_tokens": sum(item.input_tokens for item in unique.values()),
            "output_tokens": sum(item.output_tokens for item in unique.values()),
            "inference_ms": sum(item.duration_ms for item in unique.values()),
            "transport_retries": 0,
            "hosted_calls": 0,
            "external_transmissions": 0,
            "api_cost_usd": 0.0,
        },
        "request_fingerprint": sha256_payload(
            [
                {
                    "task_kind": item["task_kind"],
                    "request_hash": item["request_hash"],
                    "status": item["status"],
                    "error_type": item["error_type"],
                    "terminal": item["terminal"],
                    "terminal_outcome_hash": item["terminal_outcome_hash"],
                }
                for item in operations
            ]
        ),
        "operations": operations,
    }


def _verify_seal(seal, theories, queries, policies, audit, request_ledger) -> None:
    predictions = {
        name: sha256_payload([_canonical_prediction(item) for item in result["predictions"]])
        for name, result in policies.items()
    }
    decision = sha256_payload(_canonical_decisions(theories, queries))
    audit_hash = sha256_payload(audit)
    expected = sha256_payload(
        {
            "predictions": predictions,
            "decisions": decision,
            "audit": audit_hash,
            "requests": request_ledger["request_fingerprint"],
        }
    )
    if (
        seal["status"] != "sealed"
        or predictions != seal["prediction_fingerprints"]
        or decision != seal["decision_fingerprint"]
        or audit_hash != seal["audit_fingerprint"]
        or expected != seal["seal_fingerprint"]
    ):
        raise RecoveryR2Error("Phase 6-R2 prediction seal verification failed")


def _extended_correction_metrics(theories, queries, p0, p1) -> dict[str, object]:
    metrics = _correction_metrics(theories, queries)
    decisions = [*theories.values(), *queries.values()]
    metrics.update(
        {
            "critic_theory_calls": sum(
                outcome.task_kind is TaskKind.CRITIC_THEORY
                for decision in decisions
                for outcome in decision.task_outcomes
            ),
            "critic_query_calls": sum(
                outcome.task_kind is TaskKind.CRITIC_QUERY
                for decision in decisions
                for outcome in decision.task_outcomes
            ),
            "critic_accept_decisions": sum(
                item.critic_decision is CriticDecision.ACCEPT for item in decisions
            ),
            "critic_revise_decisions": sum(
                item.critic_decision is CriticDecision.REVISE for item in decisions
            ),
            "records_newly_answerable": sum(
                raw.predicted_label is PredictionLabel.ERROR
                and corrected.predicted_label
                in {
                    PredictionLabel.ENTAILED,
                    PredictionLabel.CONTRADICTED,
                    PredictionLabel.UNKNOWN,
                }
                for raw, corrected in zip(p0, p1, strict=True)
            ),
            "records_lost_after_correction": sum(
                raw.predicted_label
                in {
                    PredictionLabel.ENTAILED,
                    PredictionLabel.CONTRADICTED,
                    PredictionLabel.UNKNOWN,
                }
                and corrected.predicted_label
                not in {
                    PredictionLabel.ENTAILED,
                    PredictionLabel.CONTRADICTED,
                    PredictionLabel.UNKNOWN,
                }
                for raw, corrected in zip(p0, p1, strict=True)
            ),
            "p0_to_p1_transition_matrix": _transition_matrix(p0, p1),
        }
    )
    return metrics


def _abstention_metrics(p1, p2) -> dict[str, object]:
    transition = _transition_matrix(p1, p2)
    p1_answered = [
        item
        for item in p1
        if item.predicted_label
        in {PredictionLabel.ENTAILED, PredictionLabel.CONTRADICTED, PredictionLabel.UNKNOWN}
    ]
    p2_answered = [
        item
        for item in p2
        if item.predicted_label
        in {PredictionLabel.ENTAILED, PredictionLabel.CONTRADICTED, PredictionLabel.UNKNOWN}
    ]
    return {
        "p1_to_p2_transition_matrix": transition,
        "abstention_count": sum(item.predicted_label is PredictionLabel.ABSTAIN for item in p2),
        "abstention_reasons": dict(
            Counter(
                item.abstention_reason
                for item in p2
                if item.predicted_label is PredictionLabel.ABSTAIN
            )
        ),
        "coverage_retained": len(p2_answered) / len(p1_answered) if p1_answered else 0,
        "p1_errors": sum(item.predicted_label is PredictionLabel.ERROR for item in p1),
        "p2_errors": sum(item.predicted_label is PredictionLabel.ERROR for item in p2),
    }


def _reasoning_metrics(predictions, attempted, verified) -> dict[str, object]:
    counts = Counter(item.predicted_label.value for item in predictions)
    return {
        "records_reaching_symbolic_engine": attempted,
        "entailed": counts["ENTAILED"],
        "contradicted": counts["CONTRADICTED"],
        "unknown": counts["UNKNOWN"],
        "inconsistent": sum(item.error_type == "INCONSISTENT" for item in predictions),
        "proofs_emitted": attempted,
        "proofs_verified": verified,
        "proof_verification_failures": attempted - verified,
    }


def _transition_matrix(left, right) -> dict[str, dict[str, int]]:
    labels = [item.value for item in PredictionLabel]
    matrix = {source: {target: 0 for target in labels} for source in labels}
    for before, after in zip(left, right, strict=True):
        matrix[before.predicted_label.value][after.predicted_label.value] += 1
    return matrix


def _comparison_table(p0, p1, p2) -> list[dict[str, object]]:
    def row(name, metrics):
        return {
            "system": name,
            "correct": round(30 * float(metrics["accuracy"])),
            "accuracy": metrics["accuracy"],
            "coverage": metrics.get("coverage"),
            "answered_only_accuracy": metrics.get("answered_only_accuracy"),
            "macro_f1": metrics.get("macro_f1"),
            "abstain": metrics.get("abstained_examples", 0),
            "error": metrics.get("errored_examples", 0),
        }

    return [
        {"system": "Historical direct local LLM", "correct": 17, "accuracy": 17 / 30},
        {"system": "Historical few-shot local LLM", "correct": 15, "accuracy": 0.5},
        {
            "system": "Historical Phase 5 P0",
            "correct": 3,
            "accuracy": 0.1,
            "coverage": 4 / 30,
            "answered_only_accuracy": 0.75,
            "macro_f1": 0.16317016317016317,
            "error": 26,
        },
        row("Phase 6-R2 P0", p0),
        row("Phase 6-R2 P1", p1),
        row("Phase 6-R2 P2", p2),
        {
            "system": "Phase 4 oracle-AST symbolic ceiling",
            "correct": 30,
            "accuracy": 1.0,
            "coverage": 1.0,
            "answered_only_accuracy": 1.0,
            "macro_f1": 1.0,
            "abstain": 0,
            "error": 0,
        },
    ]


def _assert_isolated_path(observed: str, expected: str) -> None:
    normalized = observed.replace("\\", "/").rstrip("/")
    if normalized != expected or "phase6-r2" not in normalized:
        raise RecoveryR2Error(f"R2 path is not isolated: {observed}")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
