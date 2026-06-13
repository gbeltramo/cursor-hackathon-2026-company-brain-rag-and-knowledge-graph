---
name: langgraph-fundamentals
description: Builds LangGraph StateGraph workflows with nodes, edges, reducers, Command routing, Send fan-out, streaming, and error handling. Use when writing any LangGraph code, designing agent graphs, or fixing state/routing bugs.
---

# LangGraph Fundamentals

Graphs = **StateGraph** + nodes + edges → **`compile()`** → `invoke()` / `stream()`.

## Design steps

1. Map workflow steps → nodes
2. Categorize each node (LLM, data, action, user input)
3. Design shared state schema
4. Implement nodes (return partial updates only)
5. Wire edges, add checkpointer if needed

## When to use LangGraph

| LangGraph | Alternative |
|-----------|-------------|
| Fine-grained orchestration, loops, branching | `create_agent()` for quick agents |
| HITL + persistence | Deep Agents for batteries-included |

## State + reducers

### Python

```python
from typing_extensions import TypedDict, Annotated
import operator

class State(TypedDict):
    name: str                                          # overwrites
    messages: Annotated[list, operator.add]            # appends
```

### TypeScript

```typescript
import { StateSchema, ReducedValue, MessagesValue } from "@langchain/langgraph";

const State = new StateSchema({
  name: z.string(),
  messages: MessagesValue,
  items: new ReducedValue(z.array(z.string()).default(() => []), {
    reducer: (curr, upd) => curr.concat(upd),
  }),
});
```

**Nodes return partial dicts** — never mutate and return full state.

## Basic graph

### Python

```python
from langgraph.graph import StateGraph, START, END

def process(state: State) -> dict:
    return {"output": f"Processed: {state['input']}"}

graph = (
    StateGraph(State)
    .add_node("process", process)
    .add_edge(START, "process")
    .add_edge("process", END)
    .compile()
)

result = graph.invoke({"input": "hello"})
```

## Edge types

| Need | API |
|------|-----|
| Fixed flow | `add_edge("a", "b")` |
| Branching | `add_conditional_edges("a", router, ["b", "c"])` |
| Update + route | `Command(update={...}, goto="b")` |
| Parallel fan-out | `Send("worker", {...})` from conditional edge |

## Conditional edges

```python
from typing import Literal

def route(state: State) -> Literal["weather", "general"]:
    return state["route"]

graph = (
    StateGraph(State)
    .add_node("classify", classify)
    .add_node("weather", weather_node)
    .add_node("general", general_node)
    .add_edge(START, "classify")
    .add_conditional_edges("classify", route, ["weather", "general"])
    .add_edge("weather", END)
    .add_edge("general", END)
    .compile()
)
```

## Command (update + route)

```python
from langgraph.types import Command
from typing import Literal

def node_a(state: State) -> Command[Literal["node_b", "node_c"]]:
    count = state["count"] + 1
    if count > 5:
        return Command(update={"count": count}, goto="node_c")
    return Command(update={"count": count}, goto="node_b")
```

**Warning:** static `add_edge` from `node_a` still runs alongside `Command(goto=...)`.

TypeScript: pass `{ ends: ["node_b", "node_c"] }` as third arg to `addNode`.

## Send (parallel workers)

Requires reducer on results field:

```python
from langgraph.types import Send

def orchestrator(state):
    return [Send("worker", {"task": t}) for t in state["tasks"]]

graph = (
    StateGraph(State)
    .add_node("worker", worker)
    .add_node("synthesize", synthesize)
    .add_conditional_edges(START, orchestrator, ["worker"])
    .add_edge("worker", "synthesize")
    .add_edge("synthesize", END)
    .compile()
)
```

## Invoke and stream

```python
result = graph.invoke({"input": "hello"}, {"configurable": {"thread_id": "1"}})

for chunk in graph.stream(input, stream_mode="messages"):
    token, metadata = chunk
    print(getattr(token, "content", ""), end="")
```

Stream modes: `values`, `updates`, `messages`, `custom`.

## Error handling

| Error | Strategy |
|-------|----------|
| Transient (network) | `RetryPolicy(max_attempts=3)` on node |
| Tool failure | `ToolNode(tools, handle_tool_errors=True)` |
| User-fixable | `interrupt()` — see langgraph-human-in-the-loop |
| Unexpected | Let bubble up |

## Common fixes

| Mistake | Fix |
|---------|-----|
| List field without reducer | `Annotated[list, operator.add]` |
| `builder.invoke()` | `builder.compile().invoke()` |
| Loop with no exit | Conditional edge returning `END` |
| Route to `START` | Use named entry node instead |
| `Command` + static edge | Both destinations may execute |
| TS forgot `await` | `await graph.invoke(...)` |

## Node signatures

| Args | When |
|------|------|
| `state` | Simple nodes |
| `state, config` | Need `thread_id` from config |
| `state, runtime` | Need store, context, stream writer |

## More examples

See [reference.md](reference.md) for full TypeScript graphs, streaming custom data, and retry/ToolNode patterns.
