# rrrymz

AI News Curator – a serverless multi-agent pipeline that discovers, verifies, and deduplicates global news using Gemini.

## How it works

A 5-stage pipeline runs daily via GitHub Actions:

1. **Scout** – Searches for news across multiple languages using Gemini's search grounding
2. **Sentinel** – Filters by user preferences (muted topics, snoozes) and Gemini relevance scoring
3. **Architect** – Clusters related articles and deduplicates against recent history
4. **Analyst** – Scrapes articles, assesses depth, extracts key facts, verifies claims
5. **Editor** – Synthesizes headlines/summaries, scores stories, applies quality thresholds

Output is a static JSON file consumed by a single-page React frontend on GitHub Pages.

## Setup

1. Clone this repo
2. Install [uv](https://docs.astral.sh/uv/)
3. Copy `.env.example` to `.env` and add your `GEMINI_API_KEY`
4. Run:

```bash
uv sync
uv run curator-run
```

5. Open `frontend/index.html` to view the digest

## Development

```bash
uv run pytest          # Run tests
uv run ruff check src/ tests/  # Lint
```

## Configuration

All settings are controlled via environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Google AI API key |
| `GEMINI_MODEL_ID` | `gemini-3-flash-preview` | Model to use |
| `SCOUT_LANGUAGES` | `en,fr,es` | Languages to search |
| `SENTINEL_RELEVANCE_THRESHOLD` | `0.6` | Minimum relevance score |
| `EDITOR_SNR_THRESHOLD` | `4` | Minimum signal-to-noise |
| `EDITOR_BREAKING_THRESHOLD` | `8` | Breaking news threshold |
| `EDITOR_IMPORTANCE_THRESHOLD` | `7` | Importance threshold |

## Feedback

Use GitHub Issues to provide feedback on stories:
- **Like**: Creates a "feedback:like" issue
- **Dislike**: Creates a "feedback:dislike" issue

Feedback is processed monthly to adjust the user persona in `data/memory.md`.
