from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from verilogic_ns_api.orchestration.models import (
    StageName,
    StageStatus,
    StageTrace,
)


class TraceCollector:
    def __init__(self) -> None:
        self._items = {
            stage: StageTrace(stage=stage, status=StageStatus.NOT_STARTED) for stage in StageName
        }

    def set(
        self,
        stage: StageName,
        status: StageStatus,
        *,
        duration_ms: float = 0,
        cache_status: str = "not_applicable",
        error_code: str | None = None,
        message: str | None = None,
    ) -> None:
        self._items[stage] = StageTrace(
            stage=stage,
            status=status,
            duration_ms=max(0, duration_ms),
            cache_status=cache_status,
            error_code=error_code,
            message=message,
        )

    @contextmanager
    def measure(self, stage: StageName, *, cache_status: str = "not_applicable") -> Iterator[None]:
        started = time.perf_counter()
        self.set(stage, StageStatus.RUNNING, cache_status=cache_status)
        try:
            yield
        except Exception:
            self.set(
                stage,
                StageStatus.FAILED,
                duration_ms=(time.perf_counter() - started) * 1000,
                cache_status=cache_status,
            )
            raise
        else:
            self.set(
                stage,
                StageStatus.SUCCEEDED,
                duration_ms=(time.perf_counter() - started) * 1000,
                cache_status=cache_status,
            )

    def finish_unstarted(self) -> None:
        for stage, item in tuple(self._items.items()):
            if item.status is StageStatus.NOT_STARTED:
                self.set(stage, StageStatus.SKIPPED)

    def as_tuple(self) -> tuple[StageTrace, ...]:
        return tuple(self._items[stage] for stage in StageName)
