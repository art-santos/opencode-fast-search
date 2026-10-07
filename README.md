# opencode-fast-search

Standalone JIT-Context + local Jev decision engine for OpenCode.
Faster agentic exploration: instant AST symbol capsules and sub-150ms
typed decisions, with zero bloat in the consuming project.

All heavy runtimes live here. The consuming project imports only the MCP
entry — no dependencies leak into it.

## Layout

- `src/jev_server/` — local `POST /v1/systemone` decision server (noul/choice/score)
- `src/ast_engine/` — fast AST symbol capsule compiler (`@ref:path:start-end`)
- `src/mcp_server.py` — unified stdio MCP server (`jit_capsule`, `jev_decide`)
- `bin/service` — daemon lifecycle manager (`start|stop|status|log`)

## Quickstart

```bash
uv venv && uv pip install -e .
./bin/service start
curl -sf http://127.0.0.1:8000/health
```

## Wire into OpenCode

Add to your project's `opencode.json`:

```json
{
  "mcp": {
    "context-optimizer": {
      "type": "local",
      "command": ["<repo>/.venv/bin/python3", "<repo>/src/mcp_server.py"],
      "environment": { "JEV_BASE_URL": "http://127.0.0.1:8000" }
    }
  }
}
```
