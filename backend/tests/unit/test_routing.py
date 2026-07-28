"""Unit tests for routing.py — auto-select profile logic and profile constants."""

import pytest
from app.core.routing import auto_select_profile, ALL_PROFILES


class TestAutoSelectProfile:
    """Tests for auto_select_profile()."""

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _make_messages(content: str = "Hello") -> list:
        return [{"role": "user", "content": content}]

    # ── Single-criterion tests ────────────────────────────────────

    def test_french_language_returns_french_profile(self, monkeypatch):
        """language='fr' should return 'french'."""
        monkeypatch.setattr("app.core.routing._profile_available", lambda p: True)
        result = auto_select_profile(
            messages=self._make_messages("Bonjour"),
            language="fr",
        )
        assert result == "french"

    def test_private_sensitivity_returns_private_profile(self, monkeypatch):
        """sensitivity='private' should return 'private'."""
        monkeypatch.setattr("app.core.routing._profile_available", lambda p: True)
        result = auto_select_profile(
            messages=self._make_messages(),
            sensitivity="private",
        )
        assert result == "private"

    def test_urgent_returns_fast(self, monkeypatch):
        """urgent=True should return 'fast'."""
        monkeypatch.setattr("app.core.routing._profile_available", lambda p: True)
        result = auto_select_profile(
            messages=self._make_messages(),
            urgent=True,
        )
        assert result == "fast"

    def test_prefer_cheap_returns_cheap(self, monkeypatch):
        """prefer_cheap=True should return 'cheap'."""
        monkeypatch.setattr("app.core.routing._profile_available", lambda p: True)
        result = auto_select_profile(
            messages=self._make_messages(),
            prefer_cheap=True,
        )
        assert result == "cheap"

    # ── Priority / tie-breaking tests ─────────────────────────────

    def test_french_takes_priority(self, monkeypatch):
        """language='fr' returns 'french' even when urgent=True
        if the fast profile is not available."""
        monkeypatch.setattr(
            "app.core.routing._profile_available",
            lambda p: p != "fast",
        )
        result = auto_select_profile(
            messages=self._make_messages("Bonjour"),
            language="fr",
            urgent=True,
        )
        assert result == "french"

    def test_private_takes_priority(self, monkeypatch):
        """sensitivity='private' should win over prefer_cheap=True."""
        monkeypatch.setattr("app.core.routing._profile_available", lambda p: True)
        result = auto_select_profile(
            messages=self._make_messages(),
            sensitivity="private",
            prefer_cheap=True,
        )
        assert result == "private"


class TestAllProfiles:
    """Tests for the ALL_PROFILES constant."""

    def test_all_profiles_contains_expected(self):
        """ALL_PROFILES should contain all seven expected profile names."""
        expected = {
            "reasoning",
            "structured",
            "fast",
            "cheap",
            "private",
            "french",
            "fallback",
        }
        assert set(ALL_PROFILES) == expected

    def test_all_profiles_unique(self):
        """ALL_PROFILES should not contain duplicates."""
        assert len(ALL_PROFILES) == len(set(ALL_PROFILES))
