from __future__ import annotations

import pytest

from app.trust.rules import evaluate_text, load_rules, static_check_score


def test_load_rules_returns_nonempty() -> None:
    rules = load_rules()
    assert len(rules) > 0
    # Spot check one known rule
    assert any(r.id == "payment_registration_fee" for r in rules)


def test_payment_fee_triggers_scam_strong() -> None:
    text = "We charge a small registration fee of ₹2000 to start training."
    hits = evaluate_text(text)
    severities = [h.severity for h in hits]
    assert "scam_strong" in severities


def test_aadhaar_pre_offer_triggers_in_india_locale() -> None:
    text = "Please send Aadhaar before we can finalize."
    hits = evaluate_text(text, locale="india")
    assert any(h.id == "document_aadhaar_pre_offer" for h in hits)


def test_legitimate_text_no_hits() -> None:
    text = """
    Senior backend engineer to build payment infrastructure used by millions.
    Stack: Python, FastAPI, PostgreSQL. 4-7 years experience required.
    Apply via greenhouse: https://boards.greenhouse.io/acme.
    """
    hits = evaluate_text(text, locale="india")
    assert hits == []


def test_mlm_phrasing_triggers_warning() -> None:
    text = "Be your own boss with unlimited earning potential."
    hits = evaluate_text(text)
    severities = {h.severity for h in hits}
    assert "warning" in severities


def test_evergreen_phrasing_triggers_info_only() -> None:
    text = "We're always hiring great talent. Reach out anytime."
    hits = evaluate_text(text)
    assert hits and all(h.severity == "info" for h in hits)


def test_score_decreases_with_severity() -> None:
    base = 100
    info_hit = static_check_score(
        [_dummy_hit("info")]
    )
    warn_hit = static_check_score(
        [_dummy_hit("warning")]
    )
    scam_hit = static_check_score(
        [_dummy_hit("scam_strong")]
    )
    assert base > info_hit > warn_hit > scam_hit
    assert scam_hit == 60  # 100 - 40
    assert warn_hit == 85  # 100 - 15
    assert info_hit == 95  # 100 - 5


def test_score_floor_at_zero() -> None:
    hits = [_dummy_hit("scam_strong") for _ in range(10)]
    assert static_check_score(hits) == 0


def _dummy_hit(severity: str):
    from app.trust.rules import RuleHit
    return RuleHit(
        id="dummy",
        severity=severity,  # type: ignore[arg-type]
        description="x",
        matched_text="x",
    )
