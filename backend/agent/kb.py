"""In-memory KB index: whole-document embeddings over backend/data/kb/.

Docs are small and highly similar (many near-identical spec sheets), so we embed
each document whole rather than chunking - this keeps shelf life + allergens
together and avoids fragment retrieval (see AGENTS.md).

Index strategy
--------------
Instead of rebuilding an InMemoryVectorStore on every cold start (slow embed
call), we persist a FAISS index to disk the *first* time and simply load it on
subsequent startups.  The index file lives at the path given by the env-var
``KB_INDEX_PATH`` (default: ``data/kb_index/``).

To force a full rebuild (e.g. after updating KB docs) delete the index
directory or set the env-var ``KB_FORCE_REBUILD=1``.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.tools import tool

from kb_index import KbDocument, load_kb_docs

from .llm import embeddings_backend_id, get_embeddings
from .logging_utils import get_logger
from .sources import record_source

logger = get_logger("kb")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_INDEX_PATH = Path("data/kb_index")
# Namespace the index by embedding backend so a vector store built with the
# remote embeddings is never loaded with the local fallback (or vice-versa),
# which would crash on a dimension mismatch.
_INDEX_DIR: Path = (
    Path(os.environ.get("KB_INDEX_PATH", _DEFAULT_INDEX_PATH)) / embeddings_backend_id()
)
_FORCE_REBUILD: bool = os.environ.get("KB_FORCE_REBUILD", "0").strip() == "1"

# ---------------------------------------------------------------------------
# Index build / load helpers
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_store: FAISS | None = None
_docs_by_id: dict[str, KbDocument] = {}


def _langchain_docs(kb_docs: list[KbDocument]) -> list[Document]:
    """Convert KbDocuments to LangChain Documents."""
    result: list[Document] = []
    for doc in kb_docs:
        result.append(
            Document(
                page_content=doc.content,
                metadata={
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                },
            )
        )
    return result


def _build_and_save(kb_docs: list[KbDocument]) -> FAISS:
    """Embed all documents and persist the FAISS index to *_INDEX_DIR*."""
    logger.info("Building FAISS KB index (%d docs) …", len(kb_docs))
    lc_docs = _langchain_docs(kb_docs)
    embeddings = get_embeddings()
    store = FAISS.from_documents(lc_docs, embeddings)
    _INDEX_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(_INDEX_DIR))
    logger.info("FAISS KB index saved to %s", _INDEX_DIR)
    return store


def _load_from_disk() -> FAISS:
    """Load a previously persisted FAISS index from *_INDEX_DIR*."""
    logger.info("Loading FAISS KB index from %s", _INDEX_DIR)
    embeddings = get_embeddings()
    return FAISS.load_local(
        str(_INDEX_DIR),
        embeddings,
        allow_dangerous_deserialization=True,  # safe: we wrote this file ourselves
    )


def _index_exists() -> bool:
    """Return True when a valid FAISS index directory is present on disk."""
    index_file = _INDEX_DIR / "index.faiss"
    pkl_file = _INDEX_DIR / "index.pkl"
    return index_file.is_file() and pkl_file.is_file()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_index() -> FAISS:
    """Return the FAISS store, loading from disk or building it as needed.

    Thread-safe and idempotent: subsequent calls return the cached store
    without hitting disk or the embedding API.
    """
    global _store
    with _lock:
        if _store is not None:
            return _store

        kb_docs = load_kb_docs()

        # Populate the doc-by-id lookup used by callers that need raw KbDocument.
        _docs_by_id.clear()
        for doc in kb_docs:
            _docs_by_id[doc.doc_id] = doc

        if _FORCE_REBUILD or not _index_exists():
            _store = _build_and_save(kb_docs)
        else:
            try:
                _store = _load_from_disk()
            except Exception:
                logger.exception("Failed to load FAISS index from disk; rebuilding …")
                _store = _build_and_save(kb_docs)

        logger.info("KB ready (%d documents indexed)", len(kb_docs))
        return _store


def search_kb(query: str, k: int = 5, fetch_k: int = 10) -> list[Document]:
    """Return the top-*k* whole documents for *query* by similarity score.

    Retrieves *fetch_k* candidates, re-ranks them by similarity score and keeps
    the best *k*.
    """
    store = build_index()
    candidates = store.similarity_search_with_score(query, k=fetch_k)
    # FAISS returns L2 distance (lower = more similar); re-rank ascending.
    candidates.sort(key=lambda pair: pair[1])
    return [doc for doc, _score in candidates[:k]]


def format_context(docs: list[Document]) -> str:
    """Render a list of retrieved documents into a single context string."""
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
    docs = search_kb(query, k=20, fetch_k=25)
    if not docs:
        return "No matching knowledge base documents."
    for d in docs:
        record_source(d.metadata.get("doc_id", "kb"))
    return format_context(docs)
