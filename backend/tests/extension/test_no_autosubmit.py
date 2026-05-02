"""Per Agent.md § Critical Do-Not-Break Tests:

The browser extension autofills form fields. It does NOT click submit.
This test guards that contract structurally — any pattern that could
trigger form submission from the extension's content script is
forbidden.

If this test fails, the extension is broken in a way that matters
more than features. Do not work around it.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EXTENSION_DIR = REPO_ROOT / "extension"

# Patterns that would submit a form. Each is matched against every
# .js / .ts file under extension/.
_FORBIDDEN = [
    re.compile(r"\.submit\s*\(", re.IGNORECASE),
    re.compile(r"form\.submit\b", re.IGNORECASE),
    re.compile(r"requestSubmit\s*\("),
    re.compile(r"type\s*=\s*['\"]submit['\"][^>]*\.click\s*\("),
    # Pressing Enter to submit
    re.compile(r"key\s*:\s*['\"]Enter['\"]"),
    re.compile(r"keyCode\s*:\s*13"),
]


def _scan_files() -> list[Path]:
    return [
        p
        for p in EXTENSION_DIR.rglob("*")
        if p.is_file() and p.suffix in {".js", ".ts", ".tsx", ".mjs"}
    ]


_LINE_COMMENT_RE = re.compile(r"//.*?$", re.MULTILINE)
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_comments(text: str) -> str:
    """Remove JS line + block comments so doc text doesn't trigger
    false positives."""
    text = _BLOCK_COMMENT_RE.sub("", text)
    text = _LINE_COMMENT_RE.sub("", text)
    return text


def test_extension_never_submits_forms() -> None:
    offenders: list[tuple[Path, str, str]] = []
    for path in _scan_files():
        text = _strip_comments(path.read_text(encoding="utf-8"))
        for pat in _FORBIDDEN:
            for m in pat.finditer(text):
                offenders.append((path, pat.pattern, m.group(0)))

    assert offenders == [], (
        "Extension must never submit forms. Offending matches:\n"
        + "\n".join(
            f"  {p.relative_to(REPO_ROOT)}: pattern {pat!r} matched {found!r}"
            for p, pat, found in offenders
        )
    )


def test_extension_uses_only_localhost_backend() -> None:
    """The extension's only outbound HTTP target must be localhost:8000.

    Per Agent.md § 6, no telemetry / no off-machine endpoints.
    """
    fetch_pattern = re.compile(r"(?:fetch|XMLHttpRequest)\s*\([^)]*['\"]https?://([^/'\"]+)")
    offenders: list[tuple[Path, str]] = []
    for path in _scan_files():
        text = _strip_comments(path.read_text(encoding="utf-8"))
        for match in fetch_pattern.finditer(text):
            host = match.group(1)
            if host not in {"localhost:8000", "127.0.0.1:8000"}:
                offenders.append((path, host))

    assert offenders == [], (
        "Extension may only call localhost:8000. Offending hosts:\n"
        + "\n".join(f"  {p.relative_to(REPO_ROOT)}: {host}" for p, host in offenders)
    )
