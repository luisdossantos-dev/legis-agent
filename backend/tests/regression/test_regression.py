"""
🔴 REGRESSION TESTS — Prevent fixed bugs from recurring.

Each test reproduces a known bug scenario and verifies it stays fixed.
"""

import pytest


@pytest.mark.asyncio
class TestAuthRegression:
    """Regression tests for auth-related bugs."""

    async def test_upload_without_auth_returns_200_not_401(self, client, sample_txt):
        """
        BUG: Upload endpoint required authentication, returning 401.
        FIX: Made auth optional via get_optional_current_user().
        This test verifies that upload works WITHOUT any auth headers.
        """
        with open(sample_txt, "rb") as f:
            resp = await client.post(
                "/api/documents/upload",
                files={"file": ("regression_test.txt", f, "text/plain")},
            )
        assert resp.status_code == 200, (
            f"Upload without auth should return 200, got {resp.status_code}. "
            "This is a regression of the auth-required-on-upload bug."
        )
        data = resp.json()
        assert "id" in data

    async def test_upload_works_with_auth_headers(self, client, sample_txt, admin_password):
        """
        Ensures upload also works when auth headers ARE provided.
        Both auth and no-auth paths must work.
        """
        # Login first
        login = await client.post(
            "/api/rbac/auth/login",
            params={"username": "admin", "password": admin_password},
        )
        token = login.json()["token"]

        with open(sample_txt, "rb") as f:
            resp = await client.post(
                "/api/documents/upload",
                files={"file": ("auth_test.txt", f, "text/plain")},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestAnalysisRegression:
    """Regression tests for analysis-related bugs."""

    async def test_analyze_returns_document_id(self, client, sample_txt, mock_llm_fallback, mock_embeddings):
        """
        BUG: AnalysisResult was missing document_id, causing Pydantic validation error.
        FIX: Defensive code in api/agents.py adds document_id if missing.
        This test verifies that analysis always includes document_id.
        """
        # Upload
        with open(sample_txt, "rb") as f:
            upload = await client.post(
                "/api/documents/upload",
                files={"file": ("regression_docid.txt", f, "text/plain")},
            )
        assert upload.status_code == 200, f"Upload failed: {upload.text}"
        doc_id = upload.json()["id"]

        # Analyze
        resp = await client.post(
            "/api/agents/analyze",
            json={"document_id": doc_id, "query": "Analyze this legal document."},
        )
        assert resp.status_code == 200, f"Analysis failed: {resp.text[:200]}"
        analysis = resp.json()["analysis"]
        assert "document_id" in analysis, "AnalysisResult must contain document_id"
        assert analysis["document_id"] == doc_id, (
            f"document_id should match: expected {doc_id}, got {analysis['document_id']}"
        )


@pytest.mark.asyncio
class TestEmailTemplateRegression:
    """Regression tests for email template bugs."""

    async def test_email_templates_are_in_english(self, client):
        """
        BUG: Email templates were in Spanish.
        FIX: Translated all templates to English.
        This test verifies templates have English descriptions.
        """
        resp = await client.get("/api/email/templates")
        assert resp.status_code == 200
        templates = resp.json()["templates"]
        for tmpl in templates:
            assert tmpl["language"] == "en", (
                f"Template '{tmpl['act_type']}' has language='{tmpl['language']}', expected 'en'. "
                "This is a regression of the Spanish template bug."
            )
            # Description should be in English (no Spanish words)
            english_indicators = ["Notification", "Confirmation", "Appointment", "Communication", "Correspondence", "Generic", "Deed", "Power of Attorney", "Will", "Marriage", "Signing"]
            has_english = any(ind in tmpl["description"] for ind in english_indicators)
            assert has_english, (
                f"Template '{tmpl['act_type']}' description '{tmpl['description']}' "
                "doesn't appear to be in English."
            )


class TestModelRegression:
    """Regression tests for Pydantic model bugs."""

    def test_analysis_result_accepts_empty_dict(self):
        """
        BUG: AnalysisResult(**{}) raised Field required for document_id.
        FIX: document_id has default value "".
        This test verifies the default works.
        """
        from app.models.schemas import AnalysisResult
        result = AnalysisResult(**{})
        assert result.document_id == ""
        assert result.document_type is None
        assert result.parties == []
        assert result.summary == ""

    def test_user_update_without_username(self):
        """
        BUG: UserUpdate had reference to non-existent 'username' field.
        FIX: Removed username reference from update_user().
        This test verifies UserUpdate works without username.
        """
        from app.models.auth import UserUpdate
        update = UserUpdate(email="new@test.com", is_active=False)
        assert update.email == "new@test.com"
        assert update.is_active is False
        assert update.role is None  # not provided
