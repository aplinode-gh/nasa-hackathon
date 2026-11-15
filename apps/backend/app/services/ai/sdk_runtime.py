"""OpenAI Agents SDK runtime: custom model provider, streaming helpers, and event mapping.

This mirrors the boilerplate's use of @openai/agents (Agent, handoff, Runner.run
streamed) while pointing at a configurable OpenAI-compatible endpoint so the
deployment can run its own NASA-grounded model.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from agents import (
    Agent,
    AsyncOpenAI,
    InputGuardrailTripwireTriggered,
    ModelSettings,
    OpenAIChatCompletionsModel,
    OutputGuardrailTripwireTriggered,
    RunConfig,
    Runner,
    set_tracing_disabled,
)
from agents.stream_events import AgentUpdatedStreamEvent, RawResponsesStreamEvent, RunItemStreamEvent

from app.services.ai.llm import get_llm_config

# The SDK ships with tracing enabled for OpenAI; disable when no tracing key is
# configured so self-hosted/custom endpoints don't emit noisy trace failures.
set_tracing_disabled(True)


def build_model(feature: str | None = None) -> OpenAIChatCompletionsModel:
    """Return an Agents SDK model bound to the configured LLM endpoint."""
    config = get_llm_config(feature)
    client = AsyncOpenAI(
        api_key=config.api_key or "not-needed",
        base_url=config.base_url,
    )
    return OpenAIChatCompletionsModel(model=config.model, openai_client=client)


def build_run_config(feature: str | None = None) -> RunConfig:
    """RunConfig that forces the custom model for every agent in a run."""
    return RunConfig(
        model=build_model(feature),
        model_settings=ModelSettings(temperature=0.4),
        tracing_disabled=True,
    )


def _tool_marker_event(result: Any) -> dict[str, Any] | None:
    """Convert structured tool results into frontend action events."""
    text = ""
    if isinstance(result, str):
        text = result.strip()
    elif isinstance(result, (dict, list)):
        try:
            text = json.dumps(result)
        except Exception:
            return None
    else:
        try:
            text = str(result).strip()
        except Exception:
            return None

    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None

    marker_type = parsed.get("type")
    if marker_type == "navigation_button":
        return {"type": "navigation_button", "path": parsed.get("path"), "label": parsed.get("label")}
    if marker_type == "confirmation":
        return {
            "type": "action_card",
            "card": {"type": "confirmation", "message": parsed.get("message"), "data": parsed.get("data")},
        }
    if marker_type in ("price_table", "pnl_summary", "weather_forecast", "record_diff"):
        return {"type": "action_card", "card": {"type": marker_type, "data": parsed.get("data")}}
    return None


def _item_to_marker(item: Any) -> dict[str, Any] | None:
    """Extract UI marker events from a completed tool output item."""
    item_type = getattr(item, "type", None)
    if item_type != "tool_call_output_item":
        return None
    output = getattr(item, "output", None)
    return _tool_marker_event(output)


async def stream_sdk_agent(
    agent: Agent[Any],
    message: str,
    *,
    history: str = "",
    feature: str | None = None,
    max_turns: int = 10,
) -> AsyncIterator[dict[str, Any]]:
    """Run an Agents SDK agent with streaming and yield normalized SSE events.

    Events:
      {"type":"text","delta":str}
      {"type":"handoff","agent":str}
      {"type":"navigation_button"/"action_card", ...}
      {"type":"done","output":str}
      {"type":"error","message":str}
    """
    input_items: list[dict[str, Any]] = []
    if history:
        input_items.append(
            {
                "role": "user",
                "content": f"Conversation so far:\n{history}\n\nPlease continue helping with the next message.",
            }
        )
        input_items.append(
            {
                "role": "assistant",
                "content": "Understood. I have the conversation context and will continue.",
            }
        )
    input_items.append({"role": "user", "content": message})

    accumulated = ""
    try:
        result = Runner.run_streamed(
            agent,
            input=input_items,
            run_config=build_run_config(feature),
            max_turns=max_turns,
        )
        async for event in result.stream_events():
            if isinstance(event, RawResponsesStreamEvent):
                data = event.data
                if getattr(data, "type", None) == "response.output_text.delta":
                    delta = getattr(data, "delta", "") or ""
                    if delta:
                        accumulated += delta
                        yield {"type": "text", "delta": delta}
            elif isinstance(event, AgentUpdatedStreamEvent):
                new_agent = getattr(event, "new_agent", None)
                name = getattr(new_agent, "name", None)
                if name:
                    yield {"type": "handoff", "agent": name}
            elif isinstance(event, RunItemStreamEvent):
                if getattr(event, "name", None) == "tool_output":
                    marker = _item_to_marker(getattr(event, "item", None))
                    if marker:
                        yield marker

        await result.completed
        final = result.final_output
        output = final if isinstance(final, str) else (accumulated or str(final or ""))
        if not isinstance(output, str):
            output = str(output)
        yield {"type": "done", "output": output}
    except InputGuardrailTripwireTriggered:
        yield {
            "type": "error",
            "message": "I'm here to help with farming questions. How can I assist with your crops or farm?",
        }
    except OutputGuardrailTripwireTriggered:
        yield {
            "type": "error",
            "message": "Advisor service is temporarily unavailable. Please try again in a moment.",
        }
    except Exception as err:
        yield {"type": "error", "message": str(err)}
