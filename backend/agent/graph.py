"""LangGraph flow for POST /ask.

START -> input_guard -> route -> {api_agent | kb | artifact | refuse}
      -> output_guard -> END

The graph is compiled once and reused. Each ``/ask`` resets the per-request
source collector, invokes the graph synchronously, and maps the final state to
the frozen AskResponse schema.
"""

from __future__ import annotations

import operator
import time
from functools import lru_cache
from typing import Annotated, Literal

from langchain.agents import create_agent
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .api_tools import TOOLS_BY_VERTICALE
from .artifacts import build_artifact, detect_binary_format
from .guardrails import REFUSAL_MESSAGE, check_input, sanitize_output
from .kb import format_context, kb_search, search_kb
from .llm import get_chat_model, get_reasoning_model, message_text
from .logging_utils import get_logger, log_node, setup_logging
from .router import route_question
from .sources import get_sources, reset_sources

logger = get_logger("graph")


# A 3-hop chain (e.g. BOM -> supplier -> inventory) or a multi-aspect deck needs
# ~4-5 LLM turns; each turn + its tool round is 2 graph steps. Keep enough budget
# that real chains finish instead of dying mid-loop (the salvage path is a backstop).
_RECURSION_LIMIT = 14

_API_SYSTEM = """You are the Al Dente S.r.l. company-data assistant (pasta maker). \
Answer ONLY from tool results.

Rules:
- Verify premises first. If the question names a customer, order, SKU, supplier, \
or call, confirm it exists with a tool before answering. If it does not exist, \
say so explicitly (e.g. "There is no customer named X in the CRM"). Never invent.
- For counts, totals, or sums, call the relevant list tool with fetch_all=true \
and compute from the returned rows or the "total" field. Do not guess numbers.
- For "total ... grouped by channel/segment" questions, use crm_opportunities_by_channel \
(it joins opportunities to customers and sums per channel exactly). Do not group by hand.
- Some metrics are NOT stored anywhere: profit margin, cost, COGS, profitability, \
markup. If asked for such a figure, do NOT compute, estimate, or hunt across tools \
for it - state plainly that it is not available in the sources.
- To check if a specific item is below minimum stock, call erp_inventory with \
search=<sku> and compare on-hand vs minimum. State the conclusion explicitly using \
the words "below minimum" or "not below minimum".
- Filters are exact and case-sensitive (channel=GDO, status=active, type=support).
- Transcripts are long: use call_transcript with a focused search term only. A call \
id looks like CALL-#####, never CUST-####.
- Be concise and factual. If the data is not in any source, say it is not available."""

_KB_SYSTEM = """You answer questions about Al Dente S.r.l. using ONLY the provided \
knowledge base documents. If the answer is not contained in them, say it is not \
available in the documents. Be concise and precise; keep allergens, shelf life and \
prices exact. Do not invent figures."""

_HTML_SUFFIX = (
    "\n\nFirst gather every figure you need with tools (profile, deals, orders/lots, "
    "calls). Compute and explicitly include all key totals as concrete numbers - e.g. "
    "the count AND total value of open deals - do not leave aggregates implicit. Then "
    "produce the deliverable as a single self-contained block of inline HTML (semantic "
    "tags, minimal inline CSS) containing those real numbers. Return only the HTML."
)

_REPORT_SUFFIX = (
    "\n\nCompile the answer as a structured markdown report: use headings, bullet "
    "points, and markdown tables for any tabular data. Include all the real figures "
    "from the sources."
)


class State(TypedDict, total=False):
    question: str
    verticale: str
    intent: str
    artifact_format: str | None
    answer: str
    artifact_url: str | None
    sources: Annotated[list[str], operator.add]
    blocked: bool


@lru_cache(maxsize=8)
def _api_agent(verticale: str, reasoning: bool = False):
    tools = TOOLS_BY_VERTICALE[verticale] + [kb_search]
    model = get_reasoning_model() if reasoning else get_chat_model()
    return create_agent(model=model, tools=tools, system_prompt=_API_SYSTEM)


# --- Nodes --------------------------------------------------------------------


@log_node
def input_guard(state: State) -> dict:
    verdict = check_input(state["question"])
    if not verdict["allowed"]:
        return {"blocked": True, "answer": REFUSAL_MESSAGE, "verticale": "kb"}
    return {"blocked": False}


@log_node
def route(state: State) -> dict:
    decision = route_question(state["question"])
    fmt = detect_binary_format(state["question"]) if decision.intent == "artifact" else None
    return {
        "verticale": decision.verticale,
        "intent": decision.intent,
        "artifact_format": fmt,
    }


def _force_answer(messages: list, question: str, reasoning: bool) -> str:
    """Synthesize a final answer from the tool results gathered so far.

    Used when the agent loop is cut short (recursion limit) or ends without a
    textual answer. We flatten tool outputs into a plain prompt (avoiding orphaned
    tool_call/tool-message pairing errors) so the data already fetched is not
    wasted on a generic "couldn't find" fallback.
    """
    chunks: list[str] = []
    for m in messages:
        mtype = getattr(m, "type", "")
        if mtype == "tool":
            chunks.append(message_text(m)[:2000])
        elif mtype == "ai":
            t = message_text(m)
            if t:
                chunks.append(t)
    context = "\n\n".join(c for c in chunks if c)[:8000]
    if not context:
        return ""
    model = get_reasoning_model() if reasoning else get_chat_model()
    prompt = (
        f"Question: {question}\n\nTool results gathered so far:\n{context}\n\n"
        "Answer the question using ONLY these tool results. If the needed data is "
        "not present, say it is not available. Be concise and factual."
    )
    try:
        return message_text(
            model.invoke(
                [
                    {"role": "system", "content": _API_SYSTEM},
                    {"role": "user", "content": prompt},
                ]
            )
        )
    except Exception:
        return ""


def _gather_api(question: str, verticale: str, reasoning: bool = False) -> tuple[str, list[str]]:
    """Run the verticale tool-loop agent; capture tool sources in this context.

    Streams so that if the loop hits the recursion limit (or otherwise ends
    without a textual answer) we still have the intermediate messages and can
    salvage an answer from the data already fetched.
    """
    reset_sources()
    last_state: dict | None = None
    text = ""
    try:
        for chunk in _api_agent(verticale, reasoning).stream(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": _RECURSION_LIMIT},
            stream_mode="values",
        ):
            last_state = chunk
        if last_state and last_state.get("messages"):
            text = message_text(last_state["messages"][-1])
    except Exception:
        logger.warning("API agent loop interrupted (recursion/limit); salvaging.", exc_info=True)

    if not text and last_state and last_state.get("messages"):
        text = _force_answer(last_state["messages"], question, reasoning)
    return text, get_sources()


def _gather_kb(question: str, reasoning: bool = False) -> tuple[str, list[str]]:
    docs = search_kb(question)
    if not docs:
        return "", []
    user = f"Documents:\n\n{format_context(docs)}\n\nQuestion: {question}"
    model = get_reasoning_model() if reasoning else get_chat_model()
    try:
        response = model.invoke(
            [
                {"role": "system", "content": _KB_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        text = message_text(response)
    except Exception:
        text = ""
    return text, [d.metadata.get("doc_id", "kb") for d in docs]


@log_node
def api_agent_node(state: State) -> dict:
    question = state["question"]
    if state.get("intent") == "artifact":  # inline HTML deliverable
        question += _HTML_SUFFIX
    answer, sources = _gather_api(question, state["verticale"], reasoning=False)
    return {"answer": answer, "sources": sources}


@log_node
def kb_node(state: State) -> dict:
    question = state["question"]
    if state.get("intent") == "artifact":  # inline HTML deliverable
        question += _HTML_SUFFIX
    answer, sources = _gather_kb(question, reasoning=False)
    if not answer and not sources:
        return {
            "answer": "I couldn't find this in the company knowledge base documents.",
            "sources": [],
        }
    return {"answer": answer, "sources": sources}


def _artifact_title(question: str) -> str:
    words = (question or "").strip().split()
    title = " ".join(words[:10]) if words else "Al Dente Report"
    return title[:80]


@log_node
def artifact_node(state: State) -> dict:
    """Binary deliverable (docx/pptx/pdf/xlsx): gather the data as markdown, then
    render the file and return its absolute URL."""
    fmt = state.get("artifact_format") or "pdf"
    question = state["question"] + _REPORT_SUFFIX
    verticale = state.get("verticale", "kb")
    if verticale in ("crm", "erp", "calls"):
        content, sources = _gather_api(question, verticale)
    else:
        content, sources = _gather_kb(question)

    if not content.strip():
        return {"answer": _FALLBACK, "sources": sources}

    title = _artifact_title(state["question"])
    try:
        url = build_artifact(fmt, title, content)
    except Exception:
        # Couldn't render the file; still return the facts inline.
        return {"answer": content, "sources": sources}

    answer = (
        f"I've generated the {fmt.upper()} file with the requested Al Dente data: "
        f"{url}\n\n{content}"
    )
    return {"answer": answer, "artifact_url": url, "sources": sources}


@log_node
def refuse_node(state: State) -> dict:
    if state.get("answer"):
        return {}
    return {"answer": REFUSAL_MESSAGE}


@log_node
def output_guard(state: State) -> dict:
    return {"answer": sanitize_output(state.get("answer", ""))}


# --- Routing functions --------------------------------------------------------


def _after_input(state: State) -> Literal["route", "refuse"]:
    return "refuse" if state.get("blocked") else "route"


def _after_route(state: State) -> Literal["api_agent", "kb", "artifact", "refuse"]:
    if state.get("intent") == "not_available":
        return "refuse"
    if state.get("intent") == "artifact" and state.get("artifact_format"):
        return "artifact"
    if state.get("verticale") in ("crm", "erp", "calls"):
        return "api_agent"
    return "kb"


@lru_cache(maxsize=1)
def get_graph():
    builder = StateGraph(State)
    builder.add_node("input_guard", input_guard)
    builder.add_node("route", route)
    builder.add_node("api_agent", api_agent_node)
    builder.add_node("kb", kb_node)
    builder.add_node("artifact", artifact_node)
    builder.add_node("refuse", refuse_node)
    builder.add_node("output_guard", output_guard)

    builder.add_edge(START, "input_guard")
    builder.add_conditional_edges("input_guard", _after_input, ["route", "refuse"])
    builder.add_conditional_edges("route", _after_route, ["api_agent", "kb", "artifact", "refuse"])
    builder.add_edge("api_agent", "output_guard")
    builder.add_edge("kb", "output_guard")
    builder.add_edge("artifact", "output_guard")
    builder.add_edge("refuse", "output_guard")
    builder.add_edge("output_guard", END)
    return builder.compile()


_FALLBACK = "I cannot answer that right now. Please try again in a moment."
_cache: dict[str, dict] = {}


def answer_question(question: str) -> dict:
    setup_logging()  # idempotent: ensures the debug file exists for non-FastAPI callers
    key = " ".join((question or "").lower().split())
    if key in _cache:
        logger.debug("Cache hit for: %r", key)
        return _cache[key]

    try:
        t0 = time.perf_counter()
        # Stream so you see each node as it runs
        state = {}
        for event in get_graph().stream({"question": question}, stream_mode="updates"):
            node = list(event.keys())[0]
            patch = event[node]
            logger.info("Node %-20s | %s", node, {k: str(v)[:120] for k, v in patch.items()})
            state.update(patch)

        elapsed = time.perf_counter() - t0
        logger.info("Graph finished in %.2fs | verticale=%s", elapsed, state.get("verticale"))

        result = {
            "answer": state.get("answer") or _FALLBACK,
            "sources": list(dict.fromkeys(state.get("sources") or [])),
            "verticale": state.get("verticale") or "kb",
            "artifact_url": state.get("artifact_url"),
        }
    except Exception:
        logger.exception("Graph raised for question: %r", question)
        result = {
            "answer": _FALLBACK,
            "sources": [],
            "verticale": "kb",
            "artifact_url": None,
        }

    _cache[key] = result
    return result
