from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from verilogic_ns_api.reasoning.models import Theory

SHA256_PATTERN = r"^[a-f0-9]{64}$"
COMMIT_PATTERN = r"^[a-f0-9]{40}$"
ID_PATTERN = r"^[a-z][a-z0-9_.-]{0,127}$"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceType(StrEnum):
    DIRECTLY_OBSERVED = "DIRECTLY_OBSERVED"
    DERIVED = "DERIVED"
    DOCUMENTED = "DOCUMENTED"
    UNAVAILABLE = "UNAVAILABLE"


class EvidenceVerification(StrEnum):
    HASH_VERIFIED = "HASH_VERIFIED"
    CROSS_CHECKED = "CROSS_CHECKED"
    SOURCE_HASH_RECORDED = "SOURCE_HASH_RECORDED"
    UNAVAILABLE = "UNAVAILABLE"


class ExperimentStatus(StrEnum):
    PASS = "PASS"
    BLOCKED = "BLOCKED"
    INVALIDATED = "INVALIDATED"
    COMPLETE_WITH_NEGATIVE_RESULT = "COMPLETE_WITH_NEGATIVE_RESULT"


class ComparisonType(StrEnum):
    PAIRED = "PAIRED"
    SAME_SELECTION_DIFFERENT_REPRESENTATION = "SAME_SELECTION_DIFFERENT_REPRESENTATION"
    DESCRIPTIVE_ONLY = "DESCRIPTIVE_ONLY"
    INCOMPARABLE = "INCOMPARABLE"


class SourceArtifact(StrictModel):
    artifact_id: str = Field(pattern=ID_PATTERN)
    path: str = Field(min_length=1, max_length=300)
    sha256: str = Field(pattern=SHA256_PATTERN)
    source_commit: str | None = Field(default=None, pattern=COMMIT_PATTERN)
    tracked: bool
    description: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def safe_relative_path(self) -> Self:
        normalized = self.path.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized or ".." in normalized.split("/"):
            raise ValueError("source artifact path must be a safe repository-relative identifier")
        return self


class MetricEvidence(StrictModel):
    metric_id: str = Field(pattern=ID_PATTERN)
    display_name: str = Field(min_length=1, max_length=200)
    value: float | int | None
    unit: str = Field(pattern=r"^[a-z][a-z0-9_.-]{0,63}$")
    numerator: float | int | None
    denominator: float | int | None
    dataset: str
    dataset_version: str
    split: str
    benchmark_variant: str
    sample_size: int = Field(ge=0)
    selection_manifest: str | None
    phase: str = Field(pattern=r"^Phase [3-7](?:-R[0-9]+)?$")
    condition: str
    policy_mode: str | None
    model_name: str | None
    model_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    run_id: str | None
    source_artifact: str = Field(pattern=ID_PATTERN)
    source_artifact_hash: str = Field(pattern=SHA256_PATTERN)
    source_commit: str | None = Field(default=None, pattern=COMMIT_PATTERN)
    evidence_type: EvidenceType
    derivation_formula: str | None
    comparability_group: str = Field(pattern=ID_PATTERN)
    limitations: tuple[str, ...] = Field(default=(), max_length=20)
    verification_status: EvidenceVerification
    dimensions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence_contract(self) -> Self:
        if self.evidence_type is EvidenceType.UNAVAILABLE:
            if (
                self.value is not None
                or self.verification_status is not EvidenceVerification.UNAVAILABLE
            ):
                raise ValueError(
                    "unavailable evidence must have a null value and unavailable status"
                )
        elif self.value is None:
            raise ValueError("available evidence requires a value")
        if self.evidence_type is EvidenceType.DERIVED and not self.derivation_formula:
            raise ValueError("derived metrics require a derivation formula")
        if self.denominator is not None and self.denominator < 0:
            raise ValueError("metric denominators cannot be negative")
        return self


class ExperimentDetail(StrictModel):
    experiment_id: str = Field(pattern=ID_PATTERN)
    name: str = Field(min_length=1, max_length=200)
    phase: str
    condition: str
    policy_mode: str | None
    status: ExperimentStatus
    recorded_at: datetime | None
    branch: str | None
    commit: str | None = Field(default=None, pattern=COMMIT_PATTERN)
    model_name: str | None
    model_digest: str | None = Field(default=None, pattern=SHA256_PATTERN)
    dataset: str
    dataset_version: str
    split: str
    benchmark_variant: str
    sample_size: int = Field(ge=0)
    selection_manifest: str | None
    run_id: str | None
    replay_status: str
    provider_call_count: int | None = Field(default=None, ge=0)
    api_cost_usd: float | None = Field(default=None, ge=0)
    metrics: tuple[MetricEvidence, ...]
    evidence_sources: tuple[str, ...] = Field(min_length=1)
    limitations: tuple[str, ...] = Field(default=(), max_length=30)
    comparability_groups: tuple[str, ...] = Field(default=(), max_length=20)
    chart_eligible: bool = True
    evidence_verification_status: EvidenceVerification

    @model_validator(mode="after")
    def unique_metrics_and_consistency(self) -> Self:
        keys = [
            (metric.metric_id, tuple(sorted(metric.dimensions.items()))) for metric in self.metrics
        ]
        if len(keys) != len(set(keys)):
            raise ValueError(f"experiment {self.experiment_id!r} has duplicate metrics")
        for metric in self.metrics:
            if metric.phase != self.phase or metric.condition != self.condition:
                raise ValueError("metric phase and condition must match its experiment")
            if metric.sample_size != self.sample_size:
                raise ValueError("metric sample size must match its experiment")
        metric_ids = {metric.metric_id for metric in self.metrics if not metric.dimensions}
        if "accuracy" in metric_ids and "coverage" not in metric_ids:
            raise ValueError("accuracy must be accompanied by coverage")
        if "answered_only_accuracy" in metric_ids and "coverage" not in metric_ids:
            raise ValueError("answered-only accuracy must be accompanied by coverage")
        return self


class ExperimentSummary(StrictModel):
    experiment_id: str
    name: str
    phase: str
    condition: str
    policy_mode: str | None
    status: ExperimentStatus
    recorded_at: datetime | None
    commit: str | None
    model_name: str | None
    dataset: str
    split: str
    sample_size: int
    replay_status: str
    provider_call_count: int | None
    api_cost_usd: float | None
    primary_metrics: dict[str, float | int | None]
    main_limitation: str | None
    comparability_groups: tuple[str, ...]
    chart_eligible: bool
    evidence_verification_status: EvidenceVerification


class ComparisonCompatibility(StrictModel):
    comparison_id: str = Field(pattern=ID_PATTERN)
    title: str
    comparison_type: ComparisonType
    experiment_ids: tuple[str, ...] = Field(min_length=2, max_length=8)
    paired: bool
    same_selection: bool
    supported_metrics: tuple[str, ...]
    outcome_counts: dict[str, int | None] = Field(default_factory=dict)
    warning: str
    evidence_sources: tuple[str, ...]
    limitations: tuple[str, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def paired_contract(self) -> Self:
        if self.comparison_type is ComparisonType.PAIRED and not (
            self.paired and self.same_selection
        ):
            raise ValueError("paired comparisons require paired=true and same_selection=true")
        if self.comparison_type is ComparisonType.INCOMPARABLE and self.paired:
            raise ValueError("incomparable experiments cannot be paired")
        return self


class ResearchCatalogue(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    catalogue_id: Literal["phase1-7-evidence"] = "phase1-7-evidence"
    catalogue_version: Literal["1.0.0"] = "1.0.0"
    source_checkpoint: str = Field(pattern=COMMIT_PATTERN)
    evidence_sources: tuple[SourceArtifact, ...] = Field(min_length=1)
    experiments: tuple[ExperimentDetail, ...] = Field(min_length=1)
    comparisons: tuple[ComparisonCompatibility, ...] = Field(min_length=1)
    global_limitations: tuple[str, ...] = Field(min_length=1, max_length=30)
    zero_cost: Literal[True] = True
    provider_calls_during_phase8: Literal[0] = 0

    @model_validator(mode="after")
    def catalogue_integrity(self) -> Self:
        sources = {item.artifact_id: item for item in self.evidence_sources}
        if len(sources) != len(self.evidence_sources):
            raise ValueError("duplicate evidence source identifier")
        experiments = {item.experiment_id: item for item in self.experiments}
        if len(experiments) != len(self.experiments):
            raise ValueError("duplicate experiment identifier")
        for experiment in self.experiments:
            if not set(experiment.evidence_sources).issubset(sources):
                raise ValueError(f"experiment {experiment.experiment_id!r} has an unknown source")
            for metric in experiment.metrics:
                source = sources.get(metric.source_artifact)
                if source is None or source.sha256 != metric.source_artifact_hash:
                    raise ValueError(f"metric {metric.metric_id!r} has mismatched provenance")
                if source.source_commit != metric.source_commit:
                    raise ValueError(f"metric {metric.metric_id!r} has a source commit mismatch")
        for comparison in self.comparisons:
            if not set(comparison.experiment_ids).issubset(experiments):
                raise ValueError(
                    f"comparison {comparison.comparison_id!r} references an unknown experiment"
                )
            if not set(comparison.evidence_sources).issubset(sources):
                raise ValueError(f"comparison {comparison.comparison_id!r} has an unknown source")
            if comparison.comparison_type is ComparisonType.PAIRED:
                selected = [experiments[item] for item in comparison.experiment_ids]
                manifests = {item.selection_manifest for item in selected}
                sizes = {item.sample_size for item in selected}
                if None in manifests or len(manifests) != 1 or len(sizes) != 1:
                    raise ValueError("paired comparison evidence does not share a selection")
        return self

    @property
    def canonical_hash(self) -> str:
        return sha256_json(self.model_dump(mode="json"))


class CatalogueOverview(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    catalogue_id: str
    catalogue_version: str
    catalogue_hash: str = Field(pattern=SHA256_PATTERN)
    evidence_validation_status: Literal["VERIFIED"] = "VERIFIED"
    experiment_count: int = Field(ge=0)
    comparison_count: int = Field(ge=0)
    experiments: tuple[ExperimentSummary, ...]
    global_limitations: tuple[str, ...]
    zero_cost: bool
    provider_calls_during_phase8: int


class ExperimentListResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    items: tuple[ExperimentSummary, ...]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class ResearchApiError(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]{0,127}$")
    message: str = Field(min_length=1, max_length=500)


class AggregateExportManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    catalogue_version: str
    export_format: Literal["json", "csv", "markdown"]
    applied_filters: dict[str, str]
    generated_at: datetime
    canonical_content_hash: str = Field(pattern=SHA256_PATTERN)
    missing_value: Literal["NA"] = "NA"
    filename: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,127}$")
    metric_count: int = Field(ge=0)


class TermView(StrictModel):
    kind: Literal["entity", "variable"]
    value: str


class LiteralView(StrictModel):
    canonical_id: str = Field(pattern=SHA256_PATTERN)
    predicate: str
    arguments: tuple[TermView, ...]
    negated: bool
    source_id: str
    display: str


class RuleView(StrictModel):
    rule_id: str
    variables: tuple[str, ...]
    premises: tuple[LiteralView, ...]
    conclusion: LiteralView
    source_id: str


class PredicateView(StrictModel):
    name: str
    arity: Literal[1, 2]
    argument_types: tuple[str, ...] | None


class SourceMappingView(StrictModel):
    source_id: str
    text: str
    referenced_by: tuple[str, ...]


class CorrectionDiff(StrictModel):
    available: bool
    additions: tuple[str, ...] = ()
    removals: tuple[str, ...] = ()
    changed_predicates: tuple[str, ...] = ()
    changed_arguments: tuple[str, ...] = ()
    changed_polarity: tuple[str, ...] = ()
    changed_source_references: tuple[str, ...] = ()
    reason: str | None = None


class AstInspectionRequest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    accepted_theory: Theory
    pre_correction_theory: Theory | None = None
    correction_attempted: bool = False
    proof_roots: tuple[str, ...] = Field(default=(), max_length=2)


class NormalizedAstInspection(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    theory_id: str
    canonical_theory_id: str = Field(pattern=SHA256_PATTERN)
    facts: tuple[LiteralView, ...]
    rules: tuple[RuleView, ...]
    query: LiteralView
    predicates: tuple[PredicateView, ...]
    entities: tuple[dict[str, str | None], ...]
    source_mapping: tuple[SourceMappingView, ...]
    semantic_validation_status: Literal["VALID"] = "VALID"
    source_coverage_status: Literal["COMPLETE", "INCOMPLETE"]
    correction_attempted: bool
    correction_diff: CorrectionDiff
    proof_roots: tuple[str, ...]
    canonical_json: dict[str, Any]


def sha256_json(value: object) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()
