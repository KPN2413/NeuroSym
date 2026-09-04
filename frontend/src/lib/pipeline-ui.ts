import type {
  NaturalLanguageStatement,
  PipelineResult,
  RunStatus,
} from "./neurosymbolic-contract.generated";

export const TERMINAL_RUN_STATES = new Set<RunStatus>([
  "COMPLETED",
  "FAILED",
  "CANCELLED",
]);

export function isTerminalRun(status: RunStatus) {
  return TERMINAL_RUN_STATES.has(status);
}

export function pollDelayMs(unchangedPolls: number, consecutiveFailures = 0) {
  if (consecutiveFailures > 0) {
    return Math.min(8_000, 2_000 * 2 ** (consecutiveFailures - 1));
  }
  if (unchangedPolls < 3) return 900;
  if (unchangedPolls < 8) return 1_500;
  return 2_000;
}

export function validateNaturalInput(statements: NaturalLanguageStatement[], query: string) {
  if (statements.length === 0) return "Add at least one theory statement.";
  if (statements.some((item) => !item.text.trim())) return "Every statement needs text.";
  if (!query.trim()) return "Enter a query to verify.";
  const ids = statements.map((item) => item.source_id).filter(Boolean);
  if (new Set(ids).size !== ids.length) return "Source IDs must be unique.";
  return null;
}

export function resultTone(result: PipelineResult | null | undefined) {
  if (!result) return "neutral";
  if (result.disposition === "ABSTAINED") return "abstained";
  if (result.disposition === "ERROR") return "error";
  return result.logical_result?.toLowerCase() ?? "neutral";
}
