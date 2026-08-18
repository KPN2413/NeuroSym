from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pydantic import ValidationError

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase9.aggregate import build_aggregate, write_aggregate
from verilogic_ns_api.phase9.correction import run_phase9_correction
from verilogic_ns_api.phase9.freeze import Phase9FreezeError, load_and_validate_freeze
from verilogic_ns_api.phase9.oracle import run_oracle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 9 regenerated-evidence tooling")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-freeze")
    validate.add_argument("--manifest", type=Path, required=True)
    correction = commands.add_parser("run-correction")
    correction.add_argument("--freeze", type=Path, required=True)
    correction.add_argument("--config", type=Path, required=True)
    correction.add_argument("--output", type=Path, required=True)
    correction.add_argument("--run-id", required=True)
    correction.add_argument("--mode", choices=("live", "replay"), required=True)
    oracle = commands.add_parser("run-oracle")
    oracle.add_argument("--freeze", type=Path, required=True)
    oracle.add_argument("--archive", type=Path, required=True)
    oracle.add_argument("--selection-manifest", type=Path, required=True)
    oracle.add_argument("--output", type=Path, required=True)
    oracle.add_argument("--run-id", required=True)
    aggregate = commands.add_parser("aggregate")
    aggregate.add_argument("--freeze", type=Path, required=True)
    aggregate.add_argument("--archive", type=Path, required=True)
    aggregate.add_argument("--direct-run", type=Path, required=True)
    aggregate.add_argument("--few-shot-run", type=Path, required=True)
    aggregate.add_argument("--semantic-run", type=Path, required=True)
    aggregate.add_argument("--correction-run", type=Path, required=True)
    aggregate.add_argument("--oracle-run", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)
    aggregate.add_argument("--replay-verified", action="store_true")
    aggregate.add_argument("--check", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-freeze":
            freeze = load_and_validate_freeze(args.manifest)
            print(json.dumps({"status": "VERIFIED", "freeze_hash": freeze.freeze_hash}))
            return 0
        freeze = load_and_validate_freeze(args.freeze)
        root = repository_root(args.freeze)
        if args.command == "run-correction":
            report = run_phase9_correction(
                config_path=args.config,
                output_directory=args.output,
                run_id=args.run_id,
                replay=args.mode == "replay",
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        if args.command == "run-oracle":
            report = run_oracle(
                archive=args.archive,
                selection_manifest=args.selection_manifest,
                output_directory=args.output,
                run_id=args.run_id,
            )
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        report = build_aggregate(
            root=root,
            freeze=freeze,
            archive=args.archive,
            direct_run=args.direct_run,
            few_shot_run=args.few_shot_run,
            semantic_run=args.semantic_run,
            correction_run=args.correction_run,
            oracle_run=args.oracle_run,
            replay_verified=args.replay_verified,
        )
        write_aggregate(args.output, report, check=args.check)
        print(json.dumps({"status": "VERIFIED", "fingerprint": report.report_fingerprint}))
        return 0
    except (OSError, ValueError, ValidationError, Phase9FreezeError) as error:
        print(f"phase9 error: {error}", file=sys.stderr)
        return 2
