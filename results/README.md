# Results

Generated experiment outputs are written beneath `results/runs/` and ignored by Git. Each Phase 2 run is first written to a unique `.incomplete` directory and promoted atomically only after predictions, metrics, and the final manifest are durable.

Phase 3 local Ollama payloads remain only in ignored `results/cache/ollama-responses/`
entries; the unexecuted OpenAI cache has its separate `results/cache/llm-responses/` root.
Rendered requests are reconstructed locally from frozen prompts and the ignored dataset. Synthetic
smoke, canary, aggregate, run, replay, and comparison evidence stays ignored. Cache references in
prediction rows are relative and contain no credential. Replay validates the full request identity
and has no inner provider, so it cannot make an inference call.

The repository contains no fabricated or placeholder measurements. Real local Phase 3 measurements
are retained only in the ignored results tree according to repository policy; no raw cache, model
weight, or record-level result is committed. Reproduce local checks with the commands in
`docs/LOCAL_LLM_BASELINE.md`. A local run requires the locally acquired ProofWriter archive and the
exact pinned Ollama model, but no paid-use flag, provider account, external-transfer approval, or API
key. Those explicit gates still apply to the optional, operationally unverified OpenAI path.

Phase 4 reasoning and ProofWriter conformance outputs are generated beneath
`results/reasoning/` and remain ignored. The balanced 300-example and frozen same-30 reports contain
aggregate oracle-structure results only; they are reproducible from the local archive and do not
measure natural-language parsing. Do not commit raw theories, record-level labels, proof payloads,
or dataset text from these runs.

Phase 5 parser responses are isolated under ignored `results/cache/semantic-parser/`; live,
calibration, and replay runs are under ignored `results/semantic-parsing/`. Replay constructs no
provider and must report all 58 pilot requests as cache hits with zero provider requests. The
sanitized aggregate is documented in `docs/PHASE5_PILOT_RESULTS.md`; raw candidate ASTs, source text,
per-record labels, local paths, and model output remain uncommitted.

Phase 6 uses separate ignored cache namespaces beneath
`results/cache/validation-correction/` for critic and correction responses. Train calibration,
development P0/P1/P2 runs, sanitized controller traces, comparisons, and replay outputs live under
ignored `results/validation-correction/`. Replay constructs no provider and must reproduce the same
non-timing fingerprint with zero local inference calls. No raw source text, candidate, critic output,
corrected AST, per-record label, absolute path, or model thinking is committed.
