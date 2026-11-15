"""Central LLM/embedding provider configuration.

The agents only need an OpenAI-compatible chat-completions endpoint. These
helpers let the deployment point every feature at a self-hosted or custom
provider through LLM_* variables while keeping the OPENAI_* names working.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"


@dataclass(frozen=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def get_llm_config(feature: str | None = None) -> LLMConfig:
    """Resolve the provider for a feature (advisor, app_control, detect, ...)."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    base_url = (
        os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")
    model = os.getenv("LLM_MODEL") or os.getenv("ADVISOR_MODEL") or DEFAULT_MODEL

    if feature == "app_control":
        model = os.getenv("APP_CONTROL_MODEL") or model
    elif feature == "detect":
        model = os.getenv("DETECT_MODEL") or model
    elif feature == "summary":
        model = os.getenv("SUMMARY_MODEL") or model

    return LLMConfig(api_key=api_key, base_url=base_url, model=model)


def get_embedding_config() -> LLMConfig:
    """Embeddings may use the same provider or a dedicated one."""
    api_key = os.getenv("EMBEDDING_API_KEY") or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or None
    base_url = (
        os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("LLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")
    model = os.getenv("EMBEDDING_MODEL") or DEFAULT_EMBEDDING_MODEL
    return LLMConfig(api_key=api_key, base_url=base_url, model=model)


def llm_configured(feature: str | None = None) -> bool:
    """A key is optional for self-hosted providers; a base URL is required."""
    return bool(get_llm_config(feature).base_url)
