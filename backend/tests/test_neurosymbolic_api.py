from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from verilogic_ns_api.main import create_app
from verilogic_ns_api.orchestration.factory import OrchestrationFactory
from verilogic_ns_api.orchestration.models import ProviderMode
from verilogic_ns_api.orchestration.schema_export import export_contracts

ROOT = Path(__file__).resolve().parents[2]


def _formal_payload(name: str = "entailed") -> dict[str, object]:
    theory = json.loads((ROOT / "examples" / "theories" / f"{name}.json").read_text())
    return {
        "schema_version": "1.0",
        "input_mode": "FORMAL_AST",
        "policy_mode": "P2_SELECTIVE",
        "formal_ast": {"theory": theory, "query": theory["query"]},
        "natural_language": None,
    }


def _wait(client: TestClient, run_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while True:
        response = client.get(f"/api/v1/neurosymbolic/runs/{run_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"COMPLETED", "FAILED", "CANCELLED"}:
            return payload
        assert time.monotonic() < deadline
        time.sleep(0.01)


def test_formal_api_submission_polling_and_repeated_get_are_provider_free() -> None:
    with TestClient(create_app()) as client:
        submitted = client.post("/api/v1/neurosymbolic/runs", json=_formal_payload())
        assert submitted.status_code == 202
        run_id = submitted.json()["run_id"]
        completed = _wait(client, run_id)
        assert completed["status"] == "COMPLETED"
        assert completed["result"]["logical_result"] == "ENTAILED"
        assert completed["result"]["provenance"]["provider_dispatches"] == 0
        first = client.get(f"/api/v1/neurosymbolic/runs/{run_id}").json()
        second = client.get(f"/api/v1/neurosymbolic/runs/{run_id}").json()
        assert first == second


def test_api_rejects_invalid_unknown_and_oversized_requests_safely() -> None:
    with TestClient(create_app()) as client:
        invalid = client.post(
            "/api/v1/neurosymbolic/runs",
            json={"input_mode": "NATURAL_LANGUAGE"},
        )
        assert invalid.status_code == 422
        assert invalid.json()["code"] == "INVALID_REQUEST"
        unknown = client.get("/api/v1/neurosymbolic/runs/not-a-run")
        assert unknown.status_code == 404
        assert unknown.json()["code"] == "RUN_NOT_FOUND"
        oversized = client.post(
            "/api/v1/neurosymbolic/runs",
            json={
                "input_mode": "NATURAL_LANGUAGE",
                "natural_language": {
                    "statements": [{"source_id": "s1", "kind": "fact", "text": "x" * 10_001}],
                    "query": "Q?",
                },
            },
        )
        assert oversized.status_code == 422
        assert "x" * 100 not in oversized.text


def test_api_cancellation_and_cors_contract() -> None:
    with TestClient(create_app()) as client:
        submitted = client.post("/api/v1/neurosymbolic/runs", json=_formal_payload("unknown"))
        run_id = submitted.json()["run_id"]
        cancelled = client.delete(f"/api/v1/neurosymbolic/runs/{run_id}")
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] in {"CANCELLED", "CANCEL_REQUESTED", "COMPLETED"}
        preflight = client.options(
            "/api/v1/neurosymbolic/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_capabilities_and_openapi_are_versioned_and_schema_contracts_are_fresh() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/neurosymbolic/capabilities")
        assert response.status_code == 200
        payload = response.json()
        assert payload["api_version"] == "v1"
        assert payload["symbolic_engine_ready"] is True
        assert payload["supported_input_modes"] == ["NATURAL_LANGUAGE", "FORMAL_AST"]
        openapi = client.get("/openapi.json").json()
        assert "/api/v1/neurosymbolic/runs" in openapi["paths"]
        assert "/health" in openapi["paths"]
    assert export_contracts(root=ROOT, check=True) == []


def test_live_natural_submission_returns_503_when_exact_model_is_unavailable() -> None:
    factory = OrchestrationFactory(provider_mode=ProviderMode.LIVE)
    assert factory.model_ready() is False
    with TestClient(create_app(orchestration_factory=factory)) as client:
        response = client.post(
            "/api/v1/neurosymbolic/runs",
            json={
                "input_mode": "NATURAL_LANGUAGE",
                "policy_mode": "P2_SELECTIVE",
                "natural_language": {
                    "statements": [
                        {"source_id": "s1", "kind": "fact", "text": "The robin is red."}
                    ],
                    "query": "The robin is warm.",
                },
            },
        )
        assert response.status_code == 503
        assert response.json()["code"] == "LOCAL_MODEL_UNAVAILABLE"


def test_model_readiness_reuses_result_and_connection_until_ttl_expires() -> None:
    now = [10.0]
    requests: list[str] = []
    available = [True]
    factory: OrchestrationFactory

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        runtime = factory.frozen.parser_config.runtime
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": runtime.provider_version})
        models = []
        if available[0]:
            models.append(
                {
                    "name": runtime.model,
                    "model": runtime.model,
                    "modified_at": "2026-01-01T00:00:00Z",
                    "size": 1,
                    "digest": runtime.model_digest,
                    "details": {},
                }
            )
        return httpx.Response(200, json={"models": models})

    factory = OrchestrationFactory(
        provider_mode=ProviderMode.LIVE,
        readiness_ttl_seconds=5,
        readiness_transport=httpx.MockTransport(handler),
        readiness_clock=lambda: now[0],
    )
    try:
        assert factory.model_ready() is True
        assert factory.model_ready() is True
        assert requests == ["/api/version", "/api/tags"]

        available[0] = False
        now[0] = 14.99
        assert factory.model_ready() is True
        assert requests == ["/api/version", "/api/tags"]

        now[0] = 15.0
        assert factory.model_ready() is False
        assert requests == ["/api/version", "/api/tags", "/api/version", "/api/tags"]

        now[0] = 20.0
        assert factory.model_ready() is False
        assert requests == [
            "/api/version",
            "/api/tags",
            "/api/version",
            "/api/tags",
            "/api/version",
            "/api/tags",
        ]
    finally:
        factory.close()


def test_model_readiness_rejects_wrong_digest_and_http_failures() -> None:
    responses = ["wrong-digest", "http-error"]
    factory: OrchestrationFactory

    def handler(request: httpx.Request) -> httpx.Response:
        runtime = factory.frozen.parser_config.runtime
        if responses[0] == "http-error":
            return httpx.Response(503)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": runtime.provider_version})
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": runtime.model,
                        "model": runtime.model,
                        "modified_at": "2026-01-01T00:00:00Z",
                        "size": 1,
                        "digest": "0" * 64,
                        "details": {},
                    }
                ]
            },
        )

    now = [0.0]
    factory = OrchestrationFactory(
        provider_mode=ProviderMode.LIVE,
        readiness_ttl_seconds=1,
        readiness_transport=httpx.MockTransport(handler),
        readiness_clock=lambda: now[0],
    )
    try:
        assert factory.model_ready() is False
        responses[0] = "http-error"
        now[0] = 1.0
        assert factory.model_ready() is False
    finally:
        factory.close()
