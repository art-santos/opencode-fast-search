"""Regex-based TS symbol indexer. No native deps, <15ms per file."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

PATTERNS = [
    ("class", re.compile(r"^\s*(?:export\s+)?(?:abstract\s+)?class\s+(\w+)", re.M)),
    ("interface", re.compile(r"^\s*(?:export\s+)?interface\s+(\w+)", re.M)),
    ("type", re.compile(r"^\s*(?:export\s+)?type\s+(\w+)", re.M)),
    ("function", re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+(\w+)", re.M)),
    ("const", re.compile(r"^\s*export\s+const\s+(\w+)", re.M)),
    ("enum", re.compile(r"^\s*(?:export\s+)?enum\s+(\w+)", re.M)),
]

SKIP_DIRS = {".git", "node_modules", ".venv", "dist", "build", ".next"}


@dataclass
class Symbol:
    kind: str
    name: str
    line: int


def extract_symbols(file_path: str) -> list[Symbol]:
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return []
    text = "".join(lines)
    # Build line offsets for char->line mapping
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    import bisect

    symbols: list[Symbol] = []
    for kind, rx in PATTERNS:
        for m in rx.finditer(text):
            line_no = bisect.bisect_right(offsets, m.start())
            symbols.append(Symbol(kind=kind, name=m.group(1), line=line_no))
    symbols.sort(key=lambda s: s.line)
    return symbols


def iter_ts_files(root: str) -> list[str]:
    out: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith((".ts", ".tsx")) and not fn.endswith(".d.ts.map"):
                out.append(os.path.join(dirpath, fn))
        if len(out) > 400:
            break
    return out
