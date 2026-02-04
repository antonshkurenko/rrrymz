"""Tests for history management."""

import json
from datetime import date, timedelta
from pathlib import Path

from curator.config import Settings
from curator.history import HistoryManager
from curator.models import HistoryEntry


def test_load_empty(sample_settings: Settings):
    mgr = HistoryManager(sample_settings)
    data = mgr.load()
    assert data.entries == []


def test_load_existing(sample_settings: Settings):
    path = Path(sample_settings.history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "cluster_id": "abc",
                        "label": "Test",
                        "urls": ["https://a.com"],
                        "first_seen": "2025-01-01",
                        "last_seen": "2025-01-01",
                    }
                ],
                "last_updated": "2025-01-01",
            }
        )
    )
    mgr = HistoryManager(sample_settings)
    data = mgr.load()
    assert len(data.entries) == 1
    assert data.entries[0].cluster_id == "abc"


def test_save(sample_settings: Settings):
    mgr = HistoryManager(sample_settings)
    mgr.load()
    mgr.add_entries(
        [
            HistoryEntry(
                cluster_id="x1",
                label="Test",
                urls=["https://x.com"],
                first_seen="2025-01-15",
                last_seen="2025-01-15",
            )
        ]
    )
    mgr.save()

    path = Path(sample_settings.history_path)
    assert path.exists()
    raw = json.loads(path.read_text())
    assert len(raw["entries"]) == 1


def test_apply_retention(sample_settings: Settings):
    mgr = HistoryManager(sample_settings)
    mgr.load()
    today = date(2025, 3, 1)
    old_date = (today - timedelta(days=31)).isoformat()
    recent_date = (today - timedelta(days=5)).isoformat()

    mgr.add_entries(
        [
            HistoryEntry(
                cluster_id="old",
                label="Old",
                urls=["https://old.com"],
                first_seen=old_date,
                last_seen=old_date,
            ),
            HistoryEntry(
                cluster_id="recent",
                label="Recent",
                urls=["https://recent.com"],
                first_seen=recent_date,
                last_seen=recent_date,
            ),
        ]
    )

    removed = mgr.apply_retention(today=today)
    assert removed == 1
    assert len(mgr.data.entries) == 1
    assert mgr.data.entries[0].cluster_id == "recent"


def test_get_dedup_window(sample_settings: Settings):
    mgr = HistoryManager(sample_settings)
    mgr.load()
    today = date(2025, 3, 1)

    mgr.add_entries(
        [
            HistoryEntry(
                cluster_id="within",
                label="Within Window",
                urls=["https://w.com"],
                first_seen=(today - timedelta(days=3)).isoformat(),
                last_seen=(today - timedelta(days=3)).isoformat(),
            ),
            HistoryEntry(
                cluster_id="outside",
                label="Outside Window",
                urls=["https://o.com"],
                first_seen=(today - timedelta(days=10)).isoformat(),
                last_seen=(today - timedelta(days=10)).isoformat(),
            ),
        ]
    )

    window = mgr.get_dedup_window(today=today)
    assert len(window) == 1
    assert window[0].cluster_id == "within"


def test_add_entries_merge(sample_settings: Settings):
    mgr = HistoryManager(sample_settings)
    mgr.load()

    mgr.add_entries(
        [
            HistoryEntry(
                cluster_id="c1",
                label="Event",
                urls=["https://a.com"],
                first_seen="2025-01-01",
                last_seen="2025-01-01",
            )
        ]
    )
    mgr.add_entries(
        [
            HistoryEntry(
                cluster_id="c1",
                label="Event",
                urls=["https://b.com"],
                last_seen="2025-01-02",
            )
        ]
    )

    assert len(mgr.data.entries) == 1
    entry = mgr.data.entries[0]
    assert set(entry.urls) == {"https://a.com", "https://b.com"}
    assert entry.last_seen == "2025-01-02"
