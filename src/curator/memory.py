"""Parse and write memory.md into a UserPersona."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from curator.models import UserPersona


def parse_memory(path: str | Path) -> UserPersona:
    """Parse memory.md sections into a UserPersona."""
    path = Path(path)
    if not path.exists():
        return UserPersona()

    text = path.read_text(encoding="utf-8")
    return _parse_text(text)


def _parse_text(text: str) -> UserPersona:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None

    for line in text.splitlines():
        header_match = re.match(r"^##\s+(.+)$", line.strip())
        if header_match:
            current_section = header_match.group(1).strip().lower()
            sections[current_section] = []
            continue
        if current_section is not None:
            stripped = line.strip()
            if stripped.startswith("- "):
                sections[current_section].append(stripped[2:].strip())

    interests = sections.get("interests", [])
    muted = sections.get("muted topics", []) or sections.get("muted", [])

    # Parse snoozes: "topic (until YYYY-MM-DD)"
    raw_snoozes = sections.get("active snoozes", []) or sections.get("snoozes", [])
    snoozes: dict[str, str] = {}
    for item in raw_snoozes:
        m = re.match(r"^(.+?)\s*\(until\s+(\d{4}-\d{2}-\d{2})\)", item)
        if m:
            snoozes[m.group(1).strip()] = m.group(2)
        else:
            snoozes[item] = ""

    notes = sections.get("notes", [])

    return UserPersona(
        interests=interests,
        muted_topics=muted,
        active_snoozes=snoozes,
        notes=notes,
    )


def is_topic_muted(persona: UserPersona, topic: str) -> bool:
    """Check if a topic matches any muted pattern (case-insensitive substring)."""
    topic_lower = topic.lower()
    return any(m.lower() in topic_lower for m in persona.muted_topics)


def is_topic_snoozed(persona: UserPersona, topic: str, today: date | None = None) -> bool:
    """Check if a topic is snoozed and the snooze is still active."""
    today = today or date.today()
    topic_lower = topic.lower()
    for snoozed_topic, expiry_str in persona.active_snoozes.items():
        if snoozed_topic.lower() in topic_lower:
            if not expiry_str:
                return True
            try:
                expiry = date.fromisoformat(expiry_str)
                if today <= expiry:
                    return True
            except ValueError:
                return True
    return False


def write_memory(persona: UserPersona, path: str | Path) -> None:
    """Write a UserPersona back to memory.md format."""
    path = Path(path)
    lines = ["# Memory", ""]

    lines.append("## Interests")
    for item in persona.interests:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Muted Topics")
    for item in persona.muted_topics:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("## Active Snoozes")
    for topic, expiry in persona.active_snoozes.items():
        if expiry:
            lines.append(f"- {topic} (until {expiry})")
        else:
            lines.append(f"- {topic}")
    lines.append("")

    lines.append("## Notes")
    for item in persona.notes:
        lines.append(f"- {item}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
