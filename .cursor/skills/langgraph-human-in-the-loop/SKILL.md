---
name: langgraph-human-in-the-loop
description: Implements LangGraph human-in-the-loop with interrupt(), Command(resume=...), approval workflows, and idempotent side effects. Use when pausing graphs for user input, approval gates, or validation loops.
---

# LangGraph Human-in-the-Loop

## Requirements (all three)

1. **Checkpointer** at compile time
2. **`thread_id`** on every `invoke` / `stream`
3. **JSON-serializable** `interrupt()` payload

## Basic interrupt + resume

### Python

```python
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import StateGraph, START, END

def approval_node(state):
    approved = interrupt("Do you approve this action?")
    return {"approved": approved}

graph = (
    StateGraph(State)
    .add_node("approval", approval_node)
    .add_edge(START, "approval")
    .add_edge("approval", END)
    .compile(checkpointer=InMemorySaver())
)

config = {"configurable": {"thread_id": "thread-1"}}
result = graph.invoke({"approved": False}, config)
# result["__interrupt__"] → [Interrupt(value='Do you approve...')]

result = graph.invoke(Command(resume=True), config)
# result["approved"] → True
```

### TypeScript

```typescript
import { interrupt, Command, MemorySaver, StateGraph, START, END } from "@langchain/langgraph";

const approvalNode = async (state) => {
  const approved = interrupt("Do you approve this action?");
  return { approved };
};

const graph = new StateGraph(State)
  .addNode("approval", approvalNode)
  .addEdge(START, "approval")
  .addEdge("approval", END)
  .compile({ checkpointer: new MemorySaver() });

let result = await graph.invoke({ approved: false }, config);
result = await graph.invoke(new Command({ resume: true }), config);
```

**Critical:** on resume, the node **restarts from the beginning** — all code before `interrupt()` re-runs.

## Approval workflow with routing

```python
from langgraph.types import interrupt, Command
from typing import Literal

def human_review(state) -> Command[Literal["send_reply", "__end__"]]:
    decision = interrupt({
        "draft": state["draft_response"],
        "action": "Please review and approve/edit",
    })
    if decision.get("approved"):
        return Command(
            update={"draft_response": decision.get("edited_response", state["draft_response"])},
            goto="send_reply",
        )
    return Command(update={}, goto=END)
```

Put `interrupt()` **first** in the node when possible.

## Validation loop

```python
def get_age_node(state):
    prompt = "What is your age?"
    while True:
        answer = interrupt(prompt)
        if isinstance(answer, int) and answer > 0:
            break
        prompt = f"'{answer}' is not valid. Enter a positive number."
    return {"age": answer}
```

Each invalid answer needs a new `Command(resume=...)`.

## Multiple parallel interrupts

```python
result = graph.invoke({"vals": []}, config)
resume_map = {i.id: f"answer for {i.value}" for i in result["__interrupt__"]}
result = graph.invoke(Command(resume=resume_map), config)
```

## Idempotency rules

On resume, code **before** `interrupt()` re-runs (including parent nodes calling subgraphs).

| Do | Don't |
|----|-------|
| Upsert before interrupt | Insert/create before interrupt |
| Side effects after interrupt | Append to lists before interrupt |
| Separate side-effect nodes | Assume pre-interrupt code runs once |

```python
# Good
def node(state):
    approved = interrupt("Approve?")
    if approved:
        db.create_audit_log(...)  # runs once
    return {"approved": approved}

# Bad — duplicates on each resume
def node(state):
    db.create_audit_log(...)  # re-runs!
    approved = interrupt("Approve?")
    return {"approved": approved}
```

## Command rules

- **`Command(resume=...)`** — only valid input to resume from interrupt
- **Do not** pass `Command(update=...)` as invoke input — graph appears stuck
- **Do not** pass plain dict `{"resume": ...}` — use `Command(resume=...)`

## Common mistakes

| Wrong | Correct |
|-------|---------|
| `compile()` without checkpointer | `compile(checkpointer=InMemorySaver())` |
| Resume without same `thread_id` | Same config on every call |
| `invoke({"resume_data": ...})` | `invoke(Command(resume=...), config)` |

For tool-level HITL in LangChain agents, see **langchain-middleware** skill.

For the 4-tier error strategy (RetryPolicy, ToolNode), see **langgraph-fundamentals**.
