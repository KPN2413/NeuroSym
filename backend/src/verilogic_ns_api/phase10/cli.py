from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
from pydantic import ValidationError

from verilogic_ns_api.phase10.deliverables import validate_deliverables
from verilogic_ns_api.phase10.demo import run_demo_smoke, write_demo_report
from verilogic_ns_api.phase10.deployment import validate_deployment_contract
from verilogic_ns_api.phase10.evidence import FinalEvidenceError, write_final_evidence
from verilogic_ns_api.phase10.schema_export import export_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify the Phase 10 deployment and evidence-backed deliverables."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    evidence = commands.add_parser("export-evidence")
    evidence.add_argument("--check", action="store_true")
    schema = commands.add_parser("export-schema")
    schema.add_argument("--check", action="store_true")
    commands.add_parser("validate-deployment")
    commands.add_parser("validate-deliverables")
    smoke = commands.add_parser("demo-smoke")
    smoke.add_argument("--backend-origin", default="http://127.0.0.1:8000")
    smoke.add_argument("--frontend-origin", default="http://127.0.0.1:3000")
    smoke.add_argument("--timeout-seconds", type=float, default=10)
    smoke.add_argument("--output", type=Path, default=Path("results/phase10/demo-smoke.json"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "export-evidence":
            path = write_final_evidence(check=args.check)
            print(path.as_posix())
            return 0
        if args.command == "export-schema":
            path = export_schema(check=args.check)
            print(path.as_posix())
            return 0
        if args.command == "validate-deployment":
            checks = validate_deployment_contract()
            print(json.dumps({"status": "VERIFIED", "checks": checks}))
            return 0
        if args.command == "validate-deliverables":
            print(json.dumps(validate_deliverables(), indent=2, sort_keys=True))
            return 0
        report = run_demo_smoke(
            backend_origin=args.backend_origin,
            frontend_origin=args.frontend_origin,
            timeout_seconds=args.timeout_seconds,
        )
        write_demo_report(args.output, report)
        print(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return 0
    except (
        FinalEvidenceError,
        OSError,
        TimeoutError,
        ValidationError,
        ValueError,
        httpx.HTTPError,
    ) as error:
        print(f"phase10 error: {error}", file=sys.stderr)
        return 2
