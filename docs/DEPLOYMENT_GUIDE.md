# Local Production and Demonstration Deployment

## Deployment model

Phase 10 uses a reproducible local production/demo deployment. It does not expose the backend to a
public network, create a cloud resource, copy the ProofWriter archive, or require a paid provider.
The verified provider mode is `cache_only`; formal reasoning and the research dashboard work with
Ollama stopped.

## System requirements

- Windows 10/11, Linux, or macOS capable of running Python and Node.js
- Python 3.11 or newer (verified here with Python 3.13.7)
- Node.js 20.9 or newer (verified here with Node.js 24.13.0)
- Corepack and pnpm 9.15.4
- Git
- Optional: Ollama 0.32.1 and the exact `qwen3.5:4b-q4_K_M` digest for natural-language live mode
- Optional: Docker with Compose v2 (not installed on the Phase 10 verification machine)

Default loopback ports:

| Service | Origin | Required for the final provider-free demo |
|---|---|---|
| Frontend | `http://127.0.0.1:3000` | Yes |
| Backend | `http://127.0.0.1:8000` | Yes |
| Ollama | `http://127.0.0.1:11434` | No |

## Installation

From the repository root, create and populate the isolated backend environment:

```powershell
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install --upgrade pip
backend\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
```

Install the frontend exactly from the tracked lock file:

```powershell
Set-Location frontend
corepack pnpm install --frozen-lockfile
Set-Location ..
```

Do not use npm, Yarn, or Bun for this repository.

## Environment setup

The tracked examples contain no secret:

- root `.env.example` documents Compose/local defaults;
- `backend/.env.example` documents FastAPI settings;
- `frontend/.env.example` documents the browser-visible API origin.

For the verified local production flow, set these values in the shell before starting services:

```powershell
$env:VERILOGIC_CORS_ORIGINS='["http://127.0.0.1:3000"]'
$env:VERILOGIC_ORCHESTRATION_PROVIDER_MODE='cache_only'
$env:VERILOGIC_ORCHESTRATION_QUEUE_SIZE='3'
$env:VERILOGIC_ORCHESTRATION_RETENTION_SECONDS='1800'
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
```

`NEXT_PUBLIC_API_BASE_URL` is embedded during `pnpm build`; rebuild after changing it. Do not place
API keys or provider credentials in `NEXT_PUBLIC_*` variables.

## Evidence and deployment preflight

Run from the repository root:

```powershell
backend\.venv\Scripts\python.exe -m verilogic_ns_api.phase10 export-evidence --check
backend\.venv\Scripts\python.exe -m verilogic_ns_api.phase10 export-schema --check
backend\.venv\Scripts\python.exe -m verilogic_ns_api.phase10 validate-deployment
backend\.venv\Scripts\python.exe -m verilogic_ns_api.phase10 validate-deliverables
```

These commands do not call a provider or access the test split.

## Backend production startup

Open terminal 1 at the repository root:

```powershell
$env:VERILOGIC_CORS_ORIGINS='["http://127.0.0.1:3000"]'
$env:VERILOGIC_ORCHESTRATION_PROVIDER_MODE='cache_only'
backend\.venv\Scripts\python.exe -m uvicorn verilogic_ns_api.main:app --host 127.0.0.1 --port 8000
```

Do not add `--reload` for the production/demo process.

Health and capability checks:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/neurosymbolic/capabilities
Invoke-RestMethod http://127.0.0.1:8000/api/v1/research/catalogue
```

Expected: health `ok`, symbolic engine ready, provider mode `cache_only`, 19 experiments, and 10
comparisons.

## Frontend production build and startup

Open terminal 2 at the repository root:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
Set-Location frontend
corepack pnpm build
Copy-Item -Recurse -Force public .next\standalone\public
New-Item -ItemType Directory -Force .next\standalone\.next | Out-Null
Copy-Item -Recurse -Force .next\static .next\standalone\.next\static
$env:HOSTNAME='127.0.0.1'
$env:PORT='3000'
node .next\standalone\server.js
```

The two copy steps mirror the final Docker image layout. They are required for the local standalone
server to serve client bundles and hydrate interactive pages; all copied files remain under the
ignored `.next/` build directory.

Open:

- `http://127.0.0.1:3000/` — neuro-symbolic workbench
- `http://127.0.0.1:3000/research` — research evidence dashboard

## Ollama and the required model

Ollama is not needed for the final provider-free demo. To intentionally enable natural-language
live mode in a separate research session, use only loopback Ollama 0.32.1 with:

- model: `qwen3.5:4b-q4_K_M`
- digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`
- `think: false`, temperature 0

Then start the backend with `VERILOGIC_ORCHESTRATION_PROVIDER_MODE=live`. If the exact runtime is
absent, the API returns `LOCAL_MODEL_UNAVAILABLE`; formal mode and `/research` remain available.
Do not substitute another model under the frozen Phase 9 identity.

## Automated demo smoke

With both production processes running:

```powershell
backend\.venv\Scripts\python.exe -m verilogic_ns_api.phase10 demo-smoke
```

The command accepts only loopback ports 8000 and 3000. It verifies liveness, capabilities,
catalogue/detail/export endpoints, frontend routes, CORS, and one formal `ENTAILED` run with a
verified proof, deterministic explanation, and zero provider dispatches. Its local JSON report is
written atomically under ignored `results/phase10/`.

## Shutdown

Press `Ctrl+C` once in the frontend terminal and once in the backend terminal. No database or
external resource needs cleanup. If Ollama was started separately, stop it through its normal local
application controls.

## Docker configuration

The repository includes separate non-root backend/frontend Dockerfiles and Compose health checks.
Phase 10 statically validates its YAML, ports, service boundary, health checks, cache-only default,
and absence of provider secrets/model mounts. Docker is not installed on the verification machine,
so these commands are documented but runtime-unverified here:

```text
docker compose config
docker compose up --build
```

Do not report them as passed until run on a host with Docker Compose v2.

## Troubleshooting

| Symptom | Check | Resolution |
|---|---|---|
| Backend does not start | Port 8000 and backend virtual environment | Stop the conflicting local process; reinstall only in `backend/.venv` |
| Frontend says backend offline | `NEXT_PUBLIC_API_BASE_URL` build-time value | Set it to `http://127.0.0.1:8000`, rebuild, and restart |
| Browser reports CORS error | `VERILOGIC_CORS_ORIGINS` | Use the exact frontend origin including scheme and port |
| Natural-language request returns 503 | Capabilities `local_model_ready` | Start the exact Ollama model or use formal mode; do not downgrade the error |
| `/research` fails | Catalogue/source hashes | Run `research_frontend validate-catalogue`; do not edit evidence to bypass integrity checks |
| Export hash mismatch | Backend catalogue integrity | Stop the demo and rerun the full evidence validation gate |
| Formal run does not complete | Backend log and bounded queue | Retry after the active local job completes; do not start parallel workers |

## Known limitations

This is a single-machine research deployment: no authentication, database, durable job queue,
multi-process coordination, public rate limiting, TLS termination, production monitoring, or cloud
service-level objective is claimed. Public deployment was not authorized. ProofWriter raw data,
model weights, caches, and provider responses remain local and ignored.
