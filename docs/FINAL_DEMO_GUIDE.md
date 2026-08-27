# Final Demonstration Guide

## Purpose and timing

This 7–9 minute demo shows the implemented system and frozen research evidence without rerunning an
experiment. Use the provider-free formal path so the demonstration is fast, deterministic, and
independent of Ollama.

## Pre-demo checklist

1. Follow `docs/DEPLOYMENT_GUIDE.md` and start the backend on `127.0.0.1:8000` in `cache_only` mode.
2. Start the built frontend on `127.0.0.1:3000`.
3. Run `python -m verilogic_ns_api.phase10 demo-smoke` from the backend environment.
4. Confirm the smoke reports `PASS`, `ENTAILED`, verified proof, and zero provider dispatches.
5. Keep `/`, `/research`, and `http://127.0.0.1:8000/health` open in separate tabs.
6. Keep Ollama stopped. Do not run the 30-record experiment during the demonstration.

## Demo script

### 1. Frame the project — 45 seconds

Say: “VeriLogic-NS separates language interpretation from formal reasoning. The model may suggest a
symbolic representation, but only a validated AST and deterministic solver can produce an accepted
logical result. The system verifies conclusions relative to supplied premises, not factual truth.”

### 2. Show backend health — 20 seconds

Open `/health`. Point out the typed service status and version. Open capabilities and show:

- symbolic engine ready;
- provider mode `cache_only`;
- formal mode available;
- local model not required for this demo.

### 3. Show the workbench — 45 seconds

Open `/`. Explain the two modes, P0/P1/P2 policies, bounded pipeline stages, and the difference
between `UNKNOWN`, `ABSTAINED`, and `ERROR`.

### 4. Run one provider-free formal example — 2 minutes

Select **Formal AST · advanced**, keep the `ENTAILED` preset, and choose **P2 Selective**. Submit.
Show the completed pipeline and verify:

- logical result `ENTAILED`;
- provider dispatches `0`;
- proof verifier status `VERIFIED`;
- source-linked proof steps;
- deterministic explanation derived from the proof.

Explain that the same formal engine also has fixed presets for `CONTRADICTED`, `UNKNOWN`, and
`INCONSISTENT`.

### 5. Explain the safety property — 45 seconds

Point out that a formal/provider error cannot become logical `UNKNOWN`, and a rejected semantic
parse becomes a typed error or abstention. The proof is independently replayed before an answer is
displayed.

### 6. Open the research dashboard — 2 minutes

Navigate to `/research`. Show:

- 19 experiments and 10 registered comparisons;
- Direct and Few-shot at 16/30 each with full coverage;
- P0 at 4/30 with five answered and 25 errors;
- validation-only retaining 4/30 while converting those 25 errors to abstentions;
- P2 at 1/30 with one answer, 25 abstentions, and four errors;
- the 30/30 formal symbolic oracle ceiling, labelled as a different representation;
- `NA` for unavailable P1/P2 exact token totals.

State clearly: “These are 30 development examples. There is no test-set or significance claim.”

### 7. Export and reproducibility — 45 seconds

Use one JSON/CSV/Markdown export button. Explain that all formats come from the same hash-validated
catalogue and include a response content SHA-256. Mention strict zero-call replay with Ollama
stopped, 190 historical local dispatches, zero hosted calls, zero external transfer, and USD 0.00.

### 8. Close with the research finding — 30 seconds

Say: “The deterministic reasoner was perfect when given oracle formal structures, but the end-to-end
pipeline lost coverage at the semantic parser. The result is not that neuro-symbolic AI always wins;
it is that verified reasoning works once formalization is correct, and formalization is the next
research target.”

## Recovery paths

- If Ollama is unavailable: continue; the final demo does not require it.
- If natural-language mode is selected accidentally: switch to formal mode.
- If the frontend loses the backend: show the already verified smoke report, restart only the local
  backend/frontend processes, and rerun the provider-free smoke.
- If Docker is requested: explain that configuration was statically validated but runtime execution
  was skipped because Docker was unavailable.
- Never substitute screenshots or invented results for a failing live check.
