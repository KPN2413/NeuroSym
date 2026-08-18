from __future__ import annotations

from pathlib import Path

from verilogic_ns_api.baselines.configuration import resolve_repository_path
from verilogic_ns_api.validation_correction.cache import CorrectionResponseCache
from verilogic_ns_api.validation_correction.configuration import prepare_correction_experiment
from verilogic_ns_api.validation_correction.evaluation import run_correction_evaluation
from verilogic_ns_api.validation_correction.provider import OllamaCorrectionProvider
from verilogic_ns_api.validation_correction.service import CorrectionTaskService


def run_phase9_correction(
    *, config_path: Path, output_directory: Path, run_id: str, replay: bool
) -> dict[str, object]:
    prepared = prepare_correction_experiment(config_path)
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
    try:
        return run_correction_evaluation(
            prepared=prepared,
            service=service,
            output_directory=output_directory,
            run_id=run_id,
            calibration=False,
            enforce_historical_p0=False,
        )
    finally:
        if provider is not None:
            provider.close()
