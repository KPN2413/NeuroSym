from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from verilogic_ns_api.baselines.selection import load_manifest
from verilogic_ns_api.evaluation.metrics import compute_metrics
from verilogic_ns_api.phase9.freeze import file_sha256
from verilogic_ns_api.reasoning.engine import ForwardChainingEngine
from verilogic_ns_api.reasoning.models import ReasoningStatus
from verilogic_ns_api.reasoning.proofwriter import select_conformance_examples
from verilogic_ns_api.reasoning.verifier import ProofVerifier
from verilogic_ns_api.research.models import PredictionLabel, PredictionRecord, Split


def run_oracle(
    *, archive: Path, selection_manifest: Path, output_directory: Path, run_id: str
) -> dict[str, object]:
    if output_directory.exists():
        raise ValueError("oracle output directory already exists")
    manifest = load_manifest(selection_manifest)
    if manifest.split is not Split.DEVELOPMENT:
        raise ValueError("Phase 9 oracle accepts the development split only")
    selected = {item.example_id for item in manifest.entries}
    examples = select_conformance_examples(
        archive,
        variant=manifest.variant,
        split=Split.DEVELOPMENT,
        example_ids=selected,
    )
    by_id = {item.example_id: item for item in examples}
    engine = ForwardChainingEngine()
    verifier = ProofVerifier()
    predictions: list[PredictionRecord] = []
    proof_verified = 0
    started = perf_counter()
    mapping = {
        ReasoningStatus.ENTAILED: PredictionLabel.ENTAILED,
        ReasoningStatus.CONTRADICTED: PredictionLabel.CONTRADICTED,
        ReasoningStatus.UNKNOWN: PredictionLabel.UNKNOWN,
    }
    for entry in manifest.entries:
        example = by_id[entry.example_id]
        outcome = engine.reason(example.theory)
        verifier.verify_result(example.theory, outcome.result)
        proof_verified += 1
        predictions.append(
            PredictionRecord(
                run_id=run_id,
                example_id=example.example_id,
                predicted_label=mapping[outcome.result.status],
                latency_ms=outcome.telemetry.execution_duration_ms,
                cache_hit=False,
                configured_model=None,
                returned_model=None,
                estimated_cost_usd=0,
                predictor_name="oracle-structure-symbolic-ceiling",
                predictor_version="phase9-v1",
                timestamp=datetime.now(UTC),
            )
        )
    benchmark = _benchmark_examples(archive, manifest)
    metrics = compute_metrics(benchmark, predictions)
    output_directory.mkdir(parents=True)
    records_path = output_directory / "predictions.jsonl"
    _write_jsonl(records_path, predictions)
    report = {
        "schema_version": "1.0",
        "run_id": run_id,
        "status": "complete",
        "split": "dev",
        "test_split": False,
        "sample_size": len(predictions),
        "metrics": metrics.model_dump(mode="json"),
        "proof_attempted": len(predictions),
        "proof_verified": proof_verified,
        "provider_call_count": 0,
        "api_cost_usd": 0.0,
        "wall_seconds": perf_counter() - started,
        "raw_records_sha256": file_sha256(records_path),
    }
    _write_json(output_directory / "report.json", report)
    return report


def _benchmark_examples(archive: Path, manifest):
    from verilogic_ns_api.baselines.selection import load_selected_examples
    from verilogic_ns_api.datasets.proofwriter import ProofWriterLoader

    loader = ProofWriterLoader(archive, dataset_version="V2020.12.3")
    return load_selected_examples(loader, manifest)


def _write_jsonl(path: Path, predictions: list[PredictionRecord]) -> None:
    payload = "".join(
        json.dumps(item.model_dump(mode="json"), sort_keys=True) + "\n" for item in predictions
    )
    _atomic_text(path, payload)


def _write_json(path: Path, payload: object) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_text(path: Path, payload: str) -> None:
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
