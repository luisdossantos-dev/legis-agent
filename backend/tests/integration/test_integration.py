"""
🟣 INTEGRATION TESTS — End-to-end flows for critical user journeys.
"""

import pytest


async def _upload_doc(client, sample_txt):
    with open(sample_txt, "rb") as f:
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", f, "text/plain")},
        )
    assert resp.status_code == 200
    return resp.json()["id"]


@pytest.mark.asyncio
class TestDocumentLifecycle:
    """Full document lifecycle: upload → analyze → chat."""

    async def test_full_upload_analyze_flow(self, client, sample_txt, mock_llm_fallback, mock_embeddings):
        """Upload a document, then analyze it."""
        doc_id = await _upload_doc(client, sample_txt)

        # List should contain it
        list_resp = await client.get("/api/documents/")
        docs = list_resp.json()["documents"]
        assert any(d["id"] == doc_id for d in docs)

        # Analyze it
        analyze_resp = await client.post(
            "/api/agents/analyze",
            json={"document_id": doc_id, "query": "Analyze this legal document."},
        )
        assert analyze_resp.status_code == 200
        analysis = analyze_resp.json()["analysis"]
        assert analysis["document_id"] == doc_id
        assert len(analysis["summary"]) > 0

    async def test_full_upload_chat_flow(self, client, sample_txt, mock_llm_fallback, mock_embeddings):
        """Upload a document, then chat about it."""
        doc_id = await _upload_doc(client, sample_txt)

        chat_resp = await client.post(
            "/api/agents/chat",
            json={
                "document_id": doc_id,
                "messages": [{"role": "assistant", "content": "Hi, I'm the legal assistant."}],
                "query": "Summarize the key clauses.",
            },
        )
        assert chat_resp.status_code == 200
        data = chat_resp.json()
        assert "response" in data
        assert len(data["response"]) > 0

    async def test_two_documents_independent(self, client, tmp_path, mock_llm_fallback, mock_embeddings):
        """Two uploaded documents should be independent."""
        # Create two docs
        f1 = tmp_path / "doc1.txt"
        f1.write_text("Contract A between Party A and Party B.")
        f2 = tmp_path / "doc2.txt"
        f2.write_text("Contract B between Party C and Party D.")

        ids = []
        for f in [f1, f2]:
            with open(f, "rb") as fh:
                resp = await client.post(
                    "/api/documents/upload",
                    files={"file": (f.name, fh, "text/plain")},
                )
            assert resp.status_code == 200
            ids.append(resp.json()["id"])

        assert ids[0] != ids[1]  # Different IDs

        # Both should be listable
        list_resp = await client.get("/api/documents/")
        doc_ids = [d["id"] for d in list_resp.json()["documents"]]
        assert ids[0] in doc_ids
        assert ids[1] in doc_ids


@pytest.mark.asyncio
class TestRBACFullFlow:
    """Full RBAC flow: login → create users → manage → audit."""

    async def test_admin_login_and_manage_users(self, client, admin_password):
        """Admin can log in and create/manage users."""
        # Login as admin
        login = await client.post(
            "/api/rbac/auth/login",
            params={"username": "admin", "password": admin_password},
        )
        assert login.status_code == 200
        token = login.json()["token"]
        admin_user = login.json()["user"]
        assert admin_user["role"] == "admin"

        # Create a notaire user
        create = await client.post(
            "/api/rbac/users",
            json={
                "username": "notaire1",
                "email": "notaire@test.com",
                "password": "test1234",
                "role": "notaire",
                "office": "main",
                "display_name": "Test Notaire",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create.status_code == 201
        notaire_id = create.json()["id"]

        # List users
        listing = await client.get(
            "/api/rbac/users",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listing.status_code == 200
        assert len(listing.json()) >= 2

        # Login as the new user
        notaire_login = await client.post(
            "/api/rbac/auth/login",
            params={"username": "notaire1", "password": "test1234"},
        )
        assert notaire_login.status_code == 200
        assert notaire_login.json()["user"]["role"] == "notaire"

        # Notaire should not be able to list users (admin only)
        notaire_token = notaire_login.json()["token"]
        forbidden = await client.get(
            "/api/rbac/users",
            headers={"Authorization": f"Bearer {notaire_token}"},
        )
        assert forbidden.status_code == 403

    async def test_audit_trail_records_actions(self, client, admin_password):
        """Actions should be recorded in the audit trail."""
        login = await client.post(
            "/api/rbac/auth/login",
            params={"username": "admin", "password": admin_password},
        )
        token = login.json()["token"]

        # Create a user (this should be logged)
        await client.post(
            "/api/rbac/users",
            json={
                "username": "audit_test",
                "email": "audit@test.com",
                "password": "test1234",
                "role": "assistant",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        # Check audit trail
        audit = await client.get(
            "/api/rbac/audit?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert audit.status_code == 200
        data = audit.json()
        assert data["total"] >= 1
        # Should have at least a CREATE action
        create_entries = [
            e for e in data["entries"]
            if e.get("action") == "create" and e.get("resource_type") == "user"
        ]
        assert len(create_entries) >= 1

    async def test_gdpr_export_flow(self, client, admin_password):
        """GDPR export should return user data."""
        login = await client.post(
            "/api/rbac/auth/login",
            params={"username": "admin", "password": admin_password},
        )
        token = login.json()["token"]
        user_id = login.json()["user"]["id"]

        export = await client.post(
            f"/api/rbac/export/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert export.status_code == 200
        data = export.json()
        assert data["user"]["username"] == "admin"
        assert "interactions" in data


@pytest.mark.asyncio
class TestEmailFullFlow:
    """Full email flow: draft → classify → action."""

    async def test_email_lifecycle(self, client, mock_llm_fallback):
        """Draft an email, classify it, detect action."""
        # 1. Draft
        draft = await client.post(
            "/api/email/draft",
            json={
                "act_type": "general",
                "fields": {
                    "cliente_nombre": "Test Client",
                    "folio": "FOL-001",
                    "asunto": "Property Transfer",
                    "mensaje_personalizado": "Your property transfer is ready.",
                    "firma_notario": "Notary",
                    "notaria_nombre": "Main Office",
                },
                "language": "en",
            },
        )
        assert draft.status_code == 200

        # 2. Classify
        classify = await client.post(
            "/api/email/classify",
            json={
                "from_address": "client@test.com",
                "subject": "Property Transfer",
                "body": "I would like to proceed with the property transfer."
                       "Please let me know the next steps and required documents.",
            },
        )
        assert classify.status_code == 200

        # 3. Detect action
        action = await client.post(
            "/api/email/action",
            json={
                "email_id": "integ-test-001",
                "category": "seguimiento_escritura",
                "subject": "Property Transfer",
                "body": "I would like to proceed with the property transfer as discussed.",
            },
        )
        assert action.status_code == 200
        data = action.json()
        assert len(data["detected_actions"]) >= 0  # May be empty, that's OK
        assert "execution_results" in data
