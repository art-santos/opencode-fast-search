"""Local Jev-compatible decision server.

Exposes POST /v1/systemone with typed noul / choice / score questions.
Deterministic lexical-overlap scorer — fast (<5ms), no model weights.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

STOP = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "to",
    "of", "in", "on", "for", "with", "and", "or", "it", "this", "that",
    "does", "do", "did", "what", "where", "when", "how", "why", "which",
    "i", "you", "we", "they", "he", "she", "my", "your", "our", "their",
    "at", "by", "from", "as", "if", "then", "than", "so", "but", "not",
    "no", "yes", "can", "could", "would", "should",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9_]+", text.lower())


def _keywords(text: str) -> set[str]:
    return {t for t in _tokens(text) if t not in STOP and len(t) > 1}


def _state_text(state: Any) -> str:
    if isinstance(state, str):
        return state
    try:
        return json.dumps(state, ensure_ascii=False)
    except Exception:
        return str(state)


def _overlap_ratio(state_kw: set[str], query_kw: set[str]) -> float:
    if not query_kw:
        return 0.0
    return len(state_kw & query_kw) / len(query_kw)


def _clamp(v: float, lo: float = 0.05, hi: float = 0.99) -> float:
    return max(lo, min(hi, v))


def _score_noul(state: str, instructions: str, criteria: Any) -> dict[str, Any]:
    state_kw = _keywords(state)
    crit_text = ""
    if isinstance(criteria, dict):
        crit_text = " ".join(str(v) for v in criteria.values())
    elif isinstance(criteria, list):
        crit_text = " ".join(str(v) for v in criteria)
    elif criteria is not None:
        crit_text = str(criteria)
    query_kw = _keywords(f"{instructions} {crit_text}")
    ratio = _overlap_ratio(state_kw, query_kw)
    # Boost: direct substring hits count extra
    low_state = state.lower()
    hits = sum(1 for k in query_kw if k in low_state)
    boost = min(0.3, hits * 0.1)
    prob = _clamp(0.5 + 0.5 * ratio + boost)
    conf = _clamp(0.55 + 0.4 * ratio + boost * 0.5)
    return {"type": "noul", "probability": round(prob, 4), "confidence": round(conf, 4)}


def _score_choice(state: str, instructions: str, criteria: Any) -> dict[str, Any]:
    state_kw = _keywords(state)
    if isinstance(criteria, dict):
        options = [(str(k), str(v) if v else str(k)) for k, v in criteria.items()]
    elif isinstance(criteria, list):
        options = [(str(v), str(v)) for v in criteria]
    else:
        raise ValueError("choice criteria must be an object or array")
    if not 1 <= len(options) <= 255:
        raise ValueError("choice requires 1..255 options")
    raw: list[float] = []
    for _key, desc in options:
        desc_kw = _keywords(f"{instructions} {desc}")
        ratio = _overlap_ratio(state_kw, desc_kw) if desc_kw else 0.0
        low_state = state.lower()
        hits = sum(1 for k in desc_kw if k in low_state)
        raw.append(ratio + min(0.5, hits * 0.15) + 0.05)
    # Softmax T=1.0
    m = max(raw)
    exps = [math.exp(r - m) for r in raw]
    total = sum(exps)
    probs = [e / total for e in exps]
    top = max(range(len(probs)), key=lambda i: probs[i])
    return {
        "type": "choice",
        "choice": options[top][0],
        "confidence": round(_clamp(probs[top]), 4),
        "probabilities": {k: round(p, 4) for (k, _), p in zip(options, probs)},
    }


def _score_score(state: str, instructions: str, criteria: Any) -> dict[str, Any]:
    if isinstance(criteria, dict):
        levels = list(criteria.values())
        n = len(levels)
    elif isinstance(criteria, list):
        levels = list(criteria)
        n = len(levels)
    else:
        raise ValueError("score criteria must be an object or array")
    if not 2 <= n <= 10:
        raise ValueError("score requires 2..10 levels")
    state_kw = _keywords(state)
    query_kw = _keywords(f"{instructions} {' '.join(str(v) for v in levels)}")
    ratio = _overlap_ratio(state_kw, query_kw)
    score = ratio * (n - 1)
    conf = _clamp(0.5 + 0.45 * ratio)
    return {
        "type": "score",
        "score": round(score, 4),
        "confidence": round(conf, 4),
        "levels": n,
    }


def evaluate_systemone(req: dict[str, Any]) -> dict[str, Any]:
    questions = req.get("questions")
    if not isinstance(questions, dict) or not questions:
        raise ValueError("questions must be a non-empty object")
    state = req.get("state", "")
    state_str = _state_text(state)
    model = str(req.get("model", "jev-local-lexical"))
    answers: dict[str, Any] = {}
    for qid, q in questions.items():
        if not isinstance(q, dict):
            raise ValueError(f"question {qid} must be an object")
        qtype = q.get("type")
        instructions = str(q.get("instructions", ""))
        criteria = q.get("criteria", {})
        if qtype == "noul":
            # noul criteria keys must be true/false only when present
            if isinstance(criteria, dict) and criteria:
                for k in criteria:
                    if k not in ("true", "false"):
                        raise ValueError("noul criteria keys must be true/false only")
            answers[qid] = _score_noul(state_str, instructions, criteria)
        elif qtype == "choice":
            answers[qid] = _score_choice(state_str, instructions, criteria)
        elif qtype == "score":
            answers[qid] = _score_score(state_str, instructions, criteria)
        else:
            raise ValueError(f"unsupported question type {qtype!r}")
    usage = {
        "input_tokens": max(1, len(state_str) // 4),
        "output_tokens": len(questions),
    }
    return {"model": model, "answers": answers, "usage": usage}


app = FastAPI(title="opencode-fast-search jev-local")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"ok": "true", "model": "jev-local-lexical"}


@app.get("/")
def root() -> dict[str, str]:
    return {"ok": "true", "model": "jev-local-lexical"}


@app.post("/v1/systemone")
def systemone(body: dict[str, Any]) -> JSONResponse:
    try:
        return JSONResponse(evaluate_systemone(body))
    except (ValueError, KeyError, TypeError) as e:
        return JSONResponse({"error": str(e)}, status_code=400)
