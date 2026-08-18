import type {
  ComparisonCompatibility,
  ExperimentDetail,
  ExperimentSummary,
} from "./research-contract.generated";

export type ResearchFilters = {
  phase: string;
  status: string;
  model: string;
  condition: string;
  policy: string;
  dataset: string;
  split: string;
  depth: string;
  label: string;
};

export function formatMetric(value: number | null | undefined, unit = "ratio") {
  if (value === null || value === undefined) return "NA";
  if (unit === "ratio") return `${(value * 100).toFixed(value === 1 ? 0 : 1)}%`;
  if (unit === "usd") return `$${value.toFixed(2)}`;
  if (unit === "seconds") return `${value.toLocaleString()} s`;
  return value.toLocaleString();
}

export function primaryMetric(experiment: ExperimentSummary, metric: string) {
  return experiment.primary_metrics[metric] ?? null;
}

export function filterExperiments(
  experiments: ExperimentSummary[],
  filters: ResearchFilters,
  details: Record<string, ExperimentDetail> = {},
) {
  return experiments.filter(
    (experiment) => {
      const metrics = details[experiment.experiment_id]?.metrics ?? [];
      return (
        (!filters.phase || experiment.phase === filters.phase) &&
        (!filters.status || experiment.status === filters.status) &&
        (!filters.model || experiment.model_name === filters.model) &&
        (!filters.condition || experiment.condition === filters.condition) &&
        (!filters.policy || experiment.policy_mode === filters.policy) &&
        (!filters.dataset || experiment.dataset === filters.dataset) &&
        (!filters.split || experiment.split === filters.split) &&
        (!filters.depth || metrics.some((metric) => metric.dimensions.depth === filters.depth)) &&
        (!filters.label || metrics.some((metric) => metric.dimensions.label === filters.label))
      );
    },
  );
}

export function compatibleComparison(
  comparisons: ComparisonCompatibility[],
  left: string,
  right: string,
) {
  return comparisons.find(
    (comparison) =>
      comparison.experiment_ids.length === 2 &&
      comparison.experiment_ids.includes(left) &&
      comparison.experiment_ids.includes(right),
  );
}

export function metricValue(
  experiment: ExperimentDetail | undefined,
  metricId: string,
  dimensions: Record<string, string> = {},
) {
  return (
    experiment?.metrics.find(
      (metric) =>
        metric.metric_id === metricId &&
        Object.entries(dimensions).every(([key, value]) => metric.dimensions[key] === value),
    )?.value ?? null
  );
}

export function attritionStages(experiment: ExperimentDetail | undefined) {
  const ids = [
    ["sample_size", "Submitted"],
    ["structured_pairs", "Structured"],
    ["source_covered_pairs", "Source covered"],
    ["semantic_valid_pairs", "Semantically valid"],
    ["accepted_records", "Answered"],
  ] as const;
  return ids.map(([id, label]) => ({
    id,
    label,
    value:
      id === "sample_size" ? (experiment?.sample_size ?? 0) : (metricValue(experiment, id) ?? 0),
  }));
}
