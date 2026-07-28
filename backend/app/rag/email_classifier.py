"""
Intelligent email classifier for notarial communications.

Hybrid approach:
1. Fast path: Embed the email text and find the closest category
   centroid by cosine similarity. If confidence >= 0.7, return it.
2. Slow path: If confidence < 0.7, route to the active LLM
   for assisted classification.

Categories:
  - cliente_nuevo      New client / first contact
  - seguimiento_escritura  Deed of sale follow-up
  - consulta_hipoteca  Mortgage / loan consultation
  - notificacion_banco Bank notification
  - spam               Unsolicited / junk
  - interno            Internal office communication
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.core.llm import llm_complete
from app.models.schemas import EMAIL_CATEGORIES, EmailClassificationResponse
from app.rag.embeddings import embeddings_provider

logger = logging.getLogger(__name__)

# ── Seed descriptions for each category ───────────────────────
# Each category has a list of example phrases that represent it.
# These are embedded once and averaged to form category centroids.

_CATEGORY_SEEDS: Dict[str, List[str]] = {
    "cliente_nuevo": [
        "I would like to inquire about your notarial services",
        "First contact request for information about property deeds",
        "New client looking for a notary public",
        "I need information about costs and procedures for a power of attorney",
        "Quisiera solicitar información sobre servicios notariales",
        "Soy un nuevo cliente y necesito asesoramiento",
    ],
    "seguimiento_escritura": [
        "Follow-up on the deed of sale for property transfer",
        "Status update on escritura pública for Main St property",
        "When will the deed be ready for signing",
        "Coordination of closing date for property purchase",
        "Seguimiento de escritura de compraventa",
        "Consulta sobre el estado de mi escritura",
    ],
    "consulta_hipoteca": [
        "Mortgage loan consultation for a new property",
        "I would like to discuss financing options",
        "Questions about mortgage interest rates and terms",
        "Loan pre-approval for home purchase",
        "Consulta sobre hipoteca para compra de vivienda",
        "Información sobre préstamos hipotecarios",
    ],
    "notificacion_banco": [
        "Payment confirmation from Banco Santander for deed processing",
        "Bank transfer notification for escrow account",
        "Notification of funds release for property purchase",
        "Bank statement for mortgage account #12345",
        "Notificación bancaria de transferencia recibida",
        "Confirmación de pago de honorarios notariales",
    ],
    "spam": [
        "You have won a free vacation, claim now",
        "Get rich quick with real estate investments",
        "Exclusive offer for you, limited time only",
        "Your account has been compromised, click here to verify",
        "Gana dinero fácil invirtiendo en propiedades",
        "Oferta exclusiva, actúe ahora",
    ],
    "interno": [
        "Internal memo regarding office hours during holidays",
        "Staff meeting agenda for next week",
        "New document management system training",
        "Office supply request for the notary department",
        "Memorándum interno sobre horarios de atención",
        "Reunión de personal del departamento legal",
    ],
}

_CATEGORY_LIST = list(_CATEGORY_SEEDS.keys())

# ── Pre-computed category centroids ───────────────────────────

_centroids: Optional[Dict[str, List[float]]] = None


async def _compute_centroids() -> Dict[str, List[float]]:
    """Embed each category's seed phrases and average them into centroids."""
    global _centroids
    if _centroids is not None:
        return _centroids

    centroids: Dict[str, List[float]] = {}
    for cat, phrases in _CATEGORY_SEEDS.items():
        embeddings = await embeddings_provider.embed_texts(phrases)
        if embeddings:
            arr = np.array(embeddings)
            centroid = arr.mean(axis=0).tolist()
            centroids[cat] = centroid
        else:
            logger.warning("No embeddings for category '%s', using random centroid", cat)
            rng = np.random.RandomState(hash(cat) % 2**32)
            centroids[cat] = rng.randn(1536).tolist()

    _centroids = centroids
    logger.info("Computed %d category centroids", len(centroids))
    return centroids


# ── Fast path: embedding-based classification ─────────────────


async def _classify_by_embedding(
    email_text: str,
) -> Optional[Tuple[str, float]]:
    """
    Classify by finding the closest category centroid.

    Returns:
        (category, confidence) or None if no categories
    """
    centroids = await _compute_centroids()
    if not centroids:
        return None

    email_vec = np.array(await embeddings_provider.embed_text(email_text))
    if email_vec.size == 0:
        return None

    # Normalize email vector
    email_norm = np.linalg.norm(email_vec)
    if email_norm == 0:
        return None
    email_vec = email_vec / email_norm

    best_cat: Optional[str] = None
    best_score = -1.0

    for cat, centroid in centroids.items():
        c_vec = np.array(centroid)
        c_norm = np.linalg.norm(c_vec)
        if c_norm == 0:
            continue
        c_vec = c_vec / c_norm

        score = float(np.dot(email_vec, c_vec))
        if score > best_score:
            best_score = score
            best_cat = cat

    if best_cat is None:
        return None

    # Convert cosine similarity to a 0-1 confidence score
    # Cosine sim is [-1, 1]; shift to [0, 1]
    confidence = (best_score + 1.0) / 2.0
    # Clamp
    confidence = max(0.0, min(1.0, confidence))

    return best_cat, confidence


# ── Slow path: LLM-assisted classification ────────────────────

_CLASSIFICATION_SYSTEM_PROMPT = """You are a notarial office assistant specialized in email classification.

Classify the following email into EXACTLY ONE of these categories:

- cliente_nuevo: New client inquiry, first contact, request for notarial services info
- seguimiento_escritura: Deed of sale follow-up, property transfer status, escritura pública
- consulta_hipoteca: Mortgage consultation, loan inquiry, financing questions
- notificacion_banco: Bank notification, payment confirmation, bank transfer notice
- spam: Unsolicited commercial email, phishing, junk mail, scams
- interno: Internal office communication, staff memo, inter-departmental

Respond with ONLY a JSON object:
{"category": "<category_name>", "confidence": <0.0-1.0>, "reason": "<brief explanation>"}"""


async def _classify_by_llm(email_text: str) -> Tuple[str, float, str]:
    """
    Classify using the active LLM with a structured prompt.

    Returns:
        (category, confidence, reason)
    """
    # Truncate to avoid excessive token usage
    max_chars = 3000
    if len(email_text) > max_chars:
        email_text = email_text[:max_chars] + "\n\n[...truncated...]"

    messages = [
        {"role": "system", "content": _CLASSIFICATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Email to classify:\n\n{email_text}",
        },
    ]

    response = await llm_complete(messages)

    # Try to parse JSON from the response
    try:
        # Find JSON block in the response
        import re
        json_match = re.search(r"\{[^}]+\}", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
        else:
            data = json.loads(response)

        category = data.get("category", "interno")
        confidence = float(data.get("confidence", 0.5))
        reason = data.get("reason", "")

        # Validate category
        if category not in EMAIL_CATEGORIES:
            logger.warning("LLM returned invalid category '%s', defaulting to 'interno'", category)
            category = "interno"
            confidence = 0.5

        confidence = max(0.0, min(1.0, confidence))
        return category, confidence, reason

    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning("Failed to parse LLM classification response: %s", e)
        # Fallback: try to find a category name in the response
        for cat in EMAIL_CATEGORIES:
            if cat in response.lower():
                logger.info("Fallback: matched category '%s' in LLM response", cat)
                return cat, 0.6, "Parsed from LLM response text"
        return "interno", 0.5, "Classification failed, defaulted to interno"


# ── Public API ────────────────────────────────────────────────


async def classify_email(
    subject: str,
    body: str,
    from_address: str = "",
    to_address: str = "",
    email_id: Optional[str] = None,
) -> EmailClassificationResponse:
    """
    Classify an incoming email using the hybrid approach.

    1. Fast path: Embed the email text and find closest category centroid.
       If confidence >= 0.7, return immediately.
    2. Slow path: Route to LLM for assisted classification.

    Args:
        subject: Email subject line
        body: Email body text
        from_address: Sender email address
        to_address: Recipient email address
        email_id: Optional email identifier

    Returns:
        EmailClassificationResponse with category, confidence, method
    """
    email_text = f"Subject: {subject}\n\n{body}"
    if from_address:
        email_text = f"From: {from_address}\n{email_text}"
    if to_address:
        email_text = f"To: {to_address}\n{email_text}"

    eid = email_id or str(uuid.uuid4())

    # ── Fast path: embedding ──────────────────────────────
    # Only use embedding path if we have real (non-mock) embeddings.
    # Mock embeddings produce random cosine similarities and are unreliable.
    from app.rag.embeddings import embeddings_provider
    using_mock = getattr(embeddings_provider, "_local_mode", False)

    if not using_mock:
        embedding_result = await _classify_by_embedding(email_text)

        if embedding_result is not None:
            category, confidence = embedding_result
            logger.info(
                "Email %s: embedding classified as '%s' (confidence=%.4f)",
                eid, category, confidence,
            )

            if confidence >= 0.7:
                return EmailClassificationResponse(
                    email_id=eid,
                    category=category,
                    confidence=round(confidence, 4),
                    method="embedding",
                    details="High-confidence embedding match",
                )

        logger.info("Email %s: embedding confidence < 0.7, routing to LLM", eid)
    else:
        logger.info("Email %s: mock embeddings active, routing directly to LLM", eid)

    # ── Slow path: LLM ────────────────────────────────────

    llm_category, llm_confidence, llm_reason = await _classify_by_llm(email_text)

    logger.info(
        "Email %s: LLM classified as '%s' (confidence=%.4f, reason=%s)",
        eid, llm_category, llm_confidence, llm_reason,
    )

    return EmailClassificationResponse(
        email_id=eid,
        category=llm_category,
        confidence=round(llm_confidence, 4),
        method="llm",
        details=llm_reason or f"LLM assisted classification (embedding gave {embedding_result[1] if embedding_result else 'N/A'})",
    )
