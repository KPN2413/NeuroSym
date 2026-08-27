from __future__ import annotations

import json
from pathlib import Path

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase10.models import FinalEvidencePackage

SCHEMA_PATH = Path("schemas/phase10-final-evidence.v1.schema.json")


def export_schema(root: Path | None = None, *, check: bool = False) -> Path:
    resolved = repository_root(root or Path.cwd())
    target = resolved / SCHEMA_PATH
    content = json.dumps(FinalEvidencePackage.model_json_schema(), indent=2, sort_keys=True) + "\n"
    if check:
        if not target.is_file() or target.read_text(encoding="utf-8") != content:
            raise ValueError("Phase 10 final-evidence schema is stale")
        return target
    target.write_text(content, encoding="utf-8", newline="\n")
    return target
