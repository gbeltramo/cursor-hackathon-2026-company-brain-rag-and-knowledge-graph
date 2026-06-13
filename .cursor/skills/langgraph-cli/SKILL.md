---
name: langgraph-cli
description: Scaffolds, develops, builds, and deploys LangGraph applications with the langgraph CLI and langgraph.json. Use when running langgraph dev/up/deploy, creating a new LangGraph project, or configuring graph entrypoints.
---

# LangGraph CLI

Manages the LangGraph app lifecycle: scaffold → dev → validate → deploy.

## Install

```bash
# Python — with dev server
pip install 'langgraph-cli[inmem]'
# or: uv add "langgraph-cli[inmem]"

# Python — build/deploy only
pip install langgraph-cli

# JavaScript
npx @langchain/langgraph-cli
# or: npm install -g @langchain/langgraph-cli  # CLI: langgraphjs
```

## Commands

| Command | Purpose |
|---------|---------|
| `langgraph new [PATH]` | Scaffold from template |
| `langgraph dev` | Local dev, hot reload, port 2024, no Docker |
| `langgraph build -t IMAGE` | Build Docker image |
| `langgraph up` | Docker Compose stack, port 8123, Postgres |
| `langgraph deploy` | Deploy to LangGraph Platform |
| `langgraph dockerfile PATH` | Generate Dockerfile |

### Scaffold

```bash
langgraph new
langgraph new ./my-agent --template agent-python
```

Templates: `agent-python`, `agent-js`, `deep-agent-python`, `deep-agent-js`, `new-langgraph-project-python`, `new-langgraph-project-js`

### Dev

```bash
langgraph dev
langgraph dev --port 8000 --no-browser
langgraph dev --tunnel          # remote access via Cloudflare
langgraph dev --debug-port 5678 # debugger (needs debugpy)
```

### Deploy

Requires Docker + `LANGSMITH_API_KEY`.

```bash
langgraph deploy --name my-agent
langgraph deploy list
langgraph deploy logs -f --name my-agent
langgraph deploy delete <id> --force
```

## langgraph.json

### Minimal (Python)

```json
{
  "dependencies": ["."],
  "graphs": {
    "agent": "./my_agent/agent.py:graph"
  },
  "env": "./.env"
}
```

### Key fields

| Key | Required | Description |
|-----|----------|-------------|
| `dependencies` | Yes | `["."]` or package paths/names |
| `graphs` | Yes | `"id": "./file.py:variable"` — must be `CompiledGraph` |
| `env` | No | `.env` path or inline env map |
| `python_version` | No | `"3.11"`, `"3.12"`, `"3.13"` |
| `dockerfile_lines` | No | Extra Dockerfile commands |

## Workflow

1. `langgraph new` — scaffold
2. Edit `langgraph.json` — point `graphs` at compiled graph(s)
3. `langgraph dev` — rapid iteration
4. `langgraph up --recreate` — production-like validation
5. `langgraph deploy` — ship to platform
6. `langgraph deploy logs -f` — monitor

## dev vs up

| | `langgraph dev` | `langgraph up` |
|--|-----------------|----------------|
| Docker | No | Yes |
| Persistence | In-memory / local pickle | PostgreSQL |
| Hot reload | Yes (default) | Optional (`--watch`) |
| Port | 2024 | 8123 |

## Gotchas

- `langgraph deploy` needs Docker; Apple Silicon also needs Buildx for `linux/amd64`.
- Deployments created in LangSmith UI cannot be updated via CLI deploy.
- `dependencies` must include `"."` (or subdir) where `pyproject.toml` / `requirements.txt` lives.
- `langgraph dev` runs in your local env — system deps (e.g. `ffmpeg`) must be installed locally.
- JS: use `npx @langchain/langgraph-cli <cmd>` or global `langgraphjs`.
