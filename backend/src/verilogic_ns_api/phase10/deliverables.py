from __future__ import annotations

import json
from pathlib import Path

from verilogic_ns_api.baselines.configuration import repository_root
from verilogic_ns_api.phase10.evidence import build_final_evidence, write_final_evidence

REPORT_PATH = Path("docs/FINAL_REPORT.md")
PRESENTATION_NOTES_PATH = Path("presentations/VeriLogic-NS-Final-Presentation.md")
PRESENTATION_PATH = Path("presentations/VeriLogic-NS-Final-Presentation.pptx")
DEMO_GUIDE_PATH = Path("docs/FINAL_DEMO_GUIDE.md")

REQUIRED_REPORT_HEADINGS = (
    "# VeriLogic-NS: Final Technical and Research Report",
    "## Abstract",
    "## 1. Problem statement",
    "## 2. Objectives",
    "## 3. Background and motivation",
    "## 4. System architecture",
    "## 5. Dataset and experimental controls",
    "## 6. Neural semantic parsing",
    "## 7. Symbolic reasoning engine",
    "## 8. Validation, critic, and correction",
    "## 9. Reliability policies",
    "## 10. Proof verification and explainability",
    "## 11. Backend and API",
    "## 12. Research frontend",
    "## 13. Experimental methodology",
    "## 14. Baselines",
    "## 15. Phase 9 results",
    "## 16. Ablation comparisons",
    "## 17. Replay and reproducibility",
    "## 18. Deployment and demonstration",
    "## 19. Security and cost",
    "## 20. Limitations",
    "## 21. Future work",
    "## 22. Conclusion",
    "## 23. Reproduction guide",
)


def validate_deliverables(root: Path | None = None) -> dict[str, object]:
    resolved = repository_root(root or Path.cwd())
    write_final_evidence(resolved, check=True)
    evidence = build_final_evidence(resolved)
    report = (resolved / REPORT_PATH).read_text(encoding="utf-8")
    notes = (resolved / PRESENTATION_NOTES_PATH).read_text(encoding="utf-8")
    demo = (resolved / DEMO_GUIDE_PATH).read_text(encoding="utf-8")
    if not (resolved / PRESENTATION_PATH).is_file():
        raise ValueError("final PowerPoint presentation is missing")
    missing = [heading for heading in REQUIRED_REPORT_HEADINGS if heading not in report]
    if missing:
        raise ValueError(f"final report headings are incomplete: {missing}")

    required_claims = (
        f"Evidence package fingerprint: `{evidence.package_fingerprint}`",
        "30 development examples",
        "No test-set experiment was performed",
        "same-selection, different-representation formal symbolic ceiling",
        "P1/P2 exact token totals are unavailable",
        "three typed terminal correction/cache failures",
        "ProofWriter licence remains unverified",
        "Direct | 16/30",
        "Few-shot | 16/30",
        "P0 raw neuro-symbolic | 4/30",
        "P2 selective | 1/30",
        "Formal symbolic oracle ceiling | 30/30",
    )
    for claim in required_claims:
        if claim not in report:
            raise ValueError(f"final report is missing an evidence-bound claim: {claim}")
        if claim not in notes:
            raise ValueError(f"presentation source is missing an evidence-bound claim: {claim}")
    if "do not run the 30-record experiment" not in demo.lower():
        raise ValueError("final demo guide does not prohibit experiment reruns")
    if "provider-free" not in demo.lower() or "proof" not in demo.lower():
        raise ValueError("final demo guide omits the provider-free proof flow")
    return {
        "status": "VERIFIED",
        "evidence_package_fingerprint": evidence.package_fingerprint,
        "report_sections": len(REQUIRED_REPORT_HEADINGS),
        "presentation_source": PRESENTATION_NOTES_PATH.as_posix(),
        "presentation": PRESENTATION_PATH.as_posix(),
        "demo_guide": DEMO_GUIDE_PATH.as_posix(),
    }


def load_presentation_evidence(root: Path | None = None) -> dict[str, object]:
    resolved = repository_root(root or Path.cwd())
    return json.loads((resolved / "research/evidence/phase10-final-evidence.v1.json").read_text())
