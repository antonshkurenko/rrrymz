"""Stage 2: Sentinel – two-phase filtering (rule-based + Gemini batch)."""

from __future__ import annotations

import logging

from curator.config import Settings
from curator.gemini import GeminiClient
from curator.memory import is_topic_muted, is_topic_snoozed
from curator.models import (
    DiscoveryCandidate,
    FilteredCandidate,
    ScoutOutput,
    SentinelOutput,
    UserPersona,
)

logger = logging.getLogger(__name__)


def _build_batch_prompt(candidates: list[DiscoveryCandidate], persona: UserPersona) -> str:
    interests_str = ", ".join(persona.interests)
    items = []
    for i, c in enumerate(candidates):
        items.append(f"{i}. [{c.title}] — {c.snippet}")
    items_str = "\n".join(items)

    return f"""You are a news relevance filter. The user is interested in: {interests_str}

Rate each candidate's relevance from 0.0 to 1.0 based on how well it matches these interests.

Candidates:
{items_str}

Return a JSON object:
{{
  "scores": [0.85, 0.3, ...]
}}

The scores array must have exactly {len(candidates)} entries, one per candidate, in order.
Return valid JSON only."""


class Sentinel:
    def __init__(self, client: GeminiClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def run(self, scout_output: ScoutOutput, persona: UserPersona) -> SentinelOutput:
        # Phase 1: Rule-based filtering (muted/snoozed topics)
        phase1_passed: list[DiscoveryCandidate] = []
        filtered_count = 0

        for candidate in scout_output.candidates:
            text = f"{candidate.title} {candidate.snippet}"
            if is_topic_muted(persona, text) or is_topic_snoozed(persona, text):
                filtered_count += 1
                continue
            phase1_passed.append(candidate)

        logger.info(
            "Sentinel phase 1: %d/%d passed (rule-based)",
            len(phase1_passed),
            len(scout_output.candidates),
        )

        if not phase1_passed:
            return SentinelOutput(passed=[], filtered_count=filtered_count, api_calls=0)

        # Phase 2: Gemini batch relevance scoring
        api_calls = 0
        prompt = _build_batch_prompt(phase1_passed, persona)
        threshold = self._settings.sentinel_relevance_threshold

        try:
            from pydantic import BaseModel, Field

            class ScoresResponse(BaseModel):
                scores: list[float] = Field(default_factory=list)

            result = self._client.generate(prompt, response_model=ScoresResponse)
            api_calls += 1

            scores = result.scores if isinstance(result, ScoresResponse) else []
        except Exception:
            logger.exception("Sentinel batch scoring failed, passing all through")
            api_calls += 1
            scores = [1.0] * len(phase1_passed)

        passed: list[FilteredCandidate] = []
        for i, candidate in enumerate(phase1_passed):
            score = scores[i] if i < len(scores) else 0.0
            if score >= threshold:
                passed.append(
                    FilteredCandidate(
                        title=candidate.title,
                        url=candidate.url,
                        snippet=candidate.snippet,
                        source_language=candidate.source_language,
                        interest_query=candidate.interest_query,
                        relevance_score=score,
                    )
                )
            else:
                filtered_count += 1

        logger.info(
            "Sentinel phase 2: %d/%d passed (relevance >= %.1f)",
            len(passed),
            len(phase1_passed),
            threshold,
        )

        return SentinelOutput(
            passed=passed,
            filtered_count=filtered_count,
            api_calls=api_calls,
        )
