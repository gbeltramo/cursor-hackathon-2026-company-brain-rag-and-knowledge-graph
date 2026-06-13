"""LangGraph flow for POST /ask.

START -> input_guard -> route -> {api_agent | kb | artifact | refuse}
      -> output_guard -> END

The graph is compiled once and reused. Each ``/ask`` resets the per-request
source collector, invokes the graph synchronously, and maps the final state to
the frozen AskResponse schema.
"""

from __future__ import annotations

import operator
from functools import lru_cache
from typing import Annotated, Literal

from langchain.agents import create_agent
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .guardrails import REFUSAL_MESSAGE, check_input, sanitize_output
from .kb import format_context, infer_category, kb_search, search_kb
from .llm import get_chat_model, message_text
from .router import route_question
from .sources import get_sources, reset_sources
from .api_tools import TOOLS_BY_VERTICALE

_RECURSION_LIMIT = 8

_API_SYSTEM = """You are the Al Dente S.r.l. company-data assistant (pasta maker). \
Answer ONLY from tool results.

Rules:
- Verify premises first. If the question names a customer, order, SKU, supplier, \
or call, confirm it exists with a tool before answering. If it does not exist, \
say so explicitly (e.g. "There is no customer named X in the CRM"). Never invent.
- For counts, totals, or sums, call the relevant list tool with fetch_all=true \
and compute from the returned rows or the "total" field. Do not guess numbers.
- Filters are exact and case-sensitive (channel=GDO, status=active, type=support).
- Transcripts are long: use call_transcript with a focused search term only.
- Be concise and factual. If the data is not in any source, say it is not available."""

_KB_SYSTEM = """You answer questions about Al Dente S.r.l. using ONLY the provided \
knowledge base documents. If the answer is not contained in them, say it is not \
available in the documents. Be concise and precise; keep allergens, shelf life and \
prices exact. Do not invent figures."""

_ARTIFACT_SUFFIX = (
    "\n\nProduce the deliverable as a single self-contained block of inline HTML "
    "(use semantic tags and minimal inline CSS). Put real data from the sources in "
    "it. Return only the HTML."
)


class State(TypedDict, total=False):
    question: str
    verticale: str
    intent: str
    answer: str
    artifact_url: str | None
    sources: Annotated[list[str], operator.add]
    blocked: bool


@lru_cache(maxsize=4)
def _api_agent(verticale: str):
    tools = TOOLS_BY_VERTICALE[verticale] + [kb_search]
    return create_agent(model=get_chat_model(), tools=tools, system_prompt=_API_SYSTEM)


# --- Nodes --------------------------------------------------------------------


def input_guard(state: State) -> dict:
    verdict = check_input(state["question"])
    if not verdict["allowed"]:
        return {"blocked": True, "answer": REFUSAL_MESSAGE, "verticale": "kb"}
    return {"blocked": False}


def route(state: State) -> dict:
    decision = route_question(state["question"])
    return {"verticale": decision.verticale, "intent": decision.intent}


def api_agent_node(state: State) -> dict:
    # Reset + read within this single node call so tool sources are captured in
    # the same execution context (robust to LangGraph's threading model).
    reset_sources()
    question = state["question"]
    if state.get("intent") == "artifact":
        question += _ARTIFACT_SUFFIX
    try:
        result = _api_agent(state["verticale"]).invoke(
            {"messages": [{"role": "user", "content": question}]},
            config={"recursion_limit": _RECURSION_LIMIT},
        )
        answer = message_text(result["messages"][-1])
    except Exception:
        answer = ""
    return {"answer": answer, "sources": get_sources()}


def kb_node(state: State) -> dict:
    question = state["question"]
    docs = search_kb(question, k=3, category=infer_category(question))
    if not docs:
        return {
            "answer": "I couldn't find this in the company knowledge base documents.",
            "sources": [],
        }
    context = format_context(docs)
    system = _KB_SYSTEM
    user = f"Documents:\n\n{context}\n\nQuestion: {question}"
    if state.get("intent") == "artifact":
        user += _ARTIFACT_SUFFIX
    try:
        response = get_chat_model().invoke(
            [{"role": "system", "content": system}, {"role": "user", "content": user}]
        )
        answer = message_text(response)
    except Exception:
        answer = ""
    return {"answer": answer, "sources": [d.metadata.get("doc_id", "kb") for d in docs]}


def refuse_node(state: State) -> dict:
    if state.get("answer"):
        return {}
    return {"answer": REFUSAL_MESSAGE}


def output_guard(state: State) -> dict:
    return {"answer": sanitize_output(state.get("answer", ""))}


# --- Routing functions --------------------------------------------------------


def _after_input(state: State) -> Literal["route", "refuse"]:
    return "refuse" if state.get("blocked") else "route"


def _after_route(state: State) -> Literal["api_agent", "kb", "refuse"]:
    if state.get("intent") == "not_available":
        return "refuse"
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
    builder.add_node("refuse", refuse_node)
    builder.add_node("output_guard", output_guard)

    builder.add_edge(START, "input_guard")
    builder.add_conditional_edges("input_guard", _after_input, ["route", "refuse"])
    builder.add_conditional_edges("route", _after_route, ["api_agent", "kb", "refuse"])
    builder.add_edge("api_agent", "output_guard")
    builder.add_edge("kb", "output_guard")
    builder.add_edge("refuse", "output_guard")
    builder.add_edge("output_guard", END)
    return builder.compile()


_FALLBACK = "I cannot answer that right now. Please try again in a moment."
_cache: dict[str, dict] = {}


def answer_question(question: str) -> dict:
    """Run the graph for one question and return the AskResponse payload.

    Caches identical questions (the platform self-test repeats them) and never
    raises - any failure becomes an honest answer so /ask always returns 200.
    """
    key = " ".join((question or "").lower().split())
    if key in _cache:
        return _cache[key]

    try:
        final = get_graph().invoke({"question": question})
        result = {
            "answer": final.get("answer") or _FALLBACK,
            "sources": list(dict.fromkeys(final.get("sources") or [])),
            "verticale": final.get("verticale") or "kb",
            "artifact_url": final.get("artifact_url"),
        }
    except Exception:
        result = {
            "answer": _FALLBACK,
            "sources": [],
            "verticale": "kb",
            "artifact_url": None,
        }

    _cache[key] = result
    return result
