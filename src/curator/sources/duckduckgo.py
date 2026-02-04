"""DuckDuckGo news search source."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from duckduckgo_search import DDGS

from curator.models import DiscoveryCandidate

logger = logging.getLogger(__name__)


def _parse_ddg_date(date_str: str) -> datetime | None:
    """Parse a date string from DDG news results."""
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def fetch_duckduckgo_news(
    query: str,
    since: datetime | None = None,
    max_results: int = 10,
) -> list[DiscoveryCandidate]:
    """Fetch recent news from DuckDuckGo for a search query."""
    try:
        results = list(DDGS().news(query, max_results=max_results))
    except Exception:
        logger.warning("Failed to fetch DuckDuckGo news for query=%s", query, exc_info=True)
        return []

    candidates = []
    for item in results:
        pub_date = _parse_ddg_date(item.get("date", ""))
        if since and pub_date and pub_date < since:
            continue

        title = item.get("title", "")
        url = item.get("url", "")
        snippet = item.get("body", "")

        if not title or not url:
            continue

        candidates.append(
            DiscoveryCandidate(
                title=title,
                url=url,
                snippet=snippet[:500],
                source_language="en",
                interest_query=query,
            )
        )

    logger.info("DuckDuckGo: %d candidates for query=%s", len(candidates), query)
    return candidates
