# Phase 9 Regenerated-Evidence Protocol

## Status and identity

This document preregisters **Phase 9 regenerated evidence under newly frozen protocol**. The
historical Phase 3, Phase 5, Phase 6, Phase 7 and Phase 8 caches are unavailable and are not being
restored, reconstructed or relabelled. Phase 9 creates a separate evidence namespace and preserves
all earlier claims unchanged.

No development metric may be inspected until the selection, prompts, schemas, model/runtime,
condition definitions and configuration hashes have been frozen in
`experiments/manifests/phase9-recovery-freeze.v1.json` and committed.

## Dataset and selection

- Dataset: ProofWriter V2020.12.3 from the project's recorded public source
  `https://aristo-data-public.s3.amazonaws.com/proofwriter/proofwriter-dataset-V2020.12.3.zip`.
- Integrity: the locally downloaded archive must equal the previously observed SHA-256
  `bbc5694901e8306d0bd659aa1ad53ccfd02c201864f4b320ffa3777827d1fc26`.
- World assumption and variant: OWA, `depth-5`.
- Evaluation split: development only. The test split is forbidden for selection, execution,
  tuning, reporting and troubleshooting.
- Evaluation sample: 30 records, with two records in every depth (0, 1, 2, 3, 5) by label
  (ENTAILED, CONTRADICTED, UNKNOWN) cell.
- Demonstrations: six training records, two per label, with one depth-0 and one depth-at-least-2
  record per label.
- Selection seed: `20260818`.
- Selection method: SHA-256 ordering over `seed:example_id`, using the existing Phase 3 selection
  implementation. IDs and normalized-content hashes must not overlap between train demonstrations
  and development evaluation.
- Safe manifests:
  `experiments/manifests/phase9-regenerated-dev.v1.json` and
  `experiments/manifests/phase9-regenerated-train-demos.v1.json`.

The archive and normalized records stay ignored. Selection manifests contain only stable IDs,
content hashes, labels, depths and provenance needed to reproduce selection.

## Local model and prompting

- Provider: native Ollama chat at loopback `http://127.0.0.1:11434` only.
- Ollama version: `0.32.1`.
- Model: `qwen3.5:4b-q4_K_M`.
- Model digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
- Device: CPU; concurrency 1; temperature 0; seed `20260818`; `think: false`.
- Baseline context/output: 4,096/128 tokens.
- Semantic/correction context: 8,192 tokens; the existing task-specific output limits remain
  unchanged.
- Prompts and schemas: reuse the checked Phase 3, Phase 5 and Phase 6 v1 artifacts byte-for-byte.
- Cost: USD 0.00. Paid APIs, hosted providers, cloud model tags, tools and browsing are forbidden.

The model, model digest, settings, prompts and selected records cannot be changed after inspecting
development results. Terminal structured-output failures are recorded as `ERROR`; they are not
silently regenerated with a changed request.

## Conditions and controlled ablations

All conditions use the same 30-record development selection.

1. **Direct local LLM**: zero-shot label prediction.
2. **Few-shot local LLM**: the direct condition plus exactly six frozen train demonstrations.
3. **P0 raw neuro-symbolic**: raw local semantic parser output, unchanged deterministic validation,
   symbolic reasoning and independent proof verification; no critic or correction.
4. **Validation-only**: P0 with invalid parser outputs rejected; no neural critic or correction.
5. **P1 corrected-valid**: typed deterministic feedback, local critic, at most one complete
   replacement correction, unchanged validators, reasoner and proof verifier.
6. **P2 corrected-selective**: P1 plus critic-acceptance gating and explicit abstention.
7. **Oracle-structure symbolic ceiling**: existing ProofWriter formal S-expressions on the same
   selected IDs, deterministic reasoner and independent verifier, with no language parser.

Direct versus few-shot is a paired prompt ablation. P0 versus validation-only, P0 versus P1 and P1
versus P2 are controlled same-selection component ablations. The oracle ceiling is
`SAME_SELECTION_DIFFERENT_REPRESENTATION`, not a paired natural-language system result. Proof
verification is a mandatory safety boundary and is not disabled. No causal claim is permitted
beyond the listed one-component controlled comparisons, and 30 records do not support a
significance or state-of-the-art claim.

## Execution, caching and retention

- Newly generated raw JSON/JSONL, requests, responses, accepted ASTs, proofs, traces and caches live
  only below ignored `results/phase9/` and `results/cache/phase9/` roots.
- Cache entries are content-addressed and validated against provider, exact model digest, runtime,
  prompt/schema hashes, selection hash and rendered request identity.
- Live local execution records provider dispatch counts. Cache-only replay must make zero
  inference dispatches and reproduce all non-timing scientific fields.
- Interrupted runs resume only through validated immutable cache entries. No partial run may be
  reported as complete.
- Only safe selection/freeze manifests, sanitized aggregate reports, hashes and catalogue entries
  are committed. No raw benchmark text, per-record provider payload, model thinking, cache, model
  weight, secret, absolute path or run directory may enter Git.

## Metrics and failures

The canonical raw prediction records feed the Phase 2 metric implementation:

- overall accuracy = correct / all selected examples;
- coverage = answered / all selected examples;
- answered-only accuracy = correct / answered and is always reported with coverage;
- selective risk = 1 - answered-only accuracy;
- three-label macro precision, recall and F1 use explicit zero-division handling;
- per-label and per-depth metrics, the five-column confusion matrix, proof verification,
  latency/token accounting and API cost are retained when available.

`UNKNOWN` is a valid logical label. `ABSTAIN` and `ERROR` are separate non-answer outcomes.
Failures include parser/schema/validation, provider terminal/transport, critic/correction,
resource-limit, inconsistency and proof-verification categories. Unavailable telemetry remains
null, never zero.

## Provenance, exports and catalogue

Every aggregate records the experiment ID, phase, dataset/version/split, sample size, selection and
freeze hashes, model/runtime, prompt/config hashes, seed, cache mode, provider calls, cost, runtime,
metric denominators, failures, proof status, source hashes, execution commit and limitations.
Aggregates must reproduce from ignored raw prediction records before publication.

Phase 9 entries extend the Phase 8 catalogue without overwriting historical conditions. They must
be visibly labelled **Phase 9 regenerated evidence under newly frozen protocol**. The read-only API,
deterministic JSON/CSV/Markdown exports and `/research` UI expose only sanitized aggregate evidence
and registered comparisons.

## Security and reproduction gates

Before execution, validate the archive, manifests, freeze hashes, loopback endpoint, exact local
model/digest/version, stopped old services, clean Git checkpoint and test-split prohibition. Abort
on any mismatch. After live execution, stop Ollama and prove cache-only replay.

Reproduction commands are versioned by the Phase 9 CLI and documented in
`docs/PHASE9_VERIFICATION.md` after successful execution. The intended sequence is dataset download,
manifest freeze validation, direct/few-shot local runs, parser/correction conditions, oracle
ceiling, zero-call replay, aggregate reproduction, catalogue generation and full regression and
security verification.
