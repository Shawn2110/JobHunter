from __future__ import annotations

import re
from difflib import SequenceMatcher

_SUFFIXES = (
    "private limited",
    "pvt. ltd.",
    "pvt ltd",
    "pvt.",
    "pvt",
    "limited",
    "ltd.",
    "ltd",
    "inc.",
    "inc",
    "corp.",
    "corp",
    "llc",
    "gmbh",
    "co.",
    "co",
)

_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def canonical_company(name: str) -> str:
    """Normalize a company name for dedup.

    Lowercases, strips common legal suffixes, collapses non-alphanumerics
    to single spaces. Matches "Razorpay Software Pvt. Ltd." and
    "Razorpay" to the same canonical "razorpay software".
    """
    n = name.lower().strip()
    for suffix in _SUFFIXES:
        if n.endswith(" " + suffix):
            n = n[: -len(suffix) - 1].strip()
    n = _NORMALIZE_RE.sub(" ", n)
    return " ".join(n.split())


def normalize_title(title: str) -> str:
    return " ".join(_NORMALIZE_RE.sub(" ", title.lower()).split())


def description_similarity(a: str | None, b: str | None) -> float:
    """Quick Levenshtein-ish similarity (0.0–1.0) using stdlib SequenceMatcher.

    Returns 1.0 when both descriptions are empty (treat as match — no
    information either way). Returns 0.0 when one is empty and the other
    isn't.
    """
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a[:5000], b[:5000]).ratio()


def is_duplicate(
    a_company: str,
    a_title: str,
    a_description: str | None,
    b_company: str,
    b_title: str,
    b_description: str | None,
    desc_threshold: float = 0.6,
) -> bool:
    """Two jobs are duplicates when canonical company AND normalized title
    match exactly, AND descriptions are at least `desc_threshold` similar.
    """
    if canonical_company(a_company) != canonical_company(b_company):
        return False
    if normalize_title(a_title) != normalize_title(b_title):
        return False
    return description_similarity(a_description, b_description) >= desc_threshold
