"""Tests for Stage 1: Polyglot Scout."""

from unittest.mock import patch

from curator.config import Settings
from curator.models import ScoutOutput
from curator.stages.scout import PolyglotScout, _compute_since


def _patch_sources():
    """Patch external sources to return empty lists, isolating Gemini grounding tests."""
    return (
        patch("curator.stages.scout.fetch_google_news", return_value=[]),
        patch("curator.stages.scout.fetch_duckduckgo_news", return_value=[]),
        patch("curator.stages.scout.load_feed_urls", return_value=[]),
    )


def test_scout_basic(mock_client, sample_settings, sample_persona):
    mock_client.set_responses(
        [
            {
                "candidates": [
                    {
                        "title": "AI Breakthrough",
                        "url": "https://example.com/ai",
                        "snippet": "Big AI news.",
                        "source_language": "en",
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "title": "Space Discovery",
                        "url": "https://example.com/space",
                        "snippet": "New space finding.",
                        "source_language": "en",
                    }
                ]
            },
        ]
    )

    settings = Settings(
        gemini_api_key="test",
        model_id="test",
        scout_languages=["en"],
        memory_path=sample_settings.memory_path,
        history_path=sample_settings.history_path,
        output_path=sample_settings.output_path,
    )
    scout = PolyglotScout(mock_client, settings)

    p1, p2, p3 = _patch_sources()
    with p1, p2, p3:
        result = scout.run(sample_persona)

    assert isinstance(result, ScoutOutput)
    assert len(result.candidates) == 2
    assert result.api_calls == 2


def test_scout_deduplicates_urls(mock_client, sample_settings, sample_persona):
    """Same URL returned for different queries should be deduped."""
    mock_client.set_responses(
        [
            {
                "candidates": [
                    {
                        "title": "Story A",
                        "url": "https://example.com/same",
                        "snippet": "A",
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "title": "Story B",
                        "url": "https://example.com/same",
                        "snippet": "B",
                    }
                ]
            },
        ]
    )

    settings = Settings(
        gemini_api_key="test",
        model_id="test",
        scout_languages=["en"],
        memory_path=sample_settings.memory_path,
        history_path=sample_settings.history_path,
        output_path=sample_settings.output_path,
    )
    scout = PolyglotScout(mock_client, settings)

    p1, p2, p3 = _patch_sources()
    with p1, p2, p3:
        result = scout.run(sample_persona)

    assert len(result.candidates) == 1


def test_scout_handles_failure(mock_client, sample_settings, sample_persona):
    """Scout should handle Gemini failures gracefully."""

    def failing_generate(*args, **kwargs):
        mock_client.call_count += 1
        raise RuntimeError("API Error")

    mock_client.generate = failing_generate

    settings = Settings(
        gemini_api_key="test",
        model_id="test",
        scout_languages=["en"],
        memory_path=sample_settings.memory_path,
        history_path=sample_settings.history_path,
        output_path=sample_settings.output_path,
    )
    scout = PolyglotScout(mock_client, settings)

    p1, p2, p3 = _patch_sources()
    with p1, p2, p3:
        result = scout.run(sample_persona)

    assert isinstance(result, ScoutOutput)
    assert len(result.candidates) == 0


def test_scout_aggregates_all_sources(mock_client, sample_settings, sample_persona):
    """Scout should merge candidates from all sources."""
    from curator.models import DiscoveryCandidate

    google_candidates = [
        DiscoveryCandidate(title="Google Story", url="https://google.com/1", snippet="G"),
    ]
    ddg_candidates = [
        DiscoveryCandidate(title="DDG Story", url="https://ddg.com/1", snippet="D"),
    ]

    # Gemini returns one candidate too
    mock_client.set_responses(
        [
            {
                "candidates": [
                    {
                        "title": "Gemini Story",
                        "url": "https://gemini.com/1",
                        "snippet": "Gem",
                    }
                ]
            },
            {
                "candidates": [
                    {
                        "title": "Gemini Story 2",
                        "url": "https://gemini.com/2",
                        "snippet": "Gem2",
                    }
                ]
            },
        ]
    )

    settings = Settings(
        gemini_api_key="test",
        model_id="test",
        scout_languages=["en"],
        memory_path=sample_settings.memory_path,
        history_path=sample_settings.history_path,
        output_path=sample_settings.output_path,
    )
    scout = PolyglotScout(mock_client, settings)

    with (
        patch("curator.stages.scout.fetch_google_news", return_value=google_candidates),
        patch("curator.stages.scout.fetch_duckduckgo_news", return_value=ddg_candidates),
        patch("curator.stages.scout.load_feed_urls", return_value=[]),
    ):
        result = scout.run(sample_persona)

    # 1 Google + 1 DDG + 2 Gemini = 4 (×2 interests for Google/DDG, but deduped by URL)
    urls = {c.url for c in result.candidates}
    assert "https://google.com/1" in urls
    assert "https://ddg.com/1" in urls
    assert "https://gemini.com/1" in urls


def test_scout_deduplicates_across_sources(mock_client, sample_settings, sample_persona):
    """Same URL from different sources should be deduped."""
    from curator.models import DiscoveryCandidate

    google_candidates = [
        DiscoveryCandidate(title="Same Story", url="https://example.com/same", snippet="G"),
    ]
    ddg_candidates = [
        DiscoveryCandidate(title="Same Story DDG", url="https://example.com/same", snippet="D"),
    ]

    mock_client.set_responses([{"candidates": []}] * 2)

    settings = Settings(
        gemini_api_key="test",
        model_id="test",
        scout_languages=["en"],
        memory_path=sample_settings.memory_path,
        history_path=sample_settings.history_path,
        output_path=sample_settings.output_path,
    )
    scout = PolyglotScout(mock_client, settings)

    with (
        patch("curator.stages.scout.fetch_google_news", return_value=google_candidates),
        patch("curator.stages.scout.fetch_duckduckgo_news", return_value=ddg_candidates),
        patch("curator.stages.scout.load_feed_urls", return_value=[]),
    ):
        result = scout.run(sample_persona)

    # Same URL should appear only once
    urls = [c.url for c in result.candidates if c.url == "https://example.com/same"]
    assert len(urls) == 1


def test_compute_since_with_date():
    from datetime import timezone

    result = _compute_since("2026-02-01", 48)
    assert result.year == 2026
    assert result.month == 2
    assert result.day == 1
    assert result.tzinfo == timezone.utc


def test_compute_since_without_date():
    result = _compute_since(None, 48)
    assert result.tzinfo is not None


def test_compute_since_with_invalid_date():
    result = _compute_since("not-a-date", 48)
    assert result.tzinfo is not None
