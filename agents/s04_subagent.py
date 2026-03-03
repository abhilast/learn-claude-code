#!/usr/bin/env python3
"""
s04_subagent.py - Subagents

Spawn a child agent with fresh messages=[]. The child works in its own
context, sharing the filesystem, then returns only a summary to the parent.

    Parent agent                     Subagent
    +------------------+             +------------------+
    | messages=[...]   |             | messages=[]      |  <-- fresh
    |                  |  dispatch   |                  |
    | tool: task       | ---------->| while tool_use:  |
    |   prompt="..."   |            |   call tools     |
    |   description="" |            |   append results |
    |                  |  summary   |                  |
    |   result = "..." | <--------- | return last text |
    +------------------+             +------------------+
              |
    Parent context stays clean.
    Subagent context is discarded.

Key insight: "Process isolation gives context isolation for free."
"""

import os
import subprocess
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv
try:
    from agents.tool_call_fallback import collect_tool_calls, format_text_tool_results
except ModuleNotFoundError:
    from tool_call_fallback import collect_tool_calls, format_text_tool_results

# Load local .env variables so the scripts run without exporting env vars manually.
load_dotenv(override=True)

# The Anthropic SDK can target Anthropic cloud or any compatible local server (like Ollama).
BASE_URL = os.getenv("ANTHROPIC_BASE_URL")
API_KEY = os.getenv("ANTHROPIC_API_KEY")
AUTH_TOKEN = os.getenv("ANTHROPIC_AUTH_TOKEN")

if BASE_URL and not API_KEY:
    if AUTH_TOKEN:
        API_KEY = AUTH_TOKEN
    elif "localhost:11434" in BASE_URL or "127.0.0.1:11434" in BASE_URL:
        API_KEY = "ollama"

if BASE_URL:
    os.environ.pop("ANTHROPIC_AUTH_TOKEN", None)

WORKDIR = Path.cwd()
# One client instance is reused for every model call in this process.
client = Anthropic(base_url=BASE_URL, api_key=API_KEY)
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {WORKDIR}. Use the task tool to delegate exploration or subtasks."
SUBAGENT_SYSTEM = f"You are a coding subagent at {WORKDIR}. Complete the given task, then summarize your findings."


# -- Tool implementations shared by parent and child --
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=WORKDIR,
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"

def run_read(path: str, limit: int = None) -> str:
    try:
        lines = safe_path(path).read_text().splitlines()
        if limit and limit < len(lines):
            lines = lines[:limit] + [f"... ({len(lines) - limit} more)"]
        return "\n".join(lines)[:50000]
    except Exception as e:
        return f"Error: {e}"

def run_write(path: str, content: str) -> str:
    try:
        fp = safe_path(path)
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        return f"Wrote {len(content)} bytes"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path: str, old_text: str, new_text: str) -> str:
    try:
        fp = safe_path(path)
        content = fp.read_text()
        if old_text not in content:
            return f"Error: Text not found in {path}"
        fp.write_text(content.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"


TOOL_HANDLERS = {
    "bash":       lambda **kw: run_bash(kw["command"]),
    "read_file":  lambda **kw: run_read(kw["path"], kw.get("limit")),
    "write_file": lambda **kw: run_write(kw["path"], kw["content"]),
    "edit_file":  lambda **kw: run_edit(kw["path"], kw["old_text"], kw["new_text"]),
}

# Child gets all base tools except task (no recursive spawning)
CHILD_TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read file contents.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "limit": {"type": "integer"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write content to file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace exact text in file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
]


# -- Subagent: fresh context, filtered tools, summary-only return --
def run_subagent(prompt: str) -> str:
    sub_messages = [{"role": "user", "content": prompt}]  # fresh context
    for _ in range(30):  # safety limit
        response = client.messages.create(
            model=MODEL, system=SUBAGENT_SYSTEM, messages=sub_messages,
            tools=CHILD_TOOLS, max_tokens=8000,
        )
        sub_messages.append({"role": "assistant", "content": response.content})
        # Normalize tool calls: use structured tool_use blocks when available,
        # otherwise parse XML-like fallback text emitted by some local models.
        tool_calls = collect_tool_calls(response.content)
        # If the model returned plain text (no tool calls), this turn is complete.
        if response.stop_reason != "tool_use" and not tool_calls:
            break
        results = []
        text_results = []
        for call in tool_calls:
            handler = TOOL_HANDLERS.get(call["name"])
            output = (
                handler(**call["input"])
                if handler
                else f"Unknown tool: {call['name']}"
            )
            if call["tool_use_id"]:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call["tool_use_id"],
                        "content": str(output)[:50000],
                    }
                )
            else:
                text_results.append(
                    {"name": call["name"], "input": call["input"], "output": str(output)}
                )
        if results:
            sub_messages.append({"role": "user", "content": results})
        elif text_results:
            sub_messages.append(
                {
                    "role": "user",
                    "content": format_text_tool_results(text_results),
                }
            )
        else:
            break
    # Only the final text returns to the parent -- child context is discarded
    return "".join(b.text for b in response.content if hasattr(b, "text")) or "(no summary)"


# -- Parent tools: base tools + task dispatcher --
PARENT_TOOLS = CHILD_TOOLS + [
    {"name": "task", "description": "Spawn a subagent with fresh context. It shares the filesystem but not conversation history.",
     "input_schema": {"type": "object", "properties": {"prompt": {"type": "string"}, "description": {"type": "string", "description": "Short description of the task"}}, "required": ["prompt"]}},
]


def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=PARENT_TOOLS, max_tokens=8000,
        )
        messages.append({"role": "assistant", "content": response.content})
        # Normalize tool calls: use structured tool_use blocks when available,
        # otherwise parse XML-like fallback text emitted by some local models.
        tool_calls = collect_tool_calls(response.content)
        # If the model returned plain text (no tool calls), this turn is complete.
        if response.stop_reason != "tool_use" and not tool_calls:
            return
        results = []
        text_results = []
        for call in tool_calls:
            if call["name"] == "task":
                desc = call["input"].get("description", "subtask")
                print(f"> task ({desc}): {call['input'].get('prompt', '')[:80]}")
                output = run_subagent(call["input"]["prompt"])
            else:
                handler = TOOL_HANDLERS.get(call["name"])
                output = (
                    handler(**call["input"])
                    if handler
                    else f"Unknown tool: {call['name']}"
                )
            print(f"  {str(output)[:200]}")
            if call["tool_use_id"]:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call["tool_use_id"],
                        "content": str(output),
                    }
                )
            else:
                text_results.append(
                    {"name": call["name"], "input": call["input"], "output": str(output)}
                )
        if results:
            messages.append({"role": "user", "content": results})
        elif text_results:
            messages.append(
                {
                    "role": "user",
                    "content": format_text_tool_results(text_results),
                }
            )
        else:
            return


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms04 >> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break
        if query.strip().lower() in ("q", "exit", ""):
            break
        history.append({"role": "user", "content": query})
        agent_loop(history)
        response_content = history[-1]["content"]
        if isinstance(response_content, list):
            for block in response_content:
                if hasattr(block, "text"):
                    print(block.text)
        print()
