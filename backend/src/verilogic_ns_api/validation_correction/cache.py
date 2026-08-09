from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from verilogic_ns_api.semantic_parsing.models import ParserResponse
from verilogic_ns_api.terminal_outcomes import (
    CachedOutcomeType,
    SuccessCacheEnvelope,
    TerminalCacheEnvelope,
    TerminalProviderOutcome,
)
from verilogic_ns_api.validation_correction.provider import CorrectionTaskRequest


class CorrectionCacheError(RuntimeError):
    pass


class CorrectionCacheContractMismatch(CorrectionCacheError):
    pass


class CorrectionCacheIncomplete(CorrectionCacheError):
    pass


class CorrectionCacheCorrupt(CorrectionCacheError):
    pass


@dataclass(frozen=True)
class CorrectionCacheLookup:
    outcome_type: CachedOutcomeType
    response: ParserResponse | None = None
    terminal_error: TerminalProviderOutcome | None = None


class CorrectionResponseCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, request: CorrectionTaskRequest) -> Path:
        namespace = request.namespace.replace(".", "-")
        return self.root / namespace / request.request_hash[:2] / f"{request.request_hash}.json"

    def load(self, request: CorrectionTaskRequest) -> ParserResponse | None:
        result = self.load_outcome(request)
        if result is None:
            return None
        if result.outcome_type is CachedOutcomeType.TERMINAL_ERROR:
            raise CorrectionCacheError("terminal correction outcome requires typed cache lookup")
        return result.response

    def load_outcome(self, request: CorrectionTaskRequest) -> CorrectionCacheLookup | None:
        path = self.path_for(request)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, AttributeError) as error:
            raise CorrectionCacheCorrupt("correction cache entry is corrupt") from error
        if not isinstance(envelope, dict):
            raise CorrectionCacheCorrupt("correction cache entry is not an object")
        if "request_identity" not in envelope:
            raise CorrectionCacheIncomplete("correction cache entry lacks request identity")
        if envelope.get("request_identity") != request.identity():
            raise CorrectionCacheContractMismatch("correction cache metadata mismatch")
        try:
            if envelope.get("outcome_type") == CachedOutcomeType.TERMINAL_ERROR:
                terminal_envelope = TerminalCacheEnvelope.model_validate(envelope)
                return CorrectionCacheLookup(
                    outcome_type=CachedOutcomeType.TERMINAL_ERROR,
                    terminal_error=terminal_envelope.terminal_error,
                )
            if "response" not in envelope:
                raise CorrectionCacheIncomplete("correction cache entry lacks a completed outcome")
            success = SuccessCacheEnvelope.model_validate(envelope)
        except CorrectionCacheIncomplete:
            raise
        except (ValueError, ValidationError, AttributeError) as error:
            raise CorrectionCacheCorrupt("correction cache entry is corrupt") from error
        return CorrectionCacheLookup(
            outcome_type=CachedOutcomeType.SUCCESS,
            response=success.response,
        )

    def store(self, request: CorrectionTaskRequest, response: ParserResponse) -> Path:
        if response.request_hash != request.request_hash:
            raise CorrectionCacheError("cannot cache a response for another request")
        path = self.path_for(request)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "schema_version": "1.0",
            "outcome_type": CachedOutcomeType.SUCCESS,
            "request_identity": request.identity(),
            "response": response.model_dump(mode="json"),
        }
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(
                    envelope, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return path

    def store_terminal(
        self,
        request: CorrectionTaskRequest,
        terminal_error: TerminalProviderOutcome,
    ) -> Path:
        if terminal_error.request_hash != request.request_hash:
            raise CorrectionCacheError("cannot cache a terminal outcome for another request")
        envelope = TerminalCacheEnvelope(
            request_identity=request.identity(),
            terminal_error=terminal_error,
        )
        return _atomic_envelope(self.path_for(request), envelope.model_dump(mode="json"))


def _atomic_envelope(path: Path, envelope: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(envelope, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path
