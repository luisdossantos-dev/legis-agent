"""
Notarial act generation pipeline — LangGraph state machine.

5 nodes:
  1. RETRIEVE  — Find similar acts as reference
  2. STRUCTURE — LLM generates act structure (sections)
  3. DRAFT     — LLM drafts each section with formal legal tone
  4. VALIDATE  — Pydantic checks required fields
       ↓ error → back to DRAFT with feedback (max 3 cycles)
       ↓ OK → continue
  5. FORMAT    — Assemble final document
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.core.langfuse import observe
from app.core.llm import llm_complete
from app.models.act_generation import (
    ActDraft,
    GenerateActRequest,
    GenerationResult,
    GenerationSection,
    ValidationIssue,
    ValidationResult,
)
from app.models.act_schemas import ACT_SCHEMA_REGISTRY, ACT_TYPE_LABELS
from app.rag.docx_formatter import format_as_docx
from app.rag.retriever import vector_store

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 3


# ── Prompts ───────────────────────────────────────────────────

_STRUCTURE_PROMPT = """You are a notarial document expert. Given the act type and details below, generate the structure (sections) for a formal notarial act.

Act type: {act_type}
Details: {details}

Output a JSON array of sections:
[
  {{"title": "Article 1 — ...", "description": "What this section should contain"}},
  ...
]

Each act typically includes: preamble (parties), recitals, covenants/clauses, signatures.
Return ONLY the JSON array."""

_DRAFT_PROMPT = """You are a notarial lawyer drafting a formal legal document. Write section {section_index} of the act.

Act type: {act_type}
Section title: {section_title}
Section description: {section_description}
Context details: {details}

{feedback}

Write in formal French notarial style. Include proper legal phrasing.
Output ONLY the section content, no additional text."""

_VALIDATE_PROMPT = """You are a legal quality inspector. Review this act section for:

1. Missing required legal fields (dates, party names, amounts, property details)
2. Inconsistent or contradictory information
3. Improper formatting for a notarial act

Act type: {act_type}
Section: {section_title}
Content: {section_content}

Output JSON:
{{"valid": true/false, "issues": [{{"field": "...", "message": "...", "severity": "error"/"warning"}}], "score": 0.0-1.0}}"""


# ── Graph state ───────────────────────────────────────────────


class GenerationState(TypedDict):
    request: Dict[str, Any]  # Serialized GenerateActRequest
    similar_acts: List[str]
    structure: List[Dict[str, str]]
    draft: Dict[str, Any]    # Serialized ActDraft
    validation: Dict[str, Any]  # Serialized ValidationResult
    iterations: int
    output_path: Optional[str]
    error: Optional[str]


# ── Node 1: RETRIEVE ──────────────────────────────────────────


async def retrieve_node(state: GenerationState) -> Dict[str, Any]:
    """Find similar notarial acts in the vector store as reference."""
    req = state["request"]
    act_type = req.get("act_type", "general")
    details = json.dumps(req.get("parties", {}))[:500]

    query = f"{act_type} notarial act: {details}"
    logger.info("🔍 RETRIEVE: Searching for similar acts: %s", act_type)

    results = await vector_store.search(query=query, top_k=3)
    similar = [r["text"][:1000] for r in results]

    logger.info("   -> %d similar acts found", len(similar))
    return {"similar_acts": similar}


# ── Node 2: STRUCTURE ─────────────────────────────────────────


async def structure_node(state: GenerationState) -> Dict[str, Any]:
    """LLM generates the act structure (sections)."""
    req = state["request"]
    act_type = req.get("act_type", "general")
    details = {k: v for k, v in req.items() if v and k != "act_type"}

    prompt = _STRUCTURE_PROMPT.format(
        act_type=ACT_TYPE_LABELS.get(act_type, act_type),
        details=json.dumps(details, indent=2)[:2000],
    )

    logger.info("📐 STRUCTURE: Generating structure for %s", act_type)
    response = await llm_complete(
        [{"role": "user", "content": prompt}],
        max_tokens=2048,
        temperature=0.2,
    )

    structure = _parse_structure(response)
    if not structure:
        # Fallback: generate a basic structure
        structure = [
            {"title": "Préambule — Parties", "description": "Identification of the parties"},
            {"title": "Exposé", "description": "Background and recitals"},
            {"title": "Article 1 — Objet", "description": "Purpose of the act"},
            {"title": "Article 2 — Conditions", "description": "Terms and conditions"},
            {"title": "Article 3 — Dispositions finales", "description": "Final provisions and signatures"},
        ]

    logger.info("   -> %d sections generated", len(structure))
    return {"structure": structure}


def _parse_structure(response: str) -> List[Dict[str, str]]:
    """Parse the LLM structure response into a list of sections."""
    try:
        json_match = re.search(r"\[[\s\S]*\]", response)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)

        if isinstance(data, list):
            return [
                {"title": item.get("title", f"Section {i+1}"), "description": item.get("description", "")}
                for i, item in enumerate(data)
            ]
    except (json.JSONDecodeError, ValueError, AttributeError) as e:
        logger.debug("Structure parse failed: %s", e)

    return []


# ── Node 3: DRAFT ─────────────────────────────────────────────


async def draft_node(state: GenerationState) -> Dict[str, Any]:
    """LLM drafts each section with formal legal tone.
    Includes feedback from previous validation if rerunning."""
    req = state["request"]
    structure = state.get("structure", [])
    prev_feedback = state.get("validation", {}).get("issues", [])
    act_type = req.get("act_type", "general")
    details = {k: v for k, v in req.items() if v and k != "act_type"}

    feedback_text = ""
    if prev_feedback and state.get("iterations", 0) > 0:
        feedback_items = [f"- {i.get('field')}: {i.get('message')}" for i in prev_feedback[:5]]
        feedback_text = "Previous validation feedback to address:\n" + "\n".join(feedback_items)

    sections = []
    for i, sec in enumerate(structure):
        section_prompt = _DRAFT_PROMPT.format(
            section_index=i + 1,
            act_type=ACT_TYPE_LABELS.get(act_type, act_type),
            section_title=sec.get("title", f"Section {i+1}"),
            section_description=sec.get("description", ""),
            details=json.dumps(details, indent=2)[:1500],
            feedback=feedback_text,
        )

        logger.info("✍️  DRAFT: Section %d/%d: %s", i + 1, len(structure), sec.get("title", "")[:50])

        response = await llm_complete(
            [{"role": "user", "content": section_prompt}],
            max_tokens=2048,
            temperature=0.3,
        )

        sections.append(GenerationSection(
            title=sec.get("title", f"Section {i+1}"),
            content=response or "(Content to be drafted)",
        ))

    full_text = "\n\n".join(f"{s.title}\n{s.content}" for s in sections)

    draft = ActDraft(
        act_type=act_type,
        title=ACT_TYPE_LABELS.get(act_type, f"Acte {act_type}"),
        sections=sections,
        raw_text=full_text,
        model_used="primary",
    )

    iterations = state.get("iterations", 0) + 1
    logger.info("   -> %d sections drafted (%d chars, iteration %d)", len(sections), len(full_text), iterations)
    return {"draft": draft.model_dump(), "iterations": iterations}


# ── Node 4: VALIDATE ──────────────────────────────────────────


async def validate_node(state: GenerationState) -> Dict[str, Any]:
    """Validate the draft against required fields and legal standards."""
    draft_data = state.get("draft", {})
    sections = draft_data.get("sections", [])
    req = state["request"]
    act_type = req.get("act_type", "general")

    logger.info("🔍 VALIDATE: Checking %d sections for %s", len(sections), act_type)

    all_issues: List[Dict[str, Any]] = []

    # Check 1: Required fields from schema
    # Only check top-level structural fields, not nested model fields
    schema_cls = ACT_SCHEMA_REGISTRY.get(act_type)
    if schema_cls:
        for field_name, field in schema_cls.model_fields.items():
            if field.is_required() and field_name not in ("type_acte", "acte_date"):
                # Get French description for the field
                desc = (field.description or field_name).lower()
                field_mentioned = False
                for sec in sections:
                    content = (sec.get("title", "") + " " + sec.get("content", "")).lower()
                    # Check if the field name or its description appears
                    if field_name.lower().replace("_", " ") in content:
                        field_mentioned = True
                        break
                    # Check for key terms from the description
                    key_terms = desc.split()[:3]
                    if any(term in content for term in key_terms if len(term) > 4):
                        field_mentioned = True
                        break

                if not field_mentioned and field_name not in ("type_acte",):
                    all_issues.append({
                        "field": field_name,
                        "message": f"Required field '{field_name}' ({desc[:50]}) may be missing",
                        "severity": "warning",  # downgraded to warning for schema checking
                    })

    # Check 2: LLM-based validation for each section
    for i, sec in enumerate(sections[:3]):  # Validate first 3 sections
        val_prompt = _VALIDATE_PROMPT.format(
            act_type=ACT_TYPE_LABELS.get(act_type, act_type),
            section_title=sec.get("title", ""),
            section_content=sec.get("content", "")[:2000],
        )

        response = await llm_complete(
            [{"role": "user", "content": val_prompt}],
            max_tokens=1024,
            temperature=0.1,
        )

        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                val_data = json.loads(json_match.group())
                if not val_data.get("valid", True):
                    for issue in val_data.get("issues", []):
                        all_issues.append({
                            "field": issue.get("field", sec.get("title", f"Section {i+1}")),
                            "message": issue.get("message", "Validation issue"),
                            "severity": issue.get("severity", "error"),
                        })
        except (json.JSONDecodeError, ValueError):
            pass

    # Deduplicate
    seen = set()
    unique_issues = []
    for issue in all_issues:
        key = (issue["field"], issue["message"][:50])
        if key not in seen:
            seen.add(key)
            unique_issues.append(ValidationIssue(**issue))

    # Calculate score
    errors = sum(1 for i in unique_issues if i.severity == "error")
    warnings = sum(1 for i in unique_issues if i.severity == "warning")
    score = max(0.0, 1.0 - (errors * 0.3 + warnings * 0.1))

    result = ValidationResult(
        valid=errors == 0,
        issues=unique_issues,
        score=round(score, 2),
    )

    logger.info(
        "   -> Valid: %s, score: %.2f, issues: %d errors, %d warnings",
        result.valid, result.score, errors, warnings,
    )

    return {"validation": result.model_dump()}


def decide_rerun_or_format(state: GenerationState) -> Literal["draft", "format"]:
    """Decision: if validation fails and iterations remain → rerun draft."""
    validation = state.get("validation", {})
    iterations = state.get("iterations", 0)

    if not validation.get("valid", True) and iterations < MAX_ITERATIONS:
        logger.info("↩️  VALIDATION FAILED → rerun DRAFT (iteration %d/%d)", iterations + 1, MAX_ITERATIONS)
        return "draft"

    logger.info("✅ VALIDATION PASSED or max iterations → FORMAT")
    return "format"


# ── Node 5: FORMAT ────────────────────────────────────────────


async def format_node(state: GenerationState) -> Dict[str, Any]:
    """Assemble the final document (text + optional .docx)."""
    draft_data = state.get("draft", {})
    sections_data = draft_data.get("sections", [])
    req = state["request"]

    sections = [GenerationSection(**s) for s in sections_data]
    full_text = draft_data.get("raw_text", "")

    logger.info("📄 FORMAT: Assembling final document (%d chars)", len(full_text))

    # Generate .docx
    try:
        docx_path = format_as_docx(
            title=draft_data.get("title", "Notarial Act"),
            sections=sections,
            act_type=req.get("act_type", "general"),
        )
        logger.info("   -> DOCX saved: %s", docx_path)
    except Exception as e:
        logger.warning("DOCX generation failed: %s", e)
        docx_path = None

    return {"output_path": docx_path}


# ── Graph builder ─────────────────────────────────────────────


def create_act_generation_graph():
    """Create and compile the 5-node act generation graph."""
    workflow = StateGraph(GenerationState)

    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("structure", structure_node)
    workflow.add_node("draft", draft_node)
    workflow.add_node("validate", validate_node)
    workflow.add_node("format", format_node)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "structure")
    workflow.add_edge("structure", "draft")
    workflow.add_edge("draft", "validate")

    # Cyclic validation: validate → draft (with feedback) or format
    workflow.add_conditional_edges(
        "validate",
        decide_rerun_or_format,
        {
            "draft": "draft",
            "format": "format",
        },
    )

    workflow.add_edge("format", END)

    return workflow.compile()


# Compiled graph
act_gen_graph = create_act_generation_graph()


# ── Public API ─────────────────────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def generate_act(request: GenerateActRequest) -> GenerationResult:
    """Run the full act generation pipeline."""
    start = time.time()

    # Determine model based on sensitivity
    model_override = None

    initial_state: GenerationState = {
        "request": request.model_dump(),
        "similar_acts": [],
        "structure": [],
        "draft": {},
        "validation": {"valid": False, "issues": [], "score": 0.0},
        "iterations": 0,
        "output_path": None,
        "error": None,
    }

    try:
        result = await act_gen_graph.ainvoke(initial_state)
        elapsed = (time.time() - start) * 1000

        draft_data = result.get("draft", {})
        val_data = result.get("validation", {})
        iterations = result.get("iterations", 0)

        logger.info(
            "✅ Act generation completed in %.0fms (%d iterations)",
            elapsed, iterations + 1,
        )

        return GenerationResult(
            act_type=request.act_type,
            title=draft_data.get("title", ""),
            sections=[GenerationSection(**s) for s in draft_data.get("sections", [])],
            full_text=draft_data.get("raw_text", ""),
            docx_path=result.get("output_path"),
            iterations=iterations + 1,
            model_used=draft_data.get("model_used", ""),
            tokens_used=draft_data.get("tokens_used", 0),
            validation_score=val_data.get("score", 0.0),
            status="success",
        )

    except Exception as e:
        logger.error("❌ Act generation error: %s", str(e))
        return GenerationResult(
            act_type=request.act_type,
            status="error",
            error=str(e),
        )
