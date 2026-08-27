import assert from "node:assert/strict";
import test from "node:test";

import {
  attritionStages,
  compatibleComparison,
  filterExperiments,
  formatMetric,
  metricValue,
} from "../src/lib/research-ui";

const summary = {
  experiment_id: "direct",
  phase: "Phase 3",
  status: "PASS",
  model_name: "local-model",
  condition: "DIRECT_ZERO_SHOT",
  primary_metrics: { accuracy: 0.5 },
} as never;

test("research values preserve unavailable evidence as NA", () => {
  assert.equal(formatMetric(null), "NA");
  assert.equal(formatMetric(undefined), "NA");
  assert.equal(formatMetric(0.5), "50.0%");
  assert.equal(formatMetric(0, "count"), "0");
  assert.equal(formatMetric(5, "count"), "5");
  assert.equal(formatMetric(25, "count"), "25");
});

test("research filters combine without rewriting evidence", () => {
  assert.equal(
    filterExperiments([summary], {
      phase: "Phase 3",
      status: "PASS",
      model: "local-model",
      condition: "DIRECT_ZERO_SHOT",
      policy: "",
      dataset: "",
      split: "",
      depth: "",
      label: "",
    }).length,
    1,
  );
  assert.equal(
    filterExperiments([summary], {
      phase: "Phase 6",
      status: "",
      model: "",
      condition: "",
      policy: "",
      dataset: "",
      split: "",
      depth: "",
      label: "",
    }).length,
    0,
  );
});

test("comparison lookup requires both exact experiment IDs", () => {
  const comparisons = [
    {
      comparison_id: "paired",
      experiment_ids: ["direct", "few"],
      comparison_type: "PAIRED",
    },
  ] as never;
  assert.equal(compatibleComparison(comparisons, "few", "direct")?.comparison_id, "paired");
  assert.equal(compatibleComparison(comparisons, "direct", "hybrid"), undefined);
});

test("metric lookup and attrition retain zero and missing separately", () => {
  const detail = {
    sample_size: 30,
    metrics: [
      { metric_id: "accuracy", dimensions: {}, value: 0 },
      { metric_id: "structured_pairs", dimensions: {}, value: 29 },
    ],
  } as never;
  assert.equal(metricValue(detail, "accuracy"), 0);
  assert.equal(metricValue(detail, "coverage"), null);
  assert.deepEqual(
    attritionStages(detail).map((stage) => stage.value),
    [30, 29, 0, 0, 0],
  );
});
