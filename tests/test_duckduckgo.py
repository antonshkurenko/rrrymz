"""Tests for DuckDuckGo news source."""

from datetime import datetime, timezone
from unittest.mock import patch

from curator.sources.duckduckgo import _parse_ddg_date, fetch_duckduckgo_news


def test_parse_ddg_date_iso():
    result = _parse_ddg_date("2026-02-02T10:00:00+00:00")
    assert result == datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)


def test_parse_ddg_date_z_suffix():
    result = _parse_ddg_date("2026-02-02T10:00:00Z")
    assert result is not None
    assert result.year == 2026


def test_parse_ddg_date_compact():
    result = _parse_ddg_date("20260202T100000")
    assert result == datetime(2026, 2, 2, 10, 0, 0, tzinfo=timezone.utc)


def test_parse_ddg_date_empty():
    assert _parse_ddg_date("") is None
    assert _parse_ddg_date("not-a-date") is None


def test_fetch_duckduckgo_news_basic():
    mock_results = [
        {
            "title": "AI News",
            "url": "https://example.com/ai",
            "body": "AI stuff happened.",
            "date": "2026-02-02T10:00:00+00:00",
        },
        {
            "title": "Space News",
            "url": "https://example.com/space",
            "body": "Space stuff.",
            "date": "2026-02-02T08:00:00+00:00",
        },
    ]

    with patch("curator.sources.duckduckgo.DDGS") as mock_ddgs:
        mock_ddgs.return_value.news.return_value = mock_results
        result = fetch_duckduckgo_news("AI")

    assert len(result) == 2
    assert result[0].title == "AI News"
    assert result[0].url == "https://example.com/ai"
    assert result[0].interest_query == "AI"


def test_fetch_duckduckgo_news_filters_by_since():
    mock_results = [
        {
            "title": "New",
            "url": "https://example.com/new",
            "body": "Recent.",
            "date": "2026-02-02T10:00:00+00:00",
        },
        {
            "title": "Old",
            "url": "https://example.com/old",
            "body": "Ancient.",
            "date": "2026-01-01T10:00:00+00:00",
        },
    ]
    since = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)

    with patch("curator.sources.duckduckgo.DDGS") as mock_ddgs:
        mock_ddgs.return_value.news.return_value = mock_results
        result = fetch_duckduckgo_news("AI", since=since)

    assert len(result) == 1
    assert result[0].title == "New"


def test_fetch_duckduckgo_news_handles_failure():
    with patch("curator.sources.duckduckgo.DDGS") as mock_ddgs:
        mock_ddgs.return_value.news.side_effect = Exception("network error")
        result = fetch_duckduckgo_news("AI")

    assert result == []


def test_fetch_duckduckgo_news_skips_empty():
    mock_results = [
        {"title": "", "url": "https://example.com/no-title", "body": "x", "date": ""},
        {"title": "Good", "url": "https://example.com/good", "body": "ok", "date": ""},
    ]

    with patch("curator.sources.duckduckgo.DDGS") as mock_ddgs:
        mock_ddgs.return_value.news.return_value = mock_results
        result = fetch_duckduckgo_news("AI")

    assert len(result) == 1
    assert result[0].title == "Good"
