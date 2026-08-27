# VeriLogic-NS: Final Technical and Research Report

**Project:** Neuro-Symbolic AI Framework<br>
**Implementation name:** VeriLogic-NS / NeuroSym<br>
**Project state:** implementation roadmap complete through Phase 10<br>
**Evidence boundary:** Phase 9 regenerated evidence under a separately frozen protocol
Evidence package fingerprint: `d4d289cfeeafcdecc0a930d57ad78896c5e4a0ed8f02814c9c34c79a946326e6`

> **Interpretation rule.** VeriLogic-NS verifies whether a conclusion follows from supplied
> premises. It does not establish that those premises are factually true.

## Abstract

Large language models can produce fluent answers without a dependable logical certificate.
VeriLogic-NS studies a bounded alternative: a local language model translates controlled natural
language into a restricted, versioned symbolic representation; deterministic validation,
forward-chaining reasoning, and independent proof replay then decide whether a query is entailed,
contradicted, unknown, or inconsistent. Uncertain formalizations fail closed as typed errors or
abstentions rather than being relabelled as logical answers.

The system was evaluated on **30 development examples** from ProofWriter V2020.12.3 under an
open-world protocol. Direct and six-example few-shot local-LLM baselines each answered all records
and achieved 16/30 accuracy. The raw neuro-symbolic pipeline answered five records and achieved
4/30 overall accuracy; validation preserved those five answers while converting 25 invalid
formalizations from errors to abstentions. Corrected-valid and selective policies reduced coverage
without improving overall accuracy. When the deterministic reasoner received dataset-provided
formal structures, the same-selection, different-representation formal symbolic ceiling reached
30/30 with 30/30 independently verified proofs and no model call. This is a component ceiling, not
natural-language system performance. The central negative finding is that the local 4B semantic
parser—not the symbolic engine—is the main end-to-end bottleneck.

## 1. Problem statement

Neural language models are effective pattern learners but may make unsupported logical jumps,
confuse absence with contradiction, or produce explanations that are not faithful to the actual
decision process. A useful research prototype must therefore separate two responsibilities:

1. interpreting controlled language; and
2. determining formal entailment.

The project asks whether a transparent neuro-symbolic pipeline can provide verifiable answers and
safer failure behavior on rule-based reasoning tasks. It does not attempt to train a new language
model, solve unrestricted first-order logic, or guarantee the truth of input premises.

## 2. Objectives

The implemented objectives were to:

- represent facts, explicit negative facts, unary/binary predicates, variables, and conjunctive
  Horn-style rules in a non-executable JSON AST;
- use a provider-independent semantic parser while keeping logical decisions deterministic;
- validate structure, semantics, source coverage, and rule safety before reasoning;
- produce `ENTAILED`, `CONTRADICTED`, `UNKNOWN`, or query-specific `INCONSISTENT` decisions;
- return source-linked proof DAGs and independently replay every published proof;
- expose raw, corrected-valid, and selective policies without collapsing `UNKNOWN`, `ABSTAIN`, and
  `ERROR` into one meaning;
- compare direct, few-shot, neuro-symbolic, validation, correction, selection, and oracle-ceiling
  conditions on one frozen development selection; and
- provide a local API, workbench, research dashboard, deterministic exports, tests, and a
  reproducible demonstration workflow.

## 3. Background and motivation

Neuro-symbolic systems combine learned language or perception components with explicit symbolic
representations and inference. Prior work such as Logic-LM and LINC demonstrated the broad pattern
of translating language to formal constraints and invoking a symbolic solver. VeriLogic-NS focuses
on the engineering and scientific weakness that follows from that pattern: a correct solver can
still reason over an incorrectly translated theory.

ProofWriter was selected because it supplies natural-language theories, queries, formal structure,
three-way open-world labels, proof information, and controlled reasoning depths. Its formal fields
also permit an oracle-structure ceiling that isolates the symbolic component. The public archive is
downloadable, but the archive contains no verified dataset licence declaration; redistribution is
therefore deliberately excluded.

Primary background sources:

- [ProofWriter (Tafjord, Dalvi, and Clark, 2021)](https://aclanthology.org/2021.findings-acl.317/)
- [Logic-LM (Pan et al., 2023)](https://aclanthology.org/2023.findings-emnlp.248/)
- [LINC (Olausson et al., 2023)](https://aclanthology.org/2023.emnlp-main.313/)

## 4. System architecture

```text
Controlled natural-language facts, rules, query
                    |
                    v
         Gold-isolated local semantic parser
                    |
                    v
       Restricted typed JSON AST candidate
                    |
          validation + source coverage
             /                 \
      fail closed          valid candidate
          |                     |
 typed error/abstain   optional bounded correction + critic
                                |
                         full revalidation
                                |
                    deterministic forward chaining
                                |
                    independent proof verification
                                |
        ENTAILED / CONTRADICTED / UNKNOWN / INCONSISTENT
```

The trust boundary is the validated AST. Dataset text, user input, and model responses are
untrusted. No model-generated Python, JavaScript, SQL, shell, Prolog, template, or other executable
content is run. Formal AST mode bypasses every model component and directly exercises the
validator, reasoner, proof producer, verifier, and explanation renderer.

## 5. Dataset and experimental controls

Phase 9 used ProofWriter V2020.12.3, open-world `depth-5`, development split only. The observed
archive SHA-256 was
`bbc5694901e8306d0bd659aa1ad53ccfd02c201864f4b320ffa3777827d1fc26`.
The frozen seed was `20260818`. The selection contained two examples for each combination of depth
0/1/2/3/5 and label `ENTAILED`/`CONTRADICTED`/`UNKNOWN`, for 30 records total. Few-shot prompting
used six train-only demonstrations, two per label, with zero train/development overlap.

The Phase 9 freeze SHA-256 was
`c7039474c7f4522767a747deb384fa0ee9e05e450fb7a108d3b2001b36b4719e`.
The local model was `qwen3.5:4b-q4_K_M` with digest
`2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`.
Prompts, schema, model identity, selections, and comparisons were frozen before aggregate metrics
were inspected.

**No test-set experiment was performed.** Test-split access count remained zero. The 30-example
development pilot supports descriptive findings only; it does not support a statistical
superiority, state-of-the-art, or generalization claim.

## 6. Neural semantic parsing

The local semantic parser receives a gold-free view containing neutral source identifiers and
natural-language text. It does not receive gold labels, formal fields, proof payloads, dataset
paths, or reasoning depth. Theory parsing and query parsing are separate schema-constrained tasks.
The exact Ollama endpoint, version, model tag, digest, decoding configuration, and prompt hashes are
part of cache identity.

Every response crosses strict Pydantic and semantic validation. Missing sources, wrong arity,
undeclared terms, unsafe identifiers, unsupported operators, or incomplete coverage become typed
failures. Parser failure is never changed into the valid open-world answer `UNKNOWN`.

Phase 9 accepted five complete theory/query formalizations. The error taxonomy was 14
semantic-invalid, eight incomplete-source-coverage, and three structured-output failures. Exact
theory matching was 1/30 and exact query matching was 3/30. These results identify semantic
formalization as the main practical bottleneck.

## 7. Symbolic reasoning engine

The Phase 4 engine implements finite Datalog-style least-fixpoint forward chaining. Positive and
explicit negative literals are separate signed atoms. Safe conjunctive rules are grounded over a
finite domain, applied deterministically, and iterated to closure. The engine does not use
contraposition, negation as failure, or explosive inference.

- `ENTAILED`: the query is derivable and its explicit opposite is not.
- `CONTRADICTED`: the explicit opposite is derivable and the query is not.
- `UNKNOWN`: neither polarity is derivable.
- `INCONSISTENT`: both polarities are derivable for this query.

Resource exhaustion is a typed failure, never `UNKNOWN`. The same component reached 30/30 on the
Phase 9 selected sample when supplied with oracle formal structures, supporting the conclusion that
the tested symbolic fragment is not the observed end-to-end bottleneck.

## 8. Validation, critic, and correction

Structural and semantic validation is deterministic. The Phase 6 controller converts validation
failures into typed feedback, permits at most one complete semantic replacement per theory/query,
revalidates the replacement, and applies a separate structured fidelity critic. It does not run an
open-ended reflection loop.

In Phase 9, 31 correction attempts produced four observed semantic recoveries. Four regressions and
four no-progress outcomes were retained. The critic evaluated 33 cases, with observed precision
1.0, recall 0.1, and F1 0.1818. There were **three typed terminal correction/cache failures**; they
were preserved as errors, not regenerated until favorable or rewritten as logical outcomes.

## 9. Reliability policies

The evaluated policies were:

- **P0 raw neuro-symbolic:** accept only raw formalizations that already validate.
- **Validation-only:** convert deterministic formalization failures into abstentions while leaving
  valid answers unchanged.
- **P1 corrected-valid:** permit one correction and release every fully validated, independently
  verified result.
- **P2 selective:** additionally require critic acceptance before releasing the answer.

This separation preserves meaning: `UNKNOWN` is a logical result, `ABSTAIN` is a deliberate safety
decision, and `ERROR` is an infrastructure or formalization failure. Coverage and answered-only
accuracy are always reported with overall accuracy so a selective system cannot look strong merely
by answering very little.

## 10. Proof verification and explainability

Every accepted formal conclusion carries a canonical source-linked proof DAG. Fact nodes refer to
the exact input source. Rule-application nodes contain the grounded rule, antecedent roots, source
identifier, depth, and stable hash. A separate verifier checks graph integrity and independently
recomputes closure with a naive reference implementation.

All attempted proofs in the published Phase 9 neuro-symbolic conditions verified: P0 5/5,
validation-only 5/5, P1 3/3, P2 1/1, and oracle 30/30. The user-facing explanation is generated
deterministically from verified proof nodes; model-authored prose and hidden reasoning are not used
as evidence.

## 11. Backend and API

FastAPI exposes:

- `GET /health` for liveness;
- `/api/v1/neurosymbolic/capabilities` for provider, model, queue, limits, and schema status;
- asynchronous submit/poll/cancel endpoints for bounded neuro-symbolic runs; and
- read-only research catalogue, experiment, comparison, AST-inspection, and export endpoints.

The local job manager has one worker, a bounded queue, finite result retention, and cooperative
cancellation. Formal requests create no provider. Natural-language live mode fails closed with a
sanitized `LOCAL_MODEL_UNAVAILABLE` response when the exact local model is not ready. CORS accepts
only explicit configured origins; credentials and wildcard origins are not enabled.

## 12. Research frontend

The Next.js application has two main routes:

- `/` — the workbench for natural-language or formal-AST reasoning, policy selection, stage trace,
  proof, explanation, provenance, cancellation, and typed failures;
- `/research` — the evidence dashboard for 19 experiments, 10 registered comparisons, exact-value
  tables, parser attrition, policy dispositions, per-depth/per-label views, proof rates, token and
  runtime evidence, AST inspection, and deterministic JSON/CSV/Markdown exports.

The research UI reads only the validated tracked catalogue. It never starts Ollama, reads ignored
caches, reconstructs missing history, substitutes zero for unavailable evidence, or permits
unregistered comparisons.

## 13. Experimental methodology

The same frozen 30 development records were used for Direct, few-shot, P0, validation-only, P1,
P2, and the oracle-structure ceiling. Direct and few-shot used the same local model, settings,
output schema, task definition, and record order; few-shot added only the six frozen training
demonstrations. Neuro-symbolic ablations reused the same parser/correction evidence where their
intervention permitted it.

Metrics include overall accuracy, answered-only accuracy, coverage, selective risk, macro
precision/recall/F1, confusion matrices, per-label and per-depth results, failures, proof attempts,
proof verification, runtime, and tokens. Paired outcome counts are descriptive. The P2–oracle
relationship is explicitly different-representation and therefore not a paired natural-language
performance claim.

## 14. Baselines

The **Direct** baseline requests only one of `ENTAILED`, `CONTRADICTED`, or `UNKNOWN`. The
**Few-shot** baseline uses the same task prompt and adds exactly six training demonstrations. Both
operate on natural language and answer every selected record. The **formal symbolic oracle
ceiling** bypasses natural-language parsing and therefore answers a different component question:
whether the deterministic reasoner is correct when supplied with the dataset's formal structure.

## 15. Phase 9 results

| Condition | Overall correct | Answered | Abstained | Errors | Coverage | Answered-only accuracy | Verified proofs |
|---|---:|---:|---:|---:|---:|---:|---:|
| Direct | 16/30 | 30 | 0 | 0 | 100.00% | 53.33% | NA |
| Few-shot | 16/30 | 30 | 0 | 0 | 100.00% | 53.33% | NA |
| P0 raw neuro-symbolic | 4/30 | 5 | 0 | 25 | 16.67% | 80.00% | 5/5 |
| Validation-only | 4/30 | 5 | 25 | 0 | 16.67% | 80.00% | 5/5 |
| P1 corrected-valid | 2/30 | 3 | 23 | 4 | 10.00% | 66.67% | 3/3 |
| P2 selective | 1/30 | 1 | 25 | 4 | 3.33% | 100.00% | 1/1 |
| Formal symbolic oracle ceiling | 30/30 | 30 | 0 | 0 | 100.00% | 100.00% | 30/30 |

Direct and Few-shot achieved identical aggregate accuracy but differed on four individual records.
Validation improved failure handling by converting 25 invalid P0 parser outputs from errors to
abstentions, not by changing accuracy. P1 and P2 did not outperform the direct/few-shot baseline on
this sample. P2's 100% answered-only accuracy applies to exactly one answer and must be interpreted
with its 1/30 coverage.

## 16. Ablation comparisons

| Comparison | Both correct | Baseline only | Changed only | Both incorrect | Interpretation |
|---|---:|---:|---:|---:|---|
| Direct → Few-shot | 14 | 2 | 2 | 12 | Paired descriptive; equal aggregate accuracy |
| P0 → Validation-only | 4 | 0 | 0 | 26 | 25 errors became abstentions |
| P0 → P1 | 1 | 3 | 1 | 25 | Correction reduced accuracy and coverage |
| P1 → P2 | 1 | 1 | 0 | 28 | Selective gate reduced released answers |
| P2 → Oracle | 1 | 0 | 29 | 0 | Different representation; ceiling only |

None of these 30-record comparisons supports statistical significance or a causal superiority
claim. The P2–oracle gap indicates the potential available after perfect formalization; it is not
evidence that the natural-language system achieved oracle performance.

## 17. Replay and reproducibility

Phase 9 produced 190 unique local model dispatches: 30 Direct, 30 few-shot, 60 parser, and 70
correction/critic. Strict replay then completed with Ollama stopped: Direct 30/30 hits, few-shot
30/30, parser 60/60, and all 70 correction/critic entries resolved with no new inference.

The verified **aggregate fingerprint** is
`30146ca1a9cae630b18a96607c7c0a32173f6590631fc470c9c61cc22c5c26b1`.
The active catalogue hash is
`b849a0d00c683a39a4df3583dec18793aad14d8754b795e4cacc07308be64c73`,
and the immutable Phase 8 v1 canonical hash is
`6908ff69506907551ec4e20e2e52aed44ddf3b3826b01cdaf61ceb7df1566842`.

Automated deliverable validation binds the report and presentation claims to these complete
machine-readable identities.

## 18. Deployment and demonstration

The approved deployment is a reproducible **local production/demo deployment**, not a public
multi-user service. FastAPI runs on loopback port 8000 in cache-only provider mode. The optimized
Next.js production build runs on loopback port 3000 and connects to the explicit backend origin.
Ollama port 11434 is optional: the research dashboard and formal workbench require no model, while
natural-language live mode requires the exact frozen model and fails closed if it is unavailable.

The final smoke verifies backend health, capabilities, CORS, catalogue and experiment endpoints,
JSON/CSV/Markdown export hashes, both frontend routes, a provider-free formal `ENTAILED` run, proof
verification, deterministic explanation, and zero provider dispatches. Dockerfiles and Compose are
statically validated; runtime Docker execution is not claimed because Docker is not installed on
the verification machine. No public cloud deployment was authorized or performed.

## 19. Security and cost

The architecture rejects executable model output, unsafe identifiers, unknown AST fields,
unsupported operators, missing source links, type/arity errors, unsafe rules, proof tampering,
remote Ollama endpoints, cache identity mismatch, and unregistered research paths. Provider keys
remain environment-only and mere key presence cannot authorize paid calls.

Phase 9 and Phase 10 used zero hosted inference calls, zero external transfers, and **USD 0.00 paid
API cost**. No raw ProofWriter archive, raw benchmark text, local model weight, provider response,
cache, virtual environment, dependency directory, secret, or personal absolute path is included in
the tracked deliverables.

## 20. Limitations

1. The Phase 9 experiment contains 30 development examples only.
2. No test-set experiment was performed and no superiority claim is supported.
3. The local 4B semantic parser is the main end-to-end bottleneck.
4. The symbolic oracle is a same-selection, different-representation formal symbolic ceiling.
5. **P1/P2 exact token totals are unavailable**; only an observed lower bound of 127,252 input and
   62,249 output tokens is retained.
6. There were three typed terminal correction/cache failures.
7. The ProofWriter licence remains unverified.
8. The selected reasoning language is restricted and does not support arbitrary first-order,
   modal, probabilistic, or temporal logic.
9. The queue is process-local and the application has no database, authentication, multi-user
   isolation, rate-limit service, or public deployment hardening.
10. Model aliases and local runtime behavior are not mathematical determinism; reproducibility is
    supported through exact identity, caching, and replay rather than guaranteed regeneration.

## 21. Future work

Future work should begin only under a new approved protocol. High-value directions are: improve or
fine-tune the natural-language-to-AST parser on training data; compare larger local models under
equal frozen conditions; expand semantic equivalence evaluation; introduce stronger deterministic
normalization before neural correction; evaluate a newly frozen held-out test protocol once all
development decisions are complete; and study more expressive logic only after versioning the AST
and proof contracts. FOLIO, Z3 cross-verification, RAG, authentication, and public deployment remain
optional extensions, not completed claims.

## 22. Conclusion

VeriLogic-NS demonstrates a complete, auditable neuro-symbolic research pipeline: controlled
language is transformed into a restricted AST, unsafe formalizations are rejected or selectively
abstained, deterministic reasoning produces a decision, and an independent verifier checks the
proof used for explanation. The system's strongest validated property is not higher aggregate
accuracy; it is the separation of untrusted language interpretation from verifiable logical
inference and the preservation of explicit failure states.

The experiments also deliver a useful negative result. Direct and few-shot local LLM baselines
outperformed the end-to-end neuro-symbolic conditions on the 30 development examples, while the
formal symbolic ceiling was perfect. The evidence therefore localizes the improvement target:
better semantic formalization is necessary before the symbolic safety and explainability benefits
can translate into competitive end-to-end coverage and accuracy.

## 23. Reproduction guide

1. Follow [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for exact prerequisites and production startup.
2. Validate frozen evidence and deliverables:

   ```text
   backend/.venv/Scripts/python.exe -m verilogic_ns_api.phase10 export-evidence --check
   backend/.venv/Scripts/python.exe -m verilogic_ns_api.phase10 export-schema --check
   backend/.venv/Scripts/python.exe -m verilogic_ns_api.phase10 validate-deployment
   backend/.venv/Scripts/python.exe -m verilogic_ns_api.phase10 validate-deliverables
   ```

3. Start the backend in cache-only mode and the built frontend on loopback.
4. Execute the provider-free smoke:

   ```text
   backend/.venv/Scripts/python.exe -m verilogic_ns_api.phase10 demo-smoke
   ```

5. Use [FINAL_DEMO_GUIDE.md](FINAL_DEMO_GUIDE.md) for the presentation flow. Do not rerun the
   30-record experiment during a demo.

## Evidence and repository references

- [Phase 9 verification](PHASE9_VERIFICATION.md)
- [Research evidence catalogue](RESEARCH_EVIDENCE_CATALOGUE.md)
- [Experiment protocol](EXPERIMENT_PROTOCOL.md)
- [Architecture](ARCHITECTURE.md)
- [Security rules](SECURITY_RULES.md)
- [Final Phase 10 evidence package](../research/evidence/phase10-final-evidence.v1.json)
- [Phase 9 sanitized aggregate](../research/evidence/phase9-regenerated-aggregate.v1.json)
- [Active catalogue v2](../research/catalogues/phase1-9-evidence.v2.json)
