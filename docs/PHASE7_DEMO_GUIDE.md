# Phase 7 Demonstration Guide

This demo shows logical verification relative to supplied premises. It does not establish that the
premises are true, and the local neural parser can be wrong.

## Start locally

Install the documented backend/frontend dependencies, then start the backend from `backend/` and
the frontend from `frontend/`:

```text
python -m uvicorn verilogic_ns_api.main:app --host 127.0.0.1 --port 8000
pnpm dev
```

The default backend mode is `cache_only`. Formal AST examples work with Ollama stopped. Natural
language needs either complete Phase 7 cache entries or a live, exact local Ollama model configured
through `VERILOGIC_ORCHESTRATION_PROVIDER_MODE=live`.

## Recommended formal demonstration

1. Open `http://127.0.0.1:3000`.
2. Confirm backend connected, symbolic engine ready, and provider mode displayed.
3. Choose Formal AST and run the Entailed preset.
4. Observe the ordered stage trace, `ANSWERED / ENTAILED`, verified proof steps, source links,
   proof hash, and zero provider dispatches.
5. Repeat with Contradicted, Unknown, and Inconsistent.
6. Submit the same preset again and confirm the scientific fields and proof hash remain stable.

The equivalent command-line smoke is:

```text
python -m verilogic_ns_api.orchestration run --formal-theory examples/theories/entailed.json --provider-mode cache_only
```

## Natural-language demonstration

Use the Robin preset only after explaining that it tests integration, not model quality. The frozen
Phase 7 run completed safely and reproducibly but the local 4B parser produced `UNKNOWN` instead of
the expected entailment. Do not change the prompt, policy, or input to conceal that negative result.

## Manual browser checklist

- Keyboard focus is visible and every input has a label.
- Natural/Formal and P0/P1/P2 controls update the submitted request.
- Fact/rule rows can be added, removed, reordered, and reset.
- Loading, queued/running, answered, abstained, error, cancellation, and backend-disconnected states
  remain readable without color alone.
- Proof, explanation, provenance, and raw JSON sections render only real API data.
- Narrow viewport layout does not overflow horizontally.
- Browser console contains no application errors.
- Polling stops after a terminal outcome and does not create another run.

Automated browser control was unavailable during Phase 7 verification, so this checklist accompanies
HTTP endpoint smoke tests, component logic tests, lint, type checking, and the production build. It
must be executed in a browser before a public presentation.
