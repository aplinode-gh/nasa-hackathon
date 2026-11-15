"""Lightweight multi-agent runtime built on OpenAI-compatible chat completions.

Mirrors the parts of the ``@openai/agents`` SDK used by the Next.js app:
agents own instructions and tools, can hand off to specialists, and the
runner streams text while executing tool calls until the model produces a
final answer.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Awaitable, Callable

import httpx

MAX_STEPS = 8
ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class AgentDef:
    name: str
    instructions: str
    tools: list[Tool] = field(default_factory=list)
    handoffs: list[str] = field(default_factory=list)
    handoff_description: str = ""


def _handoff_tool_name(agent_name: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in agent_name).strip("_")
    return f"transfer_to_{slug}"


def _handoff_tool(agent: AgentDef) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": _handoff_tool_name(agent.name),
            "description": agent.handoff_description or f"Transfer the conversation to the {agent.name}.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Short reason for transferring to this specialist.",
                    }
                },
            },
        },
    }


def _inline_handoffs(agents: dict[str, AgentDef], agent: AgentDef) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for name in agent.handoffs:
        target = agents.get(name)
        if target:
            pairs.append((_handoff_tool_name(target.name), name))
    return pairs


def _tool_schemas(agents: dict[str, AgentDef], agent: AgentDef) -> list[dict[str, Any]]:
    schemas = [tool.schema() for tool in agent.tools]
    for name in agent.handoffs:
        target = agents.get(name)
        if target:
            schemas.append(_handoff_tool(target))
    return schemas


async def _stream_chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
) -> AsyncIterator[tuple[str, Any]]:
    """Stream one model turn, yielding ('text', delta) and ('tool', call) events."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.getenv("ADVISOR_MODEL") or "gpt-4o-mini"
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.4,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=90.0) as client:
        async with client.stream("POST", f"{base_url}/chat/completions", headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    event = json.loads(data)
                except Exception:
                    continue
                choices = event.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield ("text", content)
                for call in delta.get("tool_calls") or []:
                    yield ("tool", call)


def _tool_marker_event(result: str) -> dict[str, Any] | None:
    """Convert structured tool markers into UI events."""
    text = (result or "").strip()
    if not text.startswith("{"):
        return None
    try:
        parsed = json.loads(text)
    except Exception:
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


async def _execute_tool(tool: Tool, arguments: dict[str, Any]) -> str:
    try:
        return await tool.handler(arguments)
    except Exception as err:
        return f"Tool error: {err}"


async def stream_agent(
    agents: dict[str, AgentDef],
    start_agent: str,
    message: str,
    history: str = "",
) -> AsyncIterator[dict[str, Any]]:
    """Run a triage/handoff agent loop and yield stream events.

    Event shapes mirror the existing advisor SSE contract:
    ``{"type": "text", "delta": str}``, ``{"type": "handoff", "agent": str}``,
    ``{"type": "done", "output": str}`` and ``{"type": "error", "message": str}``.
    """
    current = agents.get(start_agent)
    if not current:
        yield {"type": "error", "message": "Agent configuration is unavailable."}
        return

    messages: list[dict[str, Any]] = [{"role": "system", "content": current.instructions}]
    if history:
        messages.append({"role": "system", "content": f"Conversation so far:\n{history}"})
    messages.append({"role": "user", "content": message})

    accumulated = ""
    try:
        for _ in range(MAX_STEPS):
            schemas = _tool_schemas(agents, current)
            text_parts: list[str] = []
            tool_calls: dict[int, dict[str, Any]] = {}

            async for kind, value in _stream_chat(messages, schemas):
                if kind == "text":
                    text_parts.append(value)
                    yield {"type": "text", "delta": value}
                else:
                    index = int(value.get("index", 0))
                    entry = tool_calls.setdefault(index, {"id": "", "name": "", "arguments": ""})
                    if value.get("id"):
                        entry["id"] = value["id"]
                    function = value.get("function") or {}
                    if function.get("name"):
                        entry["name"] += function["name"]
                    if function.get("arguments"):
                        entry["arguments"] += function["arguments"]

            assistant_text = "".join(text_parts)
            if assistant_text:
                accumulated = assistant_text

            if not tool_calls:
                yield {"type": "done", "output": accumulated}
                return

            ordered_calls = [tool_calls[idx] for idx in sorted(tool_calls)]
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_text or None,
                    "tool_calls": [
                        {
                            "id": call["id"] or f"call_{idx}",
                            "type": "function",
                            "function": {"name": call["name"], "arguments": call["arguments"] or "{}"},
                        }
                        for idx, call in enumerate(ordered_calls)
                    ],
                }
            )

            handoffs = dict(_inline_handoffs(agents, current))
            for call in ordered_calls:
                call_id = call["id"] or f"call_{call['name']}"
                name = call["name"]
                try:
                    arguments = json.loads(call["arguments"] or "{}")
                except Exception:
                    arguments = {}

                if name in handoffs:
                    target = agents[handoffs[name]]
                    current = target
                    messages[0] = {"role": "system", "content": current.instructions}
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": f"Transferred to {current.name}.",
                        }
                    )
                    yield {"type": "handoff", "agent": current.name}
                    continue

                tool = next((item for item in current.tools if item.name == name), None)
                result = await _execute_tool(tool, arguments) if tool else f"Unknown tool: {name}"
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": result[:12000],
                    }
                )

                marker = _tool_marker_event(result)
                if marker:
                    yield marker

        yield {"type": "done", "output": accumulated}
    except Exception as err:
        yield {"type": "error", "message": str(err)}
