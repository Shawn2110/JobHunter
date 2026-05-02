#!/usr/bin/env python3
"""JobHunt initial setup CLI.

Asks for the one required key — Anthropic — and writes it to .env.
Every other provider key is optional; defaults are baked in. Add
aggregator / search / crawler keys to .env later when you want
them. See .env.example for the full list.

Usage:
    python scripts/setup_ai.py

Stdlib-only. Safe to run repeatedly — preserves any existing values
in .env (other than ANTHROPIC_API_KEY, which it overwrites if you
enter a new one).
"""

from __future__ import annotations

import getpass
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"
ENV_EXAMPLE = REPO_ROOT / ".env.example"


def main() -> int:
    print("─" * 60)
    print(" JobHunt — initial AI setup")
    print("─" * 60)

    if not ENV_EXAMPLE.exists():
        print(f"ERROR: .env.example not found at {ENV_EXAMPLE}")
        return 1

    if ENV_PATH.exists():
        existing = _read_env(ENV_PATH)
        print(f"\nFound existing .env at {ENV_PATH.relative_to(REPO_ROOT)}.")
    else:
        existing = {}
        print(f"\nNo .env yet — will create one at {ENV_PATH.relative_to(REPO_ROOT)}.")

    current_key = existing.get("ANTHROPIC_API_KEY", "").strip()

    print()
    if current_key:
        masked = (
            current_key[:8] + "…" + current_key[-4:]
            if len(current_key) > 14
            else "***"
        )
        print(f"Current ANTHROPIC_API_KEY: {masked}")
        print("Enter a new key, or press Enter to keep this one.")
    else:
        print("Anthropic API key — get one at https://console.anthropic.com")
        print()
        print("This is the ONLY key you need to start. It enables:")
        print("  • Resume parsing (Phase 1)")
        print("  • Fit assessment (Phase 3)")
        print("  • Trust assessment (Phase 3.5)")
        print("  • Resume tailoring (Phase 4)")
        print("  • Cover letters + custom-question answers (Phase 5)")
        print("  • Outreach drafting (Phase 7)")
        print()
        print("Other providers (job aggregators, search APIs, crawler) are")
        print("optional — add them in .env later when you want them.")

    print()
    new_key = getpass.getpass("ANTHROPIC_API_KEY (input hidden): ").strip()

    if new_key:
        if not new_key.startswith(("sk-ant-", "sk-")):
            print()
            print("⚠ Warning: key doesn't start with 'sk-ant-'. Saving anyway")
            print("  in case the prefix changes — verify it with one real call.")
        existing["ANTHROPIC_API_KEY"] = new_key
    elif not current_key:
        print()
        print("✗ No key provided and none on file. Aborting.")
        return 1

    _write_env(ENV_PATH, existing)

    print()
    print("─" * 60)
    print(f"✓ Saved to {ENV_PATH.relative_to(REPO_ROOT)}")
    print("─" * 60)
    print()
    print("Next steps:")
    print("  1. (Re)start the backend so it picks up the new .env:")
    print("       cd backend")
    print("       .venv/Scripts/python -m uvicorn app.main:app --reload")
    print("     (Linux/macOS: source .venv/bin/activate first)")
    print()
    print("  2. Visit http://localhost:3000 → /profile → upload your resume.")
    print()
    print("  3. (Optional) Add aggregator keys to .env later for Mode 1")
    print("     search results. Reddit job-search subreddits work today")
    print("     with no extra keys via the founder-post mode.")
    return 0


def _read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.lstrip().startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def _write_env(path: Path, values: dict[str, str]) -> None:
    """Preserve .env.example structure (comments + ordering); replace
    values where present, append keys that aren't in the template."""
    template = ENV_EXAMPLE.read_text(encoding="utf-8")
    out_lines: list[str] = []
    written: set[str] = set()
    for line in template.splitlines():
        stripped = line.lstrip()
        if "=" in line and not stripped.startswith("#"):
            k, _, _ = line.partition("=")
            k = k.strip()
            if k in values:
                out_lines.append(f"{k}={values[k]}")
                written.add(k)
                continue
        out_lines.append(line)
    for k, v in values.items():
        if k not in written:
            out_lines.append(f"{k}={v}")
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
