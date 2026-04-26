from __future__ import annotations

from urllib.parse import urlparse

# Per Architecture.md § 7 — ATS family detection from apply_url.
_RULES: list[tuple[str, str]] = [
    ("myworkdayjobs.com", "workday"),
    ("workdayjobs.com", "workday"),
    ("greenhouse.io", "greenhouse"),
    ("lever.co", "lever"),
    ("icims.com", "icims"),
    ("taleo.net", "taleo"),
    ("smartrecruiters.com", "smartrecruiters"),
    ("ashbyhq.com", "ashby"),
    ("naukri.com", "naukri"),
    ("foundit.in", "foundit"),
    ("instahyre.com", "instahyre"),
    ("cutshort.io", "cutshort"),
    ("hasjob.co", "hasjob"),
    ("wellfound.com", "wellfound"),
    ("angel.co", "wellfound"),
]


def detect_ats_family(apply_url: str | None) -> str | None:
    """Classify the ATS family from a job's apply URL.

    Returns one of: workday, greenhouse, lever, icims, taleo,
    smartrecruiters, ashby, naukri, foundit, instahyre, cutshort,
    hasjob, wellfound — or None if no rule matches.
    """
    if not apply_url:
        return None
    try:
        host = (urlparse(apply_url).hostname or "").lower()
    except (ValueError, TypeError):
        return None
    if not host:
        return None
    for needle, family in _RULES:
        if needle in host:
            return family
    return None
