from __future__ import annotations

from collections import defaultdict

from verilogic_ns_api.reasoning.models import (
    EntityTerm,
    GroundLiteral,
    RuleLiteral,
    Theory,
    VariableTerm,
    canonical_theory_payload,
    theory_hash,
)
from verilogic_ns_api.research_frontend.models import (
    AstInspectionRequest,
    CorrectionDiff,
    LiteralView,
    NormalizedAstInspection,
    PredicateView,
    RuleView,
    SourceMappingView,
    TermView,
    sha256_json,
)


def inspect_ast(request: AstInspectionRequest) -> NormalizedAstInspection:
    theory = request.accepted_theory
    facts = tuple(_literal_view(item) for item in theory.facts)
    rules = tuple(
        RuleView(
            rule_id=rule.id,
            variables=tuple(item.name for item in rule.variables),
            premises=tuple(_literal_view(item) for item in rule.body),
            conclusion=_literal_view(rule.head),
            source_id=rule.source_id,
        )
        for rule in theory.rules
    )
    query = _literal_view(theory.query)
    references: dict[str, list[str]] = defaultdict(list)
    for index, fact in enumerate(theory.facts, start=1):
        references[fact.source_id].append(f"fact:{index}")
    for rule in theory.rules:
        references[rule.source_id].append(f"rule:{rule.id}")
        for index, literal in enumerate(rule.body, start=1):
            references[literal.source_id].append(f"rule:{rule.id}:premise:{index}")
        references[rule.head.source_id].append(f"rule:{rule.id}:conclusion")
    references[theory.query.source_id].append("query")
    source_mapping = tuple(
        SourceMappingView(
            source_id=source.id,
            text=source.text,
            referenced_by=tuple(sorted(set(references.get(source.id, [])))),
        )
        for source in theory.source_statements
    )
    complete = all(item.referenced_by for item in source_mapping)
    return NormalizedAstInspection(
        theory_id=theory.theory_id,
        canonical_theory_id=theory_hash(theory),
        facts=facts,
        rules=rules,
        query=query,
        predicates=tuple(
            PredicateView(
                name=item.name,
                arity=item.arity,
                argument_types=item.argument_types,
            )
            for item in theory.predicates
        ),
        entities=tuple(
            {"id": item.id, "label": item.label, "type": item.type} for item in theory.entities
        ),
        source_mapping=source_mapping,
        source_coverage_status="COMPLETE" if complete else "INCOMPLETE",
        correction_attempted=request.correction_attempted,
        correction_diff=_correction_diff(request.pre_correction_theory, theory),
        proof_roots=request.proof_roots,
        canonical_json=canonical_theory_payload(theory),
    )


def _literal_view(literal: GroundLiteral | RuleLiteral) -> LiteralView:
    arguments = tuple(_term_view(item) for item in literal.arguments)
    sign = "not " if literal.negated else ""
    rendered = f"{sign}{literal.predicate}({', '.join(item.value for item in arguments)})"
    identity = {
        "predicate": literal.predicate,
        "arguments": [item.model_dump(mode="json") for item in arguments],
        "negated": literal.negated,
        "source_id": literal.source_id,
    }
    return LiteralView(
        canonical_id=sha256_json(identity),
        predicate=literal.predicate,
        arguments=arguments,
        negated=literal.negated,
        source_id=literal.source_id,
        display=rendered,
    )


def _term_view(term: EntityTerm | VariableTerm) -> TermView:
    if isinstance(term, EntityTerm):
        return TermView(kind="entity", value=term.id)
    return TermView(kind="variable", value=term.name)


def _correction_diff(before: Theory | None, after: Theory) -> CorrectionDiff:
    if before is None:
        return CorrectionDiff(
            available=False, reason="Pre-correction normalized AST is unavailable."
        )
    before_items = _theory_items(before)
    after_items = _theory_items(after)
    before_values = set(before_items.values())
    after_values = set(after_items.values())
    shared_sources = set(before_items) & set(after_items)
    changed_predicates: set[str] = set()
    changed_arguments: set[str] = set()
    changed_polarity: set[str] = set()
    changed_sources: set[str] = set()
    for source in shared_sources:
        left = before_items[source]
        right = after_items[source]
        if left[0] != right[0]:
            changed_predicates.add(source)
        if left[1] != right[1]:
            changed_arguments.add(source)
        if left[2] != right[2]:
            changed_polarity.add(source)
        if left[3] != right[3]:
            changed_sources.add(source)
    return CorrectionDiff(
        available=True,
        additions=tuple(sorted(_render_tuple(item) for item in after_values - before_values)),
        removals=tuple(sorted(_render_tuple(item) for item in before_values - after_values)),
        changed_predicates=tuple(sorted(changed_predicates)),
        changed_arguments=tuple(sorted(changed_arguments)),
        changed_polarity=tuple(sorted(changed_polarity)),
        changed_source_references=tuple(sorted(changed_sources)),
    )


def _theory_items(theory: Theory) -> dict[str, tuple[str, tuple[str, ...], bool, str]]:
    items: dict[str, tuple[str, tuple[str, ...], bool, str]] = {}
    for index, fact in enumerate(theory.facts, start=1):
        items[f"fact:{fact.source_id}:{index}"] = _literal_tuple(fact)
    for rule in theory.rules:
        for index, literal in enumerate(rule.body, start=1):
            items[f"rule:{rule.id}:body:{index}"] = _literal_tuple(literal)
        items[f"rule:{rule.id}:head"] = _literal_tuple(rule.head)
    items["query"] = _literal_tuple(theory.query)
    return items


def _literal_tuple(
    literal: GroundLiteral | RuleLiteral,
) -> tuple[str, tuple[str, ...], bool, str]:
    arguments = tuple(
        item.id if isinstance(item, EntityTerm) else item.name for item in literal.arguments
    )
    return (literal.predicate, arguments, literal.negated, literal.source_id)


def _render_tuple(item: tuple[str, tuple[str, ...], bool, str]) -> str:
    predicate, arguments, negated, source = item
    return f"{'not ' if negated else ''}{predicate}({', '.join(arguments)}) [{source}]"
