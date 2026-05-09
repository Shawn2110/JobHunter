"""Build a distributable zip of the browser extension.

The published zip lives at `release/jobhunt-extension-<version>.zip`
so the README download link resolves on GitHub. The version comes
straight from `extension/manifest.json` — bump it there and re-run.

Usage:
    python scripts/build_extension.py
"""

from __future__ import annotations

import json
import os
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "extension"
OUT_DIR = REPO_ROOT / "release"


def main() -> int:
    if not SRC.is_dir():
        print(f"error: {SRC} not found", file=sys.stderr)
        return 1
    manifest = json.loads((SRC / "manifest.json").read_text(encoding="utf-8"))
    version = manifest["version"]
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"jobhunt-extension-{version}.zip"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(SRC):
            for f in files:
                if f == ".gitkeep":
                    continue
                full = Path(root) / f
                arc = full.relative_to(SRC).as_posix()
                z.write(full, arc)
                print(f"  + {arc}")
    print(f"\nwrote {out.relative_to(REPO_ROOT)} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
