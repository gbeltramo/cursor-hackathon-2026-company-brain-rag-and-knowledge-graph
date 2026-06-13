"""Al Dente Company Brain - backend entry point.

Your job: implement the agent behind POST /ask. It orchestrates the Al Dente
mock APIs (CRM / ERP / call logs) and a knowledge base you build over data/kb/,
then answers with text or an artifact. Full spec and rules in AGENTS.md.

The /ask contract below is FROZEN - the automated evaluator depends on it.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv()

logger = logging.getLogger("company_brain")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Build the in-memory KB embedding index once at startup (35 small docs =
    # one batched embed call, well within the Railway healthcheck window).
    try:
        from agent.kb import build_index

        build_index()
        logger.info("KB index built")
    except Exception:  # never block startup / healthcheck on a provider hiccup
        logger.exception("KB index build failed; will build lazily on first use")
    yield


app = FastAPI(title="Al Dente Company Brain", lifespan=lifespan)

_STATIC = Path(__file__).resolve().parent / "static"
_FILES = _STATIC / "files"
_WEB = _STATIC / "web"
_FILES.mkdir(parents=True, exist_ok=True)

# Binary artifacts (docx / pptx / pdf / xlsx) you generate at request time go in
# static/files/ and are served from /files/<name> by this same backend.
# artifact_url must be ABSOLUTE: f"{os.environ['PUBLIC_BASE_URL']}/files/<name>"
app.mount("/files", StaticFiles(directory=_FILES), name="files")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)


class AskResponse(BaseModel):
    answer: str
    sources: list[str]
    verticale: str  # one of: "crm", "erp", "calls", "kb"
    artifact_url: str | None = None  # only for docx/pptx/pdf/xlsx questions


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    """Answer a question about Al Dente via the LangGraph agent.

    Always returns HTTP 200 (per the frozen contract): provider/tool failures
    are turned into an honest natural-language answer inside the graph.
    """
    from agent.graph import answer_question

    result = answer_question(request.question)
    return AskResponse(**result)


# Serve the Flutter web UI at the root. Mounted LAST so the API routes above
# (/ask, /health, /files) keep priority; this catch-all handles "/" and all the
# SPA assets (main.dart.js, assets/, canvaskit/, ...). Falls back to the
# placeholder page if the web build has not been copied into static/web.
if (_WEB / "index.html").exists():
    app.mount("/", StaticFiles(directory=_WEB, html=True), name="webapp")
else:

    @app.get("/", include_in_schema=False)
    def ui() -> FileResponse:
        return FileResponse(_STATIC / "index.html")
