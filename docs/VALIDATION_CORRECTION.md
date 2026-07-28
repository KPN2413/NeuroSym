# Validation-Guided Correction

## Scope and frozen protocol

Phase 6 reuses the immutable Phase 5 raw semantic-parser cache. It does not regenerate raw parses.
Each theory and query is handled independently by a typed controller with these states:

```text
RAW -> VALIDATING -> CRITIQUING -> ACCEPTED
                      |              ^
                      v              |
               NEEDS_CORRECTION -> CORRECTING -> REVALIDATING -> FINAL_CRITIQUE
                                      |              |                 |
                                      +--------------+-----------------+-> ABSTAINED

Provider or verifier infrastructure failure -> ERROR
```

The exact transition depends on whether deterministic validation initially passes. At most one
meaning-changing correction is allowed per component. Exact-request transport retries do not count
as semantic corrections. Repeated candidates, invalid outputs, unresolved source coverage,
remaining semantic failures, critic rejection, and resource limits terminate without another loop.

The development pilot uses the same frozen 30 OWA development examples as Phases 3-5. Prompts,
schemas, model/runtime, train-only calibration manifest, correction limit, and reliability policy
are recorded in `experiments/manifests/phase6-freeze.v1.json` before the pilot. Test data is excluded.

## Interrupted-pilot recovery status

The committed controller is operational, but the development pilot cannot currently resume. The
workspace contains zero of the required Phase 5 semantic-parser cache entries and only one Phase 6
cache JSON. No incomplete Phase 6 run directory survives. The plan command therefore exits with a
typed, sanitized missing-cache error before any model request or metric inspection.

The original ignored `results/cache/semantic-parser/` directory must be restored with the exact 28
theory and 30 query responses used by Phase 5. The original
`results/cache/validation-correction/` critic/correction entries should also be restored so the
interrupted work is reused. These entries must come from backup or filesystem/version history;
regenerating Phase 5 responses would violate the frozen protocol. After restoration, plan must show
58 Phase 5 hits before run/resume is permitted.

## Typed feedback and critic

Deterministic feedback is versioned, canonically ordered, length-bounded, source-linked where
possible, and hash-addressed. It reports observable schema, source-coverage, and semantic-validation
failures without revealing the correct AST, answer, proof, depth, or oracle result.

The local neural critic receives only neutralized source text, its source map, and the candidate. It
returns `ACCEPT` or `REVISE` plus structured fidelity issues. It cannot correct the candidate and is
never asked for chain-of-thought. Correction requests contain the same gold-free source view, the
previous candidate, deterministic feedback, optional critic issues, and the strict replacement
schema. Model text is untrusted data and cannot execute code or invoke tools.

## Calibration and hypotheses

Prompt development used synthetic corruptions and six ProofWriter training records only. The
controlled corruption catalogue includes omission, duplication, invention, polarity, predicate,
constant, arity, fact/rule, premise, conclusion, unsafe-variable, and query errors. The completed
train-only local calibration recovered three semantic components from seven correction attempts but
also showed four regressions; the selective policy abstained on all six calibration examples. This
negative calibration evidence was retained. The development policy was frozen rather than relaxed
to manufacture coverage.

The pre-registered Phase 6 questions and hypotheses are in `RESEARCH_QUESTIONS.md`. No performance
threshold is an engineering acceptance criterion.

## Policies evaluated

- **P0 raw:** exact Phase 5 behavior and metrics, replayed from the Phase 5 cache.
- **P1 corrected-valid:** answer any corrected theory/query pair that passes deterministic validation and independent Phase 4 result verification; critic decisions are diagnostic.
- **P2 corrected-selective:** additionally require critic acceptance for both components. This is the operational Phase 6 policy.

P1 and P2 reuse identical candidates and model calls. Gold labels are introduced only after all
controller decisions are frozen. Aggregate results report correction recovery, post-hoc critic
quality, AST quality, accuracy, coverage, answered-only accuracy, selective risk, proof verification,
abstention reasons, tokens, local inference time, and cache use. The 30-example pilot supports no
significance claim.

Resume accounting separates new local calls in the completion invocation from reused cache hits and
deduplicates telemetry by request hash. It reports total unique pilot requests, critic requests,
correction requests, input/output tokens, and inference time across both the interrupted and
completion invocations. Gold-free trace envelopes retain controller/reliability decisions and
sanitized operation metadata without candidates, source text, gold data, or model thinking.

## Reproduction

From the activated backend environment:

```text
python -m verilogic_ns_api.validation_correction plan --config experiments/configs/ollama-validation-correction-pilot.yaml --dataset pilot
python -m verilogic_ns_api.validation_correction calibrate --config experiments/configs/ollama-validation-correction-pilot.yaml --run-id phase6-calibration-v1
python -m verilogic_ns_api.validation_correction run --config experiments/configs/ollama-validation-correction-pilot.yaml --run-id phase6-dev-pilot-v1
python -m verilogic_ns_api.validation_correction replay --config experiments/configs/ollama-validation-correction-pilot.yaml --run-id phase6-dev-pilot-v1-replay
```

Raw inputs, requests, model responses, traces, and record-level predictions remain ignored locally.
All inference is loopback-only through the digest-pinned Qwen model; API cost and hosted calls are
zero. ProofWriter's dataset licence remains unverified.

## Recovery Replication v2 outcome

Phase 6-R2 used isolated `phase6-r2` cache/result namespaces and froze its protocol before local
development inference. Of 57 unique Phase 5 request hashes, 56 produced valid immutable cache
entries. The remaining theory request reached the unchanged 4,096-token output limit on two
executions without valid structured output. The no-repeat rule and frozen runtime prevent another
attempt or a larger output limit. Phase 6-R2 therefore stopped at 57/58 logical replayable
components before controller execution, prediction sealing, or metric access. This provider
failure is an operational blocker, not an `ABSTAIN`, `UNKNOWN`, or reconstructed response.
