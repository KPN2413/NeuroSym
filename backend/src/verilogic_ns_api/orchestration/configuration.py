from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from verilogic_ns_api.baselines.configuration import file_sha256, repository_root
from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.semantic_parsing.configuration import load_parser_config
from verilogic_ns_api.semantic_parsing.models import (
    CandidateQueryOutput,
    CandidateTheoryOutput,
    ParserExperimentConfig,
)
from verilogic_ns_api.semantic_parsing.prompts import PromptRegistry
from verilogic_ns_api.validation_correction.configuration import load_correction_config
from verilogic_ns_api.validation_correction.models import (
    CorrectionExperimentConfig,
    QueryCriticReport,
    TaskKind,
    TheoryCriticReport,
    ValidationFeedback,
)

PHASE5_CONFIG = Path("experiments/configs/ollama-semantic-parser-pilot.yaml")
PHASE6_CONFIG = Path("experiments/configs/ollama-validation-correction-pilot.yaml")
PHASE7_CACHE = Path("results/cache/orchestration-phase7")
PHASE7_OUTPUT = Path("results/orchestration/phase7-canaries")


@dataclass(frozen=True)
class FrozenOrchestrationConfig:
    root: Path
    parser_config: ParserExperimentConfig
    correction_config: CorrectionExperimentConfig
    theory_prompt: str
    query_prompt: str
    correction_prompts: dict[TaskKind, tuple[str, str]]
    prompt_hashes: dict[str, str]
    schema_hashes: dict[str, str]


def load_frozen_orchestration_config(start: Path | None = None) -> FrozenOrchestrationConfig:
    root = repository_root(start or Path.cwd())
    phase5_path = root / PHASE5_CONFIG
    phase6_path = root / PHASE6_CONFIG
    parser_config = load_parser_config(phase5_path)
    correction_config = load_correction_config(phase6_path)
    if correction_config.phase5_config != PHASE5_CONFIG.as_posix():
        raise ValueError("Phase 6 does not reference the frozen Phase 5 configuration")
    if correction_config.phase5_config_sha256 != file_sha256(phase5_path):
        raise ValueError("frozen Phase 5 configuration hash mismatch")
    if correction_config.runtime != parser_config.runtime:
        raise ValueError("Phase 5 and Phase 6 runtime configurations differ")

    registry = PromptRegistry(root)
    theory_prompt, theory_hash = registry.load(parser_config.theory_prompt)
    query_prompt, query_hash = registry.load(parser_config.query_prompt)
    if theory_hash != parser_config.theory_prompt_sha256:
        raise ValueError("frozen theory prompt hash mismatch")
    if query_hash != parser_config.query_prompt_sha256:
        raise ValueError("frozen query prompt hash mismatch")

    prompt_specs = {
        TaskKind.CRITIC_THEORY: (
            correction_config.critic_theory_prompt,
            correction_config.critic_theory_prompt_sha256,
        ),
        TaskKind.CRITIC_QUERY: (
            correction_config.critic_query_prompt,
            correction_config.critic_query_prompt_sha256,
        ),
        TaskKind.CORRECTION_THEORY: (
            correction_config.correction_theory_prompt,
            correction_config.correction_theory_prompt_sha256,
        ),
        TaskKind.CORRECTION_QUERY: (
            correction_config.correction_query_prompt,
            correction_config.correction_query_prompt_sha256,
        ),
    }
    correction_prompts: dict[TaskKind, tuple[str, str]] = {}
    prompt_hashes = {"theory_parser": theory_hash, "query_parser": query_hash}
    for kind, (path, expected_hash) in prompt_specs.items():
        prompt, observed_hash = registry.load(path)
        if observed_hash != expected_hash:
            raise ValueError(f"frozen {kind.value} prompt hash mismatch")
        correction_prompts[kind] = (prompt, observed_hash)
        prompt_hashes[kind.value] = observed_hash

    schemas = {
        "theory_parser": CandidateTheoryOutput.model_json_schema(),
        "query_parser": CandidateQueryOutput.model_json_schema(),
        "validation_feedback": ValidationFeedback.model_json_schema(),
        "critic_theory": TheoryCriticReport.model_json_schema(),
        "critic_query": QueryCriticReport.model_json_schema(),
    }
    schema_hashes = {name: sha256_payload(schema) for name, schema in schemas.items()}
    if schema_hashes["theory_parser"] != parser_config.theory_schema_sha256:
        raise ValueError("frozen theory schema hash mismatch")
    if schema_hashes["query_parser"] != parser_config.query_schema_sha256:
        raise ValueError("frozen query schema hash mismatch")
    return FrozenOrchestrationConfig(
        root=root,
        parser_config=parser_config,
        correction_config=correction_config,
        theory_prompt=theory_prompt,
        query_prompt=query_prompt,
        correction_prompts=correction_prompts,
        prompt_hashes=dict(sorted(prompt_hashes.items())),
        schema_hashes=dict(sorted(schema_hashes.items())),
    )
