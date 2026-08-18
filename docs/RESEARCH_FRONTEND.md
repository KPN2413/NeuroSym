# Research Frontend

Phase 8 adds a read-only `/research` route beside the Phase 7 reasoning workbench. It presents
sanitized aggregate evidence from Phases 3–7 without reading ignored run directories or starting a
model provider. The page works with Ollama stopped.

## Sections

- evidence overview and catalogue integrity;
- filterable experiment history, including blocked and negative-result conditions;
- explicit paired, descriptive, ceiling and incomparable comparison contracts;
- accuracy/coverage, oracle gap, parser attrition, R3 dispositions, paired outcomes, errors,
  runtime/tokens, proof verification, per-depth and per-label views;
- a provider-free normalized AST inspector using a bundled synthetic theory;
- proof/provenance summaries and deterministic aggregate exports.

Charts use catalogue records rather than separately embedded measurements. Every chart has text
labels and an exact-value table. Missing values render as `NA`; selective accuracy is always shown
with coverage. The Phase 7 natural canary remains a synthetic integration miss, not a benchmark.

## Run locally

Start the FastAPI service on `127.0.0.1:8000`, then run `pnpm dev` from `frontend/` and open
`http://127.0.0.1:3000/research`. `NEXT_PUBLIC_API_BASE_URL` may select another explicit local API
origin. No Ollama process, model weight, API key or dataset archive is required for the dashboard.

## Failure states

The page has loading, empty, evidence-unavailable and backend-error states. Catalogue loading fails
closed if a tracked source hash differs. It never substitutes zero for missing evidence or tries to
reconstruct a missing historical AST.

## Limits

This interface reconstructs retained aggregate evidence. Phase 3 and Phase 5/6 measurements are
development pilots; Phase 4 is an oracle-structure ceiling; Phase 7 natural input is a canary.
Comparisons outside the registered compatibility catalogue are unsupported.
