from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.semantic_parsing.models import (
    CandidateQueryOutput,
    CandidateTheoryOutput,
    ParserResponse,
)
from verilogic_ns_api.semantic_parsing.provider import (
    ParserConfigurationError,
    ParserProviderError,
    ParserStructuredOutputError,
    ParserTimeoutError,
    ParserTransientError,
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
    validation_error_hash,
)
from verilogic_ns_api.validation_correction.cache import (
    CorrectionCacheError,
    CorrectionResponseCache,
)
from verilogic_ns_api.validation_correction.models import (
    CorrectionExperimentConfig,
    QueryCorrectionInput,
    QueryCriticInput,
    QueryCriticReport,
    TaskKind,
    TaskOutcome,
    TaskStatus,
    TheoryCorrectionInput,
    TheoryCriticInput,
    TheoryCriticReport,
)
from verilogic_ns_api.validation_correction.prompts import (
    render_correction_input,
    render_critic_input,
)
from verilogic_ns_api.validation_correction.provider import (
    CorrectionTaskRequest,
    OllamaCorrectionProvider,
)

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class TaskExecution(Generic[T]):
    outcome: TaskOutcome
    value: T | None


class CorrectionTaskService:
    def __init__(
        self,
        *,
        config: CorrectionExperimentConfig,
        prompts: dict[TaskKind, tuple[str, str]],
        cache: CorrectionResponseCache,
        provider: OllamaCorrectionProvider | None,
        replay_only: bool = False,
    ) -> None:
        self.config = config
        self.prompts = prompts
        self.cache = cache
        self.provider = provider
        self.replay_only = replay_only
        self.new_call_count = 0

    def critique_theory(self, value: TheoryCriticInput) -> TaskExecution[TheoryCriticReport]:
        return self._execute(
            kind=TaskKind.CRITIC_THEORY,
            value=value,
            rendered=render_critic_input(value),
            output_model=TheoryCriticReport,
        )

    def critique_query(self, value: QueryCriticInput) -> TaskExecution[QueryCriticReport]:
        return self._execute(
            kind=TaskKind.CRITIC_QUERY,
            value=value,
            rendered=render_critic_input(value),
            output_model=QueryCriticReport,
        )

    def correct_theory(self, value: TheoryCorrectionInput) -> TaskExecution[CandidateTheoryOutput]:
        return self._execute(
            kind=TaskKind.CORRECTION_THEORY,
            value=value,
            rendered=render_correction_input(value),
            output_model=CandidateTheoryOutput,
        )

    def correct_query(self, value: QueryCorrectionInput) -> TaskExecution[CandidateQueryOutput]:
        return self._execute(
            kind=TaskKind.CORRECTION_QUERY,
            value=value,
            rendered=render_correction_input(value),
            output_model=CandidateQueryOutput,
        )

    def _execute(
        self,
        *,
        kind: TaskKind,
        value: BaseModel,
        rendered: str,
        output_model: type[T],
    ) -> TaskExecution[T]:
        if len(rendered) > self.config.limits.maximum_request_characters:
            return _failure(
                kind, "0" * 64, TaskStatus.PROVIDER_ERROR, ValueError("request too large")
            )
        prompt, prompt_hash = self.prompts[kind]
        schema = output_model.model_json_schema()
        request = CorrectionTaskRequest(
            task_kind=kind,
            instructions=prompt,
            input_text=rendered,
            prompt_hash=prompt_hash,
            input_hash=sha256_payload(value.model_dump(mode="json")),
            output_schema=schema,
            schema_hash=sha256_payload(schema),
            num_predict=self._num_predict(kind),
            config=self.config.runtime,
        )
        try:
            cached = self.cache.load_outcome(request)
        except CorrectionCacheError as error:
            return _failure(kind, request.request_hash, TaskStatus.PROVIDER_ERROR, error)
        if cached is not None and cached.outcome_type is CachedOutcomeType.TERMINAL_ERROR:
            assert cached.terminal_error is not None
            return _terminal_execution(kind, cached.terminal_error)
        response = cached.response if cached is not None else None
        cache_hit = cached is not None
        if cached is None:
            if self.replay_only or self.provider is None:
                return _failure(
                    kind,
                    request.request_hash,
                    TaskStatus.PROVIDER_ERROR,
                    RuntimeError("cache miss in correction replay-only mode"),
                )
            if self.new_call_count >= self.config.limits.maximum_new_pilot_calls:
                return _failure(
                    kind,
                    request.request_hash,
                    TaskStatus.RESOURCE_LIMIT,
                    RuntimeError("frozen Phase 6 local-call budget reached"),
                )
            self.new_call_count += 1
            dispatched = self._dispatch(request)
            if isinstance(dispatched, TaskExecution):
                terminal = _terminal_from_failure(request, dispatched.outcome, self.config)
                self.cache.store_terminal(request, terminal)
                return _terminal_execution(kind, terminal, cache_hit=False)
            response = dispatched
        try:
            parsed = output_model.model_validate(response.content)
        except ValidationError as error:
            terminal = _terminal_from_invalid_response(
                request,
                response,
                self.config,
                error,
            )
            if cached is None:
                self.cache.store_terminal(request, terminal)
            return _terminal_execution(kind, terminal, cache_hit=cache_hit)
        if cached is None:
            self.cache.store(request, response)
        return TaskExecution(
            outcome=TaskOutcome(
                task_kind=kind,
                request_hash=request.request_hash,
                status=TaskStatus.SUCCESS,
                cache_hit=cache_hit,
                output=parsed.model_dump(mode="json"),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                duration_ms=response.timing.total_duration_ms,
            ),
            value=parsed,
        )

    def _dispatch(self, request: CorrectionTaskRequest) -> object:
        assert self.provider is not None
        for attempt in range(self.config.runtime.max_attempts):
            try:
                return self.provider.complete(request)
            except ParserTimeoutError as error:
                if attempt + 1 == self.config.runtime.max_attempts:
                    return _failure(
                        request.task_kind, request.request_hash, TaskStatus.TIMEOUT, error
                    )
            except ParserTransientError as error:
                if attempt + 1 == self.config.runtime.max_attempts:
                    return _failure(
                        request.task_kind, request.request_hash, TaskStatus.PROVIDER_ERROR, error
                    )
            except ParserStructuredOutputError as error:
                return _failure(
                    request.task_kind,
                    request.request_hash,
                    TaskStatus.STRUCTURED_OUTPUT_ERROR,
                    error,
                )
            except (ParserConfigurationError, ParserProviderError) as error:
                return _failure(
                    request.task_kind, request.request_hash, TaskStatus.PROVIDER_ERROR, error
                )
            time.sleep(0.25 * (2**attempt))
        raise AssertionError("unreachable correction retry state")

    def _num_predict(self, kind: TaskKind) -> int:
        limits = self.config.limits
        return {
            TaskKind.CRITIC_THEORY: limits.critic_theory_num_predict,
            TaskKind.CRITIC_QUERY: limits.critic_query_num_predict,
            TaskKind.CORRECTION_THEORY: limits.correction_theory_num_predict,
            TaskKind.CORRECTION_QUERY: limits.correction_query_num_predict,
        }[kind]


def _terminal_from_failure(
    request: CorrectionTaskRequest,
    outcome: TaskOutcome,
    config: CorrectionExperimentConfig,
) -> TerminalProviderOutcome:
    observed_attempts = (
        1 if outcome.status is TaskStatus.STRUCTURED_OUTPUT_ERROR else config.runtime.max_attempts
    )
    observed_at = datetime.now(UTC)
    attempts = tuple(
        AttemptEvidence(
            attempt_number=index,
            request_hash=request.request_hash,
            evidence_sha256=sha256_payload(
                {
                    "namespace": "phase6-r3-live-terminal-attempt.v1",
                    "request_hash": request.request_hash,
                    "attempt": index,
                    "status": outcome.status,
                    "error_type": outcome.error_type,
                    "error_message": outcome.error_message,
                }
            ),
            finish_reason="provider_error",
            input_tokens=None,
            output_tokens=None,
            total_duration_ms=None,
            observed_at=observed_at,
        )
        for index in range(1, observed_attempts + 1)
    )
    stage = {
        TaskKind.CRITIC_THEORY: TerminalStage.THEORY_CRITIC,
        TaskKind.CRITIC_QUERY: TerminalStage.QUERY_CRITIC,
        TaskKind.CORRECTION_THEORY: TerminalStage.THEORY_CORRECTION,
        TaskKind.CORRECTION_QUERY: TerminalStage.QUERY_CORRECTION,
    }[request.task_kind]
    error_code = {
        TaskStatus.STRUCTURED_OUTPUT_ERROR: TerminalErrorCode.INVALID_STRUCTURED_OUTPUT,
        TaskStatus.TIMEOUT: TerminalErrorCode.TIMEOUT_EXHAUSTED,
        TaskStatus.PROVIDER_ERROR: TerminalErrorCode.PROVIDER_FAILURE,
        TaskStatus.RESOURCE_LIMIT: TerminalErrorCode.PROVIDER_FAILURE,
        TaskStatus.SUCCESS: TerminalErrorCode.PROVIDER_FAILURE,
    }[outcome.status]
    pipeline_status = {
        TaskStatus.STRUCTURED_OUTPUT_ERROR: PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        TaskStatus.TIMEOUT: PipelineFailureStatus.TIMEOUT,
        TaskStatus.PROVIDER_ERROR: PipelineFailureStatus.PROVIDER_ERROR,
        TaskStatus.RESOURCE_LIMIT: PipelineFailureStatus.PROVIDER_ERROR,
        TaskStatus.SUCCESS: PipelineFailureStatus.PROVIDER_ERROR,
    }[outcome.status]
    runtime = TerminalRuntime(
        endpoint=config.runtime.endpoint,
        provider_version=config.runtime.provider_version,
        model=config.runtime.model,
        model_digest=config.runtime.model_digest,
        temperature=config.runtime.temperature,
        seed=config.runtime.seed,
        num_ctx=config.runtime.num_ctx,
        num_predict=request.num_predict,
        think=config.runtime.think,
    )
    return build_terminal_outcome(
        stage=stage,
        error_code=error_code,
        pipeline_status=pipeline_status,
        reason=(outcome.error_message or outcome.error_type or "terminal provider failure")[:500],
        request_identity=request.identity(),
        semantic_config_hash=sha256_payload(
            {
                "runtime": config.runtime.model_dump(mode="json"),
                "limits": config.limits.model_dump(mode="json"),
            }
        ),
        runtime=runtime,
        permitted_attempt_count=config.runtime.max_attempts,
        attempts=attempts,
    )


def _terminal_from_invalid_response(
    request: CorrectionTaskRequest,
    response: ParserResponse,
    config: CorrectionExperimentConfig,
    error: ValidationError,
) -> TerminalProviderOutcome:
    evidence = sha256_payload(
        {
            "namespace": "phase6-r3-invalid-correction-response.v1",
            "request_hash": request.request_hash,
            "response_content_sha256": sha256_payload(response.content),
            "validation_error_sha256": validation_error_hash(error),
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
    stage = {
        TaskKind.CRITIC_THEORY: TerminalStage.THEORY_CRITIC,
        TaskKind.CRITIC_QUERY: TerminalStage.QUERY_CRITIC,
        TaskKind.CORRECTION_THEORY: TerminalStage.THEORY_CORRECTION,
        TaskKind.CORRECTION_QUERY: TerminalStage.QUERY_CORRECTION,
    }[request.task_kind]
    return build_terminal_outcome(
        stage=stage,
        error_code=TerminalErrorCode.INVALID_STRUCTURED_OUTPUT,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason="Provider response failed the frozen task output schema.",
        request_identity=request.identity(),
        semantic_config_hash=sha256_payload(
            {
                "runtime": config.runtime.model_dump(mode="json"),
                "limits": config.limits.model_dump(mode="json"),
            }
        ),
        runtime=TerminalRuntime(
            endpoint=config.runtime.endpoint,
            provider_version=config.runtime.provider_version,
            model=config.runtime.model,
            model_digest=config.runtime.model_digest,
            temperature=config.runtime.temperature,
            seed=config.runtime.seed,
            num_ctx=config.runtime.num_ctx,
            num_predict=request.num_predict,
            think=config.runtime.think,
        ),
        permitted_attempt_count=config.runtime.max_attempts,
        attempts=(attempt,),
    )


def _terminal_execution(
    kind: TaskKind,
    terminal: TerminalProviderOutcome,
    *,
    cache_hit: bool = True,
) -> TaskExecution:
    status = {
        PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR: TaskStatus.STRUCTURED_OUTPUT_ERROR,
        PipelineFailureStatus.TIMEOUT: TaskStatus.TIMEOUT,
        PipelineFailureStatus.PROVIDER_ERROR: TaskStatus.PROVIDER_ERROR,
    }[terminal.pipeline_status]
    input_tokens, output_tokens, duration_ms = _terminal_accounting(terminal)
    return TaskExecution(
        outcome=TaskOutcome(
            task_kind=kind,
            request_hash=terminal.request_hash,
            status=status,
            cache_hit=cache_hit,
            error_type=terminal.error_code.value,
            error_message=terminal.reason,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
            terminal=True,
            terminal_outcome_hash=terminal.terminal_outcome_sha256,
        ),
        value=None,
    )


def _terminal_accounting(
    terminal: TerminalProviderOutcome,
) -> tuple[int | None, int | None, float | None]:
    """Interpret legacy provider-error zeroes as unavailable response telemetry."""
    aggregate_is_zero = (
        terminal.input_tokens == 0
        and terminal.output_tokens == 0
        and terminal.total_duration_ms == 0
    )
    provider_failed_before_response = any(
        attempt.finish_reason == "provider_error" for attempt in terminal.attempts
    )
    if aggregate_is_zero and provider_failed_before_response:
        return None, None, None
    return terminal.input_tokens, terminal.output_tokens, terminal.total_duration_ms


def _failure(
    kind: TaskKind,
    request_hash: str,
    status: TaskStatus,
    error: Exception,
    *,
    cache_hit: bool = False,
) -> TaskExecution:
    return TaskExecution(
        outcome=TaskOutcome(
            task_kind=kind,
            request_hash=request_hash,
            status=status,
            cache_hit=cache_hit,
            error_type=type(error).__name__,
            error_message=str(error)[:500],
        ),
        value=None,
    )
