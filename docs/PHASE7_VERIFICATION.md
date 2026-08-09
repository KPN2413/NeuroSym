# Phase 7 Verification Record

**Status:** PASS for Phase 7 engineering and reproducibility gates on 2026-08-09.

Phase 7 began from clean commit `4a74aa56f4b03b4c639b3cf79c74e59ad1e2f7f0`. The frozen canary
manifest is `experiments/manifests/phase7-integration-canaries.v1.json`; raw requests, responses,
proof payloads, and runtime results remain in ignored local directories.

## Deterministic formal path

With Ollama stopped, all four committed theories returned `ANSWERED`, the expected logical status,
and an independently verified proof:

| Fixture | Result | Provider calls |
|---|---|---:|
| `entailed.json` | `ENTAILED` | 0 |
| `contradicted.json` | `CONTRADICTED` | 0 |
| `unknown.json` | `UNKNOWN` | 0 |
| `inconsistent.json` | `INCONSISTENT` | 0 |

Repeating the entailed input reproduced the canonical non-timing result and proof identity.

## Natural local path and replay

The frozen P2 Robin request used Ollama `0.32.1` and
`qwen3.5:4b-q4_K_M` digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
It reached `ANSWERED / UNKNOWN`, made four local dispatches, produced an independently verified
proof, and attempted no correction. This is a correctness miss—the intended conclusion is
entailed—but it satisfies the preregistered integration gate because a typed, verified terminal
outcome was required rather than a favorable model result.

After stopping Ollama, cache-only replay used four validated hits, zero misses, and zero provider
dispatches. Disposition, logical result, accepted theory, proof, proof verification, explanation,
abstention/error state, correction flag, and ordered stage statuses matched the live run.

API cost was USD 0.00. Hosted-provider calls, test-split records, and external data transfer were
all zero.

## Regression evidence

- Phase 6-R3 cache-only replay: 67 hits, zero misses/calls, seven terminal outcomes; prediction
  fingerprint `86120857fdcb0d4414939861e10d3acfe168b5801d5b1d4bf18de459fa9547c9`
  and report fingerprint
  `af70a0c2d0b3eb1134a61b0bda330c3d0421673768f1f8bdab02b291efc327ad` unchanged.
- Phase 4 balanced OWA development conformance: 300/300 correct and 300 verified proofs.
- Phase 4 frozen same-30 development conformance: 30/30 correct and 30 verified proofs.
- API formal submission completed as `ANSWERED / ENTAILED` with zero provider calls; repeated GET
  was stable.
- Frontend served successfully and the backend capabilities endpoint reported cache-only mode.

The final backend suite passed 332 tests with one upstream Starlette/httpx deprecation warning.
Ruff lint/format, dependency integrity, all CLI help checks, schema freshness, synthetic dataset,
evaluation/baseline/reasoning/orchestration smokes, three frontend component tests, frontend lint,
type checking, and the Next.js production build passed. Docker was not installed, so the explicitly
conditional `docker compose config --quiet` check was skipped without installing it.

## Limitations

- The local 4B semantic parser remains the quality bottleneck; Phase 7 does not improve or tune it.
- The job queue and result retention are process-local and intentionally non-durable.
- The interface is a local research tool without authentication or public deployment hardening.
- Automated browser tooling was unavailable; HTTP smoke tests and a documented manual checklist
  were used, and presentation readiness still requires that manual browser pass.
- Docker Compose was not locally executable because Docker was unavailable; its configuration was
  reviewed but not parsed by Docker during the final gate.
- No final benchmark, significance claim, or test-split evaluation is part of Phase 7.
