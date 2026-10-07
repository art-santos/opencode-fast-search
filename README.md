# Agent Exploration Optimizer

Standalone JIT-Context + local Jev decision engine for OpenCode.

All heavy runtimes live here. The monorepo imports only the MCP entry —
zero bloat.

## Layout

- `src/jev_server/` — local `POST /v1/systemone` decision server (noul/choice/score)
- `src/ast_engine/` — fast AST symbol capsule compiler (`@ref:path:start-end`)
- `src/mcp_server.py` — unified stdio MCP server (`jit_capsule`, `jev_decide`)
- `bin/service` — daemon lifecycle manager

## Quickstart

```bash
cd /home/dev-env/agent-exploration-optimizer
uv venv && uv pip install -e .
./bin/service start
curl -sf http://127.0.0.1:8000/health
```
