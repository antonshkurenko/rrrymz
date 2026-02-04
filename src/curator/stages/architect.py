"""Stage 3: Architect – cluster candidates and dedup against history."""

from __future__ import annotations

import hashlib
import logging

from curator.gemini import GeminiClient
from curator.models import (
    ArchitectOutput,
    EventCluster,
    FilteredCandidate,
    HistoryEntry,
    SentinelOutput,
)

logger = logging.getLogger(__name__)


def compute_cluster_id(urls: list[str]) -> str:
    """Deterministic cluster ID from sorted URLs."""
    canonical = "\n".join(sorted(set(urls)))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _build_cluster_prompt(candidates: list[FilteredCandidate]) -> str:
    items = []
    for i, c in enumerate(candidates):
        items.append(f'{i}. title="{c.title}" url="{c.url}" snippet="{c.snippet}"')
    items_str = "\n".join(items)

    return f"""You are a news clustering engine. Group these candidates by the underlying event
they describe. Candidates covering the same event should be in the same cluster.

Candidates:
{items_str}

Return a JSON object:
{{
  "clusters": [
    {{
      "label": "short descriptive label for the event",
      "candidate_indices": [0, 3, 5],
      "best_index": 0
    }}
  ]
}}

- Each candidate index should appear in exactly one cluster.
- best_index is the candidate with the most comprehensive coverage.
- Return valid JSON only."""


class Architect:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    def run(
        self,
        sentinel_output: SentinelOutput,
        history_window: list[HistoryEntry],
    ) -> ArchitectOutput:
        candidates = sentinel_output.passed
        if not candidates:
            return ArchitectOutput(clusters=[], deduped_count=0, api_calls=0)

        # Step 1: Cluster candidates via Gemini
        prompt = _build_cluster_prompt(candidates)
        api_calls = 0

        try:
            from pydantic import BaseModel, Field

            class ClusterItem(BaseModel):
                label: str = ""
                candidate_indices: list[int] = Field(default_factory=list)
                best_index: int = 0

            class ClusterResponse(BaseModel):
                clusters: list[ClusterItem] = Field(default_factory=list)

            result = self._client.generate(prompt, response_model=ClusterResponse)
            api_calls += 1
            raw_clusters = result.clusters if isinstance(result, ClusterResponse) else []
        except Exception:
            logger.exception("Architect clustering failed, treating each candidate as own cluster")
            api_calls += 1
            raw_clusters = []
            from pydantic import BaseModel, Field

            class ClusterItem(BaseModel):  # type: ignore[no-redef]
                label: str = ""
                candidate_indices: list[int] = Field(default_factory=list)
                best_index: int = 0

            for i, c in enumerate(candidates):
                raw_clusters.append(ClusterItem(label=c.title, candidate_indices=[i], best_index=i))

        # Step 2: Build EventClusters with deterministic IDs
        clusters: list[EventCluster] = []
        history_urls: set[str] = set()
        for h in history_window:
            history_urls.update(h.urls)

        deduped_count = 0

        for rc in raw_clusters:
            cluster_candidates = [
                candidates[idx]
                for idx in rc.candidate_indices
                if idx < len(candidates)
            ]
            if not cluster_candidates:
                continue

            urls = [c.url for c in cluster_candidates]
            cluster_id = compute_cluster_id(urls)
            best_idx = rc.best_index if rc.best_index < len(candidates) else rc.candidate_indices[0]
            best_url = candidates[best_idx].url if best_idx < len(candidates) else urls[0]

            # Check if cluster overlaps significantly with history
            overlap = sum(1 for u in urls if u in history_urls)
            is_dup = overlap > len(urls) * 0.5

            cluster = EventCluster(
                cluster_id=cluster_id,
                label=rc.label,
                candidates=cluster_candidates,
                best_url=best_url,
                is_duplicate_of_history=is_dup,
            )

            if is_dup:
                deduped_count += 1
                logger.info("Deduped cluster %s: %s", cluster_id, rc.label)
            else:
                clusters.append(cluster)

        logger.info(
            "Architect: %d clusters formed, %d deduped against history",
            len(clusters),
            deduped_count,
        )

        return ArchitectOutput(
            clusters=clusters,
            deduped_count=deduped_count,
            api_calls=api_calls,
        )
