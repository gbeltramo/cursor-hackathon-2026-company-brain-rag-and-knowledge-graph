"""Deterministic guardrails - no LLM calls, near-zero latency.

Input guard: block prompt-injection / jailbreak attempts before routing.
Output guard: ensure a non-empty answer and redact obvious leaked PII.

Kept intentionally lightweight (pure regex) so it adds no model downloads or
latency on Railway. Structured so a transformer-based PII/toxicity check can be
slotted in later without touching the graph.
"""

from __future__ import annotations

import re

_JAILBREAK_PATTERNS = [
    r"ignore (all |previous |prior )?instructions",
    r"disregard (all |the )?(previous |prior )?(instructions|rules)",
    r"you are now (dan|an? ai with no restrictions)",
    r"pretend (you have no|there are no) (rules|restrictions|guidelines)",
    r"(bypass|override|disable) (your )?(safety|filters|restrictions|guardrails)",
    r"reveal (your |the )?(system )?prompt",
    r"do anything now",
    r"jailbreak",
]
_JAILBREAK_RE = re.compile("|".join(_JAILBREAK_PATTERNS), re.IGNORECASE)

# Only emails are redacted from output. Phone/numeric patterns are intentionally
# NOT redacted: company answers contain legitimate numeric facts (order ids,
# EANs, SKUs, totals) and over-redaction would corrupt scored answers.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

REFUSAL_MESSAGE = (
    "I can't help with that request. I can answer questions about Al Dente's "
    "customers, orders, production, suppliers, calls, and company documents."
)


def check_input(question: str) -> dict:
    """Return {'allowed': bool, 'reason': str|None} for an incoming question."""
    match = _JAILBREAK_RE.search(question or "")
    if match:
        return {"allowed": False, "reason": f"jailbreak_pattern:{match.group(0)!r}"}
    return {"allowed": True, "reason": None}


def sanitize_output(answer: str) -> str:
    """Redact obvious PII from a generated answer; never returns empty."""
    if not answer or not answer.strip():
        return (
            "I couldn't find a reliable answer in the available sources. "
            "Please rephrase or ask about a specific customer, order, or document."
        )
    return _EMAIL_RE.sub("[redacted-email]", answer)
