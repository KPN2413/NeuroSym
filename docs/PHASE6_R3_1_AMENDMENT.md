# Phase 6-R3.1 Terminal Error Hashing Amendment

## Why an amendment is required

The R3 protocol was frozen at commit `f207515f6fab96bd9f785a0c42c4926a64b872c2`.
Three theory-correction responses completed and were atomically cached. The next request's first
execution was interrupted by the command worker before an envelope was written. Its final permitted
execution returned a structured object, but three literals had arity/argument-count mismatches.

The terminal path correctly rejected that object. While creating its evidence hash, however,
`ValidationError.errors()` exposed `ValueError` objects inside Pydantic's context. The project's
canonical JSON encoder correctly refuses arbitrary Python objects, so terminal construction crashed
before writing an envelope.

This is a behavior-affecting implementation bug found after inference began. The R3 stop rule
therefore applies: preserve both incomplete runs, stop inference, preregister a correction, and
continue only after a new commit.

## Frozen correction

R3.1 makes exactly two changes:

1. Hash `ValidationError.json(include_url=false)`. Pydantic's JSON encoder deterministically
   stringifies exception context, so the evidence remains canonical and no arbitrary object reaches
   `canonical_json`.
2. Reconstruct the exact frozen request identity and materialize an
   `INVALID_STRUCTURED_OUTPUT` terminal outcome from the preserved interruption observation and
   stderr evidence. No provider call is permitted during materialization.
3. Represent token and timing accounting that was not persisted as `null`. This preserves the
   required fields while distinguishing unavailable evidence from observed zero-cost model work.

The schema change is a backward-compatible widening: already observed non-negative numbers remain
valid, while `null` is permitted only to express unavailable accounting. The original R3 schema
hash and the amended schema hash are both frozen in the amendment manifest.

The request hash is
`31b97fc053418bf0c44b8cac49cc0a51a05d21870789da082253fa5d35954be8`.
It has exhausted its two executions. A third execution is forbidden.

## What does not change

The dataset, ordered development examples, prompts, schemas, model, exact digest, runtime,
temperature, seed, context, token limits, correction limit, retry limits, P0/P1/P2 rules,
abstention policy, call budget, metrics, seal, and replay gates remain unchanged. No development
label, formal structure, prediction set, aggregate metric, or test record was inspected.

The three successful correction caches remain immutable and reusable. The incomplete run
directories and ignored logs remain preserved. Missing token and timing details for the interrupted
and pre-cache-crash executions are reported as unavailable, never as observed zero-cost model work.

## Acceptance

Before further inference, the regression test must pass, the full backend suite and Ruff checks must
pass, evidence hashes must match, the terminal materialization must make zero provider calls, and
cache-only lookup must return the typed error. The amendment must be committed separately before
the Phase 6 run resumes.
