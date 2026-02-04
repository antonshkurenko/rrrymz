"""Read feedback from GitHub Issues and adjust persona weights."""

from __future__ import annotations

import json
import logging
import subprocess

from curator.config import Settings
from curator.memory import parse_memory, write_memory

logger = logging.getLogger(__name__)


def _run_gh(args: list[str]) -> str:
    """Run a gh CLI command and return stdout."""
    result = subprocess.run(
        ["gh"] + args,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        logger.warning("gh command failed: %s", result.stderr)
        return ""
    return result.stdout


def fetch_feedback_issues(repo: str) -> list[dict]:
    """Fetch open feedback issues (liked/disliked) from the repo."""
    issues = []
    for label in ("feedback:like", "feedback:dislike"):
        raw = _run_gh([
            "issue",
            "list",
            "--repo",
            repo,
            "--label",
            label,
            "--state",
            "open",
            "--json",
            "number,title,body,labels",
            "--limit",
            "100",
        ])
        if raw.strip():
            try:
                issues.extend(json.loads(raw))
            except json.JSONDecodeError:
                logger.warning("Failed to parse gh output for label=%s", label)
    return issues


def process_feedback(settings: Settings) -> None:
    """Process feedback issues: adjust persona, close issues."""
    if not settings.github_repo:
        logger.warning("GITHUB_REPO not set, skipping feedback processing")
        return

    persona = parse_memory(settings.memory_path)
    issues = fetch_feedback_issues(settings.github_repo)

    if not issues:
        logger.info("No feedback issues to process")
        return

    likes: list[str] = []
    dislikes: list[str] = []

    for issue in issues:
        labels = [lbl.get("name", "") for lbl in issue.get("labels", [])]
        body = issue.get("body", "")
        title = issue.get("title", "")
        topic = _extract_topic(title, body)

        if "feedback:like" in labels and topic:
            likes.append(topic)
        elif "feedback:dislike" in labels and topic:
            dislikes.append(topic)

        # Close the processed issue
        issue_num = issue.get("number")
        if issue_num:
            _run_gh([
                "issue",
                "close",
                str(issue_num),
                "--repo",
                settings.github_repo,
                "--comment",
                "Feedback processed. Thank you!",
            ])

    # Adjust persona
    if likes:
        note = f"Liked topics: {', '.join(likes)}"
        if note not in persona.notes:
            persona.notes.append(note)

    if dislikes:
        note = f"Disliked topics: {', '.join(dislikes)}"
        if note not in persona.notes:
            persona.notes.append(note)

    write_memory(persona, settings.memory_path)
    logger.info("Processed %d likes, %d dislikes", len(likes), len(dislikes))


def _extract_topic(title: str, body: str) -> str:
    """Extract topic/cluster info from issue title or body."""
    # Try to find cluster_id or topic from the issue body
    for line in body.splitlines():
        line = line.strip()
        if line.lower().startswith("topic:"):
            return line.split(":", 1)[1].strip()
        if line.lower().startswith("cluster_id:"):
            return line.split(":", 1)[1].strip()
    # Fall back to title
    for prefix in ("Like:", "Dislike:", "[Like]", "[Dislike]"):
        if title.startswith(prefix):
            return title[len(prefix) :].strip()
    return title


def main() -> None:
    """CLI entry point for monthly feedback processing."""
    settings = Settings.from_env()
    process_feedback(settings)
