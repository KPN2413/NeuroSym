# VeriLogic-NS Final Presentation Source and Speaker Notes

Evidence package fingerprint: `d4d289cfeeafcdecc0a930d57ad78896c5e4a0ed8f02814c9c34c79a946326e6`

This source is the evidence-auditable companion to the generated PowerPoint. Visible copy is kept
short; each slide includes the intended talk track and its project sources.

## Slide 1 — VeriLogic-NS

Visible: “Verifiable reasoning with a local neuro-symbolic pipeline” and “Capstone project · Final
presentation”. Speaker note: the system verifies conclusions relative to supplied premises.
Sources: `docs/FINAL_REPORT.md`, `docs/PROJECT_CHARTER.md`.

## Slide 2 — The problem

Visible: fluent does not imply logically supported; explanations can be post-hoc; absence is not
contradiction. Speaker note: the project separates language interpretation from entailment.
Sources: `docs/FINAL_REPORT.md` sections 1 and 3.

## Slide 3 — Why neuro-symbolic?

Visible: neural component understands controlled language; symbolic component decides and proves;
validation is the trust boundary. Speaker note: neither component alone supplies all desired
properties. Sources: `docs/ARCHITECTURE.md`.

## Slide 4 — Project goals

Visible: restricted AST, deterministic four-way decision, explicit failure states, verified proof,
reproducible evaluation, local demo. Sources: `docs/PROJECT_CHARTER.md`, `docs/FINAL_REPORT.md`.

## Slide 5 — Overall architecture

Visible flow: natural language → local semantic parser → typed AST → validation/correction →
deterministic reasoner → proof replay → answer/explanation. Sources: `docs/ARCHITECTURE.md`.

## Slide 6 — Neural semantic parser

Visible: gold-free input, neutral source IDs, strict JSON schemas, local 4B model, fail closed.
Speaker note: exact theory match 1/30; exact query match 3/30. Sources: `docs/PHASE9_VERIFICATION.md`.

## Slide 7 — Symbolic reasoner

Visible: finite Datalog-style forward chaining; explicit negation; open world; no contraposition;
`ENTAILED`, `CONTRADICTED`, `UNKNOWN`, `INCONSISTENT`. Sources: `docs/SYMBOLIC_ENGINE.md`.

## Slide 8 — Validation, correction, reliability

Visible: P0 raw; validation-only; P1 one bounded correction; P2 critic-gated; `UNKNOWN ≠ ABSTAIN ≠
ERROR`. Speaker note: there were three typed terminal correction/cache failures. Sources:
`docs/PHASE9_VERIFICATION.md`, `docs/ABSTENTION_POLICY.md`.

## Slide 9 — Proof verification and explainability

Visible: source-linked proof DAG; canonical hashes; independent closure replay; explanation generated
from verified proof—not model prose. Sources: `docs/PROOF_FORMAT.md`, `docs/END_TO_END_PIPELINE.md`.

## Slide 10 — Product surfaces

Visible: workbench `/`; research dashboard `/research`; API; deterministic exports. Speaker note:
formal mode is provider-free and the research UI runs with Ollama stopped. Sources:
`docs/RESEARCH_FRONTEND.md`, `docs/FINAL_DEMO_GUIDE.md`.

## Slide 11 — Experimental protocol

Visible: ProofWriter V2020.12.3; OWA depth-5; 30 development examples; depths 0/1/2/3/5 × three
labels; seed 20260818; six train-only demos; overlap 0. Footer: “Development only · no test-set or
significance claim.” Sources: `docs/PHASE9_VERIFICATION.md`.

## Slide 12 — Baselines and ablations

Visible: Direct, Few-shot, P0 raw, Validation-only, P1 corrected-valid, P2 selective, formal oracle
ceiling. Speaker note: oracle inputs have a different representation. Sources:
`research/evidence/phase10-final-evidence.v1.json`.

## Slide 13 — Phase 9 main results

Visible table:

Direct | 16/30 | answered 30 | abstained 0 | errors 0<br>
Few-shot | 16/30 | answered 30 | abstained 0 | errors 0<br>
P0 raw neuro-symbolic | 4/30 | answered 5 | abstained 0 | errors 25<br>
Validation-only | 4/30 | answered 5 | abstained 25 | errors 0<br>
P1 corrected-valid | 2/30 | answered 3 | abstained 23 | errors 4<br>
P2 selective | 1/30 | answered 1 | abstained 25 | errors 4<br>
Formal symbolic oracle ceiling | 30/30 | answered 30 | abstained 0 | errors 0

Footer: “n=30 development · accuracy must be read with coverage.” Sources:
`research/evidence/phase10-final-evidence.v1.json`.

## Slide 14 — Paired ablations

Visible: Direct→Few 14 both / 2 direct / 2 few / 12 neither; P0→validation 4 / 0 / 0 / 26;
P0→P1 1 / 3 / 1 / 25; P1→P2 1 / 1 / 0 / 28. Speaker note: descriptive only, no
significance claim. Sources: `research/evidence/phase10-final-evidence.v1.json`.

## Slide 15 — The parser bottleneck

Visible: 30 inputs → 5 valid end-to-end formalizations → 4 correct answers. Errors: 14
semantic-invalid, 8 incomplete coverage, 3 structured-output. Speaker note: correction recovered
four of 31 attempts but did not improve aggregate performance. Sources: `docs/PHASE9_VERIFICATION.md`.

## Slide 16 — The oracle ceiling

Visible: P2 natural-language 1/30 at 1/30 coverage versus oracle formal 30/30 at full coverage;
30/30 proofs verified; zero model calls. Required label: **same-selection, different-representation formal symbolic ceiling**.
Sources: `research/evidence/phase10-final-evidence.v1.json`.

## Slide 17 — Replay, telemetry, and cost

Visible: 190 local dispatches; strict replay with Ollama stopped; hosted calls 0; external transfers
0; API cost USD 0.00; test-split access 0. Token callouts: Direct 10,711/351; Few-shot 48,301/243;
P0 39,562/34,277; P1/P2 exact token totals are unavailable, lower bound 127,252/62,249; oracle
0/0. Sources: `docs/PHASE9_VERIFICATION.md`.

## Slide 18 — Deployment and live demo

Visible: local production deployment; Next.js :3000; FastAPI :8000; Ollama :11434 optional; formal
demo with verified proof and zero calls; deterministic exports. Speaker note: Docker configuration
is static-validated; no Docker runtime or public cloud deployment was claimed. Sources:
`docs/DEPLOYMENT_GUIDE.md`, `docs/FINAL_DEMO_GUIDE.md`.

## Slide 19 — Limitations

Visible: 30 development examples; no test-set result; no superiority claim; 4B parser bottleneck;
P1/P2 exact telemetry unavailable; three terminal failures; ProofWriter licence remains unverified;
local single-user deployment. Sources: `docs/FINAL_REPORT.md` section 20.

## Slide 20 — Conclusion and future work

Visible: verified reasoning works when formalization is correct; fail-closed behavior is a concrete
safety contribution; natural-language formalization is the improvement target. Future work:
training-only parser improvement, larger local model comparison, then a separately frozen held-out
protocol. Sources: `docs/FINAL_REPORT.md` sections 21–22.

## Evidence-bound claims required by automated validation

30 development examples. No test-set experiment was performed. The oracle is a same-selection,
different-representation formal symbolic ceiling. P1/P2 exact token totals are unavailable. There
were three typed terminal correction/cache failures. The ProofWriter licence remains unverified.

Direct | 16/30<br>
Few-shot | 16/30<br>
P0 raw neuro-symbolic | 4/30<br>
P2 selective | 1/30<br>
Formal symbolic oracle ceiling | 30/30
