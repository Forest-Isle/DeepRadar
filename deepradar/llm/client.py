from __future__ import annotations

import logging
from typing import Any

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around Claude API with retry and token tracking."""

    def __init__(self, config: dict[str, Any]) -> None:
        llm_cfg = config.get("settings", {}).get("llm", {})
        api_key = config.get("settings", {}).get("anthropic_api_key", "")
        self.model = llm_cfg.get("model", "claude-sonnet-4-20250514")
        self.max_tokens = llm_cfg.get("max_tokens_per_request", 4096)
        self.temperature = llm_cfg.get("temperature", 0.3)
        base_url = llm_cfg.get("base_url") or None
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((anthropic.RateLimitError, anthropic.APIConnectionError)),
    )
    def complete(self, system: str, user_message: str) -> str:
        """Send a message to Claude and return the response text."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        return response.content[0].text

    def get_usage_stats(self) -> dict[str, int]:
        return {
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
        }
