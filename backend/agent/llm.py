"""Shared LLM and embedding clients pointed at the Regolo (OpenAI-compatible) API.

Models are created lazily and cached so importing this module never requires
credentials at import time (handy for tests and the FastAPI startup path).
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from functools import lru_cache
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .logging_utils import get_logger

logger = get_logger("llm")


def _base_url() -> str:
    return os.environ.get("LLM_BASE_URL", "https://api.regolo.ai/v1")


def _api_key() -> str:
    # Empty string still lets the object build; the failure surfaces on the
    # first request, where the graph turns it into an honest 200 fallback.
    return os.environ.get("LLM_API_KEY", "")


def _embedding_api_key() -> str:
    """Credentials for the embedding endpoint (falls back to the chat key)."""
    return os.environ.get("EMBEDDING_API_KEY", "").strip() or _api_key().strip()


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    """Tool-calling chat model used by the router and the verticale agents."""
    return ChatOpenAI(
        model=os.environ.get("MODEL", "qwen3.5-9b"),
        base_url=_base_url(),
        api_key=_api_key(),
        temperature=0,
        timeout=25,
        max_retries=2,
    )


_LOCAL_EMBEDDING_DIM = 1024
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class LocalHashingEmbeddings(Embeddings):
    """Deterministic, dependency-free lexical embedding (the hashing trick).

    A credential-free fallback used when no embedding API key is configured so
    the KB still builds and answers. Tokens are hashed into a fixed-size,
    L2-normalized vector; cosine/L2 similarity then behaves like a lightweight
    BM25-style lexical match — fine for the small, near-identical KB corpus.
    """

    def __init__(self, dim: int = _LOCAL_EMBEDDING_DIM) -> None:
        self.dim = dim

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for token in _TOKEN_RE.findall(text.lower()):
            digest = hashlib.md5(token.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] & 1 else -1.0
            vec[bucket] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def embeddings_backend_id() -> str:
    """Stable identifier for the active embedding backend.

    Used to namespace the persisted index so a switch between the remote and
    local backends never loads a vector store with a mismatched dimension.
    """
    if _embedding_api_key():
        model = os.environ.get("EMBEDDING_MODEL", "Qwen3-Embedding-8B")
        return "remote-" + re.sub(r"[^a-zA-Z0-9]+", "_", model).strip("_").lower()
    return f"local-hash-{_LOCAL_EMBEDDING_DIM}"


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """Embedding model used to build the in-memory KB index.

    Uses the remote (Regolo/OpenAI-compatible) embeddings when an API key is
    available, otherwise falls back to a local credential-free embedding so the
    KB never blocks startup on missing credentials.
    """
    api_key = _embedding_api_key()
    if not api_key:
        logger.warning(
            "No embedding API key set (LLM_API_KEY/EMBEDDING_API_KEY); "
            "using local hashing embeddings for the KB."
        )
        return LocalHashingEmbeddings()

    return OpenAIEmbeddings(
        model=os.environ.get("EMBEDDING_MODEL", "Qwen3-Embedding-8B"),
        base_url=_base_url(),
        api_key=api_key,
        # KB docs are short; one batched call indexes the whole corpus.
        check_embedding_ctx_length=False,
    )


def message_text(message: BaseMessage | Any) -> str:
    """Extract the textual answer from a model response.

    Some reasoning models on Regolo leave ``content`` empty and put the answer
    in ``reasoning_content`` (see AGENTS.md). Handle both shapes.
    """
    content = getattr(message, "content", message)
    if isinstance(content, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ]
        content = "".join(parts)
    text = (content or "").strip() if isinstance(content, str) else str(content).strip()
    if text:
        return text

    extra = getattr(message, "additional_kwargs", {}) or {}
    reasoning = extra.get("reasoning_content") or extra.get("reasoning") or ""
    return reasoning.strip() if isinstance(reasoning, str) else ""
