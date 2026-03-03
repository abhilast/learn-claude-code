"""Session test v1 — covers agents/s02_tool_use.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests._session_helpers import skip_without_api
import agents.s02_tool_use as m

class TestStructure(unittest.TestCase):
    def test_required_symbols(self):
        self.assertTrue(callable(m.agent_loop))
        self.assertTrue(callable(m.safe_path))
        self.assertTrue(callable(m.run_bash))
        self.assertTrue(callable(m.run_read))
        self.assertTrue(callable(m.run_write))
        self.assertTrue(callable(m.run_edit))

class TestLive(unittest.TestCase):
    @skip_without_api
    def test_placeholder(self): pass

if __name__ == "__main__": unittest.main()
