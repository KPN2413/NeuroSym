from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from verilogic_ns_api.phase10.deliverables import validate_deliverables
from verilogic_ns_api.phase10.demo import validate_loopback_origin, write_demo_report
from verilogic_ns_api.phase10.deployment import (
    DeploymentContractError,
    validate_deployment_contract,
)
from verilogic_ns_api.phase10.evidence import build_final_evidence, write_final_evidence
from verilogic_ns_api.phase10.models import DemoCheck, DemoSmokeReport, FinalEvidencePackage
from verilogic_ns_api.phase10.schema_export import export_schema

ROOT = Path(__file__).resolve().parents[2]


def test_final_evidence_is_derived_from_frozen_phase9_evidence() -> None:
    evidence = build_final_evidence(ROOT)
    conditions = {item.condition: item for item in evidence.conditions}

    assert evidence.package_fingerprint == (
        "d4d289cfeeafcdecc0a930d57ad78896c5e4a0ed8f02814c9c34c79a946326e6"
    )
    assert evidence.phase9_aggregate_fingerprint == (
        "30146ca1a9cae630b18a96607c7c0a32173f6590631fc470c9c61cc22c5c26b1"
    )
    assert evidence.evaluation_records == 30
    assert evidence.test_split_access_count == 0
    assert evidence.hosted_provider_calls == 0
    assert evidence.external_transfers == 0
    assert evidence.api_cost_usd == 0
    assert conditions["direct"].correct == 16
    assert conditions["few_shot"].correct == 16
    assert conditions["p0_raw_neuro_symbolic"].correct == 4
    assert conditions["p2_corrected_selective"].correct == 1
    assert conditions["oracle_structure_symbolic_ceiling"].correct == 30
    assert conditions["p1_corrected_valid"].exact_input_tokens is None
    assert conditions["p2_corrected_selective"].exact_output_tokens is None


def test_final_evidence_rejects_tampering() -> None:
    payload = build_final_evidence(ROOT).model_dump(mode="json")
    payload["conditions"][0]["correct"] = 0
    with pytest.raises(ValidationError, match="fingerprint mismatch"):
        FinalEvidencePackage.model_validate(payload)


def test_final_evidence_and_schema_are_current_and_valid() -> None:
    evidence_path = write_final_evidence(ROOT, check=True)
    schema_path = export_schema(ROOT, check=True)
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(payload)


def test_deployment_contract_is_safe_for_provider_free_local_use() -> None:
    checks = validate_deployment_contract(ROOT)
    assert "cache_only_default" in checks
    assert "no_provider_secret_or_model_mount" in checks
    assert "non_root_images" in checks


def test_deployment_contract_rejects_provider_secrets(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "AGENTS.md").write_text("test rules\n", encoding="utf-8")
    shutil.copyfile(ROOT / "docker-compose.yml", tmp_path / "docker-compose.yml")
    for directory in ("backend", "frontend"):
        (tmp_path / directory).mkdir()
        shutil.copyfile(ROOT / directory / "Dockerfile", tmp_path / directory / "Dockerfile")
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(
        compose.read_text(encoding="utf-8") + "\n# OPENAI_API_KEY must never be mounted\n",
        encoding="utf-8",
    )

    with pytest.raises(DeploymentContractError, match="credentials or Ollama"):
        validate_deployment_contract(tmp_path)


def test_final_deliverables_are_complete_and_evidence_bound() -> None:
    result = validate_deliverables(ROOT)
    assert result["status"] == "VERIFIED"
    assert result["report_sections"] == 25
    assert result["evidence_package_fingerprint"] == (
        "d4d289cfeeafcdecc0a930d57ad78896c5e4a0ed8f02814c9c34c79a946326e6"
    )


def test_final_presentation_is_a_20_slide_editable_powerpoint() -> None:
    presentation = ROOT / "presentations/VeriLogic-NS-Final-Presentation.pptx"
    assert presentation.stat().st_size > 50_000
    with zipfile.ZipFile(presentation) as archive:
        slide_parts = [
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        ]
        notes_parts = [
            name
            for name in archive.namelist()
            if name.startswith("ppt/notesSlides/notesSlide") and name.endswith(".xml")
        ]
    assert len(slide_parts) == 20
    assert len(notes_parts) == 20


@pytest.mark.parametrize(
    ("origin", "port"),
    (
        ("https://example.com", 8000),
        ("http://192.0.2.1:8000", 8000),
        ("http://localhost:9000", 8000),
    ),
)
def test_demo_smoke_rejects_non_loopback_or_wrong_port(origin: str, port: int) -> None:
    with pytest.raises(ValueError, match=r"loopback|port"):
        validate_loopback_origin(origin, port)


def test_demo_report_write_is_atomic_and_contains_no_provider_dispatch(tmp_path: Path) -> None:
    report = DemoSmokeReport(
        backend_origin="http://127.0.0.1:8000",
        frontend_origin="http://127.0.0.1:3000",
        provider_mode="cache_only",
        provider_dispatches=0,
        logical_result="ENTAILED",
        proof_verified=True,
        explanation_steps=2,
        catalogue_experiments=19,
        catalogue_comparisons=10,
        checks=tuple(DemoCheck(name=f"check-{index}", detail="verified") for index in range(10)),
    )
    target = tmp_path / "demo.json"
    write_demo_report(target, report)

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["provider_dispatches"] == 0
    assert not target.with_suffix(".json.tmp").exists()
