---
name: langchain-dependencies
description: Sets up LangChain, LangGraph, LangSmith, and Deep Agents package versions for Python and TypeScript projects. Use when installing dependencies, choosing between LangGraph and Deep Agents, pinning versions, or fixing import/package compatibility errors.
---

# LangChain Dependencies

## Principles

- **LangChain 1.0+** is the current LTS. Do not start new projects on 0.3.
- Always install **`langchain-core`** explicitly (peer dependency in TS/monorepos).
- **`langchain-community`** is not semver — pin to a minor series or prefer dedicated integration packages.
- Pick **one** orchestration layer: **LangGraph** (custom graphs) or **Deep Agents** (batteries-included).

## Environment

| Requirement | Python | TypeScript |
|-------------|--------|------------|
| Runtime | 3.10+ | Node 20+ |
| LangChain | 1.0+ | 1.0+ |
| LangSmith | >= 0.3.0 | >= 0.3.0 |

## Core packages

### Python — always

| Package | Role |
|---------|------|
| `langchain` | Agents, chains, retrieval |
| `langchain-core` | Base types |
| `langsmith` | Tracing, eval |

### Python — orchestration (pick one)

| Package | When |
|---------|------|
| `langgraph` | Custom graphs, loops, branching |
| `deepagents` | Planning, memory, skills out of the box |

### Python — providers (as needed)

`langchain-openai`, `langchain-anthropic`, `langchain-google-genai`, `langchain-mistralai`, `langchain-ollama`, etc.

### Python — common tools/RAG

| Package | Adds |
|---------|------|
| `langchain-tavily` | Tavily search |
| `langchain-text-splitters` | Chunking |
| `langchain-chroma` / `langchain-pinecone` / `langchain-qdrant` | Vector stores |
| `langchain-community` | Fallback integrations (pin conservatively) |

### TypeScript — always

`@langchain/core`, `langchain`, `langsmith`

### TypeScript — orchestration (pick one)

`@langchain/langgraph` or `deepagents`

## Minimal templates

### LangGraph (Python)

```text
langchain>=1.0,<2.0
langchain-core>=1.0,<2.0
langgraph>=1.0,<2.0
langsmith>=0.3.0
# + provider, e.g. langchain-openai
```

### LangGraph (TypeScript)

```json
{
  "dependencies": {
    "@langchain/core": "^1.0.0",
    "langchain": "^1.0.0",
    "@langchain/langgraph": "^1.0.0",
    "langsmith": "^0.3.0"
  }
}
```

### With RAG tools (Python)

```text
langchain>=1.0,<2.0
langchain-core>=1.0,<2.0
langgraph>=1.0,<2.0
langsmith>=0.3.0
langchain-tavily
langchain-chroma
langchain-text-splitters
```

## Versioning policy

| Package | Strategy |
|---------|----------|
| `langchain`, `langchain-core`, `langgraph` | `>=1.0,<2.0` |
| `langsmith` | `>=0.3.0` |
| Dedicated integrations (`langchain-chroma`, `langchain-tavily`) | Latest minor |
| `langchain-community` | `>=0.4.0,<0.5.0` (pin minor) |

Prefer dedicated packages over `langchain-community` imports.

## Environment variables

```bash
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=...          # optional

OPENAI_API_KEY=...             # or other provider keys
TAVILY_API_KEY=...             # if using Tavily
PINECONE_API_KEY=...           # if using Pinecone
```

## Common mistakes

**Legacy LangChain 0.3**

```text
# Wrong
langchain>=0.3,<0.4
# Correct
langchain>=1.0,<2.0
```

**Unpinned community**

```text
# Wrong
langchain-community>=0.4
# Correct
langchain-community>=0.4.0,<0.5.0
```

**Deprecated community imports**

```python
# Wrong
from langchain_community.vectorstores import Chroma
from langchain_community.tools.tavily_search import TavilySearchResults

# Correct
from langchain_chroma import Chroma
from langchain_tavily import TavilySearch
```

**Missing `@langchain/core` in TS monorepos** — always list it explicitly in `package.json`.

**Python < 3.10** — not supported by LangChain 1.0.
