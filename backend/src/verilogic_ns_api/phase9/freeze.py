from __future__ import annotations

import hashlib
import json
from pathlib import Path

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase9.models import Phase9FreezeManifest
from verilogic_ns_api.reasoning.models import sha256_payload


class Phase9FreezeError(ValueError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def expected_freeze_hash(manifest: Phase9FreezeManifest) -> str:
    payload = manifest.model_dump(mode="json")
    payload.pop("freeze_hash")
    return sha256_payload(payload)


def load_and_validate_freeze(path: Path) -> Phase9FreezeManifest:
    root = repository_root(path)
    manifest = Phase9FreezeManifest.model_validate_json(path.read_text(encoding="utf-8"))
    if expected_freeze_hash(manifest) != manifest.freeze_hash:
        raise Phase9FreezeError("Phase 9 freeze hash mismatch")
    for artifact in manifest.artifacts:
        target = (root / artifact.path).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise Phase9FreezeError(f"frozen artifact is unavailable: {artifact.artifact_id}")
        if file_sha256(target) != artifact.sha256:
            raise Phase9FreezeError(f"frozen artifact hash mismatch: {artifact.artifact_id}")
    return manifest


def canonical_json_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
