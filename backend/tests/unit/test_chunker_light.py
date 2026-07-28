"""Lightweight unit tests for chunker.py — pure functions only, no fixtures."""

from app.rag.chunker import chunk_by_sections, chunk_with_metadata


class TestChunkBySections:
    def test_empty_returns_empty(self):
        assert chunk_by_sections("") == []
        assert chunk_by_sections("   ") == []

    def test_short_single_chunk(self):
        chunks = chunk_by_sections("Bonjour ceci est un test.")
        assert len(chunks) == 1
        assert isinstance(chunks[0], tuple)
        assert len(chunks[0]) == 2
        assert isinstance(chunks[0][0], str)
        assert isinstance(chunks[0][1], int)

    def test_french_chapters(self):
        text = (
            "CHAPITRE PREMIER\n"
            "Le bien est situé à Paris, au 123 rue de la Paix, dans le "
            "huitième arrondissement. Il s'agit d'un appartement de type "
            "trois pièces comprenant salon, cuisine équipée et deux chambres.\n\n"
            "CHAPITRE II\n"
            "Le prix de vente est fixé à 350 000 euros. Cette somme sera "
            "payée par l'acquéreur au vendeur selon les modalités prévues "
            "à l'acte authentique de vente."
        )
        chunks = chunk_by_sections(text)
        assert len(chunks) >= 2

    def test_french_articles(self):
        text = (
            "Article 1er\n"
            "La nature du bien est un bien immobilier situé en zone urbaine, "
            "comprenant une maison individuelle avec jardin et garage. Le "
            "bien est libre de toute hypothèque et servitude. Le bien est "
            "décrit dans son état actuel et le vendeur déclare n'avoir "
            "effectué aucun travaux modifiant sa structure depuis son "
            "acquisition. L'acquéreur reconnaît avoir visité les lieux.\n\n"
            "Article 2\n"
            "Le droit de propriété est transféré à l'acquéreur à compter de "
            "la date de signature de l'acte authentique devant le notaire. "
            "Le transfert comprend tous les droits réels et personnels "
            "attachés au bien. Le vendeur garantit l'acquéreur contre "
            "toutes les conséquences de l'éviction et contre les vices "
            "cachés conformément à la législation en vigueur."
        )
        chunks = chunk_by_sections(text)
        assert len(chunks) >= 2

    def test_spanish_fallback(self):
        text = (
            "Artículo 1. Del objeto.\n"
            "El presente contrato tiene por objeto la compraventa de las "
            "participaciones sociales de la sociedad mercantil indicada en "
            "el exponendo primero de este documento. La transmisión se "
            "realiza por un precio cierto y determinado que las partes "
            "declaran conocer y aceptar. El vendedor garantiza que las "
            "participaciones están libres de cargas y gravámenes.\n\n"
            "Artículo 2. Del plazo.\n"
            "El plazo de duración del presente contrato será de noventa días "
            "hábiles contados desde la fecha de su firma, prorrogables por "
            "acuerdo expreso de ambas partes. Durante este plazo, el "
            "comprador podrá realizar todas las verificaciones que "
            "considere oportunas sobre la situación de la sociedad."
        )
        chunks = chunk_by_sections(text)
        assert len(chunks) >= 2

    def test_legal_patterns(self):
        for header in [
            "CONSIDÉRANT que les parties sont d'accord.",
            "ENTRE LES SOUSSIGNÉS : Monsieur X.",
            "FAIT à Paris, le 15 janvier 2026",
        ]:
            chunks = chunk_by_sections(header)
            assert len(chunks) >= 1

    def test_output_format(self):
        chunks = chunk_by_sections("Just a single paragraph of text for testing.")
        for c in chunks:
            assert isinstance(c, tuple)
            assert len(c) == 2
            assert isinstance(c[0], str)
            assert isinstance(c[1], int)


class TestChunkWithMetadata:
    def test_returns_dicts(self):
        result = chunk_with_metadata("Some text.")
        assert isinstance(result, list)
        for r in result:
            assert "text" in r
            assert "index" in r
            assert "section" in r
            assert "start_char" in r
            assert "end_char" in r

    def test_empty(self):
        assert chunk_with_metadata("") == []
