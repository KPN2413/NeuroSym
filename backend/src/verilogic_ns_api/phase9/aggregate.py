from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from verilogic_ns_api.baselines.configuration import file_sha256
from verilogic_ns_api.baselines.selection import load_manifest, load_selected_examples
from verilogic_ns_api.datasets.proofwriter import ProofWriterLoader
from verilogic_ns_api.evaluation.metrics import compute_metrics
from verilogic_ns_api.phase9.freeze import canonical_json_hash
from verilogic_ns_api.phase9.models import (
    ComparisonKind,
    Phase9AggregateReport,
    Phase9Comparison,
    Phase9ConditionAggregate,
    Phase9FreezeManifest,
)
from verilogic_ns_api.research.models import MetricReport, PredictionRecord

PROTOCOL_LABEL = "Phase 9 regenerated evidence under newly frozen protocol"


def build_aggregate(
    *,
    root: Path,
    freeze: Phase9FreezeManifest,
    archive: Path,
    direct_run: Path,
    few_shot_run: Path,
    semantic_run: Path,
    correction_run: Path,
    oracle_run: Path,
    replay_verified: bool,
) -> Phase9AggregateReport:
    manifest = load_manifest(root / "experiments/manifests/phase9-regenerated-dev.v1.json")
    examples = load_selected_examples(
        ProofWriterLoader(archive, dataset_version="V2020.12.3"), manifest
    )
    conditions: list[Phase9ConditionAggregate] = []

    direct = _baseline_condition(
        root=root,
        examples=examples,
        run=direct_run,
        condition="direct",
        experiment_id="phase9-regenerated-direct",
        config="experiments/configs/ollama-direct-phase9.yaml",
        freeze=freeze,
    )
    few = _baseline_condition(
        root=root,
        examples=examples,
        run=few_shot_run,
        condition="few_shot",
        experiment_id="phase9-regenerated-few-shot",
        config="experiments/configs/ollama-few-shot-phase9.yaml",
        freeze=freeze,
    )
    conditions.extend((direct, few))

    semantic_report = _json(semantic_run / "metrics.json")
    correction_report = _json(correction_run / "report.json")
    p0_proof = semantic_report["proof_verification"]
    p1_proof = correction_report["p1_corrected_valid"]["proof_verification"]
    p2_proof = correction_report["p2_corrected_selective"]["proof_verification"]
    phase5_calls = int(semantic_report["efficiency"]["provider_requests"])
    correction_calls = int(correction_report["efficiency"]["new_local_calls"])
    semantic_input_tokens = int(semantic_report["efficiency"]["input_tokens"])
    semantic_output_tokens = int(semantic_report["efficiency"]["output_tokens"])
    correction_observed_input = int(correction_report["efficiency"]["observed_input_tokens"])
    correction_observed_output = int(correction_report["efficiency"]["observed_output_tokens"])
    correction_wall = float(correction_report["wall_seconds"])
    parser_wall = float(semantic_report["efficiency"]["wall_seconds"])
    correction_config = "experiments/configs/ollama-validation-correction-phase9.yaml"
    semantic_config = "experiments/configs/ollama-semantic-parser-phase9.yaml"
    condition_specs = (
        (
            "p0_raw_neuro_symbolic",
            "P0_RAW",
            correction_run / "p0-predictions.jsonl",
            phase5_calls,
            parser_wall,
            p0_proof,
            semantic_config,
        ),
        (
            "validation_only",
            "VALIDATION_ONLY",
            correction_run / "validation-only-predictions.jsonl",
            phase5_calls,
            parser_wall,
            p0_proof,
            correction_config,
        ),
        (
            "p1_corrected_valid",
            "P1_CORRECTED",
            correction_run / "p1-predictions.jsonl",
            phase5_calls + correction_calls,
            parser_wall + correction_wall,
            p1_proof,
            correction_config,
        ),
        (
            "p2_corrected_selective",
            "P2_SELECTIVE",
            correction_run / "p2-predictions.jsonl",
            phase5_calls + correction_calls,
            parser_wall + correction_wall,
            p2_proof,
            correction_config,
        ),
    )
    for name, policy, records, calls, runtime, proof, config in condition_specs:
        metrics = compute_metrics(examples, _predictions(records))
        corrected = name in {"p1_corrected_valid", "p2_corrected_selective"}
        conditions.append(
            Phase9ConditionAggregate(
                experiment_id=f"phase9-regenerated-{name.replace('_', '-')}",
                condition=name,
                policy_mode=policy,
                selection_manifest_hash=freeze.selection_manifest_hash,
                model=freeze.model,
                model_digest=freeze.model_digest,
                config_hash=file_sha256(root / config),
                cache_mode="live-local-with-content-addressed-cache",
                provider_call_count=calls,
                runtime_seconds=runtime,
                telemetry_complete=not corrected,
                input_tokens=None if corrected else semantic_input_tokens,
                output_tokens=None if corrected else semantic_output_tokens,
                observed_input_tokens=(
                    semantic_input_tokens + correction_observed_input
                    if corrected
                    else semantic_input_tokens
                ),
                observed_output_tokens=(
                    semantic_output_tokens + correction_observed_output
                    if corrected
                    else semantic_output_tokens
                ),
                metrics=metrics,
                proof_attempted=int(proof["attempted"]) if proof else None,
                proof_verified=int(proof["verified"]) if proof else None,
                raw_records_sha256=file_sha256(records),
                limitations=(
                    "Development-only 30-record regenerated evidence; no significance claim.",
                ),
            )
        )

    oracle_report = _json(oracle_run / "report.json")
    oracle_records = oracle_run / "predictions.jsonl"
    oracle_metrics = compute_metrics(examples, _predictions(oracle_records))
    conditions.append(
        Phase9ConditionAggregate(
            experiment_id="phase9-regenerated-oracle-structure-ceiling",
            condition="oracle_structure_symbolic_ceiling",
            policy_mode="FORMAL_ORACLE",
            selection_manifest_hash=freeze.selection_manifest_hash,
            model=None,
            model_digest=None,
            config_hash=freeze.freeze_hash,
            cache_mode="not_applicable",
            provider_call_count=0,
            runtime_seconds=float(oracle_report["wall_seconds"]),
            telemetry_complete=True,
            input_tokens=0,
            output_tokens=0,
            observed_input_tokens=0,
            observed_output_tokens=0,
            metrics=oracle_metrics,
            proof_attempted=int(oracle_report["proof_attempted"]),
            proof_verified=int(oracle_report["proof_verified"]),
            raw_records_sha256=file_sha256(oracle_records),
            limitations=("Formal S-expression ceiling; not a natural-language end-to-end result.",),
        )
    )

    by_name = {item.condition: item for item in conditions}
    predictions_by_name = {
        "direct": _predictions(direct_run / "predictions.jsonl"),
        "few_shot": _predictions(few_shot_run / "predictions.jsonl"),
        **{
            name: _predictions(records)
            for name, _policy, records, _calls, _runtime, _proof, _config in condition_specs
        },
        "oracle_structure_symbolic_ceiling": _predictions(oracle_records),
    }
    comparisons = (
        _comparison(
            by_name,
            predictions_by_name,
            examples,
            "direct",
            "few_shot",
            "six fixed training demonstrations",
        ),
        _comparison(
            by_name,
            predictions_by_name,
            examples,
            "p0_raw_neuro_symbolic",
            "validation_only",
            "deterministic validation rejection",
        ),
        _comparison(
            by_name,
            predictions_by_name,
            examples,
            "p0_raw_neuro_symbolic",
            "p1_corrected_valid",
            "typed critic and one bounded correction",
        ),
        _comparison(
            by_name,
            predictions_by_name,
            examples,
            "p1_corrected_valid",
            "p2_corrected_selective",
            "critic-acceptance abstention gate",
        ),
        _comparison(
            by_name,
            predictions_by_name,
            examples,
            "p2_corrected_selective",
            "oracle_structure_symbolic_ceiling",
            "gold formal representation replaces natural-language parsing",
            representation=True,
        ),
    )
    payload = {
        "schema_version": "1.0",
        "protocol_label": PROTOCOL_LABEL,
        "status": "COMPLETE",
        "execution_commit": _git_commit(root),
        "freeze_hash": freeze.freeze_hash,
        "archive_sha256": freeze.archive_sha256,
        "selection_manifest_hash": freeze.selection_manifest_hash,
        "test_split_used": False,
        "test_split_access_count": 0,
        "hosted_provider_calls": 0,
        "external_transfers": 0,
        "local_provider_dispatches": (
            direct.provider_call_count + few.provider_call_count + phase5_calls + correction_calls
        ),
        "api_cost_usd": 0.0,
        "conditions": [item.model_dump(mode="json") for item in conditions],
        "comparisons": [item.model_dump(mode="json") for item in comparisons],
        "replay_verified": replay_verified,
        "limitations": [
            "ProofWriter licence remains unverified.",
            "The archive checksum is locally observed, not publisher verified.",
            "The development-only sample contains 30 records and supports no significance claim.",
            "Historical Phase 3-8 caches were not restored or reconstructed.",
        ],
    }
    payload["report_fingerprint"] = canonical_json_hash(payload)
    return Phase9AggregateReport.model_validate(payload)


def write_aggregate(path: Path, report: Phase9AggregateReport, *, check: bool = False) -> None:
    rendered = json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    if check:
        if not path.is_file() or path.read_text(encoding="utf-8") != rendered:
            raise ValueError("Phase 9 aggregate is stale")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(rendered)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _baseline_condition(*, root, examples, run, condition, experiment_id, config, freeze):
    records = run / "predictions.jsonl"
    observed = _predictions(records)
    metrics = compute_metrics(examples, observed)
    stored = MetricReport.model_validate_json((run / "metrics.json").read_text(encoding="utf-8"))
    if metrics != stored:
        raise ValueError(f"{condition} metrics do not reproduce from raw JSONL")
    calls = sum(item.cache_hit is False for item in observed)
    return Phase9ConditionAggregate(
        experiment_id=experiment_id,
        condition=condition,
        policy_mode=None,
        selection_manifest_hash=freeze.selection_manifest_hash,
        model=freeze.model,
        model_digest=freeze.model_digest,
        config_hash=file_sha256(root / config),
        cache_mode="live-local-with-content-addressed-cache",
        provider_call_count=calls,
        runtime_seconds=metrics.non_cache_total_latency_ms / 1000,
        telemetry_complete=True,
        input_tokens=metrics.input_tokens,
        output_tokens=metrics.output_tokens,
        observed_input_tokens=metrics.input_tokens,
        observed_output_tokens=metrics.output_tokens,
        metrics=metrics,
        raw_records_sha256=file_sha256(records),
        limitations=("Development-only 30-record regenerated evidence; no significance claim.",),
    )


def _comparison(
    by_name,
    predictions_by_name,
    examples,
    baseline,
    changed,
    component,
    *,
    representation=False,
):
    left = by_name[baseline]
    right = by_name[changed]
    gold = {item.example_id: item.gold_label.value for item in examples}
    left_predictions = {
        item.example_id: item.predicted_label.value for item in predictions_by_name[baseline]
    }
    right_predictions = {
        item.example_id: item.predicted_label.value for item in predictions_by_name[changed]
    }
    counts = {
        "both_correct": 0,
        "baseline_only_correct": 0,
        "changed_only_correct": 0,
        "both_incorrect": 0,
    }
    matrix: dict[str, dict[str, int]] = {}
    for example_id, expected in sorted(gold.items()):
        left_label = left_predictions[example_id]
        right_label = right_predictions[example_id]
        left_correct = left_label == expected
        right_correct = right_label == expected
        key = (
            "both_correct"
            if left_correct and right_correct
            else "baseline_only_correct"
            if left_correct
            else "changed_only_correct"
            if right_correct
            else "both_incorrect"
        )
        counts[key] += 1
        matrix.setdefault(left_label, {}).setdefault(right_label, 0)
        matrix[left_label][right_label] += 1
    return Phase9Comparison(
        comparison_id=f"phase9-{baseline}-vs-{changed}".replace("_", "-"),
        comparison_kind=(
            ComparisonKind.SAME_SELECTION_DIFFERENT_REPRESENTATION
            if representation
            else ComparisonKind.PAIRED_COMPONENT_ABLATION
        ),
        baseline_condition=baseline,
        changed_condition=changed,
        changed_component=component,
        paired=not representation,
        accuracy_delta=right.metrics.accuracy - left.metrics.accuracy,
        coverage_delta=right.metrics.coverage - left.metrics.coverage,
        outcome_counts=counts,
        prediction_disagreement_matrix=matrix,
        warning=(
            "Ceiling comparison only; representations differ."
            if representation
            else "Paired same-selection descriptive effect; no significance claim."
        ),
    )


def _predictions(path: Path) -> list[PredictionRecord]:
    values = [
        PredictionRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(values) != 30 or len({item.example_id for item in values}) != 30:
        raise ValueError(f"raw prediction records are incomplete: {path.name}")
    return values


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _git_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
