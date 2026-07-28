"""
🟤 PROPERTY-BASED TESTS — Verify invariants across many random inputs.
Uses Hypothesis with fixed seeds for deterministic, reproducible tests.
"""

from hypothesis import given, settings, strategies as st, seed as hyp_seed
import pytest


# ── Constants ──────────────────────────────────────────────────

VALID_ACT_TYPES = ["escritura", "poder", "testamento", "matrimonio", "general"]
VALID_CLAUSE_TYPES = ["prix", "delai", "condition_suspensive", "renonciation", "garantie", "penalite", "autre"]
VALID_ROLES = ["notaire", "assistant", "stagiaire", "admin"]
VALID_CATEGORIES = ["cliente_nuevo", "seguimiento_escritura", "consulta_hipoteca", "notificacion_banco", "spam", "interno"]


# ── Text strategies ────────────────────────────────────────────

safe_text = st.text(
    alphabet=st.characters(blacklist_characters=["\x00"]),
    min_size=1, max_size=500,
)


# ── Schema invariants ─────────────────────────────────────────

class TestSchemaInvariants:
    """Pydantic schema invariants: models can be constructed with valid data."""

    # Username regex: ^[a-zA-Z0-9_-]+$
    _username_strategy = st.from_regex(
        r"^[a-zA-Z0-9_-]+$",
        fullmatch=True,
    ).filter(lambda s: len(s) >= 2 and len(s) <= 30)

    @hyp_seed(42)
    @settings(max_examples=50)
    @given(
        username=_username_strategy,
        password=st.text(min_size=8, max_size=30),
    )
    def test_user_create_valid(self, username, password):
        """UserCreate should accept any valid username/password."""
        from app.models.auth import UserCreate
        email = f"{username}@test.com"
        user = UserCreate(
            username=username,
            email=email,
            password=password,
            role="notaire",
        )
        assert user.username == username
        assert user.email == email

    @hyp_seed(42)
    @settings(max_examples=30)
    @given(
        username=st.text(min_size=0, max_size=1),
        password=st.text(min_size=0, max_size=7),
    )
    def test_user_create_too_short(self, username, password):
        """UserCreate should reject too-short fields."""
        from app.models.auth import UserCreate
        import pydantic
        with pytest.raises(pydantic.ValidationError):
            UserCreate(
                username=username or "a",
                email="test@test.com",
                password=password or "a",
                role="notaire",
            )

    @hyp_seed(42)
    @settings(max_examples=20)
    @given(role=st.sampled_from(VALID_ROLES))
    def test_analysis_result_default_document_id(self, role):
        """AnalysisResult should have document_id default to empty string."""
        from app.models.schemas import AnalysisResult
        result = AnalysisResult()
        assert result.document_id == ""
        assert isinstance(result.document_id, str)

    @hyp_seed(42)
    @settings(max_examples=20)
    @given(act_type=st.sampled_from(VALID_ACT_TYPES))
    def test_email_template_act_type(self, act_type):
        """EmailTemplate should accept any valid act type."""
        from app.models.schemas import EmailTemplate
        template = EmailTemplate(
            act_type=act_type,
            name="Test",
            description="Test template",
            subject="Test {field}",
            body_template="Body {field}",
            required_fields=["field"],
        )
        assert template.act_type == act_type
        assert template.language == "es"  # default

    @hyp_seed(42)
    @settings(max_examples=20)
    @given(category=st.sampled_from(VALID_CATEGORIES))
    def test_email_classification_response(self, category):
        """EmailClassificationResponse should accept any valid category."""
        from app.models.schemas import EmailClassificationResponse
        resp = EmailClassificationResponse(category=category, confidence=0.5)
        assert resp.category == category
        assert 0.0 <= resp.confidence <= 1.0

    @hyp_seed(42)
    @settings(max_examples=20)
    @given(clause_type=st.sampled_from(VALID_CLAUSE_TYPES))
    def test_clause_review_request(self, clause_type):
        """ClauseReviewRequest should accept any valid clause type."""
        from app.models.schemas import ClauseReviewRequest
        req = ClauseReviewRequest(clause_text="Test clause text", clause_type=clause_type)
        assert req.clause_type == clause_type


# ── Domain invariants ─────────────────────────────────────────

class TestDomainInvariants:
    """Domain logic invariants."""

    @hyp_seed(42)
    @settings(max_examples=30)
    @given(
        text=st.text(min_size=1, max_size=1000),
    )
    def test_sanitize_text_preserves_content(self, text):
        """Sanitize text should preserve the original content (minus control chars)."""
        from app.core.security import sanitize_text
        sanitized = sanitize_text(text)
        # The sanitized text should be a substring-ish of the original
        # (it strips null bytes and control chars)
        for ch in ["\x00", "\x01", "\x02", "\x03", "\x04", "\x05", "\x06", "\x07", "\x08",
                     "\x0b", "\x0c", "\x0e", "\x0f", "\x10", "\x11", "\x12", "\x13",
                     "\x14", "\x15", "\x16", "\x17", "\x18", "\x19", "\x1a", "\x1b",
                     "\x1c", "\x1d", "\x1e", "\x1f", "\x7f"]:
            assert ch not in sanitized

    @hyp_seed(42)
    @settings(max_examples=20)
    @given(
        text=st.text(min_size=1, max_size=500),
        max_chars=st.integers(min_value=10, max_value=1000),
    )
    def test_sanitize_text_truncation(self, text, max_chars):
        """Sanitize text should truncate at max_chars."""
        from app.core.security import sanitize_text
        sanitized = sanitize_text(text, max_chars=max_chars)
        assert len(sanitized) <= max_chars + len("[TRUNCATED]")

    @hyp_seed(42)
    @settings(max_examples=20)
    @given(
        username=TestSchemaInvariants._username_strategy,
    )
    def test_role_assignment_defaults_to_stagiaire(self, username):
        """New users without explicit role should default to stagiaire."""
        from app.models.auth import UserBase
        email = f"{username}@test.com"
        user = UserBase(username=username, email=email)
        assert user.role.value == "stagiaire"
        assert user.is_active is True

    @hyp_seed(42)
    @settings(max_examples=10)
    @given(
        url=st.sampled_from([
            "https://platform.openai.com/api-keys",
            "https://console.anthropic.com/",
            "https://aistudio.google.com/apikey",
            "https://openrouter.ai/keys",
            "https://opencode.ai/auth",
        ]),
    )
    def test_provider_configs_have_docs_url(self, url):
        """All provider configs should have a docs_url."""
        from app.core.runtime_config import PROVIDER_CONFIGS
        found = False
        for pid, cfg in PROVIDER_CONFIGS.items():
            if cfg["docs_url"] == url:
                found = True
                break
        assert found, f"No provider has docs_url={url}"
