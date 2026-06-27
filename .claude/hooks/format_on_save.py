#!/usr/bin/env python
"""Format-on-save hook for graduation-arena.

Claude Code runs this as a PostToolUse hook after every Edit/Write. It reads the
hook payload from stdin, picks a formatter by file extension, and formats the
file in place:

  *.py                              -> ruff format
  *.ts/.tsx/.js/.json/.md/.yml/...  -> prettier --write

It is a deliberate no-op when the formatter is not installed, so it stays silent
until the Python and TypeScript toolchains land. It always exits 0 so a missing
or failing formatter never blocks an edit.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

PRETTIER_EXTS = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".json", ".jsonc", ".css", ".scss", ".html",
    ".md", ".mdx", ".yml", ".yaml",
}


def find_prettier() -> list[str] | None:
    """Locate prettier: on PATH, else a locally-installed copy under web/."""
    exe = shutil.which("prettier")
    if exe:
        return [exe]
    for base in ("web/node_modules/.bin/prettier", "node_modules/.bin/prettier"):
        for candidate in (base, base + ".cmd"):
            if os.path.isfile(candidate):
                return [candidate]
    return None


def formatter_for(path: str) -> list[str] | None:
    """Return the argv to format `path`, or None if nothing applies."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".py":
        ruff = shutil.which("ruff")
        return [ruff, "format", path] if ruff else None
    if ext in PRETTIER_EXTS:
        prettier = find_prettier()
        return [*prettier, "--write", path] if prettier else None
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = (payload.get("tool_input") or {}).get("file_path")
    if not path or not os.path.isfile(path):
        return 0

    cmd = formatter_for(path)
    if not cmd:
        return 0

    try:
        subprocess.run(
            cmd,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass  # formatter vanished mid-flight; never block the edit
    return 0


if __name__ == "__main__":
    sys.exit(main())
