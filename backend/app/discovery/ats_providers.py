from __future__ import annotations

import re
from typing import Literal

AtsProvider = Literal["greenhouse", "lever", "ashby"]


_PATTERNS: list[tuple[re.Pattern[str], AtsProvider]] = [
    # Greenhouse: boards.greenhouse.io/<slug> or job-boards.greenhouse.io/<slug>
    # (also accepts the API form boards-api.greenhouse.io/v1/boards/<slug>).
    (
        re.compile(
            r"(?:boards|job-boards|boards-api)\.greenhouse\.io"
            r"(?:/v1/boards)?/([a-z0-9_-]+)",
            re.IGNORECASE,
        ),
        "greenhouse",
    ),
    # Lever: jobs.lever.co/<slug>
    (re.compile(r"jobs\.lever\.co/([a-z0-9_-]+)", re.IGNORECASE), "lever"),
    # Ashby: jobs.ashbyhq.com/<slug>
    (re.compile(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", re.IGNORECASE), "ashby"),
]


def detect_ats(url: str) -> tuple[AtsProvider, str] | None:
    """Identify the ATS provider + company slug from any URL form.

    Returns `(provider, slug)` on match, `None` otherwise. Matches are
    case-insensitive; the returned slug is lowercased for stable
    storage / lookup.
    """
    if not url:
        return None
    for pattern, provider in _PATTERNS:
        m = pattern.search(url)
        if m:
            return provider, m.group(1).lower()
    return None
