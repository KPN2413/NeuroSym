# Phase 6-R3.3 Null Accounting Propagation Amendment

## Trigger

After R3.2, the resumed batch read the frozen terminal cache entry without calling the provider.
Conversion into the controller's `TaskOutcome` then failed because that downstream model still
required numeric token and timing fields. The run stopped before dispatching another task.

The incomplete run state and stderr are preserved and hashed in the R3.3 manifest. No development
label, prediction, or metric was inspected.

## Frozen correction

Only terminal task outcomes may carry `null` input-token, output-token, or duration accounting.
Non-terminal outcomes continue requiring complete non-negative numbers.

Operational summaries become explicit about incomplete accounting:

- the complete total is `null` if any included value is unavailable;
- the observed subtotal is reported separately;
- the number of unavailable values is reported separately.

This prevents unavailable model work from becoming a fabricated zero while preserving all observed
telemetry.

No prompt, provider, model, runtime, retry, correction, abstention, sample, threshold, label, or
metric-definition change is permitted. The exhausted request remains terminal and cannot execute
again.
