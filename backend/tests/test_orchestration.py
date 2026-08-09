from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from verilogic_ns_api.orchestration.budget import DispatchBudget
from verilogic_ns_api.orchestration.errors import PipelineCancelled, QueueFullError
from verilogic_ns_api.orchestration.factory import PipelineRuntime
from verilogic_ns_api.orchestration.jobs import InMemoryJobManager
from verilogic_ns_api.orchestration.models import (
    InputMode,
    PipelineDisposition,
    PipelineRequest,
    PolicyMode,
    RunStatus,
)
from verilogic_ns_api.orchestration.pipeline import NeuroSymbolicPipeline
from verilogic_ns_api.reasoning.configuration import ProofVerificationError, ResourceLimitError
from verilogic_ns_api.semantic_parsing.models import (
    CandidateFactLiteral,
    CandidateFactStatement,
    CandidateQueryOutput,
    CandidateRule,
    CandidateRuleLiteral,
    CandidateRuleStatement,
    CandidateTheoryOutput,
    ParserKind,
    ParserOutcome,
    ParserStatus,
)
from verilogic_ns_api.semantic_parsing.service import ParseExecution
from verilogic_ns_api.validation_correction.controller import ValidationCorrectionController
from verilogic_ns_api.validation_correction.models import (
    CriticCategory,
    CriticDecision,
    QueryCriticReport,
    TaskKind,
    TaskOutcome,
    TaskStatus,
    TheoryCriticIssue,
    TheoryCriticReport,
)
from verilogic_ns_api.validation_correction.service import TaskExecution

ROOT = Path(__file__).resolve().parents[2]


def _formal(name: str) -> PipelineRequest:
    raw = json.loads((ROOT / "examples" / "theories" / f"{name}.json").read_text())
    return PipelineRequest.model_validate(
        {
            "input_mode": "FORMAL_AST",
            "formal_ast": {"theory": raw, "query": raw["query"]},
        }
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("entailed", "ENTAILED"),
        ("contradicted", "CONTRADICTED"),
        ("unknown", "UNKNOWN"),
        ("inconsistent", "INCONSISTENT"),
    ],
)
def test_formal_pipeline_answers_without_provider(name: str, expected: str) -> None:
    result = NeuroSymbolicPipeline().run(_formal(name))
    assert result.disposition is PipelineDisposition.ANSWERED
    assert result.logical_result.value == expected
    assert result.proof_verification is not None and result.proof_verification.valid
    assert result.provenance.provider_dispatches == 0
    assert result.provenance.model_used is False
    assert result.explanation.verifier_status == "VERIFIED"


def test_formal_explanation_and_hashes_are_deterministic() -> None:
    first = NeuroSymbolicPipeline().run(_formal("entailed"))
    second = NeuroSymbolicPipeline().run(_formal("entailed"))
    assert first.explanation == second.explanation
    assert first.provenance.input_hash == second.provenance.input_hash
    assert first.proof == second.proof


class _LimitEngine:
    def reason(self, _theory: object) -> object:
        raise ResourceLimitError("max_rounds", 1, 2)


class _FailingVerifier:
    def verify_result(self, _theory: object, _result: object) -> object:
        raise ProofVerificationError("tampered", "proof did not replay")


def test_symbolic_limit_and_proof_failure_are_typed_errors() -> None:
    limited = NeuroSymbolicPipeline(engine=_LimitEngine()).run(_formal("entailed"))  # type: ignore[arg-type]
    assert limited.disposition is PipelineDisposition.ERROR
    assert limited.logical_result is None
    assert limited.error is not None and limited.error.code == "SYMBOLIC_RESOURCE_LIMIT"

    unverified = NeuroSymbolicPipeline(verifier=_FailingVerifier()).run(_formal("entailed"))  # type: ignore[arg-type]
    assert unverified.disposition is PipelineDisposition.ERROR
    assert unverified.logical_result is None
    assert unverified.proof is None
    assert unverified.error is not None and unverified.error.code == "PROOF_VERIFICATION_FAILED"


def _fact(source_id: str, predicate: str, entity: str, *, negated: bool = False):
    return CandidateFactStatement(
        source_id=source_id,
        kind="fact",
        fact=CandidateFactLiteral(
            predicate=predicate,
            arity=1,
            arguments=({"kind": "entity", "id": entity},),
            negated=negated,
        ),
    )


def _rule(source_id: str):
    return CandidateRuleStatement(
        source_id=source_id,
        kind="rule",
        rule=CandidateRule(
            variables=({"name": "X"},),
            body=(
                CandidateRuleLiteral(
                    predicate="red",
                    arity=1,
                    arguments=({"kind": "variable", "name": "X"},),
                    negated=False,
                ),
            ),
            head=CandidateRuleLiteral(
                predicate="warm",
                arity=1,
                arguments=({"kind": "variable", "name": "X"},),
                negated=False,
            ),
        ),
    )


GOOD_THEORY = CandidateTheoryOutput(
    facts=(_fact("sent1", "red", "robin"),), rules=(_rule("sent2"),)
)
MISSING_SOURCE_THEORY = CandidateTheoryOutput(facts=(_fact("sent1", "red", "robin"),), rules=())
GOOD_QUERY = CandidateQueryOutput(
    query=CandidateFactLiteral(
        predicate="warm",
        arity=1,
        arguments=({"kind": "entity", "id": "robin"},),
        negated=False,
    )
)


class _FakeParser:
    def __init__(self, theory=GOOD_THEORY, query=GOOD_QUERY, *, fail: str | None = None) -> None:
        self.theory = theory
        self.query = query
        self.fail = fail

    def parse_theory(self, value) -> ParseExecution:
        if self.fail == "theory":
            return self._failed(ParserKind.THEORY, value.input_hash)
        return self._parsed(ParserKind.THEORY, value.input_hash, self.theory)

    def parse_query(self, value) -> ParseExecution:
        if self.fail == "query":
            return self._failed(ParserKind.QUERY, value.input_hash)
        return self._parsed(ParserKind.QUERY, value.input_hash, self.query)

    @staticmethod
    def _parsed(kind, input_hash, candidate):
        return ParseExecution(
            outcome=ParserOutcome(
                parser_kind=kind,
                input_hash=input_hash,
                request_hash="a" * 64,
                status=ParserStatus.PARSED,
                cache_hit=True,
                candidate=candidate.model_dump(mode="json"),
            ),
            candidate=candidate,
        )

    @staticmethod
    def _failed(kind, input_hash):
        return ParseExecution(
            outcome=ParserOutcome(
                parser_kind=kind,
                input_hash=input_hash,
                request_hash="b" * 64,
                status=ParserStatus.PROVIDER_ERROR,
                cache_hit=True,
                error_type="PROVIDER_FAILURE",
                error_message="typed terminal",
            ),
            candidate=None,
        )


class _FakeCorrectionService:
    def __init__(self, mode: str = "accept") -> None:
        self.mode = mode
        self.calls = 0

    def critique_theory(self, _value):
        return self._critic(TaskKind.CRITIC_THEORY)

    def critique_query(self, _value):
        return self._critic(TaskKind.CRITIC_QUERY)

    def correct_theory(self, _value):
        if self.mode == "terminal_correction":
            return self._terminal(TaskKind.CORRECTION_THEORY)
        return self._success(TaskKind.CORRECTION_THEORY, GOOD_THEORY)

    def correct_query(self, _value):
        if self.mode == "terminal_correction":
            return self._terminal(TaskKind.CORRECTION_QUERY)
        return self._success(TaskKind.CORRECTION_QUERY, GOOD_QUERY)

    def _critic(self, kind):
        if self.mode == "terminal_critic":
            return self._terminal(kind)
        if self.mode == "revise":
            report = TheoryCriticReport(
                decision=CriticDecision.REVISE,
                issues=(
                    TheoryCriticIssue(
                        source_id="sent1",
                        category=CriticCategory.OTHER_MISMATCH,
                        description="Synthetic revision request.",
                    ),
                ),
            )
            if kind is TaskKind.CRITIC_QUERY:
                report = QueryCriticReport(decision=CriticDecision.ACCEPT)
            return self._success(kind, report)
        report = (
            TheoryCriticReport(decision=CriticDecision.ACCEPT)
            if kind is TaskKind.CRITIC_THEORY
            else QueryCriticReport(decision=CriticDecision.ACCEPT)
        )
        return self._success(kind, report)

    def _success(self, kind, value):
        self.calls += 1
        return TaskExecution(
            outcome=TaskOutcome(
                task_kind=kind,
                request_hash=f"{self.calls:x}".rjust(64, "0"),
                status=TaskStatus.SUCCESS,
                cache_hit=True,
                output=value.model_dump(mode="json"),
            ),
            value=value,
        )

    def _terminal(self, kind):
        self.calls += 1
        return TaskExecution(
            outcome=TaskOutcome(
                task_kind=kind,
                request_hash=f"{self.calls:x}".rjust(64, "0"),
                status=TaskStatus.PROVIDER_ERROR,
                cache_hit=True,
                error_type="PROVIDER_FAILURE",
                error_message="typed terminal failure",
                input_tokens=None,
                output_tokens=None,
                duration_ms=None,
                terminal=True,
                terminal_outcome_hash="f" * 64,
            ),
            value=None,
        )


def _natural(policy: PolicyMode = PolicyMode.P2_SELECTIVE) -> PipelineRequest:
    return PipelineRequest.model_validate(
        {
            "input_mode": InputMode.NATURAL_LANGUAGE,
            "policy_mode": policy,
            "natural_language": {
                "statements": [
                    {"source_id": "s1", "kind": "fact", "text": "The robin is red."},
                    {
                        "source_id": "s2",
                        "kind": "rule",
                        "text": "If something is red, then it is warm.",
                    },
                ],
                "query": "The robin is warm.",
            },
        }
    )


@pytest.mark.parametrize("policy", list(PolicyMode))
def test_natural_fake_provider_supports_all_policy_modes(policy: PolicyMode) -> None:
    service = _FakeCorrectionService()
    pipeline = NeuroSymbolicPipeline(
        parser=_FakeParser(),
        controller=ValidationCorrectionController(service),  # type: ignore[arg-type]
    )
    result = pipeline.run(_natural(policy))
    assert result.disposition is PipelineDisposition.ANSWERED
    assert result.logical_result.value == "ENTAILED"
    assert result.proof_verification is not None
    assert service.calls == (0 if policy is PolicyMode.P0_RAW else 2)


def test_correction_abstention_and_terminal_failures_remain_distinct() -> None:
    corrected_service = _FakeCorrectionService()
    corrected = NeuroSymbolicPipeline(
        parser=_FakeParser(theory=MISSING_SOURCE_THEORY),
        controller=ValidationCorrectionController(corrected_service),  # type: ignore[arg-type]
    ).run(_natural())
    assert corrected.disposition is PipelineDisposition.ANSWERED
    assert corrected.correction_attempted

    revise_service = _FakeCorrectionService("revise")
    abstained = NeuroSymbolicPipeline(
        parser=_FakeParser(),
        controller=ValidationCorrectionController(revise_service),  # type: ignore[arg-type]
    ).run(_natural())
    assert abstained.disposition is PipelineDisposition.ABSTAINED
    assert abstained.logical_result is None
    assert abstained.error is None

    critic_service = _FakeCorrectionService("terminal_critic")
    critic_error = NeuroSymbolicPipeline(
        parser=_FakeParser(),
        controller=ValidationCorrectionController(critic_service),  # type: ignore[arg-type]
    ).run(_natural())
    assert critic_error.disposition is PipelineDisposition.ERROR
    assert critic_error.logical_result is None
    assert critic_error.abstention_reason is None

    correction_service = _FakeCorrectionService("terminal_correction")
    correction_error = NeuroSymbolicPipeline(
        parser=_FakeParser(theory=MISSING_SOURCE_THEORY),
        controller=ValidationCorrectionController(correction_service),  # type: ignore[arg-type]
    ).run(_natural())
    assert correction_error.disposition is PipelineDisposition.ERROR
    assert correction_error.error is not None
    assert correction_error.error.stage.value == "CORRECTION"


def test_parser_and_source_coverage_failures_never_become_unknown_or_abstain() -> None:
    parser_error = NeuroSymbolicPipeline(parser=_FakeParser(fail="theory")).run(
        _natural(PolicyMode.P0_RAW)
    )
    assert parser_error.disposition is PipelineDisposition.ERROR
    assert parser_error.logical_result is None

    coverage_error = NeuroSymbolicPipeline(parser=_FakeParser(theory=MISSING_SOURCE_THEORY)).run(
        _natural(PolicyMode.P0_RAW)
    )
    assert coverage_error.disposition is PipelineDisposition.ERROR
    assert coverage_error.error is not None
    assert coverage_error.error.code == "SOURCE_COVERAGE_ERROR"


class _BlockingPipeline:
    def __init__(
        self, entered: threading.Event, release: threading.Event, calls: list[int]
    ) -> None:
        self.entered = entered
        self.release = release
        self.calls = calls

    def run(self, request, *, cancelled, on_stage):
        self.calls.append(1)
        self.entered.set()
        while not self.release.wait(0.01):
            if cancelled():
                raise PipelineCancelled()
        return NeuroSymbolicPipeline().run(request, cancelled=cancelled)


def test_job_manager_bounds_queue_cancels_and_polling_never_executes_again() -> None:
    entered = threading.Event()
    release = threading.Event()
    calls: list[int] = []

    def factory(_request):
        return PipelineRuntime(
            pipeline=_BlockingPipeline(entered, release, calls),  # type: ignore[arg-type]
            budget=DispatchBudget(),
            providers=(),
        )

    manager = InMemoryJobManager(factory, maximum_queued_jobs=1, maximum_retained_jobs=4)
    first = manager.submit(_formal("entailed"))
    assert entered.wait(1)
    queued = manager.submit(_formal("unknown"))
    with pytest.raises(QueueFullError):
        manager.submit(_formal("contradicted"))
    assert manager.cancel(queued.run_id).status is RunStatus.CANCELLED
    for _ in range(5):
        assert manager.get(first.run_id).status in {RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED}
    assert calls == [1]
    release.set()
    deadline = time.monotonic() + 2
    while manager.get(first.run_id).status is not RunStatus.COMPLETED:
        assert time.monotonic() < deadline
        time.sleep(0.01)
    assert calls == [1]
    manager.shutdown()
