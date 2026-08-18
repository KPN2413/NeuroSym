from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verilogic_ns_api.research.models import MetricReport

SHA256_PATTERN = r"^[a-f0-9]{64}$"
COMMIT_PATTERN = r"^[a-f0-9]{40}$"
SAFE_PATH_PATTERN = r"^[A-Za-z0-9_.][A-Za-z0-9_./-]{0,299}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FrozenArtifact(StrictModel):
    artifact_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,127}$")
    path: str = Field(pattern=SAFE_PATH_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def safe_path(self) -> Self:
        normalized = self.path.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            raise ValueError("frozen artifact path must be repository-relative")
        return self


class Phase9FreezeManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    protocol_label: Literal["Phase 9 regenerated evidence under newly frozen protocol"]
    parent_checkpoint: str = Field(pattern=COMMIT_PATTERN)
    dataset: Literal["ProofWriter"] = "ProofWriter"
    dataset_version: Literal["V2020.12.3"] = "V2020.12.3"
    archive_sha256: str = Field(pattern=SHA256_PATTERN)
    world_assumption: Literal["OWA"] = "OWA"
    variant: Literal["depth-5"] = "depth-5"
    split: Literal["dev"] = "dev"
    test_split_forbidden: Literal[True] = True
    sample_size: Literal[30] = 30
    seed: Literal[20260818] = 20260818
    selection_manifest_hash: str = Field(pattern=SHA256_PATTERN)
    demonstration_manifest_hash: str = Field(pattern=SHA256_PATTERN)
    provider: Literal["ollama-local-only"] = "ollama-local-only"
    endpoint: Literal["http://127.0.0.1:11434"] = "http://127.0.0.1:11434"
    provider_version: Literal["0.32.1"] = "0.32.1"
    model: Literal["qwen3.5:4b-q4_K_M"] = "qwen3.5:4b-q4_K_M"
    model_digest: str = Field(pattern=SHA256_PATTERN)
    think: Literal[False] = False
    temperature: Literal[0] = 0
    conditions: tuple[str, ...] = Field(min_length=7, max_length=7)
    artifacts: tuple[FrozenArtifact, ...] = Field(min_length=1)
    freeze_hash: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def unique_contract(self) -> Self:
        expected = {
            "direct",
            "few_shot",
            "p0_raw_neuro_symbolic",
            "validation_only",
            "p1_corrected_valid",
            "p2_corrected_selective",
            "oracle_structure_symbolic_ceiling",
        }
        if set(self.conditions) != expected:
            raise ValueError("Phase 9 conditions do not match the frozen protocol")
        ids = [item.artifact_id for item in self.artifacts]
        paths = [item.path for item in self.artifacts]
        if len(ids) != len(set(ids)) or len(paths) != len(set(paths)):
            raise ValueError("frozen artifact identifiers and paths must be unique")
        return self


class ComparisonKind(StrEnum):
    PAIRED_COMPONENT_ABLATION = "PAIRED_COMPONENT_ABLATION"
    SAME_SELECTION_DIFFERENT_REPRESENTATION = "SAME_SELECTION_DIFFERENT_REPRESENTATION"


class Phase9Comparison(StrictModel):
    comparison_id: str
    comparison_kind: ComparisonKind
    baseline_condition: str
    changed_condition: str
    changed_component: str
    same_selection: Literal[True] = True
    paired: bool
    accuracy_delta: float | None
    coverage_delta: float | None
    warning: str

    @model_validator(mode="after")
    def compatibility_contract(self) -> Self:
        if self.comparison_kind is ComparisonKind.PAIRED_COMPONENT_ABLATION and not self.paired:
            raise ValueError("component ablations must be paired")
        if (
            self.comparison_kind is ComparisonKind.SAME_SELECTION_DIFFERENT_REPRESENTATION
            and self.paired
        ):
            raise ValueError("different-representation comparisons cannot be paired")
        return self


class Phase9ConditionAggregate(StrictModel):
    experiment_id: str
    condition: str
    policy_mode: str | None
    dataset: Literal["ProofWriter"] = "ProofWriter"
    dataset_version: Literal["V2020.12.3"] = "V2020.12.3"
    split: Literal["dev"] = "dev"
    sample_size: Literal[30] = 30
    selection_manifest_hash: str = Field(pattern=SHA256_PATTERN)
    model: str | None
    model_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    config_hash: str = Field(pattern=SHA256_PATTERN)
    cache_mode: str
    provider_call_count: int = Field(ge=0)
    api_cost_usd: Literal[0.0] = 0.0
    runtime_seconds: float | None = Field(default=None, ge=0)
    metrics: MetricReport
    proof_attempted: int | None = Field(default=None, ge=0)
    proof_verified: int | None = Field(default=None, ge=0)
    raw_records_sha256: str = Field(pattern=SHA256_PATTERN)
    limitations: tuple[str, ...] = ()

    @model_validator(mode="after")
    def proof_counts(self) -> Self:
        if self.metrics.total_examples != self.sample_size:
            raise ValueError("condition metrics do not match the frozen sample size")
        if (
            self.proof_attempted is not None
            and self.proof_verified is not None
            and self.proof_verified > self.proof_attempted
        ):
            raise ValueError("verified proof count cannot exceed attempted proofs")
        return self


class Phase9AggregateReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    protocol_label: Literal["Phase 9 regenerated evidence under newly frozen protocol"]
    status: Literal["COMPLETE"] = "COMPLETE"
    execution_commit: str = Field(pattern=COMMIT_PATTERN)
    freeze_hash: str = Field(pattern=SHA256_PATTERN)
    archive_sha256: str = Field(pattern=SHA256_PATTERN)
    selection_manifest_hash: str = Field(pattern=SHA256_PATTERN)
    test_split_used: Literal[False] = False
    hosted_provider_calls: Literal[0] = 0
    api_cost_usd: Literal[0.0] = 0.0
    conditions: tuple[Phase9ConditionAggregate, ...] = Field(min_length=7, max_length=7)
    comparisons: tuple[Phase9Comparison, ...] = Field(min_length=5)
    replay_verified: bool
    limitations: tuple[str, ...] = Field(min_length=1)
    report_fingerprint: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def unique_conditions(self) -> Self:
        names = [item.condition for item in self.conditions]
        if len(names) != len(set(names)):
            raise ValueError("aggregate conditions must be unique")
        return self
