"""
Tests básicos del pipeline RAG y agentes.
"""

import pytest


@pytest.mark.asyncio
async def test_chunk_by_sections():
    """Test que el chunking divide correctamente."""
    from app.rag.chunker import chunk_by_sections

    text = """Artículo 1. Del objeto del contrato.
El presente contrato tiene por objeto...

Artículo 2. Del plazo.
El plazo del presente contrato es de 90 días.

Artículo 3. Del precio.
El precio total es de $10,000."""

    chunks = chunk_by_sections(text)
    assert len(chunks) >= 1
    assert all(isinstance(c, tuple) for c in chunks)
    assert all(len(c[0]) > 0 for c in chunks)


@pytest.mark.asyncio
async def test_embeddings_provider():
    """Test que el proveedor de embeddings funciona."""
    from app.rag.embeddings import embeddings_provider

    texts = ["Este es un texto de prueba legal", "Cláusula de confidencialidad"]
    embeddings = await embeddings_provider.embed_texts(texts)

    assert len(embeddings) == 2
    assert all(len(e) > 0 for e in embeddings)


@pytest.mark.asyncio
async def test_vector_store_index_and_search():
    """Test que el vector store indexa y busca."""
    from app.rag.retriever import vector_store

    doc_id = "test-doc-1"
    chunks = [
        "El contrato establece un plazo de 90 días.",
        "Las partes acuerdan un precio de $10,000.",
        "La confidencialidad se mantiene por 2 años.",
    ]

    num = await vector_store.index_document(doc_id, chunks)
    assert num == 3

    results = await vector_store.search("plazo del contrato", document_id=doc_id)
    assert len(results) > 0
    assert "plazo" in results[0]["text"].lower()


@pytest.mark.asyncio
async def test_document_parser_txt(tmp_path):
    """Test del parser de TXT."""
    from app.ingestion.parser import parser

    test_file = tmp_path / "test.txt"
    test_file.write_text("Este es un documento de prueba legal.\n\nArtículo 1.")

    text = await parser.parse(str(test_file))
    assert "documento de prueba" in text


@pytest.mark.asyncio
async def test_analyze_agent():
    """Test del agente de análisis (usando mock)."""
    from app.agents.analyzer import analyze_document

    doc_text = "Contrato de prestación de servicios entre Juan Pérez y Empresa XYZ."

    analysis = await analyze_document(doc_text)
    assert analysis is not None
    assert hasattr(analysis, "document_type")
    assert hasattr(analysis, "summary")
