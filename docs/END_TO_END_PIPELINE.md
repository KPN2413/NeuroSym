# End-to-End Neuro-Symbolic Pipeline

Phase 7 exposes one versioned orchestration boundary over the completed Phase 4-6 components. It
does not replace their contracts or let a model decide logical entailment.

## Inputs and policies

`PipelineRequest` version `1.0` supports two mutually exclusive modes:

- `FORMAL_AST`: accepts a validated Phase 4 theory and ground query. It never constructs an LLM
  provider, even when the service is configured for live local inference.
- `NATURAL_LANGUAGE`: accepts up to 32 typed fact/rule statements and one query. Missing source IDs
  are assigned deterministically before the gold-free Phase 5 parser boundary.

Natural-language requests select one frozen Phase 6 policy: `P0_RAW`, `P1_CORRECTED`, or
`P2_SELECTIVE`. P0 evaluates the raw parser candidate, P1 permits the bounded corrected-valid path,
and P2 additionally requires the critic/evidence gate. The same validated theory then crosses the
unchanged Phase 4 reasoner and independent proof verifier.

## Ordered stages

Every terminal result contains exactly these eleven stages:

1. input validation;
2. theory parsing;
3. query parsing;
4. source coverage;
5. semantic validation;
6. critic;
7. correction;
8. reliability policy;
9. symbolic reasoning;
10. proof verification;
11. final decision.

Formal input marks model-only stages as skipped. Natural input preserves the Phase 5/6 cache,
validation, correction, and policy outcomes. A failed provider or internal component remains
`ERROR`; a policy rejection remains `ABSTAINED`; neither is converted to logical `UNKNOWN`.

## Outcomes and evidence

`ANSWERED` requires one of `ENTAILED`, `CONTRADICTED`, `UNKNOWN`, or `INCONSISTENT`, a Phase 4 proof
DAG, and successful independent proof verification. Explanations are deterministic projections of
that verified proof and source provenance. Model prose and hidden reasoning are never accepted as
evidence.

`ABSTAINED` carries a typed reliability reason and no logical result. `ERROR` carries a sanitized
stage, code, and message and no logical result. Resource exhaustion is an error, not `UNKNOWN`.

## Execution controls

The API uses one worker and a bounded in-memory queue. Polling only reads state; it cannot dispatch
provider work. Completed jobs expire after the configured local retention period, and service
restart intentionally loses in-memory jobs. Natural local inference is loopback-only, digest-pinned,
`think: false`, concurrency one, and limited to twelve new provider dispatches per request. Formal
execution has a hard zero-provider invariant.

Phase 7 uses isolated ignored cache and result roots. Cache-only replay constructs no provider,
requires validated terminal entries, and fails closed on a miss. See `API_CONTRACT.md` and
`PHASE7_VERIFICATION.md` for the public interface and recorded acceptance evidence.
