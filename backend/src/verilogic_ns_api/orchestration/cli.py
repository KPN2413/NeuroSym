from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from pydantic import ValidationError

from verilogic_ns_api.orchestration.factory import OrchestrationFactory
from verilogic_ns_api.orchestration.models import (
    InputMode,
    PipelineRequest,
    PolicyMode,
    ProviderMode,
)
from verilogic_ns_api.orchestration.schema_export import export_contracts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verilogic-orchestration",
        description="Run the local end-to-end VeriLogic-NS pipeline.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Run one versioned pipeline request")
    run.add_argument("--input", type=Path, help="Versioned request JSON")
    run.add_argument(
        "--statement",
        action="append",
        default=[],
        metavar="KIND:TEXT",
        help="Natural statement; KIND is fact or rule",
    )
    run.add_argument("--query", help="Natural-language query")
    run.add_argument("--formal-theory", type=Path, help="Phase 4 theory JSON")
    run.add_argument("--policy", choices=[item.value for item in PolicyMode])
    run.add_argument(
        "--provider-mode",
        choices=[item.value for item in ProviderMode],
        default=ProviderMode.CACHE_ONLY.value,
    )
    run.add_argument("--output", type=Path, help="Optional atomic JSON output")

    export = subparsers.add_parser("export-schemas", help="Export API schemas and types")
    export.add_argument("--check", action="store_true", help="Fail if generated files are stale")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export-schemas":
        try:
            paths = export_contracts(check=args.check)
        except RuntimeError as error:
            print(str(error), file=sys.stderr)
            return 2
        if paths:
            print(json.dumps([path.as_posix() for path in paths], indent=2))
        return 0
    try:
        request = _request(args)
        runtime = OrchestrationFactory(provider_mode=ProviderMode(args.provider_mode)).create_for(
            request
        )
        try:
            result = runtime.pipeline.run(request)
        finally:
            runtime.close()
        rendered = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
        if args.output is not None:
            _atomic_output(args.output, rendered)
        print(rendered, end="")
        return 0 if result.disposition.value != "ERROR" else 3
    except (OSError, ValueError, ValidationError) as error:
        print(f"Pipeline request rejected safely: {type(error).__name__}", file=sys.stderr)
        return 2


def _request(args: argparse.Namespace) -> PipelineRequest:
    selected = sum(
        (
            args.input is not None,
            bool(args.statement or args.query),
            args.formal_theory is not None,
        )
    )
    if selected != 1:
        raise ValueError("choose exactly one of --input, natural fields, or --formal-theory")
    if args.input is not None:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        if args.policy:
            payload["policy_mode"] = args.policy
        return PipelineRequest.model_validate(payload)
    policy = args.policy or PolicyMode.P2_SELECTIVE.value
    if args.formal_theory is not None:
        theory = json.loads(args.formal_theory.read_text(encoding="utf-8"))
        return PipelineRequest.model_validate(
            {
                "input_mode": InputMode.FORMAL_AST,
                "policy_mode": policy,
                "formal_ast": {"theory": theory, "query": theory.get("query")},
            }
        )
    if not args.statement or not args.query:
        raise ValueError("natural mode requires at least one --statement and --query")
    statements = []
    for index, raw in enumerate(args.statement, start=1):
        kind, separator, text = raw.partition(":")
        if not separator or kind not in {"fact", "rule"} or not text.strip():
            raise ValueError("each statement must use KIND:TEXT with fact or rule")
        statements.append({"source_id": f"source_{index}", "kind": kind, "text": text.strip()})
    return PipelineRequest.model_validate(
        {
            "input_mode": InputMode.NATURAL_LANGUAGE,
            "policy_mode": policy,
            "natural_language": {"statements": statements, "query": args.query},
        }
    )


def _atomic_output(path: Path, content: str) -> None:
    root = Path.cwd().resolve()
    target = path.resolve()
    if not target.is_relative_to(root):
        raise ValueError("output path must remain beneath the current working directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
