"""Tests for Pydantic models."""

from curator.models import (
    AnalysisResult,
    ArchitectOutput,
    CurationMetrics,
    DailyDigest,
    DigestStory,
    DiscoveryCandidate,
    EventCluster,
    FilteredCandidate,
    HistoryEntry,
    HistoryFile,
    PipelineMetadata,
    ScoutOutput,
    SentinelOutput,
    UserPersona,
)


def test_user_persona_defaults():
    p = UserPersona()
    assert p.interests == []
    assert p.muted_topics == []
    assert p.active_snoozes == {}
    assert p.notes == []


def test_discovery_candidate():
    c = DiscoveryCandidate(title="Test", url="https://example.com")
    assert c.title == "Test"
    assert c.snippet == ""
    assert c.source_language == "en"


def test_scout_output():
    s = ScoutOutput(
        candidates=[DiscoveryCandidate(title="A", url="https://a.com")],
        api_calls=1,
    )
    assert len(s.candidates) == 1
    assert s.api_calls == 1


def test_filtered_candidate():
    f = FilteredCandidate(title="T", url="https://t.com", relevance_score=0.8)
    assert f.relevance_score == 0.8


def test_sentinel_output():
    s = SentinelOutput(filtered_count=5)
    assert s.filtered_count == 5
    assert s.passed == []


def test_event_cluster():
    c = EventCluster(cluster_id="abc123", label="Test Event")
    assert c.cluster_id == "abc123"
    assert c.is_duplicate_of_history is False


def test_architect_output():
    a = ArchitectOutput()
    assert a.clusters == []
    assert a.deduped_count == 0


def test_analysis_result_bounds():
    a = AnalysisResult(cluster_id="x", label="x", knowledge_depth=10)
    assert a.knowledge_depth == 10


def test_curation_metrics():
    m = CurationMetrics(breaking=8, importance=7, snr=6)
    assert m.breaking == 8


def test_digest_story():
    s = DigestStory(
        cluster_id="abc",
        headline="Test Headline",
        core_fact="Test fact.",
        summary="Test summary.",
    )
    assert s.headline == "Test Headline"


def test_daily_digest():
    d = DailyDigest(date="2025-01-01")
    assert d.stories == []
    assert d.metadata.total_api_calls == 0


def test_history_entry():
    h = HistoryEntry(cluster_id="c1", label="Test")
    assert h.urls == []


def test_history_file():
    hf = HistoryFile()
    assert hf.entries == []


def test_pipeline_metadata():
    m = PipelineMetadata(run_date="2025-01-01", total_discovered=50)
    assert m.total_discovered == 50


def test_model_round_trip():
    """Test JSON serialization/deserialization round trip."""
    story = DigestStory(
        cluster_id="abc",
        headline="Test",
        core_fact="Fact",
        summary="Summary",
        sources=["https://a.com"],
        metrics=CurationMetrics(breaking=8, importance=7, snr=6),
    )
    json_str = story.model_dump_json()
    restored = DigestStory.model_validate_json(json_str)
    assert restored.cluster_id == story.cluster_id
    assert restored.metrics.breaking == 8
