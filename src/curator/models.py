"""Pydantic data models for the entire pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field

# --- Memory / Persona ---


class UserPersona(BaseModel):
    interests: list[str] = Field(default_factory=list)
    muted_topics: list[str] = Field(default_factory=list)
    active_snoozes: dict[str, str] = Field(default_factory=dict)  # topic -> expiry date str
    notes: list[str] = Field(default_factory=list)


# --- Stage 1: Scout ---


class DiscoveryCandidate(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_language: str = "en"
    interest_query: str = ""


class ScoutOutput(BaseModel):
    candidates: list[DiscoveryCandidate] = Field(default_factory=list)
    api_calls: int = 0


# --- Stage 2: Sentinel ---


class FilteredCandidate(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_language: str = "en"
    interest_query: str = ""
    relevance_score: float = 0.0


class SentinelOutput(BaseModel):
    passed: list[FilteredCandidate] = Field(default_factory=list)
    filtered_count: int = 0
    api_calls: int = 0


# --- Stage 3: Architect ---


class EventCluster(BaseModel):
    cluster_id: str
    label: str
    candidates: list[FilteredCandidate] = Field(default_factory=list)
    best_url: str = ""
    is_duplicate_of_history: bool = False


class ArchitectOutput(BaseModel):
    clusters: list[EventCluster] = Field(default_factory=list)
    deduped_count: int = 0
    api_calls: int = 0


# --- Stage 4: Analyst ---


class AnalysisResult(BaseModel):
    cluster_id: str
    label: str
    best_url: str = ""
    scraped_text: str = ""
    knowledge_depth: int = Field(default=1, ge=1, le=10)
    key_facts: list[str] = Field(default_factory=list)
    claims_verified: bool = False
    scrape_failed: bool = False


class AnalystOutput(BaseModel):
    analyses: list[AnalysisResult] = Field(default_factory=list)
    api_calls: int = 0


# --- Stage 5: Editor ---


class CurationMetrics(BaseModel):
    breaking: int = Field(default=1, ge=1, le=10)
    importance: int = Field(default=1, ge=1, le=10)
    snr: int = Field(default=1, ge=1, le=10)


class DigestStory(BaseModel):
    cluster_id: str
    headline: str
    core_fact: str
    summary: str
    sources: list[str] = Field(default_factory=list)
    metrics: CurationMetrics = Field(default_factory=CurationMetrics)
    label: str = ""


class PipelineMetadata(BaseModel):
    run_date: str = ""
    total_discovered: int = 0
    after_sentinel: int = 0
    clusters_formed: int = 0
    after_dedup: int = 0
    stories_published: int = 0
    total_api_calls: int = 0


class DailyDigest(BaseModel):
    date: str = ""
    stories: list[DigestStory] = Field(default_factory=list)
    metadata: PipelineMetadata = Field(default_factory=PipelineMetadata)


# --- Archive ---


class ArchiveEntry(BaseModel):
    date: str
    file: str
    story_count: int = 0


class ArchiveIndex(BaseModel):
    digests: list[ArchiveEntry] = Field(default_factory=list)


# --- History ---


class HistoryEntry(BaseModel):
    cluster_id: str
    label: str
    urls: list[str] = Field(default_factory=list)
    first_seen: str = ""  # ISO date
    last_seen: str = ""  # ISO date


class HistoryFile(BaseModel):
    entries: list[HistoryEntry] = Field(default_factory=list)
    last_updated: str = ""
