"""
Template engine for notarial acts.

Flow:
1. Client sends flat field values + act_type
2. Engine validates against the Pydantic schema for that act_type
3. If validation fails → returns 422 with list of missing/invalid fields
4. If validation passes → hydrates the template with field values
5. Returns the rendered document

Field resolution supports nested paths like "vendeur.nom" which
map to the Pydantic model's nested structure.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.models.act_schemas import ACT_SCHEMA_REGISTRY, ACT_TYPE_LABELS
from app.rag.dynamic_templates import DYNAMIC_TEMPLATES

logger = logging.getLogger(__name__)


# ── Field resolution ──────────────────────────────────────────


def _resolve_field(data: Dict[str, Any], path: str) -> Optional[str]:
    """
    Resolve a nested field path like "vendeur.nom" from a dict.

    Args:
        data: The validated Pydantic model data (as dict)
        path: Dot-separated path like "vendeur.nom"

    Returns:
        String value or None if not found
    """
    parts = path.split(".")
    current = data
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            # For list fields like legataires, format as bullet list
            if part.isdigit():
                idx = int(part)
                current = current[idx] if idx < len(current) else None
            else:
                return None
        else:
            return None
        if current is None:
            return None
    return str(current)


def _format_list_field(items: List[Any]) -> str:
    """Format a list field as a numbered list for the template."""
    if not items:
        return "Néant (none)"
    lines = []
    for i, item in enumerate(items, 1):
        if isinstance(item, dict):
            # For list of objects (like legataires), format compactly
            lines.append(f"  {i}. {item.get('prenom', '')} {item.get('nom', '')} — {item.get('adresse', '')}")
        else:
            lines.append(f"  {i}. {item}")
    return "\n".join(lines)


def _hydrate_template(
    template_body: str,
    data: Dict[str, Any],
) -> str:
    """
    Replace all {placeholders} in the template with resolved values.

    Supports:
      - Simple: {date}, {objet}
      - Nested: {vendeur.nom}, {bien.adresse}
      - List: {legataires}, {biens}
      - Missing: replaced with "[MISSING FIELD]"
    """
    def _replace_match(match: re.Match) -> str:
        path = match.group(1).strip()

        # Handle list fields
        if path in data and isinstance(data[path], list):
            return _format_list_field(data[path])

        # Handle nested fields
        value = _resolve_field(data, path)
        if value is not None:
            return value

        logger.debug("Template field '%s' not found in data", path)
        return f"[{path}]"

    result = re.sub(r"\{([^}]+)\}", _replace_match, template_body)
    return result


# ── Validation ────────────────────────────────────────────────


def validate_act_data(
    act_type: str,
    data: Dict[str, Any],
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate input data against the Pydantic schema for an act type.

    Args:
        act_type: Type of notarial act (vente, pouvoir, etc.)
        data: Flat or structured input data

    Returns:
        (is_valid, validated_data, error_message)
    """
    schema_cls = ACT_SCHEMA_REGISTRY.get(act_type)
    if schema_cls is None:
        return False, None, f"Unknown act type: '{act_type}'. Available: {', '.join(ACT_SCHEMA_REGISTRY.keys())}"

    try:
        validated = schema_cls(**data)
        return True, validated.model_dump(), None
    except ValidationError as e:
        errors = e.errors()
        error_details = []
        for err in errors:
            field_path = " → ".join(str(p) for p in err["loc"])
            error_details.append(f"  - {field_path}: {err['msg']} (type={err['type']})")
        error_msg = f"Validation failed for {act_type}:\n" + "\n".join(error_details)
        logger.warning("Template validation error: %s", error_msg)
        return False, None, error_msg


# ── Rendering ─────────────────────────────────────────────────


def render_template(
    act_type: str,
    data: Dict[str, Any],
    template_name: Optional[str] = None,
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
    """
    Validate input data against schema and render the template.

    Args:
        act_type: Type of notarial act
        data: Input data (will be validated against schema)
        template_name: Specific template name (uses first available if not specified)

    Returns:
        (success, result_dict, error_message)

    result_dict contains:
        - act_type: The act type
        - act_label: Human-readable label
        - template_name: Name of the template used
        - subject: Rendered subject line
        - body: Rendered document body
        - missing_fields: List of template fields not found in data
        - validated: bool
    """
    # Step 1: Validate against schema
    is_valid, validated_data, error_msg = validate_act_data(act_type, data)
    if not is_valid:
        return False, None, error_msg

    # Step 2: Find the template
    templates = DYNAMIC_TEMPLATES.get(act_type, DYNAMIC_TEMPLATES.get("general", []))
    if not templates:
        return False, None, f"No templates available for act type '{act_type}'."

    template = templates[0]
    if template_name:
        for t in templates:
            if t["name"] == template_name:
                template = t
                break
        else:
            logger.warning("Template '%s' not found for '%s', using default", template_name, act_type)

    # Step 3: Hydrate subject and body
    subject = _hydrate_template(template["subject"], validated_data)
    body = _hydrate_template(template["body"], validated_data)

    # Step 4: Check for missing required fields
    missing = []
    for field in template.get("required_fields", []):
        if _resolve_field(validated_data, field) is None:
            value = _resolve_field(data, field)
            if value is None:
                missing.append(field)

    result = {
        "act_type": act_type,
        "act_label": ACT_TYPE_LABELS.get(act_type, act_type),
        "template_name": template["name"],
        "template_description": template.get("description", ""),
        "language": template.get("language", "fr"),
        "subject": subject,
        "body": body,
        "missing_fields": missing,
        "validated": len(missing) == 0,
    }

    logger.info(
        "Template rendered: %s/%s (%d fields, %d missing)",
        act_type, template["name"], len(validated_data), len(missing),
    )

    return True, result, None
