"""Custom RSS feed source with since-last-run filtering."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from re import sub as re_sub

import feedparser

from curator.models import DiscoveryCandidate

logger = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    clean = re_sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def _parse_published(entry: dict) -> datetime | None:
    """Parse the published or updated date from a feedparser entry."""
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def load_feed_urls(feeds_path: str) -> list[str]:
    """Load RSS feed URLs from a text file (one per line, # comments)."""
    path = Path(feeds_path)
    if not path.exists():
        return []
    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            urls.append(stripped)
    return urls


def fetch_rss_feeds(
    feed_urls: list[str],
    since: datetime | None = None,
) -> list[DiscoveryCandidate]:
    """Fetch recent items from custom RSS feeds, filtered by since date."""
    candidates = []

    for feed_url in feed_urls:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            logger.warning("Failed to fetch RSS feed: %s", feed_url)
            continue

        if feed.bozo and not feed.entries:
            logger.warning("RSS parse error for %s: %s", feed_url, feed.bozo_exception)
            continue

        count = 0
        for entry in feed.entries:
            pub_date = _parse_published(entry)
            if since and pub_date and pub_date < since:
                continue

            title = _strip_html(entry.get("title", ""))
            link = entry.get("link", "")
            snippet = _strip_html(entry.get("summary", entry.get("description", "")))

            if not title or not link:
                continue

            candidates.append(
                DiscoveryCandidate(
                    title=title,
                    url=link,
                    snippet=snippet[:500],
                    source_language="en",
                    interest_query="rss",
                )
            )
            count += 1

        logger.info("RSS %s: %d items", feed_url, count)

    return candidates
