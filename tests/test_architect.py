"""Tests for Stage 3: Architect."""

from curator.models import FilteredCandidate, HistoryEntry, SentinelOutput
from curator.stages.architect import Architect, compute_cluster_id


def test_compute_cluster_id():
    urls = ["https://b.com", "https://a.com"]
    cid = compute_cluster_id(urls)
    assert len(cid) == 16
    # Deterministic
    assert cid == compute_cluster_id(["https://a.com", "https://b.com"])


def test_compute_cluster_id_dedup():
    urls = ["https://a.com", "https://a.com"]
    cid = compute_cluster_id(urls)
    assert cid == compute_cluster_id(["https://a.com"])


def test_architect_basic_clustering(mock_client):
    candidates = [
        FilteredCandidate(title="AI Story A", url="https://a.com/ai1", snippet="AI news"),
        FilteredCandidate(title="AI Story B", url="https://a.com/ai2", snippet="More AI"),
        FilteredCandidate(title="Space News", url="https://b.com/space", snippet="Space"),
    ]
    sentinel_output = SentinelOutput(passed=candidates)

    mock_client.set_responses(
        [
            {
                "clusters": [
                    {"label": "AI Research", "candidate_indices": [0, 1], "best_index": 0},
                    {"label": "Space Mission", "candidate_indices": [2], "best_index": 2},
                ]
            }
        ]
    )

    architect = Architect(mock_client)
    result = architect.run(sentinel_output, history_window=[])

    assert len(result.clusters) == 2
    assert result.api_calls == 1
    assert result.deduped_count == 0


def test_architect_dedup_against_history(mock_client):
    candidates = [
        FilteredCandidate(title="Old Story", url="https://old.com/1", snippet="Old"),
    ]
    sentinel_output = SentinelOutput(passed=candidates)

    mock_client.set_responses(
        [
            {
                "clusters": [
                    {"label": "Old Event", "candidate_indices": [0], "best_index": 0},
                ]
            }
        ]
    )

    history = [
        HistoryEntry(
            cluster_id="x",
            label="Old Event",
            urls=["https://old.com/1"],
            first_seen="2025-01-01",
            last_seen="2025-01-01",
        )
    ]

    architect = Architect(mock_client)
    result = architect.run(sentinel_output, history_window=history)

    assert len(result.clusters) == 0
    assert result.deduped_count == 1


def test_architect_empty_input(mock_client):
    sentinel_output = SentinelOutput(passed=[])
    architect = Architect(mock_client)
    result = architect.run(sentinel_output, history_window=[])

    assert len(result.clusters) == 0
    assert result.api_calls == 0
