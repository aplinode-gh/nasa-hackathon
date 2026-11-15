"""Tests for provider-agnostic LLM configuration."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.ai.llm import get_embedding_config, get_llm_config, llm_configured  # noqa: E402

CLEAR_KEYS = {
    key: ""
    for key in (
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "ADVISOR_MODEL",
        "APP_CONTROL_MODEL",
        "DETECT_MODEL",
        "SUMMARY_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
    )
}


class LLMConfigTests(unittest.TestCase):
    def test_custom_provider(self) -> None:
        with patch.dict(os.environ, {**CLEAR_KEYS, "LLM_API_KEY": "k", "LLM_BASE_URL": "http://localhost:8000/v1", "LLM_MODEL": "nasa-agri-1"}, clear=False):
            config = get_llm_config()
            self.assertEqual(config.api_key, "k")
            self.assertEqual(config.base_url, "http://localhost:8000/v1")
            self.assertEqual(config.model, "nasa-agri-1")
            self.assertEqual(config.headers["Authorization"], "Bearer k")

    def test_openai_fallback(self) -> None:
        with patch.dict(os.environ, {**CLEAR_KEYS, "OPENAI_API_KEY": "o", "OPENAI_BASE_URL": "https://api.openai.com/v1", "ADVISOR_MODEL": "gpt-4o-mini"}, clear=False):
            config = get_llm_config()
            self.assertEqual(config.api_key, "o")
            self.assertEqual(config.model, "gpt-4o-mini")

    def test_feature_model_overrides(self) -> None:
        with patch.dict(os.environ, {**CLEAR_KEYS, "LLM_MODEL": "base", "APP_CONTROL_MODEL": "app", "DETECT_MODEL": "vision"}, clear=False):
            self.assertEqual(get_llm_config("app_control").model, "app")
            self.assertEqual(get_llm_config("detect").model, "vision")
            self.assertEqual(get_llm_config().model, "base")

    def test_keyless_local_provider_is_configured(self) -> None:
        with patch.dict(os.environ, {**CLEAR_KEYS, "LLM_BASE_URL": "http://127.0.0.1:11434/v1"}, clear=False):
            config = get_llm_config()
            self.assertIsNone(config.api_key)
            self.assertTrue(llm_configured())
            self.assertNotIn("Authorization", config.headers)

    def test_embedding_provider(self) -> None:
        with patch.dict(
            os.environ,
            {**CLEAR_KEYS, "LLM_API_KEY": "k", "LLM_BASE_URL": "http://localhost:8000/v1", "EMBEDDING_MODEL": "agri-embed"},
            clear=False,
        ):
            config = get_embedding_config()
            self.assertEqual(config.model, "agri-embed")
            self.assertEqual(config.base_url, "http://localhost:8000/v1")


if __name__ == "__main__":
    unittest.main()
