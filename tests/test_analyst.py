"""Tests for Stage 4: Technical Analyst."""

from unittest.mock import patch

from curator.models import ArchitectOutput, EventCluster, FilteredCandidate
from curator.stages.analyst import TechnicalAnalyst
from curator.stages.architect import compute_cluster_id


def _make_cluster(url: str = "https://example.com/article") -> EventCluster:
    candidate = FilteredCandidate(
        title="Test Article",
        url=url,
        snippet="An important test article about technology.",
    )
    return EventCluster(
        cluster_id=compute_cluster_id([url]),
        label="Test Event",
        candidates=[candidate],
        best_url=url,
    )


def test_analyst_with_scraped_content(mock_client):
    cluster = _make_cluster()
    architect_output = ArchitectOutput(clusters=[cluster])

    mock_client.set_responses(
        [
            {
                "knowledge_depth": 7,
                "key_facts": ["Fact 1", "Fact 2"],
                "claims_verified": True,
            }
        ]
    )

    with patch("curator.stages.analyst._scrape_url") as mock_scrape:
        mock_scrape.return_value = "Full article text about technology advances..."

        analyst = TechnicalAnalyst(mock_client)
        result = analyst.run(architect_output)

    assert len(result.analyses) == 1
    analysis = result.analyses[0]
    assert analysis.knowledge_depth == 7
    assert len(analysis.key_facts) == 2
    assert analysis.claims_verified is True
    assert analysis.scrape_failed is False


def test_analyst_scrape_failure_uses_snippets(mock_client):
    cluster = _make_cluster()
    architect_output = ArchitectOutput(clusters=[cluster])

    mock_client.set_responses(
        [
            {
                "knowledge_depth": 3,
                "key_facts": ["Limited fact"],
                "claims_verified": False,
            }
        ]
    )

    with patch("curator.stages.analyst._scrape_url") as mock_scrape:
        mock_scrape.return_value = None

        analyst = TechnicalAnalyst(mock_client)
        result = analyst.run(architect_output)

    assert len(result.analyses) == 1
    assert result.analyses[0].scrape_failed is True


def test_analyst_empty_input(mock_client):
    architect_output = ArchitectOutput(clusters=[])
    analyst = TechnicalAnalyst(mock_client)
    result = analyst.run(architect_output)

    assert len(result.analyses) == 0
    assert result.api_calls == 0
