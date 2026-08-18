# Research Evidence Catalogue

The canonical tracked catalogue is `research/catalogues/phase1-7-evidence.v1.json`. It is generated
deterministically from `research_frontend.seed`, validated by Pydantic, and bound to tracked source
documents with SHA-256. Run:

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

## Historical integrity

The catalogue contains twelve distinct experiment conditions. Original Phase 6 and R2 remain
`BLOCKED`; R3 P0/P1/P2 remain separate terminal policies; the Phase 7 natural canary remains a
`COMPLETE_WITH_NEGATIVE_RESULT`. No blocked record is merged into the successful R3 history.

## Comparability

- `PAIRED`: same frozen records and selection manifest, currently direct versus few-shot only.
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
rejected.
