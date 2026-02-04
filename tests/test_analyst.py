"""Tests for Stage 4: Technical Analyst (batched)."""

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

    # New batched response format
    mock_client.set_responses(
        [
            {
                "analyses": [
                    {
                        "cluster_id": cluster.cluster_id,
                        "knowledge_depth": 7,
                        "key_facts": ["Fact 1", "Fact 2"],
                        "claims_verified": True,
                    }
                ]
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
    assert result.api_calls == 1  # Single batched call


def test_analyst_scrape_failure_uses_snippets(mock_client):
    cluster = _make_cluster()
    architect_output = ArchitectOutput(clusters=[cluster])

    mock_client.set_responses(
        [
            {
                "analyses": [
                    {
                        "cluster_id": cluster.cluster_id,
                        "knowledge_depth": 3,
                        "key_facts": ["Limited fact"],
                        "claims_verified": False,
                    }
                ]
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


def test_analyst_multiple_clusters_batched(mock_client):
    """Test that multiple clusters are analyzed in a single API call."""
    cluster1 = _make_cluster("https://example.com/article1")
    cluster2 = _make_cluster("https://example.com/article2")
    architect_output = ArchitectOutput(clusters=[cluster1, cluster2])

    mock_client.set_responses(
        [
            {
                "analyses": [
                    {
                        "cluster_id": cluster1.cluster_id,
                        "knowledge_depth": 8,
                        "key_facts": ["Fact A"],
                        "claims_verified": True,
                    },
                    {
                        "cluster_id": cluster2.cluster_id,
                        "knowledge_depth": 6,
                        "key_facts": ["Fact B"],
                        "claims_verified": False,
                    },
                ]
            }
        ]
    )

    with patch("curator.stages.analyst._scrape_url") as mock_scrape:
        mock_scrape.return_value = "Article content..."

        analyst = TechnicalAnalyst(mock_client)
        result = analyst.run(architect_output)

    assert len(result.analyses) == 2
    assert result.api_calls == 1  # Single batched call for both clusters
    assert result.analyses[0].knowledge_depth == 8
    assert result.analyses[1].knowledge_depth == 6
