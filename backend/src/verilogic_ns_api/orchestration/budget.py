from __future__ import annotations

from threading import Lock
from typing import Generic, Protocol, TypeVar

from verilogic_ns_api.semantic_parsing.provider import ParserProviderError


class CompletesRequests(Protocol):
    def complete(self, request: object) -> object: ...


T = TypeVar("T", bound=CompletesRequests)


class DispatchLimitError(ParserProviderError):
    pass


class DispatchBudget:
    def __init__(self, limit: int = 12) -> None:
        if not 1 <= limit <= 12:
            raise ValueError("Phase 7 dispatch limit must be between one and twelve")
        self.limit = limit
        self._count = 0
        self._lock = Lock()

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def claim(self) -> None:
        with self._lock:
            if self._count >= self.limit:
                raise DispatchLimitError("Phase 7 local inference dispatch limit reached")
            self._count += 1


class BudgetedProvider(Generic[T]):
    def __init__(self, provider: T, budget: DispatchBudget) -> None:
        self.provider = provider
        self.budget = budget

    def complete(self, request: object) -> object:
        self.budget.claim()
        return self.provider.complete(request)

    def close(self) -> None:
        close = getattr(self.provider, "close", None)
        if callable(close):
            close()
