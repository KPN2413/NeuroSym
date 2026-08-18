from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from verilogic_ns_api.main import create_app
from verilogic_ns_api.reasoning.models import Theory
from verilogic_ns_api.research_frontend.ast_inspection import inspect_ast
from verilogic_ns_api.research_frontend.catalogue import (
    CATALOGUE_PATH,
    CatalogueIntegrityError,
    ResearchCatalogueService,
    write_seed_catalogue,
)
from verilogic_ns_api.research_frontend.exports import render_export
from verilogic_ns_api.research_frontend.models import (
    AstInspectionRequest,
    ComparisonCompatibility,
    EvidenceType,
    ExperimentDetail,
    MetricEvidence,
    ResearchCatalogue,
    SourceArtifact,
)
from verilogic_ns_api.research_frontend.schema_export import export_schemas
from verilogic_ns_api.research_frontend.seed import build_catalogue

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_seed_catalogue_is_deterministic_valid_and_current() -> None:
    first = build_catalogue().model_dump_json()
    second = build_catalogue().model_dump_json()
    assert first == second
    assert write_seed_catalogue(ROOT, check=True) == ROOT / CATALOGUE_PATH
    assert export_schemas(root=ROOT, check=True) == []


def test_catalogue_validates_every_tracked_source_hash() -> None:
    service = ResearchCatalogueService(ROOT)
    tracked = tuple(item for item in service.catalogue.evidence_sources if item.tracked)
    assert tracked
    for source in tracked:
        observed = hashlib.sha256((ROOT / source.path).read_bytes()).hexdigest()
        assert observed == source.sha256


def test_catalogue_fails_closed_when_a_tracked_source_changes(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("test marker", encoding="utf-8")
    catalogue = build_catalogue()
    catalogue_path = tmp_path / CATALOGUE_PATH
    catalogue_path.parent.mkdir(parents=True)
    catalogue_path.write_text(json.dumps(catalogue.model_dump(mode="json")), encoding="utf-8")
    for source in catalogue.evidence_sources:
        if source.tracked:
            target = tmp_path / source.path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source.path, target)
    first = next(item for item in catalogue.evidence_sources if item.tracked)
    (tmp_path / first.path).write_text("tampered", encoding="utf-8")
    with pytest.raises(CatalogueIntegrityError, match="hash mismatch"):
        ResearchCatalogueService(tmp_path)


def test_metric_contract_rejects_false_availability_and_unpaired_accuracy() -> None:
    catalogue = build_catalogue()
    metric = catalogue.experiments[0].metrics[0].model_dump(mode="json")
    metric.update({"value": None, "evidence_type": "DOCUMENTED"})
    with pytest.raises(ValidationError):
        MetricEvidence.model_validate(metric)
    experiment = catalogue.experiments[0].model_dump(mode="json")
    experiment["metrics"] = [
        item for item in experiment["metrics"] if item["metric_id"] != "coverage"
    ]
    payload = catalogue.model_dump(mode="json")
    payload["experiments"][0] = experiment
    with pytest.raises(ValidationError, match="accuracy must be accompanied by coverage"):
        ResearchCatalogue.model_validate(payload)


def test_catalogue_distinguishes_observed_documented_and_derived_evidence() -> None:
    catalogue = build_catalogue()
    evidence_types = {
        metric.evidence_type
        for experiment in catalogue.experiments
        for metric in experiment.metrics
    }
    assert {"DOCUMENTED", "DERIVED", "UNAVAILABLE"}.issubset(evidence_types)
    # Raw machine results are no longer present, so this catalogue must not relabel
    # documentation as directly observed evidence.
    assert EvidenceType.DIRECTLY_OBSERVED not in evidence_types
    assert EvidenceType.DOCUMENTED is not EvidenceType.DIRECTLY_OBSERVED
    derived = [
        metric
        for experiment in catalogue.experiments
        for metric in experiment.metrics
        if metric.evidence_type == "DERIVED"
    ]
    assert derived
    assert all(metric.derivation_formula for metric in derived)


def test_duplicate_metrics_and_invalid_comparison_contracts_are_rejected() -> None:
    catalogue = build_catalogue()
    experiment = catalogue.experiments[0].model_dump(mode="json")
    experiment["metrics"].append(experiment["metrics"][0])
    with pytest.raises(ValidationError, match="duplicate metrics"):
        ExperimentDetail.model_validate(experiment)
    comparison = catalogue.comparisons[0].model_dump(mode="json")
    comparison.update({"comparison_type": "PAIRED", "paired": False})
    with pytest.raises(ValidationError, match="paired comparisons"):
        ComparisonCompatibility.model_validate(comparison)
    assert any(item.comparison_type == "DESCRIPTIVE_ONLY" for item in catalogue.comparisons)
    phase5_r3 = next(
        item for item in catalogue.comparisons if item.comparison_type == "INCOMPARABLE"
    )
    assert "not" in phase5_r3.warning.lower()


def test_source_paths_reject_traversal() -> None:
    source = build_catalogue().evidence_sources[0].model_dump(mode="json")
    source["path"] = "../secret.txt"
    with pytest.raises(ValidationError, match="safe repository-relative"):
        SourceArtifact.model_validate(source)


def test_research_overview_is_sanitized_and_provider_free(client: TestClient) -> None:
    response = client.get("/api/v1/research/catalogue")
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_validation_status"] == "VERIFIED"
    assert payload["experiment_count"] == 12
    assert payload["zero_cost"] is True
    assert payload["provider_calls_during_phase8"] == 0
    rendered = response.text.lower()
    assert "c:\\users" not in rendered
    assert "api_key" not in rendered
    assert "proofwriter context" not in rendered


def test_experiment_filters_and_pagination_are_bounded(client: TestClient) -> None:
    response = client.get(
        "/api/v1/research/experiments", params={"phase": "Phase 6-R3", "page_size": 2}
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 3
    assert len(payload["items"]) == 2
    assert all(item["phase"] == "Phase 6-R3" for item in payload["items"])
    invalid = client.get("/api/v1/research/experiments", params={"page_size": 101})
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "INVALID_RESEARCH_REQUEST"


def test_experiment_detail_preserves_missing_values_and_provenance(client: TestClient) -> None:
    response = client.get("/api/v1/research/experiments/phase6-original-blocked")
    assert response.status_code == 200
    payload = response.json()
    accuracy = next(item for item in payload["metrics"] if item["metric_id"] == "accuracy")
    assert accuracy["value"] is None
    assert accuracy["evidence_type"] == "UNAVAILABLE"
    assert accuracy["verification_status"] == "UNAVAILABLE"
    assert accuracy["source_artifact_hash"]
    missing = client.get("/api/v1/research/experiments/not-present")
    assert missing.status_code == 404
    assert missing.json()["code"] == "RESEARCH_EVIDENCE_NOT_FOUND"


def test_comparisons_mark_unsupported_cross_run_claims(client: TestClient) -> None:
    response = client.get("/api/v1/research/comparisons")
    assert response.status_code == 200
    comparisons = response.json()
    paired = next(item for item in comparisons if item["comparison_type"] == "PAIRED")
    assert paired["same_selection"] is True
    incomparable = next(item for item in comparisons if item["comparison_type"] == "INCOMPARABLE")
    assert incomparable["paired"] is False
    assert "not" in incomparable["warning"].lower()


@pytest.mark.parametrize(
    ("export_format", "content_type", "suffix"),
    [
        ("json", "application/json", ".json"),
        ("csv", "text/csv", ".csv"),
        ("markdown", "text/markdown", ".md"),
    ],
)
def test_exports_are_deterministic_safe_and_attributed(
    client: TestClient, export_format: str, content_type: str, suffix: str
) -> None:
    first = client.get(f"/api/v1/research/exports/{export_format}")
    second = client.get(f"/api/v1/research/exports/{export_format}")
    assert first.status_code == 200
    assert first.content == second.content
    assert first.headers["content-type"].startswith(content_type)
    assert first.headers["content-disposition"].endswith(f'{suffix}"')
    assert len(first.headers["x-evidence-content-sha256"]) == 64
    text = first.text.lower()
    assert "c:\\users" not in text
    assert "openai_api_key" not in text
    assert "unavailable" in text or "na" in text


def test_export_filters_change_hash_without_overwriting_missing_values() -> None:
    service = ResearchCatalogueService(ROOT)
    whole = render_export(service, "json")
    phase6 = render_export(service, "json", {"phase": "Phase 6-R3"})
    assert whole.manifest.canonical_content_hash != phase6.manifest.canonical_content_hash
    assert render_export(service, "json").content == whole.content
    parsed = json.loads(whole.content)
    assert parsed["manifest"]["canonical_content_hash"] == whole.manifest.canonical_content_hash
    assert parsed["evidence"]["missing_value"] == "NA"


def test_ast_inspector_renders_canonical_structure_without_inference(client: TestClient) -> None:
    theory = json.loads((ROOT / "examples/theories/entailed.json").read_text())
    response = client.post(
        "/api/v1/research/ast-inspect",
        json={
            "schema_version": "1.0",
            "accepted_theory": theory,
            "correction_attempted": False,
            "proof_roots": [],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["semantic_validation_status"] == "VALID"
    assert payload["source_coverage_status"] == "COMPLETE"
    assert payload["facts"]
    assert payload["rules"]
    assert payload["query"]
    assert payload["correction_diff"]["available"] is False


def test_invalid_ast_request_uses_sanitized_error(client: TestClient) -> None:
    response = client.post(
        "/api/v1/research/ast-inspect", json={"accepted_theory": {"malicious": "x"}}
    )
    assert response.status_code == 422
    assert response.json() == {
        "schema_version": "1.0",
        "code": "INVALID_RESEARCH_REQUEST",
        "message": "The request does not satisfy the versioned research API contract.",
    }


def test_ast_inspector_supports_binary_predicates_and_explicit_negation() -> None:
    binary = Theory.model_validate(
        json.loads((ROOT / "examples/theories/binary-join.json").read_text())
    )
    binary_view = inspect_ast(AstInspectionRequest(accepted_theory=binary))
    assert any(predicate.arity == 2 for predicate in binary_view.predicates)
    assert any(len(fact.arguments) == 2 for fact in binary_view.facts)
    contradicted = Theory.model_validate(
        json.loads((ROOT / "examples/theories/contradicted.json").read_text())
    )
    negative_view = inspect_ast(AstInspectionRequest(accepted_theory=contradicted))
    assert any(fact.negated for fact in negative_view.facts)


def test_ast_correction_diff_reports_safe_normalized_changes() -> None:
    before_payload = json.loads((ROOT / "examples/theories/entailed.json").read_text())
    after_payload = json.loads((ROOT / "examples/theories/entailed.json").read_text())
    after_payload["facts"][0]["negated"] = True
    view = inspect_ast(
        AstInspectionRequest(
            accepted_theory=Theory.model_validate(after_payload),
            pre_correction_theory=Theory.model_validate(before_payload),
            correction_attempted=True,
        )
    )
    assert view.correction_diff.available is True
    assert view.correction_diff.changed_polarity
