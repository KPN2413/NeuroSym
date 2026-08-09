import type { NaturalLanguageStatement } from "./neurosymbolic-contract.generated";

const entity = (id: string) => ({ kind: "entity", id });

const source = (id: string, text: string) => ({ id, text });

const literal = (predicate: string, id: string, sourceId: string, negated = false) => ({
  predicate,
  arguments: [entity(id)],
  negated,
  source_id: sourceId,
});

function baseTheory(
  theoryId: string,
  sources: Array<{ id: string; text: string }>,
  facts: Array<Record<string, unknown>>,
  rules: Array<Record<string, unknown>>,
  predicates: string[],
  query: Record<string, unknown>,
) {
  return {
    schema_version: "1.0",
    theory_id: theoryId,
    source_statements: sources,
    entities: [{ id: "robin", label: "Robin" }],
    predicates: predicates.map((name) => ({ name, arity: 1 })),
    facts,
    rules,
    query,
  };
}

const entailedQuery = literal("warm", "robin", "q1");
const entailedTheory = baseTheory(
  "preset_entailed",
  [
    source("s1", "The robin is red."),
    source("s2", "Every red thing is warm."),
    source("q1", "Is the robin warm?"),
  ],
  [literal("red", "robin", "s1")],
  [
    {
      id: "s2",
      variables: [{ name: "X" }],
      body: [
        {
          predicate: "red",
          arguments: [{ kind: "variable", name: "X" }],
          negated: false,
          source_id: "s2",
        },
      ],
      head: {
        predicate: "warm",
        arguments: [{ kind: "variable", name: "X" }],
        negated: false,
        source_id: "s2",
      },
      source_id: "s2",
    },
  ],
  ["red", "warm"],
  entailedQuery,
);

const contradictedQuery = literal("warm", "robin", "q1");
const contradictedTheory = baseTheory(
  "preset_contradicted",
  [source("s1", "The robin is not warm."), source("q1", "Is the robin warm?")],
  [literal("warm", "robin", "s1", true)],
  [],
  ["warm"],
  contradictedQuery,
);

const unknownQuery = literal("warm", "robin", "q1");
const unknownTheory = baseTheory(
  "preset_unknown",
  [source("s1", "The robin is red."), source("q1", "Is the robin warm?")],
  [literal("red", "robin", "s1")],
  [],
  ["red", "warm"],
  unknownQuery,
);

const inconsistentQuery = literal("warm", "robin", "q1");
const inconsistentTheory = baseTheory(
  "preset_inconsistent",
  [
    source("s1", "The robin is warm."),
    source("s2", "The robin is not warm."),
    source("q1", "Is the robin warm?"),
  ],
  [literal("warm", "robin", "s1"), literal("warm", "robin", "s2", true)],
  [],
  ["warm"],
  inconsistentQuery,
);

export const FORMAL_PRESETS = {
  ENTAILED: { theory: entailedTheory, query: entailedQuery },
  CONTRADICTED: { theory: contradictedTheory, query: contradictedQuery },
  UNKNOWN: { theory: unknownTheory, query: unknownQuery },
  INCONSISTENT: { theory: inconsistentTheory, query: inconsistentQuery },
} as const;

export const NATURAL_PRESET: { statements: NaturalLanguageStatement[]; query: string } = {
  statements: [
    { source_id: "source_1", kind: "fact", text: "The robin is red." },
    {
      source_id: "source_2",
      kind: "rule",
      text: "If something is red, then it is warm.",
    },
  ],
  query: "The robin is warm.",
};
