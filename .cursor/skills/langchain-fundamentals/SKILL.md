---
name: langchain-fundamentals
description: Builds LangChain agents with create_agent, @tool definitions, middleware, structured output, and persistence. Use when creating agents, defining tools, configuring models, or fixing agent loop issues.
---

# LangChain Fundamentals

Use **`create_agent()`** for all new LangChain agents. Legacy chain/agent constructors are outdated.

## Basic agent

### Python

```python
from langchain.agents import create_agent
from langchain_core.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get current weather for a location."""
    return f"Weather in {location}: Sunny, 72F"

agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
)

result = agent.invoke({
    "messages": [{"role": "user", "content": "What's the weather in Paris?"}]
})
print(result["messages"][-1].content)
```

### TypeScript

```typescript
import { createAgent } from "langchain";
import { tool } from "@langchain/core/tools";
import { z } from "zod";

const getWeather = tool(
  async ({ location }) => `Weather in ${location}: Sunny, 72F`,
  {
    name: "get_weather",
    description: "Get current weather for a location.",
    schema: z.object({ location: z.string() }),
  }
);

const agent = createAgent({
  model: "anthropic:claude-sonnet-4-5",
  tools: [getWeather],
  systemPrompt: "You are a helpful assistant.",
});

const result = await agent.invoke({
  messages: [{ role: "user", content: "What's the weather in Paris?" }],
});
```

## Agent options

| Parameter | Purpose |
|-----------|---------|
| `model` | Model string or instance |
| `tools` | Tool list |
| `system_prompt` / `systemPrompt` | Instructions |
| `checkpointer` | Conversation persistence |
| `middleware` | HITL, logging, retries |
| `response_format` | Structured output (Python) |

## Tools

Docstrings / descriptions must say **when** to use the tool, not just what it does.

### Python

```python
from langchain_core.tools import tool

@tool
def search(query: str) -> str:
    """Search the web for current information. Use for recent facts.

    Args:
        query: Search query (2-10 words)
    """
    return web_search(query)
```

### TypeScript

```typescript
const search = tool(async ({ query }) => webSearch(query), {
  name: "search",
  description: "Search the web for current information. Use for recent facts.",
  schema: z.object({ query: z.string() }),
});
```

## Persistence

Requires **checkpointer** + **thread_id**.

### Python

```python
from langgraph.checkpoint.memory import MemorySaver

agent = create_agent(
    model="anthropic:claude-sonnet-4-5",
    tools=[search],
    checkpointer=MemorySaver(),
)
config = {"configurable": {"thread_id": "user-123"}}
agent.invoke({"messages": [{"role": "user", "content": "I'm Bob"}]}, config=config)
```

## Structured output

### Python

```python
from pydantic import BaseModel

class ContactInfo(BaseModel):
    name: str
    email: str

agent = create_agent(model="gpt-4.1", tools=[search], response_format=ContactInfo)
result = agent.invoke({"messages": [{"role": "user", "content": "Find John"}]})
print(result["structured_response"])
```

Or model-level: `ChatOpenAI(...).with_structured_output(ContactInfo)`.

## Model configuration

Pass a model instance for custom settings:

```python
from langchain_anthropic import ChatAnthropic
agent = create_agent(
    model=ChatAnthropic(model="claude-sonnet-4-5", temperature=0),
    tools=[...],
)
```

## Middleware

See **langchain-middleware** skill for HITL and custom hooks.

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware, wrap_tool_call
```

## Common fixes

| Problem | Fix |
|---------|-----|
| Agent forgets between calls | Add `checkpointer` + `thread_id` |
| Infinite loop | `config={"recursion_limit": 10}` (Python) / `recursionLimit: 10` (TS) |
| `result.content` fails | Use `result["messages"][-1].content` (Python) / `result.messages.at(-1).content` (TS) |
| Vague tool use | Write specific tool descriptions with args |
