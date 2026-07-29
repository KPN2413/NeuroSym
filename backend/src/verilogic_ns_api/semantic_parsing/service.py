from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.semantic_parsing.cache import ParserCacheError, ParserResponseCache
from verilogic_ns_api.semantic_parsing.models import (
    CandidateQueryOutput,
    CandidateTheoryOutput,
    ParserKind,
    ParserOutcome,
    ParserResponse,
    ParserRuntimeConfig,
    ParserStatus,
    QueryParseInput,
    TheoryParseInput,
)
from verilogic_ns_api.semantic_parsing.prompts import render_query_input, render_theory_input
from verilogic_ns_api.semantic_parsing.provider import (
    OllamaStructuredProvider,
    ParserConfigurationError,
    ParserProviderError,
    ParserStructuredOutputError,
    ParserTimeoutError,
    ParserTransientError,
    StructuredRequest,
)
from verilogic_ns_api.terminal_outcomes import (
    AttemptEvidence,
    CachedOutcomeType,
    PipelineFailureStatus,
    TerminalErrorCode,
    TerminalProviderOutcome,
    TerminalRuntime,
    TerminalStage,
    build_terminal_outcome,
)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ParseExecution(Generic[T]):
    outcome: ParserOutcome
    candidate: T | None


class SemanticParser:
    def __init__(
        self,
        *,
        config: ParserRuntimeConfig,
        theory_prompt: str,
        theory_prompt_hash: str,
        query_prompt: str,
        query_prompt_hash: str,
        cache: ParserResponseCache,
        provider: OllamaStructuredProvider | None,
        replay_only: bool = False,
    ) -> None:
        self.config = config
        self.theory_prompt = theory_prompt
        self.theory_prompt_hash = theory_prompt_hash
        self.query_prompt = query_prompt
        self.query_prompt_hash = query_prompt_hash
        self.cache = cache
        self.provider = provider
        self.replay_only = replay_only

    def parse_theory(self, value: TheoryParseInput) -> ParseExecution[CandidateTheoryOutput]:
        return self._parse(
            kind=ParserKind.THEORY,
            value=value,
            instructions=self.theory_prompt,
            prompt_hash=self.theory_prompt_hash,
            rendered=render_theory_input(value),
            output_model=CandidateTheoryOutput,
        )

    def parse_query(self, value: QueryParseInput) -> ParseExecution[CandidateQueryOutput]:
        return self._parse(
            kind=ParserKind.QUERY,
            value=value,
            instructions=self.query_prompt,
            prompt_hash=self.query_prompt_hash,
            rendered=render_query_input(value),
            output_model=CandidateQueryOutput,
        )

    def _parse(
        self,
        *,
        kind: ParserKind,
        value: TheoryParseInput | QueryParseInput,
        instructions: str,
        prompt_hash: str,
        rendered: str,
        output_model: type[T],
    ) -> ParseExecution[T]:
        schema = output_model.model_json_schema()
        request = StructuredRequest(
            kind=kind.value,
            instructions=instructions,
            input_text=rendered,
            prompt_hash=prompt_hash,
            input_hash=value.input_hash,
            output_schema=schema,
            schema_hash=sha256_payload(schema),
            config=self.config,
        )
        try:
            cached = self.cache.load_outcome(request)
        except ParserCacheError as error:
            return _failure(
                kind, value.input_hash, request.request_hash, ParserStatus.STRUCTURAL_INVALID, error
            )
        if cached is not None and cached.outcome_type is CachedOutcomeType.TERMINAL_ERROR:
            assert cached.terminal_error is not None
            return _terminal_failure(kind, value.input_hash, cached.terminal_error)
        response = cached.response if cached is not None else None
        cache_hit = cached is not None
        if cached is None:
            if self.replay_only or self.provider is None:
                return _failure(
                    kind,
                    value.input_hash,
                    request.request_hash,
                    ParserStatus.PROVIDER_ERROR,
                    RuntimeError("cache miss in replay-only mode"),
                )
            response = self._dispatch(request, kind, value.input_hash)
            if isinstance(response, ParseExecution):
                return response
        try:
            candidate = output_model.model_validate(response.content)
        except ValidationError as error:
            terminal = _invalid_response_terminal(
                request=request,
                response=response,
                kind=kind,
                error=error,
            )
            if cached is None:
                self.cache.store_terminal(request, terminal)
            return _terminal_failure(
                kind,
                value.input_hash,
                terminal,
                cache_hit=cache_hit,
            )
        if cached is None:
            self.cache.store(request, response)
        outcome = ParserOutcome(
            parser_kind=kind,
            input_hash=value.input_hash,
            request_hash=request.request_hash,
            status=ParserStatus.PARSED,
            cache_hit=cache_hit,
            candidate=candidate.model_dump(mode="json"),
            usage=response.usage,
            timing=response.timing,
        )
        return ParseExecution(outcome=outcome, candidate=candidate)

    def _dispatch(self, request: StructuredRequest, kind: ParserKind, input_hash: str) -> object:
        assert self.provider is not None
        for attempt in range(self.config.max_attempts):
            try:
                return self.provider.complete(request)
            except ParserTimeoutError as error:
                if attempt + 1 == self.config.max_attempts:
                    return _failure(
                        kind, input_hash, request.request_hash, ParserStatus.TIMEOUT, error
                    )
            except ParserTransientError as error:
                if attempt + 1 == self.config.max_attempts:
                    return _failure(
                        kind, input_hash, request.request_hash, ParserStatus.PROVIDER_ERROR, error
                    )
            except ParserStructuredOutputError as error:
                return _failure(
                    kind,
                    input_hash,
                    request.request_hash,
                    ParserStatus.STRUCTURED_OUTPUT_ERROR,
                    error,
                )
            except (ParserConfigurationError, ParserProviderError) as error:
                return _failure(
                    kind, input_hash, request.request_hash, ParserStatus.PROVIDER_ERROR, error
                )
            time.sleep(0.25 * (2**attempt))
        raise AssertionError("unreachable retry state")


def _terminal_failure(
    kind: ParserKind,
    input_hash: str,
    terminal: TerminalProviderOutcome,
    *,
    cache_hit: bool = True,
) -> ParseExecution:
    status = {
        PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR: ParserStatus.STRUCTURED_OUTPUT_ERROR,
        PipelineFailureStatus.TIMEOUT: ParserStatus.TIMEOUT,
        PipelineFailureStatus.PROVIDER_ERROR: ParserStatus.PROVIDER_ERROR,
    }[terminal.pipeline_status]
    return ParseExecution(
        outcome=ParserOutcome(
            parser_kind=kind,
            input_hash=input_hash,
            request_hash=terminal.request_hash,
            status=status,
            cache_hit=cache_hit,
            error_type=terminal.error_code.value,
            error_message=terminal.reason,
        ),
        candidate=None,
    )


def _invalid_response_terminal(
    *,
    request: StructuredRequest,
    response: ParserResponse,
    kind: ParserKind,
    error: ValidationError,
) -> TerminalProviderOutcome:
    evidence = sha256_payload(
        {
            "namespace": "semantic-parser-invalid-response.v1",
            "request_hash": request.request_hash,
            "response_content_sha256": sha256_payload(response.content),
            "validation_error_sha256": sha256_payload(error.errors(include_url=False)),
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
    num_predict = (
        request.config.theory_num_predict
        if kind is ParserKind.THEORY
        else request.config.query_num_predict
    )
    return build_terminal_outcome(
        stage=(
            TerminalStage.SEMANTIC_PARSER_THEORY
            if kind is ParserKind.THEORY
            else TerminalStage.SEMANTIC_PARSER_QUERY
        ),
        error_code=TerminalErrorCode.INVALID_STRUCTURED_OUTPUT,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason="Provider response failed the frozen parser output schema.",
        request_identity=request.identity(),
        semantic_config_hash=sha256_payload(request.config.model_dump(mode="json")),
        runtime=TerminalRuntime(
            endpoint=request.config.endpoint,
            provider_version=request.config.provider_version,
            model=request.config.model,
            model_digest=request.config.model_digest,
            temperature=request.config.temperature,
            seed=request.config.seed,
            num_ctx=request.config.num_ctx,
            num_predict=num_predict,
            think=request.config.think,
        ),
        permitted_attempt_count=request.config.max_attempts,
        attempts=(attempt,),
    )


def _failure(
    kind: ParserKind,
    input_hash: str,
    request_hash: str,
    status: ParserStatus,
    error: Exception,
    *,
    cache_hit: bool = False,
) -> ParseExecution:
    return ParseExecution(
        outcome=ParserOutcome(
            parser_kind=kind,
            input_hash=input_hash,
            request_hash=request_hash,
            status=status,
            cache_hit=cache_hit,
            error_type=type(error).__name__,
            error_message=str(error)[:1000],
        ),
        candidate=None,
    )
