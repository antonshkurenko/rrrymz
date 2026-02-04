"""Google News RSS feed source."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from html import unescape
from re import sub as re_sub
from urllib.parse import quote_plus

import feedparser
import httpx

from curator.models import DiscoveryCandidate

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl={lang}&gl=US&ceid=US:{lang}"
_REQUEST_TIMEOUT = 15.0


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    clean = re_sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def _parse_published(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None
    return None


def fetch_google_news(
    query: str,
    lang: str = "en",
    since: datetime | None = None,
) -> list[DiscoveryCandidate]:
    """Fetch recent news from Google News RSS for a search query."""
    encoded = quote_plus(query)
    url = _GOOGLE_NEWS_RSS.format(query=encoded, lang=lang)

    # Use httpx to follow redirects (Google News returns 302)
    try:
        with httpx.Client(follow_redirects=True, timeout=_REQUEST_TIMEOUT) as client:
            response = client.get(url)
            response.raise_for_status()
            content = response.text
    except Exception:
        logger.warning("Failed to fetch Google News RSS for query=%s", query, exc_info=True)
        return []

    try:
        feed = feedparser.parse(content)
    except Exception:
        logger.warning("Failed to parse Google News RSS for query=%s", query)
        return []

    if feed.bozo and not feed.entries:
        logger.warning("Google News RSS parse error for query=%s: %s", query, feed.bozo_exception)
        return []

    candidates = []
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
                source_language=lang,
                interest_query=query,
            )
        )

    logger.info("Google News: %d candidates for query=%s lang=%s", len(candidates), query, lang)
    return candidates
