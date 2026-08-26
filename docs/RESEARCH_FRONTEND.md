# Research Frontend

The read-only `/research` route now presents the immutable historical evidence plus the separately
labelled Phase 9 regenerated evidence. It reads only the tracked catalogue and never reads ignored
run directories or starts a model provider. The page works with Ollama stopped.

## Sections

- evidence overview and catalogue integrity;
- filterable experiment history, including blocked and negative-result conditions;
- explicit paired, descriptive, ceiling and incomparable comparison contracts;
- accuracy/coverage, Phase 9 oracle gap, parser attrition, policy dispositions, paired outcomes,
  errors, runtime/tokens, proof verification, per-depth and per-label views;
- a provider-free normalized AST inspector using a bundled synthetic theory;
- proof/provenance summaries and deterministic aggregate exports.

Charts use catalogue records rather than separately embedded measurements. The Phase 9 charts
show the regenerated Direct, few-shot, P0, validation, P1, P2 and oracle conditions. Every chart has text
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

This interface reconstructs retained aggregate evidence. Historical pilots remain historical;
Phase 9 is a separate 30-record development-only regeneration. Its symbolic oracle is a
same-selection, different-representation ceiling. P2's answered-only accuracy is shown with its
1/30 coverage, failed records remain visible, and incomplete P1/P2 token totals render as `NA`.
Comparisons outside the registered compatibility catalogue are unsupported.
