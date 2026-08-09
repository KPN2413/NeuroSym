# Phase 6-R3.2 Terminal Materialization Replay Amendment

## Trigger

The R3.1 materializer created the exhausted correction request's terminal cache envelope with zero
provider calls. A second zero-call invocation then rejected the cache because it compared the
post-materialization four-file inventory with the frozen three-success pre-materialization
inventory before checking for the terminal hit.

No model was running, no provider request occurred, and no development label, prediction, or metric
was inspected.

## Frozen correction

The exact interrupted request is reconstructed by its frozen request hash without depending on a
cache miss. When the terminal envelope already exists, its request binding and R3.2 evidence hashes
must validate, after which materialization returns `already_materialized` with the same terminal
outcome hash and zero provider calls.

The original three-success inventory remains mandatory only for the first materialization, when the
terminal entry is absent. The existing terminal cache file and materialization report are preserved
byte-for-byte and frozen in the R3.2 manifest.

No prompt, schema, model, runtime, correction policy, abstention policy, sample, threshold, metric,
or call budget changes. Another execution of the exhausted request remains forbidden.
