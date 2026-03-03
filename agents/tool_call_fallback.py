"""
Helpers for models that emit pseudo tool calls as plain text instead of
structured tool_use blocks.
"""

from __future__ import annotations

import re
from typing import Any


FUNCTION_PATTERN = re.compile(
    r"<function=(?P<name>[^>]+)>\s*(?P<body>.*?)\s*</function>",
    re.DOTALL,
)
PARAM_PATTERN = re.compile(
    r"<parameter=(?P<key>[^>]+)>\s*(?P<value>.*?)\s*</parameter>",
    re.DOTALL,
)


def _parse_text_tool_calls(text: str) -> list[dict[str, Any]]:
    # Parse a single text blob that may contain one or more pseudo tool calls.
    # Example input shape:
    #   <function=bash><parameter=command>ls</parameter></function>
    calls = []
    for fn in FUNCTION_PATTERN.finditer(text):
        name = fn.group("name").strip()
        body = fn.group("body")
        tool_input: dict[str, str] = {}
        for param in PARAM_PATTERN.finditer(body):
            key = param.group("key").strip()
            value = param.group("value").strip()
            if key:
                tool_input[key] = value
        # Common fallback shape when parameter tags are omitted.
        if not tool_input and body.strip():
            tool_input["command"] = body.strip()
        if name and tool_input:
            calls.append({"name": name, "input": tool_input, "tool_use_id": None})
    return calls


def extract_text_tool_calls(content_blocks: list) -> list[dict[str, Any]]:
    # Anthropic responses are block-based; only text blocks are relevant here.
    calls = []
    for block in content_blocks:
        text = getattr(block, "text", None)
        if text:
            calls.extend(_parse_text_tool_calls(text))
    return calls


def collect_tool_calls(content_blocks: list) -> list[dict[str, Any]]:
    # Preferred path: native structured blocks from the API.
    # Fallback path: parse text-formatted pseudo calls for local models that
    # don't emit real tool_use blocks.
    structured_calls = []
    for block in content_blocks:
        if getattr(block, "type", None) == "tool_use":
            structured_calls.append(
                {
                    "name": block.name,
                    "input": dict(block.input),
                    "tool_use_id": block.id,
                }
            )
    if structured_calls:
        return structured_calls
    return extract_text_tool_calls(content_blocks)


def format_text_tool_results(executed_calls: list[dict[str, Any]]) -> str:
    # When tool calls came from plain text, we can't send official tool_result
    # objects (no tool_use_id). Instead we send a readable text summary so the
    # model can continue the loop with the observed outputs.
    lines = []
    for call in executed_calls:
        name = call.get("name", "tool")
        tool_input = call.get("input", {}) or {}
        output = str(call.get("output", ""))
        if name == "bash" and "command" in tool_input:
            label = f"$ {tool_input['command']}"
        else:
            args = ", ".join(f"{k}={repr(v)}" for k, v in tool_input.items())
            label = f"{name}({args})"
        lines.append(f"{label}\n{output}")
    return "Tool execution results:\n\n" + "\n\n".join(lines)
