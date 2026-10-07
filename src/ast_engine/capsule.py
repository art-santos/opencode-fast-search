"""Fast AST symbol capsule compiler. Target: <15ms, <1500 tokens."""

from __future__ import annotations

import os
import re

from src.ast_engine.indexer import extract_symbols, iter_ts_files

_TOKEN_RX = re.compile(r"[a-z0-9_]+", re.I)


def _qtokens(query: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RX.findall(query) if len(t) > 1}


def _score_file(path: str, symbols: list, qtokens: set[str]) -> float:
    hay = f"{os.path.basename(path)} " + " ".join(s.name for s in symbols)
    hay_low = hay.lower()
    score = sum(1.0 for q in qtokens if q in hay_low)
    # filename stem bonus
    stem = os.path.basename(path).lower()
    score += sum(0.5 for q in qtokens if q in stem)
    return score


def build_capsule(target_path: str, query: str, limit: int = 12) -> str:
    qtokens = _qtokens(query)
    entries: list[tuple[float, str, list]] = []
    if os.path.isfile(target_path):
        syms = extract_symbols(target_path)
        entries.append((_score_file(target_path, syms, qtokens) + 1.0, target_path, syms))
    elif os.path.isdir(target_path):
        for fp in iter_ts_files(target_path):
            syms = extract_symbols(fp)
            if not syms:
                continue
            s = _score_file(fp, syms, qtokens)
            if s > 0 or len(entries) < limit:
                entries.append((s, fp, syms))
    else:
        return f"[capsule] target not found: {target_path}\n"
    entries.sort(key=lambda e: -e[0])
    lines = [f"[capsule query={query!r} files={len(entries)}]"]
    for _score, fp, syms in entries[:limit]:
        try:
            total = sum(1 for _ in open(fp, encoding="utf-8", errors="replace"))
        except OSError:
            total = 0
        lines.append(f"@ref:{fp}:1-{total}")
        for s in syms[:20]:
            lines.append(f"  {s.kind} {s.name} # line {s.line}")
    out = "\n".join(lines)
    return out[:6000]
