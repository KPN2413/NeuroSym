from __future__ import annotations

import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from verilogic_ns_api.baselines.configuration import file_sha256
from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.semantic_parsing.cache import ParserResponseCache
from verilogic_ns_api.semantic_parsing.configuration import (
    PreparedParserExperiment,
    prepare_parser_experiment,
)
from verilogic_ns_api.semantic_parsing.models import (
    CandidateQueryOutput,
    CandidateTheoryOutput,
    ParserResponse,
)
from verilogic_ns_api.semantic_parsing.prompts import render_query_input, render_theory_input
from verilogic_ns_api.semantic_parsing.provider import StructuredRequest
from verilogic_ns_api.semantic_parsing.views import (
    assert_same_theory,
    prepare_query_view,
    prepare_theory_view,
)
from verilogic_ns_api.terminal_outcomes import (
    AttemptEvidence,
    CachedOutcomeType,
    PipelineFailureStatus,
    TerminalErrorCode,
    TerminalRuntime,
    TerminalStage,
    build_terminal_outcome,
)
from verilogic_ns_api.validation_correction.cache import CorrectionResponseCache
from verilogic_ns_api.validation_correction.configuration import (
    PreparedCorrectionExperiment,
    load_correction_config,
    prepare_correction_experiment,
)
from verilogic_ns_api.validation_correction.feedback import validate_theory_candidate
from verilogic_ns_api.validation_correction.models import TaskKind, TheoryCorrectionInput
from verilogic_ns_api.validation_correction.prompts import render_correction_input
from verilogic_ns_api.validation_correction.provider import CorrectionTaskRequest
from verilogic_ns_api.validation_correction.raw import load_raw_phase5_candidates
from verilogic_ns_api.validation_correction.recovery_r2 import (
    EXPECTED_MODEL_DIGEST,
    ORIGINAL_CORRECTION_CONFIG,
    ORIGINAL_PARSER_CONFIG,
    RecoveryR2Error,
    assert_recovery_config_equivalent,
)

R2_FINAL_COMMIT = "3c6106d21288ed31829bd6eeb5db96e7d9ee9705"
R2_CACHE = "results/cache/semantic-parser-phase6-r2"
R3_CACHE = "results/cache/semantic-parser-phase6-r3"
R3_OUTPUT = "results/semantic-parsing-phase6-r3"
R3_CORRECTION_CACHE = "results/cache/validation-correction-phase6-r3"
R3_CORRECTION_OUTPUT = "results/validation-correction-phase6-r3"
R3_FREEZE_MANIFEST = "experiments/manifests/phase6-r3-terminal-failure-freeze.v1.json"
R3_TERMINAL_SCHEMA = "schemas/terminal-provider-outcome.v1.schema.json"
R3_1_AMENDMENT = "experiments/manifests/phase6-r3-1-terminal-hash-amendment.v1.json"
R3_2_AMENDMENT = "experiments/manifests/phase6-r3-2-terminal-replay-amendment.v1.json"
R3_3_AMENDMENT = "experiments/manifests/phase6-r3-3-null-accounting-propagation-amendment.v1.json"
R3_FREEZE_COMMIT = "f207515f6fab96bd9f785a0c42c4926a64b872c2"
MISSING_THEORY_REQUEST = "dc1e6278fc2d360bec7caba8d6d3459d26de3e1251a8683711faf93f498a23d9"
INVALID_QUERY_REQUEST = "4d6a1ff66e104bd60686e40fc4ad71fe35ef0833d8d3745016fe5f327eb2fded"
INTERRUPTED_CORRECTION_REQUEST = "31b97fc053418bf0c44b8cac49cc0a51a05d21870789da082253fa5d35954be8"

R2_EVIDENCE = {
    "cumulative": "results/semantic-parsing-phase6-r2/phase6-r2-1-cumulative-accounting.json",
    "attempt_1": (
        "results/semantic-parsing-phase6-r2/phase6-r2-1-phase5-live-v1/cache-ledger.json"
    ),
    "attempt_2": (
        "results/semantic-parsing-phase6-r2/phase6-r2-1-phase5-live-v2/cache-ledger.json"
    ),
}


class RecoveryR3Error(RecoveryR2Error):
    pass


def prepare_recovery_r3(
    path: Path,
    *,
    verify_freeze: bool = True,
) -> PreparedCorrectionExperiment:
    prepared = prepare_correction_experiment(path)
    original_parser = prepare_parser_experiment(prepared.root / ORIGINAL_PARSER_CONFIG)
    original_correction = load_correction_config(prepared.root / ORIGINAL_CORRECTION_CONFIG)
    assert_recovery_config_equivalent(
        original_parser.config,
        prepared.phase5.config,
        original_correction,
        prepared.config,
    )
    expected_paths = {
        prepared.phase5.config.cache_directory: R3_CACHE,
        prepared.phase5.config.output_directory: R3_OUTPUT,
        prepared.config.cache_directory: R3_CORRECTION_CACHE,
        prepared.config.output_directory: R3_CORRECTION_OUTPUT,
    }
    for actual, expected in expected_paths.items():
        if Path(actual).as_posix() != expected:
            raise RecoveryR3Error(f"R3 path is not isolated as frozen: {actual}")
    if prepared.config.runtime.model_digest != EXPECTED_MODEL_DIGEST:
        raise RecoveryR3Error("Phase 6-R3 model digest differs from the frozen contract")
    if verify_freeze:
        verify_r3_freeze(prepared)
        _verify_r3_3_accounting_amendment(prepared.root)
    return prepared


def r3_freeze_facts(prepared: PreparedCorrectionExperiment) -> dict[str, object]:
    root = prepared.root
    request_inventory = phase5_request_inventory(prepared.phase5)
    evidence = {name: file_sha256(root / path) for name, path in R2_EVIDENCE.items()}
    cache_inventory = r2_cache_inventory(root)
    return {
        "starting_checkpoint": R2_FINAL_COMMIT,
        "r2_final_commit": R2_FINAL_COMMIT,
        "r2_report_sha256": file_sha256(root / "docs/PHASE6_RECOVERY_R2_RESULTS.md"),
        "r2_freeze_manifest_sha256": file_sha256(
            root / "experiments/manifests/phase6-recovery-r2-freeze.v1.json"
        ),
        "r2_1_freeze_manifest_sha256": file_sha256(
            root / "experiments/manifests/phase6-recovery-r2-1-freeze.v1.json"
        ),
        "r2_cache_inventory_sha256": cache_inventory["inventory_sha256"],
        "r2_cache_files": cache_inventory["files"],
        "r2_failed_attempt_evidence": evidence,
        "phase5_r3_config_sha256": file_sha256(prepared.phase5.config_path),
        "phase6_r3_config_sha256": file_sha256(prepared.config_path),
        "development_manifest_sha256": prepared.phase5.config.pilot_manifest_sha256,
        "ordered_record_ids": [item.example_id for item in prepared.phase5.pilot_examples],
        "ordered_record_ids_sha256": sha256_payload(
            [item.example_id for item in prepared.phase5.pilot_examples]
        ),
        "phase5_request_manifest_sha256": sha256_payload(
            [item["request_hash"] for item in request_inventory]
        ),
        "logical_phase5_components": len(request_inventory),
        "unique_phase5_requests": len({item["request_hash"] for item in request_inventory}),
        "model_contract": {
            "provider": "ollama",
            "endpoint": prepared.config.runtime.endpoint,
            "provider_version": prepared.config.runtime.provider_version,
            "model": prepared.config.runtime.model,
            "model_digest": prepared.config.runtime.model_digest,
            "num_ctx": prepared.config.runtime.num_ctx,
            "temperature": prepared.config.runtime.temperature,
            "seed": prepared.config.runtime.seed,
            "think": prepared.config.runtime.think,
            "concurrency": 1,
        },
        "prompt_hashes": {
            "phase5_theory": prepared.phase5.config.theory_prompt_sha256,
            "phase5_query": prepared.phase5.config.query_prompt_sha256,
            "critic_theory": prepared.config.critic_theory_prompt_sha256,
            "critic_query": prepared.config.critic_query_prompt_sha256,
            "correction_theory": prepared.config.correction_theory_prompt_sha256,
            "correction_query": prepared.config.correction_query_prompt_sha256,
        },
        "schema_hashes": {
            "phase5_theory": prepared.phase5.config.theory_schema_sha256,
            "phase5_query": prepared.phase5.config.query_schema_sha256,
            "feedback": prepared.config.feedback_schema_sha256,
            "critic_theory": prepared.config.critic_theory_schema_sha256,
            "critic_query": prepared.config.critic_query_schema_sha256,
            "correction_theory": prepared.config.correction_theory_schema_sha256,
            "correction_query": prepared.config.correction_query_schema_sha256,
            "terminal_outcome_file_sha256": file_sha256(root / R3_TERMINAL_SCHEMA),
        },
        "reliability_policy_sha256": prepared.config.reliability_policy.policy_hash,
        "semantic_configuration_sha256": semantic_config_hash(prepared.phase5),
        "paths": {
            "source_cache_read_only": R2_CACHE,
            "phase5_cache": R3_CACHE,
            "phase5_output": R3_OUTPUT,
            "phase6_cache": R3_CORRECTION_CACHE,
            "phase6_output": R3_CORRECTION_OUTPUT,
        },
    }


def verify_r3_freeze(prepared: PreparedCorrectionExperiment) -> None:
    path = prepared.root / R3_FREEZE_MANIFEST
    if not path.is_file():
        raise RecoveryR3Error("Phase 6-R3 freeze manifest is missing")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    facts = r3_freeze_facts(prepared)
    frozen_facts = manifest.get("frozen_facts")
    if frozen_facts != facts and not _verify_r3_1_schema_amendment(
        prepared.root, frozen_facts, facts
    ):
        raise RecoveryR3Error("Phase 6-R3 frozen facts differ from current artifacts")
    if manifest.get("test_split_forbidden") is not True:
        raise RecoveryR3Error("Phase 6-R3 test-split prohibition is missing")
    if manifest.get("maximum_semantic_corrections_per_component") != 1:
        raise RecoveryR3Error("Phase 6-R3 correction bound differs from the frozen policy")
    if manifest.get("maximum_new_phase6_unique_local_tasks") != 180:
        raise RecoveryR3Error("Phase 6-R3 local-call budget differs from the frozen policy")


def phase5_request_inventory(prepared: PreparedParserExperiment) -> list[dict[str, str]]:
    return [
        {
            "kind": kind,
            "component": component,
            "request_hash": request.request_hash,
            "input_hash": request.input_hash,
        }
        for kind, component, request, _, _ in _phase5_requests(prepared)
    ]


def materialize_r3_phase5(prepared: PreparedCorrectionExperiment) -> dict[str, object]:
    root = prepared.root
    source_root = root / R2_CACHE
    destination_cache = ParserResponseCache(root / R3_CACHE)
    if not source_root.is_dir():
        raise RecoveryR3Error("preserved R2 parser cache is unavailable")
    _validate_failed_attempt_evidence(root)

    provenance: list[dict[str, object]] = []
    unique_requests: dict[
        str, tuple[str, str, StructuredRequest, type[BaseModel], TerminalStage]
    ] = {}
    logical_requests = _phase5_requests(prepared.phase5)
    for item in logical_requests:
        unique_requests.setdefault(item[2].request_hash, item)
    if len(logical_requests) != 58 or len(unique_requests) != 57:
        raise RecoveryR3Error("frozen Phase 5 request topology changed")

    counts: Counter[str] = Counter()
    for request_hash, (kind, component, request, model, stage) in sorted(unique_requests.items()):
        source = source_root / request_hash[:2] / f"{request_hash}.json"
        if source.is_file():
            payload = json.loads(source.read_text(encoding="utf-8"))
            if payload.get("request_identity") != request.identity():
                raise RecoveryR3Error(f"R2 cache contract mismatch for {request_hash}")
            response = ParserResponse.model_validate(payload.get("response"))
            _verify_response_contract(response, request)
            try:
                model.model_validate(response.content)
            except ValidationError as error:
                if request_hash != INVALID_QUERY_REQUEST:
                    raise RecoveryR3Error(
                        f"unexpected invalid R2 structured output: {request_hash}"
                    ) from error
                terminal = _invalid_cached_response_terminal(
                    prepared.phase5, request, response, source, stage
                )
                destination_cache.store_terminal(request, terminal)
                counts["terminal_error"] += 1
                provenance.append(
                    _provenance(
                        request,
                        kind,
                        component,
                        source,
                        destination_cache.path_for(request),
                        "TERMINAL_ERROR",
                        terminal.terminal_outcome_sha256,
                    )
                )
                continue
            _atomic_copy_identical(source, destination_cache.path_for(request))
            counts["success"] += 1
            provenance.append(
                _provenance(
                    request,
                    kind,
                    component,
                    source,
                    destination_cache.path_for(request),
                    "SUCCESS",
                )
            )
            continue
        if request_hash != MISSING_THEORY_REQUEST:
            raise RecoveryR3Error(f"unexpected missing R2 cache entry: {request_hash}")
        terminal = _exhausted_r2_terminal(prepared.phase5, request, stage, root)
        destination_cache.store_terminal(request, terminal)
        counts["terminal_error"] += 1
        provenance.append(
            {
                "kind": kind,
                "component": component,
                "request_hash": request_hash,
                "outcome_type": "TERMINAL_ERROR",
                "terminal_outcome_sha256": terminal.terminal_outcome_sha256,
                "inherited_evidence": {
                    name: file_sha256(root / path) for name, path in R2_EVIDENCE.items()
                },
            }
        )

    logical = Counter()
    terminal_fanout: Counter[str] = Counter()
    for _, _, request, _, _ in logical_requests:
        lookup = destination_cache.load_outcome(request)
        if lookup is None:
            raise RecoveryR3Error("R3 materialization left a cache miss")
        logical[lookup.outcome_type.value] += 1
        if lookup.terminal_error is not None:
            terminal_fanout[lookup.terminal_error.error_code.value] += 1
    if sum(logical.values()) != 58:
        raise RecoveryR3Error("R3 materialization did not resolve all logical components")
    if counts != Counter({"success": 55, "terminal_error": 2}):
        raise RecoveryR3Error(f"verified R3 outcome inventory differs: {dict(counts)}")

    report = {
        "schema_version": "1.0",
        "status": "complete",
        "source_cache": R2_CACHE,
        "destination_cache": R3_CACHE,
        "copy_method": "byte-identical for schema-valid successes",
        "logical_components": len(logical_requests),
        "unique_requests": len(unique_requests),
        "unique_successes": counts["success"],
        "unique_terminal_errors": counts["terminal_error"],
        "logical_successes": logical[CachedOutcomeType.SUCCESS.value],
        "logical_terminal_errors": logical[CachedOutcomeType.TERMINAL_ERROR.value],
        "terminal_logical_fanout": dict(sorted(terminal_fanout.items())),
        "phase5_provider_calls": 0,
        "new_inference_tokens": 0,
        "hosted_provider_calls": 0,
        "external_transmissions": 0,
        "api_cost_usd": 0.0,
        "provenance": provenance,
        "inventory_sha256": sha256_payload(provenance),
    }
    output = root / R3_OUTPUT / "phase5-r3-materialization.json"
    _atomic_json(output, report)
    return report


def materialize_r3_1_interrupted_terminal(
    prepared: PreparedCorrectionExperiment,
) -> dict[str, object]:
    """Seal the preregistered interrupted/invalid Phase 6 request without dispatch."""
    root = prepared.root
    amendment_path = root / R3_1_AMENDMENT
    if not amendment_path.is_file():
        raise RecoveryR3Error("Phase 6-R3.1 amendment is missing")
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    if not _verify_r3_1_schema_amendment(
        root,
        json.loads((root / R3_FREEZE_MANIFEST).read_text(encoding="utf-8"))["frozen_facts"],
        r3_freeze_facts(prepared),
    ):
        raise RecoveryR3Error("Phase 6-R3.1 amendment contract is invalid")
    evidence = amendment["interruption_evidence"]
    for item in evidence["files"]:
        if file_sha256(root / item["path"]) != item["sha256"]:
            raise RecoveryR3Error(f"R3.1 evidence hash mismatch: {item['path']}")

    request = _invalid_theory_correction_by_hash(prepared, INTERRUPTED_CORRECTION_REQUEST)
    if request.request_hash != INTERRUPTED_CORRECTION_REQUEST:
        raise RecoveryR3Error("R3.1 interrupted request identity differs")
    cache = CorrectionResponseCache(root / prepared.config.cache_directory)
    existing = cache.load_outcome(request)
    if existing is not None:
        if (
            existing.outcome_type is CachedOutcomeType.TERMINAL_ERROR
            and existing.terminal_error is not None
            and existing.terminal_error.request_hash == request.request_hash
        ):
            _verify_r3_2_replay_amendment(root)
            return {
                "schema_version": "1.0",
                "status": "already_materialized",
                "request_hash": request.request_hash,
                "terminal_outcome_sha256": (existing.terminal_error.terminal_outcome_sha256),
                "provider_calls": 0,
            }
        raise RecoveryR3Error("R3.1 interrupted request unexpectedly has a success cache entry")

    prior_cache = amendment["prior_phase6_cache"]
    current_cache = _cache_file_inventory(root / R3_CORRECTION_CACHE)
    if current_cache["records"] != prior_cache["files"]:
        raise RecoveryR3Error("Phase 6-R3.1 prior success cache inventory differs")
    if current_cache["inventory_sha256"] != prior_cache["canonical_inventory_sha256"]:
        raise RecoveryR3Error("Phase 6-R3.1 prior success cache hash differs")

    attempts = tuple(
        AttemptEvidence(
            attempt_number=item["attempt_number"],
            request_hash=request.request_hash,
            evidence_sha256=sha256_payload(
                {
                    "namespace": "phase6-r3-1-interrupted-attempt.v1",
                    "request_hash": request.request_hash,
                    "attempt_number": item["attempt_number"],
                    "finish_reason": item["finish_reason"],
                    "evidence_sha256": item["evidence_sha256"],
                }
            ),
            finish_reason=item["finish_reason"],
            input_tokens=None,
            output_tokens=None,
            total_duration_ms=None,
            observed_at=datetime.fromisoformat(item["observed_at"].replace("Z", "+00:00")),
        )
        for item in evidence["attempts"]
    )
    runtime = prepared.config.runtime
    terminal = build_terminal_outcome(
        stage=TerminalStage.THEORY_CORRECTION,
        error_code=TerminalErrorCode.INVALID_STRUCTURED_OUTPUT,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason=(
            "The first execution was interrupted and the final permitted execution returned "
            "a theory that failed the frozen structured-output schema."
        ),
        request_identity=request.identity(),
        semantic_config_hash=sha256_payload(
            {
                "runtime": runtime.model_dump(mode="json"),
                "limits": prepared.config.limits.model_dump(mode="json"),
            }
        ),
        runtime=TerminalRuntime(
            endpoint=runtime.endpoint,
            provider_version=runtime.provider_version,
            model=runtime.model,
            model_digest=runtime.model_digest,
            temperature=runtime.temperature,
            seed=runtime.seed,
            num_ctx=runtime.num_ctx,
            num_predict=request.num_predict,
            think=runtime.think,
        ),
        permitted_attempt_count=runtime.max_attempts,
        attempts=attempts,
    )
    cache.store_terminal(request, terminal)
    report = {
        "schema_version": "1.0",
        "status": "complete",
        "request_hash": request.request_hash,
        "stage": terminal.stage,
        "error_code": terminal.error_code,
        "pipeline_status": terminal.pipeline_status,
        "observed_attempts": terminal.observed_attempt_count,
        "terminal_outcome_sha256": terminal.terminal_outcome_sha256,
        "token_accounting": "unavailable_after_client_interruption_and_pre-cache_crash",
        "provider_calls": 0,
        "hosted_provider_calls": 0,
        "external_transmissions": 0,
        "api_cost_usd": 0.0,
    }
    _atomic_json(root / R3_OUTPUT / "phase6-r3-1-terminal-materialization.json", report)
    return report


def r2_cache_inventory(root: Path) -> dict[str, object]:
    return _cache_file_inventory(root / R2_CACHE)


def _cache_file_inventory(cache_root: Path) -> dict[str, object]:
    records = [
        {
            "relative_path": path.relative_to(cache_root).as_posix(),
            "sha256": file_sha256(path),
            "size": path.stat().st_size,
        }
        for path in sorted(cache_root.rglob("*.json"))
    ]
    return {
        "files": len(records),
        "inventory_sha256": sha256_payload(records),
        "records": records,
    }


def _verify_r3_1_schema_amendment(
    root: Path,
    frozen_facts: object,
    current_facts: object,
) -> bool:
    if not isinstance(frozen_facts, dict) or not isinstance(current_facts, dict):
        return False
    amendment_path = root / R3_1_AMENDMENT
    if not amendment_path.is_file():
        return False
    try:
        amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
        frozen_copy = json.loads(json.dumps(frozen_facts))
        current_copy = json.loads(json.dumps(current_facts))
        frozen_schema = frozen_copy["schema_hashes"]["terminal_outcome_file_sha256"]
        current_schema = current_copy["schema_hashes"]["terminal_outcome_file_sha256"]
        current_copy["schema_hashes"]["terminal_outcome_file_sha256"] = frozen_schema
        return (
            current_copy == frozen_copy
            and amendment["amends_freeze_commit"] == R3_FREEZE_COMMIT
            and amendment["amends_manifest"] == R3_FREEZE_MANIFEST
            and amendment["amends_manifest_sha256"] == file_sha256(root / R3_FREEZE_MANIFEST)
            and amendment["previous_terminal_outcome_schema_sha256"] == frozen_schema
            and amendment["amended_terminal_outcome_schema_sha256"] == current_schema
            and amendment["development_metrics_examined"] is False
            and amendment["prediction_sets_sealed"] is False
            and amendment["performance_based_change"] is False
        )
    except (KeyError, TypeError, ValueError, OSError):
        return False


def semantic_config_hash(prepared: PreparedParserExperiment) -> str:
    return sha256_payload(
        prepared.config.model_dump(exclude={"name", "cache_directory", "output_directory"})
    )


def _phase5_requests(
    prepared: PreparedParserExperiment,
) -> list[tuple[str, str, StructuredRequest, type[BaseModel], TerminalStage]]:
    theory_views: dict[str, Any] = {}
    for example in prepared.pilot_examples:
        key = example.theory_id or example.example_id
        view = prepare_theory_view(example)
        if key in theory_views:
            assert_same_theory(theory_views[key], view)
        else:
            theory_views[key] = view
    requests = [
        (
            "theory",
            key,
            _parser_request(
                prepared,
                "theory",
                view.public.input_hash,
                render_theory_input(view.public),
            ),
            CandidateTheoryOutput,
            TerminalStage.SEMANTIC_PARSER_THEORY,
        )
        for key, view in sorted(theory_views.items())
    ]
    requests.extend(
        (
            "query",
            example.example_id,
            _parser_request(
                prepared,
                "query",
                prepare_query_view(example).public.input_hash,
                render_query_input(prepare_query_view(example).public),
            ),
            CandidateQueryOutput,
            TerminalStage.SEMANTIC_PARSER_QUERY,
        )
        for example in prepared.pilot_examples
    )
    return requests


def _invalid_theory_correction_by_hash(
    prepared: PreparedCorrectionExperiment,
    expected_request_hash: str,
) -> CorrectionTaskRequest:
    raw = load_raw_phase5_candidates(prepared.phase5, calibration=False)
    prompt, prompt_hash = prepared.prompts[TaskKind.CORRECTION_THEORY]
    schema = CandidateTheoryOutput.model_json_schema()
    for key, view in sorted(raw.theory_views.items()):
        validation = validate_theory_candidate(raw.theories[key], view, theory_id=key)
        if validation.valid:
            continue
        value = TheoryCorrectionInput(
            source=view.public,
            previous_candidate=(raw.theories[key] if isinstance(raw.theories[key], dict) else {}),
            validator_feedback=validation.feedback,
            critic_report=None,
        )
        request = CorrectionTaskRequest(
            task_kind=TaskKind.CORRECTION_THEORY,
            instructions=prompt,
            input_text=render_correction_input(value),
            prompt_hash=prompt_hash,
            input_hash=sha256_payload(value.model_dump(mode="json")),
            output_schema=schema,
            schema_hash=sha256_payload(schema),
            num_predict=prepared.config.limits.correction_theory_num_predict,
            config=prepared.config.runtime,
        )
        if request.request_hash == expected_request_hash:
            return request
    raise RecoveryR3Error("R3.1 could not reconstruct the interrupted correction request")


def _verify_r3_2_replay_amendment(root: Path) -> None:
    path = root / R3_2_AMENDMENT
    if not path.is_file():
        raise RecoveryR3Error("Phase 6-R3.2 replay amendment is missing")
    amendment = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "amends_commit": "67ec57e9c4aee4b2cc8e74970adb8469d8fe5891",
        "amends_manifest_sha256": file_sha256(root / R3_1_AMENDMENT),
        "terminal_request_hash": INTERRUPTED_CORRECTION_REQUEST,
        "terminal_cache_sha256": file_sha256(
            root
            / R3_CORRECTION_CACHE
            / "semantic-correction-v1"
            / "31"
            / f"{INTERRUPTED_CORRECTION_REQUEST}.json"
        ),
        "materialization_report_sha256": file_sha256(
            root / R3_OUTPUT / "phase6-r3-1-terminal-materialization.json"
        ),
        "development_metrics_examined": False,
        "performance_based_change": False,
    }
    if any(amendment.get(key) != value for key, value in expected.items()):
        raise RecoveryR3Error("Phase 6-R3.2 replay amendment differs from preserved evidence")


def _verify_r3_3_accounting_amendment(root: Path) -> None:
    path = root / R3_3_AMENDMENT
    if not path.is_file():
        raise RecoveryR3Error("Phase 6-R3.3 accounting amendment is missing")
    amendment = json.loads(path.read_text(encoding="utf-8"))
    evidence = amendment["failed_resume_evidence"]
    expected = {
        "amends_commit": "e2c486fce2e48abf157d2558b87569139f1e3768",
        "amends_manifest_sha256": file_sha256(root / R3_2_AMENDMENT),
        "development_metrics_examined": False,
        "prediction_sets_sealed": False,
        "performance_based_change": False,
    }
    if any(amendment.get(key) != value for key, value in expected.items()):
        raise RecoveryR3Error("Phase 6-R3.3 amendment differs from the frozen contract")
    for kind in ("stderr", "stdout", "run_state"):
        item = evidence[kind]
        if file_sha256(root / item["path"]) != item["sha256"]:
            raise RecoveryR3Error(f"Phase 6-R3.3 {kind} evidence hash differs")
    terminal_path = (
        root
        / R3_CORRECTION_CACHE
        / "semantic-correction-v1"
        / "31"
        / f"{INTERRUPTED_CORRECTION_REQUEST}.json"
    )
    if file_sha256(terminal_path) != evidence["terminal_cache_sha256"]:
        raise RecoveryR3Error("Phase 6-R3.3 terminal cache evidence differs")
    if evidence["provider_calls"] != 0 or evidence["new_cache_entries"] != 0:
        raise RecoveryR3Error("Phase 6-R3.3 failed resume accounting is not zero-call")


def _parser_request(
    prepared: PreparedParserExperiment,
    kind: str,
    input_hash: str,
    rendered: str,
) -> StructuredRequest:
    theory = kind == "theory"
    model = CandidateTheoryOutput if theory else CandidateQueryOutput
    schema = model.model_json_schema()
    return StructuredRequest(
        kind=kind,
        instructions=prepared.theory_prompt if theory else prepared.query_prompt,
        input_text=rendered,
        prompt_hash=(
            prepared.config.theory_prompt_sha256 if theory else prepared.config.query_prompt_sha256
        ),
        input_hash=input_hash,
        output_schema=schema,
        schema_hash=sha256_payload(schema),
        config=prepared.config.runtime,
    )


def _runtime(prepared: PreparedParserExperiment, *, num_predict: int) -> TerminalRuntime:
    config = prepared.config.runtime
    return TerminalRuntime(
        endpoint=config.endpoint,
        provider_version=config.provider_version,
        model=config.model,
        model_digest=config.model_digest,
        temperature=config.temperature,
        seed=config.seed,
        num_ctx=config.num_ctx,
        num_predict=num_predict,
        think=config.think,
    )


def _invalid_cached_response_terminal(
    prepared: PreparedParserExperiment,
    request: StructuredRequest,
    response: ParserResponse,
    source: Path,
    stage: TerminalStage,
):
    evidence = sha256_payload(
        {
            "namespace": "phase6-r3-invalid-r2-response.v1",
            "source_sha256": file_sha256(source),
            "request_hash": request.request_hash,
            "response_content_sha256": sha256_payload(response.content),
            "validation_target": "CandidateQueryOutput",
        }
    )
    attempt = AttemptEvidence(
        attempt_number=1,
        request_hash=request.request_hash,
        evidence_sha256=evidence,
        finish_reason="invalid_structured_output",
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        total_duration_ms=response.timing.total_duration_ms,
        observed_at=response.completed_at,
    )
    return build_terminal_outcome(
        stage=stage,
        error_code=TerminalErrorCode.INVALID_STRUCTURED_OUTPUT,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason="Preserved R2 provider response failed the frozen query output schema.",
        request_identity=request.identity(),
        semantic_config_hash=semantic_config_hash(prepared),
        runtime=_runtime(prepared, num_predict=request.config.query_num_predict),
        permitted_attempt_count=request.config.max_attempts,
        attempts=(attempt,),
    )


def _exhausted_r2_terminal(
    prepared: PreparedParserExperiment,
    request: StructuredRequest,
    stage: TerminalStage,
    root: Path,
):
    evidence_hashes = {name: file_sha256(root / path) for name, path in R2_EVIDENCE.items()}
    observed = (
        (1, 940, "2026-07-28T21:50:55Z", 595577.47, evidence_hashes["attempt_1"]),
        (2, 1008, "2026-07-28T22:41:22Z", 563528.38, evidence_hashes["attempt_2"]),
    )
    attempts = tuple(
        AttemptEvidence(
            attempt_number=number,
            request_hash=request.request_hash,
            evidence_sha256=sha256_payload(
                {
                    "namespace": "phase6-r3-exhausted-r2-attempt.v1",
                    "request_hash": request.request_hash,
                    "attempt_number": number,
                    "attempt_ledger_sha256": ledger_hash,
                    "cumulative_accounting_sha256": evidence_hashes["cumulative"],
                    "input_tokens": input_tokens,
                    "output_tokens": 4096,
                    "total_duration_ms": duration,
                    "completed_at": timestamp,
                }
            ),
            finish_reason="output_limit",
            input_tokens=input_tokens,
            output_tokens=4096,
            total_duration_ms=duration,
            observed_at=datetime.fromisoformat(timestamp.replace("Z", "+00:00")),
        )
        for number, input_tokens, timestamp, duration, ledger_hash in observed
    )
    return build_terminal_outcome(
        stage=stage,
        error_code=TerminalErrorCode.OUTPUT_LIMIT_EXHAUSTED,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason=(
            "Both frozen R2 attempts exhausted the 4,096-token output limit without "
            "a valid structured theory."
        ),
        request_identity=request.identity(),
        semantic_config_hash=semantic_config_hash(prepared),
        runtime=_runtime(prepared, num_predict=request.config.theory_num_predict),
        permitted_attempt_count=request.config.max_attempts,
        attempts=attempts,
    )


def _validate_failed_attempt_evidence(root: Path) -> None:
    cumulative = json.loads((root / R2_EVIDENCE["cumulative"]).read_text(encoding="utf-8"))
    blocked = cumulative["blocked_request"]
    required = {
        "request_hash": MISSING_THEORY_REQUEST,
        "failed_dispatches": 2,
        "server_observed_generation_tokens": 8192,
        "server_observed_prompt_evaluation_tokens": 1948,
        "status": "STRUCTURED_OUTPUT_ERROR",
        "type": "ParserStructuredOutputError",
    }
    for key, value in required.items():
        if blocked.get(key) != value:
            raise RecoveryR3Error(f"R2 terminal evidence mismatch: {key}")
    for name in ("attempt_1", "attempt_2"):
        ledger = json.loads((root / R2_EVIDENCE[name]).read_text(encoding="utf-8"))
        matches = [
            item for item in ledger["operations"] if item["request_hash"] == MISSING_THEORY_REQUEST
        ]
        if len(matches) != 1:
            raise RecoveryR3Error(f"R2 {name} does not bind exactly one terminal request")
        if matches[0]["status"] != "STRUCTURED_OUTPUT_ERROR":
            raise RecoveryR3Error(f"R2 {name} terminal status differs")


def _verify_response_contract(response: ParserResponse, request: StructuredRequest) -> None:
    if response.request_hash != request.request_hash:
        raise RecoveryR3Error("R2 cache response belongs to another request")
    runtime = request.config
    if (
        response.configured_model != runtime.model
        or response.returned_model != runtime.model
        or response.model_digest != runtime.model_digest
        or response.provider_version != runtime.provider_version
    ):
        raise RecoveryR3Error("R2 cache response model contract differs")


def _provenance(
    request: StructuredRequest,
    kind: str,
    component: str,
    source: Path,
    destination: Path,
    outcome_type: str,
    terminal_hash: str | None = None,
) -> dict[str, object]:
    source_hash = file_sha256(source)
    destination_hash = file_sha256(destination)
    if outcome_type == "SUCCESS" and source_hash != destination_hash:
        raise RecoveryR3Error("R3 success copy is not byte-identical")
    payload: dict[str, object] = {
        "kind": kind,
        "component": component,
        "request_hash": request.request_hash,
        "prompt_hash": request.prompt_hash,
        "schema_hash": request.schema_hash,
        "outcome_type": outcome_type,
        "source_sha256": source_hash,
        "destination_sha256": destination_hash,
        "byte_identical": outcome_type == "SUCCESS",
    }
    if terminal_hash is not None:
        payload["terminal_outcome_sha256"] = terminal_hash
    return payload


def _atomic_copy_identical(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        if file_sha256(source) != file_sha256(destination):
            raise RecoveryR3Error("existing R3 cache destination differs from R2 evidence")
        return
    handle, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    try:
        with source.open("rb") as source_stream, os.fdopen(handle, "wb") as target:
            while chunk := source_stream.read(1024 * 1024):
                target.write(chunk)
            target.flush()
            os.fsync(target.fileno())
        if file_sha256(source) != file_sha256(Path(temporary)):
            raise RecoveryR3Error("R3 cache copy hash verification failed")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


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
