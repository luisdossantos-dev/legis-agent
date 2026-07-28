"""
Pydantic models for automatic case file assembly (expedientes).

A case file groups related notarial documents (deed + annexes +
correspondence + identity docs) into a structured bundle.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Document categories within a case file ─────────────────────


class DocCategory(str):
    """Document category within a case file."""
    PRINCIPAL = "principal"
    ANNEXE = "annexe"
    CORRESPONDANCE = "correspondance"
    IDENTITE = "identite"


CATEGORY_LABELS: Dict[str, str] = {
    "principal": "📜 Main Document",
    "annexe": "📎 Annex",
    "correspondance": "✉️ Correspondence",
    "identite": "🪪 Identity Document",
}

CATEGORY_ORDER = ["principal", "annexe", "correspondance", "identite"]


# ── Case document ──────────────────────────────────────────────


class CaseDocument(BaseModel):
    """A document within a case file."""
    id: str
    filename: str
    category: str = "annexe"  # principal, annexe, correspondance, identite
    doc_type: str = ""  # vente, pouvoir, contrat, etc.
    chunk_count: int = 0
    text_length: int = 0
    added_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    embedding: Optional[List[float]] = None
    summary: str = ""


# ── Case file ──────────────────────────────────────────────────


class CaseFile(BaseModel):
    """A case file grouping related notarial documents."""
    id: str
    name: str
    status: str = "open"  # open, closed, archived
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    document_count: int = 0
    documents: List[CaseDocument] = []
    centroid: Optional[List[float]] = None  # average embedding of all docs
    parties: List[str] = []
    property_ref: str = ""
    notes: str = ""
    confidence: float = 0.0  # clustering confidence


class CaseFileSummary(BaseModel):
    """Lightweight case file summary for listing."""
    id: str
    name: str
    status: str
    document_count: int
    created_at: str
    updated_at: str
    parties: List[str] = []
    property_ref: str = ""


class CaseListResponse(BaseModel):
    """Response for listing case files."""
    cases: List[CaseFileSummary]
    total: int = 0


# ── Process / Assign requests ──────────────────────────────────


class ProcessDocumentRequest(BaseModel):
    """Request to process a document into case files."""
    document_id: str
    filename: str = ""
    text: str
    chunks: List[str] = []
    embeddings: Optional[List[List[float]]] = None


class ProcessDocumentResponse(BaseModel):
    """Response after processing a document into the case system."""
    document_id: str
    assigned_to: Optional[str] = None  # case file ID
    action: str = ""  # "new_case" | "assigned_existing" | "clustered"
    case_name: str = ""
    confidence: float = 0.0
    similarity_scores: Dict[str, float] = {}


class AssignDocumentRequest(BaseModel):
    """Manually assign a document to a case file."""
    document_id: str
    case_id: str
    category: str = "annexe"


class RenameCaseRequest(BaseModel):
    """Rename a case file."""
    case_id: str
    name: str


class MergeCasesRequest(BaseModel):
    """Merge two case files into one."""
    target_case_id: str  # keep this one
    source_case_id: str  # merge into target


# ── Case stats ─────────────────────────────────────────────────


class CaseStats(BaseModel):
    """Statistics about the case file system."""
    total_cases: int = 0
    total_documents: int = 0
    open_cases: int = 0
    closed_cases: int = 0
    avg_docs_per_case: float = 0.0
    auto_assigned_count: int = 0
    manually_created_count: int = 0
