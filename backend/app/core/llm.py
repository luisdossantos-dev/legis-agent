"""
Multi-LLM router using LiteLLM with fallback support.
Supports OpenAI, Anthropic, Google, Azure, OpenRouter, OpenCode Go,
and local models (Ollama/vLLM).

Reads the active provider and its config from runtime_config,
falling back to .env values when no runtime config exists.

Gracefully handles authentication errors by returning a fallback
message instead of crashing the agent pipeline.

Router cache is invalidated whenever the provider config changes,
so the user can switch providers at runtime without restart.

NOTE: LiteLLM import is deferred to avoid slow startup time.
"""

import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from app.core.circuit_breaker import CircuitBreakerOpenError, llm_circuit_breaker
from app.core.config import settings
from app.core.langfuse import observe
from app.core.logging import record_error
from app.core.profiler import timed
from app.core.observability import get_langfuse, metrics
from app.core.request_id import get_current_request_id
from app.core.routing import ALL_PROFILES, auto_select_profile
from app.core.security import apply_security, audit_log, detect_injection_attempt
from app.core.runtime_config import (
    get_active_api_base,
    get_active_model,
    get_active_provider,
)
from app.core.router_factory import _build_litellm_router, _resolve_api_key, _resolve_profile_model, CachedRouter

logger = logging.getLogger(__name__)

# Sentinel used when no valid API key is configured
_FALLBACK_RESPONSE = (
    "[LLM unavailable — no valid API key configured. "
    "Configure a provider from the Settings panel to enable AI responses.]"
)


def _build_model_list() -> List[Dict[str, Any]]:
    """Build a multi-profile LiteLLM model list.

    Creates entries for all available routing profiles:
      - structured, reasoning, fast, cheap, private, french, fallback

    Each profile maps to the same active provider/key but can be
    configured with different models in the future.
    """
    provider_id = get_active_provider()
    api_key = _resolve_api_key()
    base_model = get_active_model()
    api_base = get_active_api_base()

    if not api_key or api_key in ("sk-your-api-key-here", ""):
        return []

    # Base params shared by all profiles
    base_params = {
        "api_key": api_key,
        "max_tokens": settings.LITELLM_MAX_TOKENS,
        "temperature": settings.LITELLM_TEMPERATURE,
    }
    if api_base:
        base_params["api_base"] = api_base

    from app.core.runtime_config import get_provider_config
    pcfg = get_provider_config(provider_id)
    if "api_version" in pcfg:
        base_params["api_version"] = pcfg["api_version"]

    # Build model list with all profiles
    # Each profile resolves to the appropriate model variant
    # (e.g., "fast" → gpt-4o-mini, "reasoning" → gpt-4o)
    model_list = []

    for profile_name in ALL_PROFILES:
        params = dict(base_params)
        resolved = _resolve_profile_model(
            base_model, profile_name, provider_id=provider_id,
        )
        params["model"] = resolved

        model_list.append({
            "model_name": profile_name,
            "litellm_params": params,
        })

    logger.debug(
        "Model list: %s",
        {m["model_name"]: m["litellm_params"]["model"] for m in model_list},
    )

    return model_list



def _build_llm_router() -> Any:
    """Build the full-featured LLM Router with multi-profile support."""
    model_list = _build_model_list()
    if not model_list:
        return None
    return _build_litellm_router(
        model_list=model_list,
        num_retries=3,
        retry_after=1.0,
        timeout=60,
    )


# Lazy router with config hash for cache invalidation
_llm_router = CachedRouter(name="llm", build_fn=_build_llm_router)


def invalidate_router_cache() -> None:
    """Force the router to be rebuilt on the next call."""
    _llm_router.invalidate()


def _extract_first_json(text: str) -> Optional[Dict[str, Any]]:
    """Extract the first complete JSON object from text.
    Handles arbitrary nesting by counting brace depth."""
    import json
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


@timed("app.core.llm")
@observe(capture_input=True, capture_output=True)
async def llm_complete(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    profile: Optional[str] = None,
    sensitivity: Optional[str] = None,
    language: Optional[str] = None,
    urgent: bool = False,
    prefer_cheap: bool = False,
    **kwargs: Any,
) -> str:
    """
    Execute an LLM call using multi-provider routing.

    Args:
        messages: The messages to send
        model: Specific model_name to use (overrides auto-select)
        profile: Specific routing profile (reasoning, fast, cheap, etc.)
        sensitivity: "normal" or "private" (affects routing)
        language: Language code ("en", "fr", etc.)
        urgent: If True, prioritize low-latency
        prefer_cheap: If True, prioritize cost

    Falls back gracefully when:
    - No API key is configured (returns sentinel message)
    - Authentication fails (returns sentinel message)
    - Any other error occurs (returns sentinel message)
    """
    # ── Security layer: sanitize + guard prompt ────────────────
    injection_warning = None
    for msg in messages:
        content = msg.get("content", "")
        warning = detect_injection_attempt(content)
        if warning:
            injection_warning = warning
            break

    messages = apply_security(messages, metadata={"model": model or profile or "auto"})
    # ────────────────────────────────────────────────────────────

    router = await _llm_router.get()
    if router is None:
        return _FALLBACK_RESPONSE

    # Select model_name: explicit > profile > auto-detect
    if model:
        model_name = model
    elif profile:
        model_name = profile
    else:
        model_name = auto_select_profile(
            messages=messages,
            sensitivity=sensitivity,
            language=language,
            urgent=urgent,
            prefer_cheap=prefer_cheap,
        )

    # Circuit breaker guards — if the LLM provider has been failing
    # repeatedly, the circuit opens and we skip the call entirely.
    # The circuit breaker call is inside the outer try so that any
    # non-circuit-breaker errors (timeouts, auth failures) still hit
    # the outer exception handler for proper logging and metrics.
    # Attach request_id as metadata for observability (Langfuse, etc.)
    llm_metadata = kwargs.pop("metadata", {})
    req_id = get_current_request_id()
    if req_id:
        llm_metadata["request_id"] = req_id
    llm_metadata["application"] = "legis-agent"

    try:
        try:
            response = await llm_circuit_breaker.call(
                router.acompletion,
                model=model_name,
                messages=messages,
                metadata=llm_metadata,
                **kwargs,
            )
        except CircuitBreakerOpenError as e:
            logger.warning("LLM call skipped: %s", e)
            record_error(
                source="llm",
                message=f"LLM circuit breaker open for {model_name}",
                details={"model": model_name, "circuit_state": llm_circuit_breaker.state.value},
            )
            return _FALLBACK_RESPONSE

        msg = response.choices[0].message

        # Some reasoning models (DeepSeek, etc.) put the final answer
        # in 'content' but the reasoning in 'reasoning_content'.
        content = msg.content or ""
        if not content:
            reasoning = getattr(msg, "reasoning_content", None) or getattr(msg, "reasoning", None) or ""
            if reasoning:
                reasoning_str = str(reasoning)
                json_obj = _extract_first_json(reasoning_str)
                if json_obj:
                    import json
                    content = json.dumps(json_obj)
                else:
                    content = reasoning_str

        if hasattr(response, "usage") and response.usage:
            logger.debug(
                "LLM response received (%d tokens, content_len=%d)",
                response.usage.total_tokens,
                len(content),
            )

        # Audit log (non-critical, best-effort)
        try:
            await audit_log.log_interaction(
                messages=messages,
                response=content[:2000],
                metadata={
                    "model": model_name,
                    "provider": get_active_provider(),
                    "tokens": response.usage.total_tokens if hasattr(response, "usage") and response.usage else 0,
                    "request_id": get_current_request_id()[:12],
                },
                injection_warning=injection_warning,
            )
        except (OSError, ConnectionError) as e:
            logger.warning("Failed to write audit log (success path): %s", e)

        # Observability (non-critical, best-effort)
        try:
            tokens_in = 0
            tokens_out = 0
            if hasattr(response, "usage") and response.usage:
                if hasattr(response.usage, "prompt_tokens"):
                    tokens_in = response.usage.prompt_tokens
                if hasattr(response.usage, "completion_tokens"):
                    tokens_out = response.usage.completion_tokens

            from app.core.observability import estimate_call_cost, score_llm_response, get_langfuse
            cost = estimate_call_cost(model_name, tokens_in, tokens_out)

            metrics.record_llm_call(
                provider=get_active_provider(),
                model=model_name,
                operation="llm_complete",
                latency_ms=0,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                cost_usd=cost,
                success=True,
            )

            if model_name in ("reasoning", "structured", "private", "fast", "french", "cheap", "fallback"):
                metrics.record_routing(model_name, "auto-selected", len(messages))

            # Langfuse quality scoring (best-effort)
            lf = get_langfuse()
            if lf:
                try:
                    last_query = messages[-1].get("content", "") if messages else ""
                    llm_metadata.get("langfuse_trace_id")
                    score_llm_response(
                        trace_id=llm_metadata.get("langfuse_trace_id", "") or req_id or "unknown",
                        response=content[:2000],
                        query=last_query[:500],
                        operation="llm_complete",
                        expected_format=llm_metadata.get("expected_format"),
                    )
                except (OSError, ValueError) as e:
                    logger.debug("Langfuse scoring failed: %s", e)
        except (OSError, ValueError) as e:
            logger.debug("Failed to record metrics (success path): %s", e)

        return content

    except (ConnectionError, TimeoutError, ValueError, OSError, ImportError) as e:
        error_str = str(e)
        is_auth = "401" in error_str or "AuthenticationError" in error_str or "authentication" in error_str.lower()

        record_error(
            source="llm",
            message=f"LLM call failed: {error_str[:200]}",
            details={
                "provider": get_active_provider(),
                "model": model_name,
                "auth_error": is_auth,
            },
            exc_info=not is_auth,
        )

        # ── Audit log (error) ──────────────────────────────────
        try:
            await audit_log.log_interaction(
                messages=messages,
                response=f"ERROR: {error_str[:300]}",
                metadata={
                    "model": model_name,
                    "provider": get_active_provider(),
                    "error": error_str[:200],
                    "auth_error": is_auth,
                    "request_id": get_current_request_id()[:12],
                },
                injection_warning=injection_warning,
            )
        except (OSError, ConnectionError) as e:
            logger.warning("Failed to write audit log (error path): %s", e)

        # ── Observability (error) ──────────────────────────────
        try:
            metrics.record_llm_call(
                provider=get_active_provider(),
                model=model_name,
                operation="llm_complete",
                latency_ms=0,
                success=False,
                error=error_str[:200],
            )
        except (OSError, ValueError) as e:
            logger.debug("Failed to record metrics (error path): %s", e)
        # ────────────────────────────────────────────────────────

        if is_auth:
            logger.warning(
                "LLM auth error for provider '%s'. Check your API key.",
                get_active_provider(),
            )
        else:
            logger.error("LLM call error: %s", error_str[:300])

        return _FALLBACK_RESPONSE


async def llm_complete_stream(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    profile: Optional[str] = None,
    sensitivity: Optional[str] = None,
    language: Optional[str] = None,
    urgent: bool = False,
    prefer_cheap: bool = False,
    **kwargs: Any,
) -> AsyncGenerator[str, None]:
    """
    Stream an LLM call token by token.

    Same routing, security, and fallback logic as `llm_complete`,
    but yields each content token as it arrives from the provider.

    Yields:
        SSE-formatted strings:
          data: {"token": "...", "done": false}\n\n
          data: {"token": "", "done": true, "error": "..."}\n\n  (on completion/error)
    """
    import json

    # ── Security layer ────────────────────────────────────────
    injection_warning = None
    for msg in messages:
        content = msg.get("content", "")
        warning = detect_injection_attempt(content)
        if warning:
            injection_warning = warning
            break

    messages = apply_security(messages, metadata={"model": model or profile or "auto"})
    # ──────────────────────────────────────────────────────────

    router = await _llm_router.get()
    if router is None:
        yield f"data: {json.dumps({'token': _FALLBACK_RESPONSE, 'done': True})}\n\n"
        return

    # Select model
    if model:
        model_name = model
    elif profile:
        model_name = profile
    else:
        model_name = auto_select_profile(
            messages=messages,
            sensitivity=sensitivity,
            language=language,
            urgent=urgent,
            prefer_cheap=prefer_cheap,
        )

    llm_metadata = kwargs.pop("metadata", {})
    req_id = get_current_request_id()
    if req_id:
        llm_metadata["request_id"] = req_id
    llm_metadata["application"] = "legis-agent"

    collected_tokens: List[str] = []

    try:
        try:
            stream = await llm_circuit_breaker.call(
                router.acompletion,
                model=model_name,
                messages=messages,
                stream=True,
                metadata=llm_metadata,
                **kwargs,
            )
        except CircuitBreakerOpenError as e:
            logger.warning("LLM stream skipped: %s", e)
            record_error(
                source="llm",
                message=f"LLM circuit breaker open for {model_name}",
                details={"model": model_name, "circuit_state": llm_circuit_breaker.state.value},
            )
            yield f"data: {json.dumps({'token': _FALLBACK_RESPONSE, 'done': True})}\n\n"
            return

        async for chunk in stream:
            # Some streaming implementations may have empty choices on the first chunk
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                token = delta.content
                collected_tokens.append(token)
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"

            finish_reason = chunk.choices[0].finish_reason
            if finish_reason == "stop":
                break

        full_content = "".join(collected_tokens)

        # ── Audit log (non-critical, best-effort) ─────────────
        try:
            await audit_log.log_interaction(
                messages=messages,
                response=full_content[:2000],
                metadata={
                    "model": model_name,
                    "provider": get_active_provider(),
                    "request_id": get_current_request_id()[:12],
                },
                injection_warning=injection_warning,
            )
        except (OSError, ConnectionError) as e:
            logger.warning("Failed to write audit log (stream): %s", e)

        # ── Metrics (non-critical) ────────────────────────────
        try:
            tokens_in = sum(len(m.get("content", "")) for m in messages) // 4
            tokens_out = len(full_content.split())
            from app.core.observability import estimate_call_cost
            cost = estimate_call_cost(model_name, tokens_in, tokens_out)

            metrics.record_llm_call(
                provider=get_active_provider(),
                model=model_name,
                operation="llm_complete_stream",
                latency_ms=0,
                tokens_input=tokens_in,
                tokens_output=tokens_out,
                cost_usd=cost,
                success=True,
            )
        except (OSError, ValueError) as e:
            logger.debug("Failed to record metrics (stream): %s", e)

        yield f"data: {json.dumps({'token': '', 'done': True})}\n\n"

    except (ConnectionError, TimeoutError, ValueError, OSError, ImportError) as e:
        error_str = str(e)
        is_auth = "401" in error_str or "AuthenticationError" in error_str or "authentication" in error_str.lower()

        record_error(
            source="llm",
            message=f"LLM stream failed: {error_str[:200]}",
            details={"provider": get_active_provider(), "model": model_name, "auth_error": is_auth},
            exc_info=not is_auth,
        )

        try:
            metrics.record_llm_call(
                provider=get_active_provider(),
                model=model_name,
                operation="llm_complete_stream",
                latency_ms=0,
                success=False,
                error=error_str[:200],
            )
        except (OSError, ValueError):
            pass

        yield f"data: {json.dumps({'token': _FALLBACK_RESPONSE, 'done': True, 'error': error_str[:200]})}\n\n"
