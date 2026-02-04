"""Stage 4: Technical Analyst – scrape, assess depth, verify claims."""

from __future__ import annotations

import logging

import trafilatura

from curator.gemini import GeminiClient
from curator.models import AnalysisResult, AnalystOutput, ArchitectOutput, EventCluster

logger = logging.getLogger(__name__)

_MAX_SCRAPED_CHARS = 8000


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


def _build_analysis_prompt(label: str, scraped_text: str) -> str:
    truncated = scraped_text[:_MAX_SCRAPED_CHARS]
    return f"""You are a technical news analyst. Analyze this article about: {label}

Article text:
{truncated}

Assess the article and return a JSON object:
{{
  "knowledge_depth": 7,
  "key_facts": ["fact 1", "fact 2", "fact 3"],
  "claims_verified": true
}}

- knowledge_depth: 1-10, how much substantive new information the article provides
- key_facts: 3-5 most important factual claims from the article
- claims_verified: true if the key facts are internally consistent and supported
- Return valid JSON only."""


class TechnicalAnalyst:
    def __init__(self, client: GeminiClient) -> None:
        self._client = client

    def run(self, architect_output: ArchitectOutput) -> AnalystOutput:
        analyses: list[AnalysisResult] = []
        api_calls = 0

        for cluster in architect_output.clusters:
            analysis = self._analyze_cluster(cluster)
            api_calls += analysis.get("api_calls", 0)
            analyses.append(analysis["result"])

        logger.info("Analyst: analyzed %d clusters", len(analyses))
        return AnalystOutput(analyses=analyses, api_calls=api_calls)

    def _analyze_cluster(self, cluster: EventCluster) -> dict:
        # Try scraping the best URL
        scraped_text = _scrape_url(cluster.best_url)
        scrape_failed = scraped_text is None

        # Fallback: try other URLs in the cluster
        if scrape_failed:
            for candidate in cluster.candidates:
                if candidate.url != cluster.best_url:
                    scraped_text = _scrape_url(candidate.url)
                    if scraped_text:
                        scrape_failed = False
                        break

        if scraped_text is None:
            # Use snippets as fallback content
            scraped_text = " ".join(c.snippet for c in cluster.candidates if c.snippet)
            scrape_failed = True

        api_calls = 0

        if scraped_text.strip():
            prompt = _build_analysis_prompt(cluster.label, scraped_text)
            try:
                from pydantic import BaseModel, Field

                class AnalysisResponse(BaseModel):
                    knowledge_depth: int = 5
                    key_facts: list[str] = Field(default_factory=list)
                    claims_verified: bool = False

                result = self._client.generate(prompt, response_model=AnalysisResponse)
                api_calls += 1

                return {
                    "result": AnalysisResult(
                        cluster_id=cluster.cluster_id,
                        label=cluster.label,
                        best_url=cluster.best_url,
                        scraped_text=scraped_text[:2000],
                        knowledge_depth=result.knowledge_depth
                        if isinstance(result, AnalysisResponse)
                        else 5,
                        key_facts=result.key_facts if isinstance(result, AnalysisResponse) else [],
                        claims_verified=result.claims_verified
                        if isinstance(result, AnalysisResponse)
                        else False,
                        scrape_failed=scrape_failed,
                    ),
                    "api_calls": api_calls,
                }
            except Exception:
                logger.exception("Analysis failed for cluster %s", cluster.cluster_id)
                api_calls += 1

        return {
            "result": AnalysisResult(
                cluster_id=cluster.cluster_id,
                label=cluster.label,
                best_url=cluster.best_url,
                scraped_text=scraped_text[:2000] if scraped_text else "",
                knowledge_depth=1,
                key_facts=[],
                claims_verified=False,
                scrape_failed=scrape_failed,
            ),
            "api_calls": api_calls,
        }
