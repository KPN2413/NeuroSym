from __future__ import annotations

import json
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase10.models import DemoCheck, DemoSmokeReport
from verilogic_ns_api.research_frontend.models import sha256_json


def validate_loopback_origin(value: str, expected_port: int) -> str:
    parsed = urlparse(value.rstrip("/"))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("demo verification accepts only an HTTP loopback origin")
    if parsed.port != expected_port or parsed.path not in {"", "/"}:
        raise ValueError(f"demo origin must use loopback port {expected_port}")
    return f"http://127.0.0.1:{expected_port}"


def _check(response: httpx.Response, name: str, detail: str) -> DemoCheck:
    response.raise_for_status()
    return DemoCheck(name=name, detail=detail)


def run_demo_smoke(
    *,
    root: Path | None = None,
    backend_origin: str = "http://127.0.0.1:8000",
    frontend_origin: str = "http://127.0.0.1:3000",
    timeout_seconds: float = 10,
) -> DemoSmokeReport:
    resolved = repository_root(root or Path.cwd())
    backend = validate_loopback_origin(backend_origin, 8000)
    frontend = validate_loopback_origin(frontend_origin, 3000)
    checks: list[DemoCheck] = []
    with httpx.Client(timeout=timeout_seconds, follow_redirects=True) as client:
        health = client.get(f"{backend}/health")
        checks.append(_check(health, "backend_health", "GET /health returned status ok"))
        if health.json().get("status") != "ok":
            raise ValueError("backend health payload is not ready")

        capabilities = client.get(f"{backend}/api/v1/neurosymbolic/capabilities")
        checks.append(
            _check(
                capabilities,
                "capabilities",
                "formal reasoning is available in cache-only provider mode",
            )
        )
        capability_payload = capabilities.json()
        if capability_payload.get("provider_mode") != "cache_only":
            raise ValueError("demo backend must run in cache-only provider mode")
        if capability_payload.get("symbolic_engine_ready") is not True:
            raise ValueError("symbolic engine is not ready")

        catalogue = client.get(f"{backend}/api/v1/research/catalogue")
        checks.append(
            _check(
                catalogue,
                "research_catalogue",
                "validated catalogue exposes 19 experiments and 10 comparisons",
            )
        )
        catalogue_payload = catalogue.json()
        if (
            catalogue_payload.get("experiment_count"),
            catalogue_payload.get("comparison_count"),
        ) != (
            19,
            10,
        ):
            raise ValueError("research catalogue counts do not match Phase 9 evidence")

        experiment = client.get(f"{backend}/api/v1/research/experiments/phase9-regenerated-direct")
        checks.append(
            _check(experiment, "research_experiment", "Phase 9 Direct detail is available")
        )

        canonical_export_hash: str | None = None
        for export_format in ("json", "csv", "markdown"):
            exported = client.get(f"{backend}/api/v1/research/exports/{export_format}")
            checks.append(
                _check(
                    exported,
                    f"research_export_{export_format}",
                    f"deterministic {export_format.upper()} export is available",
                )
            )
            declared = exported.headers.get("x-evidence-content-sha256")
            if export_format == "json":
                document = exported.json()
                canonical_export_hash = sha256_json(document["evidence"])
                if declared != document["manifest"]["canonical_content_hash"]:
                    raise ValueError("JSON export header does not match its manifest")
                if declared != canonical_export_hash:
                    raise ValueError("JSON export canonical evidence hash is invalid")
            elif declared != canonical_export_hash or declared.encode() not in exported.content:
                raise ValueError(
                    f"{export_format} export does not bind the canonical evidence hash"
                )

        home = client.get(frontend)
        checks.append(_check(home, "frontend_workbench", "production workbench route rendered"))
        if "VeriLogic-NS" not in home.text:
            raise ValueError("frontend workbench marker is missing")
        research = client.get(f"{frontend}/research")
        checks.append(_check(research, "frontend_research", "production research route rendered"))
        if "Research evidence" not in research.text:
            raise ValueError("frontend research marker is missing")

        theory = json.loads(
            (resolved / "examples/theories/entailed.json").read_text(encoding="utf-8")
        )
        request = {
            "schema_version": "1.0",
            "input_mode": "FORMAL_AST",
            "policy_mode": "P2_SELECTIVE",
            "natural_language": None,
            "formal_ast": {"theory": theory, "query": theory["query"]},
        }
        submitted = client.post(f"{backend}/api/v1/neurosymbolic/runs", json=request)
        checks.append(_check(submitted, "formal_submission", "formal provider-free run accepted"))
        run_id = submitted.json()["run_id"]
        deadline = time.monotonic() + timeout_seconds
        while True:
            state = client.get(f"{backend}/api/v1/neurosymbolic/runs/{run_id}")
            state.raise_for_status()
            state_payload = state.json()
            if state_payload["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("formal demo run did not complete within the timeout")
            time.sleep(0.05)
        result = state_payload.get("result") or {}
        if state_payload["status"] != "COMPLETED" or result.get("logical_result") != "ENTAILED":
            raise ValueError("formal demo did not produce the expected ENTAILED result")
        verification = result.get("proof_verification") or {}
        if verification.get("valid") is not True:
            raise ValueError("formal demo proof did not verify")
        provenance = result.get("provenance") or {}
        if provenance.get("provider_dispatches") != 0:
            raise ValueError("formal demo unexpectedly dispatched a provider request")
        steps = len((result.get("explanation") or {}).get("steps") or [])
        if steps < 1:
            raise ValueError("formal demo explanation is empty")
        checks.append(
            DemoCheck(
                name="formal_result",
                detail="ENTAILED with verified proof, deterministic explanation, and zero calls",
            )
        )

        preflight = client.options(
            f"{backend}/api/v1/neurosymbolic/runs",
            headers={
                "Origin": frontend,
                "Access-Control-Request-Method": "POST",
            },
        )
        checks.append(_check(preflight, "cors", "frontend loopback origin is explicitly allowed"))
        if preflight.headers.get("access-control-allow-origin") != frontend:
            raise ValueError("CORS did not allow the production frontend origin")

    return DemoSmokeReport(
        backend_origin=backend,
        frontend_origin=frontend,
        provider_mode="cache_only",
        provider_dispatches=0,
        logical_result="ENTAILED",
        proof_verified=True,
        explanation_steps=steps,
        catalogue_experiments=19,
        catalogue_comparisons=10,
        checks=tuple(checks),
    )


def write_demo_report(path: Path, report: DemoSmokeReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)
