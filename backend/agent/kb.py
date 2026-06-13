"""In-memory KB index: whole-document embeddings over backend/data/kb/.

Docs are small and highly similar (many near-identical spec sheets), so we embed
each document whole rather than chunking - this keeps shelf life + allergens
together and avoids fragment retrieval (see AGENTS.md). Built once at startup.
"""

from __future__ import annotations

import threading

from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_core.vectorstores import InMemoryVectorStore

from kb_index import KbDocument, load_kb_docs

from .llm import get_embeddings
from .sources import record_source

_lock = threading.Lock()
_store: InMemoryVectorStore | None = None
_docs_by_id: dict[str, KbDocument] = {}

# Lightweight query -> category hints to bias retrieval on this small corpus.
_CATEGORY_HINTS: dict[str, tuple[str, ...]] = {
    "product_specification": (
        "allergen", "shelf life", "ingredient", "nutrition", "spec", "gluten",
        "best before", "storage", "ean", "format",
    ),
    "commercial": ("price", "prices", "list price", "listino", "cost", "eur"),
    "policy": ("policy", "return", "complaint", "quality", "warranty", "refund"),
    "procedure": ("procedure", "process", "how do we", "steps", "workflow"),
}


def infer_category(query: str) -> str | None:
    q = query.lower()
    best: tuple[int, str | None] = (0, None)
    for category, hints in _CATEGORY_HINTS.items():
        score = sum(1 for h in hints if h in q)
        if score > best[0]:
            best = (score, category)
    return best[1]


def build_index() -> InMemoryVectorStore:
    """Embed every KB document into an in-memory vector store (idempotent)."""
    global _store
    with _lock:
        if _store is not None:
            return _store
        docs = load_kb_docs()
        _docs_by_id.clear()
        documents: list[Document] = []
        for doc in docs:
            _docs_by_id[doc.doc_id] = doc
            documents.append(
                Document(
                    page_content=doc.content,
                    metadata={
                        "doc_id": doc.doc_id,
                        "category": doc.category,
                        "title": doc.title,
                    },
                )
            )
        _store = InMemoryVectorStore.from_documents(documents, get_embeddings())
        return _store


def search_kb(query: str, k: int = 3, category: str | None = None) -> list[Document]:
    """Return the top-k whole documents for a query, optionally biased by category."""
    store = build_index()
    if category:
        results = store.similarity_search(
            query, k=k, filter=lambda d: d.metadata.get("category") == category
        )
        if results:
            return results
    return store.similarity_search(query, k=k)


def format_context(docs: list[Document]) -> str:
    blocks = []
    for d in docs:
        meta = d.metadata
        blocks.append(f"[{meta.get('doc_id')}] {meta.get('title')}\n{d.page_content}")
    return "\n\n---\n\n".join(blocks)


@tool
def kb_search(query: str) -> str:
    """Search the company knowledge base (product specs, allergens, shelf life,
    quality/returns policies, price list, customer requirements). Use for any
    policy/spec/price question, including the policy side of a complaint."""
    docs = search_kb(query, k=3, category=infer_category(query))
    if not docs:
        return "No matching knowledge base documents."
    for d in docs:
        record_source(d.metadata.get("doc_id", "kb"))
    return format_context(docs)
