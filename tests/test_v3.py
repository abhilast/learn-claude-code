"""Session test v3 — covers agents/s04_subagent.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests._session_helpers import skip_without_api
import agents.s04_subagent as m

class TestStructure(unittest.TestCase):
    def test_required_symbols(self):
        self.assertTrue(callable(m.agent_loop))
        self.assertTrue(callable(m.run_subagent))

class TestLive(unittest.TestCase):
    @skip_without_api
    def test_placeholder(self): pass

if __name__ == "__main__": unittest.main()
