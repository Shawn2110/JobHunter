from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.trust.longitudinal import GhostJobSignal
from app.trust.rules import RuleHit

Verdict = Literal["verified", "likely_real", "suspicious", "likely_scam", "unknown"]


@dataclass(frozen=True)
class ComposedVerdict:
    verdict: Verdict
    scam_signals: list[dict[str, Any]]
    ghost_job_signals: list[dict[str, Any]]
    positive_signals: list[dict[str, Any]]
    rationale_md: str


def compose_verdict(
    *,
    rule_hits: list[RuleHit],
    ai_result: dict[str, Any],
    longitudinal_signals: list[GhostJobSignal],
    web_footprint_positive: bool = False,
) -> ComposedVerdict:
    """Combine Layer A (rules), Layer B (AI), and Layer C (longitudinal)
    into a final verdict per Architecture.md § 5.6.
    """
    has_scam_strong = any(h.severity == "scam_strong" for h in rule_hits)
    warning_count = sum(1 for h in rule_hits if h.severity == "warning")
    ai_verdict = ai_result.get("verdict", "unknown")

    has_strong_ghost = any(s.severity == "strong" for s in longitudinal_signals)
    has_warning_ghost = any(s.severity == "warning" for s in longitudinal_signals)

    # Decision tree, in priority order
    if has_scam_strong:
        verdict: Verdict = "likely_scam"
    elif ai_verdict == "likely_scam" or warning_count >= 3:
        verdict = "suspicious"
    elif has_strong_ghost or has_warning_ghost:
        verdict = "suspicious"
    elif ai_verdict == "verified" and web_footprint_positive and not rule_hits:
        verdict = "verified"
    elif ai_verdict == "likely_real" and web_footprint_positive:
        verdict = "likely_real"
    elif ai_verdict in ("verified", "likely_real") and not rule_hits:
        # AI is positive and nothing flagged — accept the lower-confidence label
        verdict = ai_verdict  # type: ignore[assignment]
    else:
        verdict = "unknown"

    # Build the signal arrays
    scam_signals = [
        {
            "id": h.id,
            "severity": h.severity,
            "description": h.description,
            "source": "static_rules",
        }
        for h in rule_hits
        if h.severity in ("scam_strong", "warning")
    ]
    for s in ai_result.get("additional_signals_found", []):
        if s.get("kind") == "scam":
            scam_signals.append({
                "id": "ai_finding",
                "severity": "warning",
                "description": s.get("description", ""),
                "source": "ai_check",
            })

    ghost_job_signals = [
        {
            "kind": s.kind,
            "severity": s.severity,
            "description": s.description,
            "source": "longitudinal",
        }
        for s in longitudinal_signals
    ]
    for s in ai_result.get("additional_signals_found", []):
        if s.get("kind") == "ghost":
            ghost_job_signals.append({
                "kind": "ai_finding",
                "severity": "warning",
                "description": s.get("description", ""),
                "source": "ai_check",
            })

    positive_signals = [
        {
            "kind": "info",
            "severity": h.severity,
            "description": h.description,
        }
        for h in rule_hits
        if h.severity == "info"
    ]
    for s in ai_result.get("additional_signals_found", []):
        if s.get("kind") == "positive":
            positive_signals.append({
                "kind": "ai_finding",
                "severity": "info",
                "description": s.get("description", ""),
                "source": "ai_check",
            })

    rationale = ai_result.get("rationale_md") or "No detailed rationale available."
    if scam_signals or ghost_job_signals:
        prefix_lines = []
        if scam_signals:
            prefix_lines.append(f"**Scam signals:** {len(scam_signals)} hit(s).")
        if ghost_job_signals:
            prefix_lines.append(f"**Ghost-job signals:** {len(ghost_job_signals)} hit(s).")
        rationale = "\n".join(prefix_lines) + "\n\n" + rationale

    return ComposedVerdict(
        verdict=verdict,
        scam_signals=scam_signals,
        ghost_job_signals=ghost_job_signals,
        positive_signals=positive_signals,
        rationale_md=rationale,
    )
