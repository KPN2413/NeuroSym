from __future__ import annotations

import secrets
import threading
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from verilogic_ns_api.orchestration.errors import (
    PipelineCancelled,
    QueueFullError,
    UnknownRunError,
)
from verilogic_ns_api.orchestration.factory import PipelineRuntime
from verilogic_ns_api.orchestration.models import (
    PipelineRequest,
    PipelineRunAccepted,
    PipelineRunState,
    RunStatus,
    StageName,
)


@dataclass
class _Job:
    run_id: str
    request: PipelineRequest
    submitted_at: datetime
    status: RunStatus = RunStatus.QUEUED
    current_stage: StageName | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: object | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


class InMemoryJobManager:
    """One-worker local job manager with bounded waiting and retention."""

    def __init__(
        self,
        runtime_factory: Callable[[PipelineRequest], PipelineRuntime],
        *,
        maximum_queued_jobs: int = 3,
        maximum_retained_jobs: int = 32,
        retention_seconds: int = 1_800,
    ) -> None:
        if not 1 <= maximum_queued_jobs <= 16:
            raise ValueError("maximum_queued_jobs must be between one and sixteen")
        if maximum_retained_jobs < maximum_queued_jobs + 1:
            raise ValueError("retention must exceed the active queue capacity")
        self.runtime_factory = runtime_factory
        self.maximum_queued_jobs = maximum_queued_jobs
        self.maximum_retained_jobs = maximum_retained_jobs
        self.retention = timedelta(seconds=retention_seconds)
        self._jobs: dict[str, _Job] = {}
        self._queue: deque[str] = deque()
        self._condition = threading.Condition()
        self._shutdown = False
        self._worker: threading.Thread | None = None

    def submit(self, request: PipelineRequest) -> PipelineRunAccepted:
        with self._condition:
            self._prune_locked()
            waiting = sum(self._jobs[run_id].status is RunStatus.QUEUED for run_id in self._queue)
            if waiting >= self.maximum_queued_jobs:
                raise QueueFullError("the local inference queue is full")
            run_id = secrets.token_urlsafe(18)
            job = _Job(run_id=run_id, request=request, submitted_at=datetime.now(UTC))
            self._jobs[run_id] = job
            self._queue.append(run_id)
            self._ensure_worker_locked()
            self._condition.notify()
            return PipelineRunAccepted(run_id=run_id, status=job.status)

    def get(self, run_id: str) -> PipelineRunState:
        with self._condition:
            self._prune_locked()
            job = self._jobs.get(run_id)
            if job is None:
                raise UnknownRunError(run_id)
            return _public_state(job)

    def cancel(self, run_id: str) -> PipelineRunState:
        with self._condition:
            self._prune_locked()
            job = self._jobs.get(run_id)
            if job is None:
                raise UnknownRunError(run_id)
            if job.status is RunStatus.QUEUED:
                job.status = RunStatus.CANCELLED
                job.completed_at = datetime.now(UTC)
                job.cancel_event.set()
            elif job.status is RunStatus.RUNNING:
                job.status = RunStatus.CANCEL_REQUESTED
                job.cancel_event.set()
            return _public_state(job)

    def shutdown(self, *, timeout_seconds: float = 5) -> None:
        with self._condition:
            self._shutdown = True
            for job in self._jobs.values():
                if job.status is RunStatus.QUEUED:
                    job.status = RunStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                elif job.status in {RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED}:
                    job.status = RunStatus.CANCEL_REQUESTED
                job.cancel_event.set()
            self._condition.notify_all()
            worker = self._worker
        if worker is not None:
            worker.join(timeout=timeout_seconds)

    def _ensure_worker_locked(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(
            target=self._work,
            name="verilogic-neurosymbolic-worker",
            daemon=True,
        )
        self._worker.start()

    def _work(self) -> None:
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._shutdown or bool(self._queue))
                if self._shutdown and not self._queue:
                    return
                run_id = self._queue.popleft()
                job = self._jobs.get(run_id)
                if job is None or job.status is RunStatus.CANCELLED:
                    continue
                job.status = RunStatus.RUNNING
                job.started_at = datetime.now(UTC)
            runtime: PipelineRuntime | None = None
            try:
                runtime = self.runtime_factory(job.request)
                result = runtime.pipeline.run(
                    job.request,
                    cancelled=job.cancel_event.is_set,
                    on_stage=lambda stage, current=job: self._stage(current, stage),
                )
            except PipelineCancelled:
                with self._condition:
                    job.status = RunStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                    job.result = None
            except Exception:
                with self._condition:
                    job.status = RunStatus.FAILED
                    job.completed_at = datetime.now(UTC)
                    job.result = None
            else:
                with self._condition:
                    if job.cancel_event.is_set():
                        job.status = RunStatus.CANCELLED
                        job.result = None
                    else:
                        job.status = RunStatus.COMPLETED
                        job.result = result
                    job.completed_at = datetime.now(UTC)
                    job.current_stage = StageName.FINAL_DECISION
            finally:
                if runtime is not None:
                    runtime.close()
                with self._condition:
                    self._prune_locked()

    def _stage(self, job: _Job, stage: StageName) -> None:
        with self._condition:
            job.current_stage = stage

    def _prune_locked(self) -> None:
        now = datetime.now(UTC)
        terminal = {
            RunStatus.COMPLETED,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        }
        expired = [
            run_id
            for run_id, job in self._jobs.items()
            if job.status in terminal
            and job.completed_at is not None
            and now - job.completed_at > self.retention
        ]
        for run_id in expired:
            self._jobs.pop(run_id, None)
        retained_terminal = sorted(
            (
                job
                for job in self._jobs.values()
                if job.status in terminal and job.completed_at is not None
            ),
            key=lambda item: item.completed_at or item.submitted_at,
        )
        excess = max(0, len(self._jobs) - self.maximum_retained_jobs)
        for job in retained_terminal[:excess]:
            self._jobs.pop(job.run_id, None)


def _public_state(job: _Job) -> PipelineRunState:
    from verilogic_ns_api.orchestration.models import PipelineResult

    return PipelineRunState(
        run_id=job.run_id,
        status=job.status,
        current_stage=job.current_stage,
        submitted_at=job.submitted_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        result=job.result if isinstance(job.result, PipelineResult) else None,
    )
