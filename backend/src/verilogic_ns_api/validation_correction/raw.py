from __future__ import annotations

from dataclasses import dataclass

from verilogic_ns_api.baselines.configuration import resolve_repository_path
from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.semantic_parsing.cache import ParserResponseCache
from verilogic_ns_api.semantic_parsing.configuration import PreparedParserExperiment
from verilogic_ns_api.semantic_parsing.models import (
    CandidateQueryOutput,
    CandidateTheoryOutput,
    ParserKind,
    ParserOutcome,
    ParserStatus,
)
from verilogic_ns_api.semantic_parsing.prompts import render_query_input, render_theory_input
from verilogic_ns_api.semantic_parsing.provider import StructuredRequest
from verilogic_ns_api.semantic_parsing.views import (
    PreparedTheoryView,
    assert_same_theory,
    prepare_query_view,
    prepare_theory_view,
)
from verilogic_ns_api.terminal_outcomes import CachedOutcomeType


class Phase5CacheMissError(RuntimeError):
    pass


@dataclass(frozen=True)
class RawPhase5Candidates:
    theory_views: dict[str, PreparedTheoryView]
    theories: dict[str, object]
    queries: dict[str, object]
    theory_terminal_errors: dict[str, ParserOutcome]
    query_terminal_errors: dict[str, ParserOutcome]
    cache_hits: int


def load_raw_phase5_candidates(
    prepared: PreparedParserExperiment,
    *,
    calibration: bool,
) -> RawPhase5Candidates:
    examples = prepared.calibration_examples if calibration else prepared.pilot_examples
    cache = ParserResponseCache(
        resolve_repository_path(prepared.root, prepared.config.cache_directory)
    )
    theory_views: dict[str, PreparedTheoryView] = {}
    for example in examples:
        key = example.theory_id or example.example_id
        view = prepare_theory_view(example)
        if key in theory_views:
            assert_same_theory(theory_views[key], view)
        else:
            theory_views[key] = view

    theories: dict[str, object] = {}
    theory_terminal_errors: dict[str, ParserOutcome] = {}
    for key, view in sorted(theory_views.items()):
        request = StructuredRequest(
            kind="theory",
            instructions=prepared.theory_prompt,
            input_text=render_theory_input(view.public),
            prompt_hash=prepared.config.theory_prompt_sha256,
            input_hash=view.public.input_hash,
            output_schema=CandidateTheoryOutput.model_json_schema(),
            schema_hash=sha256_payload(CandidateTheoryOutput.model_json_schema()),
            config=prepared.config.runtime,
        )
        outcome = cache.load_outcome(request)
        if outcome is None:
            raise Phase5CacheMissError(f"missing frozen Phase 5 theory cache entry for {key}")
        if outcome.outcome_type is CachedOutcomeType.TERMINAL_ERROR:
            assert outcome.terminal_error is not None
            terminal = outcome.terminal_error
            theories[key] = None
            theory_terminal_errors[key] = ParserOutcome(
                parser_kind=ParserKind.THEORY,
                input_hash=view.public.input_hash,
                request_hash=terminal.request_hash,
                status=ParserStatus(terminal.pipeline_status.value),
                cache_hit=True,
                error_type=terminal.error_code.value,
                error_message=terminal.reason,
            )
        else:
            assert outcome.response is not None
            theories[key] = outcome.response.content

    queries: dict[str, object] = {}
    query_terminal_errors: dict[str, ParserOutcome] = {}
    for example in examples:
        view = prepare_query_view(example)
        request = StructuredRequest(
            kind="query",
            instructions=prepared.query_prompt,
            input_text=render_query_input(view.public),
            prompt_hash=prepared.config.query_prompt_sha256,
            input_hash=view.public.input_hash,
            output_schema=CandidateQueryOutput.model_json_schema(),
            schema_hash=sha256_payload(CandidateQueryOutput.model_json_schema()),
            config=prepared.config.runtime,
        )
        outcome = cache.load_outcome(request)
        if outcome is None:
            raise Phase5CacheMissError(
                f"missing frozen Phase 5 query cache entry for {example.example_id}"
            )
        if outcome.outcome_type is CachedOutcomeType.TERMINAL_ERROR:
            assert outcome.terminal_error is not None
            terminal = outcome.terminal_error
            queries[example.example_id] = None
            query_terminal_errors[example.example_id] = ParserOutcome(
                parser_kind=ParserKind.QUERY,
                input_hash=view.public.input_hash,
                request_hash=terminal.request_hash,
                status=ParserStatus(terminal.pipeline_status.value),
                cache_hit=True,
                error_type=terminal.error_code.value,
                error_message=terminal.reason,
            )
        else:
            assert outcome.response is not None
            queries[example.example_id] = outcome.response.content
    return RawPhase5Candidates(
        theory_views=theory_views,
        theories=theories,
        queries=queries,
        theory_terminal_errors=theory_terminal_errors,
        query_terminal_errors=query_terminal_errors,
        cache_hits=len(theories) + len(queries),
    )
