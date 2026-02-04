"""Integration test for the pipeline orchestrator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from curator.config import Settings
from curator.models import (
    AnalysisResult,
    AnalystOutput,
    ArchitectOutput,
    CurationMetrics,
    DailyDigest,
    DigestStory,
    EventCluster,
    FilteredCandidate,
    ScoutOutput,
    SentinelOutput,
)
from curator.pipeline import run_pipeline


def test_pipeline_end_to_end(tmp_path: Path):
    """Test full pipeline with mocked stages."""
    memory_path = tmp_path / "memory.md"
    memory_path.write_text(
        """# Memory

## Interests
- AI research

## Muted Topics

## Active Snoozes

## Notes
"""
    )

    history_path = tmp_path / "history.json"
    history_path.write_text('{"entries": [], "last_updated": ""}')

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "latest.json"

    settings = Settings(
        gemini_api_key="test-key",
        model_id="test-model",
        scout_languages=["en"],
        memory_path=str(memory_path),
        history_path=str(history_path),
        output_path=str(output_path),
    )

    # Mock all stages
    mock_scout_output = ScoutOutput(
        candidates=[
            {
                "title": "AI News",
                "url": "https://example.com/ai",
                "snippet": "AI breakthrough",
                "source_language": "en",
                "interest_query": "AI research",
            }
        ],
        api_calls=1,
    )

    mock_sentinel_output = SentinelOutput(
        passed=[
            FilteredCandidate(
                title="AI News",
                url="https://example.com/ai",
                snippet="AI breakthrough",
                relevance_score=0.9,
            )
        ],
        filtered_count=0,
        api_calls=1,
    )

    mock_architect_output = ArchitectOutput(
        clusters=[
            EventCluster(
                cluster_id="abc123",
                label="AI Breakthrough",
                candidates=[mock_sentinel_output.passed[0]],
                best_url="https://example.com/ai",
            )
        ],
        deduped_count=0,
        api_calls=1,
    )

    mock_analyst_output = AnalystOutput(
        analyses=[
            AnalysisResult(
                cluster_id="abc123",
                label="AI Breakthrough",
                best_url="https://example.com/ai",
                knowledge_depth=8,
                key_facts=["Major AI advance"],
                claims_verified=True,
            )
        ],
        api_calls=1,
    )

    mock_stories = [
        DigestStory(
            cluster_id="abc123",
            headline="AI Makes Major Advance",
            core_fact="Researchers achieved a breakthrough.",
            summary="A detailed summary.",
            sources=["https://example.com/ai"],
            metrics=CurationMetrics(breaking=8, importance=9, snr=7),
            label="AI Breakthrough",
        )
    ]

    with (
        patch("curator.pipeline.PolyglotScout") as MockScout,
        patch("curator.pipeline.Sentinel") as MockSentinel,
        patch("curator.pipeline.Architect") as MockArchitect,
        patch("curator.pipeline.TechnicalAnalyst") as MockAnalyst,
        patch("curator.pipeline.MasterEditor") as MockEditor,
        patch("curator.pipeline.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value = MagicMock(call_count=5)
        MockScout.return_value.run.return_value = mock_scout_output
        MockSentinel.return_value.run.return_value = mock_sentinel_output
        MockArchitect.return_value.run.return_value = mock_architect_output
        MockAnalyst.return_value.run.return_value = mock_analyst_output
        MockEditor.return_value.run.return_value = mock_stories

        digest = run_pipeline(settings)

    assert isinstance(digest, DailyDigest)
    assert len(digest.stories) == 1
    assert digest.stories[0].headline == "AI Makes Major Advance"

    # Verify output file was written
    assert output_path.exists()
    output_data = json.loads(output_path.read_text())
    assert len(output_data["stories"]) == 1

    # Verify dated archive file was written
    from datetime import date

    dated_path = output_dir / f"{date.today().isoformat()}.json"
    assert dated_path.exists()
    dated_data = json.loads(dated_path.read_text())
    assert dated_data == output_data

    # Verify archive index was written
    archive_path = output_dir / "archive.json"
    assert archive_path.exists()
    archive_data = json.loads(archive_path.read_text())
    assert len(archive_data["digests"]) == 1
    assert archive_data["digests"][0]["date"] == date.today().isoformat()
    assert archive_data["digests"][0]["story_count"] == 1

    # Verify history was updated
    history_data = json.loads(history_path.read_text())
    assert len(history_data["entries"]) == 1


def test_pipeline_empty_results(tmp_path: Path):
    """Pipeline should handle empty results gracefully."""
    memory_path = tmp_path / "memory.md"
    memory_path.write_text("# Memory\n\n## Interests\n- Test\n")

    history_path = tmp_path / "history.json"
    history_path.write_text('{"entries": [], "last_updated": ""}')

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "latest.json"

    settings = Settings(
        gemini_api_key="test-key",
        model_id="test-model",
        scout_languages=["en"],
        memory_path=str(memory_path),
        history_path=str(history_path),
        output_path=str(output_path),
    )

    with (
        patch("curator.pipeline.PolyglotScout") as MockScout,
        patch("curator.pipeline.Sentinel") as MockSentinel,
        patch("curator.pipeline.Architect") as MockArchitect,
        patch("curator.pipeline.TechnicalAnalyst") as MockAnalyst,
        patch("curator.pipeline.MasterEditor") as MockEditor,
        patch("curator.pipeline.GeminiClient") as MockGemini,
    ):
        MockGemini.return_value = MagicMock(call_count=0)
        MockScout.return_value.run.return_value = ScoutOutput(candidates=[], api_calls=0)
        MockSentinel.return_value.run.return_value = SentinelOutput(
            passed=[], filtered_count=0, api_calls=0
        )
        MockArchitect.return_value.run.return_value = ArchitectOutput(
            clusters=[], deduped_count=0, api_calls=0
        )
        MockAnalyst.return_value.run.return_value = AnalystOutput(analyses=[], api_calls=0)
        MockEditor.return_value.run.return_value = []

        digest = run_pipeline(settings)

    assert len(digest.stories) == 0
    assert output_path.exists()
