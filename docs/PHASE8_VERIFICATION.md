# Phase 8 Verification

Phase 8 reconstructs evidence only; it made zero model/provider calls, used no test split and added
USD 0.00 API cost. The starting checkpoint was `7ffffed4ae9dc1274b8f4fecd26531a7be665103`
on the new `phase/08-research-frontend` branch.

## Evidence audit

- Phase 6 prediction seal: `86120857fdcb0d4414939861e10d3acfe168b5801d5b1d4bf18de459fa9547c9`.
- Phase 6 report fingerprint: `af70a0c2d0b3eb1134a61b0bda330c3d0421673768f1f8bdab02b291efc327ad`.
- catalogue hash: `6908ff69506907551ec4e20e2e52aed44ddf3b3826b01cdaf61ceb7df1566842`.
- twelve experiment conditions and five comparison contracts validated.
- original Phase 6 and R2 remain blocked; the R3 result and Phase 7 natural miss remain visible.
- deterministic export file hashes: JSON
  `48efab5eae6d64f0448af2da36b4284e5962c8f300d16b4a1e0798c43d9070f9`, CSV
  `bf80982635fe08d66f1d8afae5dfbc090cf31bbec30dc0f3e94690c2a3550ec3`, and Markdown
  `65622fa2d52375f22dc01c3a12f05a8389558a998ac6ae839e1652cd483da283`.

## Verification scope

Backend tests cover catalogue/source integrity, null evidence, derivations, duplicate rejection,
comparison rules, filters, pagination, three deterministic exports, sanitized errors, explicit
negation, binary predicates, source mapping and correction diffs. Frontend tests cover evidence
formatting/filtering, comparison lookup, attrition, required page states, exports, accessibility
surfaces and workbench navigation. Ruff, pytest, ESLint, TypeScript and the Next.js production build
are mandatory final checks.

The final backend suite passed 351 tests; the frontend suite passed 11 tests. Ruff lint/format,
ESLint, TypeScript and the Next.js production build passed. One initial full pytest execution saw a
transient Windows permission race in the pre-existing cache-lock concurrency test; its immediate
targeted rerun and the complete second suite both passed. Docker was not installed, so Compose
configuration verification was skipped without installing it.

The running local stack returned HTTP 200 for `/research`, a `VERIFIED` catalogue with twelve
conditions, deterministic export content hashes and a complete synthetic AST inspection while
port 11434 had no listener. Browser automation could not connect because the installed Browser
plugin bundle imported a runtime module disallowed by the available browser-control sandbox;
HTTP checks, frontend tests/build and the manual checklist below were used as the documented
fallback.

Manual checklist:

1. Open `/research` at desktop and narrow mobile widths; confirm no horizontal overflow.
2. Tab through navigation, filters, comparison selects, AST action, details and export links.
3. Confirm both `PASS` and `BLOCKED` histories, and that blocked accuracy displays `NA`.
4. Select direct/few-shot and confirm the paired badge; select unsupported conditions and confirm
   the no-comparison warning.
5. Run the synthetic AST inspector and inspect facts, rule, query, source mapping, predicates,
   canonical JSON and unavailable correction/proof connections.
6. Download all three export formats and verify their fixed filenames.

The ignored ProofWriter archive and Phase 6 caches had been removed before this branch. No network
transfer or new benchmark inference was authorized, so Phase 4 300/same-30 conformance and Phase 6
strict cache replay were not regenerated. Their tracked source hashes and Phase 6 fingerprints were
verified; the full deterministic solver, proof and orchestration regression suites were rerun. No
historical result report was changed.
