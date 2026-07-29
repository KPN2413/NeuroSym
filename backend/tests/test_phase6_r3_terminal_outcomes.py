from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from verilogic_ns_api.evaluation.metrics import compute_metrics
from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.research.models import (
    BenchmarkExample,
    ExampleProvenance,
    GoldLabel,
    PredictionLabel,
    PredictionRecord,
    SourceStatement,
    Split,
    WorldAssumption,
)
from verilogic_ns_api.semantic_parsing.cache import (
    ParserCacheContractMismatch,
    ParserCacheCorrupt,
    ParserCacheIncomplete,
    ParserResponseCache,
)
from verilogic_ns_api.semantic_parsing.models import (
    CandidateTheoryOutput,
    ParserRuntimeConfig,
    ParserStatus,
)
from verilogic_ns_api.semantic_parsing.prompts import render_theory_input
from verilogic_ns_api.semantic_parsing.provider import StructuredRequest
from verilogic_ns_api.semantic_parsing.service import SemanticParser
from verilogic_ns_api.semantic_parsing.views import prepare_theory_view
from verilogic_ns_api.terminal_outcomes import (
    AttemptEvidence,
    CachedOutcomeType,
    PipelineFailureStatus,
    TerminalCacheEnvelope,
    TerminalErrorCode,
    TerminalRuntime,
    TerminalStage,
    build_terminal_outcome,
    terminal_outcome_hash,
    validation_error_hash,
)
from verilogic_ns_api.validation_correction.controller import ValidationCorrectionController
from verilogic_ns_api.validation_correction.models import (
    ComponentDecision,
    ComponentType,
    ReliabilityEvidence,
    TaskKind,
    TaskOutcome,
    TaskStatus,
)
from verilogic_ns_api.validation_correction.recovery_r2 import _request_ledger
from verilogic_ns_api.validation_correction.service import TaskExecution

DIGEST = "2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd"
HASH = "a" * 64


def _runtime() -> ParserRuntimeConfig:
    return ParserRuntimeConfig(
        endpoint="http://127.0.0.1:11434",
        provider_version="0.32.1",
        model="qwen3.5:4b-q4_K_M",
        model_digest=DIGEST,
        seed=20260713,
        num_ctx=8192,
        theory_num_predict=4096,
        query_num_predict=256,
        keep_alive="30m",
        timeout_seconds=30,
        max_attempts=2,
    )


def _example(index: int = 1) -> BenchmarkExample:
    source = SourceStatement(source_id="triple1", text="The dog is red.", kind="fact")
    return BenchmarkExample(
        example_id=f"proofwriter/synthetic/Q{index}",
        dataset_version="V2020.12.3",
        variant="synthetic",
        split=Split.DEVELOPMENT,
        theory_id=f"synthetic-theory-{index}",
        question_id=f"Q{index}",
        reasoning_depth=0,
        source_statements=[source],
        context=source.text,
        query="The dog is blue.",
        gold_label=GoldLabel.UNKNOWN,
        original_raw_label="Unknown",
        world_assumption=WorldAssumption.OPEN,
        source_relative_path="synthetic/dev.jsonl",
        provenance=ExampleProvenance(
            loader_version="test",
            record_line=index,
            record_sha256=f"{index:064x}",
            content_sha256=f"{index + 100:064x}",
        ),
    )


def _request() -> StructuredRequest:
    view = prepare_theory_view(_example()).public
    schema = CandidateTheoryOutput.model_json_schema()
    return StructuredRequest(
        kind="theory",
        instructions="Return a structured theory.",
        input_text=render_theory_input(view),
        prompt_hash=sha256_payload("Return a structured theory."),
        input_hash=view.input_hash,
        output_schema=schema,
        schema_hash=sha256_payload(schema),
        config=_runtime(),
    )


def _terminal(
    request: StructuredRequest | None = None,
    *,
    stage: TerminalStage = TerminalStage.SEMANTIC_PARSER_THEORY,
    error_code: TerminalErrorCode = TerminalErrorCode.OUTPUT_LIMIT_EXHAUSTED,
) -> object:
    request = request or _request()
    attempt = AttemptEvidence(
        attempt_number=1,
        request_hash=request.request_hash,
        evidence_sha256=sha256_payload({"evidence": request.request_hash}),
        finish_reason="output_limit",
        input_tokens=17,
        output_tokens=request.config.theory_num_predict,
        total_duration_ms=100,
        observed_at=datetime(2026, 7, 28, tzinfo=UTC),
    )
    return build_terminal_outcome(
        stage=stage,
        error_code=error_code,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason="Frozen request exhausted its permitted execution budget.",
        request_identity=request.identity(),
        semantic_config_hash=HASH,
        runtime=TerminalRuntime(
            endpoint=request.config.endpoint,
            provider_version=request.config.provider_version,
            model=request.config.model,
            model_digest=request.config.model_digest,
            temperature=request.config.temperature,
            seed=request.config.seed,
            num_ctx=request.config.num_ctx,
            num_predict=request.config.theory_num_predict,
            think=request.config.think,
        ),
        permitted_attempt_count=2,
        attempts=(attempt,),
    )


def test_terminal_outcome_is_strict_versioned_and_canonically_hashed() -> None:
    terminal = _terminal()
    assert terminal.schema_version == "1.0"
    assert terminal.outcome_type is CachedOutcomeType.TERMINAL_ERROR
    assert terminal.final is True
    assert terminal.valid_structured_result_produced is False
    assert terminal.terminal_outcome_sha256 == terminal_outcome_hash(terminal)
    with pytest.raises(ValidationError):
        terminal.__class__.model_validate(
            {**terminal.model_dump(mode="json"), "fabricated_ast": {}}
        )


def test_validation_error_hash_handles_exception_context() -> None:
    invalid = {
        "facts": [
            {
                "source_id": "sent1",
                "kind": "fact",
                "fact": {
                    "predicate": "red",
                    "arity": 2,
                    "arguments": [{"kind": "entity", "id": "dog"}],
                    "negated": False,
                },
            }
        ],
        "rules": [],
    }
    with pytest.raises(ValidationError) as captured:
        CandidateTheoryOutput.model_validate(invalid)
    first = validation_error_hash(captured.value)
    second = validation_error_hash(captured.value)
    assert first == second
    assert len(first) == 64


def test_terminal_outcome_preserves_unavailable_accounting_as_null() -> None:
    request = _request()
    attempt = AttemptEvidence(
        attempt_number=1,
        request_hash=request.request_hash,
        evidence_sha256=HASH,
        finish_reason="client_interrupted",
        input_tokens=None,
        output_tokens=None,
        total_duration_ms=None,
        observed_at=datetime(2026, 7, 29, tzinfo=UTC),
    )
    terminal = build_terminal_outcome(
        stage=TerminalStage.THEORY_CORRECTION,
        error_code=TerminalErrorCode.INVALID_STRUCTURED_OUTPUT,
        pipeline_status=PipelineFailureStatus.STRUCTURED_OUTPUT_ERROR,
        reason="The response was rejected before telemetry could be persisted.",
        request_identity=request.identity(),
        semantic_config_hash="d" * 64,
        runtime=TerminalRuntime(
            endpoint=request.config.endpoint,
            provider_version=request.config.provider_version,
            model=request.config.model,
            model_digest=request.config.model_digest,
            temperature=request.config.temperature,
            seed=request.config.seed,
            num_ctx=request.config.num_ctx,
            num_predict=request.config.theory_num_predict,
            think=request.config.think,
        ),
        permitted_attempt_count=2,
        attempts=(attempt,),
    )
    assert terminal.input_tokens is None
    assert terminal.output_tokens is None
    assert terminal.total_duration_ms is None
    assert terminal.model_dump(mode="json")["output_tokens"] is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("request_hash", "b" * 64, "another request"),
        ("input_tokens", 18, "input-token"),
        ("output_tokens", 4095, "output-token"),
        ("observed_attempt_count", 2, "attempt count"),
        ("terminal_outcome_sha256", "b" * 64, "outcome hash"),
    ],
)
def test_terminal_outcome_rejects_tampered_provenance(
    field: str, value: object, message: str
) -> None:
    terminal = _terminal()
    payload = terminal.model_dump(mode="json")
    payload[field] = value
    with pytest.raises(ValidationError, match=message):
        terminal.__class__.model_validate(payload)


def test_terminal_outcome_rejects_wrong_model_digest() -> None:
    terminal = _terminal()
    payload = terminal.model_dump(mode="json")
    payload["model_digest"] = "b" * 64
    with pytest.raises(ValidationError, match="model contract"):
        terminal.__class__.model_validate(payload)


@pytest.mark.parametrize("field", ["prompt_hash", "schema_hash"])
def test_terminal_envelope_rejects_wrong_prompt_or_schema(field: str) -> None:
    request = _request()
    terminal = _terminal(request)
    identity = request.identity()
    identity[field] = "b" * 64
    with pytest.raises(ValidationError):
        TerminalCacheEnvelope(request_identity=identity, terminal_error=terminal)


def test_cache_distinguishes_miss_terminal_and_success(tmp_path: Path) -> None:
    request = _request()
    cache = ParserResponseCache(tmp_path)
    assert cache.load_outcome(request) is None
    cache.store_terminal(request, _terminal(request))
    lookup = cache.load_outcome(request)
    assert lookup is not None
    assert lookup.outcome_type is CachedOutcomeType.TERMINAL_ERROR
    assert lookup.response is None
    assert lookup.terminal_error is not None


def test_cache_distinguishes_incomplete_corrupt_and_contract_mismatch(tmp_path: Path) -> None:
    request = _request()
    cache = ParserResponseCache(tmp_path)
    target = cache.path_for(request)
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    with pytest.raises(ParserCacheIncomplete):
        cache.load_outcome(request)
    target.write_text("{", encoding="utf-8")
    with pytest.raises(ParserCacheCorrupt):
        cache.load_outcome(request)
    target.write_text(
        json.dumps({"request_identity": {"wrong": True}, "response": {}}),
        encoding="utf-8",
    )
    with pytest.raises(ParserCacheContractMismatch):
        cache.load_outcome(request)


def test_terminal_cache_write_is_atomic_and_replay_needs_no_provider(tmp_path: Path) -> None:
    request = _request()
    cache = ParserResponseCache(tmp_path)
    target = cache.store_terminal(request, _terminal(request))
    assert target.is_file()
    assert not list(target.parent.glob(f".{target.name}.*"))

    provider = SimpleNamespace(calls=0)

    def complete(_request):
        provider.calls += 1
        raise AssertionError("terminal cache replay must not dispatch")

    provider.complete = complete
    parser = SemanticParser(
        config=request.config,
        theory_prompt=request.instructions,
        theory_prompt_hash=request.prompt_hash,
        query_prompt="unused",
        query_prompt_hash=HASH,
        cache=cache,
        provider=provider,
        replay_only=False,
    )
    result = parser.parse_theory(prepare_theory_view(_example()).public)
    assert result.candidate is None
    assert result.outcome.status is ParserStatus.STRUCTURED_OUTPUT_ERROR
    assert result.outcome.error_type == "OUTPUT_LIMIT_EXHAUSTED"
    assert result.outcome.cache_hit is True
    assert provider.calls == 0


def test_cache_only_terminal_replay_is_identical(tmp_path: Path) -> None:
    request = _request()
    cache = ParserResponseCache(tmp_path)
    terminal = _terminal(request)
    cache.store_terminal(request, terminal)
    first = cache.load_outcome(request)
    second = cache.load_outcome(request)
    assert first == second
    assert second.terminal_error.terminal_outcome_sha256 == terminal.terminal_outcome_sha256


def test_terminal_critic_and_correction_propagate_as_error() -> None:
    terminal_task = TaskOutcome(
        task_kind=TaskKind.CRITIC_THEORY,
        request_hash=HASH,
        status=TaskStatus.STRUCTURED_OUTPUT_ERROR,
        cache_hit=True,
        error_type="OUTPUT_LIMIT_EXHAUSTED",
        terminal=True,
        terminal_outcome_hash="b" * 64,
    )

    class Service:
        def critique_theory(self, _value):
            return TaskExecution(outcome=terminal_task, value=None)

    decision = ValidationCorrectionController(Service()).run_theory(
        view=prepare_theory_view(_example()),
        raw_candidate={
            "facts": [
                {
                    "source_id": "sent1",
                    "kind": "fact",
                    "fact": {
                        "predicate": "red",
                        "arity": 1,
                        "arguments": [{"kind": "entity", "id": "dog"}],
                        "negated": False,
                    },
                }
            ],
            "rules": [],
        },
        theory_id="synthetic-theory-1",
    )
    assert decision.error_type == "OUTPUT_LIMIT_EXHAUSTED"
    assert decision.abstention_reason is None
    assert decision.task_outcomes[0].terminal is True

    correction_task = terminal_task.model_copy(update={"task_kind": TaskKind.CORRECTION_THEORY})

    class CorrectionService:
        def correct_theory(self, _value):
            return TaskExecution(outcome=correction_task, value=None)

    corrected = ValidationCorrectionController(CorrectionService()).run_theory(
        view=prepare_theory_view(_example()),
        raw_candidate=None,
        theory_id="synthetic-theory-1",
    )
    assert corrected.error_type == "OUTPUT_LIMIT_EXHAUSTED"
    assert corrected.correction_attempts == 1
    assert corrected.abstention_reason is None


def test_terminal_failure_does_not_become_unknown_or_abstain_in_metrics() -> None:
    item = _example()
    prediction = PredictionRecord(
        run_id="r3-test",
        example_id=item.example_id,
        predicted_label=PredictionLabel.ERROR,
        error_type="OUTPUT_LIMIT_EXHAUSTED",
        latency_ms=0,
        predictor_name="r3-test",
        predictor_version="1",
        timestamp=datetime.now(UTC),
    )
    report = compute_metrics((item,), (prediction,))
    assert report.total_examples == 1
    assert report.errored_examples == 1
    assert report.answered_examples == 0
    assert report.accuracy == 0
    assert report.coverage == 0
    assert report.confusion_matrix["UNKNOWN"]["ERROR"] == 1


def test_terminal_outcomes_are_not_counted_as_cache_misses_or_new_calls() -> None:
    terminal_task = TaskOutcome(
        task_kind=TaskKind.CORRECTION_QUERY,
        request_hash=HASH,
        status=TaskStatus.STRUCTURED_OUTPUT_ERROR,
        cache_hit=True,
        error_type="OUTPUT_LIMIT_EXHAUSTED",
        terminal=True,
        terminal_outcome_hash="b" * 64,
        input_tokens=10,
        output_tokens=4096,
        duration_ms=500,
    )
    decision = SimpleNamespace(task_outcomes=(terminal_task,))
    ledger = _request_ledger({"theory": decision}, {})
    assert ledger["summary"]["terminal_outcomes"] == 1
    assert ledger["summary"]["cache_misses"] == 0
    assert ledger["summary"]["new_local_calls"] == 0
    assert ledger["summary"]["input_tokens"] == 10
    assert ledger["summary"]["output_tokens"] == 4096


def test_terminal_task_model_cannot_fabricate_success() -> None:
    with pytest.raises(ValidationError):
        TaskOutcome(
            task_kind=TaskKind.CORRECTION_QUERY,
            request_hash=HASH,
            status=TaskStatus.SUCCESS,
            terminal=True,
            terminal_outcome_hash="b" * 64,
        )


def test_one_correction_maximum_remains_in_model_contract() -> None:
    reliability = ReliabilityEvidence(
        structured_output_valid=False,
        source_coverage_complete=False,
        semantic_validation_passed=False,
        critic_accepted=False,
        correction_required=True,
        correction_succeeded=False,
    )
    with pytest.raises(ValidationError):
        ComponentDecision(
            component_type=ComponentType.THEORY,
            input_hash=HASH,
            raw_candidate_hash=HASH,
            deterministic_accepted=False,
            selective_accepted=False,
            correction_attempts=2,
            reliability=reliability,
            transitions=(),
        )
