from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verilogic_ns_api.baselines.configuration import file_sha256
from verilogic_ns_api.reasoning.models import sha256_payload
from verilogic_ns_api.research.models import (
    BenchmarkExample,
    ExampleProvenance,
    GoldLabel,
    SourceStatement,
    Split,
    WorldAssumption,
)
from verilogic_ns_api.semantic_parsing import cli as parser_cli
from verilogic_ns_api.semantic_parsing.configuration import load_parser_config
from verilogic_ns_api.semantic_parsing.models import (
    ParserKind,
    ParserOutcome,
    ParserStatus,
)
from verilogic_ns_api.semantic_parsing.precompute import (
    ParserPrecomputeError,
    precompute_parser_cache,
)
from verilogic_ns_api.validation_correction.configuration import load_correction_config
from verilogic_ns_api.validation_correction.recovery_r2 import (
    RecoveryR2Error,
    assert_recovery_config_equivalent,
    compare_recovery_replay,
)

ROOT = Path(__file__).resolve().parents[2]


def test_r2_configs_change_only_operational_identity() -> None:
    original_parser = load_parser_config(
        ROOT / "experiments/configs/ollama-semantic-parser-pilot.yaml"
    )
    r2_parser = load_parser_config(
        ROOT / "experiments/configs/ollama-semantic-parser-phase6-r2.yaml"
    )
    original_correction = load_correction_config(
        ROOT / "experiments/configs/ollama-validation-correction-pilot.yaml"
    )
    r2_correction = load_correction_config(
        ROOT / "experiments/configs/ollama-validation-correction-phase6-r2.yaml"
    )
    assert_recovery_config_equivalent(
        original_parser,
        r2_parser,
        original_correction,
        r2_correction,
    )
    assert r2_parser.cache_directory == "results/cache/semantic-parser-phase6-r2"
    assert r2_correction.cache_directory == "results/cache/validation-correction-phase6-r2"
    assert (
        file_sha256(ROOT / "experiments/configs/ollama-semantic-parser-phase6-r2.yaml")
        == r2_correction.phase5_config_sha256
    )


def test_r2_config_comparison_rejects_behavior_change() -> None:
    parser = load_parser_config(ROOT / "experiments/configs/ollama-semantic-parser-pilot.yaml")
    correction = load_correction_config(
        ROOT / "experiments/configs/ollama-validation-correction-pilot.yaml"
    )
    changed = parser.model_copy(
        update={"runtime": parser.runtime.model_copy(update={"seed": parser.runtime.seed + 1})}
    )
    with pytest.raises(RecoveryR2Error, match="behavioral parser"):
        assert_recovery_config_equivalent(parser, changed, correction, correction)


def test_original_blocked_artifacts_remain_immutable() -> None:
    assert (
        file_sha256(ROOT / "docs/PHASE6_PILOT_RESULTS.md")
        == "16654dac532310773cac188e49f743edff56979b6e3c188bf59c55c7ce9dd7f7"
    )
    assert (
        file_sha256(ROOT / "experiments/configs/ollama-semantic-parser-pilot.yaml")
        == "30e20a37f602dbbb259696a57d715b9d2cf43e57a1b7ab95d28dda7c036808e3"
    )
    assert (
        file_sha256(ROOT / "experiments/configs/ollama-validation-correction-pilot.yaml")
        == "c2cfea0ab428518d12cb3d9adc4bc355e5a45c09affff7a1af04b07ca748a606"
    )


def test_gold_free_parser_precompute_and_cache_replay(tmp_path: Path) -> None:
    examples = _examples()
    cache = tmp_path / "cache"
    live = FakeParser(cache, cache_hits=False)
    live_report = precompute_parser_cache(
        examples=examples,
        parser=live,
        output_directory=tmp_path / "live",
        run_id="live",
    )
    assert live_report["logical_components"] == 58
    assert live_report["unique_request_hashes"] == 57
    assert live_report["duplicate_cache_reuses"] == 1
    assert live_report["new_local_calls"] == 57
    assert live_report["cache_entries_available"] == 58
    assert live_report["gold_fields_accessed"] is False

    replay = FakeParser(cache, cache_hits=True)
    replay_report = precompute_parser_cache(
        examples=examples,
        parser=replay,
        output_directory=tmp_path / "replay",
        run_id="replay",
    )
    assert replay_report["cache_hits"] == 58
    assert replay_report["new_local_calls"] == 0
    assert replay_report["operation_fingerprint"] == live_report["operation_fingerprint"]


def test_recovery_replay_comparison_rejects_any_cache_miss(tmp_path: Path) -> None:
    live = tmp_path / "live"
    replay = tmp_path / "replay"
    live.mkdir()
    replay.mkdir()
    for directory in (live, replay):
        (directory / "prediction-seal.json").write_text(
            json.dumps({"seal_fingerprint": "a" * 64}), encoding="utf-8"
        )
        (directory / "report.json").write_text(
            json.dumps({"report_fingerprint": "b" * 64}), encoding="utf-8"
        )
    (live / "request-ledger.json").write_text(
        json.dumps({"summary": {"cache_misses": 0, "cache_hits": 2}}), encoding="utf-8"
    )
    (replay / "request-ledger.json").write_text(
        json.dumps({"summary": {"cache_misses": 0, "cache_hits": 2}}), encoding="utf-8"
    )
    replay_seal = {"seal_fingerprint": "a" * 64, "new_local_calls_this_invocation": 0}
    (replay / "prediction-seal.json").write_text(json.dumps(replay_seal), encoding="utf-8")
    assert compare_recovery_replay(live, replay)["passed"] is True

    (replay / "request-ledger.json").write_text(
        json.dumps({"summary": {"cache_misses": 1, "cache_hits": 1}}), encoding="utf-8"
    )
    with pytest.raises(RecoveryR2Error, match="replay differs"):
        compare_recovery_replay(live, replay)


def test_precompute_error_is_reported_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        parser_cli,
        "prepare_parser_experiment",
        lambda _path: (_ for _ in ()).throw(ParserPrecomputeError("cache incomplete")),
    )
    assert (
        parser_cli.main(
            [
                "cache",
                "--config",
                "synthetic.yaml",
                "--dataset",
                "pilot",
                "--run-id",
                "synthetic",
            ]
        )
        == 2
    )
    captured = capsys.readouterr()
    assert "semantic-parser error: cache incomplete" in captured.err
    assert "Traceback" not in captured.err


class FakeParser:
    def __init__(self, cache: Path, *, cache_hits: bool) -> None:
        self.cache = SimpleNamespace(root=cache)
        self.cache_hits = cache_hits

    def parse_theory(self, value):
        return self._parse(ParserKind.THEORY, value.input_hash)

    def parse_query(self, value):
        return self._parse(ParserKind.QUERY, value.input_hash)

    def _parse(self, kind: ParserKind, input_hash: str):
        request_hash = sha256_payload({"kind": kind.value, "input_hash": input_hash})
        target = self.cache.root / request_hash[:2] / f"{request_hash}.json"
        cache_hit = self.cache_hits or target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{}", encoding="utf-8")
        outcome = ParserOutcome(
            parser_kind=kind,
            input_hash=input_hash,
            request_hash=request_hash,
            status=ParserStatus.PARSED,
            cache_hit=cache_hit,
        )
        return SimpleNamespace(outcome=outcome, candidate=object())


def _examples() -> tuple[BenchmarkExample, ...]:
    examples = []
    for index in range(30):
        theory_index = min(index, 27)
        source = SourceStatement(
            source_id=f"triple{theory_index + 1}",
            text=f"Entity {theory_index} is blue.",
            kind="fact",
        )
        examples.append(
            BenchmarkExample(
                example_id=f"proofwriter/synthetic/Q{index + 1}",
                dataset_version="synthetic",
                variant="synthetic",
                split=Split.DEVELOPMENT,
                theory_id=f"theory-{theory_index}",
                question_id=f"Q{index + 1}",
                reasoning_depth=index % 6,
                source_statements=[source],
                context=source.text,
                query=f"Entity {min(index, 28)} is kind.",
                gold_label=GoldLabel.UNKNOWN,
                original_raw_label="Unknown",
                world_assumption=WorldAssumption.OPEN,
                source_relative_path="synthetic/dev.jsonl",
                provenance=ExampleProvenance(
                    loader_version="test",
                    record_line=index + 1,
                    record_sha256=f"{index + 1:064x}",
                    content_sha256=f"{index + 101:064x}",
                ),
            )
        )
    return tuple(examples)
