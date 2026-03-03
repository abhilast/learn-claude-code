#!/usr/bin/env python3
"""
s01_agent_loop.py - The Agent Loop

The entire secret of an AI coding agent in one pattern:

    while stop_reason == "tool_use":
        response = LLM(messages, tools)
        execute tools
        append results

    +----------+      +-------+      +---------+
    |   User   | ---> |  LLM  | ---> |  Tool   |
    |  prompt  |      |       |      | execute |
    +----------+      +---+---+      +----+----+
                          ^               |
                          |   tool_result |
                          +---------------+
                          (loop continues)

This is the core loop: feed tool results back to the model
until the model decides to stop. Production agents layer
policy, hooks, and lifecycle controls on top.
"""

import os
import subprocess

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

# One client instance is reused for every model call in this process.
client = Anthropic(base_url=BASE_URL, api_key=API_KEY)
MODEL = os.environ["MODEL_ID"]

SYSTEM = f"You are a coding agent at {os.getcwd()}. Use bash to solve tasks. Act, don't explain."

TOOLS = [{
    "name": "bash",
    "description": "Run a shell command.",
    "input_schema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
        "required": ["command"],
    },
}]


def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot", "> /dev/"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, cwd=os.getcwd(),
                           capture_output=True, text=True, timeout=120)
        out = (r.stdout + r.stderr).strip()
        return out[:50000] if out else "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: Timeout (120s)"


# -- The core pattern: a while loop that calls tools until the model stops --
def agent_loop(messages: list):
    while True:
        response = client.messages.create(
            model=MODEL, system=SYSTEM, messages=messages,
            tools=TOOLS, max_tokens=8000,
        )
        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})
        # Normalize tool calls: use structured tool_use blocks when available,
        # otherwise parse XML-like fallback text emitted by some local models.
        tool_calls = collect_tool_calls(response.content)
        # If the model didn't call a tool, we're done
        # If the model returned plain text (no tool calls), this turn is complete.
        if response.stop_reason != "tool_use" and not tool_calls:
            return
        results = []
        text_results = []
        for call in tool_calls:
            if call["name"] != "bash":
                continue
            command = call["input"].get("command", "")
            print(f"\033[33m$ {command}\033[0m")
            output = run_bash(command)
            print(output[:200])
            if call["tool_use_id"]:
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call["tool_use_id"],
                        "content": output,
                    }
                )
            else:
                text_results.append(
                    {"name": call["name"], "input": call["input"], "output": output}
                )
        if results:
            messages.append({"role": "user", "content": results})
            continue
        if text_results:
            messages.append(
                {
                    "role": "user",
                    "content": format_text_tool_results(text_results),
                }
            )
            continue
        return


if __name__ == "__main__":
    history = []
    while True:
        try:
            query = input("\033[36ms01 >> \033[0m")
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
