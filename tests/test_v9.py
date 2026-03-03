"""Session test v9 — covers agents/s12_worktree_task_isolation.py."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests._session_helpers import skip_without_api
import agents.s12_worktree_task_isolation as m

class TestStructure(unittest.TestCase):
    def test_required_symbols(self):
        self.assertTrue(callable(m.detect_repo_root))
        self.assertTrue(hasattr(m, 'WorktreeManager'))
        self.assertTrue(hasattr(m, 'TaskManager'))

class TestLive(unittest.TestCase):
    @skip_without_api
    def test_placeholder(self): pass

if __name__ == "__main__": unittest.main()
