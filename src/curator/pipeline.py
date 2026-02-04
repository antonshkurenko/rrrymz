"""Pipeline orchestrator – runs all stages sequentially."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from curator.config import Settings
from curator.gemini import GeminiClient
from curator.history import HistoryManager
from curator.memory import parse_memory
from curator.models import (
    ArchiveEntry,
    ArchiveIndex,
    DailyDigest,
    HistoryEntry,
    PipelineMetadata,
)
from curator.stages.analyst import TechnicalAnalyst
from curator.stages.architect import Architect
from curator.stages.editor import MasterEditor
from curator.stages.scout import PolyglotScout
from curator.stages.sentinel import Sentinel

logger = logging.getLogger(__name__)


def run_pipeline(settings: Settings) -> DailyDigest:
    """Execute the full pipeline and return the daily digest."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    # Initialize
    client = GeminiClient(settings)
    persona = parse_memory(settings.memory_path)
    history_mgr = HistoryManager(settings)
    history_mgr.load()
    history_mgr.apply_retention()

    today = date.today().isoformat()
    total_api_calls = 0

    # Stage 1: Scout
    logger.info("=== Stage 1: Scout ===")
    scout = PolyglotScout(client, settings)
    last_run_date = history_mgr.data.last_updated or None
    scout_output = scout.run(persona, last_run_date=last_run_date)
    total_api_calls += scout_output.api_calls
    logger.info("Discovered %d candidates", len(scout_output.candidates))

    if not scout_output.candidates:
        logger.warning(
            "No candidates discovered. Search grounding may be unavailable "
            "(check your Gemini API quota at https://ai.dev/rate-limit)."
        )

    # Stage 2: Sentinel
    logger.info("=== Stage 2: Sentinel ===")
    sentinel = Sentinel(client, settings)
    sentinel_output = sentinel.run(scout_output, persona)
    total_api_calls += sentinel_output.api_calls
    logger.info(
        "After filtering: %d passed, %d filtered",
        len(sentinel_output.passed),
        sentinel_output.filtered_count,
    )

    # Stage 3: Architect
    logger.info("=== Stage 3: Architect ===")
    architect = Architect(client)
    history_window = history_mgr.get_dedup_window()
    architect_output = architect.run(sentinel_output, history_window)
    total_api_calls += architect_output.api_calls
    logger.info(
        "Clusters: %d formed, %d deduped",
        len(architect_output.clusters),
        architect_output.deduped_count,
    )

    # Stage 4: Analyst
    logger.info("=== Stage 4: Analyst ===")
    analyst = TechnicalAnalyst(client)
    analyst_output = analyst.run(architect_output)
    total_api_calls += analyst_output.api_calls
    logger.info("Analyzed %d clusters", len(analyst_output.analyses))

    # Stage 5: Editor
    logger.info("=== Stage 5: Editor ===")
    editor = MasterEditor(client, settings)
    stories = editor.run(analyst_output)
    total_api_calls += client.call_count - total_api_calls  # Capture editor calls

    # Build digest
    digest = DailyDigest(
        date=today,
        stories=stories,
        metadata=PipelineMetadata(
            run_date=today,
            total_discovered=len(scout_output.candidates),
            after_sentinel=len(sentinel_output.passed),
            clusters_formed=len(architect_output.clusters) + architect_output.deduped_count,
            after_dedup=len(architect_output.clusters),
            stories_published=len(stories),
            total_api_calls=client.call_count,
        ),
    )

    # Update history with new clusters
    new_entries = [
        HistoryEntry(
            cluster_id=cluster.cluster_id,
            label=cluster.label,
            urls=[c.url for c in cluster.candidates],
            first_seen=today,
            last_seen=today,
        )
        for cluster in architect_output.clusters
    ]
    history_mgr.add_entries(new_entries)
    history_mgr.save()

    # Write output
    output_path = Path(settings.output_path)
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    digest_json = digest.model_dump_json(indent=2) + "\n"

    # Write latest.json
    output_path.write_text(digest_json, encoding="utf-8")

    # Write dated archive file (YYYY-MM-DD.json)
    dated_filename = f"{today}.json"
    dated_path = output_dir / dated_filename
    dated_path.write_text(digest_json, encoding="utf-8")

    # Update archive index
    archive_path = output_dir / "archive.json"
    if archive_path.exists():
        import json

        archive = ArchiveIndex.model_validate(json.loads(archive_path.read_text(encoding="utf-8")))
    else:
        archive = ArchiveIndex()

    # Replace existing entry for today or append
    archive.digests = [e for e in archive.digests if e.date != today]
    archive.digests.insert(
        0,
        ArchiveEntry(date=today, file=dated_filename, story_count=len(stories)),
    )
    archive.digests.sort(key=lambda e: e.date, reverse=True)
    archive_path.write_text(
        archive.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    logger.info("Wrote digest to %s and %s (%d stories)", output_path, dated_path, len(stories))

    return digest


def main() -> None:
    """CLI entry point."""
    settings = Settings.from_env()
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY environment variable is required")
    run_pipeline(settings)
