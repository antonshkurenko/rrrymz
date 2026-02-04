"""Thin wrapper around the Google GenAI client with structured output and retry."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, TypeVar

from google import genai
from google.genai import types
from pydantic import BaseModel

from curator.config import Settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

_MAX_RETRIES = 5
_INITIAL_BACKOFF = 5.0
_CALL_DELAY = 2.0  # seconds between calls to stay within free-tier RPM


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model_id = settings.model_id
        self.call_count = 0
        self._last_call_time: float = 0.0

    def generate(
        self,
        prompt: str,
        *,
        response_model: type[T] | None = None,
        use_search_grounding: bool = False,
        temperature: float = 0.2,
    ) -> str | T:
        """Generate content, optionally with structured output or search grounding.

        If response_model is provided AND use_search_grounding is False, uses native
        structured output. Otherwise falls back to manual JSON parsing.
        """
        config_kwargs: dict[str, Any] = {"temperature": temperature}
        tools: list[types.Tool] | None = None

        if use_search_grounding:
            tools = [types.Tool(google_search=types.GoogleSearch())]

        use_native_schema = response_model is not None and not use_search_grounding

        if use_native_schema:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_model

        config = types.GenerateContentConfig(**config_kwargs)

        # Rate-limit: wait between calls to avoid hitting RPM quota
        now = time.monotonic()
        elapsed = now - self._last_call_time
        if self._last_call_time > 0 and elapsed < _CALL_DELAY:
            time.sleep(_CALL_DELAY - elapsed)

        response_text = self._call_with_retry(prompt, config, tools)
        self._last_call_time = time.monotonic()
        self.call_count += 1

        if response_model is None:
            return response_text

        if use_native_schema:
            return response_model.model_validate_json(response_text)

        # Fallback: parse JSON from free-text response
        return self._parse_model_from_text(response_text, response_model)

    def _call_with_retry(
        self,
        prompt: str,
        config: types.GenerateContentConfig,
        tools: list[types.Tool] | None,
    ) -> str:
        backoff = _INITIAL_BACKOFF
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES):
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model_id,
                    "contents": prompt,
                    "config": config,
                }
                if tools:
                    kwargs["config"] = types.GenerateContentConfig(
                        temperature=config.temperature,
                        tools=tools,
                    )
                response = self._client.models.generate_content(**kwargs)
                return response.text or ""
            except Exception as exc:
                last_exc = exc
                is_rate_limit = "429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)

                # Check if quota is hard-zero (limit: 0) — no point retrying
                if is_rate_limit and "limit: 0" in str(exc):
                    logger.warning("Quota is zero, not retrying: %s", exc)
                    break

                if attempt < _MAX_RETRIES - 1:
                    wait = min(backoff, 15.0) if is_rate_limit else backoff
                    logger.warning(
                        "Gemini call failed (attempt %d/%d), retrying in %.0fs: %s",
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                    backoff *= 2

        raise RuntimeError("Gemini call failed after retries") from last_exc

    @staticmethod
    def _parse_model_from_text(text: str, model: type[T]) -> T:
        """Extract JSON from text that may contain markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            json_lines = []
            in_fence = False
            for line in lines:
                if line.strip().startswith("```") and not in_fence:
                    in_fence = True
                    continue
                if line.strip() == "```" and in_fence:
                    break
                if in_fence:
                    json_lines.append(line)
            cleaned = "\n".join(json_lines)

        try:
            return model.model_validate_json(cleaned)
        except Exception:
            # Last resort: find first { and last }
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                return model.model_validate(json.loads(cleaned[start : end + 1]))
            # Try array
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start != -1 and end != -1:
                data = json.loads(cleaned[start : end + 1])
                return model.model_validate(data)
            raise
