"""
Multi-provider routing strategy for LiteLLM.

Selects the optimal model based on:
  - sensitivity: private data → local model
  - complexity: long/complex texts → reasoning model
  - language: French → Mistral (or other French-optimized)
  - latency: urgent requests → fast model
  - cost: budget-conscious → cheap model

Each profile maps to a model_name in the LiteLLM Router model list.
"""

import logging
import os
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Model profiles ─────────────────────────────────────────────
#
# These are the model_name values used in the LiteLLM Router.
# Each maps to a specific provider/model combination.
# The actual provider/model details are configured in runtime_config.

PROFILE_REASONING = "reasoning"      # Claude 3 Opus / GPT-4o for complex legal
PROFILE_STRUCTURED = "structured"    # GPT-4o for tool use / JSON
PROFILE_PRIVATE = "private"          # Llama 3.3 self-hosted for sensitive data
PROFILE_FAST = "fast"               # Groq / Haiku for low-latency
PROFILE_FRENCH = "french"            # Mistral for French language
PROFILE_CHEAP = "cheap"              # Gemini Flash for cost savings
PROFILE_FALLBACK = "fallback"        # GPT-4o-mini if all others fail

ALL_PROFILES = [
    PROFILE_REASONING,
    PROFILE_STRUCTURED,
    PROFILE_PRIVATE,
    PROFILE_FAST,
    PROFILE_FRENCH,
    PROFILE_CHEAP,
    PROFILE_FALLBACK,
]

PROFILE_DESCRIPTIONS: Dict[str, str] = {
    PROFILE_REASONING: "Complex legal reasoning (Claude Opus / GPT-4o)",
    PROFILE_STRUCTURED: "Structured tool use & JSON (GPT-4o)",
    PROFILE_PRIVATE: "Sensitive data — local only (Llama 3.3 via vLLM)",
    PROFILE_FAST: "Low-latency responses (Groq / Haiku)",
    PROFILE_FRENCH: "French-optimized (Mistral Large)",
    PROFILE_CHEAP: "Cost-efficient (Gemini Flash)",
    PROFILE_FALLBACK: "Last resort fallback (GPT-4o-mini)",
}


# ── Auto-select strategy ──────────────────────────────────────


def auto_select_profile(
    messages: List[Dict[str, str]],
    sensitivity: Optional[str] = None,
    language: Optional[str] = None,
    urgent: bool = False,
    prefer_cheap: bool = False,
) -> str:
    """
    Auto-select the best model profile for a request.

    Criteria priority:
    1. Sensitivity: private/sensitive → PRIVATE
    2. Urgency: urgent → FAST
    3. Language: French → FRENCH
    4. Cost: budget → CHEAP
    5. Complexity: long/complex → REASONING
    6. Default: STRUCTURED

    Args:
        messages: The message list to analyze
        sensitivity: "normal" | "private"
        language: Language code like "fr", "en", etc.
        urgent: If True, prioritize speed
        prefer_cheap: If True, prioritize cost

    Returns:
        Profile name (model_name for the router)
    """
    # 1. Sensitivity check
    if sensitivity == "private" and _profile_available(PROFILE_PRIVATE):
        logger.info("📡 Routing: PRIVATE (sensitive data)")
        profile = PROFILE_PRIVATE
    elif _detect_sensitive_data(messages) and _profile_available(PROFILE_PRIVATE):
        logger.info("📡 Routing: PRIVATE (sensitive data detected)")
        profile = PROFILE_PRIVATE
    # 2. Urgency
    elif urgent and _profile_available(PROFILE_FAST):
        logger.info("📡 Routing: FAST (urgent)")
        profile = PROFILE_FAST
    # 3. Language
    elif _is_french(messages, language) and _profile_available(PROFILE_FRENCH):
        logger.info("📡 Routing: FRENCH (language)")
        profile = PROFILE_FRENCH
    # 4. Cost
    elif prefer_cheap and _profile_available(PROFILE_CHEAP):
        logger.info("📡 Routing: CHEAP (cost)")
        profile = PROFILE_CHEAP
    # 5. Complexity
    elif _is_complex(messages) and _profile_available(PROFILE_REASONING):
        logger.info("📡 Routing: REASONING (complex query)")
        profile = PROFILE_REASONING
    # 6. Default
    else:
        logger.info("📡 Routing: STRUCTURED (default)")
        profile = PROFILE_STRUCTURED

    # Record routing decision for observability
    try:
        reason = _get_route_reason(profile)
        from app.core.observability import trace_routing
        trace_routing(profile, reason, len(messages))
    except Exception as e:
        logger.debug("Routing trace failed: %s", e)

    return profile


def _get_route_reason(profile: str) -> str:
    """Get a human-readable reason for a routing decision."""
    reasons = {
        PROFILE_PRIVATE: "sensitive_data",
        PROFILE_FAST: "urgent",
        PROFILE_FRENCH: "language_french",
        PROFILE_CHEAP: "cost_optimization",
        PROFILE_REASONING: "complex_query",
        PROFILE_STRUCTURED: "default",
        PROFILE_FALLBACK: "fallback",
    }
    return reasons.get(profile, "unknown")


# ── Detection helpers ──────────────────────────────────────────


_SENSITIVE_PATTERNS = [
    r"\b\d{13}\b",             # French Social Security
    r"\b\d{15}\b",             # SIRET
    r"(?:né|née)\s+le\s+\d{2}/\d{2}/\d{4}",
    r"(?:pièce|passeport|CNI|carte\s+d'identité)\s+n[°o]?\s*\d+",
    r"\b(?:IBAN|RIB|BIC)\b",
    r"\b\d{16}\b",             # Credit card
]


def _detect_sensitive_data(messages: List[Dict[str, str]]) -> bool:
    """Detect if messages contain sensitive personal data."""
    for msg in messages:
        content = msg.get("content", "")
        for pattern in _SENSITIVE_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.debug("Sensitive pattern matched: %s", pattern)
                return True
    return False


def _is_french(messages: List[Dict[str, str]], language: Optional[str] = None) -> bool:
    """Check if the messages are in French."""
    if language == "fr":
        return True
    detected = _detect_language(messages)
    return detected == "fr"


def _detect_language(messages: List[Dict[str, str]]) -> str:
    """Detect the dominant language in messages."""
    combined = " ".join(msg.get("content", "") for msg in messages if msg.get("role") != "system")
    if not combined.strip():
        return "en"

    # French indicators
    fr_words = ["le", "la", "les", "des", "est", "sont", "dans", "avec", "sur",
                "vente", "contrat", "notaire", "clause", "prix", "bien", "soussigné"]

    en_words = ["the", "is", "are", "in", "with", "on", "contract", "sale",
                "price", "property", "party", "clause", "agreement"]

    combined_lower = combined.lower()
    fr_count = sum(1 for w in fr_words if re.search(rf"\b{w}\b", combined_lower))
    en_count = sum(1 for w in en_words if re.search(rf"\b{w}\b", combined_lower))

    # Require ~50% more French indicator words than English ones
    # before classifying as French (avoids false positives on
    # documents with a few French loanwords in English text).
    _LANG_RATIO_THRESHOLD = 1.5
    if fr_count > en_count * _LANG_RATIO_THRESHOLD:
        return "fr"
    return "en"


def _is_complex(messages: List[Dict[str, str]]) -> bool:
    """
    Determine if the request is complex enough to need a reasoning model.
    Based on message length, presence of legal terms, and query depth.
    """
    combined = " ".join(msg.get("content", "") for msg in messages)

    # Long messages — messages over ~1K tokens (~4K chars) suggest
    # enough content to benefit from a reasoning-capable model.
    _COMPLEX_LENGTH_THRESHOLD = 4000
    if len(combined) > _COMPLEX_LENGTH_THRESHOLD:
        return True

    # Legal complexity indicators
    complex_terms = ["clause", "jurisprudence", "article", "code civil",
                     "nullité", "condition suspensive", "hypothèque", "servitude",
                     "usufruit", "indivision", "succession", "donation"]
    combined_lower = combined.lower()
    complex_count = sum(1 for t in complex_terms if t in combined_lower)

    # At least 2 complex legal terms trigger the reasoning profile.
    _COMPLEX_TERM_THRESHOLD = 2
    return complex_count >= _COMPLEX_TERM_THRESHOLD


def _profile_available(profile: str) -> bool:
    """Check if a model profile is available (has API key configured)."""
    # Check if the profile has been configured with credentials
    if profile == PROFILE_PRIVATE:
        # Private profile requires a local vLLM instance
        vllm_base = os.environ.get("VLLM_API_BASE", "")
        return bool(vllm_base)

    # For cloud profiles, check if any provider is configured
    from app.core.runtime_config import has_valid_api_key
    return has_valid_api_key()


# ── Routing config for the LiteLLM Router builder ──────────────


def get_profile_config() -> Dict[str, Any]:
    """
    Get the routing configuration for the current setup.
    Returns the profiles that are available and their descriptions.
    """
    profiles = {}
    for p in ALL_PROFILES:
        profiles[p] = {
            "available": _profile_available(p),
            "description": PROFILE_DESCRIPTIONS.get(p, ""),
        }
    return {
        "strategy": "auto",
        "profiles": profiles,
        "criteria": ["sensitivity", "complexity", "language", "latency", "cost"],
    }
