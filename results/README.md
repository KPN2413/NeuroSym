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

The original interrupted Phase 5/6 cache namespaces remain incomplete historical evidence and must
not be synthesized or rewritten. The separately preregistered R3 experiment completed in isolated
`phase6-r3` namespaces using typed terminal outcomes. This does not retroactively complete or
change the original interrupted experiment.

Phase 6-R2 runtime evidence is isolated under
`results/cache/semantic-parser-phase6-r2/`,
`results/semantic-parsing-phase6-r2/`,
`results/cache/validation-correction-phase6-r2/`, and
`results/validation-correction-phase6-r2/`. The preserved local state contains 56 of 57 required
unique Phase 5 responses (57 of 58 logical components because one request is duplicated). One
theory request failed structured output twice at the frozen output limit. Keep these partial caches
and attempt ledgers; do not delete, synthesize the missing response, or write into the original
cache namespaces.

Phase 6-R3 evidence is isolated under
`results/cache/semantic-parser-phase6-r3/`,
`results/semantic-parsing-phase6-r3/`,
`results/cache/validation-correction-phase6-r3/`, and
`results/validation-correction-phase6-r3/`. The final replay directory is
`phase6-r3-replay-final-r5`: it records 67 logical cache hits over 64 unique Phase 6 outcomes,
seven typed terminal errors, zero misses/calls, and three unavailable telemetry records. These
ignored artifacts reproduce the sealed live predictions and report fingerprint; the sanitized
aggregate is committed in `docs/PHASE6_R3_RESULTS.md`.
