from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from verilogic_ns_api.research_frontend.catalogue import ResearchCatalogueService
from verilogic_ns_api.research_frontend.models import (
    AggregateExportManifest,
    ExperimentDetail,
    sha256_json,
)

ExportFormat = Literal["json", "csv", "markdown"]
MAX_EXPORT_METRICS = 5_000


@dataclass(frozen=True)
class RenderedExport:
    content: bytes
    media_type: str
    manifest: AggregateExportManifest


def select_experiments(
    service: ResearchCatalogueService, filters: dict[str, str]
) -> tuple[ExperimentDetail, ...]:
    items = service.catalogue.experiments
    mapping = {
        "phase": "phase",
        "condition": "condition",
        "policy_mode": "policy_mode",
        "model": "model_name",
        "dataset": "dataset",
        "split": "split",
        "status": "status",
        "comparability_group": "comparability_groups",
    }
    for key, value in filters.items():
        field = mapping.get(key)
        if field is None:
            continue
        if field == "comparability_groups":
            items = tuple(item for item in items if value in item.comparability_groups)
        else:
            items = tuple(item for item in items if str(getattr(item, field) or "") == value)
    return tuple(items)


def render_export(
    service: ResearchCatalogueService,
    export_format: ExportFormat,
    filters: dict[str, str] | None = None,
    *,
    generated_at: datetime | None = None,
) -> RenderedExport:
    applied = dict(sorted((filters or {}).items()))
    experiments = select_experiments(service, applied)
    metric_count = sum(len(item.metrics) for item in experiments)
    if metric_count > MAX_EXPORT_METRICS:
        raise ValueError("filtered export exceeds the metric limit")
    selected_ids = {item.experiment_id for item in experiments}
    comparisons = tuple(
        item
        for item in service.catalogue.comparisons
        if set(item.experiment_ids).issubset(selected_ids)
    )
    canonical = {
        "schema_version": "1.0",
        "catalogue_version": service.catalogue.catalogue_version,
        "applied_filters": applied,
        "experiments": [item.model_dump(mode="json") for item in experiments],
        "comparisons": [item.model_dump(mode="json") for item in comparisons],
        "global_limitations": list(service.catalogue.global_limitations),
        "missing_value": "NA",
    }
    content_hash = sha256_json(canonical)
    extension = {"json": "json", "csv": "csv", "markdown": "md"}[export_format]
    major = service.catalogue.catalogue_version.split(".", maxsplit=1)[0]
    filename = f"verilogic-ns-{service.catalogue.catalogue_id}.v{major}.{extension}"
    manifest = AggregateExportManifest(
        catalogue_version=service.catalogue.catalogue_version,
        export_format=export_format,
        applied_filters=applied,
        generated_at=generated_at or _catalogue_timestamp(service),
        canonical_content_hash=content_hash,
        filename=filename,
        metric_count=metric_count,
    )
    if export_format == "json":
        document = {"manifest": manifest.model_dump(mode="json"), "evidence": canonical}
        content = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
        media_type = "application/json"
    elif export_format == "csv":
        content = _csv(experiments, manifest).encode()
        media_type = "text/csv; charset=utf-8"
    else:
        content = _markdown(experiments, comparisons, manifest).encode()
        media_type = "text/markdown; charset=utf-8"
    return RenderedExport(content=content, media_type=media_type, manifest=manifest)


def _csv(experiments: tuple[ExperimentDetail, ...], manifest: AggregateExportManifest) -> str:
    output = io.StringIO(newline="")
    fields = [
        "catalogue_version",
        "canonical_content_hash",
        "experiment_id",
        "phase",
        "condition",
        "status",
        "split",
        "sample_size",
        "metric_id",
        "dimension",
        "value",
        "unit",
        "numerator",
        "denominator",
        "evidence_type",
        "source_artifact",
        "source_artifact_hash",
        "limitations",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for experiment in experiments:
        for metric in experiment.metrics:
            writer.writerow(
                {
                    "catalogue_version": manifest.catalogue_version,
                    "canonical_content_hash": manifest.canonical_content_hash,
                    "experiment_id": experiment.experiment_id,
                    "phase": experiment.phase,
                    "condition": experiment.condition,
                    "status": experiment.status,
                    "split": experiment.split,
                    "sample_size": experiment.sample_size,
                    "metric_id": metric.metric_id,
                    "dimension": ";".join(
                        f"{key}={value}" for key, value in sorted(metric.dimensions.items())
                    ),
                    "value": "NA" if metric.value is None else metric.value,
                    "unit": metric.unit,
                    "numerator": "NA" if metric.numerator is None else metric.numerator,
                    "denominator": "NA" if metric.denominator is None else metric.denominator,
                    "evidence_type": metric.evidence_type,
                    "source_artifact": metric.source_artifact,
                    "source_artifact_hash": metric.source_artifact_hash,
                    "limitations": " | ".join(metric.limitations),
                }
            )
    return output.getvalue()


def _markdown(
    experiments: tuple[ExperimentDetail, ...],
    comparisons: tuple[object, ...],
    manifest: AggregateExportManifest,
) -> str:
    lines = [
        "# VeriLogic-NS aggregate research evidence",
        "",
        f"Catalogue version: `{manifest.catalogue_version}`  ",
        f"Canonical evidence hash: `{manifest.canonical_content_hash}`  ",
        f"Applied filters: `{json.dumps(manifest.applied_filters, sort_keys=True)}`",
        "",
        "| Experiment | Phase | Condition | Status | Split | n | Accuracy | Coverage | Macro F1 |",
        "|---|---|---|---|---|---:|---:|---:|---:|",
    ]
    for experiment in experiments:
        metrics = {item.metric_id: item.value for item in experiment.metrics if not item.dimensions}
        lines.append(
            "| "
            + " | ".join(
                [
                    experiment.name,
                    experiment.phase,
                    experiment.condition,
                    experiment.status,
                    experiment.split,
                    str(experiment.sample_size),
                    _md_value(metrics.get("accuracy")),
                    _md_value(metrics.get("coverage")),
                    _md_value(metrics.get("macro_f1")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Comparison warnings", ""])
    if comparisons:
        for comparison in comparisons:
            lines.append(
                f"- **{comparison.title} ({comparison.comparison_type})** — {comparison.warning}"
            )
    else:
        lines.append("- No supported comparison remains after filtering.")
    lines.extend(
        [
            "",
            "Unavailable values are shown as `NA`, not zero. Accuracy must be interpreted with coverage.",
            "",
        ]
    )
    return "\n".join(lines)


def _md_value(value: float | int | None) -> str:
    if value is None:
        return "NA"
    return f"{value:.4f}" if isinstance(value, float) else str(value)


def _catalogue_timestamp(service: ResearchCatalogueService) -> datetime:
    timestamps = tuple(
        item.recorded_at for item in service.catalogue.experiments if item.recorded_at is not None
    )
    return max(timestamps, default=datetime(1970, 1, 1, tzinfo=UTC))
