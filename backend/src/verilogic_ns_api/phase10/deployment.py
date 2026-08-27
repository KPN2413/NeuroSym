from __future__ import annotations

from pathlib import Path

import yaml

from verilogic_ns_api.baselines.configuration import repository_root


class DeploymentContractError(ValueError):
    pass


def validate_deployment_contract(root: Path | None = None) -> tuple[str, ...]:
    resolved = repository_root(root or Path.cwd())
    compose_path = resolved / "docker-compose.yml"
    try:
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise DeploymentContractError("Docker Compose configuration is invalid") from error
    services = compose.get("services", {}) if isinstance(compose, dict) else {}
    if set(services) != {"backend", "frontend"}:
        raise DeploymentContractError("Compose must contain exactly backend and frontend services")
    backend = services["backend"]
    frontend = services["frontend"]
    backend_ports = " ".join(str(item) for item in backend.get("ports", []))
    frontend_ports = " ".join(str(item) for item in frontend.get("ports", []))
    if not any(value in backend_ports for value in ("8000:8000", "8000}:8000")):
        raise DeploymentContractError("backend port mapping is missing")
    if not any(value in frontend_ports for value in ("3000:3000", "3000}:3000")):
        raise DeploymentContractError("frontend port mapping is missing")
    for name, service in services.items():
        if not service.get("healthcheck"):
            raise DeploymentContractError(f"{name} service has no health check")
    environment = backend.get("environment", {})
    if environment.get("VERILOGIC_ORCHESTRATION_PROVIDER_MODE") is None:
        raise DeploymentContractError("backend provider mode is not explicit")
    forbidden = ("OPENAI_API_KEY", "OLLAMA_HOST", "11434")
    rendered = compose_path.read_text(encoding="utf-8")
    if any(item in rendered for item in forbidden):
        raise DeploymentContractError("Compose must not publish credentials or Ollama")
    backend_dockerfile = (resolved / "backend/Dockerfile").read_text(encoding="utf-8")
    frontend_dockerfile = (resolved / "frontend/Dockerfile").read_text(encoding="utf-8")
    if "USER verilogic" not in backend_dockerfile or "USER nextjs" not in frontend_dockerfile:
        raise DeploymentContractError("production containers must run as non-root users")
    return (
        "compose_yaml_valid",
        "two_service_boundary",
        "explicit_ports",
        "service_healthchecks",
        "cache_only_default",
        "no_provider_secret_or_model_mount",
        "non_root_images",
    )
