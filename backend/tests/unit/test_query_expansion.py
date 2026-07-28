"""Unit tests for query_expansion.py — LLM-based query expansion.

Tests _parse_json_list with mock data and expand_query error handling.
"""

import pytest


class TestParseJsonList:
    """Tests for _parse_json_list(text) — the JSON parser from LLM output."""

    def test_valid_json_array(self):
        """Valid JSON array is parsed correctly."""
        from app.rag.query_expansion import _parse_json_list
        result = _parse_json_list('["rupture contrat", "résiliation convention"]')
        assert result == ["rupture contrat", "résiliation convention"]

    def test_json_with_prefix_text(self):
        """JSON array embedded in text is extracted."""
        from app.rag.query_expansion import _parse_json_list
        result = _parse_json_list(
            'Here are some variants: ["contrat résiliation", "fin de contrat"]'
        )
        assert "contrat résiliation" in result
        assert "fin de contrat" in result

    def test_empty_brackets(self):
        """Empty JSON array returns empty list."""
        from app.rag.query_expansion import _parse_json_list
        assert _parse_json_list("[]") == []

    def test_non_json_response(self):
        """Non-JSON response falls back to line-by-line extraction."""
        from app.rag.query_expansion import _parse_json_list
        result = _parse_json_list("variant 1\nvariant 2\nvariant 3")
        assert len(result) >= 2

    def test_single_item(self):
        """Single item in array."""
        from app.rag.query_expansion import _parse_json_list
        result = _parse_json_list('["only one variant"]')
        assert result == ["only one variant"]

    def test_json_with_trailing_text(self):
        """JSON array followed by text."""
        from app.rag.query_expansion import _parse_json_list
        result = _parse_json_list('["var1", "var2"] and some explanation')
        assert result == ["var1", "var2"]

    def test_invalid_json(self):
        """Invalid input returns empty list."""
        from app.rag.query_expansion import _parse_json_list
        assert _parse_json_list("not even close to json") == []
        assert _parse_json_list("{broken") == []

    def test_unicode_in_variants(self):
        """Unicode characters in variants."""
        from app.rag.query_expansion import _parse_json_list
        result = _parse_json_list('["cláusula de rescisión", "résiliation contrat"]')
        assert len(result) == 2


class TestExpandQuery:
    """Tests for expand_query(query). Uses mock to avoid real LLM calls."""

    @pytest.mark.asyncio
    async def test_empty_query_returns_empty(self):
        """Empty query returns empty list without calling LLM."""
        from app.rag.query_expansion import expand_query
        assert await expand_query("") == []
        assert await expand_query("   ") == []

    @pytest.mark.asyncio
    async def test_llm_error_returns_empty(self, monkeypatch):
        """LLM failure returns empty list (graceful degradation)."""
        async def _mock_fail(*args, **kwargs):
            raise RuntimeError("LLM unavailable")
        monkeypatch.setattr("app.core.llm.llm_complete", _mock_fail)

        from app.rag.query_expansion import expand_query
        result = await expand_query("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_mocked_response(self, monkeypatch):
        """With mocked LLM, returns parsed variants."""
        async def _mock_llm(*args, **kwargs):
            return '["variant one", "variant two"]'
        monkeypatch.setattr("app.core.llm.llm_complete", _mock_llm)

        from app.rag.query_expansion import expand_query
        result = await expand_query("test query")
        assert len(result) == 2
        assert "variant one" in result

    @pytest.mark.asyncio
    async def test_empty_llm_response(self, monkeypatch):
        """Empty LLM response returns empty list."""
        async def _mock_llm(*args, **kwargs):
            return "[]"
        monkeypatch.setattr("app.core.llm.llm_complete", _mock_llm)

        from app.rag.query_expansion import expand_query
        result = await expand_query("test query")
        assert result == []

    @pytest.mark.asyncio
    async def test_num_expansions_clamped(self, monkeypatch):
        """num_expansions is clamped to [1, 4]."""
        async def _mock_llm(*args, **kwargs):
            return '["a", "b", "c", "d", "e"]'
        monkeypatch.setattr("app.core.llm.llm_complete", _mock_llm)

        from app.rag.query_expansion import expand_query
        # Should pass num=4 (clamped from 10)
        result = await expand_query("test query", num_expansions=10)
        # The mock returns 5 items but we only expect up to 4
        assert len(result) <= 4
