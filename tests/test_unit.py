"""Unit tests for tool_call_fallback.py — no API key required."""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.tool_call_fallback import (
    _parse_text_tool_calls,
    extract_text_tool_calls,
    collect_tool_calls,
    format_text_tool_results,
)


class TestParseTextToolCalls(unittest.TestCase):
    def test_single_function_with_parameter(self):
        text = "<function=bash><parameter=command>ls -la</parameter></function>"
        calls = _parse_text_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "bash")
        self.assertEqual(calls[0]["input"]["command"], "ls -la")
        self.assertIsNone(calls[0]["tool_use_id"])

    def test_multiple_functions(self):
        text = (
            "<function=read><parameter=path>/tmp/a.txt</parameter></function>"
            "<function=bash><parameter=command>echo hi</parameter></function>"
        )
        calls = _parse_text_tool_calls(text)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["name"], "read")
        self.assertEqual(calls[1]["name"], "bash")

    def test_function_without_parameter_tags_uses_body(self):
        text = "<function=bash>ls</function>"
        calls = _parse_text_tool_calls(text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["input"]["command"], "ls")

    def test_no_functions_returns_empty(self):
        calls = _parse_text_tool_calls("Just some plain text.")
        self.assertEqual(calls, [])

    def test_multiline_parameter_value(self):
        text = "<function=write><parameter=content>line1\nline2</parameter></function>"
        calls = _parse_text_tool_calls(text)
        self.assertEqual(calls[0]["input"]["content"], "line1\nline2")


class _FakeBlock:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestExtractTextToolCalls(unittest.TestCase):
    def test_extracts_from_text_blocks(self):
        block = _FakeBlock(text="<function=bash><parameter=command>pwd</parameter></function>")
        calls = extract_text_tool_calls([block])
        self.assertEqual(calls[0]["name"], "bash")

    def test_ignores_blocks_without_text(self):
        block = _FakeBlock(type="tool_use", name="bash")
        calls = extract_text_tool_calls([block])
        self.assertEqual(calls, [])


class TestCollectToolCalls(unittest.TestCase):
    def test_prefers_structured_tool_use_blocks(self):
        block = _FakeBlock(type="tool_use", name="bash", input={"command": "ls"}, id="tu_1")
        calls = collect_tool_calls([block])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "bash")
        self.assertEqual(calls[0]["tool_use_id"], "tu_1")

    def test_falls_back_to_text_parsing(self):
        block = _FakeBlock(
            type="text",
            text="<function=bash><parameter=command>ls</parameter></function>",
        )
        calls = collect_tool_calls([block])
        self.assertEqual(calls[0]["name"], "bash")
        self.assertIsNone(calls[0]["tool_use_id"])

    def test_empty_blocks_returns_empty(self):
        self.assertEqual(collect_tool_calls([]), [])


class TestFormatTextToolResults(unittest.TestCase):
    def test_bash_call_formatted_as_shell(self):
        calls = [{"name": "bash", "input": {"command": "ls"}, "output": "file.txt"}]
        result = format_text_tool_results(calls)
        self.assertIn("$ ls", result)
        self.assertIn("file.txt", result)

    def test_non_bash_call_uses_function_style(self):
        calls = [{"name": "read", "input": {"path": "/tmp/x"}, "output": "content"}]
        result = format_text_tool_results(calls)
        self.assertIn("read(", result)
        self.assertIn("content", result)

    def test_header_always_present(self):
        result = format_text_tool_results([])
        self.assertIn("Tool execution results", result)


if __name__ == "__main__":
    unittest.main()
