"""Shared LLM and embedding clients pointed at the Regolo (OpenAI-compatible) API.

Models are created lazily and cached so importing this module never requires
credentials at import time (handy for tests and the FastAPI startup path).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

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


@lru_cache(maxsize=1)
def get_embeddings() -> OpenAIEmbeddings:
    """Embedding model used to build the in-memory KB index."""
    return OpenAIEmbeddings(
        model=os.environ.get("EMBEDDING_MODEL", "Qwen3-Embedding-8B"),
        base_url=_base_url(),
        api_key=_api_key(),
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
