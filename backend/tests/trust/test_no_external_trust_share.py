"""Per Agent.md § Critical Do-Not-Break Tests:

Trust verdicts must never leave the local SQLite. They are not shared
with companies, not sent to telemetry, not posted to any public list.
This test provides a simple structural guard.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend" / "app"

# Patterns that would indicate trust verdicts being sent off-machine.
_FORBIDDEN_PATTERNS = [
    # No telemetry / analytics shipping trust data
    re.compile(r"sentry.*trust", re.IGNORECASE),
    re.compile(r"datadog.*trust", re.IGNORECASE),
    re.compile(r"posthog.*trust", re.IGNORECASE),
    re.compile(r"segment.*trust", re.IGNORECASE),
    re.compile(r"mixpanel.*trust", re.IGNORECASE),
    # No publishing trust data to any HTTP endpoint outside this project
    re.compile(r"requests\.post.*trust", re.IGNORECASE),
    re.compile(r"httpx.*post.*trust", re.IGNORECASE),
]


def test_no_outbound_trust_publication() -> None:
    """Scan backend source for any pattern that would publish trust data.

    A failure here means someone added code that ships trust verdicts
    off the user's machine. That violates PRD § 3.9 and Agent.md § 8.
    Do not work around this test — fix the offending code.
    """
    offenders: list[tuple[Path, str]] = []
    for py_file in BACKEND.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for pat in _FORBIDDEN_PATTERNS:
            if pat.search(text):
                offenders.append((py_file, pat.pattern))
    assert offenders == [], (
        "Trust verdicts must never leave local SQLite. Offending matches:\n"
        + "\n".join(f"  {p.relative_to(REPO_ROOT)}: {pat}" for p, pat in offenders)
    )


def test_trust_assessment_table_has_no_outbound_references() -> None:
    """Sanity-check: the TrustAssessment model module doesn't import any
    HTTP/telemetry library."""
    trust_model = BACKEND / "models" / "trust.py"
    text = trust_model.read_text(encoding="utf-8")
    forbidden = ["httpx", "requests", "sentry_sdk", "posthog", "segment"]
    for needle in forbidden:
        assert needle not in text, (
            f"models/trust.py imports {needle!r} — trust data must stay local"
        )
