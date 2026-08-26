# Research Evidence Catalogue

The active tracked catalogue is `research/catalogues/phase1-9-evidence.v2.json`. It is generated
deterministically from the immutable historical seed plus the sanitized Phase 9 aggregate,
validated by Pydantic, and bound to tracked source documents with SHA-256. The original
`research/catalogues/phase1-7-evidence.v1.json` remains unchanged as a historical Phase 8 artifact.
Run:

```text
python -m verilogic_ns_api.research_frontend build-catalogue --check
python -m verilogic_ns_api.research_frontend validate-catalogue
python -m verilogic_ns_api.research_frontend catalogue-summary
python -m verilogic_ns_api.research_frontend export-schemas --check
```

## Evidence contract

Every metric records its value or null, unit, optional numerator/denominator, dataset/version,
split, variant, sample size, selection reference, phase/condition/policy/model, run reference,
source artifact/hash/commit, comparability group, limitations and verification status. Evidence
types are `DIRECTLY_OBSERVED`, `DERIVED`, `DOCUMENTED` and `UNAVAILABLE`.

The original machine-readable Phase 3, 5 and 6 result directories are ignored and no longer present
in this workspace. Their retained measurements are therefore `DOCUMENTED`, never relabelled as
directly observed. Derived values include their formula. Missing evidence has a null value and
`UNAVAILABLE` status.

Phase 9 metrics are `DIRECTLY_OBSERVED` because the new aggregate reproduces from retained ignored
raw JSONL. Two correction cache outcomes lack usage telemetry, so P1/P2 exact token totals remain
null/`UNAVAILABLE`; separately named observed lower-bound metrics retain the partial counts.

## Historical integrity

The catalogue contains nineteen distinct experiment conditions: twelve historical conditions and
seven separately labelled Phase 9 regenerated conditions. Original Phase 6 and R2 remain
`BLOCKED`; R3 P0/P1/P2 remain separate terminal policies; the Phase 7 natural canary remains a
`COMPLETE_WITH_NEGATIVE_RESULT`. No blocked record is merged into the successful R3 history.

## Comparability

- `PAIRED`: same frozen records and selection manifest, including the registered Phase 9 component
  ablations; this supports descriptive paired counts, not significance or causality claims.
- `SAME_SELECTION_DIFFERENT_REPRESENTATION`: oracle structure versus natural-language processing;
  useful as a ceiling, not a paired system claim.
- `DESCRIPTIVE_ONLY`: aggregates may be displayed together but do not support causal deltas.
- `INCOMPARABLE`: explicitly prevents a claimed delta, including Phase 5 versus regenerated R3.

The validator requires a shared selection and sample size for paired comparisons. It rejects
duplicate experiment IDs, duplicate metric dimensions, unknown sources, source hash mismatches and
accuracy without coverage.

## Sanitization

The catalogue contains no raw prompts, responses, benchmark text, credentials, model thinking,
weights, cache paths or personal paths. Relative source identifiers are safe and traversal is
rejected. Phase 9 records explicitly retain 190 local dispatches, zero hosted calls, zero external
transfers, zero API cost, development-only split provenance, and the regenerated-protocol label.
