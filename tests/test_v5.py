"""Session test v5 — covers agents/s06_context_compact.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests._session_helpers import skip_without_api
import agents.s06_context_compact as m

class TestStructure(unittest.TestCase):
    def test_required_symbols(self):
        self.assertTrue(callable(m.agent_loop))
        self.assertTrue(callable(m.estimate_tokens))
        self.assertTrue(callable(m.micro_compact))
        self.assertTrue(callable(m.auto_compact))

    def test_estimate_tokens_rough(self):
        msgs = [{"role": "user", "content": "hello world"}]
        tokens = m.estimate_tokens(msgs)
        self.assertIsInstance(tokens, int)
        self.assertGreater(tokens, 0)

    def test_micro_compact_noop_few_messages(self):
        msgs = [{"role": "user", "content": "hi"}]
        result = m.micro_compact(msgs)
        self.assertEqual(result, msgs)

class TestLive(unittest.TestCase):
    @skip_without_api
    def test_placeholder(self): pass

if __name__ == "__main__": unittest.main()
