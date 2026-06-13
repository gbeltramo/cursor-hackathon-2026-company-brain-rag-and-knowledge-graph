"""Centralized logging for the company_brain agent package.

Every module gets a logger via ``get_logger("<module>")`` so names are uniform
under the ``company_brain`` hierarchy. ``setup_logging`` attaches a console
handler and a per-process file handler at ``logs/lang_graph_{timestamp}.log``
that captures the full LangGraph execution flow for debugging. The
``log_node`` decorator records each node call (inputs + truncated output patch)
so the debug file reads as a step-by-step trace of a request.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from functools import wraps
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

_ROOT_NAME = "company_brain"
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s | %(message)s"

# Guard so repeated calls (FastAPI startup + lazy callers) don't stack handlers.
_configured = False
_log_path: Path | None = None


def get_logger(module: str) -> logging.Logger:
    """Return the uniform ``company_brain.<module>`` logger."""
    return logging.getLogger(f"{_ROOT_NAME}.{module}")


def _log_dir() -> Path:
    return Path(os.environ.get("LANGGRAPH_LOG_DIR", "logs"))


def setup_logging(level: int = logging.INFO) -> Path:
    """Configure the ``company_brain`` logger once (idempotent).

    Attaches a console ``StreamHandler`` and a ``FileHandler`` writing to
    ``logs/lang_graph_{timestamp}.log``. Returns the active log file path.
    """
    global _configured, _log_path
    if _configured and _log_path is not None:
        return _log_path

    root = logging.getLogger(_ROOT_NAME)
    root.setLevel(level)
    root.propagate = False  # don't double-log through the python root logger

    formatter = logging.Formatter(_FORMAT)

    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = log_dir / f"lang_graph_{timestamp}.log"

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # Replace any prior handlers so reconfiguration stays clean.
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _configured = True
    _log_path = log_path
    root.info("Logging configured | debug log -> %s", log_path)
    return log_path


def get_log_path() -> Path | None:
    """Return the active LangGraph debug log path, if logging is configured."""
    return _log_path


def _truncate(value: Any, limit: int = 160) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def log_node(fn: Callable[..., dict]) -> Callable[..., dict]:
    node_logger = get_logger("graph")

    @wraps(fn)
    def wrapper(state: dict) -> dict:
        if not _configured:
            setup_logging()
        in_keys = sorted(state.keys()) if isinstance(state, dict) else state
        node_logger.info("→ node %-20s | in: %s", fn.__name__, in_keys)

        t0 = perf_counter()  # ← start
        patch = fn(state)
        elapsed = perf_counter() - t0  # ← stop

        rendered = (
            {k: _truncate(v) for k, v in patch.items()}
            if isinstance(patch, dict)
            else _truncate(patch)
        )
        node_logger.info(
            "← node %-20s | %.2fs | out: %s",  # ← %.2fs added
            fn.__name__,
            elapsed,
            rendered,
        )
        return patch

    return wrapper
