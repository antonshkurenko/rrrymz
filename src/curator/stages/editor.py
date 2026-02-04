"""Stage 5: Master Editor – synthesize, score, threshold filter."""

from __future__ import annotations

import logging

from curator.config import Settings
from curator.gemini import GeminiClient
from curator.models import (
    AnalysisResult,
    AnalystOutput,
    CurationMetrics,
    DigestStory,
)

logger = logging.getLogger(__name__)


def _build_editor_prompt(analyses: list[AnalysisResult]) -> str:
    items = []
    for a in analyses:
        facts_str = "; ".join(a.key_facts) if a.key_facts else "no key facts extracted"
        items.append(
            f'cluster_id="{a.cluster_id}" label="{a.label}" '
            f"depth={a.knowledge_depth} verified={a.claims_verified} "
            f"facts=[{facts_str}] "
            f'text_preview="{a.scraped_text[:500]}"'
        )
    items_str = "\n\n".join(items)

    return f"""You are a master news editor. For each story cluster below, write a polished
digest entry and score it.

Stories:
{items_str}

For each story, return:
{{
  "stories": [
    {{
      "cluster_id": "the cluster_id",
      "headline": "concise, engaging headline (max 100 chars)",
      "core_fact": "single most important fact (1 sentence)",
      "summary": "2-3 sentence summary with context and significance",
      "metrics": {{
        "breaking": 7,
        "importance": 8,
        "snr": 6
      }}
    }}
  ]
}}

Scoring guide:
- breaking (1-10): How time-sensitive? 10 = happening right now, 1 = old/evergreen
- importance (1-10): How significant globally? 10 = world-changing, 1 = trivial
- snr (1-10): Signal-to-noise ratio. 10 = pure substance, 1 = mostly filler/clickbait

Return valid JSON only."""


class MasterEditor:
    def __init__(self, client: GeminiClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def run(self, analyst_output: AnalystOutput) -> list[DigestStory]:
        analyses = analyst_output.analyses
        if not analyses:
            return []

        prompt = _build_editor_prompt(analyses)

        try:
            from pydantic import BaseModel, Field

            class StoryDraft(BaseModel):
                cluster_id: str = ""
                headline: str = ""
                core_fact: str = ""
                summary: str = ""
                metrics: CurationMetrics = Field(default_factory=CurationMetrics)

            class EditorResponse(BaseModel):
                stories: list[StoryDraft] = Field(default_factory=list)

            result = self._client.generate(prompt, response_model=EditorResponse)
            drafts = result.stories if isinstance(result, EditorResponse) else []
        except Exception:
            logger.exception("Editor synthesis failed")
            return []

        # Build lookup for sources
        analysis_map = {a.cluster_id: a for a in analyses}

        # Apply thresholds and build final stories
        stories: list[DigestStory] = []
        for draft in drafts:
            m = draft.metrics
            snr_ok = m.snr >= self._settings.editor_snr_threshold
            breaking_ok = m.breaking >= self._settings.editor_breaking_threshold
            importance_ok = m.importance >= self._settings.editor_importance_threshold

            if snr_ok and (breaking_ok or importance_ok):
                analysis = analysis_map.get(draft.cluster_id)
                sources = []
                if analysis:
                    sources = [analysis.best_url]
                    for c in analysis_map.get(draft.cluster_id, analysis).key_facts:
                        pass  # key_facts aren't URLs
                    # Collect all candidate URLs from the analysis
                    if analysis.best_url:
                        sources = [analysis.best_url]

                stories.append(
                    DigestStory(
                        cluster_id=draft.cluster_id,
                        headline=draft.headline,
                        core_fact=draft.core_fact,
                        summary=draft.summary,
                        sources=sources,
                        metrics=draft.metrics,
                        label=analysis.label if analysis else "",
                    )
                )

        # Sort: breaking first, then importance
        stories.sort(key=lambda s: (s.metrics.breaking, s.metrics.importance), reverse=True)

        logger.info(
            "Editor: %d/%d stories passed thresholds",
            len(stories),
            len(drafts),
        )

        return stories
