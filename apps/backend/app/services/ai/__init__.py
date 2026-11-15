"""Multi-agent runtime for the advisor and app-control features.

The runtime now uses the OpenAI Agents SDK (``openai-agents``) via
``sdk_runtime``/``sdk_tools``, configured for an OpenAI-compatible endpoint so
a custom/NASA-grounded model can be plugged in with LLM_* env vars.
"""

from app.services.ai.sdk_runtime import build_model, build_run_config, stream_sdk_agent
from app.services.ai.sdk_tools import to_sdk_tool, to_sdk_tools

__all__ = [
    "build_model",
    "build_run_config",
    "stream_sdk_agent",
    "to_sdk_tool",
    "to_sdk_tools",
]
