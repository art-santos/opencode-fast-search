"""Unified stdio MCP server: jit_capsule + jev_decide.

Protocol: newline-delimited JSON-RPC 2.0 on stdin/stdout.
Methods: initialize, tools/list, tools/call. Fail-open (I6): Jev HTTP
timeout 500ms, fallback to local lexical scorer.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from src.ast_engine.capsule import build_capsule
from src.jev_server.app import evaluate_systemone

TOOLS = [
    {
        "name": "jit_capsule",
        "description": "Return instant AST symbol map (@ref) for a file or directory. No full file reads.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "target_path": {"type": "string"},
                "limit": {"type": "integer", "default": 12},
            },
            "required": ["query", "target_path"],
        },
    },
    {
        "name": "jev_decide",
        "description": "Sub-150ms typed choice decision between candidate options.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "choices": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["prompt", "choices"],
        },
    },
]


def _call_jit_capsule(args: dict[str, Any]) -> str:
    t0 = time.perf_counter()
    out = build_capsule(
        target_path=str(args["target_path"]),
        query=str(args.get("query", "")),
        limit=int(args.get("limit", 12)),
    )
    ms = (time.perf_counter() - t0) * 1000
    return f"{out}\n[capsule_ms={ms:.1f}]"


def _call_jev_decide(args: dict[str, Any]) -> str:
    prompt = str(args["prompt"])
    choices = [str(c) for c in args["choices"]]
    req = {
        "state": prompt,
        "model": "jev-local-lexical",
        "questions": {
            "q": {
                "type": "choice",
                "instructions": f"Which option best matches: {prompt}?",
                "criteria": {c: c for c in choices},
            }
        },
    }
    base = os.environ.get("JEV_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        import urllib.request

        data = json.dumps(req).encode()
        r = urllib.request.Request(
            base + "/v1/systemone",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        timeout_s = float(os.environ.get("JEV_TIMEOUT_S", "0.5"))
        with urllib.request.urlopen(r, timeout=timeout_s) as resp:
            body = json.load(resp)
        ans = body["answers"]["q"]
        probs = ans.get("probabilities", {})
        return f"choice={ans.get('choice')} confidence={ans.get('confidence')} probs={probs}"
    except Exception:
        # I6 fail-open: local scorer, zero crash
        ans = evaluate_systemone(req)["answers"]["q"]
        probs = ans.get("probabilities", {})
        return f"choice={ans.get('choice')} confidence={ans.get('confidence')} probs={probs} (local-fallback)"


def handle_request(req: dict[str, Any]) -> dict[str, Any]:
    rid = req.get("id")
    method = req.get("method")
    params = req.get("params", {}) or {}

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rid, "result": result}

    def err(code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}

    try:
        if method == "initialize":
            return ok(
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "context-optimizer", "version": "0.1.0"},
                }
            )
        if method == "tools/list":
            return ok({"tools": TOOLS})
        if method == "tools/call":
            name = params.get("name")
            args = params.get("arguments", {}) or {}
            if name == "jit_capsule":
                text = _call_jit_capsule(args)
            elif name == "jev_decide":
                text = _call_jev_decide(args)
            else:
                return err(-32602, f"unknown tool {name!r}")
            return ok({"content": [{"type": "text", "text": text}]})
        return err(-32601, f"unknown method {method!r}")
    except Exception as e:  # fail-open: never crash the stdio loop
        return err(-32603, f"internal error: {e}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}) + "\n")
            sys.stdout.flush()
            continue
        sys.stdout.write(json.dumps(handle_request(req)) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
