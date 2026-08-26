from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from verilogic_ns_api.baselines.selection import (
    load_manifest,
    validate_demonstration_manifest,
    validate_no_selection_overlap,
    validate_pilot_manifest,
)
from verilogic_ns_api.phase9.freeze import (
    Phase9FreezeError,
    expected_freeze_hash,
    file_sha256,
    load_and_validate_freeze,
)
from verilogic_ns_api.phase9.models import (
    ComparisonKind,
    FrozenArtifact,
    Phase9AggregateReport,
    Phase9Comparison,
    Phase9ConditionAggregate,
    Phase9FreezeManifest,
)
from verilogic_ns_api.phase9.schema_export import export_aggregate_schema
from verilogic_ns_api.research.models import MetricReport


def _freeze_payload(root: Path) -> tuple[Path, Path]:
    (root / ".git").mkdir()
    (root / "AGENTS.md").write_text("test rules\n", encoding="utf-8")
    artifact = root / "protocol.md"
    artifact.write_text("frozen\n", encoding="utf-8")
    manifest = Phase9FreezeManifest(
        protocol_label="Phase 9 regenerated evidence under newly frozen protocol",
        parent_checkpoint="5" * 40,
        archive_sha256="a" * 64,
        selection_manifest_hash="b" * 64,
        demonstration_manifest_hash="c" * 64,
        model_digest="d" * 64,
        conditions=(
            "direct",
            "few_shot",
            "p0_raw_neuro_symbolic",
            "validation_only",
            "p1_corrected_valid",
            "p2_corrected_selective",
            "oracle_structure_symbolic_ceiling",
        ),
        artifacts=(
            FrozenArtifact(
                artifact_id="protocol",
                path="protocol.md",
                sha256=file_sha256(artifact),
            ),
        ),
        freeze_hash="0" * 64,
    )
    manifest = manifest.model_copy(update={"freeze_hash": expected_freeze_hash(manifest)})
    path = root / "freeze.json"
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path, artifact


def test_phase9_freeze_validates_artifact_hashes(tmp_path: Path) -> None:
    path, _ = _freeze_payload(tmp_path)
    observed = load_and_validate_freeze(path)
    assert observed.split == "dev"
    assert observed.test_split_forbidden is True


def test_phase9_freeze_fails_closed_after_artifact_tampering(tmp_path: Path) -> None:
    path, artifact = _freeze_payload(tmp_path)
    artifact.write_text("changed\n", encoding="utf-8")
    with pytest.raises(Phase9FreezeError, match="artifact hash mismatch"):
        load_and_validate_freeze(path)


def test_phase9_freeze_rejects_test_split(tmp_path: Path) -> None:
    path, _ = _freeze_payload(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["split"] = "test"
    with pytest.raises(ValidationError):
        Phase9FreezeManifest.model_validate(payload)


def test_phase9_selection_manifests_are_balanced_and_disjoint() -> None:
    root = Path(__file__).parents[2]
    pilot = load_manifest(root / "experiments/manifests/phase9-regenerated-dev.v1.json")
    demonstrations = load_manifest(
        root / "experiments/manifests/phase9-regenerated-train-demos.v1.json"
    )
    validate_pilot_manifest(pilot)
    validate_demonstration_manifest(demonstrations)
    validate_no_selection_overlap(demonstrations, pilot)
    assert pilot.seed == demonstrations.seed == 20260818


def test_phase9_oracle_comparison_cannot_be_paired() -> None:
    comparison = Phase9Comparison(
        comparison_id="phase9-p2-vs-oracle",
        comparison_kind=ComparisonKind.SAME_SELECTION_DIFFERENT_REPRESENTATION,
        baseline_condition="p2_corrected_selective",
        changed_condition="oracle_structure_symbolic_ceiling",
        changed_component="representation",
        paired=False,
        accuracy_delta=None,
        coverage_delta=None,
        outcome_counts={
            "both_correct": 1,
            "baseline_only_correct": 0,
            "changed_only_correct": 29,
            "both_incorrect": 0,
        },
        prediction_disagreement_matrix={"CONTRADICTED": {"CONTRADICTED": 30}},
        warning="Ceiling only.",
    )
    assert comparison.paired is False


def test_phase9_neuro_symbolic_aggregate_requires_verified_proof_per_answer() -> None:
    metrics = MetricReport(
        total_examples=30,
        answered_examples=1,
        abstained_examples=25,
        errored_examples=4,
        accuracy=1 / 30,
        answered_only_accuracy=1.0,
        coverage=1 / 30,
        selective_risk=0.0,
        macro_precision=1 / 3,
        macro_recall=1 / 30,
        macro_f1=2 / 33,
        confusion_matrix={},
        per_label_metrics={},
        per_depth_metrics={},
        invalid_prediction_count=0,
    )
    payload = {
        "experiment_id": "phase9-regenerated-p2",
        "condition": "p2_corrected_selective",
        "policy_mode": "P2_SELECTIVE",
        "selection_manifest_hash": "a" * 64,
        "model": "local-model",
        "model_digest": "b" * 64,
        "config_hash": "c" * 64,
        "cache_mode": "live-local-with-content-addressed-cache",
        "provider_call_count": 1,
        "telemetry_complete": True,
        "input_tokens": 1,
        "output_tokens": 1,
        "observed_input_tokens": 1,
        "observed_output_tokens": 1,
        "metrics": metrics,
        "proof_attempted": 1,
        "proof_verified": 1,
        "raw_records_sha256": "d" * 64,
    }
    assert Phase9ConditionAggregate.model_validate(payload).proof_verified == 1
    with pytest.raises(ValidationError, match="proof-verification counts"):
        Phase9ConditionAggregate.model_validate(
            {**payload, "proof_attempted": None, "proof_verified": None}
        )
    with pytest.raises(ValidationError, match="every answered"):
        Phase9ConditionAggregate.model_validate(
            {**payload, "proof_attempted": 0, "proof_verified": 0}
        )
    with pytest.raises(ValidationError, match="preserve exact token counts as unavailable"):
        Phase9ConditionAggregate.model_validate({**payload, "telemetry_complete": False})


def test_tracked_phase9_aggregate_rejects_fingerprint_tampering() -> None:
    root = Path(__file__).parents[2]
    path = root / "research/evidence/phase9-regenerated-aggregate.v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert Phase9AggregateReport.model_validate(payload).replay_verified is True
    payload["conditions"][0]["metrics"]["accuracy"] = 0.0
    with pytest.raises(ValidationError, match="report fingerprint mismatch"):
        Phase9AggregateReport.model_validate(payload)


def test_phase9_aggregate_schema_is_current() -> None:
    root = Path(__file__).parents[2]
    assert export_aggregate_schema(root=root, check=True).name == (
        "phase9-aggregate-report.v1.schema.json"
    )
