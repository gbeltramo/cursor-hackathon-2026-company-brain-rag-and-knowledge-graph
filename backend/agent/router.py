"""Question router: one Qwen call -> verticale + intent.

verticale in {crm, erp, calls, kb} is the dominant source for the answer.
intent in {answer, artifact, not_available}:
- answer        -> normal Q&A from the chosen source
- artifact      -> the question explicitly asks to *produce a document/deck/report*
- not_available -> the question is out of scope or asks for data no source holds
                   (the router only flags obvious cases; nodes still verify premises)
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .llm import get_chat_model
from .logging_utils import get_logger

logger = get_logger("router")

VERTICALI = {"crm", "erp", "calls", "kb"}
INTENTS = {"answer", "artifact", "not_available"}

_SYSTEM = """You route questions about Al Dente S.r.l. (a pasta maker) to the \
single best data source and intent. Reply with the classification only.

Sources (verticale):
- crm: customers, opportunities, orders, invoices, sales pipeline
- erp: production lots/orders, inventory, suppliers, bill of materials, shipments
- calls: phone call logs and transcripts (complaints, negotiations, support)
- kb: documents - product specs (allergens, shelf life, nutrition), quality and \
returns policies, the wholesale price list, customer/supplier requirements

intent:
- answer: a normal question
- artifact: the user explicitly asks you to PRODUCE a document, deck, slide, \
report, spreadsheet, PDF, or similar deliverable
- not_available: the question is clearly unrelated to Al Dente or to company data

For a complaint mentioned in a call whose answer is a policy, pick the dominant \
source. Pick exactly one verticale."""


class Route(BaseModel):
    verticale: str = Field(description="one of: crm, erp, calls, kb")
    intent: str = Field(description="one of: answer, artifact, not_available")


def route_question(question: str) -> Route:
    """Classify a question. Falls back to a safe default on any failure."""
    try:
        model = get_chat_model().with_structured_output(Route)
        result: Route = model.invoke(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": question},
            ]
        )
        verticale = result.verticale if result.verticale in VERTICALI else "kb"
        intent = result.intent if result.intent in INTENTS else "answer"
        logger.info("Routed verticale=%s intent=%s", verticale, intent)
        return Route(verticale=verticale, intent=intent)
    except Exception:
        # Degraded mode: default to KB answer; nodes still handle "not found".
        logger.exception("Routing failed; falling back to verticale=kb intent=answer")
        return Route(verticale="kb", intent="answer")
