"""History management: load, save, retention, dedup window."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from curator.config import Settings
from curator.models import HistoryEntry, HistoryFile


class HistoryManager:
    def __init__(self, settings: Settings) -> None:
        self._path = Path(settings.history_path)
        self._retention_days = settings.history_retention_days
        self._dedup_window_days = settings.history_dedup_window_days
        self._data: HistoryFile = HistoryFile()

    def load(self) -> HistoryFile:
        if self._path.exists():
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = HistoryFile.model_validate(raw)
        else:
            self._data = HistoryFile()
        return self._data

    def save(self) -> None:
        self._data.last_updated = date.today().isoformat()
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            self._data.model_dump_json(indent=2) + "\n",
            encoding="utf-8",
        )

    def apply_retention(self, today: date | None = None) -> int:
        """Remove entries older than retention period. Returns count removed."""
        today = today or date.today()
        cutoff = today - timedelta(days=self._retention_days)
        before = len(self._data.entries)
        self._data.entries = [
            e
            for e in self._data.entries
            if _parse_date(e.last_seen, today) >= cutoff
        ]
        return before - len(self._data.entries)

    def get_dedup_window(self, today: date | None = None) -> list[HistoryEntry]:
        """Return entries within the dedup window."""
        today = today or date.today()
        cutoff = today - timedelta(days=self._dedup_window_days)
        return [
            e
            for e in self._data.entries
            if _parse_date(e.last_seen, today) >= cutoff
        ]

    def add_entries(self, entries: list[HistoryEntry]) -> None:
        """Add or update entries. If cluster_id exists, update last_seen and merge URLs."""
        existing = {e.cluster_id: e for e in self._data.entries}
        for entry in entries:
            if entry.cluster_id in existing:
                ex = existing[entry.cluster_id]
                ex.last_seen = entry.last_seen or date.today().isoformat()
                ex.urls = list(set(ex.urls) | set(entry.urls))
            else:
                if not entry.first_seen:
                    entry.first_seen = date.today().isoformat()
                if not entry.last_seen:
                    entry.last_seen = date.today().isoformat()
                self._data.entries.append(entry)
                existing[entry.cluster_id] = entry

    @property
    def data(self) -> HistoryFile:
        return self._data


def _parse_date(date_str: str, fallback: date) -> date:
    try:
        return date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return fallback
