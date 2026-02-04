"""Tests for custom RSS feed source."""

from datetime import datetime, timezone
from unittest.mock import patch

from curator.sources.rss_feeds import fetch_rss_feeds, load_feed_urls


def test_load_feed_urls(tmp_path):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_text(
        "# Comment line\n"
        "https://example.com/feed1.xml\n"
        "\n"
        "  # Another comment\n"
        "https://example.com/feed2.xml\n"
        "  https://example.com/feed3.xml  \n"
    )

    urls = load_feed_urls(str(feeds_file))
    assert urls == [
        "https://example.com/feed1.xml",
        "https://example.com/feed2.xml",
        "https://example.com/feed3.xml",
    ]


def test_load_feed_urls_missing_file(tmp_path):
    assert load_feed_urls(str(tmp_path / "nonexistent.txt")) == []


def test_load_feed_urls_empty_file(tmp_path):
    feeds_file = tmp_path / "feeds.txt"
    feeds_file.write_text("# Only comments\n# Nothing here\n")
    assert load_feed_urls(str(feeds_file)) == []


def _make_feed(entries):
    class Feed:
        bozo = False
        bozo_exception = None

    feed = Feed()
    feed.entries = entries
    return feed


def _make_entry(title, link, summary="", published_parsed=None, updated_parsed=None):
    entry = {"title": title, "link": link, "summary": summary}
    if published_parsed:
        entry["published_parsed"] = published_parsed
    if updated_parsed:
        entry["updated_parsed"] = updated_parsed
    return entry


def test_fetch_rss_feeds_basic():
    entries = [
        _make_entry(
            "Story A",
            "https://example.com/a",
            "Summary A.",
            published_parsed=(2026, 2, 2, 10, 0, 0, 0, 0, 0),
        ),
        _make_entry(
            "Story B",
            "https://example.com/b",
            "Summary B.",
            published_parsed=(2026, 2, 2, 8, 0, 0, 0, 0, 0),
        ),
    ]

    with patch("curator.sources.rss_feeds.feedparser") as mock_fp:
        mock_fp.parse.return_value = _make_feed(entries)
        result = fetch_rss_feeds(["https://example.com/feed.xml"])

    assert len(result) == 2
    assert result[0].title == "Story A"
    assert result[0].interest_query == "rss"


def test_fetch_rss_feeds_filters_by_since():
    entries = [
        _make_entry(
            "New",
            "https://example.com/new",
            "Recent.",
            published_parsed=(2026, 2, 2, 10, 0, 0, 0, 0, 0),
        ),
        _make_entry(
            "Old",
            "https://example.com/old",
            "Ancient.",
            published_parsed=(2026, 1, 1, 10, 0, 0, 0, 0, 0),
        ),
    ]
    since = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    with patch("curator.sources.rss_feeds.feedparser") as mock_fp:
        mock_fp.parse.return_value = _make_feed(entries)
        result = fetch_rss_feeds(["https://example.com/feed.xml"], since=since)

    assert len(result) == 1
    assert result[0].title == "New"


def test_fetch_rss_feeds_uses_updated_date():
    """Falls back to updated_parsed when published_parsed is missing."""
    entries = [
        _make_entry(
            "Updated Only",
            "https://example.com/updated",
            "Has updated date.",
            updated_parsed=(2026, 2, 2, 10, 0, 0, 0, 0, 0),
        ),
    ]
    since = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    with patch("curator.sources.rss_feeds.feedparser") as mock_fp:
        mock_fp.parse.return_value = _make_feed(entries)
        result = fetch_rss_feeds(["https://example.com/feed.xml"], since=since)

    assert len(result) == 1


def test_fetch_rss_feeds_handles_failure():
    with patch("curator.sources.rss_feeds.feedparser") as mock_fp:
        mock_fp.parse.side_effect = Exception("network error")
        result = fetch_rss_feeds(["https://example.com/feed.xml"])

    assert result == []


def test_fetch_rss_feeds_multiple_feeds():
    entries1 = [_make_entry("Feed1 Story", "https://example.com/f1", "From feed 1.")]
    entries2 = [_make_entry("Feed2 Story", "https://example.com/f2", "From feed 2.")]

    call_count = 0

    def mock_parse(url):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _make_feed(entries1)
        return _make_feed(entries2)

    with patch("curator.sources.rss_feeds.feedparser") as mock_fp:
        mock_fp.parse.side_effect = mock_parse
        result = fetch_rss_feeds(
            ["https://example.com/feed1.xml", "https://example.com/feed2.xml"]
        )

    assert len(result) == 2
    assert result[0].title == "Feed1 Story"
    assert result[1].title == "Feed2 Story"
