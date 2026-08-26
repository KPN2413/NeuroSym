import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const dashboard = readFileSync(
  resolve(process.cwd(), "src/components/research-dashboard.tsx"),
  "utf-8",
);
const loading = readFileSync(resolve(process.cwd(), "src/app/research/loading.tsx"), "utf-8");
const workbench = readFileSync(
  resolve(process.cwd(), "src/components/neurosymbolic-workbench.tsx"),
  "utf-8",
);

test("research route declares loading, error, empty, history, and blocked states", () => {
  assert.match(loading, /Loading research evidence/);
  assert.match(dashboard, /Evidence unavailable/);
  assert.match(dashboard, /No experiment matches/);
  assert.match(dashboard, /Experiment explorer/);
  assert.match(dashboard, /BLOCKED/);
});

test("research surface includes required evidence and visualization sections", () => {
  for (const text of [
    "Accuracy",
    "Coverage",
    "Comparison explorer",
    "Phase 5 acceptance funnel",
    "Phase 9 policy dispositions",
    "Normalized AST inspector",
    "Proof and provenance",
    "Aggregate exports",
    "Phase 9 · regenerated evidence catalogue",
    "Phase 9 direct vs few-shot paired outcomes",
    "historical and regenerated development evidence",
  ]) {
    assert.match(dashboard, new RegExp(text));
  }
});

test("research surface exposes all export formats and keyboard-native controls", () => {
  assert.match(dashboard, /\["json", "csv", "markdown"\]/);
  assert.match(dashboard, /<button/);
  assert.match(dashboard, /<select/);
  assert.match(dashboard, /<table/);
  assert.match(dashboard, /focus-visible/);
});

test("phase 7 workbench retains a research navigation path", () => {
  assert.match(workbench, /href="\/research"/);
  assert.match(workbench, /Research evidence/);
});
