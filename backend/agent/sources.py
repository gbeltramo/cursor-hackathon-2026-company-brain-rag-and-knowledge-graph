"""Per-request collector of the sources used to answer a question.

Tools (API endpoints, KB lookups) append identifiers here; the graph reads and
resets it around each ``/ask`` invocation. A context variable keeps requests
isolated even if the app later serves them concurrently.
"""

from __future__ import annotations

import contextvars

_sources: contextvars.ContextVar[list[str]] = contextvars.ContextVar("request_sources")


def reset_sources() -> None:
    _sources.set([])


def record_source(identifier: str) -> None:
    try:
        bucket = _sources.get()
    except LookupError:
        bucket = []
        _sources.set(bucket)
    bucket.append(identifier)


def get_sources() -> list[str]:
    try:
        return list(dict.fromkeys(_sources.get()))  # dedupe, preserve order
    except LookupError:
        return []
