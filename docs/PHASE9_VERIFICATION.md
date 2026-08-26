# Phase 9 Verification

## Approval

**Status: PASS**

Phase 9 completed the separately frozen, development-only evidence regeneration. All seven
conditions used the same 30 ProofWriter OWA development selections; the few-shot condition used
only the six frozen training demonstrations. Historical Phase 1–8 evidence remains unchanged.
This report and every new catalogue entry are labelled **Phase 9 regenerated evidence under newly
frozen protocol**.

The evidence is a small development experiment. It is not a test-set result, a significance claim,
or a state-of-the-art claim. The ProofWriter licence remains unverified, and the archive checksum
is locally observed rather than publisher-verified.

## Frozen protocol and recovery

| Item | Frozen value |
|---|---|
| Parent checkpoint | `53e2426` |
| Preregistration commit | `8cd4ea486fe6accaa75773c3ba2749d62328a9b0` |
| Execution implementation | `a7c3908b0ec12c0512a2a93e814271abe0604b38` |
| Freeze hash | `c7039474c7f4522767a747deb384fa0ee9e05e450fb7a108d3b2001b36b4719e` |
| Dataset | ProofWriter V2020.12.3, OWA depth-5, development only |
| Archive SHA-256 | `bbc5694901e8306d0bd659aa1ad53ccfd02c201864f4b320ffa3777827d1fc26` |
| Archive size | 214,185,889 bytes |
| Selection seed | 20260818 |
| Development selection | 30 records; 2 for each depth 0/1/2/3/5 × label cell |
| Selection-manifest hash | `cbc6da95e679a3959b59a311cf5137792fce623f9e425361c6c8b5f35302a16c` |
| Demonstrations | 6 training records; 2 per label; train/development overlap 0 |
| Demonstration-manifest hash | `214c2b46b81297a8a33891a76572aaf92ad90f95e240ee0db18cd4254d600a47` |
| Local runtime | Ollama 0.32.1, CPU, `think: false`, temperature 0 |
| Model | `qwen3.5:4b-q4_K_M` |
| Model digest | `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd` |

The recovery audit found the interrupted Direct condition already complete: 30/30 records were
valid, with no incomplete, failed, corrupt, or not-started records. Zero Direct records were
redispatched. No cache corruption was found. The verified archive and all valid per-record caches
were reused.

## Regenerated results

Accuracy uses all 30 selected records. Answered-only accuracy is reported separately so abstained
or failed records cannot disappear from the denominator.

| Condition | Correct / 30 | Accuracy | Macro F1 | Answered | Abstained | Error | Coverage | Answered-only accuracy | Verified proofs |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Direct | 16 | 0.5333 | 0.5310 | 30 | 0 | 0 | 1.0000 | 0.5333 | NA |
| Few-shot | 16 | 0.5333 | 0.5405 | 30 | 0 | 0 | 1.0000 | 0.5333 | NA |
| P0 raw neuro-symbolic | 4 | 0.1333 | 0.2145 | 5 | 0 | 25 | 0.1667 | 0.8000 | 5/5 |
| Validation-only | 4 | 0.1333 | 0.2145 | 5 | 25 | 0 | 0.1667 | 0.8000 | 5/5 |
| P1 corrected-valid | 2 | 0.0667 | 0.1212 | 3 | 23 | 4 | 0.1000 | 0.6667 | 3/3 |
| P2 corrected-selective | 1 | 0.0333 | 0.0606 | 1 | 25 | 4 | 0.0333 | 1.0000 | 1/1 |
| Symbolic oracle ceiling | 30 | 1.0000 | 1.0000 | 30 | 0 | 0 | 1.0000 | 1.0000 | 30/30 |

P0 failures were retained as 25 `ERROR` outcomes. Validation-only deterministically changed those
same 25 unusable formalizations to `ABSTAIN`, without changing the five answered predictions. P1
and P2 did not improve overall accuracy or coverage on this frozen sample. P2's perfect
answered-only accuracy applies to one answered record and must be read with 1/30 coverage.

The parser accepted five complete theories/queries; four of those five answers were correct and all
five proofs verified. The parser error taxonomy was 14 semantic-invalid, 8 incomplete-source-
coverage, and 3 structured-output failures. Exact theory matching was 1/30 and exact query matching
was 3/30.

The correction run made 31 correction attempts. Four were semantically recovered, giving a
4/31 observed correction success rate. Four regressions and four no-progress outcomes were
retained. The critic evaluated 33 cases; its observed precision was 1.0, recall 0.1, and F1 0.1818.
Three correction/critic cache outcomes were typed terminal failures; they remain visible in the
controller evidence and were not replaced or removed.

## Comparisons

| Registered comparison | Both correct | Baseline only | Changed only | Both incorrect | Accuracy delta | Coverage delta | Interpretation |
|---|---:|---:|---:|---:|---:|---:|---|
| Direct → few-shot | 14 | 2 | 2 | 12 | 0.0000 | 0.0000 | Paired descriptive effect only |
| P0 → validation-only | 4 | 0 | 0 | 26 | 0.0000 | 0.0000 | 25 errors became abstentions |
| P0 → P1 | 1 | 3 | 1 | 25 | -0.0667 | -0.0667 | Paired component ablation |
| P1 → P2 | 1 | 1 | 0 | 28 | -0.0333 | -0.0667 | Paired selective-gate ablation |
| P2 → oracle | 1 | 0 | 29 | 0 | +0.9667 | +0.9667 | Same selection, different representation; ceiling only |

The oracle receives dataset-provided formal structure, so it is not a paired natural-language
system comparison even though it uses the same 30 selections.

## Local calls, tokens and timing

The physical local-provider dispatch count was 190: Direct 30, few-shot 30, parser 60, and
correction/critic 70. Hosted calls, external transfers, and API cost were all zero.

| Condition | Exact input tokens | Exact output tokens | Observed lower-bound input | Observed lower-bound output | Observed runtime seconds |
|---|---:|---:|---:|---:|---:|
| Direct | 10,711 | 351 | 10,711 | 351 | 456.3293 |
| Few-shot | 48,301 | 243 | 48,301 | 243 | 7,016.0951 |
| P0 / validation-only | 39,562 | 34,277 | 39,562 | 34,277 | 5,344.8447 |
| P1 / P2 | NA | NA | 127,252 | 62,249 | 12,472.0325 |
| Oracle | 0 | 0 | 0 | 0 | 0.5645 |

P1/P2 exact totals are unavailable because two terminal correction cache outcomes do not contain
complete usage telemetry. Their observed counts are partial lower bounds, not exact totals.

## Replay and evidence integrity

Ollama was stopped before replay. Direct and few-shot each resolved 30/30 cache hits with zero
misses and zero inference calls. Parser replay resolved 60/60 hits. Correction replay resolved all
60 raw-parser references and 70 correction/critic cache entries, with zero new calls. Scientific
per-example fields and canonical fingerprints matched the live runs.

Tracked evidence:

- aggregate report: `research/evidence/phase9-regenerated-aggregate.v1.json`;
- aggregate fingerprint: `30146ca1a9cae630b18a96607c7c0a32173f6590631fc470c9c61cc22c5c26b1`;
- aggregate JSON Schema: `schemas/phase9-aggregate-report.v1.schema.json`;
- extended catalogue: `research/catalogues/phase1-9-evidence.v2.json`;
- catalogue hash: `b849a0d00c683a39a4df3583dec18793aad14d8754b795e4cacc07308be64c73`;
- catalogue contents: 19 experiment conditions and 10 registered comparisons.

The historical v1 catalogue is byte-for-byte unchanged. Its canonical Phase 8 hash remains
`6908ff69506907551ec4e20e2e52aed44ddf3b3826b01cdaf61ceb7df1566842` and its file SHA-256 remains
`ee57f84c4d4b160b8dd7330a35cc30cc3a46e04e5acd5fb87ff5c092627c5863`.

Raw Phase 9 evidence remains ignored. Condition raw-record SHA-256 values are retained in the
sanitized aggregate. The Direct and few-shot raw JSONL hashes are respectively
`6e55bc6f164422a85e4066688e24800e08714b702fa9ae686e3aea84e4280fbd` and
`7734b508a2b29fb3b491f08b5c72dc6b24b54072c83641047782070026f14ea1`.

## Safety and limitations

- Test-split access count: 0.
- Hosted-provider calls: 0.
- External transfers: 0.
- API cost: USD 0.00.
- Model thinking was neither requested nor retained.
- Historical caches were not reconstructed and historical metrics were not rewritten.
- The new catalogue preserves the original Phase 1–7 catalogue unchanged and appends separately
  labelled Phase 9 evidence through a new version.
- The experiment is development-only with 30 examples; no statistical significance or
  generalisation claim is supported.
- The local 4B semantic parser remains the main end-to-end quality bottleneck.

## Final repository verification

The first full backend run found one stale generated `openapi.v1.json` after the research overview
gained Phase 9 call/cost fields: 359/360 tests passed. The canonical orchestration exporter
regenerated OpenAPI from FastAPI/Pydantic source; no generated contract was hand-edited. The
targeted freshness test then passed. A later Phase 8 compatibility audit identified that the
expanded model changed the historical v1 canonical projection despite unchanged file bytes. The
v1 projection was restored and protected by a regression test.

Final gates:

- backend dependency integrity, Ruff lint and Ruff format: passed;
- backend pytest: 361 passed, zero failed, with one upstream Starlette/httpx deprecation warning;
- frontend: 11 tests passed; ESLint, TypeScript and Next.js production build passed;
- Phase 4 reasoning regression: 89 tests passed; retained 300/300 and same-30 conformance evidence
  remains hash-validated;
- Phase 6/R3 regression: 60 tests passed without changing historical evaluator behavior;
- Phase 7 regression: 17 tests passed; four fresh provider-free formal canaries returned
  `ENTAILED`, `CONTRADICTED`, `UNKNOWN` and `INCONSISTENT`, each with a verified proof and zero
  provider dispatches;
- Phase 8 catalogue/API/export regression: 21 tests passed; v1 identity remained immutable;
- dataset inspection, evaluation smoke, direct/few-shot fake-provider smoke, reasoning smoke, all
  CLI help commands, schema freshness and deterministic JSON/CSV/Markdown exports passed;
- Docker Compose parsing was skipped because Docker is not installed on this machine.

Security scans found no secret-shaped token, personal absolute path, tracked raw/cache file,
tracked model weight, tracked dependency directory or Phase 9 test-split record. The only
non-loopback URL in frozen Phase 9 artifacts is the recorded public ProofWriter archive source, not
an inference provider. `.gitignore` was verified for the archive, raw Phase 9 JSONL, caches, model
build/dependency directories and deterministic local exports.
