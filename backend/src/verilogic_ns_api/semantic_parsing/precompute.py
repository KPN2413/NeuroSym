from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from time import perf_counter

from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.research.models import BenchmarkExample
from verilogic_ns_api.semantic_parsing.models import ParserOutcome
from verilogic_ns_api.semantic_parsing.service import SemanticParser
from verilogic_ns_api.semantic_parsing.views import (
    PreparedTheoryView,
    assert_same_theory,
    prepare_query_view,
    prepare_theory_view,
)


class ParserPrecomputeError(RuntimeError):
    pass


def precompute_parser_cache(
    *,
    examples: tuple[BenchmarkExample, ...],
    parser: SemanticParser,
    output_directory: Path,
    run_id: str,
) -> dict[str, object]:
    """Populate or replay the parser cache without reading evaluation gold fields."""
    if output_directory.exists():
        raise ParserPrecomputeError(f"run directory already exists: {output_directory}")
    output_directory.mkdir(parents=True)
    _atomic_json(output_directory / "run-state.json", {"status": "incomplete", "run_id": run_id})

    theory_views: dict[str, PreparedTheoryView] = {}
    for example in examples:
        key = example.theory_id or example.example_id
        view = prepare_theory_view(example)
        if key in theory_views:
            assert_same_theory(theory_views[key], view)
        else:
            theory_views[key] = view

    started = perf_counter()
    operations: list[dict[str, object]] = []
    for key, view in sorted(theory_views.items()):
        execution = parser.parse_theory(view.public)
        operations.append(_operation("theory", key, execution.outcome))
    for example in examples:
        execution = parser.parse_query(prepare_query_view(example).public)
        operations.append(_operation("query", example.example_id, execution.outcome))

    request_hashes = [str(item["request_hash"]) for item in operations]
    if len(operations) != 58:
        raise ParserPrecomputeError("Phase 6-R2 parser plan must contain 58 logical requests")
    available = sum(_cache_entry_exists(parser, request_hash) for request_hash in request_hashes)
    if available != 58:
        _atomic_json(
            output_directory / "cache-ledger.json",
            {"schema_version": "1.0", "run_id": run_id, "operations": operations},
        )
        raise ParserPrecomputeError(
            f"Phase 6-R2 parser cache is incomplete: {available}/58 entries available"
        )

    unique = {str(item["request_hash"]): item for item in operations}
    report = {
        "schema_version": "1.0",
        "status": "complete",
        "run_id": run_id,
        "logical_components": len(operations),
        "theory_components": len(theory_views),
        "query_components": len(examples),
        "unique_request_hashes": len(unique),
        "duplicate_cache_reuses": len(operations) - len(unique),
        "cache_entries_available": available,
        "cache_hits": sum(bool(item["cache_hit"]) for item in operations),
        "new_local_calls": sum(not bool(item["cache_hit"]) for item in operations),
        "structured_output_successes": sum(item["status"] == "PARSED" for item in operations),
        "terminal_outcomes": sum(
            item["error_type"]
            in {
                "OUTPUT_LIMIT_EXHAUSTED",
                "INVALID_STRUCTURED_OUTPUT",
                "TIMEOUT_EXHAUSTED",
                "TRANSIENT_RETRY_EXHAUSTED",
                "PROVIDER_FAILURE",
            }
            for item in operations
        ),
        "failures": sum(item["status"] != "PARSED" for item in operations),
        "input_tokens": sum(int(item["input_tokens"]) for item in operations),
        "output_tokens": sum(int(item["output_tokens"]) for item in operations),
        "provider_inference_ms": sum(float(item["duration_ms"]) for item in operations),
        "wall_seconds": perf_counter() - started,
        "request_manifest_hash": sha256_payload(request_hashes),
        "operation_fingerprint": sha256_payload(
            [
                {
                    "component": item["component"],
                    "request_hash": item["request_hash"],
                    "status": item["status"],
                    "error_type": item["error_type"],
                }
                for item in operations
            ]
        ),
        "gold_fields_accessed": False,
        "hosted_provider_calls": 0,
        "external_transmissions": 0,
        "api_cost_usd": 0.0,
    }
    _atomic_json(
        output_directory / "cache-ledger.json",
        {"schema_version": "1.0", "run_id": run_id, "operations": operations},
    )
    _atomic_json(output_directory / "cache-seal.json", report)
    _atomic_json(output_directory / "run-state.json", {"status": "complete", "run_id": run_id})
    return report


def _operation(kind: str, key: str, outcome: ParserOutcome) -> dict[str, object]:
    return {
        "kind": kind,
        "component": sha256_payload({"kind": kind, "key": key}),
        "input_hash": outcome.input_hash,
        "request_hash": outcome.request_hash,
        "status": outcome.status,
        "cache_hit": outcome.cache_hit,
        "error_type": outcome.error_type,
        "input_tokens": outcome.usage.input_tokens if outcome.usage else 0,
        "output_tokens": outcome.usage.output_tokens if outcome.usage else 0,
        "duration_ms": outcome.timing.total_duration_ms if outcome.timing else 0,
    }


def _cache_entry_exists(parser: SemanticParser, request_hash: str) -> bool:
    return (parser.cache.root / request_hash[:2] / f"{request_hash}.json").is_file()


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
