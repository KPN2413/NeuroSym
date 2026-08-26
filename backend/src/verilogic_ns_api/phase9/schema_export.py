from __future__ import annotations

import json
from pathlib import Path

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase9.models import Phase9AggregateReport

SCHEMA_PATH = Path("schemas/phase9-aggregate-report.v1.schema.json")


def export_aggregate_schema(
    *, root: Path | None = None, output: Path | None = None, check: bool = False
) -> Path:
    resolved = repository_root(root or Path.cwd())
    target = output or (resolved / SCHEMA_PATH)
    if not target.is_absolute():
        target = resolved / target
    target = target.resolve()
    if not target.is_relative_to(resolved):
        raise ValueError("Phase 9 schema output must remain beneath the repository")
    rendered = (
        json.dumps(
            Phase9AggregateReport.model_json_schema(),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    )
    if check:
        if not target.is_file() or target.read_text(encoding="utf-8") != rendered:
            raise ValueError("tracked Phase 9 aggregate schema is stale")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered, encoding="utf-8", newline="\n")
    return target
