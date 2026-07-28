"""
Pydantic models for API request/response.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


# ── Documents ────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    pages: int
    chunks: int
    status: str = "indexed"
    created_at: datetime = Field(default_factory=_utcnow)


class DocumentSummary(BaseModel):
    id: str
    filename: str
    pages: int
    chunks: int
    status: str
    created_at: datetime


class DocumentListResponse(BaseModel):
    documents: List[DocumentSummary]
    total: int = 0


# ── Analysis ─────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    document_id: str
    query: str = "Analyze this legal document and extract its main components."


class ClauseInfo(BaseModel):
    title: str
    content: str
    risk_level: Optional[str] = None  # alto | medio | bajo


class AnalysisResult(BaseModel):
    document_id: str = ""
    document_type: Optional[str] = None
    parties: List[str] = []
    dates: List[str] = []
    amounts: List[Dict[str, Any]] = []
    clauses: List[ClauseInfo] = []
    risks: List[str] = []
    summary: str = ""


class AnalyzeResponse(BaseModel):
    analysis: AnalysisResult
    tokens_used: int = 0
    processing_time_ms: float = 0.0


# ── Chat ─────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = "user"  # user | assistant
    content: str
    references: List[str] = []  # fragmentos de documento citados


class ChatRequest(BaseModel):
    document_id: str
    messages: List[ChatMessage]
    query: str


class ChatResponse(BaseModel):
    response: str
    references: List[str] = []
    tokens_used: int = 0


# ── Internal agents ──────────────────────────────────────────

class AgentState(BaseModel):
    """Internal LangGraph agent state."""
    document_id: str
    query: str
    retrieved_chunks: List[str] = []
    analysis: Optional[AnalysisResult] = None
    draft: Optional[str] = None
    messages: List[ChatMessage] = []
    error: Optional[str] = None


# ── Email Drafting ────────────────────────────────────────────

class EmailTemplate(BaseModel):
    """Email template for notarial communications."""
    act_type: str = Field(description="Type of notarial act")
    name: str = Field(description="Template name")
    description: str = Field(description="Template description")
    language: str = Field(default="es", description="Language code")
    subject: str = Field(description="Subject line with {placeholders}")
    body_template: str = Field(description="Email body with {placeholders}")
    required_fields: List[str] = Field(default_factory=list)


class EmailDraftRequest(BaseModel):
    """Request to draft an email."""
    act_type: str = Field(description="Type of notarial act (escritura, poder, testamento, etc.)")
    fields: Dict[str, str] = Field(description="Field values to fill the template")
    sensitivity: str = Field(default="normal", description="normal | private")
    language: str = Field(default="es", description="Content language")
    urgent: bool = Field(default=False, description="Priority flag")
    custom_query: Optional[str] = Field(default=None, description="Custom instructions for the LLM")
    document_id: Optional[str] = Field(default=None, description="Optional document ID to extract context from")


class EmailDraftResponse(BaseModel):
    """Generated email draft."""
    to: str = ""
    subject: str
    body: str
    attachments: List[str] = []
    model_used: str = ""
    template_used: Optional[str] = None
    tokens_used: int = 0


# ── Email Classification ───────────────────────────────────────

EMAIL_CATEGORIES = [
    "cliente_nuevo",
    "seguimiento_escritura",
    "consulta_hipoteca",
    "notificacion_banco",
    "spam",
    "interno",
]


class EmailClassificationRequest(BaseModel):
    """Incoming email to classify."""
    from_address: str = ""
    to_address: str = ""
    subject: str = ""
    body: str
    attachments: List[str] = []


class EmailClassificationResponse(BaseModel):
    """Classification result for an incoming email."""
    email_id: str = ""
    category: str
    confidence: float = 0.0
    method: str = ""  # "embedding" | "llm"
    details: Optional[str] = None


# ── Email Action Detection ─────────────────────────────────────

class MarkAsReadParams(BaseModel):
    """Mark an email as read (no params needed)."""
    pass


class DraftReplyParams(BaseModel):
    """Draft a reply using a template."""
    template_id: str = Field(..., min_length=1, max_length=100)
    variables: Dict[str, str] = Field(default_factory=dict, max_length=20)
    priority: str = Field(default="normal", pattern=r"^(low|normal|high)$")


class CreateTaskParams(BaseModel):
    """Create a follow-up task."""
    assignee: str = Field(..., min_length=1, max_length=100)
    deadline: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    description: str = Field(..., min_length=1, max_length=500)


class ForwardToNotaryParams(BaseModel):
    """Forward email to a specific notary."""
    notary_email: str = Field(..., pattern=r"^[\w.+-]+@[\w-]+\.\w+$")
    reason: str = Field(..., max_length=500)
    include_attachments: bool = True


class ArchiveParams(BaseModel):
    """Archive an email to a folder."""
    folder: str = Field(..., pattern=r"^(inbox|done|pending|legal|personal)$")


# Union of all action params
ACTION_PARAM_MODELS = {
    "mark_as_read": MarkAsReadParams,
    "draft_reply": DraftReplyParams,
    "create_task": CreateTaskParams,
    "forward_to_notary": ForwardToNotaryParams,
    "archive": ArchiveParams,
}


class DetectedAction(BaseModel):
    """An action detected from an email."""
    action_name: str
    params: Dict[str, Any] = {}
    confidence: float = 0.0
    reasoning: str = ""


class ActionDetectionRequest(BaseModel):
    """Request to detect actions from a classified email."""
    email_id: str
    category: str = ""
    from_address: str = ""
    subject: str = ""
    body: str


class ActionExecutionResult(BaseModel):
    """Result of executing a detected action."""
    action_name: str
    status: str = ""  # success | validation_error | cost_guard | execution_error
    params: Dict[str, Any] = {}
    result: Optional[str] = None
    cost_estimated_usd: float = 0.0
    error: Optional[str] = None


class ActionDetectionResponse(BaseModel):
    """Full response with detected and executed actions."""
    email_id: str
    detected_actions: List[DetectedAction] = []
    execution_results: List[ActionExecutionResult] = []
    total_estimated_cost: float = 0.0


# ── Clause Review ────────────────────────────────────────────────

class ClauseReviewRequest(BaseModel):
    """Request to review a notarial clause."""
    clause_text: str = Field(..., min_length=1, max_length=10000)
    clause_type: str = Field(default="autre", description="prix, delai, condition_suspensive, renonciation, garantie, penalite, autre")
    context: str = Field(default="", description="Other clauses from the same document for cross-reference")


class ClauseReviewIssue(BaseModel):
    """An issue found during clause review."""
    type: str = Field(description="missing | risk | ambiguity | error")
    severity: str = Field(description="green | yellow | red")
    description: str = ""
    suggested_fix: str = ""


class ClauseReviewResponse(BaseModel):
    """Result of a clause review."""
    risk_level: str = Field(description="green | yellow | red")
    summary: str = ""
    issues: List[ClauseReviewIssue] = []
    missing_elements: List[str] = []
    recommendations: List[str] = []
    processing_time_ms: float = 0.0
    clause_type: str = ""
    checklist_summary: Optional[Dict[str, int]] = None
