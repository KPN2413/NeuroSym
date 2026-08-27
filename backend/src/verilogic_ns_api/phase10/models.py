from __future__ import annotations

import hashlib
import json
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SHA256_PATTERN = r"^[a-f0-9]{64}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinalConditionEvidence(StrictModel):
    condition: str
    correct: int = Field(ge=0, le=30)
    total: Literal[30] = 30
    answered: int = Field(ge=0, le=30)
    abstained: int = Field(ge=0, le=30)
    errors: int = Field(ge=0, le=30)
    coverage: float = Field(ge=0, le=1)
    answered_only_accuracy: float | None = Field(default=None, ge=0, le=1)
    proof_attempted: int | None = Field(default=None, ge=0, le=30)
    proof_verified: int | None = Field(default=None, ge=0, le=30)
    exact_input_tokens: int | None = Field(default=None, ge=0)
    exact_output_tokens: int | None = Field(default=None, ge=0)
    observed_input_tokens: int = Field(ge=0)
    observed_output_tokens: int = Field(ge=0)
    representation: Literal["natural_language", "formal_symbolic_ceiling"]

    @model_validator(mode="after")
    def denominators_are_preserved(self) -> Self:
        if self.answered + self.abstained + self.errors != self.total:
            raise ValueError("condition dispositions must preserve all 30 records")
        if (
            self.proof_verified is not None
            and self.proof_attempted is not None
            and self.proof_verified > self.proof_attempted
        ):
            raise ValueError("verified proof count exceeds attempted proof count")
        if (self.exact_input_tokens is None) != (self.exact_output_tokens is None):
            raise ValueError("exact token counts must be jointly available or unavailable")
        return self


class FinalComparisonEvidence(StrictModel):
    comparison_id: str
    baseline_condition: str
    changed_condition: str
    both_correct: int = Field(ge=0)
    baseline_only_correct: int = Field(ge=0)
    changed_only_correct: int = Field(ge=0)
    both_incorrect: int = Field(ge=0)
    interpretation: Literal["paired_descriptive", "different_representation_ceiling"]

    @model_validator(mode="after")
    def denominator_is_complete(self) -> Self:
        total = (
            self.both_correct
            + self.baseline_only_correct
            + self.changed_only_correct
            + self.both_incorrect
        )
        if total != 30:
            raise ValueError("comparison outcomes must preserve all 30 records")
        return self


class FinalEvidencePackage(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    phase9_aggregate_fingerprint: str = Field(pattern=SHA256_PATTERN)
    phase9_catalogue_hash: str = Field(pattern=SHA256_PATTERN)
    phase8_catalogue_hash: str = Field(pattern=SHA256_PATTERN)
    dataset: Literal["ProofWriter"] = "ProofWriter"
    dataset_version: Literal["V2020.12.3"] = "V2020.12.3"
    world_assumption: Literal["OWA"] = "OWA"
    variant: Literal["depth-5"] = "depth-5"
    split: Literal["development"] = "development"
    archive_sha256: str = Field(pattern=SHA256_PATTERN)
    freeze_hash: str = Field(pattern=SHA256_PATTERN)
    selection_seed: Literal[20260818] = 20260818
    evaluation_records: Literal[30] = 30
    few_shot_demonstrations: Literal[6] = 6
    train_development_overlap: Literal[0] = 0
    model: Literal["qwen3.5:4b-q4_K_M"] = "qwen3.5:4b-q4_K_M"
    model_digest: str = Field(pattern=SHA256_PATTERN)
    conditions: tuple[FinalConditionEvidence, ...] = Field(min_length=7, max_length=7)
    comparisons: tuple[FinalComparisonEvidence, ...] = Field(min_length=5, max_length=5)
    local_model_dispatches: Literal[190] = 190
    hosted_provider_calls: Literal[0] = 0
    external_transfers: Literal[0] = 0
    api_cost_usd: Literal[0.0] = 0.0
    test_split_access_count: Literal[0] = 0
    replay_verified_with_ollama_stopped: Literal[True] = True
    catalogue_experiments: Literal[19] = 19
    catalogue_comparisons: Literal[10] = 10
    terminal_correction_cache_failures: Literal[3] = 3
    limitations: tuple[str, ...] = Field(min_length=7)
    package_fingerprint: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def integrity(self) -> Self:
        names = [item.condition for item in self.conditions]
        if len(names) != len(set(names)):
            raise ValueError("final evidence conditions must be unique")
        payload = self.model_dump(mode="json", exclude={"package_fingerprint"})
        if _sha256_json(payload) != self.package_fingerprint:
            raise ValueError("final evidence package fingerprint mismatch")
        return self


class DemoCheck(StrictModel):
    name: str
    status: Literal["PASS"] = "PASS"
    detail: str


class DemoSmokeReport(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["PASS"] = "PASS"
    backend_origin: Literal["http://127.0.0.1:8000"]
    frontend_origin: Literal["http://127.0.0.1:3000"]
    provider_mode: Literal["cache_only"]
    provider_dispatches: Literal[0]
    logical_result: Literal["ENTAILED"]
    proof_verified: Literal[True]
    explanation_steps: int = Field(ge=1)
    catalogue_experiments: Literal[19]
    catalogue_comparisons: Literal[10]
    checks: tuple[DemoCheck, ...] = Field(min_length=10)


def _sha256_json(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def with_fingerprint(payload: dict[str, object]) -> FinalEvidencePackage:
    payload["package_fingerprint"] = _sha256_json(payload)
    return FinalEvidencePackage.model_validate(payload)
