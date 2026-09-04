from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from pydantic import ValidationError

from verilogic_ns_api.baselines.ollama_provider import OllamaTagsResponse, OllamaVersionResponse
from verilogic_ns_api.orchestration.budget import BudgetedProvider, DispatchBudget
from verilogic_ns_api.orchestration.configuration import (
    PHASE7_CACHE,
    load_frozen_orchestration_config,
)
from verilogic_ns_api.orchestration.models import InputMode, PipelineRequest, ProviderMode
from verilogic_ns_api.orchestration.pipeline import (
    NeuroSymbolicPipeline,
    PipelineMetadata,
)
from verilogic_ns_api.semantic_parsing.cache import ParserResponseCache
from verilogic_ns_api.semantic_parsing.provider import OllamaStructuredProvider
from verilogic_ns_api.semantic_parsing.service import SemanticParser
from verilogic_ns_api.validation_correction.cache import CorrectionResponseCache
from verilogic_ns_api.validation_correction.controller import ValidationCorrectionController
from verilogic_ns_api.validation_correction.provider import OllamaCorrectionProvider
from verilogic_ns_api.validation_correction.service import CorrectionTaskService


@dataclass
class PipelineRuntime:
    pipeline: NeuroSymbolicPipeline
    budget: DispatchBudget
    providers: tuple[object, ...]

    def close(self) -> None:
        for provider in self.providers:
            close = getattr(provider, "close", None)
            if callable(close):
                close()


class OrchestrationFactory:
    def __init__(
        self,
        *,
        root: Path | None = None,
        provider_mode: ProviderMode = ProviderMode.CACHE_ONLY,
        dispatch_limit: int = 12,
        readiness_ttl_seconds: float = 5.0,
        readiness_transport: httpx.BaseTransport | None = None,
        readiness_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if readiness_ttl_seconds <= 0:
            raise ValueError("readiness_ttl_seconds must be positive")
        self.frozen = load_frozen_orchestration_config(root)
        self.provider_mode = provider_mode
        self.dispatch_limit = dispatch_limit
        self.readiness_ttl_seconds = readiness_ttl_seconds
        self._readiness_transport = readiness_transport
        self._readiness_clock = readiness_clock
        self._readiness_lock = threading.Lock()
        self._readiness_client: httpx.Client | None = None
        self._readiness_cached_at: float | None = None
        self._readiness_cached_value = False

    def create(self) -> PipelineRuntime:
        frozen = self.frozen
        runtime_config = frozen.parser_config.runtime
        budget = DispatchBudget(self.dispatch_limit)
        providers: list[object] = []
        parser_provider: object | None = None
        correction_provider: object | None = None
        if self.provider_mode is ProviderMode.LIVE:
            parser_native = OllamaStructuredProvider(runtime_config)
            correction_native = OllamaCorrectionProvider(runtime_config)
            parser_provider = BudgetedProvider(parser_native, budget)
            correction_provider = BudgetedProvider(correction_native, budget)
            providers.extend((parser_provider, correction_provider))

        cache_root = frozen.root / PHASE7_CACHE
        parser = SemanticParser(
            config=runtime_config,
            theory_prompt=frozen.theory_prompt,
            theory_prompt_hash=frozen.parser_config.theory_prompt_sha256,
            query_prompt=frozen.query_prompt,
            query_prompt_hash=frozen.parser_config.query_prompt_sha256,
            cache=ParserResponseCache(cache_root / "semantic-parser"),
            provider=parser_provider,  # type: ignore[arg-type]
            replay_only=self.provider_mode is ProviderMode.CACHE_ONLY,
        )
        task_service = CorrectionTaskService(
            config=frozen.correction_config,
            prompts=frozen.correction_prompts,
            cache=CorrectionResponseCache(cache_root / "validation-correction"),
            provider=correction_provider,  # type: ignore[arg-type]
            replay_only=self.provider_mode is ProviderMode.CACHE_ONLY,
        )
        controller = ValidationCorrectionController(task_service)
        metadata = PipelineMetadata(
            provider_mode=self.provider_mode,
            model_name=runtime_config.model,
            model_digest=runtime_config.model_digest,
            provider_version=runtime_config.provider_version,
            prompt_hashes=frozen.prompt_hashes,
            schema_hashes=frozen.schema_hashes,
            policy_hash=frozen.correction_config.reliability_policy.policy_hash,
        )
        return PipelineRuntime(
            pipeline=NeuroSymbolicPipeline(
                parser=parser,
                controller=controller,
                metadata=metadata,
                dispatch_count=lambda: budget.count,
            ),
            budget=budget,
            providers=tuple(providers),
        )

    def create_for(self, request: PipelineRequest) -> PipelineRuntime:
        if request.input_mode is InputMode.NATURAL_LANGUAGE:
            return self.create()
        metadata = PipelineMetadata(
            provider_mode=self.provider_mode,
            schema_hashes=self.frozen.schema_hashes,
        )
        return PipelineRuntime(
            pipeline=NeuroSymbolicPipeline(metadata=metadata),
            budget=DispatchBudget(self.dispatch_limit),
            providers=(),
        )

    def model_ready(self) -> bool:
        with self._readiness_lock:
            checked_at = self._readiness_clock()
            if (
                self._readiness_cached_at is not None
                and checked_at - self._readiness_cached_at < self.readiness_ttl_seconds
            ):
                return self._readiness_cached_value
            ready = self._check_model_ready()
            self._readiness_cached_value = ready
            self._readiness_cached_at = self._readiness_clock()
            return ready

    def _check_model_ready(self) -> bool:
        config = self.frozen.parser_config.runtime
        try:
            if self._readiness_client is None:
                self._readiness_client = httpx.Client(
                    base_url=config.endpoint,
                    timeout=2,
                    transport=self._readiness_transport,
                    trust_env=False,
                    headers={"User-Agent": "VeriLogic-NS/0.1 readiness"},
                )
            version_response = self._readiness_client.get("/api/version")
            version_response.raise_for_status()
            tags_response = self._readiness_client.get("/api/tags")
            tags_response.raise_for_status()
            version = OllamaVersionResponse.model_validate(version_response.json())
            tags = OllamaTagsResponse.model_validate(tags_response.json())
        except (httpx.HTTPError, ValueError, ValidationError):
            return False
        return version.version == config.provider_version and any(
            item.name == config.model and item.digest == config.model_digest for item in tags.models
        )

    def close(self) -> None:
        with self._readiness_lock:
            if self._readiness_client is not None:
                self._readiness_client.close()
                self._readiness_client = None
