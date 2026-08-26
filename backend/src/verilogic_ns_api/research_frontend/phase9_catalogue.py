from __future__ import annotations

import hashlib
from pathlib import Path

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase9.models import ComparisonKind, Phase9AggregateReport
from verilogic_ns_api.research_frontend.models import (
    ComparisonCompatibility,
    ComparisonType,
    EvidenceType,
    EvidenceVerification,
    ExperimentDetail,
    ExperimentStatus,
    MetricEvidence,
    ResearchCatalogue,
    SourceArtifact,
)
from verilogic_ns_api.research_frontend.seed import build_catalogue as build_historical_catalogue

AGGREGATE_PATH = Path("research/evidence/phase9-regenerated-aggregate.v1.json")
FREEZE_PATH = Path("experiments/manifests/phase9-recovery-freeze.v1.json")
SELECTION_PATH = Path("experiments/manifests/phase9-regenerated-dev.v1.json")
PREREGISTRATION_COMMIT = "8cd4ea486fe6accaa75773c3ba2749d62328a9b0"
PHASE9_LABEL = "Phase 9 regenerated evidence under newly frozen protocol"
COMMON_GROUP = "phase9-regenerated-selection"
EXPERIMENT_IDS = {
    "direct": "phase9-regenerated-direct",
    "few_shot": "phase9-regenerated-few-shot",
    "p0_raw_neuro_symbolic": "phase9-regenerated-p0-raw-neuro-symbolic",
    "validation_only": "phase9-regenerated-validation-only",
    "p1_corrected_valid": "phase9-regenerated-p1-corrected-valid",
    "p2_corrected_selective": "phase9-regenerated-p2-corrected-selective",
    "oracle_structure_symbolic_ceiling": "phase9-regenerated-oracle-structure-ceiling",
}


def build_phase9_catalogue(root: Path | None = None) -> ResearchCatalogue:
    resolved = repository_root(root or Path.cwd())
    historical = build_historical_catalogue()
    aggregate_path = resolved / AGGREGATE_PATH
    aggregate = Phase9AggregateReport.model_validate_json(
        aggregate_path.read_text(encoding="utf-8")
    )
    sources = _sources(resolved, aggregate)
    source_by_id = {item.artifact_id: item for item in sources}
    experiments = tuple(
        _experiment(condition, aggregate, source_by_id["phase9-regenerated-aggregate"])
        for condition in aggregate.conditions
    )
    comparisons = tuple(_comparison(item) for item in aggregate.comparisons)
    return ResearchCatalogue(
        catalogue_id="phase1-9-evidence",
        catalogue_version="2.0.0",
        source_checkpoint=aggregate.execution_commit,
        evidence_sources=historical.evidence_sources + sources,
        experiments=historical.experiments + experiments,
        comparisons=historical.comparisons + comparisons,
        global_limitations=(
            *historical.global_limitations,
            f"{PHASE9_LABEL}; it does not replace historical Phase 3-8 evidence.",
            "Phase 9 is a 30-record development-only regeneration and supports no significance, generalisation or state-of-the-art claim.",
            "Two Phase 9 correction cache outcomes lack complete usage telemetry; exact P1/P2 token totals remain unavailable and partial observed counts are labelled accordingly.",
        ),
        local_provider_calls_during_phase9=aggregate.local_provider_dispatches,
        hosted_provider_calls_during_phase9=aggregate.hosted_provider_calls,
        api_cost_usd_during_phase9=aggregate.api_cost_usd,
    )


def _sources(root: Path, aggregate: Phase9AggregateReport) -> tuple[SourceArtifact, ...]:
    return (
        SourceArtifact(
            artifact_id="phase9-regenerated-aggregate",
            path=AGGREGATE_PATH.as_posix(),
            sha256=_sha256(root / AGGREGATE_PATH),
            source_commit=aggregate.execution_commit,
            tracked=True,
            description=(
                "Sanitized aggregate reproduced from ignored raw Phase 9 prediction records."
            ),
        ),
        SourceArtifact(
            artifact_id="phase9-recovery-freeze",
            path=FREEZE_PATH.as_posix(),
            sha256=_sha256(root / FREEZE_PATH),
            source_commit=PREREGISTRATION_COMMIT,
            tracked=True,
            description="Frozen Phase 9 recovery protocol, model identity and artifact hashes.",
        ),
        SourceArtifact(
            artifact_id="phase9-regenerated-selection",
            path=SELECTION_PATH.as_posix(),
            sha256=_sha256(root / SELECTION_PATH),
            source_commit=PREREGISTRATION_COMMIT,
            tracked=True,
            description="Frozen balanced 30-record development selection without benchmark text.",
        ),
    )


def _experiment(condition, aggregate, source: SourceArtifact) -> ExperimentDetail:
    labels = {
        "direct": "Direct local LLM",
        "few_shot": "Fixed six-shot local LLM",
        "p0_raw_neuro_symbolic": "P0 raw neuro-symbolic",
        "validation_only": "Validation-only neuro-symbolic",
        "p1_corrected_valid": "P1 corrected-valid neuro-symbolic",
        "p2_corrected_selective": "P2 corrected-selective neuro-symbolic",
        "oracle_structure_symbolic_ceiling": "Same-selection symbolic oracle ceiling",
    }
    subgroup = (
        "phase9-regenerated-baselines"
        if condition.condition in {"direct", "few_shot"}
        else "phase9-regenerated-oracle"
        if condition.condition == "oracle_structure_symbolic_ceiling"
        else "phase9-regenerated-neurosymbolic"
    )
    limitations = (*condition.limitations, PHASE9_LABEL)
    if not condition.telemetry_complete:
        limitations += (
            "Exact total token usage is unavailable because two terminal correction cache outcomes lack usage telemetry; observed counts are partial.",
        )
    experiment = {
        "experiment_id": condition.experiment_id,
        "name": f"Phase 9 regenerated — {labels[condition.condition]}",
        "phase": "Phase 9",
        "condition": condition.condition,
        "policy_mode": condition.policy_mode,
        "status": (
            ExperimentStatus.PASS
            if condition.condition in {"direct", "few_shot", "oracle_structure_symbolic_ceiling"}
            else ExperimentStatus.COMPLETE_WITH_NEGATIVE_RESULT
        ),
        "recorded_at": None,
        "branch": "phase/09-full-experiments-ablations",
        "commit": aggregate.execution_commit,
        "model_name": condition.model,
        "model_digest": condition.model_digest,
        "dataset": condition.dataset,
        "dataset_version": condition.dataset_version,
        "split": "development",
        "benchmark_variant": "OWA depth-5 balanced regenerated development pilot",
        "sample_size": condition.sample_size,
        "selection_manifest": SELECTION_PATH.as_posix(),
        "run_id": None,
        "replay_status": "ZERO_CALL_REPLAY_VERIFIED",
        "provider_call_count": condition.provider_call_count,
        "api_cost_usd": condition.api_cost_usd,
        "evidence_sources": (
            "phase9-regenerated-aggregate",
            "phase9-recovery-freeze",
            "phase9-regenerated-selection",
        ),
        "limitations": limitations,
        "comparability_groups": (COMMON_GROUP, subgroup),
        "chart_eligible": True,
        "evidence_verification_status": EvidenceVerification.HASH_VERIFIED,
    }
    experiment["metrics"] = _metrics(experiment, condition, source)
    return ExperimentDetail.model_validate(experiment)


def _metrics(experiment: dict[str, object], condition, source) -> tuple[MetricEvidence, ...]:
    metrics = condition.metrics
    correct = sum(
        metrics.confusion_matrix.get(label, {}).get(label, 0)
        for label in ("ENTAILED", "CONTRADICTED", "UNKNOWN")
    )
    values = [
        _metric(
            experiment,
            source,
            "accuracy",
            "Accuracy",
            metrics.accuracy,
            "ratio",
            numerator=correct,
            denominator=metrics.total_examples,
        ),
        _metric(
            experiment,
            source,
            "coverage",
            "Coverage",
            metrics.coverage,
            "ratio",
            numerator=metrics.answered_examples,
            denominator=metrics.total_examples,
        ),
        _metric(
            experiment,
            source,
            "answered_only_accuracy",
            "Answered-only accuracy",
            metrics.answered_only_accuracy,
            "ratio",
            numerator=correct,
            denominator=metrics.answered_examples,
        ),
        _metric(experiment, source, "macro_f1", "Macro F1", metrics.macro_f1, "ratio"),
        _metric(
            experiment,
            source,
            "answered",
            "Answered records",
            metrics.answered_examples,
            "count",
            numerator=metrics.answered_examples,
            denominator=metrics.total_examples,
        ),
        _metric(
            experiment,
            source,
            "abstained",
            "Abstained records",
            metrics.abstained_examples,
            "count",
            numerator=metrics.abstained_examples,
            denominator=metrics.total_examples,
        ),
        _metric(
            experiment,
            source,
            "errors",
            "Error records",
            metrics.errored_examples,
            "count",
            numerator=metrics.errored_examples,
            denominator=metrics.total_examples,
        ),
        _metric(
            experiment,
            source,
            "provider_calls",
            "Local provider calls required by condition",
            condition.provider_call_count,
            "count",
        ),
        _metric(
            experiment,
            source,
            "api_cost_usd",
            "API cost",
            condition.api_cost_usd,
            "usd",
        ),
    ]
    if condition.runtime_seconds is not None:
        values.append(
            _metric(
                experiment,
                source,
                "runtime_seconds",
                "Observed live runtime",
                condition.runtime_seconds,
                "seconds",
            )
        )
    for metric_id, display, exact, observed in (
        ("input_tokens", "Input tokens", condition.input_tokens, condition.observed_input_tokens),
        (
            "output_tokens",
            "Output tokens",
            condition.output_tokens,
            condition.observed_output_tokens,
        ),
    ):
        if condition.telemetry_complete:
            values.append(_metric(experiment, source, metric_id, display, exact, "tokens"))
        else:
            values.append(
                _metric(
                    experiment,
                    source,
                    metric_id,
                    display,
                    None,
                    "tokens",
                    evidence_type=EvidenceType.UNAVAILABLE,
                    limitations=("Exact total is unavailable; see the partial observed metric.",),
                )
            )
            values.append(
                _metric(
                    experiment,
                    source,
                    f"observed_{metric_id}",
                    f"Partial observed {display.lower()}",
                    observed,
                    "tokens",
                    limitations=("Partial lower bound; two terminal outcomes lack telemetry.",),
                )
            )
    if condition.proof_attempted is not None:
        values.append(
            _metric(
                experiment,
                source,
                "proof_verification_rate",
                "Proof verification rate",
                condition.proof_verified / condition.proof_attempted,
                "ratio",
                numerator=condition.proof_verified,
                denominator=condition.proof_attempted,
            )
        )
    for depth, item in sorted(metrics.per_depth_metrics.items(), key=lambda pair: int(pair[0])):
        values.extend(
            (
                _metric(
                    experiment,
                    source,
                    "accuracy",
                    f"Accuracy at depth {depth}",
                    item.accuracy,
                    "ratio",
                    numerator=item.correct,
                    denominator=item.total,
                    dimensions={"depth": depth},
                ),
                _metric(
                    experiment,
                    source,
                    "coverage",
                    f"Coverage at depth {depth}",
                    item.coverage,
                    "ratio",
                    numerator=item.answered,
                    denominator=item.total,
                    dimensions={"depth": depth},
                ),
            )
        )
    for label, item in sorted(metrics.per_label_metrics.items()):
        values.append(
            _metric(
                experiment,
                source,
                "accuracy",
                f"Accuracy for {label}",
                item.recall,
                "ratio",
                numerator=round(item.recall * item.support),
                denominator=item.support,
                dimensions={"label": label},
            )
        )
    return tuple(values)


def _metric(
    experiment,
    source,
    metric_id,
    display_name,
    value,
    unit,
    *,
    numerator=None,
    denominator=None,
    evidence_type=EvidenceType.DIRECTLY_OBSERVED,
    limitations=(),
    dimensions=None,
) -> MetricEvidence:
    return MetricEvidence(
        metric_id=metric_id,
        display_name=display_name,
        value=value,
        unit=unit,
        numerator=numerator,
        denominator=denominator,
        dataset=experiment["dataset"],
        dataset_version=experiment["dataset_version"],
        split=experiment["split"],
        benchmark_variant=experiment["benchmark_variant"],
        sample_size=experiment["sample_size"],
        selection_manifest=experiment["selection_manifest"],
        phase=experiment["phase"],
        condition=experiment["condition"],
        policy_mode=experiment["policy_mode"],
        model_name=experiment["model_name"],
        model_digest=experiment["model_digest"],
        run_id=experiment["run_id"],
        source_artifact=source.artifact_id,
        source_artifact_hash=source.sha256,
        source_commit=source.source_commit,
        evidence_type=evidence_type,
        derivation_formula=None,
        comparability_group=COMMON_GROUP,
        limitations=limitations,
        verification_status=(
            EvidenceVerification.UNAVAILABLE
            if evidence_type is EvidenceType.UNAVAILABLE
            else EvidenceVerification.HASH_VERIFIED
        ),
        dimensions=dimensions or {},
    )


def _comparison(item) -> ComparisonCompatibility:
    return ComparisonCompatibility(
        comparison_id=item.comparison_id,
        title=f"Phase 9 regenerated: {item.baseline_condition} versus {item.changed_condition}",
        comparison_type=(
            ComparisonType.PAIRED
            if item.comparison_kind is ComparisonKind.PAIRED_COMPONENT_ABLATION
            else ComparisonType.SAME_SELECTION_DIFFERENT_REPRESENTATION
        ),
        experiment_ids=(
            EXPERIMENT_IDS[item.baseline_condition],
            EXPERIMENT_IDS[item.changed_condition],
        ),
        paired=item.paired,
        same_selection=item.same_selection,
        supported_metrics=("accuracy", "coverage", "macro_f1", "answered", "abstained", "errors"),
        outcome_counts=item.outcome_counts.model_dump(),
        warning=item.warning,
        evidence_sources=(
            "phase9-regenerated-aggregate",
            "phase9-recovery-freeze",
            "phase9-regenerated-selection",
        ),
        limitations=(PHASE9_LABEL, "Thirty records; no significance claim."),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
