"""
Integration tests for the document flow: upload, list, and retrieval.

Covers the full CRUD surface of the documents API:
  POST   /api/v1/documents/upload
  GET    /api/v1/documents/
  GET    /api/v1/documents/{doc_id}
"""

import pytest


@pytest.mark.asyncio
class TestDocumentUpload:
    """Tests for document upload endpoint."""

    async def test_upload_txt_success(self, client, sample_txt):
        """Upload a TXT file and verify response has id, filename, status."""
        with open(sample_txt, "rb") as f:
            resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("test_doc.txt", f, "text/plain")},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["filename"] == "test_doc.txt"
        assert "status" in data

    async def test_upload_without_file_returns_422(self, client):
        """POST without file returns 422."""
        resp = await client.post("/api/v1/documents/upload")
        assert resp.status_code == 422

    async def test_upload_invalid_extension(self, client):
        """Upload .jpg returns 400."""
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.jpg", b"fake-image-content", "image/jpeg")},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    async def test_upload_empty_filename(self, client):
        """Empty filename returns 422 — httpx omits the filename param from
        Content-Disposition, so FastAPI sees no file and returns 422."""
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("", b"some content", "text/plain")},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestDocumentList:
    """Tests for document listing."""

    async def test_list_empty(self, client):
        """Empty store returns empty list."""
        from app.services.document_service import _documents_store

        _documents_store.clear()
        resp = await client.get("/api/v1/documents/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["documents"] == []
        assert data["total"] == 0

    async def test_list_after_upload(self, client, sample_txt):
        """After uploading, list contains the document."""
        with open(sample_txt, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("list_test.txt", f, "text/plain")},
            )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["id"]

        list_resp = await client.get("/api/v1/documents/")
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "documents" in data
        assert "total" in data
        doc_ids = [d["id"] for d in data["documents"]]
        assert doc_id in doc_ids

    async def test_list_pagination(self, client, tmp_path):
        """limit and offset params work."""
        from app.services.document_service import _documents_store

        _documents_store.clear()

        # Upload 3 documents
        ids = []
        for i in range(3):
            p = tmp_path / f"page_doc_{i}.txt"
            p.write_text(f"Pagination test document number {i}.")
            with open(p, "rb") as f:
                resp = await client.post(
                    "/api/v1/documents/upload",
                    files={"file": (p.name, f, "text/plain")},
                )
            assert resp.status_code == 200
            ids.append(resp.json()["id"])

        # limit=2 should cap the result set
        resp = await client.get("/api/v1/documents/?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["documents"]) == 2
        assert data["total"] == 3

        # offset=2 should skip the first 2, returning 1
        resp = await client.get("/api/v1/documents/?offset=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["documents"]) == 1
        assert data["total"] == 3

        # offset beyond total should return 0
        resp = await client.get("/api/v1/documents/?offset=100")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["documents"]) == 0
        assert data["total"] == 3


@pytest.mark.asyncio
class TestDocumentGet:
    """Tests for getting document by ID."""

    async def test_get_existing_document(self, client, sample_txt):
        """Get by ID returns document."""
        with open(sample_txt, "rb") as f:
            upload_resp = await client.post(
                "/api/v1/documents/upload",
                files={"file": ("get_test.txt", f, "text/plain")},
            )
        assert upload_resp.status_code == 200
        doc_id = upload_resp.json()["id"]

        resp = await client.get(f"/api/v1/documents/{doc_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == doc_id
        assert data["filename"] == "get_test.txt"
        assert "text" in data
        assert "status" in data

    async def test_get_nonexistent_document_returns_404(self, client):
        """Invalid ID returns 404."""
        resp = await client.get(
            "/api/v1/documents/00000000-0000-0000-0000-000000000000"
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_get_invalid_id_format(self, client):
        """Non-UUID ID returns 400."""
        resp = await client.get("/api/v1/documents/not-a-valid-uuid")
        assert resp.status_code == 400
        assert "Invalid" in resp.json()["detail"]


@pytest.mark.asyncio
class TestDocumentUploadEdgeCases:
    """Edge cases for document upload."""

    async def test_upload_empty_file(self, client):
        """Empty file content returns 400."""
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400
        assert "empty" in resp.json()["detail"].lower()

    async def test_upload_very_long_filename(self, client):
        """Filename > 255 chars returns 400."""
        long_name = "a" * 256 + ".txt"
        resp = await client.post(
            "/api/v1/documents/upload",
            files={"file": (long_name, b"content", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Filename" in resp.json()["detail"]
