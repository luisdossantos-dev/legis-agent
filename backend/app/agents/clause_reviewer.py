"""
LangGraph clause review pipeline.

Flow:
  [Clause text + type + context]
       ↓
  [analyze node] — LLM analyzes clause against:
       ├── Checklist (required elements, common issues)
       ├── Risk patterns (high-risk language)
       └── Legal references (French civil code)
       ↓
  [assess_risk node] — Determines overall risk level
       ↓
  [generate_report node] — Outputs structured report
       ↓
  [ClauseReviewResponse]
"""

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.core.langfuse import observe
from app.core.llm import llm_complete
from app.rag.clause_checklist import get_checklist_for

logger = logging.getLogger(__name__)

# ── Simplified prompt for DeepSeek compatibility ───────────────

_ANALYSIS_PROMPT = """Output ONLY JSON. Do not reason or explain.
{{"observed_elements":[],"issues":[],"missing_elements":[],"legal_references":[]}}

Clause type: {clause_type}
Required elements: {required_elements}
Common issues: {common_issues}
Risk patterns: {risk_patterns}
Legal references: {legal_references}"""

_RISK_PROMPT = """Output ONLY JSON: {{"risk_level":"green","reasoning":"","score":0}}
Clause: {clause_text}
Issues: {issues}
Missing: {missing_elements}"""

_REPORT_PROMPT = """Output ONLY JSON: {{"risk_level":"{risk}","summary":"","issues":[],"missing_elements":[],"recommendations":[]}}
Clause: {clause_excerpt}
Analysis: {analysis_json}
Risk: {risk_json}"""


# ── JSON extraction ────────────────────────────────────────────

def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first complete JSON object with arbitrary nesting depth."""
    stack = []
    for i, ch in enumerate(text):
        if ch == '{':
            stack.append(i)
        elif ch == '}':
            if stack:
                start = stack.pop()
                if not stack:
                    try:
                        return json.loads(text[start:i+1])
                    except json.JSONDecodeError:
                        return None
    return None


# ── State ──────────────────────────────────────────────────────


class ClauseReviewState(TypedDict):
    """State for the clause review graph."""
    clause_text: str
    clause_type: str
    context: str  # other clauses from same document
    checklist: Dict[str, Any]

    # Node outputs
    analysis: Optional[Dict[str, Any]]
    risk_assessment: Optional[Dict[str, Any]]
    report: Optional[Dict[str, Any]]


# ── Graph nodes ────────────────────────────────────────────────


async def analyze_node(state: ClauseReviewState) -> Dict[str, Any]:
    """
    Node 1: LLM analyzes the clause against the checklist,
    risk patterns, and legal references.
    """
    clause_text = state["clause_text"]
    clause_type = state["clause_type"]
    checklist = state["checklist"]

    required_elements = checklist.get("required_elements", [])
    common_issues = checklist.get("common_issues", [])
    risk_patterns = checklist.get("risk_patterns", [])
    legal_refs = checklist.get("legal_references", {})

    logger.info("🔍 Analyzing clause: type=%s, len=%d chars", clause_type, len(clause_text))

    issues_str = "\n".join(
        f"- [{i.get('severity', 'medium')}] {i.get('pattern', '?')}: {i.get('description', '')}"
        for i in common_issues
    ) if common_issues else "None specified"

    risk_str = "\n".join(
        f"- [{r.get('risk_level', 'yellow')}] {r.get('name', '?')}: {r.get('description', '')}"
        for r in risk_patterns
    ) if risk_patterns else "None specified"

    legal_str = "\n".join(
        f"- {k}: {v}" for k, v in legal_refs.items()
    ) if legal_refs else "No specific references"

    prompt = _ANALYSIS_PROMPT.format(
        clause_type=clause_type.replace("_", " ").title(),
        required_elements="\n".join(f"- {e}" for e in required_elements),
        common_issues=issues_str,
        risk_patterns=risk_str,
        legal_references=legal_str,
    )

    context_note = ""
    if state.get("context"):
        context_note = f"\n\nContext (other clauses from same document):\n{state['context'][:1000]}"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Clause to review:\n\n{clause_text}{context_note}"},
    ]

    response = await llm_complete(messages, max_tokens=4096, temperature=0.0)

    logger.info("LLM response received (len=%d): %s", len(response), repr(response[:200]))

    analysis = _extract_json(response)
    if analysis is None:
        logger.warning("Failed to parse analysis JSON, using fallback")
        # Check if response contains any recognizable data structure
        if 'observed_elements' not in response and ('issue' in response.lower() or 'missing' in response.lower()):
            # The LLM returned a single issue object or free text - extract what we can
            single_issue = _extract_json('{' + response.split('{', 1)[-1]) if '{' in response else None
            issues_fallback = []
            if single_issue and 'type' in single_issue:
                issues_fallback.append(single_issue)
            if not issues_fallback:
                issues_fallback.append({
                    "type": "ambiguity",
                    "severity": "yellow",
                    "description": "The LLM response could not be fully parsed. Manual review recommended.",
                    "suggested_fix": "Review the clause manually against the required elements.",
                })
            analysis = {
                "observed_elements": [],
                "issues": issues_fallback,
                "missing_elements": required_elements[:3],
                "legal_references": [],
            }
        else:
            analysis = {
                "observed_elements": [],
                "issues": [{
                    "type": "error",
                    "severity": "red",
                    "description": "Failed to parse LLM analysis response",
                    "suggested_fix": "Try rephrasing the clause or selecting a different clause type",
                }],
                "missing_elements": required_elements[:3],
                "legal_references": [],
            }

    logger.info(
        "   -> Analysis: %d issues, %d missing elements",
        len(analysis.get("issues", [])),
        len(analysis.get("missing_elements", [])),
    )

    return {"analysis": analysis}


async def assess_risk_node(state: ClauseReviewState) -> Dict[str, Any]:
    """
    Node 2: LLM determines overall risk level based on analysis.
    """
    try:
        analysis = state.get("analysis", {})
        if isinstance(analysis, str):
            logger.warning("analysis is a string, converting to dict: %s", analysis[:200])
            analysis = {}
        issues = analysis.get("issues", [])
        missing = analysis.get("missing_elements", [])

        # Quick heuristic: if any red issues, risk is at least yellow
        has_red = any(i.get("severity") == "red" for i in issues)
        has_yellow = any(i.get("severity") == "yellow" for i in issues)

        issues_str = "\n".join(
            f"- [{i.get('severity', '?')}] {i.get('description', '')[:200]}"
            for i in issues
        ) if issues else "None"

        missing_str = "\n".join(f"- {m}" for m in missing) if missing else "None"

        prompt = _RISK_PROMPT.format(
            clause_text=state["clause_text"][:500],
            issues=issues_str,
            missing_elements=missing_str,
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Assess the overall risk level."},
        ]

        response = await llm_complete(messages, max_tokens=2048, temperature=0.0)
        risk = _extract_json(response)
        if risk is None:
            if response.strip():
                # Try to extract just the risk level from text
                text_lower = response.lower()
                if '"red"' in response or 'risk_level.*red' in text_lower:
                    risk = {"risk_level": "red", "reasoning": "Extracted from LLM response", "score": 80}
                elif '"yellow"' in response or 'risk_level.*yellow' in text_lower:
                    risk = {"risk_level": "yellow", "reasoning": "Extracted from LLM response", "score": 50}
                else:
                    risk = {"risk_level": "green", "reasoning": "Extracted from LLM response", "score": 20}
            else:
                risk = {"risk_level": "yellow", "reasoning": "No LLM response", "score": 50}

        if risk is None:
            # Fallback heuristic
            if has_red:
                risk = {"risk_level": "red", "reasoning": "One or more high-severity issues detected", "score": 80}
            elif has_yellow or len(missing) > 2:
                risk = {"risk_level": "yellow", "reasoning": "Medium-severity issues or multiple missing elements", "score": 50}
            else:
                risk = {"risk_level": "green", "reasoning": "No significant issues found", "score": 20}

        logger.info(
            "   -> Risk level: %s (score=%s)",
            risk.get("risk_level", "?"),
            risk.get("score", "?"),
        )

        return {"risk_assessment": risk}
    except Exception as e:
        import traceback
        logger.error("❌ assess_risk_node error: %s\n%s", str(e), traceback.format_exc())
        return {"risk_assessment": {"risk_level": "yellow", "reasoning": f"Error: {str(e)[:200]}", "score": 50}}


async def generate_report_node(state: ClauseReviewState) -> Dict[str, Any]:
    """
    Node 3: Generate a structured final report.
    """
    try:
        clause_text = state["clause_text"]
        analysis = state.get("analysis", {})
        if isinstance(analysis, str):
            analysis = {}
        risk = state.get("risk_assessment", {})
        if isinstance(risk, str):
            risk = {}
        risk_level = risk.get("risk_level", "yellow")

        analysis_json = json.dumps(analysis, ensure_ascii=False)[:1000]
        risk_json = json.dumps(risk, ensure_ascii=False)

        prompt = _REPORT_PROMPT.format(
            risk=risk_level,
            clause_excerpt=clause_text[:300],
            analysis_json=analysis_json,
            risk_json=risk_json,
        )

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": "Generate the final review report."},
        ]

        response = await llm_complete(messages, max_tokens=2048, temperature=0.0)
        report = _extract_json(response)

        if report is None:
            # Build report from analysis + risk
            issues = analysis.get("issues", [])
            missing = analysis.get("missing_elements", [])

            recommendations = []
            for issue in issues:
                fix = issue.get("suggested_fix", "")
                if fix:
                    recommendations.append(fix)
            if missing:
                recommendations.append(f"Add missing required elements: {', '.join(missing[:3])}")

            report = {
                "risk_level": risk_level,
                "summary": risk.get("reasoning", "Review completed"),
                "issues": issues,
                "missing_elements": missing,
                "recommendations": recommendations[:5],
            }

        logger.info(
            "✅ Report generated: risk=%s, issues=%d, recommendations=%d",
            report.get("risk_level", "?"),
            len(report.get("issues", [])),
            len(report.get("recommendations", [])),
        )

        return {"report": report}
    except Exception as e:
        import traceback
        logger.error("❌ generate_report_node error: %s\n%s", str(e), traceback.format_exc())
        return {"report": {
            "risk_level": risk.get("risk_level", "yellow") if isinstance(risk, dict) else "yellow",
            "summary": f"Error generating report: {str(e)[:200]}",
            "issues": [],
            "missing_elements": [],
            "recommendations": [],
        }}


# ── Graph builder ──────────────────────────────────────────────


def create_clause_review_graph():
    """Create and compile the clause review graph."""
    workflow = StateGraph(ClauseReviewState)

    workflow.add_node("analyze", analyze_node)
    workflow.add_node("assess_risk", assess_risk_node)
    workflow.add_node("generate_report", generate_report_node)

    workflow.set_entry_point("analyze")
    workflow.add_edge("analyze", "assess_risk")
    workflow.add_edge("assess_risk", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow.compile()


# Compiled graph instance
clause_review_graph = create_clause_review_graph()


# ── Public API ──────────────────────────────────────────────────


@observe(capture_input=True, capture_output=True)
async def review_clause(
    clause_text: str,
    clause_type: str = "autre",
    context: str = "",
) -> Dict[str, Any]:
    """
    Run the full clause review pipeline: analyze → assess_risk → report.

    Args:
        clause_text: The clause text to review
        clause_type: Type of clause (prix, delai, condition_suspensive, etc.)
        context: Other clauses from the same document for cross-reference

    Returns:
        Dict with risk_level, summary, issues, missing_elements, recommendations
    """
    import time
    start_time = time.time()

    checklist = get_checklist_for(clause_type)

    initial_state: ClauseReviewState = {
        "clause_text": clause_text,
        "clause_type": clause_type if clause_type in _get_types() else "autre",
        "context": context,
        "checklist": checklist,
        "analysis": None,
        "risk_assessment": None,
        "report": None,
    }

    try:
        result = await clause_review_graph.ainvoke(initial_state)
        elapsed = (time.time() - start_time) * 1000

        report = result.get("report", {})
        report["processing_time_ms"] = round(elapsed, 1)
        report["clause_type"] = clause_type
        report["checklist_summary"] = {
            "required_count": len(checklist.get("required_elements", [])),
            "issue_templates_count": len(checklist.get("common_issues", [])),
            "risk_patterns_count": len(checklist.get("risk_patterns", [])),
        }

        logger.info("✅ Clause review completed in %.0fms: risk=%s", elapsed, report.get("risk_level", "?"))
        return report

    except Exception as e:
        logger.error("❌ Clause review error: %s", str(e))
        return {
            "risk_level": "red",
            "summary": f"Review pipeline error: {str(e)[:200]}",
            "issues": [{"type": "error", "severity": "red", "description": str(e)[:300], "suggested_fix": ""}],
            "missing_elements": [],
            "recommendations": ["Retry the review. If the error persists, check the backend logs."],
            "processing_time_ms": round((time.time() - start_time) * 1000, 1),
            "clause_type": clause_type,
        }


def _get_types() -> List[str]:
    """Get list of valid clause types."""
    from app.rag.clause_checklist import CLAUSE_TYPES
    return CLAUSE_TYPES
