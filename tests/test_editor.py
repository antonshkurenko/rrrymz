"""Tests for Stage 5: Master Editor."""

from curator.models import AnalysisResult, AnalystOutput
from curator.stages.editor import MasterEditor


def test_editor_passes_threshold(mock_client, sample_settings):
    analyses = [
        AnalysisResult(
            cluster_id="c1",
            label="Big Story",
            best_url="https://a.com",
            knowledge_depth=8,
            key_facts=["Important fact"],
            claims_verified=True,
        ),
    ]
    analyst_output = AnalystOutput(analyses=analyses)

    mock_client.set_responses(
        [
            {
                "stories": [
                    {
                        "cluster_id": "c1",
                        "headline": "Major Development",
                        "core_fact": "Something important happened.",
                        "summary": "A detailed summary of the event.",
                        "metrics": {"breaking": 9, "importance": 8, "snr": 7},
                    }
                ]
            }
        ]
    )

    editor = MasterEditor(mock_client, sample_settings)
    stories = editor.run(analyst_output)

    assert len(stories) == 1
    assert stories[0].headline == "Major Development"
    assert stories[0].metrics.breaking == 9


def test_editor_filters_low_snr(mock_client, sample_settings):
    analyses = [
        AnalysisResult(
            cluster_id="c1",
            label="Clickbait",
            best_url="https://a.com",
            knowledge_depth=2,
        ),
    ]
    analyst_output = AnalystOutput(analyses=analyses)

    mock_client.set_responses(
        [
            {
                "stories": [
                    {
                        "cluster_id": "c1",
                        "headline": "Clickbait Title",
                        "core_fact": "Not much here.",
                        "summary": "Filler content.",
                        "metrics": {"breaking": 3, "importance": 3, "snr": 2},
                    }
                ]
            }
        ]
    )

    editor = MasterEditor(mock_client, sample_settings)
    stories = editor.run(analyst_output)

    assert len(stories) == 0


def test_editor_filters_low_importance(mock_client, sample_settings):
    analyses = [
        AnalysisResult(cluster_id="c1", label="Minor", best_url="https://a.com"),
    ]
    analyst_output = AnalystOutput(analyses=analyses)

    mock_client.set_responses(
        [
            {
                "stories": [
                    {
                        "cluster_id": "c1",
                        "headline": "Minor Update",
                        "core_fact": "Small change.",
                        "summary": "A small update.",
                        "metrics": {"breaking": 3, "importance": 4, "snr": 6},
                    }
                ]
            }
        ]
    )

    editor = MasterEditor(mock_client, sample_settings)
    stories = editor.run(analyst_output)

    assert len(stories) == 0


def test_editor_breaking_override(mock_client, sample_settings):
    """Breaking >= 8 should pass even if importance < 7."""
    analyses = [
        AnalysisResult(cluster_id="c1", label="Breaking", best_url="https://a.com"),
    ]
    analyst_output = AnalystOutput(analyses=analyses)

    mock_client.set_responses(
        [
            {
                "stories": [
                    {
                        "cluster_id": "c1",
                        "headline": "Breaking News",
                        "core_fact": "Just happened.",
                        "summary": "Breaking story.",
                        "metrics": {"breaking": 9, "importance": 5, "snr": 6},
                    }
                ]
            }
        ]
    )

    editor = MasterEditor(mock_client, sample_settings)
    stories = editor.run(analyst_output)

    assert len(stories) == 1


def test_editor_empty_input(mock_client, sample_settings):
    analyst_output = AnalystOutput(analyses=[])
    editor = MasterEditor(mock_client, sample_settings)
    stories = editor.run(analyst_output)

    assert len(stories) == 0


def test_editor_sorts_by_breaking_then_importance(mock_client, sample_settings):
    analyses = [
        AnalysisResult(cluster_id="c1", label="Story A", best_url="https://a.com"),
        AnalysisResult(cluster_id="c2", label="Story B", best_url="https://b.com"),
    ]
    analyst_output = AnalystOutput(analyses=analyses)

    mock_client.set_responses(
        [
            {
                "stories": [
                    {
                        "cluster_id": "c1",
                        "headline": "Less Breaking",
                        "core_fact": "Fact A.",
                        "summary": "Summary A.",
                        "metrics": {"breaking": 7, "importance": 9, "snr": 7},
                    },
                    {
                        "cluster_id": "c2",
                        "headline": "More Breaking",
                        "core_fact": "Fact B.",
                        "summary": "Summary B.",
                        "metrics": {"breaking": 10, "importance": 8, "snr": 8},
                    },
                ]
            }
        ]
    )

    editor = MasterEditor(mock_client, sample_settings)
    stories = editor.run(analyst_output)

    assert len(stories) == 2
    assert stories[0].cluster_id == "c2"  # Higher breaking first
