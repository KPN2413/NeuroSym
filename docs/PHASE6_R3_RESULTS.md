# Phase 6-R3 Terminal-Failure Evaluation Results

## Status

Phase 6 is complete through the separately preregistered R3 recovery experiment. The original
interrupted Phase 6 run and the R2 replication remain blocked historical experiments; R3 does not
rewrite or retroactively complete them.

R3 completed all 30 frozen OWA development examples, sealed P0/P1/P2 predictions before evaluation,
verified available proofs, and reproduced the result in a strict cache-only replay with Ollama
stopped. No test-split record, hosted provider, external transfer, paid API, or Phase 7 feature was
used.

## Frozen scope

- Dataset: ProofWriter V2020.12.3, OWA development split
- Sample: the same 30 examples used in Phases 3-5
- Distribution: two examples per label at depths 0, 1, 2, 3, and 5
- Provider: local Ollama 0.32.1 on loopback
- Model: `qwen3.5:4b-q4_K_M`
- Model digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`
- Execution: CPU, concurrency one, temperature 0, seed 20260713, thinking disabled
- Context: 8,192 tokens
- Correction bound: one complete replacement per theory/query
- Hosted calls/external transmissions/API cost: 0 / 0 / USD 0.00

The R3 parser and correction configuration file SHA-256 values are:

- parser: `a8b56ba502a651a0d8f9e27d95597f5e1fcc4c12d74358d1f9cc9867fba60bb7`
- correction: `2efbe7813f6b73eff8aa3c1cddb249836b9d5e785f700b0cdb500beb2ebe2b07`

## Why R3 exists

R2 stopped because one request exhausted the frozen output budget twice and no schema-valid AST
could be cached. R3 froze a typed terminal-outcome contract before continuing. A terminal outcome
is a final experimental `ERROR`, not a fabricated AST, an open-world `UNKNOWN`, or a selective
`ABSTAIN`. It is bound to the exact request/model/schema/runtime and replays without another model
call.

Machine validation of the R2 cache found 55 schema-valid unique responses and two unique terminal
failures across 57 unique requests. One successful request is reused by two logical components, so
R3 materialized all 58 Phase 5 logical outcomes as 56 successful component references and two
terminal component references with zero new Phase 5 provider calls.

## Prediction results

| Condition | Correct | Answered | Coverage | Overall accuracy | Answered-only accuracy | Macro F1 | Abstain | Error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P0 raw parser | 2/30 | 2 | 6.67% | 6.67% | 100% | 0.1212 | 0 | 28 |
| P1 corrected-valid | 0/30 | 0 | 0% | 0% | unavailable | 0 | 22 | 8 |
| P2 corrected-selective | 0/30 | 0 | 0% | 0% | unavailable | 0 | 22 | 8 |

P0 reached the symbolic engine for two records: one `CONTRADICTED` and one `UNKNOWN`. Both were
correct, and both emitted proofs that passed independent verification. No P1/P2 record reached the
reasoner, so P1/P2 proof attempts are zero. Their answered-only accuracy and selective risk are
unavailable because the denominator is zero.

P0 accuracy by depth was 0/6 at depths 0, 3, and 5, and 1/6 at depths 1 and 2. It answered one
`CONTRADICTED` and one `UNKNOWN` record correctly; it answered no `ENTAILED` record.

For context only:

| Historical/ceiling condition | Correct | Accuracy | Coverage |
|---|---:|---:|---:|
| Direct local LLM | 17/30 | 56.67% | 100% |
| Few-shot local LLM | 15/30 | 50.00% | 100% |
| Historical Phase 5 P0 | 3/30 | 10.00% | 13.33% |
| Phase 4 oracle-AST symbolic ceiling | 30/30 | 100% | 100% |

The 30-example development pilot supports no significance, state-of-the-art, or production claim.
The oracle-AST row does not measure natural-language parsing.

## Correction and critic outcomes

Across 58 theory/query components:

- 27 raw components were invalid;
- 32 correction attempts were made;
- 25 components became structurally valid;
- four recovered complete source coverage;
- four recovered semantic validation;
- three corrections regressed a component;
- four corrections made no progress;
- zero records became newly answerable;
- two records that P0 could answer were lost after correction.

The component-level correction-success rate was 4/32 (12.5%) under the frozen definition. Critic
work comprised four theory calls and 31 query calls. It returned 29 accepts and one revise decision
on evaluated reports; three corrected components were accepted. Post-hoc critic precision was 1.0,
recall 0.0417, and F1 0.08, with one true semantic-error detection, 23 false acceptances, and zero
false rejections.

P1 abstention reasons were incomplete source coverage (10), invalid theory (8), and no correction
progress (4). P2 reasons were incomplete source coverage (10), invalid theory (8), no correction
progress (3), and critic rejection (1). All eight P1 errors remained errors under P2.

## Parser and AST observations

- examples / unique theories: 30 / 28
- theory structured parse successes: 27
- query structured parse successes: 29
- complete valid theories: 2
- structural-validity rate: 6.67%
- source-coverage rate: 20/28 (71.43%)
- semantic-validation rate among covered theories: 2/20 (10%)
- exact complete-theory rate: 0%
- exact query rate: 1/30 (3.33%)
- source-aligned statement precision/recall/F1: 0.5625 / 0.0363 / 0.0682
- closure precision/recall/F1: 0.6296 / 0.5667 / 0.5965

The deterministic reasoner remained reliable when given usable structure; semantic formalization
and correction remained the bottleneck.

## Terminal outcomes and accounting

The Phase 6 correction cache contains 64 unique outcomes referenced by 67 logical tasks:

- 57 schema-valid successes;
- seven typed terminal errors;
- all seven terminals occurred at theory correction;
- all seven have `INVALID_STRUCTURED_OUTPUT`;
- three requests are exact duplicate logical reuses.

Across the complete unique cache, observed telemetry is 65,796 input tokens, 26,065 output tokens,
and 6,023,711.5572 ms. Complete totals are intentionally null because telemetry is unavailable for
three terminal outcomes. Two sealed legacy provider-layer parse failures carried zero placeholders;
R3.5 preserves their cache hashes while interpreting those zeroes as unavailable. Future failures
at that boundary record null directly.

The completion invocation after the interrupted work created 60 new unique Phase 6 outcomes and
reported 60,344 input tokens, 23,520 output tokens, and 5,193,304.7371 ms. Before that invocation,
three successful correction outcomes contributed 5,452 input tokens, 2,545 output tokens, and
830,406.8201 ms. One separately materialized interrupted terminal represents two model executions
whose telemetry was unavailable. Total local Phase 6 provider dispatches across the preserved
operational history were 65; replay dispatches were zero.

## Freeze and amendment history

| Artifact | Commit | Manifest SHA-256 |
|---|---|---|
| R3 terminal protocol | `f207515f6fab96bd9f785a0c42c4926a64b872c2` | `2084266540bd6642a0a30fe294363e404912e53600e918c2abf03a8c55a61bf2` |
| R3.1 canonical terminal hash | `67ec57e9c4aee4b2cc8e74970adb8469d8fe5891` | `95556ce037b4a8fe5cbf7a9f40808e488f6567124f0ae0e2705f9f7f87ac29b5` |
| R3.2 idempotent terminal replay | `e2c486fce2e48abf157d2558b87569139f1e3768` | `96b88be1ad0858dc693dada1bc3049ca3776fabf851fd9e36bc2c9ebd54a3b41` |
| R3.3 null accounting propagation | `acb9e4fd3226fa6aa2e1a350288598535a247129` | `f86ea401017febe40e69ed0df5da6d61a817de7f3cdc22583716a79355b3ce06` |
| R3.4 report labels/duplicates | `54f6e7e11d03f0cec0d2454ff368e3e358843678` | `9cb430783d1e1aae55fb95222d20afafa060b78b25db5002ff5d15b394fd396e` |
| R3.5 legacy-zero interpretation | `823eacff25f6a6e80ea9a747558d941a57043692` | `82d02fb2c778c4343f06329f7eb02e1778cdf11d116d43b6ba9ac08461f6ece1` |

R3.1-R3.3 were frozen before development metrics were examined. R3.4 and R3.5 were frozen after
predictions were sealed and metrics were examined, are explicitly reporting-only, and do not alter
predictions, decisions, proofs, abstentions, model behavior, or metric definitions.

## Replay evidence

The authoritative replay ID is `phase6-r3-replay-final-r5`.

- logical cache hits: 67/67
- unique cache outcomes: 64
- cache misses: 0
- new provider calls: 0
- terminal outcomes: 7
- unavailable accounting records: 3
- Ollama process/listener: stopped/closed
- prediction seal fingerprint:
  `86120857fdcb0d4414939861e10d3acfe168b5801d5b1d4bf18de459fa9547c9`
- report fingerprint:
  `af70a0c2d0b3eb1134a61b0bda330c3d0421673768f1f8bdab02b291efc327ad`
- live/replay comparison: passed

The replay prediction-seal file SHA-256 is
`29f34aa52387c4e949031f13d7156adac31116271eac7f5c2a0b7e4538bfde9c`;
the replay report file SHA-256 is
`631a3abdd8c669cd14789f1f2909234d0dc73e3304e7482e5f6c4fea5b37e938`.
Raw requests, responses, source text, ASTs, controller traces, and per-record labels remain ignored.

## Interpretation and limitations

The preregistered hypothesis that bounded correction would improve end-to-end answerability was not
supported in this development pilot. Structural recovery alone was insufficient, and the local
critic accepted many semantically wrong candidates. This negative result is retained without
post-result tuning.

Temperature zero and a fixed seed do not make local neural inference deterministic. The sample is
small and development-only. ProofWriter's licence remains unverified, and the observed archive
checksum is not publisher-verified. The system verifies conclusions relative to supplied premises;
it does not establish factual truth.

Phase 7 may now begin under a new explicit implementation prompt. It must consume the frozen Phase
6 interfaces/results without changing this completed experiment or claiming that Phase 6 improved
accuracy.
