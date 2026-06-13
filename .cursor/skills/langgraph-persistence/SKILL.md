---
name: langgraph-persistence
description: Configures LangGraph checkpointing, thread_id, time travel, Store for cross-thread memory, and subgraph checkpointer scoping. Use when persisting conversation state, replaying checkpoints, or sharing user data across threads.
---

# LangGraph Persistence

## Two memory types

| Type | Mechanism | Scope |
|------|-----------|-------|
| Short-term | Checkpointer | Per thread (conversation) |
| Long-term | Store | Cross-thread (user prefs, facts) |

## Checkpointer selection

| Checkpointer | Use |
|--------------|-----|
| `InMemorySaver` / `MemorySaver` | Dev, tests |
| `SqliteSaver` | Local dev |
| `PostgresSaver` | Production |

## Basic setup

### Python

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)

config = {"configurable": {"thread_id": "conversation-1"}}
result1 = graph.invoke({"messages": ["Hello"]}, config)
result2 = graph.invoke({"messages": ["How are you?"]}, config)
# result2 includes prior messages (with reducer on messages field)
```

### Production Postgres

```python
from langgraph.checkpoint.postgres import PostgresSaver

with PostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as checkpointer:
    checkpointer.setup()  # once, to create tables
    graph = builder.compile(checkpointer=checkpointer)
```

## Thread isolation

Different `thread_id` values = separate checkpoint sequences.

```python
alice = {"configurable": {"thread_id": "user-alice"}}
bob = {"configurable": {"thread_id": "user-bob"}}
graph.invoke({"messages": ["Hi"]}, alice)
graph.invoke({"messages": ["Hi"]}, bob)
```

## Time travel

```python
config = {"configurable": {"thread_id": "session-1"}}
graph.invoke({"messages": ["start"]}, config)

states = list(graph.get_state_history(config))
past = states[-2]

# Replay
graph.invoke(None, past.config)

# Fork — edit then resume
fork_config = graph.update_state(past.config, {"messages": ["edited"]})
graph.invoke(None, fork_config)
```

`update_state` passes through reducers. To replace a list: `{"items": Overwrite(["C"])})`.

## Subgraph checkpointer modes

| Mode | Interrupts | Multi-turn memory | Parallel same subgraph |
|------|------------|-------------------|------------------------|
| `checkpointer=False` | No | No | Yes |
| `None` (default) | Yes | No | Yes |
| `checkpointer=True` | Yes | Yes | **No** (namespace conflict) |

```python
subgraph = builder.compile()                    # interrupts, no cross-call memory
subgraph = builder.compile(checkpointer=False)  # no interrupts
subgraph = builder.compile(checkpointer=True)   # stateful across calls
```

For parallel **different** stateful subgraphs, give each a unique node name for namespace isolation.

## Long-term Store

```python
from langgraph.store.memory import InMemoryStore
from langgraph.runtime import Runtime

store = InMemoryStore()
store.put(("alice", "preferences"), "language", {"preference": "short"})

def respond(state, runtime: Runtime):
    prefs = runtime.store.get((state["user_id"], "preferences"), "language")
    return {"response": prefs.value}

graph = builder.compile(checkpointer=checkpointer, store=store)
```

Access store via **`runtime.store`** in nodes — not a global.

Store ops: `put`, `get`, `search`, `delete`.

## Common mistakes

| Wrong | Correct |
|-------|---------|
| No `thread_id` | Always pass `config={"configurable": {"thread_id": "..."}}` |
| `InMemorySaver` in production | `PostgresSaver` |
| `update_state` to replace list | Use `Overwrite([...])` |
| `store.put()` in node directly | `runtime.store.put(...)` |
| Same stateful subgraph in parallel | One instance per call or `checkpointer=False` |

## Related skills

- **langgraph-human-in-the-loop** — interrupts require checkpointer
- **langgraph-fundamentals** — state reducers and `Command`
