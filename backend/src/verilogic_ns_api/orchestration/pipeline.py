from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from verilogic_ns_api.orchestration.errors import OrchestrationError, PipelineCancelled
from verilogic_ns_api.orchestration.explanations import (
    abstention_explanation,
    error_explanation,
    explanation_from_verified_proof,
)
from verilogic_ns_api.orchestration.models import (
    InputMode,
    PipelineDisposition,
    PipelineError,
    PipelineProvenance,
    PipelineRequest,
    PipelineResult,
    PolicyMode,
    ProviderMode,
    StageName,
    StageStatus,
)
from verilogic_ns_api.orchestration.trace import TraceCollector
from verilogic_ns_api.reasoning.configuration import (
    ProofVerificationError,
    ResourceLimitError,
)
from verilogic_ns_api.reasoning.engine import ForwardChainingEngine
from verilogic_ns_api.reasoning.models import Theory, theory_hash
from verilogic_ns_api.reasoning.verifier import ProofVerifier
from verilogic_ns_api.semantic_parsing.models import (
    CandidateQueryOutput,
    CandidateTheoryOutput,
)
from verilogic_ns_api.semantic_parsing.service import ParseExecution
from verilogic_ns_api.semantic_parsing.views import (
    PreparedQueryView,
    PreparedTheoryView,
    prepare_query_view_from_text,
    prepare_theory_view_from_statements,
)
from verilogic_ns_api.validation_correction.controller import ValidationCorrectionController
from verilogic_ns_api.validation_correction.feedback import (
    QueryValidation,
    TheoryValidation,
    validate_query_candidate,
    validate_theory_candidate,
)
from verilogic_ns_api.validation_correction.models import (
    ComponentDecision,
    FeedbackIssueCode,
    TaskKind,
    TaskStatus,
)


class ParserService(Protocol):
    def parse_theory(self, value: object) -> ParseExecution[CandidateTheoryOutput]: ...

    def parse_query(self, value: object) -> ParseExecution[CandidateQueryOutput]: ...


@dataclass(frozen=True)
class PipelineMetadata:
    provider_mode: ProviderMode = ProviderMode.CACHE_ONLY
    engine_version: str = "phase4-forward-chainer.v1"
    model_name: str | None = None
    model_digest: str | None = None
    provider_version: str | None = None
    prompt_hashes: dict[str, str] = field(default_factory=dict)
    schema_hashes: dict[str, str] = field(default_factory=dict)
    policy_hash: str | None = None


@dataclass
class _Accounting:
    cache_hits: int = 0
    cache_misses: int = 0
    correction_attempted: bool = False

    def cache(self, hit: bool) -> None:
        if hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1


class NeuroSymbolicPipeline:
    def __init__(
        self,
        *,
        parser: ParserService | None = None,
        controller: ValidationCorrectionController | None = None,
        metadata: PipelineMetadata | None = None,
        dispatch_count: Callable[[], int] | None = None,
        engine: ForwardChainingEngine | None = None,
        verifier: ProofVerifier | None = None,
    ) -> None:
        self.parser = parser
        self.controller = controller
        self.metadata = metadata or PipelineMetadata()
        self.dispatch_count = dispatch_count or (lambda: 0)
        self.engine = engine or ForwardChainingEngine()
        self.verifier = verifier or ProofVerifier()

    def run(
        self,
        request: PipelineRequest,
        *,
        cancelled: Callable[[], bool] | None = None,
        on_stage: Callable[[StageName], None] | None = None,
    ) -> PipelineResult:
        trace = TraceCollector()
        accounting = _Accounting()
        is_cancelled = cancelled or (lambda: False)
        progress = on_stage or (lambda _stage: None)
        trace.set(StageName.INPUT_VALIDATION, StageStatus.SUCCEEDED)
        try:
            self._check_cancel(is_cancelled)
            if request.input_mode is InputMode.FORMAL_AST:
                assert request.formal_ast is not None
                theory = request.formal_ast.resolved_theory()
                for stage in (
                    StageName.THEORY_PARSING,
                    StageName.QUERY_PARSING,
                    StageName.SOURCE_COVERAGE,
                    StageName.SEMANTIC_VALIDATION,
                    StageName.CRITIC,
                    StageName.CORRECTION,
                    StageName.RELIABILITY_POLICY,
                ):
                    trace.set(stage, StageStatus.SKIPPED)
                return self._reason(
                    request,
                    theory,
                    trace,
                    accounting,
                    is_cancelled,
                    progress,
                )
            return self._run_natural(request, trace, accounting, is_cancelled, progress)
        except PipelineCancelled:
            raise
        except OrchestrationError as error:
            return self._error_result(request, trace, accounting, error)
        except Exception as error:
            safe = OrchestrationError(
                StageName.FINAL_DECISION,
                "INTERNAL_PIPELINE_ERROR",
                f"The pipeline stopped safely because {type(error).__name__} occurred.",
            )
            return self._error_result(request, trace, accounting, safe)

    def _run_natural(
        self,
        request: PipelineRequest,
        trace: TraceCollector,
        accounting: _Accounting,
        cancelled: Callable[[], bool],
        progress: Callable[[StageName], None],
    ) -> PipelineResult:
        if self.parser is None:
            raise OrchestrationError(
                StageName.THEORY_PARSING,
                "NATURAL_LANGUAGE_UNAVAILABLE",
                "Natural-language parsing is unavailable in this runtime.",
            )
        assert request.natural_language is not None
        statements = tuple(
            (
                item.source_id or f"source_{index}",
                item.text,
                item.kind.value,
            )
            for index, item in enumerate(request.natural_language.statements, start=1)
        )
        theory_view = prepare_theory_view_from_statements(statements)
        query_view = prepare_query_view_from_text(request.natural_language.query)

        theory_execution = self._parse_theory(theory_view, trace, accounting, cancelled, progress)
        query_execution = self._parse_query(query_view, trace, accounting, cancelled, progress)
        if theory_execution.candidate is None:
            raise self._parser_error(StageName.THEORY_PARSING, theory_execution)
        if query_execution.candidate is None:
            raise self._parser_error(StageName.QUERY_PARSING, query_execution)

        theory_id = f"interactive_{request.canonical_hash[:16]}"
        if request.policy_mode is PolicyMode.P0_RAW:
            trace.set(StageName.CRITIC, StageStatus.SKIPPED)
            trace.set(StageName.CORRECTION, StageStatus.SKIPPED)
            trace.set(StageName.RELIABILITY_POLICY, StageStatus.SKIPPED)
            theory_validation = validate_theory_candidate(
                theory_execution.candidate.model_dump(mode="json"),
                theory_view,
                theory_id=theory_id,
            )
            self._record_validation(trace, theory_validation)
            if not theory_validation.valid or theory_validation.converted is None:
                raise self._validation_error(theory_validation)
            query_validation = validate_query_candidate(
                query_execution.candidate.model_dump(mode="json"),
                query_view,
                body=theory_validation.converted,
            )
            self._record_query_validation(trace, query_validation)
            if not query_validation.valid or query_validation.theory is None:
                raise self._query_validation_error(query_validation)
            return self._reason(
                request,
                query_validation.theory,
                trace,
                accounting,
                cancelled,
                progress,
            )

        if self.controller is None:
            raise OrchestrationError(
                StageName.CRITIC,
                "CORRECTION_UNAVAILABLE",
                "Validation-guided correction is unavailable in this runtime.",
            )
        self._check_cancel(cancelled)
        progress(StageName.SEMANTIC_VALIDATION)
        theory_decision = self.controller.run_theory(
            view=theory_view,
            raw_candidate=theory_execution.candidate.model_dump(mode="json"),
            theory_id=theory_id,
        )
        self._account_decision(accounting, theory_decision)
        self._record_decision_stages(trace, theory_decision)
        terminal = self._terminal_decision_error(theory_decision)
        if terminal is not None:
            raise terminal
        theory_accepted = self._accepted(request.policy_mode, theory_decision)
        if not theory_accepted or theory_decision.final_candidate is None:
            return self._abstained_result(
                request,
                trace,
                accounting,
                (theory_decision.abstention_reason or "RELIABILITY_GATE_FAILED").value
                if theory_decision.abstention_reason is not None
                else "RELIABILITY_GATE_FAILED",
            )
        final_theory_validation = validate_theory_candidate(
            theory_decision.final_candidate,
            theory_view,
            theory_id=theory_id,
        )
        if not final_theory_validation.valid or final_theory_validation.converted is None:
            raise self._validation_error(final_theory_validation)

        self._check_cancel(cancelled)
        query_decision = self.controller.run_query(
            view=query_view,
            raw_candidate=query_execution.candidate.model_dump(mode="json"),
            body=final_theory_validation.converted,
        )
        self._account_decision(accounting, query_decision)
        self._record_decision_stages(trace, query_decision, merge=True)
        terminal = self._terminal_decision_error(query_decision)
        if terminal is not None:
            raise terminal
        query_accepted = self._accepted(request.policy_mode, query_decision)
        if not query_accepted or query_decision.final_candidate is None:
            return self._abstained_result(
                request,
                trace,
                accounting,
                (query_decision.abstention_reason or "RELIABILITY_GATE_FAILED").value
                if query_decision.abstention_reason is not None
                else "RELIABILITY_GATE_FAILED",
            )
        final_query_validation = validate_query_candidate(
            query_decision.final_candidate,
            query_view,
            body=final_theory_validation.converted,
        )
        if not final_query_validation.valid or final_query_validation.theory is None:
            raise self._query_validation_error(final_query_validation)
        trace.set(StageName.SOURCE_COVERAGE, StageStatus.SUCCEEDED)
        trace.set(StageName.SEMANTIC_VALIDATION, StageStatus.SUCCEEDED)
        trace.set(StageName.RELIABILITY_POLICY, StageStatus.SUCCEEDED)
        return self._reason(
            request,
            final_query_validation.theory,
            trace,
            accounting,
            cancelled,
            progress,
        )

    def _parse_theory(
        self,
        view: PreparedTheoryView,
        trace: TraceCollector,
        accounting: _Accounting,
        cancelled: Callable[[], bool],
        progress: Callable[[StageName], None],
    ) -> ParseExecution[CandidateTheoryOutput]:
        self._check_cancel(cancelled)
        progress(StageName.THEORY_PARSING)
        started = time.perf_counter()
        execution = self.parser.parse_theory(view.public)  # type: ignore[union-attr]
        accounting.cache(execution.outcome.cache_hit)
        trace.set(
            StageName.THEORY_PARSING,
            StageStatus.SUCCEEDED if execution.candidate is not None else StageStatus.FAILED,
            duration_ms=(time.perf_counter() - started) * 1000,
            cache_status="hit" if execution.outcome.cache_hit else "miss",
            error_code=execution.outcome.error_type,
        )
        return execution

    def _parse_query(
        self,
        view: PreparedQueryView,
        trace: TraceCollector,
        accounting: _Accounting,
        cancelled: Callable[[], bool],
        progress: Callable[[StageName], None],
    ) -> ParseExecution[CandidateQueryOutput]:
        self._check_cancel(cancelled)
        progress(StageName.QUERY_PARSING)
        started = time.perf_counter()
        execution = self.parser.parse_query(view.public)  # type: ignore[union-attr]
        accounting.cache(execution.outcome.cache_hit)
        trace.set(
            StageName.QUERY_PARSING,
            StageStatus.SUCCEEDED if execution.candidate is not None else StageStatus.FAILED,
            duration_ms=(time.perf_counter() - started) * 1000,
            cache_status="hit" if execution.outcome.cache_hit else "miss",
            error_code=execution.outcome.error_type,
        )
        return execution

    def _reason(
        self,
        request: PipelineRequest,
        theory: Theory,
        trace: TraceCollector,
        accounting: _Accounting,
        cancelled: Callable[[], bool],
        progress: Callable[[StageName], None],
    ) -> PipelineResult:
        self._check_cancel(cancelled)
        progress(StageName.SYMBOLIC_REASONING)
        try:
            with trace.measure(StageName.SYMBOLIC_REASONING):
                reasoning = self.engine.reason(theory)
        except ResourceLimitError as error:
            raise OrchestrationError(
                StageName.SYMBOLIC_REASONING,
                "SYMBOLIC_RESOURCE_LIMIT",
                "The deterministic reasoner reached a configured resource limit.",
            ) from error
        self._check_cancel(cancelled)
        progress(StageName.PROOF_VERIFICATION)
        try:
            with trace.measure(StageName.PROOF_VERIFICATION):
                verified = self.verifier.verify_result(theory, reasoning.result)
        except (ProofVerificationError, ResourceLimitError) as error:
            raise OrchestrationError(
                StageName.PROOF_VERIFICATION,
                "PROOF_VERIFICATION_FAILED",
                "Independent proof verification failed.",
            ) from error
        trace.set(StageName.FINAL_DECISION, StageStatus.SUCCEEDED)
        trace.finish_unstarted()
        return PipelineResult(
            disposition=PipelineDisposition.ANSWERED,
            logical_result=reasoning.result.status,
            explanation=explanation_from_verified_proof(reasoning.result.proof),
            trace=trace.as_tuple(),
            provenance=self._provenance(
                request,
                accounting,
                accepted_theory=theory,
                proof_verified=True,
            ),
            proof=reasoning.result.proof,
            proof_verification=verified,
            reasoning_telemetry=reasoning.telemetry,
            accepted_theory=theory,
            correction_attempted=accounting.correction_attempted,
        )

    def _abstained_result(
        self,
        request: PipelineRequest,
        trace: TraceCollector,
        accounting: _Accounting,
        reason: str,
    ) -> PipelineResult:
        trace.set(StageName.RELIABILITY_POLICY, StageStatus.ABSTAINED, message=reason)
        trace.set(StageName.FINAL_DECISION, StageStatus.ABSTAINED, message=reason)
        trace.finish_unstarted()
        return PipelineResult(
            disposition=PipelineDisposition.ABSTAINED,
            explanation=abstention_explanation(reason),
            trace=trace.as_tuple(),
            provenance=self._provenance(request, accounting),
            correction_attempted=accounting.correction_attempted,
            abstention_reason=reason,
        )

    def _error_result(
        self,
        request: PipelineRequest,
        trace: TraceCollector,
        accounting: _Accounting,
        error: OrchestrationError,
    ) -> PipelineResult:
        trace.set(
            error.stage,
            StageStatus.FAILED,
            error_code=error.code,
            message=error.safe_message,
        )
        trace.set(
            StageName.FINAL_DECISION,
            StageStatus.FAILED,
            error_code=error.code,
            message=error.safe_message,
        )
        trace.finish_unstarted()
        return PipelineResult(
            disposition=PipelineDisposition.ERROR,
            explanation=error_explanation(error.stage.value, error.code),
            trace=trace.as_tuple(),
            provenance=self._provenance(request, accounting),
            correction_attempted=accounting.correction_attempted,
            error=PipelineError(
                stage=error.stage,
                code=error.code,
                message=error.safe_message,
            ),
        )

    def _provenance(
        self,
        request: PipelineRequest,
        accounting: _Accounting,
        *,
        accepted_theory: Theory | None = None,
        proof_verified: bool = False,
    ) -> PipelineProvenance:
        model_used = request.input_mode is InputMode.NATURAL_LANGUAGE
        return PipelineProvenance(
            input_hash=request.canonical_hash,
            input_mode=request.input_mode,
            policy_mode=request.policy_mode,
            provider_mode=self.metadata.provider_mode,
            engine_version=self.metadata.engine_version,
            model_used=model_used,
            model_name=self.metadata.model_name if model_used else None,
            model_digest=self.metadata.model_digest if model_used else None,
            provider_version=self.metadata.provider_version if model_used else None,
            prompt_hashes=self.metadata.prompt_hashes if model_used else {},
            schema_hashes=self.metadata.schema_hashes,
            policy_hash=self.metadata.policy_hash if model_used else None,
            theory_hash=theory_hash(accepted_theory) if accepted_theory is not None else None,
            proof_verified=proof_verified,
            provider_dispatches=self.dispatch_count(),
            cache_hits=accounting.cache_hits,
            cache_misses=accounting.cache_misses,
        )

    @staticmethod
    def _check_cancel(cancelled: Callable[[], bool]) -> None:
        if cancelled():
            raise PipelineCancelled()

    @staticmethod
    def _parser_error(stage: StageName, execution: ParseExecution) -> OrchestrationError:
        code = execution.outcome.error_type or execution.outcome.status.value
        return OrchestrationError(
            stage,
            _safe_code(code),
            "The local semantic parser returned a typed terminal failure.",
        )

    @staticmethod
    def _accepted(policy: PolicyMode, decision: ComponentDecision) -> bool:
        if policy is PolicyMode.P1_CORRECTED:
            return decision.deterministic_accepted
        return decision.selective_accepted

    @staticmethod
    def _terminal_decision_error(decision: ComponentDecision) -> OrchestrationError | None:
        if not decision.error_type:
            return None
        failed_task = next(
            (
                item
                for item in reversed(decision.task_outcomes)
                if item.status is not TaskStatus.SUCCESS
            ),
            None,
        )
        stage = (
            StageName.CORRECTION
            if failed_task is not None
            and failed_task.task_kind in {TaskKind.CORRECTION_THEORY, TaskKind.CORRECTION_QUERY}
            else StageName.CRITIC
        )
        return OrchestrationError(
            stage,
            _safe_code(decision.error_type),
            "A Phase 6 neural task reached a typed terminal error.",
        )

    @staticmethod
    def _record_validation(trace: TraceCollector, value: TheoryValidation) -> None:
        coverage_codes = {
            FeedbackIssueCode.MISSING_SOURCE,
            FeedbackIssueCode.DUPLICATE_SOURCE,
            FeedbackIssueCode.UNKNOWN_SOURCE,
            FeedbackIssueCode.INVENTED_SOURCE,
            FeedbackIssueCode.FACT_RULE_CONFUSION,
        }
        coverage_failed = any(item.issue_code in coverage_codes for item in value.feedback.issues)
        trace.set(
            StageName.SOURCE_COVERAGE,
            StageStatus.FAILED if coverage_failed else StageStatus.SUCCEEDED,
        )
        trace.set(
            StageName.SEMANTIC_VALIDATION,
            StageStatus.SUCCEEDED if value.valid else StageStatus.FAILED,
        )

    @staticmethod
    def _record_query_validation(trace: TraceCollector, value: QueryValidation) -> None:
        if value.valid:
            trace.set(StageName.SEMANTIC_VALIDATION, StageStatus.SUCCEEDED)
        else:
            trace.set(StageName.SEMANTIC_VALIDATION, StageStatus.FAILED)

    @staticmethod
    def _validation_error(value: TheoryValidation) -> OrchestrationError:
        coverage_codes = {
            FeedbackIssueCode.MISSING_SOURCE,
            FeedbackIssueCode.DUPLICATE_SOURCE,
            FeedbackIssueCode.UNKNOWN_SOURCE,
            FeedbackIssueCode.INVENTED_SOURCE,
            FeedbackIssueCode.FACT_RULE_CONFUSION,
        }
        stage = (
            StageName.SOURCE_COVERAGE
            if any(item.issue_code in coverage_codes for item in value.feedback.issues)
            else StageName.SEMANTIC_VALIDATION
        )
        code = (
            "SOURCE_COVERAGE_ERROR"
            if stage is StageName.SOURCE_COVERAGE
            else "SEMANTIC_VALIDATION_ERROR"
        )
        return OrchestrationError(
            stage, code, "The theory candidate failed deterministic validation."
        )

    @staticmethod
    def _query_validation_error(_value: QueryValidation) -> OrchestrationError:
        return OrchestrationError(
            StageName.SEMANTIC_VALIDATION,
            "SEMANTIC_VALIDATION_ERROR",
            "The query candidate failed deterministic validation.",
        )

    @staticmethod
    def _record_decision_stages(
        trace: TraceCollector,
        decision: ComponentDecision,
        *,
        merge: bool = False,
    ) -> None:
        critic_tasks = [
            item
            for item in decision.task_outcomes
            if item.task_kind in {TaskKind.CRITIC_THEORY, TaskKind.CRITIC_QUERY}
        ]
        correction_tasks = [
            item
            for item in decision.task_outcomes
            if item.task_kind in {TaskKind.CORRECTION_THEORY, TaskKind.CORRECTION_QUERY}
        ]
        _merge_task_stage(trace, StageName.CRITIC, critic_tasks, merge=merge)
        _merge_task_stage(trace, StageName.CORRECTION, correction_tasks, merge=merge)
        trace.set(StageName.SOURCE_COVERAGE, StageStatus.SUCCEEDED)
        trace.set(StageName.SEMANTIC_VALIDATION, StageStatus.SUCCEEDED)

    @staticmethod
    def _account_decision(accounting: _Accounting, decision: ComponentDecision) -> None:
        accounting.correction_attempted |= decision.correction_attempts > 0
        for task in decision.task_outcomes:
            accounting.cache(task.cache_hit)


def _merge_task_stage(
    trace: TraceCollector,
    stage: StageName,
    tasks: list,
    *,
    merge: bool,
) -> None:
    if not tasks:
        if not merge:
            trace.set(stage, StageStatus.SKIPPED)
        return
    failed = next((item for item in tasks if item.status is not TaskStatus.SUCCESS), None)
    status = StageStatus.FAILED if failed is not None else StageStatus.SUCCEEDED
    cache_values = {item.cache_hit for item in tasks}
    cache_status = (
        "hit" if cache_values == {True} else "miss" if cache_values == {False} else "mixed"
    )
    trace.set(
        stage,
        status,
        duration_ms=sum(item.duration_ms or 0 for item in tasks),
        cache_status=cache_status,
        error_code=failed.error_type if failed is not None else None,
    )


def _safe_code(value: str) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in value.upper())
    normalized = normalized.strip("_")[:128]
    return normalized or "PIPELINE_ERROR"
