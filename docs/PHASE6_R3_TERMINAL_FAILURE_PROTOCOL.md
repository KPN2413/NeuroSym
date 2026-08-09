# Phase 6-R3 Terminal-Failure Protocol

## Status and purpose

This protocol is frozen before any new Phase 6 inference. The original Phase 6 experiment and
Phase 6-R2 remain `BLOCKED`; their reports, manifests, caches, and attempt evidence are historical
records and are not rewritten.

R2 stopped correctly because its preregistered gate required every Phase 5 parser request to have a
structured response. One theory request exhausted the unchanged 4,096-token limit on both permitted
attempts. R3 asks a different engineering question: can the complete batch finish safely when an
exhausted neural request is represented as a typed, replayable `ERROR`?

R3 does not recover the missing AST. It does not make a third Phase 5 attempt, raise the output
limit, alter a prompt, change a threshold, or substitute a model.

## Verified inventory decision

Machine validation found 56 preserved R2 provider-response envelopes. Of those, 55 validate against
their frozen theory/query schemas. One query envelope is valid provider evidence but its payload
fails `CandidateQueryOutput`; it cannot honestly be called a structured success. Along with the
missing exhausted theory request, R3 therefore freezes this accurate inventory:

- 55 unique schema-valid `SUCCESS` outcomes;
- two unique `TERMINAL_ERROR` outcomes;
- 57 unique completed outcomes;
- 58 logical components because one query request is reused exactly.

This differs from the anticipated 56/1 split in the implementation request. The implementation
request explicitly requires investigation rather than changing evidence to force expected counts.

## Terminal outcome

`schemas/terminal-provider-outcome.v1.schema.json` defines the external contract, while the strict
Pydantic model enforces cross-field provenance and canonical hashing. Each terminal record includes
the request, prompt, schema, semantic configuration, provider, exact model digest, runtime,
permitted and observed attempts, token limit, per-attempt evidence hashes, token/timing totals,
timestamps, finality, and a canonical SHA-256.

The exhausted theory is `OUTPUT_LIMIT_EXHAUSTED`; the preserved invalid query response is
`INVALID_STRUCTURED_OUTPUT`. Both remain pipeline-facing `STRUCTURED_OUTPUT_ERROR`.

A terminal result differs from a cache miss: it proves that a frozen request has a final measured
failure under its permitted budget. It blocks further provider dispatch for that request and can be
replayed without Ollama. It is never an AST, `UNKNOWN`, `ABSTAIN`, or a fabricated prediction.

## R2 reuse

The R2 parser cache is read-only. Each schema-valid envelope is checked against its cache key,
request identity, prompt, schema, model, digest, runtime, and structured-output model, then copied
byte-for-byte to `results/cache/semantic-parser-phase6-r3/`. Destination hashes must match source
hashes. Invalid or missing responses are represented only by new R3 terminal envelopes with
preserved evidence hashes. Raw ProofWriter records and response caches remain ignored.

## P0, P1, and P2

- P0 sends only valid theory/query pairs to deterministic Phase 4 reasoning. A terminal component
  produces typed `ERROR`; other records continue.
- P1 uses the unchanged validation/correction policy. Its existing structured-output validation
  path makes an absent/invalid candidate eligible for at most one semantic correction. This does
  not permit another Phase 5 parser attempt. A terminal Phase 6 correction or critic remains
  `ERROR`.
- P2 applies the unchanged mandatory-evidence gates only to produced candidates. It never converts
  `ERROR` to `ABSTAIN` or `UNKNOWN`.

Only accepted AST pairs enter the symbolic engine. Every emitted proof must pass the independent
verifier.

## Frozen execution contract

- Dataset: ProofWriter V2020.12.3, OWA depth-5, the same ordered 30-example development sample.
- Test split: forbidden.
- Provider: local Ollama `0.32.1` at IPv4 loopback only.
- Model: `qwen3.5:4b-q4_K_M`.
- Digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
- Runtime: CPU, context 8,192, temperature 0, seed 20260713, thinking disabled,
  concurrency one.
- Phase 5 theory output limit: unchanged at 4,096.
- Provider attempts: at most two per new Phase 6 task.
- Semantic corrections: at most one per component.
- Maximum new Phase 6 unique tasks: 180.
- Hosted calls, transmissions, and API cost: zero.

No behavior may be tuned after development metrics are visible. Temperature zero and a fixed seed
do not remove local model nondeterminism. ProofWriter's licence remains unverified, and 30
development examples do not support significance or superiority claims.

## Sealing, metrics, and replay

All 30 P0/P1/P2 outcomes, component decisions, request outcomes, proof references, and verification
states are hashed and sealed before evaluation reads development labels or formal structures.
Errors remain in overall denominators, reduce coverage, and are excluded from answered-only
accuracy.

The final replay runs with Ollama unavailable. It must have zero cache misses, calls, and new tokens
and must reproduce prediction, decision, error, proof, and report fingerprints. Completion means
every record has a sealed state; it does not mean every neural request succeeded.

## Acceptance

R3 passes only if all 58 logical Phase 5 components resolve to validated success or terminal
outcomes, no Phase 5 call is made, all 30 records receive sealed P0/P1/P2 states, all correction and
call limits hold, all accepted proofs verify, the final zero-call replay matches, historical hashes
remain intact, required tests/regressions pass, and no hosted service or test record is used.

There is no minimum accuracy, correction yield, or coverage requirement. A poor measured result can
be an engineering pass.
