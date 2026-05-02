"""Per Agent.md § Critical Do-Not-Break Tests:

JobHunt must NEVER fetch LinkedIn pages. The only acceptable LinkedIn-
related operation is a Google/Brave search returning linkedin.com URLs
that the user clicks manually.

This test scans backend source for any pattern that would fetch a
LinkedIn page directly.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend" / "app"


# Patterns that fetch LinkedIn directly. Doing so via httpx, requests,
# urllib, playwright, or selenium would all be violations.
_FORBIDDEN = [
    re.compile(r"(?:httpx|requests|urllib)[^=]*['\"]https?://(?:[\w.-]+\.)?linkedin\.com", re.IGNORECASE),
    re.compile(r"client\.(?:get|post|head|put|delete)\([^)]*linkedin\.com", re.IGNORECASE),
    re.compile(r"playwright.*linkedin\.com", re.IGNORECASE),
    re.compile(r"selenium.*linkedin\.com", re.IGNORECASE),
    re.compile(r"webdriver.*linkedin\.com", re.IGNORECASE),
]

_LINE_COMMENT_RE = re.compile(r"#.*?$", re.MULTILINE)


def _strip_python_comments(text: str) -> str:
    return _LINE_COMMENT_RE.sub("", text)


def test_backend_never_fetches_linkedin_pages() -> None:
    offenders: list[tuple[Path, str, str]] = []
    for path in BACKEND.rglob("*.py"):
        text = _strip_python_comments(path.read_text(encoding="utf-8"))
        for pat in _FORBIDDEN:
            for m in pat.finditer(text):
                offenders.append((path, pat.pattern, m.group(0)[:100]))
    assert offenders == [], (
        "Backend must never fetch LinkedIn pages. Offending matches:\n"
        + "\n".join(
            f"  {p.relative_to(REPO_ROOT)}: {pat!r} matched {found!r}"
            for p, pat, found in offenders
        )
    )


def test_no_linkedin_in_discovery_adapters() -> None:
    """Stronger structural guard: there must NOT be a 'linkedin' adapter
    file in discovery/adapters/. The set of adapters is small and
    explicit; this catches anyone who tries to add one."""
    adapter_dir = BACKEND / "discovery" / "adapters"
    files = {p.name.lower() for p in adapter_dir.iterdir() if p.is_file()}
    forbidden = {"linkedin.py", "linkedin_jobs.py", "linkedin_scraper.py"}
    assert files & forbidden == set(), (
        f"discovery/adapters/ contains a LinkedIn adapter: {files & forbidden}. "
        "PRD § 3.2: no LinkedIn ingestion ever."
    )
