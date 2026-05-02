from __future__ import annotations

import re

from app.trust.longitudinal import GhostJobSignal
from app.trust.rules import RuleHit
from app.trust.verdict import compose_verdict


def _hit(severity: str, rid: str = "x") -> RuleHit:
    return RuleHit(id=rid, severity=severity, description=rid, matched_text="...")  # type: ignore[arg-type]


AI_VERIFIED = {
    "verdict": "verified",
    "additional_signals_found": [],
    "ai_check_score": 90,
    "rationale_md": "Looks legit.",
}
AI_LIKELY_REAL = {**AI_VERIFIED, "verdict": "likely_real", "ai_check_score": 75}
AI_LIKELY_SCAM = {**AI_VERIFIED, "verdict": "likely_scam", "ai_check_score": 10}
AI_UNKNOWN = {**AI_VERIFIED, "verdict": "unknown", "ai_check_score": 50}


def test_scam_strong_rule_forces_likely_scam() -> None:
    out = compose_verdict(
        rule_hits=[_hit("scam_strong", "payment_fee")],
        ai_result=AI_VERIFIED,  # AI says verified, but rule wins
        longitudinal_signals=[],
    )
    assert out.verdict == "likely_scam"


def test_three_warnings_triggers_suspicious() -> None:
    out = compose_verdict(
        rule_hits=[_hit("warning", "w1"), _hit("warning", "w2"), _hit("warning", "w3")],
        ai_result=AI_LIKELY_REAL,
        longitudinal_signals=[],
    )
    assert out.verdict == "suspicious"


def test_ai_likely_scam_triggers_suspicious_without_rule_hit() -> None:
    out = compose_verdict(
        rule_hits=[],
        ai_result=AI_LIKELY_SCAM,
        longitudinal_signals=[],
    )
    assert out.verdict == "suspicious"


def test_strong_ghost_signal_triggers_suspicious() -> None:
    out = compose_verdict(
        rule_hits=[],
        ai_result=AI_LIKELY_REAL,
        longitudinal_signals=[
            GhostJobSignal(kind="reposts", description="x", severity="strong"),
        ],
    )
    assert out.verdict == "suspicious"


def test_verified_path_requires_clean_signals() -> None:
    out = compose_verdict(
        rule_hits=[],
        ai_result=AI_VERIFIED,
        longitudinal_signals=[],
        web_footprint_positive=True,
    )
    assert out.verdict == "verified"


def test_unknown_when_evidence_thin() -> None:
    out = compose_verdict(
        rule_hits=[],
        ai_result=AI_UNKNOWN,
        longitudinal_signals=[],
    )
    assert out.verdict == "unknown"


def test_signal_arrays_built_from_inputs() -> None:
    out = compose_verdict(
        rule_hits=[
            _hit("scam_strong", "payment_fee"),
            _hit("warning", "mlm"),
            _hit("info", "evergreen"),
        ],
        ai_result={
            "verdict": "likely_scam",
            "additional_signals_found": [
                {"kind": "scam", "description": "AI-found scam pattern"},
                {"kind": "ghost", "description": "AI-found ghost pattern"},
                {"kind": "positive", "description": "named team"},
            ],
            "ai_check_score": 5,
            "rationale_md": "x",
        },
        longitudinal_signals=[
            GhostJobSignal(kind="reposts", description="reposted 5x", severity="warning"),
        ],
    )
    assert len(out.scam_signals) == 3   # 2 from rules (scam_strong+warning) + 1 AI
    assert len(out.ghost_job_signals) == 2  # 1 longitudinal + 1 AI
    assert len(out.positive_signals) == 2   # 1 info-rule + 1 AI


def test_rationale_prefixed_when_signals_present() -> None:
    out = compose_verdict(
        rule_hits=[_hit("scam_strong", "payment_fee")],
        ai_result=AI_LIKELY_SCAM,
        longitudinal_signals=[],
    )
    assert "Scam signals" in out.rationale_md
    assert re.search(r"\d+\s+hit", out.rationale_md)
