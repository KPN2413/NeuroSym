from __future__ import annotations

from verilogic_ns_api.orchestration.models import StageName


class OrchestrationError(RuntimeError):
    def __init__(self, stage: StageName, code: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.safe_message = message[:500]


class PipelineCancelled(OrchestrationError):
    def __init__(self) -> None:
        super().__init__(StageName.FINAL_DECISION, "RUN_CANCELLED", "The run was cancelled.")


class QueueFullError(RuntimeError):
    pass


class UnknownRunError(KeyError):
    pass
