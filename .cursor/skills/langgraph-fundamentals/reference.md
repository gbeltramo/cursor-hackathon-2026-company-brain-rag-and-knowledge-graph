# LangGraph Fundamentals — Reference

Extended examples referenced from SKILL.md.

## TypeScript basic graph

```typescript
import { StateGraph, StateSchema, START, END } from "@langchain/langgraph";
import { z } from "zod";

const State = new StateSchema({
  input: z.string(),
  output: z.string().default(""),
});

const processInput = async (state: typeof State.State) => ({
  output: `Processed: ${state.input}`,
});

const graph = new StateGraph(State)
  .addNode("process", processInput)
  .addEdge(START, "process")
  .addEdge("process", END)
  .compile();

const result = await graph.invoke({ input: "hello" });
```

## TypeScript Command node

```typescript
import { Command } from "@langchain/langgraph";

const nodeA = async (state: typeof State.State) => {
  const count = state.count + 1;
  return count > 5
    ? new Command({ update: { count }, goto: "node_c" })
    : new Command({ update: { count }, goto: "node_b" });
};

const graph = new StateGraph(State)
  .addNode("node_a", nodeA, { ends: ["node_b", "node_c"] })
  .addNode("node_b", async () => ({ result: "B" }))
  .addNode("node_c", async () => ({ result: "C" }))
  .addEdge(START, "node_a")
  .addEdge("node_b", END)
  .addEdge("node_c", END)
  .compile();
```

## TypeScript Send fan-out

```typescript
import { Send } from "@langchain/langgraph";

const orchestrator = (state: typeof State.State) =>
  state.tasks.map((task) => new Send("worker", { task }));

const graph = new StateGraph(State)
  .addNode("worker", worker)
  .addNode("synthesize", synthesize)
  .addConditionalEdges(START, orchestrator, ["worker"])
  .addEdge("worker", "synthesize")
  .addEdge("synthesize", END)
  .compile();
```

## Custom stream data

### Python

```python
from langgraph.config import get_stream_writer

def my_node(state):
    writer = get_stream_writer()
    writer("Processing...")
    return {"result": "done"}

for chunk in graph.stream({"data": "test"}, stream_mode="custom"):
    print(chunk)
```

### TypeScript

```typescript
import { getWriter } from "@langchain/langgraph";

const myNode = async (state) => {
  const writer = getWriter();
  writer("Processing...");
  return { result: "done" };
};
```

## RetryPolicy

### Python

```python
from langgraph.types import RetryPolicy

workflow.add_node(
    "search",
    search_fn,
    retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0),
)
```

### TypeScript

```typescript
workflow.addNode("search", searchFn, {
  retryPolicy: { maxAttempts: 3, initialInterval: 1.0 },
});
```

## ToolNode with error handling

### Python

```python
from langgraph.prebuilt import ToolNode
tool_node = ToolNode(tools, handle_tool_errors=True)
workflow.add_node("tools", tool_node)
```

### TypeScript

```typescript
import { ToolNode } from "@langchain/langgraph/prebuilt";
const toolNode = new ToolNode(tools, { handleToolErrors: true });
workflow.addNode("tools", toolNode);
```

## Node with config and runtime

### Python

```python
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime

def node_with_config(state, config: RunnableConfig):
    thread_id = config["configurable"]["thread_id"]
    return {"results": thread_id}

def node_with_runtime(state, runtime: Runtime):
    user_id = runtime.context.user_id
    return {"results": user_id}
```
