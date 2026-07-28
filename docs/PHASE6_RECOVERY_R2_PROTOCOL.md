# Phase 6 Recovery Replication v2 Protocol

## Research status

The original Phase 6 development pilot remains permanently `BLOCKED` because its ignored Phase 5
and interrupted Phase 6 response caches could not be recovered. Its report at
`docs/PHASE6_PILOT_RESULTS.md` is historical and read-only.

Phase 6 Recovery Replication v2 (Phase 6-R2) is a fresh local replication. It does not recover,
reconstruct, replace, or claim identity with the missing responses. Local inference can vary even
with temperature zero and a fixed seed, so P0-R2 is measured independently and need not reproduce
historical Phase 5 P0.

## Frozen intervention

The preregistration is `experiments/manifests/phase6-recovery-r2-freeze.v1.json`. It freezes:

- the original 30-example OWA development selection in its original order;
- unchanged Phase 5 theory/query prompts and structured-output schemas;
- unchanged Phase 6 critic/correction prompts, validators, one-attempt bound, and P0/P1/P2 policy;
- Ollama 0.32.1 on IPv4 loopback with `qwen3.5:4b-q4_K_M` at the exact recorded digest;
- temperature 0, seed 20260713, context 8192, thinking disabled, concurrency one;
- a maximum of 58 logical Phase 5 parser requests and 180 unique Phase 6 tasks;
- planned classification, parser, correction, critic, abstention, reasoning, proof, and operational
  metrics;
- no test-split access and no post-result tuning.

The R2 configs are normalized against the originals in automated tests. Only experiment name,
config reference/hash, cache path, and output path differ.

## Isolation and resumability

R2 writes only to ignored paths containing `phase6-r2`:

- `results/cache/semantic-parser-phase6-r2/`;
- `results/semantic-parsing-phase6-r2/`;
- `results/cache/validation-correction-phase6-r2/`;
- `results/validation-correction-phase6-r2/`.

No R2 code falls back to an original cache. Each provider response is atomically cached before the
next component. An interrupted invocation is resumed by using a new run ID with the same config;
valid content-addressed entries are reused and only missing requests are dispatched. Incomplete run
directories remain preserved. Cumulative request ledgers distinguish logical requests, unique
requests, live calls, cache hits, critic/correction tasks, tokens, and inference time.

Safe Phase 5 resume:

```text
python -m verilogic_ns_api.semantic_parsing cache --config experiments/configs/ollama-semantic-parser-phase6-r2.yaml --dataset pilot --run-id <new-id>
```

Safe Phase 6 resume:

```text
python -m verilogic_ns_api.validation_correction r2-run --config experiments/configs/ollama-validation-correction-phase6-r2.yaml --run-id <new-id>
```

## Leakage and sealing

Phase 5 precomputation renders only neutral theory/query views and never loads formal references or
computes metrics. Phase 6 controller decisions use the same gold-free views. Once all 30 P0/P1/P2
states exist, ordered predictions, decisions, request references, and audit records are written
atomically and hashed into `prediction-seal.json`.

Only after the seal verifies may the evaluation layer access development labels and formal ASTs.
Individual records cannot be rerun after metrics are observed. A behavior-affecting defect after
freeze invalidates the attempt and requires a separately frozen follow-up protocol.

## Replay and acceptance

Phase 5 must first replay with 58/58 logical cache hits and zero inference. After the live Phase 6-R2
run, Ollama is stopped and the complete R2 workflow is replayed with no provider object. Completion
requires:

- all 30 P0/P1/P2 states sealed;
- at most one correction per theory and query and no more than 180 unique Phase 6 tasks;
- every accepted answer produced by Phase 4 and every emitted proof independently verified;
- zero Phase 5/6 replay cache misses and zero replay inference calls;
- matching live/replay prediction seals and metric fingerprints;
- passing backend, frontend, reasoning, security, and repository checks;
- zero hosted calls, external transmissions, and API cost.

There is no minimum accuracy gate. Negative results are retained. The 30-example development
replication supports no significance, superiority, state-of-the-art, or production-readiness claim.
ProofWriter's dataset licence remains unverified.
