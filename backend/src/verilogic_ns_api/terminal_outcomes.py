from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.semantic_parsing.models import ParserResponse

SHA256_PATTERN = r"^[a-f0-9]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CachedOutcomeType(StrEnum):
    SUCCESS = "SUCCESS"
    TERMINAL_ERROR = "TERMINAL_ERROR"


class TerminalStage(StrEnum):
    SEMANTIC_PARSER_THEORY = "semantic_parser_theory"
    SEMANTIC_PARSER_QUERY = "semantic_parser_query"
    THEORY_CRITIC = "theory_critic"
    QUERY_CRITIC = "query_critic"
    THEORY_CORRECTION = "theory_correction"
    QUERY_CORRECTION = "query_correction"


class TerminalErrorCode(StrEnum):
    OUTPUT_LIMIT_EXHAUSTED = "OUTPUT_LIMIT_EXHAUSTED"
    INVALID_STRUCTURED_OUTPUT = "INVALID_STRUCTURED_OUTPUT"
    TIMEOUT_EXHAUSTED = "TIMEOUT_EXHAUSTED"
    TRANSIENT_RETRY_EXHAUSTED = "TRANSIENT_RETRY_EXHAUSTED"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"


class PipelineFailureStatus(StrEnum):
    STRUCTURED_OUTPUT_ERROR = "STRUCTURED_OUTPUT_ERROR"
    TIMEOUT = "TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class TerminalRuntime(StrictModel):
    endpoint: Literal["http://127.0.0.1:11434", "http://localhost:11434"]
    provider_version: str
    model: str
    model_digest: str = Field(pattern=SHA256_PATTERN)
    temperature: Literal[0]
    seed: int
    num_ctx: int = Field(ge=4096, le=32768)
    num_predict: int = Field(ge=1, le=8192)
    think: Literal[False]
    concurrency: Literal[1] = 1


class AttemptEvidence(StrictModel):
    attempt_number: int = Field(ge=1, le=3)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    evidence_sha256: str = Field(pattern=SHA256_PATTERN)
    finish_reason: str | None = Field(default=None, max_length=128)
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    total_duration_ms: float | None = Field(ge=0)
    observed_at: datetime
    valid_structured_result: Literal[False] = False


class TerminalProviderOutcome(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    outcome_type: Literal[CachedOutcomeType.TERMINAL_ERROR] = CachedOutcomeType.TERMINAL_ERROR
    outcome_id: str = Field(pattern=SHA256_PATTERN)
    stage: TerminalStage
    error_code: TerminalErrorCode
    pipeline_status: PipelineFailureStatus
    reason: str = Field(min_length=1, max_length=500)
    request_hash: str = Field(pattern=SHA256_PATTERN)
    prompt_hash: str = Field(pattern=SHA256_PATTERN)
    output_schema_hash: str = Field(pattern=SHA256_PATTERN)
    semantic_config_hash: str = Field(pattern=SHA256_PATTERN)
    provider: Literal["ollama"] = "ollama"
    model: str
    model_digest: str = Field(pattern=SHA256_PATTERN)
    runtime: TerminalRuntime
    permitted_attempt_count: int = Field(ge=1, le=3)
    observed_attempt_count: int = Field(ge=1, le=3)
    output_token_limit: int = Field(ge=1, le=8192)
    attempts: tuple[AttemptEvidence, ...] = Field(min_length=1, max_length=3)
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    total_duration_ms: float | None = Field(ge=0)
    attempt_evidence_hashes: tuple[str, ...] = Field(min_length=1, max_length=3)
    first_observed_at: datetime
    last_observed_at: datetime
    valid_structured_result_produced: Literal[False] = False
    final: Literal[True] = True
    terminal_outcome_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def verify_provenance_and_hash(self) -> Self:
        if self.model != self.runtime.model or self.model_digest != self.runtime.model_digest:
            raise ValueError("terminal model contract does not match runtime")
        if self.output_token_limit != self.runtime.num_predict:
            raise ValueError("terminal output limit does not match runtime")
        if self.observed_attempt_count != len(self.attempts):
            raise ValueError("terminal observed attempt count is inconsistent")
        if self.observed_attempt_count > self.permitted_attempt_count:
            raise ValueError("terminal attempts exceed the permitted budget")
        if tuple(item.evidence_sha256 for item in self.attempts) != self.attempt_evidence_hashes:
            raise ValueError("terminal attempt evidence hashes are inconsistent")
        if any(item.request_hash != self.request_hash for item in self.attempts):
            raise ValueError("terminal attempt evidence belongs to another request")
        if self.input_tokens != _sum_accounting(item.input_tokens for item in self.attempts):
            raise ValueError("terminal input-token accounting is inconsistent")
        if self.output_tokens != _sum_accounting(item.output_tokens for item in self.attempts):
            raise ValueError("terminal output-token accounting is inconsistent")
        if self.total_duration_ms != _sum_accounting(
            item.total_duration_ms for item in self.attempts
        ):
            raise ValueError("terminal duration accounting is inconsistent")
        if self.first_observed_at != min(item.observed_at for item in self.attempts):
            raise ValueError("terminal first timestamp is inconsistent")
        if self.last_observed_at != max(item.observed_at for item in self.attempts):
            raise ValueError("terminal last timestamp is inconsistent")
        if self.outcome_id != terminal_outcome_id(self.stage, self.request_hash):
            raise ValueError("terminal outcome ID is inconsistent")
        if self.terminal_outcome_sha256 != terminal_outcome_hash(self):
            raise ValueError("terminal outcome hash is inconsistent")
        return self


class SuccessCacheEnvelope(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    outcome_type: Literal[CachedOutcomeType.SUCCESS] | None = None
    request_identity: dict[str, object]
    response: ParserResponse

    @model_validator(mode="after")
    def response_matches_request(self) -> Self:
        if self.response.request_hash != sha256_payload(self.request_identity):
            raise ValueError("success response hash differs from cache identity")
        return self


class TerminalCacheEnvelope(StrictModel):
    schema_version: Literal["2.0"] = "2.0"
    outcome_type: Literal[CachedOutcomeType.TERMINAL_ERROR] = CachedOutcomeType.TERMINAL_ERROR
    request_identity: dict[str, object]
    terminal_error: TerminalProviderOutcome

    @model_validator(mode="after")
    def request_matches_terminal(self) -> Self:
        if self.request_identity.get("prompt_hash") != self.terminal_error.prompt_hash:
            raise ValueError("terminal prompt hash differs from cache request")
        if self.request_identity.get("schema_hash") != self.terminal_error.output_schema_hash:
            raise ValueError("terminal schema hash differs from cache request")
        if self.terminal_error.request_hash != sha256_payload(self.request_identity):
            raise ValueError("terminal request hash differs from cache identity")
        runtime = self.terminal_error.runtime
        expected_options = {
            "num_ctx": runtime.num_ctx,
            "num_predict": runtime.num_predict,
            "seed": runtime.seed,
            "temperature": runtime.temperature,
            "think": runtime.think,
        }
        options = self.request_identity.get("options")
        if not isinstance(options, dict) or any(
            options.get(key) != value for key, value in expected_options.items()
        ):
            raise ValueError("terminal runtime differs from cache request")
        if (
            self.request_identity.get("endpoint") != runtime.endpoint
            or self.request_identity.get("model") != runtime.model
            or self.request_identity.get("model_digest") != runtime.model_digest
            or self.request_identity.get("provider_version") != runtime.provider_version
        ):
            raise ValueError("terminal provider contract differs from cache request")
        return self


def terminal_outcome_id(stage: TerminalStage, request_hash: str) -> str:
    return sha256_payload(
        {"namespace": "terminal-provider-outcome.v1", "stage": stage, "request_hash": request_hash}
    )


def terminal_outcome_hash(outcome: TerminalProviderOutcome) -> str:
    return sha256_payload(outcome.model_dump(mode="json", exclude={"terminal_outcome_sha256"}))


def validation_error_hash(error: ValidationError) -> str:
    """Hash Pydantic errors through its JSON encoder, including stringified ctx exceptions."""
    return sha256_payload(error.json(include_url=False))


def _sum_accounting(values: Iterable[int | float | None]) -> int | float | None:
    observed = tuple(values)
    if any(value is None for value in observed):
        return None
    return sum(value for value in observed if value is not None)


def build_terminal_outcome(
    *,
    stage: TerminalStage,
    error_code: TerminalErrorCode,
    pipeline_status: PipelineFailureStatus,
    reason: str,
    request_identity: dict[str, object],
    semantic_config_hash: str,
    runtime: TerminalRuntime,
    permitted_attempt_count: int,
    attempts: tuple[AttemptEvidence, ...],
) -> TerminalProviderOutcome:
    request_hash = sha256_payload(request_identity)
    values = {
        "stage": stage,
        "error_code": error_code,
        "pipeline_status": pipeline_status,
        "reason": reason,
        "request_hash": request_hash,
        "prompt_hash": request_identity["prompt_hash"],
        "output_schema_hash": request_identity["schema_hash"],
        "semantic_config_hash": semantic_config_hash,
        "model": runtime.model,
        "model_digest": runtime.model_digest,
        "runtime": runtime,
        "permitted_attempt_count": permitted_attempt_count,
        "observed_attempt_count": len(attempts),
        "output_token_limit": runtime.num_predict,
        "attempts": attempts,
        "input_tokens": _sum_accounting(item.input_tokens for item in attempts),
        "output_tokens": _sum_accounting(item.output_tokens for item in attempts),
        "total_duration_ms": _sum_accounting(item.total_duration_ms for item in attempts),
        "attempt_evidence_hashes": tuple(item.evidence_sha256 for item in attempts),
        "first_observed_at": min(item.observed_at for item in attempts),
        "last_observed_at": max(item.observed_at for item in attempts),
        "outcome_id": terminal_outcome_id(stage, request_hash),
        "terminal_outcome_sha256": "0" * 64,
    }
    provisional = TerminalProviderOutcome.model_construct(**values)
    values["terminal_outcome_sha256"] = terminal_outcome_hash(provisional)
    return TerminalProviderOutcome.model_validate(values)
