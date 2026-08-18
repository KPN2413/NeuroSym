"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import type {
  CatalogueOverview,
  ComparisonCompatibility,
  ExperimentDetail,
  ExperimentSummary,
  NormalizedAstInspection,
} from "@/lib/research-contract.generated";
import {
  attritionStages,
  compatibleComparison,
  filterExperiments,
  formatMetric,
  metricValue,
  primaryMetric,
  type ResearchFilters,
} from "@/lib/research-ui";
import { FORMAL_PRESETS } from "@/lib/presets";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

const EMPTY_FILTERS: ResearchFilters = {
  phase: "",
  status: "",
  model: "",
  condition: "",
  policy: "",
  dataset: "",
  split: "",
  depth: "",
  label: "",
};

export function ResearchDashboard() {
  const [overview, setOverview] = useState<CatalogueOverview | null>(null);
  const [comparisons, setComparisons] = useState<ComparisonCompatibility[]>([]);
  const [details, setDetails] = useState<Record<string, ExperimentDetail>>({});
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [leftId, setLeftId] = useState("phase3-direct");
  const [rightId, setRightId] = useState("phase3-few-shot");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ast, setAst] = useState<NormalizedAstInspection | null>(null);
  const [astError, setAstError] = useState<string | null>(null);
  const [astLoading, setAstLoading] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        setLoading(true);
        const [catalogueResponse, comparisonsResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/v1/research/catalogue`, {
            cache: "no-store",
            signal: controller.signal,
          }),
          fetch(`${API_BASE_URL}/api/v1/research/comparisons`, {
            cache: "no-store",
            signal: controller.signal,
          }),
        ]);
        if (!catalogueResponse.ok || !comparisonsResponse.ok) {
          throw new Error("The evidence API returned an invalid response.");
        }
        const catalogue = (await catalogueResponse.json()) as CatalogueOverview;
        const comparisonItems =
          (await comparisonsResponse.json()) as ComparisonCompatibility[];
        const detailEntries = await Promise.all(
          catalogue.experiments.map(async (experiment) => {
            const response = await fetch(
              `${API_BASE_URL}/api/v1/research/experiments/${experiment.experiment_id}`,
              { cache: "no-store", signal: controller.signal },
            );
            if (!response.ok) throw new Error("An experiment record could not be verified.");
            return [experiment.experiment_id, (await response.json()) as ExperimentDetail] as const;
          }),
        );
        setOverview(catalogue);
        setComparisons(comparisonItems);
        setDetails(Object.fromEntries(detailEntries));
        setError(null);
      } catch (caught) {
        if ((caught as Error).name !== "AbortError") {
          setError("Research evidence is unavailable. Start the verified backend and try again.");
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, []);

  const experiments = useMemo(() => overview?.experiments ?? [], [overview]);
  const filtered = useMemo(
    () => filterExperiments(experiments, filters, details),
    [details, experiments, filters],
  );
  const relation = compatibleComparison(comparisons, leftId, rightId);
  const phase5 = details["phase5-hybrid"];

  async function inspectSyntheticAst() {
    setAstLoading(true);
    setAstError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/research/ast-inspect`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          schema_version: "1.0",
          accepted_theory: FORMAL_PRESETS.ENTAILED.theory,
          correction_attempted: false,
          proof_roots: [],
        }),
      });
      if (!response.ok) throw new Error("AST inspection failed");
      setAst((await response.json()) as NormalizedAstInspection);
    } catch {
      setAstError("The synthetic AST could not be inspected. No inference request was made.");
    } finally {
      setAstLoading(false);
    }
  }

  if (loading) return <ResearchShell><LoadingState /></ResearchShell>;
  if (error || !overview) return <ResearchShell><ErrorState message={error} /></ResearchShell>;

  return (
    <ResearchShell>
      <section className="grid gap-8 border-b border-[#17201d]/15 pb-12 pt-10 lg:grid-cols-[1.45fr_0.55fr] lg:pt-16">
        <div>
          <p className="font-mono text-xs font-semibold uppercase tracking-[0.2em] text-[#9a5d2e]">
            Phase 8 · evidence-backed research frontend
          </p>
          <h1 className="mt-4 max-w-4xl text-5xl font-semibold tracking-[-0.06em] sm:text-6xl lg:text-7xl">
            Results that keep their caveats attached.
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-7 text-[#53625d]">
            This dashboard reconstructs tracked aggregate evidence from Phases 1–7. Every metric
            carries its dataset, split, sample size, source hash, commit and comparison boundary.
          </p>
        </div>
        <AuditCard overview={overview} />
      </section>

      <section aria-labelledby="overview-title" className="py-12">
        <SectionHeading
          eyebrow="Evidence overview"
          title="One catalogue, several different scientific questions"
          description="A perfect symbolic oracle does not establish parser quality, and a selective policy cannot be ranked by accuracy without its coverage."
        />
        <div className="mt-7 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Tracked conditions" value={String(overview.experiment_count)} note="Passes, negative results and blocked replications" />
          <StatCard label="Comparison contracts" value={String(overview.comparison_count)} note="Paired, descriptive and explicitly incomparable" />
          <StatCard label="Phase 8 provider calls" value="0" note="Read-only reconstruction; API cost $0.00" />
          <StatCard label="Catalogue status" value="Verified" note={overview.catalogue_hash.slice(0, 16)} mono />
        </div>
      </section>

      <section aria-labelledby="explorer-title" className="border-y border-[#17201d]/15 py-12">
        <SectionHeading
          eyebrow="Experiment explorer"
          title="Filter the evidence without changing it"
          description="Unavailable values remain NA. Blocked runs stay visible. Filters operate only on normalized aggregate records."
        />
        <ExperimentFilters experiments={experiments} filters={filters} onChange={setFilters} />
        {filtered.length ? (
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            {filtered.map((experiment) => <ExperimentCard key={experiment.experiment_id} experiment={experiment} />)}
          </div>
        ) : (
          <div className="mt-6 rounded-2xl border border-dashed border-[#17201d]/25 p-10 text-center text-sm text-[#66736f]">
            No experiment matches all selected filters.
          </div>
        )}
      </section>

      <section className="py-12" aria-labelledby="comparison-title">
        <SectionHeading
          eyebrow="Comparison explorer"
          title="The relationship matters before the delta"
          description="Only the direct and few-shot baselines are paired on the same frozen selection. Other relationships carry narrower interpretations."
        />
        <ComparisonExplorer
          experiments={experiments}
          leftId={leftId}
          rightId={rightId}
          onLeft={setLeftId}
          onRight={setRightId}
          relation={relation}
        />
      </section>

      <section className="grid gap-6 border-y border-[#17201d]/15 py-12 lg:grid-cols-2">
        <EvidenceChart
          title="Baseline and policy outcomes"
          description="Accuracy is plotted with coverage; each bar keeps the denominator visible."
          experiments={experiments.filter((item) => item.chart_eligible)}
        />
        <AttritionFunnel experiment={phase5} />
      </section>

      <ResearchVisualizations
        experiments={experiments}
        details={details}
        comparisons={comparisons}
      />

      <section className="py-12">
        <SectionHeading
          eyebrow="Semantic parser evidence"
          title="The main bottleneck appeared before symbolic reasoning"
          description="Phase 5 retained 29 structured pairs, 19 with complete source coverage, four semantically valid ASTs, and four answered records. All four accepted proofs verified."
        />
        <div className="mt-7 grid gap-4 md:grid-cols-3">
          <MetricEvidenceCard label="Statement semantic F1" value={metricValue(phase5, "statement_f1")} source={phase5} />
          <MetricEvidenceCard label="Closure F1" value={metricValue(phase5, "closure_f1")} source={phase5} />
          <MetricEvidenceCard label="Accepted proof verification" value={metricValue(phase5, "proof_verification_rate")} source={phase5} />
        </div>
      </section>

      <section className="border-y border-[#17201d]/15 py-12">
        <SectionHeading
          eyebrow="Normalized AST inspector"
          title="Inspect structure, not hidden model reasoning"
          description="This viewer sends one bundled synthetic formal theory to a computational, provider-free endpoint. It does not read benchmark records or invoke a solver."
        />
        <AstInspector ast={ast} loading={astLoading} error={astError} onInspect={inspectSyntheticAst} />
      </section>

      <section className="py-12">
        <SectionHeading
          eyebrow="Provenance and exports"
          title="Take the aggregate evidence with you"
          description="Exports include fixed filenames, evidence hashes, comparison warnings and NA for missing values. They exclude raw prompts, benchmark text, caches and local paths."
        />
        <div className="mt-7 grid gap-5 lg:grid-cols-3">
          <ExportPanel />
          <ProofProvenancePanel experiment={phase5} />
          <LimitationsPanel limitations={overview.global_limitations} />
        </div>
      </section>
    </ResearchShell>
  );
}

function ResearchShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="min-h-screen bg-[#f4f0e8] text-[#17201d]">
      <header className="sticky top-0 z-20 border-b border-[#17201d]/15 bg-[#f4f0e8]/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between gap-5 px-5 py-4 lg:px-10">
          <Link href="/" className="flex items-center gap-3 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#173d35]">
            <span className="grid size-10 place-items-center rounded-full bg-[#173d35] font-mono text-sm font-bold text-white">VN</span>
            <span><strong className="block text-sm">VeriLogic-NS</strong><span className="block text-xs text-[#66736f]">Research evidence</span></span>
          </Link>
          <nav aria-label="Primary" className="flex items-center gap-2 text-sm">
            <Link href="/" className="rounded-full px-3 py-2 text-[#53625d] hover:bg-white">Workbench</Link>
            <Link href="/research" aria-current="page" className="rounded-full bg-[#173d35] px-3 py-2 font-medium text-white">Research</Link>
          </nav>
        </div>
      </header>
      <div className="mx-auto max-w-[1440px] px-5 lg:px-10">{children}</div>
      <footer className="border-t border-[#17201d]/15 px-5 py-8 text-center text-xs leading-5 text-[#66736f]">
        Evidence through Phase 7 · development and synthetic canary results · not a final test-set claim
      </footer>
    </main>
  );
}

function LoadingState() {
  return <div className="py-24 text-center"><p className="font-mono text-xs uppercase tracking-[0.2em] text-[#66736f]">Validating catalogue and source hashes…</p></div>;
}

function ErrorState({ message }: { message: string | null }) {
  return <div className="mx-auto max-w-2xl py-24 text-center"><p className="text-3xl font-semibold">Evidence unavailable</p><p className="mt-3 text-sm leading-6 text-[#66736f]">{message}</p></div>;
}

function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description: string }) {
  return <div className="max-w-3xl"><p className="font-mono text-xs font-semibold uppercase tracking-[0.18em] text-[#9a5d2e]">{eyebrow}</p><h2 className="mt-3 text-3xl font-semibold tracking-[-0.045em] sm:text-4xl">{title}</h2><p className="mt-3 text-sm leading-6 text-[#5d6b67]">{description}</p></div>;
}

function AuditCard({ overview }: { overview: CatalogueOverview }) {
  return <aside className="self-end rounded-2xl border border-[#173d35]/20 bg-[#173d35] p-6 text-[#eef7f3]"><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[#a9c8be]">Evidence integrity</p><p className="mt-3 text-2xl font-semibold">{overview.evidence_validation_status}</p><dl className="mt-5 space-y-3 border-t border-white/15 pt-4 text-xs"><div><dt className="text-[#a9c8be]">Catalogue version</dt><dd className="mt-1 font-mono">{overview.catalogue_version}</dd></div><div><dt className="text-[#a9c8be]">Canonical SHA-256</dt><dd className="mt-1 break-all font-mono">{overview.catalogue_hash}</dd></div><div><dt className="text-[#a9c8be]">Cost added in Phase 8</dt><dd className="mt-1">$0.00</dd></div></dl></aside>;
}

function StatCard({ label, value, note, mono = false }: { label: string; value: string; note: string; mono?: boolean }) {
  return <article className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5"><p className="text-xs font-medium text-[#66736f]">{label}</p><p className={`mt-3 text-3xl font-semibold tracking-[-0.04em] ${mono ? "font-mono text-xl" : ""}`}>{value}</p><p className="mt-2 text-xs leading-5 text-[#66736f]">{note}</p></article>;
}

function ExperimentFilters({ experiments, filters, onChange }: { experiments: ExperimentSummary[]; filters: ResearchFilters; onChange: (filters: ResearchFilters) => void }) {
  const option = (field: keyof ResearchFilters, label: string, values: string[]) => <label className="text-xs font-medium text-[#53625d]">{label}<select value={filters[field]} onChange={(event) => onChange({ ...filters, [field]: event.target.value })} className="mt-2 block w-full rounded-lg border border-[#17201d]/15 bg-white px-3 py-2.5 text-sm text-[#17201d]"><option value="">All</option>{[...new Set(values.filter(Boolean))].sort().map((value) => <option key={value}>{value}</option>)}</select></label>;
  return <div className="mt-7 grid gap-3 rounded-2xl border border-[#17201d]/15 bg-[#ebe6db]/65 p-4 sm:grid-cols-2 lg:grid-cols-5">{option("phase", "Phase", experiments.map((item) => item.phase))}{option("status", "Status", experiments.map((item) => item.status))}{option("model", "Model", experiments.map((item) => item.model_name ?? ""))}{option("condition", "Condition", experiments.map((item) => item.condition))}{option("policy", "Policy", experiments.map((item) => item.policy_mode ?? ""))}{option("dataset", "Dataset", experiments.map((item) => item.dataset))}{option("split", "Split", experiments.map((item) => item.split))}{option("depth", "Depth", ["0", "1", "2", "3", "5"])}{option("label", "Label", ["ENTAILED", "CONTRADICTED", "UNKNOWN"])}<button type="button" onClick={() => onChange(EMPTY_FILTERS)} className="self-end rounded-lg border border-[#17201d]/15 bg-white px-4 py-2.5 text-sm font-medium hover:bg-[#f8f5ee]">Reset all</button></div>;
}

function ExperimentCard({ experiment }: { experiment: ExperimentSummary }) {
  const accuracy = primaryMetric(experiment, "accuracy");
  const coverage = primaryMetric(experiment, "coverage");
  return <article className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[#9a5d2e]">{experiment.phase} · n={experiment.sample_size}</p><h3 className="mt-2 text-lg font-semibold">{experiment.name}</h3></div><StatusBadge status={experiment.status} /></div><div className="mt-5 grid grid-cols-2 gap-3"><MiniMetric label="Accuracy" value={formatMetric(accuracy)} /><MiniMetric label="Coverage" value={formatMetric(coverage)} /></div><dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-[11px]"><div><dt className="text-[#77827e]">Model</dt><dd className="mt-0.5 truncate">{experiment.model_name ?? "Not applicable"}</dd></div><div><dt className="text-[#77827e]">Dataset / split</dt><dd className="mt-0.5">{experiment.dataset} · {experiment.split}</dd></div><div><dt className="text-[#77827e]">Replay</dt><dd className="mt-0.5 font-mono">{experiment.replay_status}</dd></div><div><dt className="text-[#77827e]">Calls / API cost</dt><dd className="mt-0.5">{experiment.provider_call_count ?? "NA"} / {experiment.api_cost_usd === null ? "NA" : `$${experiment.api_cost_usd.toFixed(2)}`}</dd></div><div><dt className="text-[#77827e]">Recorded</dt><dd className="mt-0.5">{experiment.recorded_at ? new Date(experiment.recorded_at).toLocaleDateString("en-GB") : "Unavailable"}</dd></div><div><dt className="text-[#77827e]">Evidence</dt><dd className="mt-0.5 font-mono">{experiment.evidence_verification_status}</dd></div></dl><p className="mt-4 text-xs leading-5 text-[#66736f]">{experiment.main_limitation ?? "No additional limitation recorded."}</p><p className="mt-4 break-all border-t border-[#17201d]/10 pt-3 font-mono text-[10px] text-[#77827e]">{experiment.commit ?? "commit unavailable"}</p></article>;
}

function StatusBadge({ status }: { status: ExperimentSummary["status"] }) {
  const colors = status === "PASS" ? "bg-[#e4f2ec] text-[#17634d]" : status === "BLOCKED" ? "bg-[#fff0e8] text-[#97452e]" : "bg-[#f1eafa] text-[#70448c]";
  return <span className={`rounded-full px-3 py-1 font-mono text-[10px] font-semibold ${colors}`}>{status.replaceAll("_", " ")}</span>;
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-[#f2eee5] p-3"><p className="text-[10px] uppercase tracking-wider text-[#66736f]">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>;
}

function ComparisonExplorer({ experiments, leftId, rightId, onLeft, onRight, relation }: { experiments: ExperimentSummary[]; leftId: string; rightId: string; onLeft: (value: string) => void; onRight: (value: string) => void; relation: ComparisonCompatibility | undefined }) {
  const left = experiments.find((item) => item.experiment_id === leftId);
  const right = experiments.find((item) => item.experiment_id === rightId);
  const select = (label: string, value: string, onChange: (value: string) => void) => <label className="text-xs font-medium text-[#53625d]">{label}<select value={value} onChange={(event) => onChange(event.target.value)} className="mt-2 block w-full rounded-lg border border-[#17201d]/15 bg-white px-3 py-3 text-sm">{experiments.map((item) => <option key={item.experiment_id} value={item.experiment_id}>{item.name}</option>)}</select></label>;
  return <div className="mt-7 rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5 sm:p-6"><div className="grid gap-4 md:grid-cols-2">{select("Left condition", leftId, onLeft)}{select("Right condition", rightId, onRight)}</div><div className={`mt-5 rounded-xl border p-4 ${relation?.comparison_type === "PAIRED" ? "border-[#218264]/25 bg-[#eaf6f1]" : relation ? "border-[#b37b2c]/25 bg-[#fff7df]" : "border-[#b5412c]/25 bg-[#fff0eb]"}`}><p className="font-mono text-[10px] font-semibold uppercase tracking-[0.14em]">{relation?.comparison_type.replaceAll("_", " ") ?? "NO REGISTERED COMPARISON"}</p><p className="mt-2 text-sm leading-6">{relation?.warning ?? "These selected conditions have no supported comparison contract. Do not infer a performance delta."}</p></div><div className="mt-5 grid gap-3 sm:grid-cols-2"><MiniMetric label={left?.name ?? "Left accuracy"} value={formatMetric(left ? primaryMetric(left, "accuracy") : null)} /><MiniMetric label={right?.name ?? "Right accuracy"} value={formatMetric(right ? primaryMetric(right, "accuracy") : null)} /></div></div>;
}

function EvidenceChart({ title, description, experiments }: { title: string; description: string; experiments: ExperimentSummary[] }) {
  return <article className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5 sm:p-6"><h3 className="text-xl font-semibold tracking-[-0.03em]">{title}</h3><p className="mt-2 text-xs leading-5 text-[#66736f]">{description}</p><div className="mt-6 space-y-5">{experiments.slice(0, 8).map((experiment) => { const accuracy = primaryMetric(experiment, "accuracy"); const coverage = primaryMetric(experiment, "coverage"); return <div key={experiment.experiment_id}><div className="flex justify-between gap-4 text-xs"><span className="truncate font-medium">{experiment.name}</span><span className="font-mono">{formatMetric(accuracy)} / {formatMetric(coverage)}</span></div><div className="mt-2 h-3 overflow-hidden rounded-full bg-[#e5dfd3]" role="img" aria-label={`${experiment.name}: accuracy ${formatMetric(accuracy)}, coverage ${formatMetric(coverage)}`}><div className="h-full rounded-full bg-[#218264]" style={{ width: `${Math.max(0, Math.min(100, (accuracy ?? 0) * 100))}%` }} /></div><div className="mt-1 h-1 overflow-hidden rounded-full bg-[#e5dfd3]"><div className="h-full bg-[#d28a3d]" style={{ width: `${Math.max(0, Math.min(100, (coverage ?? 0) * 100))}%` }} /></div></div>; })}</div><div className="mt-5 flex gap-5 text-[10px] text-[#66736f]"><span><i className="mr-1 inline-block size-2 rounded-full bg-[#218264]" />Accuracy</span><span><i className="mr-1 inline-block size-2 rounded-full bg-[#d28a3d]" />Coverage</span></div></article>;
}

function AttritionFunnel({ experiment }: { experiment: ExperimentDetail | undefined }) {
  const stages = attritionStages(experiment);
  const total = stages[0]?.value || 1;
  return <article className="rounded-2xl border border-[#17201d]/15 bg-[#173d35] p-5 text-white sm:p-6"><h3 className="text-xl font-semibold tracking-[-0.03em]">Phase 5 acceptance funnel</h3><p className="mt-2 text-xs leading-5 text-[#bdd0ca]">Counts narrow through structured output, source coverage and semantic validity before the solver can answer.</p><div className="mt-6 space-y-3">{stages.map((stage, index) => <div key={stage.id} className="mx-auto rounded-lg bg-white/10 px-4 py-3" style={{ width: `${Math.max(46, 100 - index * 11)}%` }}><div className="flex justify-between gap-3 text-xs"><span>{stage.label}</span><strong className="font-mono">{stage.value}/{total}</strong></div></div>)}</div></article>;
}

type ExactRow = {
  label: string;
  value: number | null;
  unit?: string;
  denominator?: number;
  note?: string;
};

function ResearchVisualizations({ experiments, details, comparisons }: { experiments: ExperimentSummary[]; details: Record<string, ExperimentDetail>; comparisons: ComparisonCompatibility[] }) {
  const named = (id: string) => experiments.find((item) => item.experiment_id === id)?.name ?? id;
  const accuracyRow = (id: string): ExactRow => ({ label: named(id), value: metricValue(details[id], "accuracy"), unit: "ratio", denominator: 1 });
  const phase5 = details["phase5-hybrid"];
  const paired = comparisons.find((item) => item.comparison_id === "phase3-direct-vs-few-shot");
  const oracleGap = ["phase3-direct", "phase5-hybrid", "phase4-oracle-same30"].map(accuracyRow);
  const dispositions = ["phase6-r3-p0", "phase6-r3-p1", "phase6-r3-p2"].flatMap((id) => [
    { label: `${details[id]?.policy_mode} · answered`, value: metricValue(details[id], "answered"), denominator: 30 },
    { label: `${details[id]?.policy_mode} · abstained`, value: metricValue(details[id], "abstained"), denominator: 30 },
    { label: `${details[id]?.policy_mode} · errors`, value: metricValue(details[id], "errors"), denominator: 30 },
  ]);
  const pairedRows = Object.entries(paired?.outcome_counts ?? {}).map(([label, value]) => ({
    label: label.replaceAll("_", " "), value, denominator: 30,
  }));
  const errorRows = (phase5?.metrics ?? []).filter((metric) => metric.metric_id === "error_count").map((metric) => ({
    label: metric.dimensions.error?.replaceAll("_", " ") ?? metric.display_name,
    value: metric.value,
    denominator: phase5?.sample_size,
  }));
  const runtimeRows = ["phase3-direct", "phase3-few-shot", "phase5-hybrid"].map((id) => ({
    label: named(id), value: metricValue(details[id], "inference_seconds"), unit: "seconds",
  }));
  const tokenRows = ["phase3-direct", "phase3-few-shot", "phase5-hybrid"].flatMap((id) => [
    { label: `${named(id)} · input`, value: metricValue(details[id], "input_tokens"), unit: "tokens" },
    { label: `${named(id)} · output`, value: metricValue(details[id], "output_tokens"), unit: "tokens" },
  ]);
  const proofRows = ["phase4-oracle-same30", "phase5-hybrid", "phase6-r3-p0", "phase7-formal-canaries"].map((id) => ({
    label: named(id), value: metricValue(details[id], "proof_verification_rate"), unit: "ratio", denominator: 1,
  }));
  const depthRows = [0, 1, 2, 3, 5].flatMap((depth) => [
    { label: `Oracle · depth ${depth}`, value: metricValue(details["phase4-oracle-300"], "accuracy", { depth: String(depth) }), unit: "ratio", denominator: 1 },
    { label: `R3 P0 · depth ${depth}`, value: metricValue(details["phase6-r3-p0"], "accuracy", { depth: String(depth) }), unit: "ratio", denominator: 1 },
  ]);
  const labelRows = ["ENTAILED", "CONTRADICTED", "UNKNOWN"].flatMap((label) => [
    { label: `Oracle · ${label}`, value: metricValue(details["phase4-oracle-300"], "accuracy", { label }), unit: "ratio", denominator: 1 },
    { label: `R3 P0 · ${label}`, value: metricValue(details["phase6-r3-p0"], "accuracy", { label }), unit: "ratio", denominator: 1 },
  ]);
  return <section className="py-12" aria-labelledby="visualisations-title"><SectionHeading eyebrow="Exact visualisations" title="Ten views, all generated from the catalogue" description="Each chart has an accompanying exact-value table. Bars begin at zero, absent metrics remain NA, and the labels distinguish unlike conditions." /><div className="mt-7 grid gap-5 lg:grid-cols-2"><ExactEvidencePanel title="Oracle symbolic vs natural-language gap" description="Same 30-example selection where recorded; representation differs, so this is a ceiling comparison rather than a paired system test." rows={oracleGap} /><ExactEvidencePanel title="Phase 6-R3 policy dispositions" description="Answered, abstained and error counts for the three terminal policies." rows={dispositions} /><ExactEvidencePanel title="Direct vs few-shot paired outcomes" description={paired?.warning ?? "Paired evidence unavailable."} rows={pairedRows} /><ExactEvidencePanel title="Phase 5 error categories" description="Terminal parser and source-validation failures before accepted symbolic reasoning." rows={errorRows} /><ExactEvidencePanel title="Runtime comparison" description="Local provider duration where documented; hardware and workload differ across phases." rows={runtimeRows} /><ExactEvidencePanel title="Input/output token comparison" description="Token counts are operational evidence, not an accuracy claim." rows={tokenRows} /><ExactEvidencePanel title="Proof-verification summary" description="Verification rate applies only to produced proof attempts; coverage must be read separately." rows={proofRows} /><ExactEvidencePanel title="Per-depth accuracy" description="Evidence exists for the Phase 4 symbolic oracle and Phase 6-R3 P0 policy." rows={depthRows} /><ExactEvidencePanel title="Per-label accuracy" description="Exact aggregate label slices where retained in tracked evidence." rows={labelRows} /><ExactEvidencePanel title="Accuracy and coverage interpretation" description="A selective system can reduce coverage; answered-only accuracy is not overall accuracy." rows={experiments.filter((item) => item.chart_eligible).flatMap((item) => [{ label: `${item.name} · accuracy`, value: primaryMetric(item, "accuracy"), unit: "ratio", denominator: 1 }, { label: `${item.name} · coverage`, value: primaryMetric(item, "coverage"), unit: "ratio", denominator: 1 }])} /></div></section>;
}

function ExactEvidencePanel({ title, description, rows }: { title: string; description: string; rows: ExactRow[] }) {
  const available = rows.filter((row) => row.value !== null);
  const maximum = Math.max(1, ...available.map((row) => row.denominator ?? row.value ?? 0));
  return <article className="overflow-hidden rounded-2xl border border-[#17201d]/15 bg-[#fffdf8]"><div className="p-5 sm:p-6"><h3 className="text-lg font-semibold tracking-[-0.025em]">{title}</h3><p className="mt-2 text-xs leading-5 text-[#66736f]">{description}</p><div className="mt-5 space-y-3" role="img" aria-label={`${title}. ${rows.map((row) => `${row.label}: ${formatMetric(row.value, row.unit)}`).join("; ")}`} >{rows.map((row) => <div key={row.label}><div className="flex justify-between gap-4 text-[11px]"><span className="truncate">{row.label}</span><strong className="font-mono">{formatMetric(row.value, row.unit)}</strong></div><div className="mt-1.5 h-2 overflow-hidden rounded-full bg-[#e5dfd3]"><div className="h-full rounded-full bg-[#218264]" style={{ width: `${row.value === null ? 0 : Math.max(0, Math.min(100, (row.value / (row.denominator ?? maximum)) * 100))}%` }} /></div></div>)}</div></div><div className="max-h-64 overflow-auto border-t border-[#17201d]/10"><table className="w-full border-collapse text-left text-[11px]"><thead className="sticky top-0 bg-[#eee9df]"><tr><th scope="col" className="px-5 py-2 font-semibold">Measure</th><th scope="col" className="px-5 py-2 text-right font-semibold">Exact value</th></tr></thead><tbody>{rows.map((row) => <tr key={row.label} className="border-t border-[#17201d]/8"><th scope="row" className="px-5 py-2.5 font-normal">{row.label}</th><td className="px-5 py-2.5 text-right font-mono">{formatMetric(row.value, row.unit)}{row.denominator && row.unit !== "ratio" ? ` / ${row.denominator}` : ""}</td></tr>)}</tbody></table></div></article>;
}

function MetricEvidenceCard({ label, value, source }: { label: string; value: number | null; source: ExperimentDetail | undefined }) {
  return <article className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5"><p className="text-xs text-[#66736f]">{label}</p><p className="mt-3 text-3xl font-semibold">{formatMetric(value)}</p><p className="mt-3 font-mono text-[10px] leading-5 text-[#77827e]">n={source?.sample_size ?? "NA"} · {source?.split ?? "split unavailable"}<br />{source?.commit?.slice(0, 12) ?? "commit unavailable"}</p></article>;
}

function AstInspector({ ast, loading, error, onInspect }: { ast: NormalizedAstInspection | null; loading: boolean; error: string | null; onInspect: () => void }) {
  const correctionAvailable = ast?.correction_diff.available === true;
  return <div className="mt-7 grid gap-5 lg:grid-cols-[0.7fr_1.3fr]"><div className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5"><h3 className="font-semibold">Bundled synthetic example</h3><p className="mt-2 text-sm leading-6 text-[#66736f]">Robin is red. Every red thing is warm. Query: is Robin warm?</p><button type="button" disabled={loading} onClick={onInspect} className="mt-5 rounded-lg bg-[#173d35] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#d28a3d]">{loading ? "Inspecting…" : "Inspect normalized AST"}</button>{error && <p role="alert" className="mt-4 text-xs leading-5 text-[#9b3928]">{error}</p>}{ast && <><dl className="mt-5 grid grid-cols-2 gap-3 text-xs"><div><dt className="text-[#66736f]">Semantic status</dt><dd className="mt-1 font-mono">{ast.semantic_validation_status}</dd></div><div><dt className="text-[#66736f]">Source coverage</dt><dd className="mt-1 font-mono">{ast.source_coverage_status}</dd></div><div><dt className="text-[#66736f]">Correction comparison</dt><dd className="mt-1 font-mono">{correctionAvailable ? "AVAILABLE" : "UNAVAILABLE"}</dd></div><div><dt className="text-[#66736f]">Proof connection</dt><dd className="mt-1 font-mono">{ast.proof_roots.length ? ast.proof_roots.join(", ") : "UNAVAILABLE"}</dd></div></dl><table className="mt-5 w-full text-left text-xs"><caption className="mb-2 text-left font-semibold">Predicates and arity</caption><thead><tr className="text-[#66736f]"><th scope="col" className="py-1">Predicate</th><th scope="col" className="py-1 text-right">Arity</th></tr></thead><tbody>{ast.predicates.map((predicate) => <tr key={predicate.name} className="border-t border-[#17201d]/10"><th scope="row" className="py-1.5 font-mono font-normal">{predicate.name}</th><td className="py-1.5 text-right font-mono">{predicate.arity}</td></tr>)}</tbody></table></>}</div><div className="min-h-80 overflow-hidden rounded-2xl border border-[#17201d]/15 bg-[#14211e] p-5 text-[#d9eee7]">{ast ? <div className="grid gap-5 text-xs sm:grid-cols-3"><AstColumn title="Facts" items={ast.facts.map((item) => item.display)} /><AstColumn title="Rules" items={ast.rules.map((rule) => `${rule.premises.map((item) => item.display).join(" AND ")} → ${rule.conclusion.display}`)} /><AstColumn title="Query" items={[ast.query.display]} /><div className="sm:col-span-3"><p className="font-mono text-[10px] uppercase tracking-wider text-[#8eb5a9]">Source mapping</p><ul className="mt-2 space-y-2">{ast.source_mapping.map((source) => <li key={source.source_id}><span className="font-mono text-[#8eb5a9]">{source.source_id}</span> · {source.text} <span className="text-[#77948b]">[{source.referenced_by.join(", ")}]</span></li>)}</ul></div><details className="sm:col-span-3"><summary className="cursor-pointer font-mono text-[10px] uppercase tracking-wider text-[#8eb5a9]">Canonical JSON</summary><pre className="mt-3 max-h-80 overflow-auto rounded-lg bg-black/20 p-3 font-mono text-[10px] leading-5">{JSON.stringify(ast.canonical_json, null, 2)}</pre></details><p className="break-all font-mono text-[9px] text-[#77948b] sm:col-span-3">Canonical theory {ast.canonical_theory_id}</p></div> : <div className="grid min-h-72 place-items-center text-center text-sm text-[#8eb5a9]">Run the provider-free inspector to render facts, rules, query and source links.</div>}</div></div>;
}

function AstColumn({ title, items }: { title: string; items: string[] }) {
  return <div><p className="font-mono text-[10px] uppercase tracking-wider text-[#8eb5a9]">{title}</p><ul className="mt-2 space-y-2">{items.map((item) => <li key={item} className="rounded-md bg-white/5 p-2 font-mono leading-5">{item}</li>)}</ul></div>;
}

function ExportPanel() {
  return <div className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5 sm:p-6"><h3 className="text-lg font-semibold">Aggregate exports</h3><p className="mt-2 text-xs leading-5 text-[#66736f]">Download the full normalized catalogue in a machine-readable or report-ready form.</p><div className="mt-5 flex flex-wrap gap-2">{(["json", "csv", "markdown"] as const).map((format) => <a key={format} href={`${API_BASE_URL}/api/v1/research/exports?format=${format}`} download className="rounded-lg border border-[#17201d]/15 bg-white px-4 py-2.5 text-sm font-semibold uppercase hover:bg-[#f4f0e8] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#173d35]">{format}</a>)}</div><p className="mt-5 text-[10px] leading-5 text-[#77827e]">Fixed filenames · content SHA-256 response header · no raw benchmark or provider payloads</p></div>;
}

function ProofProvenancePanel({ experiment }: { experiment: ExperimentDetail | undefined }) {
  return <div className="rounded-2xl border border-[#17201d]/15 bg-[#fffdf8] p-5 sm:p-6"><h3 className="text-lg font-semibold">Proof and provenance</h3><dl className="mt-4 space-y-3 text-xs"><div><dt className="text-[#66736f]">Verifier state</dt><dd className="mt-1 font-mono">{formatMetric(metricValue(experiment, "proof_verification_rate"))} of produced proofs verified</dd></div><div><dt className="text-[#66736f]">Proof hash</dt><dd className="mt-1 font-mono">UNAVAILABLE IN AGGREGATE EVIDENCE</dd></div><div><dt className="text-[#66736f]">Source artifacts</dt><dd className="mt-1 font-mono">{experiment?.evidence_sources.join(", ") ?? "UNAVAILABLE"}</dd></div><div><dt className="text-[#66736f]">Commit</dt><dd className="mt-1 break-all font-mono">{experiment?.commit ?? "UNAVAILABLE"}</dd></div><div><dt className="text-[#66736f]">Selection manifest</dt><dd className="mt-1 break-all font-mono">{experiment?.selection_manifest ?? "UNAVAILABLE"}</dd></div><div><dt className="text-[#66736f]">Run reference</dt><dd className="mt-1 break-all font-mono">{experiment?.run_id ?? "UNAVAILABLE"}</dd></div></dl></div>;
}

function LimitationsPanel({ limitations }: { limitations: string[] }) {
  return <div className="rounded-2xl border border-[#9a5d2e]/25 bg-[#fff7e8] p-5 sm:p-6"><h3 className="text-lg font-semibold">Global interpretation limits</h3><ul className="mt-4 space-y-3 text-sm leading-6 text-[#695a49]">{limitations.map((limitation) => <li key={limitation} className="grid grid-cols-[12px_1fr] gap-2"><span aria-hidden="true">•</span><span>{limitation}</span></li>)}</ul></div>;
}
