"""
Dynamic template API endpoints.
POST /api/templates/render — Validate data and render a notarial act template.
GET  /api/templates — List available templates and their schemas.
GET  /api/templates/schema/{act_type} — Get the JSON schema for an act type.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.act_schemas import ACT_SCHEMA_REGISTRY, ACT_TYPE_LABELS
from app.rag.dynamic_templates import get_all_template_info
from app.rag.template_engine import render_template, validate_act_data

logger = logging.getLogger(__name__)

router = APIRouter()

class RenderRequest(BaseModel):
    act_type: str
    data: dict
    template_name: str | None = None


@router.post("/render")
async def render_document(req: RenderRequest):
    """
    Validate input data against the Pydantic schema for the act type
    and render the template. Returns 422 if validation fails with
    details about which fields are missing or invalid.

    Request body:
    {
        "act_type": "vente",
        "data": {
            "date": "2024-03-15",
            "notaire": "Jean Dupont",
            "vendeur": {
                "nom": "Martin",
                "prenom": "Pierre",
                "date_naissance": "1970-05-20",
                "adresse": "10 rue de Paris, 75001 Paris"
            },
            ...
        },
        "template_name": "acte_vente_standard" (optional)
    }
    """
    # Validate act type
    if req.act_type not in ACT_SCHEMA_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown act type '{req.act_type}'. Available: {', '.join(ACT_SCHEMA_REGISTRY.keys())}",
        )

    # Validate input is a dict
    if not isinstance(req.data, dict):
        raise HTTPException(status_code=400, detail="'data' must be a JSON object")

    # Validate and render
    success, result, error = render_template(req.act_type, req.data, req.template_name)

    if not success:
        raise HTTPException(status_code=422, detail=error)

    # If required fields are missing, return partial result with warnings
    if result.get("missing_fields"):
        result["warning"] = f"Missing fields: {', '.join(result['missing_fields'])}"

    return result


@router.get("/")
async def list_templates():
    """List all available templates with their schemas and field requirements."""
    templates = get_all_template_info()

    # Add schema info for each act type
    schemas = {}
    for act_type, schema_cls in ACT_SCHEMA_REGISTRY.items():
        schema_fields = {}
        for name, field in schema_cls.model_fields.items():
            schema_fields[name] = {
                "type": str(field.annotation) if hasattr(field, "annotation") else "unknown",
                "required": field.is_required(),
                "description": field.description or "",
            }
        schemas[act_type] = {
            "label": ACT_TYPE_LABELS.get(act_type, act_type),
            "fields": schema_fields,
        }

    return {
        "templates": templates,
        "schemas": schemas,
    }


@router.get("/schema/{act_type}")
async def get_schema(act_type: str):
    """Get the JSON schema for a specific act type."""
    if act_type not in ACT_SCHEMA_REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown act type '{act_type}'. Available: {', '.join(ACT_SCHEMA_REGISTRY.keys())}",
        )

    schema_cls = ACT_SCHEMA_REGISTRY[act_type]
    return {
        "act_type": act_type,
        "label": ACT_TYPE_LABELS.get(act_type, act_type),
        "schema": schema_cls.model_json_schema(),
    }
