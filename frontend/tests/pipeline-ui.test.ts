import assert from "node:assert/strict";
import test from "node:test";

import {
  isTerminalRun,
  pollDelayMs,
  resultTone,
  validateNaturalInput,
} from "../src/lib/pipeline-ui";

test("natural input validation covers empty, incomplete, duplicate, and valid forms", () => {
  assert.equal(validateNaturalInput([], "query"), "Add at least one theory statement.");
  assert.equal(
    validateNaturalInput([{ source_id: "s1", kind: "fact", text: "" }], "query"),
    "Every statement needs text.",
  );
  assert.equal(
    validateNaturalInput([{ source_id: "s1", kind: "fact", text: "A fact." }], ""),
    "Enter a query to verify.",
  );
  assert.equal(
    validateNaturalInput(
      [
        { source_id: "s1", kind: "fact", text: "A." },
        { source_id: "s1", kind: "rule", text: "B." },
      ],
      "Q?",
    ),
    "Source IDs must be unique.",
  );
  assert.equal(
    validateNaturalInput([{ source_id: "s1", kind: "fact", text: "A." }], "Q?"),
    null,
  );
});

test("polling stops for every terminal run state", () => {
  assert.equal(isTerminalRun("QUEUED"), false);
  assert.equal(isTerminalRun("RUNNING"), false);
  assert.equal(isTerminalRun("CANCEL_REQUESTED"), false);
  assert.equal(isTerminalRun("COMPLETED"), true);
  assert.equal(isTerminalRun("FAILED"), true);
  assert.equal(isTerminalRun("CANCELLED"), true);
});

test("polling backs off for unchanged work and transient failures", () => {
  assert.equal(pollDelayMs(0), 900);
  assert.equal(pollDelayMs(2), 900);
  assert.equal(pollDelayMs(3), 1_500);
  assert.equal(pollDelayMs(8), 2_000);
  assert.equal(pollDelayMs(0, 1), 2_000);
  assert.equal(pollDelayMs(0, 2), 4_000);
  assert.equal(pollDelayMs(0, 10), 8_000);
});

test("result tones distinguish logical, abstention, and error outcomes", () => {
  assert.equal(resultTone(undefined), "neutral");
  assert.equal(resultTone({ disposition: "ABSTAINED" } as never), "abstained");
  assert.equal(resultTone({ disposition: "ERROR" } as never), "error");
  assert.equal(
    resultTone({ disposition: "ANSWERED", logical_result: "INCONSISTENT" } as never),
    "inconsistent",
  );
});
