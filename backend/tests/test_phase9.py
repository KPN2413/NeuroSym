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
    Phase9Comparison,
    Phase9FreezeManifest,
)


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
        warning="Ceiling only.",
    )
    assert comparison.paired is False
