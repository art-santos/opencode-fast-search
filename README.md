# opencode-fast-search

Faster agentic exploration for OpenCode: instant AST symbol capsules and
sub-150ms typed local decisions, so agents stop burning turns on sequential
`grep`/`read` loops.

All heavy runtimes live in this repo. The consuming project imports a single
MCP entry — no Python dependencies leak into it.

## What it does

| Tool | What the agent gets | Latency |
| ---- | ------------------- | ------- |
| `jit_capsule(query, target_path, limit?)` | `@ref:file:start-end` symbol map (classes, interfaces, functions, consts with line numbers) for a file or directory | <50 ms, no model inference |
| `jev_decide(prompt, choices[])` | Typed `choice` verdict with confidence + probabilities over candidate options | sub-150 ms local HTTP, fail-open to in-process scorer |

Behind the tools:

- `src/jev_server/` — local Jev-compatible decision server: `POST /v1/systemone`
  with typed `noul` / `choice` / `score` questions. Deterministic scorer, no
  weights, no API key.
- `src/ast_engine/` — regex-based TypeScript symbol indexer + capsule compiler.
- `src/mcp_server.py` — unified stdio JSON-RPC MCP server exposing both tools,
  with a 500 ms circuit breaker (falls back to the local scorer, never crashes).
- `bin/service` — daemon lifecycle manager for the decision server.

## Requirements

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) (or plain `pip` + `venv`)
- OpenCode v2 (for the MCP wiring)

## Install

```bash
git clone https://github.com/art-santos/opencode-fast-search.git
cd opencode-fast-search
uv venv
uv pip install -e .
```

This installs `fastapi`, `uvicorn`, `pydantic`, `httpx`, and `pytest`.
No model weights are downloaded — the scorer is lexical and dependency-free.

Verify the install:

```bash
.venv/bin/pytest tests/
```

## Run

Start the local decision server (binds `127.0.0.1:8000`, localhost only):

```bash
./bin/service start
curl -sf http://127.0.0.1:8000/health
```

Other commands:

```bash
./bin/service status   # health probe
./bin/service log      # tail the server log
./bin/service stop     # stop the daemon
```

Try a decision directly:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/systemone \
  -H 'Content-Type: application/json' \
  -d '{"state":"The user wants to find where catalog deciders live.",
       "model":"jev-latest",
       "questions":{"relevance":{"type":"noul","instructions":"Is this about catalog items?"}}}'
```

Try a capsule without OpenCode:

```bash
.venv/bin/python3 -c "
import json, subprocess
p = subprocess.Popen(['.venv/bin/python3', 'src/mcp_server.py'],
                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
req = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call',
       'params': {'name': 'jit_capsule',
                  'arguments': {'query': 'CatalogSearcher',
                                'target_path': 'tests/fixtures'}}}
out, _ = p.communicate(input=json.dumps(req) + '\n', timeout=10)
print(json.loads(out)['result']['content'][0]['text'])
"
```

## Configure OpenCode

### 1. Register the MCP server

Add to your project's `opencode.json` (use the absolute path of this checkout):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context-optimizer": {
      "type": "local",
      "command": [
        "/path/to/opencode-fast-search/.venv/bin/python3",
        "/path/to/opencode-fast-search/src/mcp_server.py"
      ],
      "environment": { "JEV_BASE_URL": "http://127.0.0.1:8000" }
    }
  }
}
```

### 2. Steer agents toward it (recommended)

Agents default to built-in `read`/`grep`/`glob`. Add an exploration protocol
so they reach for these tools first — either in `AGENTS.md` or as the agent
`prompt` in `opencode.json`:

```markdown
### Exploration Protocol (mandatory)

- For any "find code about X" search, call `jit_capsule` (MCP server
  `context-optimizer`) FIRST with a natural-language query and target
  directory — it returns `@ref:file:start-end` symbol maps in <50ms.
- Read full files with `read` ONLY after a search tool returns targets, and
  only the files you intend to edit.
- Do NOT run sequential `grep`/`glob`/`read` loops to discover code locations.
- Use `jev_decide` (MCP server `context-optimizer`) to rank candidates when
  more than 3 exist.
- Fall back to `grep`/`glob` only when the search tools return no hits.
```

Optionally allowlist the tools for a specific agent:

```json
{
  "agent": {
    "builder": {
      "permission": { "laya_search": "allow", "jit_capsule": "allow", "jev_decide": "allow" }
    }
  }
}
```

### 3. Reload and verify

Reload the OpenCode session so it picks up the MCP server, then check:

```bash
opencode plugin list   # not needed for MCP, but confirms config loads
curl -sf http://127.0.0.1:8000/health
```

In a session, ask the agent to locate something (e.g. "where are the catalog
deciders?") and confirm its first move is a `jit_capsule` call rather than a
`grep` loop.

## Troubleshooting

| Symptom | Cause / fix |
| ------- | ----------- |
| `jit_capsule` returns "target not found" | `target_path` must be an absolute file or directory path |
| `jev_decide` appends `(local-fallback)` | `JEV_BASE_URL` unreachable or the daemon is stopped — run `./bin/service start`; results still work, just scored in-process |
| MCP server doesn't appear in OpenCode | Config paths must be absolute; reload the session after editing `opencode.json` |
| Port `8000` already in use | `lsof -ti:8000` then stop the stale process, or change `--port` in `bin/service` (and `JEV_BASE_URL` to match) |

## Layout

- `src/jev_server/app.py` — FastAPI app + pure `evaluate_systemone()` scorer
- `src/ast_engine/indexer.py` — TS symbol extraction
- `src/ast_engine/capsule.py` — capsule compiler (`build_capsule()`)
- `src/mcp_server.py` — stdio MCP server (`jit_capsule`, `jev_decide`)
- `bin/service` — daemon manager (`start|stop|status|log`)
- `tests/` — contract, capsule, and MCP protocol tests (+ `fixtures/sample.ts`)
