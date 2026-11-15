"""Adapters to expose existing tool handlers as OpenAI Agents SDK tools."""

from __future__ import annotations

import json
from typing import Any, Iterable

from agents import FunctionTool, RunContextWrapper

from app.services.ai.agent import Tool as LegacyTool


def _ensure_str(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception:
        return str(result)


def to_sdk_tool(tool: LegacyTool) -> FunctionTool:
    """Wrap a legacy Tool(name, description, parameters, handler) as an SDK FunctionTool."""

    async def on_invoke_tool(ctx: RunContextWrapper[Any], arguments_json: str) -> str:
        try:
            args = json.loads(arguments_json) if arguments_json else {}
            if not isinstance(args, dict):
                args = {"value": args}
        except Exception:
            args = {}
        result = await tool.handler(args)
        return _ensure_str(result)

    return FunctionTool(
        name=tool.name,
        description=tool.description,
        params_json_schema=tool.parameters or {"type": "object", "properties": {}},
        on_invoke_tool=on_invoke_tool,
    )


def to_sdk_tools(tools: Iterable[LegacyTool]) -> list[FunctionTool]:
    return [to_sdk_tool(tool) for tool in tools]
