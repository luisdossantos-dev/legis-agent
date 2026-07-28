"""Lightweight tests for query_expansion parser — pure function only."""

from app.rag.query_expansion import _parse_json_list


class TestParseJsonList:
    def test_valid_json_array(self):
        assert _parse_json_list('["a", "b"]') == ["a", "b"]

    def test_with_prefix_text(self):
        r = _parse_json_list('Variants: ["x", "y"]')
        assert r == ["x", "y"]

    def test_empty_brackets(self):
        assert _parse_json_list("[]") == []

    def test_non_json_fallback(self):
        r = _parse_json_list("line1\nline2\nline3")
        assert len(r) >= 2

    def test_single_item(self):
        assert _parse_json_list('["only"]') == ["only"]

    def test_invalid_returns_empty(self):
        assert _parse_json_list("not json") == []
        assert _parse_json_list("{broken") == []

    def test_unicode(self):
        r = _parse_json_list('["cláusula", "résiliation"]')
        assert len(r) == 2

    def test_llm_prefixed_response(self):
        r = _parse_json_list('Here are variants: ["var1", "var2"] and more text')
        assert "var1" in r
        assert "var2" in r
