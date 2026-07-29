# Test Matrix

The matrix grows with the implementation. Every behavior change requires corresponding positive, negative, and regression coverage.

| Area | Phase 1 coverage | Required later coverage | Primary command |
|---|---|---|---|
| Backend health | Response status and typed payload | readiness/dependency failure paths | `python -m pytest` |
| Environment settings | Construction exercised by app tests | malformed origins, production policy, precedence | `python -m pytest` |
| JSON Schema | Schema self-check; all valid fixtures accepted; each invalid fixture rejected for intended reason | version migration and compatibility | `python -m pytest` |
| Semantic AST validation | IDs/references, arity, types, declared terms, ground facts/query, safe heads | source-meaning preservation remains Phase 5/6 | `python -m pytest` |
| Reasoner | unary/binary, joins, constants, shared variables, conjunction, chains, cycles, explicit negation, OWA, inconsistency, no contraposition, determinism, limits | performance regression at larger final scale | `python -m pytest` |
| Proofs | canonical selection/hashes, exact sources/rules/substitutions, independent closure replay, graph integrity, tampering and fabricated-unknown rejection | final proof metrics/dashboard integration | `python -m pytest` |
| ProofWriter formal conformance | deterministic S-expression adapter, same-30 check, balanced 300-example OWA development ceiling, independent verification | no test split until final frozen protocol | explicit local reasoning CLI |
| Parser boundary | Gold-free views, theory/query schemas, strict local endpoint/model, malformed/extra output, source coverage, semantic validation, cache/replay, alpha canonicalization, no-thinking/no-gold tests | operational cache recovery and larger final-scale monitoring | `python -m pytest` |
| Correction controller | Typed state transitions, one-attempt bound, stable feedback/hashes, critic/correction schema failures, no-progress, gold isolation, abstention/error/unknown separation, synthetic-cache operational flow, resumed-call accounting, gold-free traces, cache identity/replay, sanitized missing-cache CLI failure, and P0 compatibility | restored real-cache pilot/replay and larger final-scale selective-risk evaluation remain operational/Phase 9 gates | `python -m pytest` |
| Terminal provider outcomes | strict schema/hash/provenance, request/prompt/schema/model binding, success/terminal/miss/corrupt/incomplete discrimination, atomic cache, no-call replay, parser/critic/correction propagation, error metrics, accounting, and one-correction bound | operational R3 cache materialization and full zero-call replay | `python -m pytest` |
| Dataset acquisition | mocked success, interruption, timeout, HTTP errors, size/checksum/ZIP failure, idempotence, force, traversal, symlink, cleanup | real-source availability regression and operational monitoring | `python -m pytest` |
| Dataset ingestion | OWA mapping, CWA refusal, malformed/missing/duplicate records, stable IDs, proof preservation, ZIP/directory streaming, official splits | further official variants and future format versions | `python -m pytest` |
| Sampling/leakage | seeds, filters, balanced/stratified sampling, impossible requests, test guard, IDs/questions/content/theory overlap | scale/performance and approved perturbation pairing | `python -m pytest` |
| Experiment metrics | perfect/wrong/mixed cases, abstention/error, coverage/risk, confusion, macro/per-depth values | proof metrics, latency distributions, token/cost accounting | `python -m pytest` |
| Evaluation outputs | predictor failures, invalid labels, gold isolation, atomic outputs, overwrite/incomplete protection | future provider interruption/replay policies | `python -m pytest` |
| LLM prompt/output boundary | direct/few-shot snapshots, label semantics, delimiters, gold isolation, strict enum/extra/malformed rejection | provider compatibility monitoring | `python -m pytest` |
| Provider resilience | mocked OpenAI Responses plus native Ollama mapping, strict local endpoint/model/version/digest/device checks, all labels, malformed output, timeout/connection failure, telemetry, bounded retry, auth fail-fast, circuit breaker, and thinking non-persistence | monitor exact runtime compatibility | `python -m pytest` |
| Cache and cost gates | deterministic keys, atomic/corrupt/mismatch/concurrent behavior, replay miss, resume, approvals, pre-dispatch/mid-run caps | billing reconciliation | `python -m pytest` |
| Phase 3 fairness | balanced 30-record dev manifest, six train-only demos, hashes, non-overlap, local direct/few config equality, distinct rendering, and paired deltas | final test protocol remains deferred | `python -m pytest` |
| Frontend | lint, TypeScript, production compilation | component states, accessibility, API integration, reasoning/proof views | `pnpm lint && pnpm type-check && pnpm build` |
| Containers | Compose parse/config validation | service health and end-to-end smoke test | `docker compose config` |
| Security | unsafe identifiers and unsupported fields rejected | injection payloads, limits, secret scanning, error redaction, CORS negatives | component suites |

## Test levels

- **Unit:** pure normalization, validation, inference, proof, and metric behavior.
- **Contract:** schema versions, API payloads, JSONL records, and provider ports.
- **Integration:** parser mock through validator/reasoner, API endpoints, and frontend-to-API states.
- **Property-based:** alpha-renaming invariance, fact/rule order invariance, idempotent closure, monotonic derivation where valid, and proof replay.
- **End-to-end:** representative local/Docker flow using deterministic fixtures and mocked external providers.
- **Research reproducibility:** rerun from recorded manifest/configuration and regenerate aggregates from raw JSONL.

## Mandatory failure paths

Tests must cover malformed JSON, unknown fields, unsupported arity and operators, unsafe identifiers, dangling sources, undeclared terms, unsafe rules, contradictory polarities, provider timeouts, correction exhaustion, critic rejection, repeated/no-progress candidates, deliberate abstention, empty theories, resource bounds, and proof tampering as soon as the corresponding feature exists.

## Quality gates

Ruff lint and format checks, pytest, frontend ESLint, frontend TypeScript, and the frontend production build must pass in CI. Dataset/evaluation CLI help and synthetic smoke commands are phase verification gates. Network acquisition is mocked in routine tests; real archive checks are explicit verification steps, not flaky CI dependencies. A skipped acceptance test requires an explicit reason and must not be reported as passed.

Ignored real datasets and response caches are never prerequisites for routine pytest. Their
preflight and replay are explicit operational gates and a missing immutable entry must fail closed.

Phase 6-R2 adds routine tests for normalized configuration equivalence, isolated namespaces,
frozen-hash enforcement, 58-logical/57-unique duplicate handling, cache-only miss rejection,
prediction-seal verification, and replay mismatch detection. The real local run exercised the
fail-closed cache gate: a persistent structured-output failure remained a miss and prevented Phase
6 execution.
