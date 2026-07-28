"""Unit tests for chunker.py — French notarial semantic chunking."""

import pytest


class TestChunkBySections:
    """Tests for chunk_by_sections(text)."""

    def test_empty_text(self):
        """Empty text returns empty list."""
        from app.rag.chunker import chunk_by_sections
        assert chunk_by_sections("") == []
        assert chunk_by_sections("   ") == []

    def test_short_text_single_chunk(self):
        """Short text returns single chunk."""
        from app.rag.chunker import chunk_by_sections
        chunks = chunk_by_sections("Bonjour ceci est un test.")
        assert len(chunks) == 1
        assert "Bonjour" in chunks[0][0]

    def test_french_notarial_structure(self):
        """French notarial text with chapters produces multiple chunks."""
        from app.rag.chunker import chunk_by_sections
        text = """ACTE DE VENTE

CHAPITRE PREMIER — DÉSIGNATION DU BIEN
Le bien est situé au 15 rue de la Paix.

Article 1er — Nature du bien
Un appartement de 85 m².

CHAPITRE II — PRIX
Le prix est de 350 000 euros.

FAIT à Paris, le 15 janvier 2026
"""
        chunks = chunk_by_sections(text)
        assert len(chunks) >= 2
        # Verify tuple format: (text, index)
        for chunk in chunks:
            assert isinstance(chunk, tuple)
            assert len(chunk) == 2
            assert isinstance(chunk[0], str)
            assert isinstance(chunk[1], int)

    def test_section_context_preserved(self):
        """Section headers are carried into chunks as context."""
        from app.rag.chunker import chunk_by_sections
        text = """CHAPITRE III — CONDITIONS SUSPENSIVES
La condition suspensive est standard.

Article 5 — Obtention du prêt
Le prêt doit être obtenu dans 45 jours.
"""
        chunks = chunk_by_sections(text)
        # At least one chunk should reference the chapter
        chapter_found = any("CHAPITRE" in c[0] for c in chunks)
        article_found = any("Article 5" in c[0] for c in chunks)
        assert chapter_found or article_found

    def test_french_legal_patterns(self):
        """Various French legal headers are detected."""
        from app.rag.chunker import chunk_by_sections

        headers = [
            "CONSIDÉRANT que les parties sont d'accord.",
            "ENTRE LES SOUSSIGNÉS : Monsieur X.",
            "FAIT à Paris, le 15 janvier 2026",
            "CLause première — Définitions",
            "CHAPITRE UNIQUE — Dispositions générales",
        ]
        for header in headers:
            chunks = chunk_by_sections(header)
            assert len(chunks) >= 1
            assert chunks[0][0]

    def test_spanish_fallback(self):
        """Spanish patterns still work as fallback."""
        from app.rag.chunker import chunk_by_sections
        text = """Artículo 1. Del objeto.
El presente contrato tiene por objeto la compraventa de las participaciones
sociales de la sociedad mercantil, que se regirá por las disposiciones
siguientes y por el código de comercio vigente en la materia. Las partes
declaran su voluntad de obligarse en los términos y condiciones establecidos
en las cláusulas siguientes, las cuales han sido libremente negociadas.

Artículo 2. Del plazo.
El plazo de duración del presente contrato será de noventa días hábiles
contados desde la fecha de su firma, prorrogables por acuerdo expreso de
ambas partes mediante comunicación escrita. Vencido el plazo sin prórroga,
el contrato se extinguirá automáticamente sin necesidad de requerimiento
alguno por ninguna de las partes intervinientes en este acto."""
        chunks = chunk_by_sections(text)
        assert len(chunks) >= 2

    def test_no_section_headers(self):
        """Text without section headers uses paragraph splitting."""
        from app.rag.chunker import chunk_by_sections
        long_text = "Paragraph one.\n\nParagraph two.\n\nParagraph three.\n\nParagraph four.\n\n" * 50
        chunks = chunk_by_sections(long_text, min_chunk_size=100)
        assert len(chunks) >= 2

    def test_output_format(self):
        """Output is list of (text, index) tuples."""
        from app.rag.chunker import chunk_by_sections
        text = "TEST\n\nCHAPITRE PREMIER\nBody text here."
        chunks = chunk_by_sections(text)
        for c in chunks:
            assert isinstance(c, tuple)
            assert len(c) == 2
            assert isinstance(c[0], str)
            assert isinstance(c[1], int)

    def test_chunk_metadata(self):
        """chunk_with_metadata returns dicts with section info."""
        from app.rag.chunker import chunk_with_metadata
        text = """CHAPITRE PREMIER
Body of chapter one."""
        result = chunk_with_metadata(text)
        assert isinstance(result, list)
        for r in result:
            assert "text" in r
            assert "index" in r
            assert "section" in r
            assert "start_char" in r
            assert "end_char" in r
