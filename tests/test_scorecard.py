import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from demo import scripts  # noqa: E402


def load_scorecard():
    spec = importlib.util.spec_from_file_location("scorecard_run", ROOT / "scorecard" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Router:
    """Sends each request to the scripted model for the recipe that made it."""

    def __init__(self):
        self.clients = {
            "contract": scripts.contract_review_client(),
            "research analyst": scripts.research_analyst_client(),
            "company announcements": scripts.announcement_monitor_client(),
            "supplier invoices": scripts.bookkeeper_client(),
            "Serious Incident Response": scripts.aged_care_client(),
        }
        self.chat = type("Chat", (), {})()
        self.chat.completions = type("Completions", (), {})()
        self.chat.completions.create = self.create

    def create(self, **kwargs):
        system = kwargs["messages"][0]["content"]
        for marker in ["Serious Incident Response", "supplier invoices", "company announcements", "research analyst", "contract"]:
            if marker in system:
                return self.clients[marker].chat.completions.create(**kwargs)
        raise AssertionError("No scripted model for this request: " + system[:80])


class ScorecardTest(unittest.TestCase):
    def test_scores_every_task_and_writes_a_table(self):
        scorecard = load_scorecard()
        row = scorecard.score_model(Router(), "scripted-model")
        for name, _ in scorecard.TASKS:
            task = row["tasks"][name]
            self.assertFalse(any(n.startswith("failed") for n in task["notes"]), (name, task["notes"]))
            self.assertGreater(task["points"], 0, name)
        # The scripted aged care model calls J.P. Priority 2. The scorecard marks the model, not the code's fix.
        self.assertLess(row["tasks"]["Aged care incidents"]["points"], 12)
        self.assertIn("code raised 1 priorities", row["tasks"]["Aged care incidents"]["notes"])
        table = scorecard.markdown([row], "https://example.test/v1")
        self.assertIn("| `scripted-model` |", table)
        self.assertIn("answers.json", table)


if __name__ == "__main__":
    unittest.main()
