# Phase 6-R3.4 Report Label and Duplicate Accounting Amendment

## Trigger

The Phase 6-R3 predictions were sealed before evaluation. Evaluation then exposed two reporting
defects:

1. comparison rows were still labeled `Phase 6-R2`;
2. the request ledger retained the last observation for duplicate request hashes, so three requests
   first executed live were later represented by their cache-hit observations.

The sealed live output, including its original report and ledger, is preserved and hashed in the
R3.4 manifest. The defects do not change a prediction, decision, proof, correction, abstention, or
metric value.

## Frozen correction

Comparison rows use the explicit experiment version. Request deduplication preserves the first
observation, matching the operational ledger and correctly retaining whether each unique request
was first executed live or inherited from cache.

The correction is reporting-only and was not selected for performance. No individual example may
be rerun. Verification must use the already complete caches with Ollama stopped, and prediction and
report fingerprints must remain identical to the sealed live run.
