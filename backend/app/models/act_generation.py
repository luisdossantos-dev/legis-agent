"""
Schemas for the notarial act generation pipeline.
Used by the 5-node LangGraph state machine.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class GenerationSection(BaseModel):
    """A single section of a notarial act."""
    title: str = Field(..., description="Section title (e.g. 'Article 1 — Designation du bien')")
    content: str = Field(..., description="Section body text")
    validated: bool = False
    feedback: Optional[str] = None


class ActDraft(BaseModel):
    """Full draft of a notarial act with metadata."""
    act_type: str = ""
    title: str = ""
    sections: List[GenerationSection] = []
    raw_text: str = ""
    model_used: str = ""
    tokens_used: int = 0


class ValidationIssue(BaseModel):
    """A single validation issue found in the draft."""
    field: str = Field(..., description="Field or section with the issue")
    message: str = Field(..., description="What's wrong")
    severity: str = "error"  # error | warning


class ValidationResult(BaseModel):
    """Result of validating an act draft."""
    valid: bool = False
    issues: List[ValidationIssue] = []
    score: float = 0.0  # 0.0 to 1.0


class GenerationResult(BaseModel):
    """Final result of the act generation pipeline."""
    act_type: str = ""
    title: str = ""
    sections: List[GenerationSection] = []
    full_text: str = ""
    docx_path: Optional[str] = None
    iterations: int = 0
    model_used: str = ""
    tokens_used: int = 0
    validation_score: float = 0.0
    status: str = ""  # success | validation_limit | error
    error: Optional[str] = None


class GenerateActRequest(BaseModel):
    """Request to generate a notarial act."""
    act_type: str = Field(..., description="Type of act (vente, pouvoir, testament, mariage, general)")
    parties: Dict[str, Any] = Field(default_factory=dict, description="Party information")
    property_info: Optional[Dict[str, Any]] = Field(default=None, description="Property details")
    amounts: Optional[Dict[str, Any]] = Field(default=None, description="Monetary amounts")
    dates: Optional[Dict[str, str]] = Field(default=None, description="Key dates")
    special_clauses: List[str] = Field(default_factory=list, description="Special clauses")
    language: str = Field(default="fr", description="Output language")
    sensitivity: str = Field(default="normal", description="normal | private")
    max_iterations: int = Field(default=3, ge=1, le=10, description="Max validation cycles")
