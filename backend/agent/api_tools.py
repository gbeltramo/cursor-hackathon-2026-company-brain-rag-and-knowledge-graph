"""LangChain tools wrapping the read-only Al Dente mock APIs.

Design notes (see API.md / AGENTS.md):
- Every list endpoint is paginated (``limit`` max 200). List tools always
  surface ``pagination.total`` and accept ``fetch_all`` to page through the
  whole set so the model can count / aggregate correctly.
- Transcripts are long: ``call_transcript`` forces a ``search`` term and a
  small page so we never download hundreds of segments.
- Filters are exact-match and case-sensitive on the server.
- Tools record the endpoints they hit in a per-request context variable so the
  graph can populate ``sources`` without parsing message history.
"""

from __future__ import annotations

import ast
import json
import math
import operator as _op
import os
from functools import lru_cache
from typing import Any

import httpx
from langchain_core.tools import tool

from .logging_utils import get_logger
from .sources import record_source as _record_source

logger = get_logger("api_tools")

# Hard cap on rows pulled by fetch_all, to stay within the latency budget.
_MAX_ROWS = 1000
_PAGE_SIZE = 200  # server max


@lru_cache(maxsize=1)
def _client() -> httpx.Client:
    base = os.environ.get("MOCK_API_BASE_URL", "https://aldente.yellowtest.it")
    token = os.environ.get("MOCK_API_TOKEN", "")
    return httpx.Client(
        base_url=base,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v not in (None, "", False)}


def _get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Single GET. Records the source and returns parsed JSON or an error dict."""
    _record_source(path.lstrip("/"))
    try:
        resp = _client().get(path, params=_clean_params(params or {}))
    except httpx.HTTPError as exc:
        logger.warning("GET %s failed: %s", path, exc)
        return {"error": "request_failed", "detail": str(exc)}
    if resp.status_code == 404:
        return {"error": "not_found", "status": 404}
    if resp.status_code == 401:
        logger.error("GET %s -> 401 access_denied (check MOCK_API_TOKEN)", path)
        return {"error": "access_denied", "status": 401}
    if resp.status_code >= 400:
        logger.warning("GET %s -> %s", path, resp.status_code)
        return {
            "error": "bad_request",
            "status": resp.status_code,
            "detail": resp.text[:200],
        }
    try:
        return resp.json()
    except ValueError:
        return {"error": "invalid_json"}


def _fetch_all(path: str, params: dict[str, Any]) -> dict[str, Any]:
    """Page through a list endpoint until exhausted (capped at _MAX_ROWS)."""
    rows: list[Any] = []
    offset = 0
    total = 0
    while True:
        page = _get(path, {**params, "limit": _PAGE_SIZE, "offset": offset})
        if "error" in page:
            return page if not rows else {"data": rows, "total": total, "partial": True}
        data = page.get("data", [])
        rows.extend(data)
        total = page.get("pagination", {}).get("total", len(rows))
        offset += _PAGE_SIZE
        if offset >= total or not data or len(rows) >= _MAX_ROWS:
            break
    return {"data": rows, "total": total, "returned": len(rows)}


def _list(path: str, params: dict[str, Any], fetch_all: bool, limit: int) -> str:
    if fetch_all:
        return json.dumps(_fetch_all(path, params))
    page = _get(path, {**params, "limit": min(limit, _PAGE_SIZE)})
    if "error" in page:
        return json.dumps(page)

    data = page.get("data", [])
    total = page.get("pagination", {}).get("total", len(data))
    returned = len(data)

    result: dict[str, Any] = {"data": data, "total": total, "returned": returned}

    # Warn the model explicitly when it's only seeing a partial view
    if returned < total:
        result["warning"] = (
            f"Only {returned} of {total} records returned. "
            "Call again with fetch_all=true to aggregate correctly."
        )

    return json.dumps(result)


# --- Calculator ---------------------------------------------------------------

# Whitelisted binary/unary operators for the safe expression evaluator.
_BIN_OPS = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
}
_UNARY_OPS = {ast.UAdd: _op.pos, ast.USub: _op.neg}

# Whitelisted callables the model may use inside an expression.
_FUNCS = {
    "round": round,
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
}


def _safe_eval(node: ast.AST) -> Any:
    """Recursively evaluate a parsed expression using only whitelisted nodes."""
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"unsupported constant: {node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
        return _BIN_OPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
        return _UNARY_OPS[type(node.op)](_safe_eval(node.operand))
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_safe_eval(elt) for elt in node.elts]
    if isinstance(node, ast.Call):
        func = node.func
        if not isinstance(func, ast.Name) or func.id not in _FUNCS:
            raise ValueError("only round/abs/min/max/sum/sqrt are allowed")
        args = [_safe_eval(arg) for arg in node.args]
        return _FUNCS[func.id](*args)
    raise ValueError(f"unsupported expression element: {type(node).__name__}")


@tool
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression and return the exact numeric result.

    ALWAYS use this for arithmetic instead of computing in your head: product
    values (unit_price * quantity), order/invoice line totals, sums and counts
    over rows you fetched, percentages, discounts and margins, and unit
    conversions. Supports + - * / // % ** parentheses and the functions
    round, abs, min, max, sum, sqrt. Example: "12.5 * 480 + 3 * 99.9".
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
    except ZeroDivisionError:
        return json.dumps({"expression": expression, "error": "division_by_zero"})
    except Exception as exc:  # invalid / disallowed expression
        logger.warning("calculator rejected %r: %s", expression, exc)
        return json.dumps(
            {
                "expression": expression,
                "error": "invalid_expression",
                "detail": str(exc),
            }
        )
    return json.dumps({"expression": expression, "result": result})


# --- CRM ----------------------------------------------------------------------


@tool
def crm_customers(
    search: str = "",
    channel: str = "",
    status: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List CRM customers. Use to find customers or count them by segment.

    Filters (exact, case-sensitive): channel = GDO | distributor | horeca;
    status = active | inactive | prospect; search matches the name.
    Set fetch_all=true to retrieve every matching customer for counting/aggregation.
    """
    return _list(
        "/crm/customers",
        {"search": search, "channel": channel, "status": status},
        fetch_all,
        limit,
    )


@tool
def crm_customer(customer_id: str) -> str:
    """Fetch one CRM customer by id (e.g. CUST-0132). Use to verify a customer
    exists before answering, or to read its full record."""
    return json.dumps(_get(f"/crm/customers/{customer_id}"))


@tool
def crm_opportunities(
    customer_id: str = "",
    stage: str = "",
    owner: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List sales opportunities. stage = qualification | negotiation | won | lost.
    Filter by customer_id or owner. fetch_all=true to count/aggregate the pipeline."""
    return _list(
        "/crm/opportunities",
        {"customer_id": customer_id, "stage": stage, "owner": owner},
        fetch_all,
        limit,
    )


@tool
def crm_opportunities_by_channel(stage: str = "") -> str:
    """Total opportunity value (value_eur) grouped by customer channel
    (GDO / distributor / horeca). Optionally filter by stage = qualification |
    negotiation | won | lost.

    Use this for ANY "total/sum of opportunities grouped by channel/segment"
    question. It pages through ALL opportunities and ALL customers, joins each
    opportunity to its customer's channel, and sums per channel in Python (exact).
    Returns per-channel totals, counts, and the grand total - do not group by hand.
    """
    opps = _fetch_all("/crm/opportunities", {"stage": stage})
    custs = _fetch_all("/crm/customers", {})
    if "error" in opps or "error" in custs:
        return json.dumps(
            {
                "error": "aggregation_failed",
                "opportunities": opps.get("error"),
                "customers": custs.get("error"),
            }
        )
    channel_by_cust = {
        c.get("id"): c.get("channel", "unknown") for c in custs.get("data", [])
    }
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for o in opps.get("data", []):
        channel = channel_by_cust.get(o.get("customer_id"), "unknown")
        totals[channel] = totals.get(channel, 0) + (o.get("value_eur") or 0)
        counts[channel] = counts.get(channel, 0) + 1
    return json.dumps(
        {
            "stage": stage or "all",
            "by_channel": {
                ch: {"total_value_eur": totals[ch], "count": counts[ch]} for ch in totals
            },
            "grand_total_eur": sum(totals.values()),
            "opportunities_considered": opps.get("total"),
        }
    )


@tool
def crm_orders(
    customer_id: str = "",
    status: str = "",
    date_from: str = "",
    date_to: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List orders. status = open | in_production | shipped | delivered | cancelled.
    date_from/date_to are ISO dates (YYYY-MM-DD). fetch_all=true to sum order values
    or count orders across all pages."""
    return _list(
        "/crm/orders",
        {
            "customer_id": customer_id,
            "status": status,
            "from": date_from,
            "to": date_to,
        },
        fetch_all,
        limit,
    )


@tool
def crm_invoices(
    customer_id: str = "",
    status: str = "",
    order_id: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List invoices. status = unpaid | paid | overdue. Filter by customer_id or
    order_id. fetch_all=true to total invoiced/overdue amounts across all pages."""
    return _list(
        "/crm/invoices",
        {"customer_id": customer_id, "status": status, "order_id": order_id},
        fetch_all,
        limit,
    )


# --- Calls --------------------------------------------------------------------


@tool
def calls_list(
    customer_id: str = "",
    call_type: str = "",
    outcome: str = "",
    date_from: str = "",
    date_to: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List call logs (metadata only). call_type = sales | support;
    outcome = complaint_open | follow_up | order_placed | resolved.
    Use to find relevant calls; then read details with call_transcript."""
    return _list(
        "/calls",
        {
            "customer_id": customer_id,
            "type": call_type,
            "outcome": outcome,
            "from": date_from,
            "to": date_to,
        },
        fetch_all,
        limit,
    )


@tool
def call_details(call_id: str) -> str:
    """Fetch metadata for one call (e.g. CALL-58213), including total_segments.
    Use before pulling transcript segments."""
    return json.dumps(_get(f"/calls/{call_id}"))


@tool
def call_transcript(call_id: str, search: str, speaker: str = "", limit: int = 20) -> str:
    """Extract relevant transcript segments for a call. ALWAYS pass a focused
    search term (a keyword/phrase from the question) - never download the full
    transcript. speaker optionally filters by who spoke. Returns matching segments."""
    _record_source(f"calls/{call_id}/transcript")
    params = _clean_params({"search": search, "speaker": speaker, "limit": min(limit, _PAGE_SIZE)})
    try:
        resp = _client().get(f"/calls/{call_id}/transcript", params=params)
        data = resp.json() if resp.status_code < 400 else {"error": resp.status_code}
    except httpx.HTTPError as exc:
        data = {"error": "request_failed", "detail": str(exc)}
    return json.dumps(data)


# --- ERP ----------------------------------------------------------------------


@tool
def erp_production_orders(
    customer_id: str = "",
    status: str = "",
    sku: str = "",
    date_from: str = "",
    date_to: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List production orders / lots. status = planned | in_progress | done | blocked.
    Filter by sku (finished good) or customer_id. fetch_all=true to count across pages."""
    return _list(
        "/erp/production-orders",
        {
            "customer_id": customer_id,
            "status": status,
            "sku": sku,
            "from": date_from,
            "to": date_to,
        },
        fetch_all,
        limit,
    )


@tool
def erp_inventory(
    inventory_type: str = "",
    below_min: bool = False,
    search: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List inventory items. inventory_type = finished_good | raw_material.
    below_min=true returns only items under their minimum stock. search matches name/SKU."""
    return _list(
        "/erp/inventory",
        {"type": inventory_type, "below_min": below_min, "search": search},
        fetch_all,
        limit,
    )


@tool
def erp_suppliers(
    search: str = "",
    category: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List suppliers. category = semolina | wheat | packaging | labels | ink | logistics.
    Use to find who supplies a raw material category."""
    return _list(
        "/erp/suppliers",
        {"search": search, "category": category},
        fetch_all,
        limit,
    )


@tool
def erp_bom(sku: str) -> str:
    """Get the bill of materials for a finished-good SKU (e.g. PAS-RIG-500):
    the raw materials and quantities that go into it. Use for lot/SKU -> material chains."""
    return json.dumps(_get("/erp/bom", {"sku": sku}))


@tool
def erp_shipments(
    customer_id: str = "",
    order_id: str = "",
    status: str = "",
    fetch_all: bool = False,
    limit: int = 50,
) -> str:
    """List shipments. status = in_transit | delivered | delayed. Filter by
    customer_id or order_id. fetch_all=true to count delayed/in-transit shipments."""
    return _list(
        "/erp/shipments",
        {"customer_id": customer_id, "order_id": order_id, "status": status},
        fetch_all,
        limit,
    )


CRM_TOOLS = [
    crm_customers,
    crm_customer,
    crm_opportunities,
    crm_opportunities_by_channel,
    crm_orders,
    crm_invoices,
]
CALLS_TOOLS = [calls_list, call_details, call_transcript, crm_customer]
ERP_TOOLS = [
    erp_production_orders,
    erp_inventory,
    erp_suppliers,
    erp_bom,
    erp_shipments,
]

# The calculator is source-agnostic: every API agent gets it so it can do exact
# arithmetic (totals, product values, margins) instead of guessing numbers.
TOOLS_BY_VERTICALE: dict[str, list] = {
    "crm": CRM_TOOLS + [calls_list, calculator],
    "calls": CALLS_TOOLS + [crm_customers, calculator],
    "erp": ERP_TOOLS + [crm_customers, crm_orders, calculator],
}

ALL_TOOLS = list({t.name: t for t in CRM_TOOLS + CALLS_TOOLS + ERP_TOOLS + [calculator]}.values())
