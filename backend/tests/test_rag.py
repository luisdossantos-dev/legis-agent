"""
Tests livianos del pipeline RAG.
Solo prueba funciones puras (chunker) sin dependencias externas.
"""

import pytest


@pytest.mark.asyncio
async def test_chunk_by_sections():
    """Test que chunk_by_sections divide correctamente texto legal."""
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
async def test_chunk_empty_text():
    """Test que chunk_by_sections maneja texto vacío."""
    from app.rag.chunker import chunk_by_sections

    chunks = chunk_by_sections("")
    assert isinstance(chunks, list)


@pytest.mark.asyncio
async def test_chunk_single_line():
    """Test que chunk_by_sections maneja texto sin secciones."""
    from app.rag.chunker import chunk_by_sections

    chunks = chunk_by_sections("Texto simple sin secciones.")
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_chunk_unicode():
    """Test que chunk_by_sections maneja Unicode."""
    from app.rag.chunker import chunk_by_sections

    chunks = chunk_by_sections("Artículo 1. ñoño — €100 «test» 🎉")
    assert len(chunks) >= 1
    assert any("ñoño" in c[0] for c in chunks)
