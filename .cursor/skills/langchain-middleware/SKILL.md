---
name: langchain-middleware
description: Configures LangChain agent middleware for human-in-the-loop approval, custom hooks, and structured output. Use when pausing for tool approval, resuming with Command, or intercepting tool/model calls.
---

# LangChain Middleware

Middleware hooks into the agent loop. **HITL requires checkpointer + thread_id.**

## Human-in-the-loop

### Python

```python
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from langchain_core.tools import tool

@tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email."""
    return f"Email sent to {to}"

agent = create_agent(
    model="gpt-4.1",
    tools=[send_email],
    checkpointer=MemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(
            interrupt_on={
                "send_email": {"allowed_decisions": ["approve", "edit", "reject"]},
                "read_email": False,
            }
        )
    ],
)

config = {"configurable": {"thread_id": "session-1"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "Email john@example.com"}]},
    config=config,
)

if "__interrupt__" in result:
    result = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),
        config=config,
    )
```

### TypeScript

```typescript
import { createAgent, humanInTheLoopMiddleware } from "langchain";
import { MemorySaver, Command } from "@langchain/langgraph";

const agent = createAgent({
  model: "anthropic:claude-sonnet-4-5",
  tools: [sendEmail],
  checkpointer: new MemorySaver(),
  middleware: [
    humanInTheLoopMiddleware({
      interruptOn: { send_email: { allowedDecisions: ["approve", "edit", "reject"] } },
    }),
  ],
});

const config = { configurable: { thread_id: "session-1" } };
const result = await agent.invoke(
  new Command({ resume: { decisions: [{ type: "approve" }] } }),
  config,
);
```

## Resume decisions

**Approve:** `{"type": "approve"}`

**Edit:** include `edited_action` / `editedAction` with `name` + `args`

**Reject:** include `feedback` explaining why

## Custom middleware hooks

| Hook | Signature | Use |
|------|-----------|-----|
| `wrap_tool_call` / `wrapToolCall` | `(request, handler)` | Retry, guard, log tools |
| `before_model` / `after_model` | `(state, runtime)` | Logging, validation |
| `before_agent` / `after_agent` | `(state, runtime)` | Setup/teardown |

### Python — wrap tool call

```python
from langchain.agents.middleware import wrap_tool_call

@wrap_tool_call
def retry_middleware(request, handler):
    for attempt in range(3):
        try:
            return handler(request)
        except Exception:
            if attempt == 2:
                raise
```

Do **not** use `yield` in `@wrap_tool_call` — it creates a generator and fails.

### TypeScript

```typescript
import { createMiddleware } from "langchain";

const retryMiddleware = createMiddleware({
  wrapToolCall: async (request, handler) => {
    for (let i = 0; i < 3; i++) {
      try { return await handler(request); }
      catch (e) { if (i === 2) throw e; }
    }
  },
});
```

## Common mistakes

| Wrong | Correct |
|-------|---------|
| HITL without checkpointer | `checkpointer=MemorySaver()` |
| `invoke(input)` without thread_id | `config={"configurable": {"thread_id": "..."}}` |
| `invoke({"resume": ...})` | `invoke(Command(resume={...}), config)` |

Interrupt happens **before** tool execution, not after.
