"""
Email drafting agent.

Orchestrates:
1. Template matching via vector store
2. Field hydration with Pydantic validation
3. Multi-model LLM routing for email generation
4. Post-generation validation
"""

import json
import logging
from typing import Any, Dict, Tuple

from app.core.email_llm import get_router, get_available_models
from app.core.langfuse import observe
from app.models.schemas import EmailDraftRequest, EmailDraftResponse, EmailTemplate
from app.rag.email_templates import find_template, hydrate_template, index_templates

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a legal notarial assistant specialized in drafting formal email communications.

Your task: Given a template and case data, produce a professional email in the requested language.

Rules:
- Use formal but clear legal language
- Keep the email concise (under 400 words unless specified)
- Include all required fields from the template
- Add a clear subject line
- Always include a professional signature block
- Never invent legal details not present in the provided data
- Output ONLY valid JSON with the structure: {"to": "", "subject": "", "body": "", "attachments": []}"""


@observe(capture_input=True, capture_output=True)
async def draft_email(
    request: EmailDraftRequest,
    document_context: Optional[str] = None,
) -> Tuple[EmailDraftResponse, Dict[str, Any]]:
    """
    Generate a professional email draft for a notarial communication.

    Args:
        request: EmailDraftRequest with act type, fields, and options
        document_context: Optional document text to use as RAG context

    Returns:
        Tuple of (EmailDraftResponse, debug_info)
    """
    debug: Dict[str, Any] = {
        "template_match": None,
        "model_selected": None,
        "model_available": get_available_models(),
        "hydration_ok": False,
        "document_context_used": bool(document_context),
    }

    # 1. Find template
    template = await find_template(
        query=request.act_type,
        act_type=request.act_type,
    )

    if template:
        debug["template_match"] = template.name
        logger.info("Template matched: %s", template.name)
    else:
        logger.warning("No template found for act_type: %s", request.act_type)
        # Use a minimal fallback template
        template = EmailTemplate(
            act_type=request.act_type,
            name="Fallback template",
            description="Auto-generated",
            language=request.language,
            subject="Comunicación notarial — {folio}",
            body_template=(
                "Estimado/a {cliente_nombre},\n\n"
                "{mensaje_personalizado}\n\n"
                "Saludos cordiales,\n"
                "{firma_notario}"
            ),
            required_fields=["cliente_nombre", "folio", "mensaje_personalizado", "firma_notario"],
        )

    # 2. Hydrate template
    hydrated = hydrate_template(template, request.fields)
    debug["hydration_ok"] = True
    logger.debug("Template hydrated with %d fields", len(request.fields))

    # 3. Generate with LLM (skip if no API key configured)
    model_key = "primary"
    from app.core.runtime_config import has_valid_api_key

    if not has_valid_api_key():
        logger.info("No API key configured, returning hydrated template directly")
        draft = EmailDraftResponse(
            subject=hydrated.subject,
            body=hydrated.body_template,
            model_used="template-only",
            template_used=template.name if template else None,
            tokens_used=0,
        )
        debug["model_used"] = "template-only"
        return draft, debug

    router = await get_router()
    if router is None:
        logger.info("No router available, returning hydrated template")
        draft = EmailDraftResponse(
            subject=hydrated.subject,
            body=hydrated.body_template,
            model_used="template-only",
            template_used=template.name if template else None,
            tokens_used=0,
        )
        debug["model_used"] = "template-only"
        return draft, debug
    custom_instructions = request.custom_query or "Complete the email with the provided data."

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Template subject: {hydrated.subject}\n\n"
                f"Template body:\n{hydrated.body_template}\n\n"
                + (f"Document context:\n{document_context[:4000]}\n\n" if document_context else "")
                + f"Additional instructions: {custom_instructions}\n\n"
                + f"Language: {request.language}\n"
                + "Use the document context above to extract real names, dates, amounts, and details.\n" if document_context else ""
                + f"Output valid JSON."
            ),
        },
    ]

    try:
        response = await router.acompletion(
            model=model_key,
            messages=messages,
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        tokens_used = response.usage.total_tokens if hasattr(response, "usage") and response.usage else 0

        try:
            email_data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("LLM did not return valid JSON, wrapping")
            email_data = {"to": "", "subject": hydrated.subject, "body": content, "attachments": []}

        draft = EmailDraftResponse(
            to=email_data.get("to", ""),
            subject=email_data.get("subject", hydrated.subject),
            body=email_data.get("body", hydrated.body_template),
            attachments=email_data.get("attachments", []),
            model_used=model_key,
            template_used=template.name if template else None,
            tokens_used=tokens_used,
        )

        logger.info("Email draft generated (%d tokens, model=%s)", tokens_used, model_key)

    except Exception as e:
        logger.warning("Email generation failed with model '%s': %s", model_key, str(e)[:100])
        draft = EmailDraftResponse(
            subject=hydrated.subject,
            body=hydrated.body_template,
            model_used="fallback",
            template_used=template.name if template else None,
            tokens_used=0,
        )

    return draft, debug
