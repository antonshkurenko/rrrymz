"""Stage 4: Technical Analyst – scrape, assess depth, verify claims (batched)."""

from __future__ import annotations

import logging

import trafilatura

from curator.gemini import GeminiClient
from curator.models import AnalysisResult, AnalystOutput, ArchitectOutput, EventCluster

logger = logging.getLogger(__name__)

_MAX_SCRAPED_CHARS = 4000  # Reduced to fit more clusters in batch
_MAX_SNIPPET_CHARS = 500


def _scrape_url(url: str) -> str | None:
    """Scrape article text using trafilatura. Returns None on failure."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return None
        text = trafilatura.extract(downloaded)
        return text[:_MAX_SCRAPED_CHARS] if text else None
    except Exception:
        logger.warning("Scrape failed for %s", url, exc_info=True)
        return None


def _scrape_cluster(cluster: EventCluster) -> tuple[str, bool]:
    """Scrape best content for a cluster. Returns (text, scrape_failed)."""
    scraped_text = _scrape_url(cluster.best_url)
    if scraped_text:
        return scraped_text, False

    # Fallback: try other URLs
    for candidate in cluster.candidates:
        if candidate.url != cluster.best_url:
            scraped_text = _scrape_url(candidate.url)
            if scraped_text:
                return scraped_text, False

    # Final fallback: use snippets
    snippets = " ".join(c.snippet for c in cluster.candidates if c.snippet)
    return snippets[:_MAX_SNIPPET_CHARS] if snippets else "", True


def _build_batch_prompt(cluster_data: list[dict]) -> str:
    items = []
    for cd in cluster_data:
        text_preview = cd["text"][:2000] if cd["text"] else "No content available"
        items.append(
            f'[CLUSTER id="{cd["cluster_id"]}" label="{cd["label"]}"]\n{text_preview}\n[/CLUSTER]'
        )
    items_str = "\n\n".join(items)

    return f"""You are a technical news analyst. Analyze each news cluster below.

{items_str}

For EACH cluster, assess and return a JSON object:
{{
  "analyses": [
    {{
      "cluster_id": "the cluster id",
      "knowledge_depth": 7,
      "key_facts": ["fact 1", "fact 2", "fact 3"],
      "claims_verified": true
    }}
  ]
}}

- knowledge_depth: 1-10, how much substantive new information
- key_facts: 3-5 most important factual claims
- claims_verified: true if facts are internally consistent

Return valid JSON with exactly {len(cluster_data)} analyses, one per cluster."""


class TechnicalAnalyst:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    def run(self, architect_output: ArchitectOutput) -> AnalystOutput:
        clusters = architect_output.clusters
        if not clusters:
            return AnalystOutput(analyses=[], api_calls=0)

        # Step 1: Scrape all clusters (no API calls)
        cluster_data: list[dict] = []
        for cluster in clusters:
            text, scrape_failed = _scrape_cluster(cluster)
            cluster_data.append({
                "cluster_id": cluster.cluster_id,
                "label": cluster.label,
                "best_url": cluster.best_url,
                "text": text,
                "scrape_failed": scrape_failed,
            })

        logger.info("Analyst: scraped %d clusters", len(cluster_data))

        # Step 2: Batch analyze all clusters in one API call
        prompt = _build_batch_prompt(cluster_data)
        api_calls = 0

        try:
            from pydantic import BaseModel, Field

            class ClusterAnalysis(BaseModel):
                cluster_id: str = ""
                knowledge_depth: int = 5
                key_facts: list[str] = Field(default_factory=list)
                claims_verified: bool = False

            class BatchAnalysisResponse(BaseModel):
                analyses: list[ClusterAnalysis] = Field(default_factory=list)

            result = self._client.generate(prompt, response_model=BatchAnalysisResponse)
            api_calls += 1

            # Build lookup from response
            response_map = {}
            if isinstance(result, BatchAnalysisResponse):
                for a in result.analyses:
                    response_map[a.cluster_id] = a

        except Exception:
            logger.exception("Batch analysis failed")
            api_calls += 1
            response_map = {}

        # Step 3: Combine scraped data with analysis results
        analyses: list[AnalysisResult] = []
        for cd in cluster_data:
            analysis = response_map.get(cd["cluster_id"])
            analyses.append(
                AnalysisResult(
                    cluster_id=cd["cluster_id"],
                    label=cd["label"],
                    best_url=cd["best_url"],
                    scraped_text=cd["text"][:2000] if cd["text"] else "",
                    knowledge_depth=analysis.knowledge_depth if analysis else 1,
                    key_facts=analysis.key_facts if analysis else [],
                    claims_verified=analysis.claims_verified if analysis else False,
                    scrape_failed=cd["scrape_failed"],
                )
            )

        logger.info("Analyst: analyzed %d clusters in 1 API call", len(analyses))
        return AnalystOutput(analyses=analyses, api_calls=api_calls)
