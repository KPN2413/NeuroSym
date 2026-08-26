# Research Exports

The research API and CLI export the validated aggregate catalogue as canonical JSON, CSV, or
IEEE-friendly Markdown.

API:

```text
GET /api/v1/research/exports?format=json
GET /api/v1/research/exports?format=csv
GET /api/v1/research/exports?format=markdown
```

CLI:

```text
python -m verilogic_ns_api.research_frontend export --format json
python -m verilogic_ns_api.research_frontend export --format csv
python -m verilogic_ns_api.research_frontend export --format markdown
```

The API accepts only enumerated formats and bounded optional phase, condition and policy filters.
It does not accept a filesystem path. The CLI permits an output directory only beneath the current
repository. Fixed filenames use `verilogic-ns-phase1-9-evidence.v2` plus the format extension.

The canonical content hash covers catalogue version, sorted filters, selected experiments,
registered comparisons, global limitations and the `NA` missing-value convention. The generation
timestamp is metadata outside that canonical hash and defaults deterministically to the latest
recorded catalogue timestamp, so identical inputs produce identical bytes. The response includes
`X-Evidence-Content-SHA256`.

CSV uses explicit `NA` for unavailable values and includes provenance, split, sample size,
dimensions and limitations. JSON round-trips through its manifest and canonical evidence object.
Markdown includes an exact aggregate table and comparison warnings. No export includes raw
benchmark examples, prompts, model responses, caches, credentials, hidden reasoning or local paths.
The Phase 9 rows remain explicitly labelled as regenerated evidence, preserve failure denominators,
and export unavailable exact P1/P2 token totals as `NA` rather than zero.
