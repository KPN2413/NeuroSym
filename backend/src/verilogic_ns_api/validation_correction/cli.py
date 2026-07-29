from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from verilogic_ns_api.baselines.configuration import resolve_repository_path
from verilogic_ns_api.validation_correction.cache import CorrectionResponseCache
from verilogic_ns_api.validation_correction.configuration import prepare_correction_experiment
from verilogic_ns_api.validation_correction.evaluation import run_correction_evaluation
from verilogic_ns_api.validation_correction.planning import build_correction_plan
from verilogic_ns_api.validation_correction.provider import OllamaCorrectionProvider
from verilogic_ns_api.validation_correction.raw import Phase5CacheMissError
from verilogic_ns_api.validation_correction.recovery_r2 import (
    RecoveryR2Error,
    compare_recovery_replay,
    evaluate_sealed_recovery,
    prepare_recovery_r2,
    recovery_freeze_facts,
    seal_recovery_predictions,
)
from verilogic_ns_api.validation_correction.recovery_r3 import (
    RecoveryR3Error,
    materialize_r3_phase5,
    prepare_recovery_r3,
    r3_freeze_facts,
)
from verilogic_ns_api.validation_correction.service import CorrectionTaskService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local validation-guided correction and selective abstention"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "calibrate", "run", "replay"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        if name != "plan":
            command.add_argument("--run-id")
            command.add_argument(
                "--resume",
                action="store_true",
                help="reuse immutable request caches after an interrupted earlier run",
            )
    inspect = subparsers.add_parser("inspect-trace")
    inspect.add_argument("--run", type=Path, required=True)
    compare = subparsers.add_parser("compare")
    compare.add_argument("--run", type=Path, required=True)
    r2_freeze = subparsers.add_parser("r2-freeze-facts")
    r2_freeze.add_argument("--config", type=Path, required=True)
    for name in ("r2-run", "r2-replay"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--run-id", required=True)
    r2_evaluate = subparsers.add_parser("r2-evaluate")
    r2_evaluate.add_argument("--config", type=Path, required=True)
    r2_evaluate.add_argument("--run", type=Path, required=True)
    r2_compare = subparsers.add_parser("r2-compare")
    r2_compare.add_argument("--live", type=Path, required=True)
    r2_compare.add_argument("--replay", type=Path, required=True)
    r3_materialize = subparsers.add_parser("r3-materialize")
    r3_materialize.add_argument("--config", type=Path, required=True)
    r3_freeze = subparsers.add_parser("r3-freeze-facts")
    r3_freeze.add_argument("--config", type=Path, required=True)
    for name in ("r3-run", "r3-replay"):
        command = subparsers.add_parser(name)
        command.add_argument("--config", type=Path, required=True)
        command.add_argument("--run-id", required=True)
    r3_evaluate = subparsers.add_parser("r3-evaluate")
    r3_evaluate.add_argument("--config", type=Path, required=True)
    r3_evaluate.add_argument("--run", type=Path, required=True)
    r3_compare = subparsers.add_parser("r3-compare")
    r3_compare.add_argument("--live", type=Path, required=True)
    r3_compare.add_argument("--replay", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"inspect-trace", "compare"}:
            name = "controller-traces.json" if args.command == "inspect-trace" else "report.json"
            path = args.run / name
            if not path.is_file():
                raise ValueError(f"completed {name} is unavailable")
            payload = json.loads(path.read_text(encoding="utf-8"))
            if args.command == "compare":
                payload = {
                    "comparison_table": payload["comparison_table"],
                    "correction_ablation": payload["correction_ablation"],
                }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if args.command in {"r2-compare", "r3-compare"}:
            print(
                json.dumps(
                    compare_recovery_replay(args.live, args.replay),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "r3-freeze-facts":
            print(
                json.dumps(
                    r3_freeze_facts(prepare_recovery_r3(args.config, verify_freeze=False)),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "r3-materialize":
            print(
                json.dumps(
                    materialize_r3_phase5(prepare_recovery_r3(args.config)),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "r2-freeze-facts":
            print(
                json.dumps(
                    recovery_freeze_facts(prepare_recovery_r2(args.config)),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command in {"r2-evaluate", "r3-evaluate"}:
            r3 = args.command == "r3-evaluate"
            print(
                json.dumps(
                    evaluate_sealed_recovery(
                        prepared=(
                            prepare_recovery_r3(args.config)
                            if r3
                            else prepare_recovery_r2(args.config)
                        ),
                        output_directory=args.run,
                        experiment_version="r3" if r3 else "r2",
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command in {"r2-run", "r2-replay", "r3-run", "r3-replay"}:
            r3 = args.command.startswith("r3-")
            prepared = prepare_recovery_r3(args.config) if r3 else prepare_recovery_r2(args.config)
            replay = args.command.endswith("-replay")
            provider = None if replay else OllamaCorrectionProvider(prepared.config.runtime)
            service = CorrectionTaskService(
                config=prepared.config,
                prompts=prepared.prompts,
                cache=CorrectionResponseCache(
                    resolve_repository_path(prepared.root, prepared.config.cache_directory)
                ),
                provider=provider,
                replay_only=replay,
            )
            output_directory = (
                resolve_repository_path(prepared.root, prepared.config.output_directory)
                / args.run_id
            )
            try:
                seal_recovery_predictions(
                    prepared=prepared,
                    service=service,
                    output_directory=output_directory,
                    run_id=args.run_id,
                    experiment_version="r3" if r3 else "r2",
                )
                report = evaluate_sealed_recovery(
                    prepared=prepared,
                    output_directory=output_directory,
                    experiment_version="r3" if r3 else "r2",
                )
            finally:
                if provider is not None:
                    provider.close()
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0
        prepared = prepare_correction_experiment(args.config)
        if args.command == "plan":
            print(json.dumps(build_correction_plan(prepared), indent=2, sort_keys=True))
            return 0
        replay = args.command == "replay"
        calibration = args.command == "calibrate"
        provider = None if replay else OllamaCorrectionProvider(prepared.config.runtime)
        cache = CorrectionResponseCache(
            resolve_repository_path(prepared.root, prepared.config.cache_directory)
        )
        service = CorrectionTaskService(
            config=prepared.config,
            prompts=prepared.prompts,
            cache=cache,
            provider=provider,
            replay_only=replay,
        )
        dataset_name = "calibration" if calibration else "pilot"
        mode = "replay" if replay else "live"
        run_id = args.run_id or (
            f"phase6-{dataset_name}-{mode}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
        )
        if args.resume:
            run_id = f"{run_id}-resumed"
        output_root = resolve_repository_path(prepared.root, prepared.config.output_directory)
        try:
            report = run_correction_evaluation(
                prepared=prepared,
                service=service,
                output_directory=output_root / run_id,
                run_id=run_id,
                calibration=calibration,
            )
        finally:
            if provider is not None:
                provider.close()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (
        OSError,
        ValueError,
        ValidationError,
        Phase5CacheMissError,
        RecoveryR2Error,
        RecoveryR3Error,
    ) as error:
        print(f"validation-correction error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
