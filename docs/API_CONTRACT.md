# Neuro-Symbolic API Contract

The stable Phase 7 prefix is `/api/v1/neurosymbolic`. OpenAPI and the six versioned JSON Schemas are
generated from the strict Pydantic models and checked into `schemas/`. The frontend TypeScript
contract is generated from the same source and must pass the schema freshness check.

## Endpoints

| Method and path | Success | Purpose |
|---|---:|---|
| `POST /api/v1/neurosymbolic/runs` | `202` | Validate and enqueue one version `1.0` request |
| `GET /api/v1/neurosymbolic/runs/{run_id}` | `200` | Read queued, running, or terminal state without doing work |
| `DELETE /api/v1/neurosymbolic/runs/{run_id}` | `200` | Cancel a queued job or request cancellation of active work |
| `GET /api/v1/neurosymbolic/capabilities` | `200` | Report modes, policies, model readiness, limits, and schema hashes |
| `GET /health` | `200` | Preserve the existing service health contract |

The run resource moves through `QUEUED`, `RUNNING`, `COMPLETED`, `FAILED`,
`CANCEL_REQUESTED`, or `CANCELLED`. A completed pipeline may have disposition `ANSWERED`,
`ABSTAINED`, or `ERROR`; transport state and scientific outcome are deliberately separate.

## Request boundary

Unknown fields are rejected. `input_mode` must match exactly one payload:

```json
{
  "schema_version": "1.0",
  "input_mode": "NATURAL_LANGUAGE",
  "policy_mode": "P2_SELECTIVE",
  "natural_language": {
    "statements": [
      {"source_id": "source_1", "kind": "fact", "text": "The robin is red."},
      {"source_id": "source_2", "kind": "rule", "text": "If something is red, then it is warm."}
    ],
    "query": "The robin is warm."
  }
}
```

Formal requests use `formal_ast` with the versioned `Theory` and a ground `query`; the checked
examples in `examples/theories/` can be submitted through the CLI without manually building this
wrapper.

## Errors and availability

- `422` rejects invalid request data using a flat, sanitized `ApiErrorResponse`.
- `429` reports `QUEUE_FULL` without starting work.
- `503` reports `LOCAL_MODEL_UNAVAILABLE` only for natural-language live requests; formal input
  remains available without Ollama.
- `404` reports `RUN_NOT_FOUND` for unknown or expired run IDs.

CORS is restricted to configured local origins and supports only the required methods. Responses do
not expose stack traces, host paths, raw provider payloads, credentials, or model thinking. The API
is an unauthenticated local research interface, not a hardened public multi-user service.

## Contract maintenance

Run from the repository root with the backend environment active:

```text
python -m verilogic_ns_api.orchestration export-schemas --check
```

Any breaking field or meaning change requires a new schema/API version and a decision record. The
checked OpenAPI artifact is `schemas/openapi.v1.json`; frontend consumers import only the generated
contract rather than duplicating backend enums by hand.
