# Phase Plan

Only the current phase may be implemented. Each phase begins with an explicit prompt and ends with tests, documentation, a verification report, and a cleanly described Git state.

## 1. Foundation

**Status:** completed at Git checkpoint `cac8f21`.

Create durable specifications, the versioned typed-AST schema and fixtures, FastAPI and Next.js shells, CI, Docker, and local verification. No solver, LLM call, dataset download, database, or experiment result.

**Gate:** all Phase 1 acceptance checks pass and the repository accurately reports limitations.

## 2. Dataset ingestion and evaluation harness

**Status:** completed on `phase/02-dataset-evaluation`; recorded by the branch's Phase 2 feature commit.

Add a versioned ProofWriter ingestion path, provenance/checksum manifest, normalized records, deterministic sampling without resplitting, JSONL run records, evaluation interfaces, and fixture-driven metrics tests. Do not call an LLM.

**Gate:** selected benchmark records ingest reproducibly and known fixture predictions produce exact expected metrics.

## 3. Direct and few-shot LLM baselines

**Status:** completed with a zero-cost local Ollama pilot; hosted OpenAI execution remains unverified.

Implemented the provider-independent LLM port, official OpenAI Responses adapter, versioned/hash-frozen prompts and selections, bounded retries/timeouts/concurrency, circuit breaking, usage/cost accounting, content-addressed replay, direct/few-shot conditions, paid/data-transfer gates, and mocked contract tests. The frozen 30-example direct and few-shot development pilot was executed locally through the digest-pinned Ollama adapter, followed by cache-only replay with the inference server stopped. Generated records and metrics remain ignored local artifacts rather than committed research results.

**Gate:** baseline runs are reproducible, raw outputs and errors are recorded, and provider-free tests pass.

## 4. Symbolic reasoning engine

**Status:** completed on `phase/04-symbolic-engine`; commit recorded in the Phase 4 completion report.

Implement semantic AST checks needed by the engine, deterministic finite forward chaining, unary/binary predicates, explicit negation, open-world decisions, multi-step derivations, inconsistency detection, and source-linked proof construction/replay.

**Gate:** passed with unit, integration, property-based, tamper, and formal ProofWriter conformance checks; no LLM participates in inference.

## 5. Neural semantic parser

**Status:** completed on `phase/05-neural-semantic-parser`; local frozen pilot and cache-only replay
completed with fail-closed parser errors.

Implement natural-language-to-AST prompting through the approved provider port, strict parsing, parser metadata, prompt/version tracking, and evaluation against reference formalizations where available.

**Gate:** parser outputs never bypass schema validation and parse/meaning errors are measured rather than hidden.

## 6. Validation, correction and abstention

**Status:** completed through the separately preregistered Phase 6-R3 terminal-failure protocol.
The original interrupted pilot and R2 replication remain blocked historical experiments.

Add structural/semantic meaning-preservation checks, limited solver-guided correction, confidence calibration/gating, explicit correction logs, and fail-closed abstention policies.

**Gate:** passed operationally with a complete 30-example prediction seal, independent proof
verification, reproducible risk/coverage metrics, and strict zero-call replay.

The original interruption cannot be completed from the current workspace. Phase 6-R2 used new,
isolated caches under a separately frozen protocol, but one of 57 unique Phase 5 requests
repeatedly exhausted its unchanged 4,096-token output limit without a schema-valid response.
Only 57 of 58 logical components can replay, so the mandatory gate failed before Phase 6 inference,
prediction sealing, or metric access. This R2 experiment remains blocked—not failed. See
`PHASE6_RECOVERY_R2_RESULTS.md`.

Phase 6-R3 is separately preregistered to treat exhausted local generations as typed replayable
errors. It preserves the same prompts, limits, ordered development sample, model digest, correction
policy, and abstention policy; it neither retries nor recovers the missing Phase 5 AST. R3
completed all 30 examples and strict replay resolved 67 logical task references from 64 unique
Phase 6 outcomes with zero misses/calls. P0 answered 2/30 correctly; P1/P2 answered none, with 22
abstentions and eight errors each. See `PHASE6_R3_RESULTS.md`.

## 7. End-to-end neuro-symbolic integration

**Status:** completed on `phase/07-end-to-end-integration` with formal, local-natural, cache-only
replay, API, frontend, and frozen-regression evidence.

Connect ingestion, parser, validators, correction/gating, reasoner, proofs, and experiment records behind stable backend services and APIs.

**Gate:** passed. Representative formal and natural cases reached typed terminal states, answered
proofs independently verified, formal execution made zero provider calls, and local replay
reproduced scientific fields with Ollama stopped. The negative natural correctness result is
retained without tuning.

## 8. Research frontend

**Status:** completed on `phase/08-research-frontend` with a versioned evidence catalogue,
read-only API, normalized AST inspector, research dashboard and deterministic aggregate exports.

Extend the Phase 7 workbench into the full research interface for normalized AST inspection,
experiment run history, baseline/ablation comparison, and exportable aggregate results. Use
shadcn/ui only when it materially improves the existing accessible interface.

**Gate:** critical UI states and API flows pass accessibility, browser, and error-path verification without fabricated data.

## 9. Full experiments and ablations

**Status:** completed on `phase/09-full-experiments-ablations` under the separately frozen Phase 9
regenerated-evidence protocol.

Freeze protocol/configurations, execute mandatory conditions and approved ablations, compute accuracy/proof/robustness/latency/cost metrics, and retain raw reproducible records.

**Gate:** passed. Seven conditions account for the same 30 development records, all answered
neuro-symbolic proofs independently verify, aggregate metrics reproduce from raw JSONL, strict
replay makes zero inference calls with Ollama stopped, and the versioned catalogue exposes failures
and unavailable telemetry honestly. See `PHASE9_VERIFICATION.md`.

## 10. Deployment, report and presentation

Harden and deploy the separate frontend/backend, finalize operational documentation, capstone report, limitations, reproducibility package, and presentation artifacts.

**Gate:** deployment smoke tests, security checks, clean-room setup instructions, report figures, and presentation claims agree with recorded evidence.
