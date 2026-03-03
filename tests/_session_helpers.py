"""Shared helpers for session tests."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def skip_without_api(test_case):
    """Decorator: skip a test method if TEST_API_KEY is not set."""
    api_key = os.environ.get("TEST_API_KEY", "").strip()
    if not api_key:
        return unittest.skip("TEST_API_KEY not set")(test_case)
    return test_case
