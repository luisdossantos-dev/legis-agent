"""
Email template library and semantic matching.

Stores a curated set of notarial/legal email templates and
uses the vector store to find the best match for a given
act type or case description.
"""

import logging
from typing import Any, Dict, List, Optional

from app.core.cache import ttl_cache
from app.models.schemas import EmailTemplate
from app.rag.retriever import vector_store

logger = logging.getLogger(__name__)

# ── Seed templates (English) ───────────────────────────────────
_SEED_TEMPLATES: List[Dict[str, Any]] = [
    {
        "act_type": "escritura",
        "name": "Deed of Sale — Notification",
        "description": "Notification of deed of sale preparation",
        "language": "en",
        "subject": "Deed of Sale — {folio} — {fecha}",
        "body_template": (
            "Dear {cliente_nombre},\n\n"
            "We are pleased to inform you that the deed of sale for the property located at "
            "{inmueble_direccion} is now being prepared.\n\n"
            "Transaction details:\n"
            "- File: {folio}\n"
            "- Scheduled date: {fecha}\n"
            "- Appearing parties: {comparecientes}\n"
            "- Amount: {monto}\n\n"
            "To coordinate the signing, please contact our legal department at {telefono_contacto}.\n\n"
            "Best regards,\n"
            "{firma_notario}\n"
            "{notaria_nombre}"
        ),
        "required_fields": [
            "cliente_nombre", "inmueble_direccion", "folio", "fecha",
            "comparecientes", "monto", "telefono_contacto", "firma_notario", "notaria_nombre"
        ],
    },
    {
        "act_type": "poder",
        "name": "Power of Attorney — Confirmation",
        "description": "Confirmation of power of attorney issuance",
        "language": "en",
        "subject": "Power of Attorney — {folio} — {poderdante}",
        "body_template": (
            "Dear {cliente_nombre},\n\n"
            "We confirm that the requested power of attorney has been executed with the following details:\n\n"
            "- File: {folio}\n"
            "- Grantor: {poderdante}\n"
            "- Attorney-in-fact: {apoderado}\n"
            "- Scope: {alcance_poder}\n"
            "- Date of execution: {fecha}\n\n"
            "You may pick up the certified copy at our office with your official ID.\n\n"
            "Best regards,\n"
            "{firma_notario}\n"
            "{notaria_nombre}"
        ),
        "required_fields": [
            "cliente_nombre", "folio", "poderdante", "apoderado",
            "alcance_poder", "fecha", "firma_notario", "notaria_nombre"
        ],
    },
    {
        "act_type": "testamento",
        "name": "Last Will — Signing Appointment",
        "description": "Appointment scheduling for will signing",
        "language": "en",
        "subject": "Last Will — Signing Appointment — {folio}",
        "body_template": (
            "Dear {cliente_nombre},\n\n"
            "Your last will and testament has been drafted according to your instructions "
            "and is ready for your review and signature.\n\n"
            "Appointment details:\n"
            "- File: {folio}\n"
            "- Proposed date: {fecha}\n"
            "- Time: {hora}\n"
            "- Address: {direccion_notaria}\n\n"
            "Please confirm your attendance by calling {telefono_contacto}.\n\n"
            "Best regards,\n"
            "{firma_notario}\n"
            "{notaria_nombre}"
        ),
        "required_fields": [
            "cliente_nombre", "folio", "fecha", "hora",
            "direccion_notaria", "telefono_contacto", "firma_notario", "notaria_nombre"
        ],
    },
    {
        "act_type": "matrimonio",
        "name": "Civil Marriage — Notification",
        "description": "Notification of civil marriage processing",
        "language": "en",
        "subject": "Civil Marriage — {contrayente1} & {contrayente2} — {folio}",
        "body_template": (
            "Dear {contrayente1} and {contrayente2},\n\n"
            "We are pleased to inform you that your civil marriage file has been "
            "processed successfully.\n\n"
            "Ceremony details:\n"
            "- File: {folio}\n"
            "- Date: {fecha}\n"
            "- Time: {hora}\n"
            "- Property regime: {regimen}\n\n"
            "Please arrive 30 minutes early with your original IDs.\n\n"
            "Congratulations!\n"
            "{firma_notario}\n"
            "{notaria_nombre}"
        ),
        "required_fields": [
            "contrayente1", "contrayente2", "folio", "fecha",
            "hora", "regimen", "firma_notario", "notaria_nombre"
        ],
    },
    {
        "act_type": "general",
        "name": "General Notarial Communication",
        "description": "Generic notarial correspondence",
        "language": "en",
        "subject": "Notarial Communication — {folio} — {asunto}",
        "body_template": (
            "Dear {cliente_nombre},\n\n"
            "{mensaje_personalizado}\n\n"
            "We remain at your disposal for any further inquiries.\n\n"
            "Best regards,\n"
            "{firma_notario}\n"
            "{notaria_nombre}"
        ),
        "required_fields": [
            "cliente_nombre", "folio", "asunto",
            "mensaje_personalizado", "firma_notario", "notaria_nombre"
        ],
    },
]

# ── Index ID for templates in vector store ───────────────────
_TEMPLATE_INDEX_ID = "__templates__"


@ttl_cache(ttl_seconds=300)
def get_seed_templates() -> List[EmailTemplate]:
    """Return all seed templates as EmailTemplate objects (cached 5 min)."""
    return [EmailTemplate(**t) for t in _SEED_TEMPLATES]


async def index_templates() -> int:
    """
    Index all seed templates into the vector store for semantic search.
    Call once at startup.
    """
    texts = []
    for t in _SEED_TEMPLATES:
        text = f"{t['name']}. {t['description']}. Act type: {t['act_type']}. {t['body_template'][:200]}"
        texts.append(text)

    num = await vector_store.index_document(
        document_id=_TEMPLATE_INDEX_ID,
        chunks=texts,
        metadata={"source": "email_templates", "count": len(texts)},
    )
    logger.info("Indexed %d email templates", num)
    return num


async def find_template(
    query: str,
    act_type: Optional[str] = None,
) -> Optional[EmailTemplate]:
    """
    Find the best matching email template by semantic similarity.

    Args:
        query: Search query (act type, case description)
        act_type: Optional specific act type filter

    Returns:
        Best matching EmailTemplate or None
    """
    # First try exact act_type match
    if act_type:
        for t in _SEED_TEMPLATES:
            if t["act_type"] == act_type:
                logger.info("Template found by act_type: %s", t["name"])
                return EmailTemplate(**t)

    # Fall back to semantic search via vector store
    results = await vector_store.search(
        query=query,
        document_id=_TEMPLATE_INDEX_ID,
        top_k=1,
    )

    if results:
        idx = int(results[0]["chunk_id"]) if results[0]["chunk_id"].isdigit() else 0
        if 0 <= idx < len(_SEED_TEMPLATES):
            logger.info("Template found by semantic search: %s", _SEED_TEMPLATES[idx]["name"])
            return EmailTemplate(**_SEED_TEMPLATES[idx])

    # Final fallback: return general template
    logger.info("No template match found, using general template")
    for t in _SEED_TEMPLATES:
        if t["act_type"] == "general":
            return EmailTemplate(**t)
    return None


def hydrate_template(template: EmailTemplate, fields: Dict[str, str]) -> EmailTemplate:
    """
    Fill a template with the provided field values.
    Missing fields are left as {placeholder}.
    """
    subject = template.subject
    body = template.body_template

    for field in template.required_fields:
        value = fields.get(field, f"{{{{{field}}}}}")
        subject = subject.replace(f"{{{field}}}", value)
        body = body.replace(f"{{{field}}}", value)

    return EmailTemplate(
        act_type=template.act_type,
        name=template.name,
        description=template.description,
        language=template.language,
        subject=subject,
        body_template=body,
        required_fields=template.required_fields,
    )
