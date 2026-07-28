"""
Shared pytest fixtures for all Legis Agent tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client(use_temp_config):
    """FastAPI test client via ASGI transport."""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def sample_txt(tmp_path):
    """Create a sample TXT document for testing."""
    f = tmp_path / "test_doc.txt"
    f.write_text(
        "SALE AND PURCHASE AGREEMENT\n\n"
        "This agreement is made on January 15, 2025 between:\n"
        "John Smith (the 'Seller') and Jane Doe (the 'Buyer').\n\n"
        "Article 1. Purchase Price: USD 150,000.\n"
        "Article 2. Closing Date: March 1, 2025.\n"
        "Article 3. The property is located at 123 Main Street.\n"
        "Article 4. Confidentiality: The parties agree to keep "
        "the terms of this agreement confidential for 2 years.\n"
    )
    return str(f)


@pytest.fixture
def sample_pdf_bytes():
    """Minimal PDF content for testing (not a real PDF — use TXT for tests)."""
    return b"%PDF-1.4 fake pdf content for parser testing"


@pytest.fixture
def mock_llm_fallback(monkeypatch):
    """Mock LLM to return a structured fallback response."""
    async def _fake_llm(*args, **kwargs):
        return (
            "Document type: Contract\n\n"
            "Parties involved:\n"
            "- John Smith (Seller)\n"
            "- Jane Doe (Buyer)\n\n"
            "Key Dates:\n"
            "- January 15, 2025 (Agreement date)\n"
            "- March 1, 2025 (Closing date)\n\n"
            "Main Clauses:\n"
            "1. Purchase Price: USD 150,000\n"
            "2. Closing Date\n"
            "3. Property Address\n"
            "4. Confidentiality: 2 years\n\n"
            "Amounts:\n"
            "- USD 150,000 (Purchase price)\n\n"
            "Risks:\n"
            "- No force majeure clause\n"
            "- Confidentiality is limited to 2 years\n\n"
            "Summary: This is a standard sale and purchase agreement "
            "between John Smith and Jane Doe for a property at "
            "123 Main Street with a purchase price of USD 150,000."
        )
    monkeypatch.setattr("app.core.llm.llm_complete", _fake_llm)
    monkeypatch.setattr("app.core.security.detect_injection_attempt", lambda x: None)
    return _fake_llm


@pytest.fixture
def mock_embeddings(monkeypatch):
    """Mock embeddings to return deterministic vectors."""
    from app.rag.embeddings import EmbeddingsProvider
    
    async def _fake_embed_texts(self, texts):
        return [[0.1, 0.2, 0.3] * 512 for _ in texts]
    
    monkeypatch.setattr(EmbeddingsProvider, "embed_texts", _fake_embed_texts)
    return _fake_embed_texts


@pytest.fixture
def use_temp_config(monkeypatch):
    """Use temporary directories for all file-based storage.

    Include this fixture in tests that need real file I/O.
    Pure unit tests (no file I/O) should NOT include it.
    """
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr("app.core.user_store.USERS_DIR", tmp)
    monkeypatch.setattr("app.core.user_store.USERS_FILE", tmp / "users.json")
    monkeypatch.setattr("app.core.token_store.TOKENS_DIR", tmp)
    monkeypatch.setattr("app.core.token_store.TOKENS_FILE", tmp / "tokens.json")
    monkeypatch.setattr("app.core.gdpr.AUDIT_DIR", tmp)
    monkeypatch.setattr("app.core.gdpr.AUDIT_FILE", tmp / "audit_trail.jsonl")

    # Enable header-based auth for test environment
    from app.core.config import settings as _test_settings
    monkeypatch.setattr(_test_settings, "ENABLE_HEADER_AUTH", True)

    # Set a known ADMIN_PASSWORD so tests can authenticate deterministically.
    monkeypatch.setattr(_test_settings, "ADMIN_PASSWORD", "testAdmin123!")

    # Disable rate limiting for test environment
    from app.core.rate_limit import limiter as _test_limiter
    monkeypatch.setattr(_test_limiter, "enabled", False)

    # Re-trigger default admin creation with temp dir
    from app.core.user_store import _ensure_default_admin
    _ensure_default_admin()
    yield


@pytest.fixture
def admin_password() -> str:
    """Return the deterministic admin password used in tests."""
    return "testAdmin123!"
