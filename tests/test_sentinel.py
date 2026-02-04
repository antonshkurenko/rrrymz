"""Tests for Stage 2: Sentinel."""

from curator.models import DiscoveryCandidate, ScoutOutput, UserPersona
from curator.stages.sentinel import Sentinel


def test_sentinel_filters_muted(mock_client, sample_settings):
    persona = UserPersona(
        interests=["AI"],
        muted_topics=["Celebrity gossip"],
    )
    candidates = [
        DiscoveryCandidate(
            title="Celebrity gossip update",
            url="https://example.com/celeb",
            snippet="Celebrity news",
        ),
        DiscoveryCandidate(
            title="AI Research Paper",
            url="https://example.com/ai",
            snippet="New AI research",
        ),
    ]
    scout_output = ScoutOutput(candidates=candidates)

    # Gemini returns high relevance for the remaining candidate
    mock_client.set_responses([{"scores": [0.9]}])

    sentinel = Sentinel(mock_client, sample_settings)
    result = sentinel.run(scout_output, persona)

    assert len(result.passed) == 1
    assert result.passed[0].title == "AI Research Paper"
    assert result.filtered_count == 1


def test_sentinel_filters_snoozed(mock_client, sample_settings):
    persona = UserPersona(
        interests=["Crypto"],
        active_snoozes={"Bitcoin ETF": "2099-12-31"},
    )
    candidates = [
        DiscoveryCandidate(
            title="Bitcoin ETF approved",
            url="https://example.com/btc",
            snippet="Bitcoin ETF gets approval",
        ),
    ]
    scout_output = ScoutOutput(candidates=candidates)

    sentinel = Sentinel(mock_client, sample_settings)
    result = sentinel.run(scout_output, persona)

    assert len(result.passed) == 0
    assert result.filtered_count == 1
    assert result.api_calls == 0  # No Gemini call needed


def test_sentinel_relevance_threshold(mock_client, sample_settings):
    persona = UserPersona(interests=["AI"])
    candidates = [
        DiscoveryCandidate(title="AI Story", url="https://a.com", snippet="AI"),
        DiscoveryCandidate(title="Cooking Tips", url="https://b.com", snippet="Cooking"),
    ]
    scout_output = ScoutOutput(candidates=candidates)

    mock_client.set_responses([{"scores": [0.9, 0.2]}])

    sentinel = Sentinel(mock_client, sample_settings)
    result = sentinel.run(scout_output, persona)

    assert len(result.passed) == 1
    assert result.passed[0].title == "AI Story"


def test_sentinel_empty_input(mock_client, sample_settings):
    persona = UserPersona(interests=["AI"])
    scout_output = ScoutOutput(candidates=[])

    sentinel = Sentinel(mock_client, sample_settings)
    result = sentinel.run(scout_output, persona)

    assert len(result.passed) == 0
    assert result.api_calls == 0
