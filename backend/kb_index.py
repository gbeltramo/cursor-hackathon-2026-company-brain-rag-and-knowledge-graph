"""Knowledge base document index over backend/data/kb/."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent / "data" / "kb"

CATEGORY_BY_ID: dict[str, str] = {
    # Product specifications (18)
    "DOC-001": "product_specification",
    "DOC-002": "product_specification",
    "DOC-003": "product_specification",
    "DOC-004": "product_specification",
    "DOC-005": "product_specification",
    "DOC-006": "product_specification",
    "DOC-007": "product_specification",
    "DOC-008": "product_specification",
    "DOC-009": "product_specification",
    "DOC-010": "product_specification",
    "DOC-018": "product_specification",
    "DOC-019": "product_specification",
    "DOC-020": "product_specification",
    "DOC-021": "product_specification",
    "DOC-022": "product_specification",
    "DOC-023": "product_specification",
    "DOC-024": "product_specification",
    "DOC-025": "product_specification",
    # Quality policies (4)
    "DOC-011": "policy",
    "DOC-012": "policy",
    "DOC-013": "policy",
    "DOC-026": "policy",
    # Procedures (6)
    "DOC-016": "procedure",
    "DOC-017": "procedure",
    "DOC-028": "procedure",
    "DOC-029": "procedure",
    "DOC-032": "procedure",
    "DOC-033": "procedure",
    # Other document types (7)
    "DOC-014": "customer_requirement",
    "DOC-015": "commercial",
    "DOC-027": "supplier_requirement",
    "DOC-030": "logistics",
    "DOC-031": "packaging_spec",
    "DOC-034": "sustainability",
    "DOC-035": "compliance",
}

_DOC_ID_RE = re.compile(r"\*\*Document ID:\*\*\s*(DOC-\d+)")
_DOC_TYPE_RE = re.compile(r"\*\*Document type:\*\*\s*(.+)")
_TITLE_RE = re.compile(r"^# (.+)$", re.MULTILINE)


@dataclass(frozen=True)
class KbDocument:
    doc_id: str
    title: str
    category: str
    document_type: str | None
    path: Path
    content: str


def parse_kb_doc(path: Path) -> KbDocument:
    text = path.read_text(encoding="utf-8")
    doc_id_match = _DOC_ID_RE.search(text)
    doc_id = doc_id_match.group(1) if doc_id_match else path.stem

    doc_type_match = _DOC_TYPE_RE.search(text)
    title_match = _TITLE_RE.search(text)

    return KbDocument(
        doc_id=doc_id,
        title=title_match.group(1) if title_match else doc_id,
        category=CATEGORY_BY_ID.get(doc_id, "unknown"),
        document_type=doc_type_match.group(1).strip() if doc_type_match else None,
        path=path,
        content=text,
    )


def load_kb_docs(kb_dir: Path = KB_DIR) -> list[KbDocument]:
    return [parse_kb_doc(path) for path in sorted(kb_dir.glob("DOC-*.md"))]
