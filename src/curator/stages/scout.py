"""Stage 1: Polyglot Scout – discover news from multiple sources."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from curator.config import Settings
from curator.gemini import GeminiClient
from curator.models import DiscoveryCandidate, ScoutOutput, UserPersona
from curator.sources.duckduckgo import fetch_duckduckgo_news
from curator.sources.google_news import fetch_google_news
from curator.sources.rss_feeds import fetch_rss_feeds, load_feed_urls

logger = logging.getLogger(__name__)

_LANG_NAMES = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "zh": "Chinese",
    "ja": "Japanese",
    "ar": "Arabic",
    "pt": "Portuguese",
    "ru": "Russian",
}


def _build_scout_prompt(interest: str, language: str) -> str:
    lang_name = _LANG_NAMES.get(language, language)
    return f"""You are a news scout. Find the latest significant news stories about: {interest}

Search in {lang_name} language sources.

For each story found, return a JSON object with this structure:
{{
  "candidates": [
    {{
      "title": "headline in English",
      "url": "source URL",
      "snippet": "1-2 sentence summary in English",
      "source_language": "{language}"
    }}
  ]
}}

Find 3-5 recent, high-quality news stories. Focus on breaking news, significant developments,
and stories with high signal-to-noise ratio. Translate all titles and snippets to English.
Return valid JSON only."""


def _compute_since(last_run_date: str | None, max_age_hours: int) -> datetime:
    """Compute the cutoff datetime for RSS/feed sources."""
    if last_run_date:
        try:
            dt = datetime.fromisoformat(last_run_date)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(hours=max_age_hours)


class PolyglotScout:
    def __init__(self, client: GeminiClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def run(self, persona: UserPersona, last_run_date: str | None = None) -> ScoutOutput:
        all_candidates: list[DiscoveryCandidate] = []
        seen_urls: set[str] = set()
        api_calls = 0

        since = _compute_since(last_run_date, self._settings.rss_max_age_hours)
        logger.info("Scout: fetching news since %s", since.isoformat())

        # --- Source 1: Google News RSS (per interest × language) ---
        for interest in persona.interests:
            for lang in self._settings.scout_languages:
                try:
                    candidates = fetch_google_news(interest, lang=lang, since=since)
                    for c in candidates:
                        if c.url and c.url not in seen_urls:
                            seen_urls.add(c.url)
                            all_candidates.append(c)
                except Exception:
                    logger.warning(
                        "Google News failed for interest=%s lang=%s", interest, lang, exc_info=True
                    )

        # --- Source 2: DuckDuckGo news (per interest) ---
        for interest in persona.interests:
            try:
                candidates = fetch_duckduckgo_news(interest, since=since)
                for c in candidates:
                    if c.url and c.url not in seen_urls:
                        seen_urls.add(c.url)
                        all_candidates.append(c)
            except Exception:
                logger.warning(
                    "DuckDuckGo failed for interest=%s", interest, exc_info=True
                )

        # --- Source 3: Custom RSS feeds ---
        feed_urls = load_feed_urls(self._settings.feeds_path)
        if feed_urls:
            try:
                candidates = fetch_rss_feeds(feed_urls, since=since)
                for c in candidates:
                    if c.url and c.url not in seen_urls:
                        seen_urls.add(c.url)
                        all_candidates.append(c)
            except Exception:
                logger.warning("Custom RSS feeds failed", exc_info=True)

        # --- Source 4: Gemini search grounding (per interest × language) ---
        # Free on paid tier (5K/month), auto-fails gracefully on free tier
        use_grounding = True
        for interest in persona.interests:
            for lang in self._settings.scout_languages:
                prompt = _build_scout_prompt(interest, lang)
                result = None

                if use_grounding:
                    try:
                        result = self._client.generate(
                            prompt,
                            response_model=ScoutOutput,
                            use_search_grounding=True,
                        )
                        api_calls += 1
                    except Exception:
                        logger.warning(
                            "Search grounding failed, disabling for remaining calls"
                        )
                        use_grounding = False
                        api_calls += 1

                # Without search grounding, skip — plain calls produce stale results
                if result is None:
                    logger.debug(
                        "Skipping Gemini grounding for interest=%s lang=%s",
                        interest,
                        lang,
                    )
                    continue

                candidates = result.candidates if isinstance(result, ScoutOutput) else []
                for c in candidates:
                    c.interest_query = interest
                    c.source_language = lang
                    if c.url and c.url not in seen_urls:
                        seen_urls.add(c.url)
                        all_candidates.append(c)

        logger.info("Scout discovered %d unique candidates", len(all_candidates))
        return ScoutOutput(candidates=all_candidates, api_calls=api_calls)
