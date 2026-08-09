# Phase 6-R3.5 Legacy Zero Accounting Interpretation Amendment

## Trigger

Final terminal-accounting consolidation found two sealed correction outcomes with
`finish_reason=provider_error` and zero token and duration fields. In both cases, the provider
failed while converting its response to the required JSON structure, before a `ParserResponse`
and its telemetry were available. The zeroes therefore meant “unavailable,” not observed zero
model work.

## Frozen interpretation

The two cache artifacts and their canonical hashes remain unchanged. When a legacy terminal
outcome has zero aggregate tokens and duration and at least one attempt has
`finish_reason=provider_error`, downstream task accounting interprets all three values as
unavailable. Future failures at this boundary record null accounting directly. A genuine observed
zero without the provider-error marker remains zero.

This amendment changes reporting only. It was frozen after predictions were sealed and metrics
were examined, was not selected for performance, and does not change any prediction, decision,
proof, abstention, prompt, model setting, policy, or metric. Final verification must be a
zero-provider-call replay with Ollama stopped.
