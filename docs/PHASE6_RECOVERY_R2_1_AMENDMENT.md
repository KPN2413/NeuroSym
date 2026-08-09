# Phase 6-R2.1 Preregistered Amendment

The first Phase 6-R2 execution attempt was stopped after six Phase 5-R2 cache responses and before
any development metric was computed. Its orchestration incorrectly required all 58 logical parser
requests to have distinct request hashes. A read-only plan proved that the frozen selection contains
57 unique request hashes because one exact query request occurs twice.

This defect did not alter prompts, schemas, inputs, model settings, response contents, or request
hashes. All six atomically written responses remain valid and are preserved for content-addressed
reuse. The incomplete run is marked invalid and is not an experiment result.

Phase 6-R2.1 changes only the completeness gate:

- require exactly 58 logical parser outcomes;
- allow the preregistered 57 unique request hashes and one duplicate cache reuse;
- require cache-only replay to satisfy all 58 logical outcomes from those 57 entries.

No neural, symbolic, correction, critic, abstention, retry, or evaluation behavior changed. The
superseding preregistration is
`experiments/manifests/phase6-recovery-r2-1-freeze.v1.json`. No development labels, proofs, or
aggregate metrics were inspected before this amendment.
