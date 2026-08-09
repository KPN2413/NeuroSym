"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import type {
  CapabilitiesResponse,
  InputMode,
  NaturalLanguageStatement,
  PipelineRequest,
  PipelineRunState,
  PolicyMode,
  StageName,
} from "@/lib/neurosymbolic-contract.generated";
import { isTerminalRun, resultTone, validateNaturalInput } from "@/lib/pipeline-ui";
import { FORMAL_PRESETS, NATURAL_PRESET } from "@/lib/presets";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

const PIPELINE_STEPS: Array<{ label: string; stages: StageName[] }> = [
  { label: "Parsing", stages: ["THEORY_PARSING", "QUERY_PARSING"] },
  { label: "Validation", stages: ["SOURCE_COVERAGE", "SEMANTIC_VALIDATION"] },
  { label: "Correction", stages: ["CRITIC", "CORRECTION"] },
  { label: "Reliability", stages: ["RELIABILITY_POLICY"] },
  { label: "Reasoning", stages: ["SYMBOLIC_REASONING"] },
  { label: "Proof check", stages: ["PROOF_VERIFICATION"] },
  { label: "Decision", stages: ["FINAL_DECISION"] },
];

type ApiMessage = { code?: string; message?: string };

export function NeuroSymbolicWorkbench() {
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [backendError, setBackendError] = useState(false);
  const [inputMode, setInputMode] = useState<InputMode>("NATURAL_LANGUAGE");
  const [policyMode, setPolicyMode] = useState<PolicyMode>("P2_SELECTIVE");
  const [statements, setStatements] = useState<NaturalLanguageStatement[]>(
    NATURAL_PRESET.statements,
  );
  const [query, setQuery] = useState(NATURAL_PRESET.query);
  const [formalJson, setFormalJson] = useState(
    JSON.stringify(FORMAL_PRESETS.ENTAILED, null, 2),
  );
  const [run, setRun] = useState<PipelineRunState | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const activeRunRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    const controller = new AbortController();
    void fetch(`${API_BASE_URL}/api/v1/neurosymbolic/capabilities`, {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("capabilities unavailable");
        return (await response.json()) as CapabilitiesResponse;
      })
      .then((value) => {
        if (mountedRef.current) {
          setCapabilities(value);
          setBackendError(false);
        }
      })
      .catch((error: Error) => {
        if (mountedRef.current && error.name !== "AbortError") setBackendError(true);
      });
    return () => {
      mountedRef.current = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!run || isTerminalRun(run.status)) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/neurosymbolic/runs/${run.run_id}`,
          { signal: controller.signal, cache: "no-store" },
        );
        if (response.status === 404) {
          setMessage("This run expired or the backend restarted. Submit it again.");
          activeRunRef.current = null;
          return;
        }
        if (!response.ok) throw new Error("poll failed");
        const next = (await response.json()) as PipelineRunState;
        setRun(next);
        if (isTerminalRun(next.status)) activeRunRef.current = null;
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setMessage("The backend became unavailable while polling.");
        }
      }
    }, 900);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [run]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (submitting || activeRunRef.current) return;
    setMessage(null);
    let payload: PipelineRequest;
    try {
      if (inputMode === "NATURAL_LANGUAGE") {
        const validation = validateNaturalInput(statements, query);
        if (validation) {
          setMessage(validation);
          return;
        }
        payload = {
          schema_version: "1.0",
          input_mode: inputMode,
          policy_mode: policyMode,
          natural_language: { statements, query: query.trim() },
          formal_ast: null,
        };
      } else {
        payload = {
          schema_version: "1.0",
          input_mode: inputMode,
          policy_mode: policyMode,
          natural_language: null,
          formal_ast: JSON.parse(formalJson) as PipelineRequest["formal_ast"],
        };
      }
    } catch {
      setMessage("Formal AST must be valid JSON matching the Phase 4 contract.");
      return;
    }
    setSubmitting(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/neurosymbolic/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await response.json()) as PipelineRunState & ApiMessage;
      if (!response.ok) {
        setMessage(
          body.code === "QUEUE_FULL"
            ? "The local model queue is full. Wait for the current run to finish."
            : body.message || "The run could not be submitted.",
        );
        return;
      }
      activeRunRef.current = body.run_id;
      setRun(body);
    } catch {
      setBackendError(true);
      setMessage("The backend is unavailable. Start FastAPI and try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function cancelRun() {
    if (!run || isTerminalRun(run.status)) return;
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/neurosymbolic/runs/${run.run_id}`,
        { method: "DELETE" },
      );
      if (response.ok) setRun((await response.json()) as PipelineRunState);
    } catch {
      setMessage("Cancellation could not reach the backend.");
    }
  }

  function reset() {
    activeRunRef.current = null;
    setRun(null);
    setMessage(null);
    setStatements(NATURAL_PRESET.statements);
    setQuery(NATURAL_PRESET.query);
    setFormalJson(JSON.stringify(FORMAL_PRESETS.ENTAILED, null, 2));
  }

  const busy = submitting || Boolean(run && !isTerminalRun(run.status));
  const result = run?.result;
  const tone = resultTone(result);

  return (
    <main className="min-h-screen bg-[#f4f0e8] text-[#17201d]">
      <header className="border-b border-[#17201d]/15 bg-[#f4f0e8]/95">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-4 px-5 py-4 lg:px-10">
          <div className="flex items-center gap-3">
            <span className="grid size-10 place-items-center rounded-full bg-[#173d35] font-mono text-sm font-bold text-[#f4f0e8]">
              VN
            </span>
            <div>
              <p className="font-semibold tracking-[-0.02em]">VeriLogic-NS</p>
              <p className="text-xs text-[#53625d]">Explainable neuro-symbolic reasoning</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`size-2 rounded-full ${backendError ? "bg-[#b5412c]" : "bg-[#218264]"}`}
              aria-hidden="true"
            />
            <span>{backendError ? "Backend offline" : "Local system"}</span>
            <span className="hidden rounded-full border border-[#17201d]/15 px-3 py-1.5 sm:inline">
              Phase 7
            </span>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1440px] gap-6 px-5 py-7 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)] lg:px-10">
        <section aria-labelledby="workbench-title">
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-[#9a5d2e]">
            Reasoning workbench
          </p>
          <h1 id="workbench-title" className="mt-3 max-w-2xl text-4xl font-semibold tracking-[-0.05em] sm:text-5xl">
            An answer you can trace back to its proof.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-[#53625d]">
            Natural language is parsed and reliability-gated before deterministic reasoning. Formal
            AST mode demonstrates the logic engine directly, with no model call.
          </p>

          <form onSubmit={submit} className="mt-7 rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5 shadow-[0_16px_50px_rgb(23_32_29_/_0.06)] sm:p-6">
            <fieldset disabled={busy}>
              <legend className="sr-only">Pipeline input mode</legend>
              <div className="grid grid-cols-2 rounded-xl bg-[#ebe6db] p-1">
                {(["NATURAL_LANGUAGE", "FORMAL_AST"] as InputMode[]).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setInputMode(mode)}
                    className={`rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#173d35] ${inputMode === mode ? "bg-[#fffdf8] shadow-sm" : "text-[#66736f]"}`}
                  >
                    {mode === "NATURAL_LANGUAGE" ? "Natural language" : "Formal AST · advanced"}
                  </button>
                ))}
              </div>

              <label className="mt-5 block text-sm font-medium" htmlFor="policy-mode">
                Reliability policy
              </label>
              <select
                id="policy-mode"
                value={policyMode}
                onChange={(event) => setPolicyMode(event.target.value as PolicyMode)}
                className="mt-2 w-full rounded-lg border border-[#17201d]/20 bg-white px-3 py-2.5 text-sm focus:border-[#173d35] focus:outline-none focus:ring-2 focus:ring-[#173d35]/20"
              >
                <option value="P2_SELECTIVE">P2 Selective · recommended</option>
                <option value="P1_CORRECTED">P1 Corrected · research mode</option>
                <option value="P0_RAW">P0 Raw · diagnostic mode</option>
              </select>

              {inputMode === "NATURAL_LANGUAGE" ? (
                <NaturalEditor statements={statements} onChange={setStatements} query={query} onQuery={setQuery} />
              ) : (
                <FormalEditor value={formalJson} onChange={setFormalJson} />
              )}
            </fieldset>

            {message && (
              <p role="alert" className="mt-4 rounded-lg border border-[#b5412c]/25 bg-[#fff1ec] px-3 py-2.5 text-sm text-[#8f2f1f]">
                {message}
              </p>
            )}

            {inputMode === "NATURAL_LANGUAGE" && capabilities && !capabilities.local_model_ready && capabilities.provider_mode === "live" && (
              <p className="mt-4 rounded-lg border border-[#b37b2c]/30 bg-[#fff7df] px-3 py-2.5 text-sm text-[#765016]">
                The exact local Ollama model is not ready. Formal mode remains available.
              </p>
            )}

            <div className="mt-5 flex flex-wrap gap-2">
              <button
                type="submit"
                disabled={busy || backendError}
                className="rounded-lg bg-[#173d35] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#0f2f28] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#173d35] disabled:cursor-not-allowed disabled:opacity-45"
              >
                {submitting ? "Submitting…" : busy ? "Pipeline running…" : "Run verification"}
              </button>
              <button
                type="button"
                onClick={cancelRun}
                disabled={!busy || submitting}
                className="rounded-lg border border-[#17201d]/20 px-4 py-2.5 text-sm font-medium disabled:opacity-40"
              >
                Cancel
              </button>
              <button type="button" onClick={reset} disabled={busy} className="rounded-lg px-4 py-2.5 text-sm font-medium text-[#53625d] disabled:opacity-40">
                Reset
              </button>
            </div>
          </form>
        </section>

        <section aria-label="Pipeline output" className="space-y-5 lg:pt-2">
          <PipelineProgress run={run} />
          {result ? (
            <ResultPanel result={result} tone={tone} />
          ) : (
            <div className="grid min-h-80 place-items-center rounded-2xl border border-dashed border-[#17201d]/20 bg-[#fffdf8]/55 p-8 text-center">
              <div>
                <div className="mx-auto grid size-14 place-items-center rounded-full border border-[#17201d]/15 bg-white font-mono text-xl">∴</div>
                <h2 className="mt-4 text-lg font-semibold">Ready for a verified result</h2>
                <p className="mt-2 max-w-sm text-sm leading-6 text-[#66736f]">
                  Run a preset or enter your own controlled facts, rules, and query. No confidence percentage will be invented.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function NaturalEditor({
  statements,
  onChange,
  query,
  onQuery,
}: {
  statements: NaturalLanguageStatement[];
  onChange: (value: NaturalLanguageStatement[]) => void;
  query: string;
  onQuery: (value: string) => void;
}) {
  function update(index: number, patch: Partial<NaturalLanguageStatement>) {
    onChange(statements.map((item, itemIndex) => (itemIndex === index ? { ...item, ...patch } : item)));
  }
  return (
    <div className="mt-6">
      <div className="flex items-center justify-between gap-4">
        <label className="text-sm font-medium">Theory statements</label>
        <button
          type="button"
          onClick={() =>
            onChange([
              ...statements,
              { source_id: `source_${statements.length + 1}`, kind: "fact", text: "" },
            ])
          }
          className="text-sm font-semibold text-[#216554]"
        >
          + Add statement
        </button>
      </div>
      <div className="mt-2 space-y-2">
        {statements.map((statement, index) => (
          <div key={`${statement.source_id}-${index}`} className="grid gap-2 rounded-xl border border-[#17201d]/15 bg-white p-3 sm:grid-cols-[88px_1fr_auto]">
            <select
              aria-label={`Statement ${index + 1} type`}
              value={statement.kind}
              onChange={(event) => update(index, { kind: event.target.value as "fact" | "rule" })}
              className="rounded-md border border-[#17201d]/15 bg-[#f7f4ed] px-2 py-2 text-xs font-medium"
            >
              <option value="fact">Fact</option>
              <option value="rule">Rule</option>
            </select>
            <textarea
              aria-label={`Statement ${index + 1}`}
              rows={2}
              value={statement.text}
              onChange={(event) => update(index, { text: event.target.value })}
              className="resize-y rounded-md border-0 bg-transparent px-1 py-1.5 text-sm leading-6 outline-none focus:ring-2 focus:ring-[#173d35]/20"
            />
            <button
              type="button"
              aria-label={`Remove statement ${index + 1}`}
              onClick={() => onChange(statements.filter((_, itemIndex) => itemIndex !== index))}
              className="self-start rounded-md px-2 py-1.5 text-[#8f2f1f] hover:bg-[#fff1ec]"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <label className="mt-5 block text-sm font-medium" htmlFor="query">
        Query
      </label>
      <textarea
        id="query"
        rows={2}
        value={query}
        onChange={(event) => onQuery(event.target.value)}
        className="mt-2 w-full resize-y rounded-lg border border-[#17201d]/20 bg-white px-3 py-2.5 text-sm leading-6 focus:border-[#173d35] focus:outline-none focus:ring-2 focus:ring-[#173d35]/20"
      />
    </div>
  );
}

function FormalEditor({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="mt-6">
      <label className="block text-sm font-medium" htmlFor="formal-preset">Formal preset</label>
      <select
        id="formal-preset"
        onChange={(event) =>
          onChange(JSON.stringify(FORMAL_PRESETS[event.target.value as keyof typeof FORMAL_PRESETS], null, 2))
        }
        className="mt-2 w-full rounded-lg border border-[#17201d]/20 bg-white px-3 py-2.5 text-sm"
      >
        {Object.keys(FORMAL_PRESETS).map((name) => (
          <option key={name}>{name}</option>
        ))}
      </select>
      <label className="mt-5 block text-sm font-medium" htmlFor="formal-json">Theory AST and query</label>
      <textarea
        id="formal-json"
        rows={16}
        spellCheck={false}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-2 w-full resize-y rounded-lg border border-[#17201d]/20 bg-[#14211e] px-4 py-3 font-mono text-xs leading-5 text-[#d9eee7] focus:outline-none focus:ring-2 focus:ring-[#218264]/50"
      />
    </div>
  );
}

function PipelineProgress({ run }: { run: PipelineRunState | null }) {
  const resultTrace = run?.result?.trace ?? [];
  return (
    <div className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold">Pipeline progress</h2>
        <span className="font-mono text-xs text-[#66736f]">{run?.status ?? "NOT STARTED"}</span>
      </div>
      <ol className="mt-4 grid grid-cols-4 gap-2 sm:grid-cols-7">
        {PIPELINE_STEPS.map((step, index) => {
          const traces = resultTrace.filter((item) => step.stages.includes(item.stage));
          const failed = traces.some((item) => ["FAILED", "ABSTAINED"].includes(item.status));
          const done = traces.length > 0 && traces.every((item) => ["SUCCEEDED", "SKIPPED"].includes(item.status));
          const current = step.stages.includes(run?.current_stage as StageName);
          return (
            <li key={step.label} className="min-w-0">
              <div className={`h-1.5 rounded-full ${failed ? "bg-[#b5412c]" : done ? "bg-[#218264]" : current ? "animate-pulse bg-[#d28a3d]" : "bg-[#ddd7ca]"}`} />
              <p className="mt-2 truncate text-[11px] text-[#66736f]">{index + 1}. {step.label}</p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ResultPanel({ result, tone }: { result: NonNullable<PipelineRunState["result"]>; tone: string }) {
  const toneClasses: Record<string, string> = {
    entailed: "border-[#218264]/30 bg-[#eaf6f1] text-[#155a45]",
    contradicted: "border-[#b5412c]/30 bg-[#fff0eb] text-[#8f2f1f]",
    unknown: "border-[#b37b2c]/35 bg-[#fff7df] text-[#765016]",
    inconsistent: "border-[#814ea0]/30 bg-[#f7edff] text-[#683982]",
    abstained: "border-[#66736f]/30 bg-[#eef1ef] text-[#3e4a46]",
    error: "border-[#b5412c]/30 bg-[#fff0eb] text-[#8f2f1f]",
    neutral: "border-[#17201d]/15 bg-white text-[#17201d]",
  };
  return (
    <div className="space-y-5">
      <article className={`rounded-2xl border p-6 ${toneClasses[tone] ?? toneClasses.neutral}`}>
        <p className="font-mono text-xs font-semibold uppercase tracking-[0.16em]">{result.disposition}</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em]">{result.logical_result ?? result.explanation.headline}</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6">{result.explanation.summary}</p>
        {result.abstention_reason && <p className="mt-4 font-mono text-xs">Reason: {result.abstention_reason}</p>}
        {result.error && <p className="mt-4 font-mono text-xs">{result.error.stage} · {result.error.code}</p>}
      </article>

      <article className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <h3 className="font-semibold">Verified explanation</h3>
          <span className="rounded-full bg-[#e8eee9] px-3 py-1 font-mono text-[10px] font-semibold">{result.explanation.verifier_status}</span>
        </div>
        {result.explanation.steps.length ? (
          <ol className="mt-5 space-y-4">
            {result.explanation.steps.map((step) => (
              <li key={step.node_id} className="grid grid-cols-[28px_1fr] gap-3">
                <span className="grid size-7 place-items-center rounded-full bg-[#173d35] font-mono text-xs text-white">{step.sequence}</span>
                <div>
                  <p className="text-sm font-medium leading-6">{step.statement}</p>
                  <p className="mt-1 text-xs leading-5 text-[#66736f]">Source {step.source_id}: “{step.source_text}” · depth {step.depth}</p>
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 text-sm leading-6 text-[#66736f]">No proof steps are claimed for this outcome.</p>
        )}
        {result.explanation.proof_hash && <p className="mt-5 break-all border-t border-[#17201d]/10 pt-4 font-mono text-[10px] text-[#66736f]">Proof {result.explanation.proof_hash}</p>}
      </article>

      <details className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5">
        <summary className="cursor-pointer text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#173d35]">Technical trace, provenance and proof DAG</summary>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#66736f]">Stage trace</h4>
            <ul className="mt-2 space-y-1 font-mono text-[10px]">
              {result.trace.map((item) => <li key={item.stage} className="flex justify-between gap-3"><span>{item.stage}</span><span>{item.status}</span></li>)}
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-[#66736f]">Provenance</h4>
            <pre className="mt-2 max-h-72 overflow-auto rounded-lg bg-[#14211e] p-3 text-[10px] leading-5 text-[#d9eee7]">{JSON.stringify(result.provenance, null, 2)}</pre>
          </div>
        </div>
        <pre className="mt-4 max-h-96 overflow-auto rounded-lg bg-[#14211e] p-3 text-[10px] leading-5 text-[#d9eee7]">{JSON.stringify(result.proof, null, 2)}</pre>
      </details>
    </div>
  );
}
