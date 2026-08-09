from __future__ import annotations

from verilogic_ns_api.orchestration.models import (
    DeterministicExplanation,
    ExplanationStep,
)
from verilogic_ns_api.reasoning.models import (
    CanonicalLiteral,
    ProofDAG,
    ReasoningStatus,
    RuleApplicationNode,
    SourceFactNode,
)


def explanation_from_verified_proof(proof: ProofDAG) -> DeterministicExplanation:
    headline, summary = _answer_text(proof.status, proof.query)
    useful_nodes = [
        node for node in proof.nodes if isinstance(node, SourceFactNode | RuleApplicationNode)
    ]
    useful_nodes.sort(key=lambda item: (item.depth, item.node_type, item.node_id))
    steps: list[ExplanationStep] = []
    for sequence, node in enumerate(useful_nodes, start=1):
        if isinstance(node, SourceFactNode):
            statement = f"Use source fact {_literal_text(node.literal)}."
            kind = "fact"
        else:
            bindings = ", ".join(f"{item.variable}={item.entity}" for item in node.substitution)
            suffix = f" with {bindings}" if bindings else ""
            statement = (
                f"Apply rule {node.rule_id}{suffix} to derive {_literal_text(node.conclusion)}."
            )
            kind = "rule"
        steps.append(
            ExplanationStep(
                sequence=sequence,
                kind=kind,
                statement=statement,
                source_id=node.source_id,
                source_text=node.source_text,
                depth=node.depth,
                node_id=node.node_id,
            )
        )
    return DeterministicExplanation(
        headline=headline,
        summary=summary,
        steps=tuple(steps),
        support_root_id=proof.support_root_id,
        opposition_root_id=proof.opposition_root_id,
        proof_depth=max((node.depth for node in proof.nodes), default=0),
        proof_hash=proof.proof_hash,
        verifier_status="VERIFIED",
    )


def abstention_explanation(reason: str) -> DeterministicExplanation:
    return DeterministicExplanation(
        headline="Answer withheld",
        summary=(
            "The reliability policy did not release this formalisation to the symbolic answer "
            "stage. No logical result is claimed."
        ),
        verifier_status="NOT_APPLICABLE",
        reasons=(reason,),
    )


def error_explanation(stage: str, code: str) -> DeterministicExplanation:
    return DeterministicExplanation(
        headline="Pipeline error",
        summary=(
            f"The pipeline stopped safely at {stage} with typed error {code}. "
            "No logical result is claimed."
        ),
        verifier_status="NOT_APPLICABLE",
        reasons=(code,),
    )


def _answer_text(status: ReasoningStatus, query: CanonicalLiteral) -> tuple[str, str]:
    query_text = _literal_text(query)
    opposite_text = _literal_text(query.opposite())
    if status is ReasoningStatus.ENTAILED:
        return "Entailed", f"The accepted knowledge base derives {query_text}."
    if status is ReasoningStatus.CONTRADICTED:
        return "Contradicted", f"The accepted knowledge base derives {opposite_text}."
    if status is ReasoningStatus.INCONSISTENT:
        return (
            "Inconsistent",
            f"The accepted knowledge base derives both {query_text} and {opposite_text}.",
        )
    return (
        "Unknown",
        f"Neither {query_text} nor {opposite_text} is derivable from the accepted knowledge base.",
    )


def _literal_text(literal: CanonicalLiteral) -> str:
    prefix = "not " if literal.negated else ""
    return f"{prefix}{literal.predicate}({', '.join(literal.arguments)})"
