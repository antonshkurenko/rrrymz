# rrrymz – AI News Curator

## Project structure
- `src/curator/` – Python package with pipeline stages
- `tests/` – pytest tests (all use mocked Gemini)
- `data/` – memory.md (user persona) + history.json (cluster history)
- `output/` – latest.json (daily digest)
- `frontend/` – Single-file React/Tailwind app (no build step)

## Commands
- `uv sync` – Install dependencies
- `uv run pytest` – Run tests
- `uv run ruff check src/ tests/` – Lint
- `uv run curator-run` – Run full pipeline (needs GEMINI_API_KEY)

## Architecture
5-stage pipeline: Scout → Sentinel → Architect → Analyst → Editor
- Scout: Gemini search grounding, multi-language news discovery
- Sentinel: Rule-based + Gemini batch filtering
- Architect: Cluster + dedup against history
- Analyst: Scrape + assess + verify
- Editor: Synthesize + score + threshold

## Key conventions
- All Gemini calls go through `GeminiClient` in `gemini.py`
- Data models in `models.py` (Pydantic v2)
- Config from env vars via `Settings.from_env()`
- Tests mock `GeminiClient` – never call real API in tests
- Cluster IDs: SHA-256 of sorted URLs (first 16 hex chars)
