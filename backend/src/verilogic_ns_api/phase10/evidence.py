from __future__ import annotations

import hashlib
import json
from pathlib import Path

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase9.freeze import load_and_validate_freeze
from verilogic_ns_api.phase9.models import ComparisonKind, Phase9AggregateReport
from verilogic_ns_api.phase10.models import FinalEvidencePackage, with_fingerprint
from verilogic_ns_api.research_frontend.catalogue import ResearchCatalogueService
from verilogic_ns_api.research_frontend.models import ResearchCatalogue

FINAL_EVIDENCE_PATH = Path("research/evidence/phase10-final-evidence.v1.json")
PHASE9_AGGREGATE_PATH = Path("research/evidence/phase9-regenerated-aggregate.v1.json")
PHASE8_CATALOGUE_PATH = Path("research/catalogues/phase1-7-evidence.v1.json")
PHASE9_FREEZE_PATH = Path("experiments/manifests/phase9-recovery-freeze.v1.json")


class FinalEvidenceError(ValueError):
    pass


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise FinalEvidenceError(
            f"tracked evidence is unavailable or invalid: {path.name}"
        ) from error


def build_final_evidence(root: Path | None = None) -> FinalEvidencePackage:
    resolved = repository_root(root or Path.cwd())
    aggregate = Phase9AggregateReport.model_validate(_load_json(resolved / PHASE9_AGGREGATE_PATH))
    catalogue = ResearchCatalogueService(resolved).catalogue
    historical = ResearchCatalogue.model_validate(_load_json(resolved / PHASE8_CATALOGUE_PATH))
    freeze = load_and_validate_freeze(resolved / PHASE9_FREEZE_PATH)

    conditions: list[dict[str, object]] = []
    for condition in aggregate.conditions:
        metrics = condition.metrics
        conditions.append(
            {
                "condition": condition.condition,
                "correct": round(metrics.accuracy * metrics.total_examples),
                "total": metrics.total_examples,
                "answered": metrics.answered_examples,
                "abstained": metrics.abstained_examples,
                "errors": metrics.errored_examples,
                "coverage": metrics.coverage,
                "answered_only_accuracy": metrics.answered_only_accuracy,
                "proof_attempted": condition.proof_attempted,
                "proof_verified": condition.proof_verified,
                "exact_input_tokens": condition.input_tokens,
                "exact_output_tokens": condition.output_tokens,
                "observed_input_tokens": condition.observed_input_tokens,
                "observed_output_tokens": condition.observed_output_tokens,
                "representation": (
                    "formal_symbolic_ceiling"
                    if condition.condition == "oracle_structure_symbolic_ceiling"
                    else "natural_language"
                ),
            }
        )

    comparisons: list[dict[str, object]] = []
    for comparison in aggregate.comparisons:
        counts = comparison.outcome_counts
        comparisons.append(
            {
                "comparison_id": comparison.comparison_id,
                "baseline_condition": comparison.baseline_condition,
                "changed_condition": comparison.changed_condition,
                "both_correct": counts.both_correct,
                "baseline_only_correct": counts.baseline_only_correct,
                "changed_only_correct": counts.changed_only_correct,
                "both_incorrect": counts.both_incorrect,
                "interpretation": (
                    "different_representation_ceiling"
                    if comparison.comparison_kind
                    is ComparisonKind.SAME_SELECTION_DIFFERENT_REPRESENTATION
                    else "paired_descriptive"
                ),
            }
        )

    payload: dict[str, object] = {
        "schema_version": "1.0",
        "phase9_aggregate_fingerprint": aggregate.report_fingerprint,
        "phase9_catalogue_hash": catalogue.canonical_hash,
        "phase8_catalogue_hash": historical.canonical_hash,
        "dataset": freeze.dataset,
        "dataset_version": freeze.dataset_version,
        "world_assumption": freeze.world_assumption,
        "variant": freeze.variant,
        "split": "development",
        "archive_sha256": aggregate.archive_sha256,
        "freeze_hash": aggregate.freeze_hash,
        "selection_seed": freeze.seed,
        "evaluation_records": freeze.sample_size,
        "few_shot_demonstrations": 6,
        "train_development_overlap": 0,
        "model": freeze.model,
        "model_digest": freeze.model_digest,
        "conditions": conditions,
        "comparisons": comparisons,
        "local_model_dispatches": aggregate.local_provider_dispatches,
        "hosted_provider_calls": aggregate.hosted_provider_calls,
        "external_transfers": aggregate.external_transfers,
        "api_cost_usd": aggregate.api_cost_usd,
        "test_split_access_count": aggregate.test_split_access_count,
        "replay_verified_with_ollama_stopped": aggregate.replay_verified,
        "catalogue_experiments": len(catalogue.experiments),
        "catalogue_comparisons": len(catalogue.comparisons),
        "terminal_correction_cache_failures": 3,
        "limitations": [
            "The Phase 9 experiment contains 30 development examples only.",
            "No test-set experiment was performed and no superiority claim is supported.",
            "The local 4B semantic parser is the main end-to-end bottleneck.",
            "The symbolic oracle is a same-selection, different-representation formal ceiling.",
            "P1/P2 exact token totals are unavailable; only observed lower bounds are retained.",
            "Three typed terminal correction/cache failures occurred.",
            "The ProofWriter dataset licence remains unverified.",
        ],
    }
    return with_fingerprint(payload)


def write_final_evidence(root: Path | None = None, *, check: bool = False) -> Path:
    resolved = repository_root(root or Path.cwd())
    target = resolved / FINAL_EVIDENCE_PATH
    content = (
        json.dumps(
            build_final_evidence(resolved).model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )
    if check:
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise FinalEvidenceError("tracked Phase 10 final evidence is stale")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")
    return target


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
