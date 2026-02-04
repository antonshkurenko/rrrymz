"""Configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str = ""
    model_id: str = "gemini-3-flash-preview"
    scout_languages: list[str] = field(default_factory=lambda: ["en", "fr", "es"])
    sentinel_relevance_threshold: float = 0.6
    editor_snr_threshold: int = 5
    editor_breaking_threshold: int = 8
    editor_importance_threshold: int = 8
    history_retention_days: int = 30
    history_dedup_window_days: int = 7
    github_repo: str = ""
    memory_path: str = "data/memory.md"
    history_path: str = "data/history.json"
    output_path: str = "output/latest.json"
    feeds_path: str = "data/feeds.txt"
    rss_max_age_hours: int = 48

    @classmethod
    def from_env(cls) -> Settings:
        langs_raw = os.environ.get("SCOUT_LANGUAGES", "en,fr,es")
        return cls(
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            model_id=os.environ.get("GEMINI_MODEL_ID", "gemini-3-flash-preview"),
            scout_languages=[lang.strip() for lang in langs_raw.split(",") if lang.strip()],
            sentinel_relevance_threshold=float(
                os.environ.get("SENTINEL_RELEVANCE_THRESHOLD", "0.6")
            ),
            editor_snr_threshold=int(os.environ.get("EDITOR_SNR_THRESHOLD", "5")),
            editor_breaking_threshold=int(os.environ.get("EDITOR_BREAKING_THRESHOLD", "8")),
            editor_importance_threshold=int(os.environ.get("EDITOR_IMPORTANCE_THRESHOLD", "8")),
            history_retention_days=int(os.environ.get("HISTORY_RETENTION_DAYS", "30")),
            history_dedup_window_days=int(os.environ.get("HISTORY_DEDUP_WINDOW_DAYS", "7")),
            github_repo=os.environ.get("GITHUB_REPO", ""),
            memory_path=os.environ.get("MEMORY_PATH", "data/memory.md"),
            history_path=os.environ.get("HISTORY_PATH", "data/history.json"),
            output_path=os.environ.get("OUTPUT_PATH", "output/latest.json"),
            feeds_path=os.environ.get("FEEDS_PATH", "data/feeds.txt"),
            rss_max_age_hours=int(os.environ.get("RSS_MAX_AGE_HOURS", "48")),
        )
