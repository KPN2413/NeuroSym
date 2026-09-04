from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.research_frontend.models import (
    CatalogueOverview,
    ExperimentDetail,
    ExperimentSummary,
    ResearchCatalogue,
    ResearchDashboardSnapshot,
)

CATALOGUE_PATH = Path("research/catalogues/phase1-9-evidence.v2.json")


class CatalogueIntegrityError(ValueError):
    pass


class ResearchCatalogueService:
    def __init__(self, root: Path | None = None) -> None:
        self.root = repository_root(root or Path.cwd())
        self.path = self.root / CATALOGUE_PATH
        self.catalogue = self._load()
        self.validate_sources()
        summaries = tuple(self._build_summary(item) for item in self.catalogue.experiments)
        self._summary_by_id: Mapping[str, ExperimentSummary] = MappingProxyType(
            {item.experiment_id: item for item in summaries}
        )
        self._experiment_by_id: Mapping[str, ExperimentDetail] = MappingProxyType(
            {item.experiment_id: item for item in self.catalogue.experiments}
        )
        self._overview = self._build_overview(summaries)
        self._dashboard = ResearchDashboardSnapshot(
            overview=self._overview,
            comparisons=self.catalogue.comparisons,
            experiments=self.catalogue.experiments,
        )
        self._canonical_bytes: bytes | None = None

    def _load(self) -> ResearchCatalogue:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return ResearchCatalogue.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as error:
            raise CatalogueIntegrityError("the research evidence catalogue is invalid") from error

    def validate_sources(self) -> None:
        for source in self.catalogue.evidence_sources:
            if not source.tracked:
                continue
            target = (self.root / source.path).resolve()
            if not target.is_relative_to(self.root) or not target.is_file():
                raise CatalogueIntegrityError(
                    f"tracked source {source.artifact_id!r} is unavailable"
                )
            observed = hashlib.sha256(target.read_bytes()).hexdigest()
            if observed != source.sha256:
                raise CatalogueIntegrityError(
                    f"tracked source {source.artifact_id!r} hash mismatch"
                )

    def _build_summary(self, experiment: ExperimentDetail) -> ExperimentSummary:
        primary: dict[str, float | int | None] = {}
        for metric in experiment.metrics:
            if not metric.dimensions and metric.metric_id in {
                "accuracy",
                "coverage",
                "answered_only_accuracy",
                "macro_f1",
            }:
                primary[metric.metric_id] = metric.value
        return ExperimentSummary(
            experiment_id=experiment.experiment_id,
            name=experiment.name,
            phase=experiment.phase,
            condition=experiment.condition,
            policy_mode=experiment.policy_mode,
            status=experiment.status,
            recorded_at=experiment.recorded_at,
            commit=experiment.commit,
            model_name=experiment.model_name,
            dataset=experiment.dataset,
            split=experiment.split,
            sample_size=experiment.sample_size,
            replay_status=experiment.replay_status,
            provider_call_count=experiment.provider_call_count,
            api_cost_usd=experiment.api_cost_usd,
            primary_metrics=primary,
            main_limitation=experiment.limitations[0] if experiment.limitations else None,
            comparability_groups=experiment.comparability_groups,
            chart_eligible=experiment.chart_eligible,
            evidence_verification_status=experiment.evidence_verification_status,
        )

    def summary(self, experiment: ExperimentDetail) -> ExperimentSummary:
        return self._summary_by_id[experiment.experiment_id]

    def _build_overview(self, summaries: tuple[ExperimentSummary, ...]) -> CatalogueOverview:
        return CatalogueOverview(
            catalogue_id=self.catalogue.catalogue_id,
            catalogue_version=self.catalogue.catalogue_version,
            catalogue_hash=self.catalogue.canonical_hash,
            experiment_count=len(self.catalogue.experiments),
            comparison_count=len(self.catalogue.comparisons),
            experiments=summaries,
            global_limitations=self.catalogue.global_limitations,
            zero_cost=self.catalogue.zero_cost,
            provider_calls_during_phase8=self.catalogue.provider_calls_during_phase8,
            local_provider_calls_during_phase9=self.catalogue.local_provider_calls_during_phase9,
            hosted_provider_calls_during_phase9=(
                self.catalogue.hosted_provider_calls_during_phase9
            ),
            api_cost_usd_during_phase9=self.catalogue.api_cost_usd_during_phase9,
        )

    def overview(self) -> CatalogueOverview:
        return self._overview

    def dashboard(self) -> ResearchDashboardSnapshot:
        return self._dashboard

    def experiment(self, experiment_id: str) -> ExperimentDetail | None:
        return self._experiment_by_id.get(experiment_id)

    def canonical_bytes(self) -> bytes:
        if self._canonical_bytes is None:
            self._canonical_bytes = (
                json.dumps(
                    self.catalogue.model_dump(mode="json"),
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=False,
                )
                + "\n"
            ).encode("utf-8")
        return self._canonical_bytes


def write_seed_catalogue(root: Path | None = None, *, check: bool = False) -> Path:
    from verilogic_ns_api.research_frontend.phase9_catalogue import build_phase9_catalogue

    resolved = repository_root(root or Path.cwd())
    path = resolved / CATALOGUE_PATH
    content = (
        json.dumps(
            build_phase9_catalogue(resolved).model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    if check:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise CatalogueIntegrityError("tracked research catalogue is stale")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return path
