"""Tests for Google News RSS source."""

from datetime import datetime, timezone
from unittest.mock import patch

from curator.sources.google_news import _strip_html, fetch_google_news


def test_strip_html():
    assert _strip_html("<b>Hello</b> &amp; world") == "Hello & world"
    assert _strip_html("plain text") == "plain text"
    assert _strip_html("<a href='x'>link</a>") == "link"


def _make_feed(entries):
    """Create a mock feedparser result."""

    class Feed:
        bozo = False
        bozo_exception = None

    feed = Feed()
    feed.entries = entries
    return feed


def _make_entry(title, link, summary="", published_parsed=None):
    return {
        "title": title,
        "link": link,
        "summary": summary,
        "published_parsed": published_parsed,
    }


def test_fetch_google_news_basic():
    entries = [
        _make_entry(
            "AI Breakthrough",
            "https://example.com/ai",
            "Big news.",
            (2026, 2, 2, 10, 0, 0, 0, 0, 0),
        ),
        _make_entry(
            "Space Launch",
            "https://example.com/space",
            "Launch today.",
            (2026, 2, 2, 8, 0, 0, 0, 0, 0),
        ),
    ]

    with patch("curator.sources.google_news.feedparser") as mock_fp:
        mock_fp.parse.return_value = _make_feed(entries)
        result = fetch_google_news("AI")

    assert len(result) == 2
    assert result[0].title == "AI Breakthrough"
    assert result[0].url == "https://example.com/ai"
    assert result[0].interest_query == "AI"


def test_fetch_google_news_filters_by_since():
    entries = [
        _make_entry(
            "New Story",
            "https://example.com/new",
            "Recent.",
            (2026, 2, 2, 10, 0, 0, 0, 0, 0),
        ),
        _make_entry(
            "Old Story",
            "https://example.com/old",
            "Ancient.",
            (2026, 1, 1, 10, 0, 0, 0, 0, 0),
        ),
    ]
    since = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    with patch("curator.sources.google_news.feedparser") as mock_fp:
        mock_fp.parse.return_value = _make_feed(entries)
        result = fetch_google_news("AI", since=since)

    assert len(result) == 1
    assert result[0].title == "New Story"


def test_fetch_google_news_handles_failure():
    with patch("curator.sources.google_news.feedparser") as mock_fp:
        mock_fp.parse.side_effect = Exception("network error")
        result = fetch_google_news("AI")

    assert result == []


def test_fetch_google_news_skips_empty_entries():
    entries = [
        _make_entry("", "https://example.com/no-title", "snippet"),
        _make_entry("Has Title", "", "snippet"),
        _make_entry("Good", "https://example.com/good", "ok"),
    ]

    with patch("curator.sources.google_news.feedparser") as mock_fp:
        mock_fp.parse.return_value = _make_feed(entries)
        result = fetch_google_news("AI")

    assert len(result) == 1
    assert result[0].title == "Good"
