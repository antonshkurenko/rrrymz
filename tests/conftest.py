"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import pytest
from pydantic import BaseModel

from curator.config import Settings
from curator.models import (
    DiscoveryCandidate,
    EventCluster,
    FilteredCandidate,
    UserPersona,
)

T = TypeVar("T", bound=BaseModel)


class MockGeminiClient:
    """A mock Gemini client that returns pre-configured responses."""

    def __init__(self) -> None:
        self.call_count = 0
        self._responses: list[Any] = []
        self._response_index = 0

    def set_responses(self, responses: list[Any]) -> None:
        self._responses = responses
        self._response_index = 0

    def generate(
        self,
        prompt: str,
        *,
        response_model: type[T] | None = None,
        use_search_grounding: bool = False,
        temperature: float = 0.2,
    ) -> str | T:
        self.call_count += 1

        if self._response_index < len(self._responses):
            resp = self._responses[self._response_index]
            self._response_index += 1
            if response_model is not None and isinstance(resp, dict):
                return response_model.model_validate(resp)
            if response_model is not None and isinstance(resp, response_model):
                return resp
            return resp

        if response_model is not None:
            return response_model()
        return ""


@pytest.fixture
def mock_client() -> MockGeminiClient:
    return MockGeminiClient()


@pytest.fixture
def sample_settings(tmp_path: Path) -> Settings:
    return Settings(
        gemini_api_key="test-key",
        model_id="test-model",
        scout_languages=["en"],
        memory_path=str(tmp_path / "memory.md"),
        history_path=str(tmp_path / "history.json"),
        output_path=str(tmp_path / "output" / "latest.json"),
    )


@pytest.fixture
def sample_persona() -> UserPersona:
    return UserPersona(
        interests=["AI breakthroughs", "Space exploration"],
        muted_topics=["Celebrity gossip", "Sports scores"],
        active_snoozes={"Bitcoin ETF": "2099-12-31"},
        notes=["Prefer technical depth"],
    )


@pytest.fixture
def sample_candidates() -> list[DiscoveryCandidate]:
    return [
        DiscoveryCandidate(
            title="New AI Model Breaks Records",
            url="https://example.com/ai-record",
            snippet="A new AI model achieves state-of-the-art results.",
            source_language="en",
            interest_query="AI breakthroughs",
        ),
        DiscoveryCandidate(
            title="SpaceX Launches New Mission",
            url="https://example.com/spacex",
            snippet="SpaceX successfully launches another mission.",
            source_language="en",
            interest_query="Space exploration",
        ),
        DiscoveryCandidate(
            title="Celebrity Wedding Update",
            url="https://example.com/celeb",
            snippet="Famous celebrity ties the knot.",
            source_language="en",
            interest_query="AI breakthroughs",
        ),
    ]


@pytest.fixture
def sample_filtered() -> list[FilteredCandidate]:
    return [
        FilteredCandidate(
            title="New AI Model Breaks Records",
            url="https://example.com/ai-record",
            snippet="A new AI model achieves state-of-the-art results.",
            source_language="en",
            interest_query="AI breakthroughs",
            relevance_score=0.9,
        ),
        FilteredCandidate(
            title="SpaceX Launches New Mission",
            url="https://example.com/spacex",
            snippet="SpaceX successfully launches another mission.",
            source_language="en",
            interest_query="Space exploration",
            relevance_score=0.85,
        ),
    ]


@pytest.fixture
def sample_clusters(sample_filtered: list[FilteredCandidate]) -> list[EventCluster]:
    from curator.stages.architect import compute_cluster_id

    return [
        EventCluster(
            cluster_id=compute_cluster_id(["https://example.com/ai-record"]),
            label="AI Model Record",
            candidates=[sample_filtered[0]],
            best_url="https://example.com/ai-record",
        ),
        EventCluster(
            cluster_id=compute_cluster_id(["https://example.com/spacex"]),
            label="SpaceX Mission",
            candidates=[sample_filtered[1]],
            best_url="https://example.com/spacex",
        ),
    ]
