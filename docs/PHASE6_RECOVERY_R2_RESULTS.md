# Phase 6 Recovery Replication v2 Results

## Final status

**Phase 6-R2: `BLOCKED`.**

The original Phase 6 pilot remains permanently `BLOCKED` and its historical report,
`docs/PHASE6_PILOT_RESULTS.md`, remains byte-for-byte unchanged. Phase 6-R2 was a fresh,
preregistered local replication, not a recovery of the missing original responses.

Phase 6-R2 stopped at the mandatory Phase 5-R2 cache-completeness gate. One frozen theory request
reached the unchanged 4,096-token generation limit twice without returning a schema-valid response.
The protocol forbids repeated prompting until a valid answer appears, and changing the output limit
would change a frozen behavior-affecting setting. No third request was made, Phase 6 inference did
not begin, and development labels or aggregate correctness metrics were not inspected.

## Checkpoints and frozen artifacts

- Starting checkpoint: `4270c83e2d5618939de9120bde307df966ce6ae3`
- Recovery branch: `phase/06r2-recovery-replication`
- Initial R2 freeze commit: `1f9c77abc4a05a2d5a3b9e6a48839677cf472aa4`
- R2.1 duplicate-cache amendment: `ab195a5d1d191e0989b2acf4f515eed59b235a54`
- Sanitized preflight error fix: `57d3973`
- Original blocked-report SHA-256:
  `16654dac532310773cac188e49f743edff56979b6e3c188bf59c55c7ce9dd7f7`
- R2 parser-config SHA-256:
  `602881bb988dddbdcd0e05150d67bb2eb221b884ded67615baa97856efc22300`
- R2 correction-config SHA-256:
  `dcda2223ce2fc7f48b59e40b719b2112110725b3c1729ec9bf263940306e13cb`
- R2.1 freeze-manifest SHA-256:
  `dd6db160bb2c23e266ab2751a129e7669db6c07d1a19be159fc692b25c8d8173`
- Frozen ordered-selection fingerprint:
  `784b01ff779fec5da534696a8f9c3d11b6c067f31568cba80466dc3442e00e98`
- Frozen request-manifest fingerprint:
  `40101985e37ec739205945db0b8ce98ffacec5bab7d8fc8dbc295e3d96327951`

All original Phase 5/6 prompt, schema, policy, model, and selection hashes matched the
preregistration before inference. R2 and original normalized configurations differed only in
approved operational identity and isolated cache/output fields.

## Local model contract

- Provider: Ollama `0.32.1` on IPv4 loopback
- Model: `qwen3.5:4b-q4_K_M`
- Digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`
- Execution: local CPU, concurrency one
- Context: 8,192 tokens
- Temperature: 0
- Seed: 20260713
- Thinking: disabled
- Theory output limit: 4,096 tokens
- API cost: `$0.00`
- Hosted inference calls: 0
- ProofWriter transmissions: 0

## Phase 5-R2 accounting

The frozen selection contains 58 logical parser components: 28 unique theories and 30 queries.
One query is an exact content-addressed duplicate, so the plan contains 57 unique request hashes.

| Item | Count |
|---|---:|
| Logical parser components | 58 |
| Unique request hashes required | 57 |
| Valid unique cache entries | 56 |
| Logical components replayable | 57 |
| Exact duplicate cache reuses | 1 |
| Missing unique cache entries | 1 |
| Successful local provider calls | 56 |
| Failed local provider calls for the missing request | 2 |
| Total local provider dispatches across preserved attempts | 58 |

The 56 valid immutable cache entries contain 37,744 input tokens, 28,134 output tokens, and
4,524,542.0534 ms of provider-reported duration. Ollama server logs independently show that each
failed request generated the full 4,096-token limit. The two failed attempts reported 940 and 1,008
prompt-evaluation tokens, 8,192 generated tokens in total, and 1,159,105.85 ms total server time.
These failure tokens and timings are reported separately because no valid parser response envelope
was produced; they were not fabricated into the response cache.

The terminal missing request hash is
`dc1e6278fc2d360bec7caba8d6d3459d26de3e1251a8683711faf93f498a23d9`.
Both executions ended as `STRUCTURED_OUTPUT_ERROR` /
`ParserStructuredOutputError`. The second server trace confirms 4,096 decoded tokens and a normal
local HTTP 200 response, so this was a model structured-output failure rather than a transport,
authentication, hosted-provider, or model-digest failure.

## Mandatory gate outcome

Required Phase 5-R2 cache-only evidence:

- logical cache hits: 58/58;
- inference calls: 0;
- cache misses: 0.

Observed attainable state:

- logical cache hits: 57/58;
- valid unique entries: 56/57;
- cache misses: 1.

The mandatory stop condition therefore applies. A third identical request would violate the
no-repeat-until-success rule. Raising `theory_num_predict`, altering the prompt/schema, substituting
a model, fabricating a terminal response, or treating the missing entry as `UNKNOWN` would each
violate the frozen protocol.

## P0/P1/P2, correction, abstention, AST, and proof results

No P0/P1/P2 prediction set was produced or sealed. Consequently:

- P0/P1/P2 accuracy, coverage, selective risk, macro metrics, and confusion matrices are
  unavailable;
- critic/correction yield and regression counts are unavailable;
- abstention totals are unavailable;
- parsing exact-match, AST, and closure metrics are unavailable;
- no Phase 6 proof was emitted or accepted;
- no development comparison or superiority claim is permitted.

These are unavailable because the preregistered precondition failed, not because zero values were
observed.

## Verification performed

- Starting branch/checkpoint, clean tree, original report hash, and all frozen hashes: passed.
- Exact dataset archive and frozen 30-example development selection: passed.
- Exact Ollama version, model tag/digest, loopback endpoint, and CPU runtime: passed.
- R2 cache/output namespace isolation: passed.
- Normalized original/R2 behavior comparison: passed.
- Preregistration before development inference: passed.
- R2.1 duplicate-request amendment before resumed inference: passed.
- Backend Ruff checks: passed.
- Backend full suite after orchestration changes: 289 tests passed with one upstream
  Starlette/httpx deprecation warning.
- Phase 5 cache-only replay: not run to completion because its precondition (58/58 logical entries)
  failed.
- Phase 6 live run, seal, evaluation, replay, regressions, frontend checks, and Docker validation:
  skipped after the mandatory stop condition.
- Test split access: none.
- Hosted CI: not triggered; no remote exists.

## Limitations and next action

Temperature zero and a fixed seed did not make local generation deterministic or guarantee schema
completion. ProofWriter's dataset licence remains unverified. This 30-example development
replication cannot support significance, state-of-the-art, or production claims.

Phase 6 is not complete, so Phase 7 must not begin. The next action is a separately authorized,
separately versioned protocol decision for handling terminal Phase 5 provider failures without
post-result selection. It must be frozen before any further development inference and cannot be
chosen based on preferred metrics.
