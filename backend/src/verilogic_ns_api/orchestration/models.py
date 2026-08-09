from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verilogic_ns_api.reasoning.models import (
    GroundLiteral,
    ProofDAG,
    ProofVerificationResult,
    ReasoningStatus,
    ReasoningTelemetry,
    Theory,
    sha256_payload,
)

SHA256_PATTERN = r"^[a-f0-9]{64}$"
SOURCE_ID_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InputMode(StrEnum):
    NATURAL_LANGUAGE = "NATURAL_LANGUAGE"
    FORMAL_AST = "FORMAL_AST"


class PolicyMode(StrEnum):
    P0_RAW = "P0_RAW"
    P1_CORRECTED = "P1_CORRECTED"
    P2_SELECTIVE = "P2_SELECTIVE"


class PipelineDisposition(StrEnum):
    ANSWERED = "ANSWERED"
    ABSTAINED = "ABSTAINED"
    ERROR = "ERROR"


class StageName(StrEnum):
    INPUT_VALIDATION = "INPUT_VALIDATION"
    THEORY_PARSING = "THEORY_PARSING"
    QUERY_PARSING = "QUERY_PARSING"
    SOURCE_COVERAGE = "SOURCE_COVERAGE"
    SEMANTIC_VALIDATION = "SEMANTIC_VALIDATION"
    CRITIC = "CRITIC"
    CORRECTION = "CORRECTION"
    RELIABILITY_POLICY = "RELIABILITY_POLICY"
    SYMBOLIC_REASONING = "SYMBOLIC_REASONING"
    PROOF_VERIFICATION = "PROOF_VERIFICATION"
    FINAL_DECISION = "FINAL_DECISION"


class StageStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    SKIPPED = "SKIPPED"
    ABSTAINED = "ABSTAINED"
    FAILED = "FAILED"


class ProviderMode(StrEnum):
    LIVE = "live"
    CACHE_ONLY = "cache_only"


class StatementKind(StrEnum):
    FACT = "fact"
    RULE = "rule"


class NaturalLanguageStatement(StrictModel):
    source_id: str | None = Field(default=None, pattern=SOURCE_ID_PATTERN)
    kind: StatementKind
    text: str = Field(min_length=1, max_length=10_000)


class NaturalLanguageInput(StrictModel):
    statements: tuple[NaturalLanguageStatement, ...] = Field(min_length=1, max_length=32)
    query: str = Field(min_length=1, max_length=10_000)

    @model_validator(mode="after")
    def unique_source_ids(self) -> Self:
        ids = [item.source_id for item in self.statements if item.source_id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("natural-language source IDs must be unique")
        if "query" in ids:
            raise ValueError("the source ID 'query' is reserved for the query")
        total = sum(len(item.text) for item in self.statements) + len(self.query)
        if total > 50_000:
            raise ValueError("natural-language request exceeds the 50,000 character limit")
        return self


class FormalAstInput(StrictModel):
    theory: Theory
    query: GroundLiteral

    def resolved_theory(self) -> Theory:
        payload = self.theory.model_dump(mode="json")
        payload["query"] = self.query.model_dump(mode="json")
        return Theory.model_validate(payload)


class PipelineRequest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    input_mode: InputMode
    policy_mode: PolicyMode = PolicyMode.P2_SELECTIVE
    natural_language: NaturalLanguageInput | None = None
    formal_ast: FormalAstInput | None = None

    @model_validator(mode="after")
    def mode_matches_payload(self) -> Self:
        if self.input_mode is InputMode.NATURAL_LANGUAGE:
            if self.natural_language is None or self.formal_ast is not None:
                raise ValueError("NATURAL_LANGUAGE requires only natural_language input")
        elif self.formal_ast is None or self.natural_language is not None:
            raise ValueError("FORMAL_AST requires only formal_ast input")
        return self

    @property
    def canonical_hash(self) -> str:
        return sha256_payload(self.model_dump(mode="json"))


class StageTrace(StrictModel):
    stage: StageName
    status: StageStatus
    duration_ms: float = Field(default=0, ge=0)
    cache_status: Literal["hit", "miss", "mixed", "not_applicable"] = "not_applicable"
    error_code: str | None = Field(default=None, max_length=128)
    message: str | None = Field(default=None, max_length=500)


class ExplanationStep(StrictModel):
    sequence: int = Field(ge=1)
    kind: Literal["fact", "rule"]
    statement: str = Field(min_length=1, max_length=1_000)
    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    source_text: str = Field(min_length=1, max_length=10_000)
    depth: int = Field(ge=0)
    node_id: str = Field(pattern=SHA256_PATTERN)


class DeterministicExplanation(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    headline: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1, max_length=1_000)
    steps: tuple[ExplanationStep, ...] = Field(default=(), max_length=100_000)
    support_root_id: str | None = Field(default=None, pattern=SHA256_PATTERN)
    opposition_root_id: str | None = Field(default=None, pattern=SHA256_PATTERN)
    proof_depth: int | None = Field(default=None, ge=0)
    proof_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    verifier_status: Literal["VERIFIED", "NOT_APPLICABLE"]
    reasons: tuple[str, ...] = Field(default=(), max_length=16)


class PipelineError(StrictModel):
    stage: StageName
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")
    message: str = Field(min_length=1, max_length=500)


class PipelineProvenance(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    input_hash: str = Field(pattern=SHA256_PATTERN)
    input_mode: InputMode
    policy_mode: PolicyMode
    provider_mode: ProviderMode
    engine_version: str
    model_used: bool
    model_name: str | None = None
    model_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    provider_version: str | None = None
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    schema_hashes: dict[str, str] = Field(default_factory=dict)
    policy_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    theory_hash: str | None = Field(default=None, pattern=SHA256_PATTERN)
    proof_verified: bool = False
    provider_dispatches: int = Field(default=0, ge=0, le=12)
    cache_hits: int = Field(default=0, ge=0)
    cache_misses: int = Field(default=0, ge=0)


class PipelineResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    disposition: PipelineDisposition
    logical_result: ReasoningStatus | None = None
    explanation: DeterministicExplanation
    trace: tuple[StageTrace, ...] = Field(min_length=11, max_length=11)
    provenance: PipelineProvenance
    proof: ProofDAG | None = None
    proof_verification: ProofVerificationResult | None = None
    reasoning_telemetry: ReasoningTelemetry | None = None
    accepted_theory: Theory | None = None
    correction_attempted: bool = False
    abstention_reason: str | None = Field(default=None, max_length=128)
    error: PipelineError | None = None

    @model_validator(mode="after")
    def disposition_contract(self) -> Self:
        if self.disposition is PipelineDisposition.ANSWERED:
            if self.logical_result is None or self.error is not None:
                raise ValueError("ANSWERED requires a logical result and no error")
            if self.proof is None or self.proof_verification is None:
                raise ValueError("ANSWERED requires an independently verified proof")
        elif self.logical_result is not None:
            raise ValueError("ABSTAINED and ERROR cannot include a logical result")
        if self.disposition is PipelineDisposition.ERROR and self.error is None:
            raise ValueError("ERROR requires typed error details")
        if self.disposition is not PipelineDisposition.ERROR and self.error is not None:
            raise ValueError("only ERROR may include error details")
        if self.disposition is PipelineDisposition.ABSTAINED and not self.abstention_reason:
            raise ValueError("ABSTAINED requires a reason")
        return self


class RunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"


class PipelineRunAccepted(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    status: Literal[RunStatus.QUEUED, RunStatus.RUNNING]


class PipelineRunState(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    status: RunStatus
    current_stage: StageName | None = None
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: PipelineResult | None = None


class CapabilitiesResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    api_version: Literal["v1"] = "v1"
    supported_input_modes: tuple[InputMode, ...]
    supported_policy_modes: tuple[PolicyMode, ...]
    symbolic_engine_ready: bool
    local_model_ready: bool
    provider_mode: ProviderMode
    model_name: str
    model_digest: str = Field(pattern=SHA256_PATTERN)
    provider_version: str
    maximum_active_jobs: Literal[1] = 1
    maximum_queued_jobs: int = Field(ge=1, le=16)
    resource_limits: dict[str, int | float | None]
    schema_hashes: dict[str, str]


class ApiErrorResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")
    message: str = Field(min_length=1, max_length=500)
