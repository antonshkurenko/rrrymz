"""Tests for memory.md parser/writer."""

from datetime import date
from pathlib import Path

from curator.memory import is_topic_muted, is_topic_snoozed, parse_memory, write_memory
from curator.models import UserPersona


def test_parse_memory(tmp_path: Path):
    md = tmp_path / "memory.md"
    md.write_text(
        """# Memory

## Interests
- AI and machine learning
- Space exploration

## Muted Topics
- Celebrity gossip
- Sports scores

## Active Snoozes
- Bitcoin ETF (until 2099-12-31)
- Election coverage (until 2025-02-01)

## Notes
- Prefer technical depth
"""
    )
    persona = parse_memory(md)
    assert len(persona.interests) == 2
    assert "AI and machine learning" in persona.interests
    assert len(persona.muted_topics) == 2
    assert "Bitcoin ETF" in persona.active_snoozes
    assert persona.active_snoozes["Bitcoin ETF"] == "2099-12-31"
    assert len(persona.notes) == 1


def test_parse_memory_missing_file(tmp_path: Path):
    persona = parse_memory(tmp_path / "nonexistent.md")
    assert persona.interests == []


def test_is_topic_muted():
    persona = UserPersona(muted_topics=["Celebrity gossip", "Sports"])
    assert is_topic_muted(persona, "Celebrity gossip update")
    assert is_topic_muted(persona, "CELEBRITY GOSSIP news")
    assert not is_topic_muted(persona, "AI research")
    assert is_topic_muted(persona, "Sports scores today")


def test_is_topic_snoozed():
    persona = UserPersona(active_snoozes={"Bitcoin ETF": "2099-12-31"})
    assert is_topic_snoozed(persona, "Bitcoin ETF news", today=date(2025, 1, 1))
    assert not is_topic_snoozed(persona, "AI research", today=date(2025, 1, 1))


def test_is_topic_snoozed_expired():
    persona = UserPersona(active_snoozes={"Bitcoin ETF": "2020-01-01"})
    assert not is_topic_snoozed(persona, "Bitcoin ETF news", today=date(2025, 1, 1))


def test_is_topic_snoozed_no_expiry():
    persona = UserPersona(active_snoozes={"Bitcoin ETF": ""})
    assert is_topic_snoozed(persona, "Bitcoin ETF news")


def test_write_memory(tmp_path: Path):
    persona = UserPersona(
        interests=["AI", "Space"],
        muted_topics=["Gossip"],
        active_snoozes={"Crypto": "2099-01-01"},
        notes=["Test note"],
    )
    path = tmp_path / "memory.md"
    write_memory(persona, path)

    # Re-parse and verify round trip
    restored = parse_memory(path)
    assert restored.interests == ["AI", "Space"]
    assert restored.muted_topics == ["Gossip"]
    assert restored.active_snoozes["Crypto"] == "2099-01-01"
    assert restored.notes == ["Test note"]
