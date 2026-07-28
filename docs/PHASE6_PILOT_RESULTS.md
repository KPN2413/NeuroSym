# Phase 6 Pilot Recovery Report

## Status

**BLOCKED — immutable response-cache evidence is missing.**

The validation/correction implementation and train-only calibration are complete. The frozen
30-example development pilot and cache-only replay are not complete and no P1/P2 development
metrics are reported.

## Frozen protocol audit

- dataset: ProofWriter V2020.12.3, OWA development split only;
- pilot: 30 examples, 28 unique theories, 30 queries;
- test split: excluded;
- local model: `qwen3.5:4b-q4_K_M`;
- model digest:
  `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`;
- Ollama: 0.32.1 through `127.0.0.1`;
- temperature: 0;
- seed: 20260713;
- context: 8192;
- thinking: disabled;
- concurrency: 1;
- semantic correction limit: one per theory and one per query;
- worst-case unique development requests: 180;
- hosted calls: 0;
- API cost: USD 0.00.

The committed freeze manifest, prompts, schemas, model/runtime settings, calibration selection, pilot
selection, and P0/P1/P2 policy were not changed during recovery.

## Surviving evidence

The recovery audit found:

- Phase 5 semantic-parser cache: 0 JSON entries; expected 28 theory plus 30 query entries;
- Phase 6 validation/correction cache in the intended repository: 1 JSON entry;
- incomplete Phase 6 run directories: 0;
- corrupt/partial cache files in those roots: 0;
- ProofWriter archive: present, 214,185,889 bytes;
- archive SHA-256:
  `bbc5694901e8306d0bd659aa1ad53ccfd02c201864f4b320ffa3777827d1fc26`.

Searches of the available workspace, common project locations, temporary storage, and recycle-bin
metadata did not recover the missing immutable entries. An unrelated nested Git repository was
preserved and was not used as substitute evidence.

The operational plan fails closed on the first missing frozen theory entry. It makes no model
request, exposes no development metric, and returns a typed sanitized error.

## Existing research evidence

The previously frozen Phase 5 P0 aggregate remains:

- overall accuracy: 10.00%;
- coverage: 13.33%;
- answered-only accuracy: 75.00%;
- macro F1: approximately 16.32%;
- errors: 26;
- independently verified proofs: 4/4.

These are the recorded Phase 5 baseline values, not a freshly replayed Phase 6 result.

Train-only Phase 6 calibration remains recorded as:

- examples: 6;
- local calls: 21;
- critic calls: 14;
- correction calls/attempts: 7;
- recovered components: 3;
- correction regressions: 4;
- P2 selective outcomes: abstained on all 6.

This calibration evidence was not used to relax the frozen development policy.

## Development results

P1 corrected-valid and P2 corrected-selective metrics are unavailable. No development aggregates
were inspected after the interruption. Correction/critic performance, AST/closure metrics,
abstention/error distributions, proof counts, token totals, inference time, and paired comparisons
must remain unreported until all 30 decisions are complete.

## Cache-independent verification

Recovery verification completed:

- the backend dependency environment and `pip check`;
- Ruff lint and format checks;
- 283 passing pytest tests;
- all dataset/evaluation/baseline/reasoning/semantic-parser/validation-correction CLI help checks;
- synthetic dataset/evaluation and fake-provider baseline smoke/replay checks;
- Phase 4 balanced 300-example oracle-structure regression: 300/300, all proofs verified;
- Phase 4 frozen same-30 oracle regression: 30/30, all proofs verified;
- frontend pnpm 9.15.4 install, lint, type-check, and production build.

Docker Compose validation was unavailable because Docker is not installed or callable in this
environment. No hosted provider call or live Phase 6 inference occurred.

## Required recovery action

Restore, without modification, from backup or OneDrive/filesystem version history:

1. `results/cache/semantic-parser/` containing the exact 28 theory and 30 query Phase 5 responses;
2. `results/cache/validation-correction/` containing the original interrupted critic/correction
   responses.

Do not regenerate the Phase 5 entries. After restoration, require the plan to report exactly 58
Phase 5 cache hits, resume the 30-example pilot using content-addressed reuse, and then run a
provider-free replay with identical fingerprints and zero inference calls. Phase 6 may be marked
complete only after those gates pass.
