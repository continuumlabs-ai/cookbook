import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from demo import scripts  # noqa: E402

RECIPE = ROOT / "jobs" / "aged-care-incidents"


def load_recipe():
    spec = importlib.util.spec_from_file_location("aged_care_incidents", RECIPE / "recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AgedCareIncidentsTest(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()
        self.client = scripts.aged_care_client()
        self.results = self.recipe.triage_folder(self.client, "test-model", RECIPE / "data" / "incidents", workers=3)
        self.by = {r["resident"]: r for r in self.results}

    def test_priorities_and_deadlines(self):
        self.assertFalse(self.by["E.W."]["reportable"])
        self.assertEqual({k: r["priority"] for k, r in self.by.items() if r["reportable"]},
                         {"R.T.": "P1", "M.K.": "P1", "J.P.": "P1", "D.L.": "P2", "A.N.": "P2"})
        self.assertEqual(self.by["M.K."]["commission_by"], datetime(2026, 10, 16, 6, 45))  # 24 hours
        self.assertEqual(self.by["D.L."]["commission_by"], datetime(2026, 11, 14, 8, 10))  # 30 days
        self.assertIn("police_by", self.by["J.P."])
        self.assertNotIn("police_by", self.by["R.T."])  # police already involved to find him, no crime suspected

    def test_code_raises_priority_the_model_got_wrong(self):
        jp = self.by["J.P."]
        self.assertEqual(jp["model_priority"], "P2")
        self.assertTrue(jp["escalated"])
        self.assertIn("reasonable grounds to report to police", jp["priority_reasons"])

    def test_invented_evidence_is_sent_back(self):
        self.assertTrue(self.by["D.L."]["corrected"])
        requests = [r for r in self.client.requests if "IR-2618" in r["messages"][1]["content"]]
        self.assertEqual(len(requests), 2)
        self.assertIn("word for word", requests[1]["messages"][-1]["content"])

    def test_rules_reject_impossible_readings(self):
        report = (RECIPE / "data" / "incidents" / "05-bed-rails-overnight.txt").read_text()
        reading = dict(scripts.INCIDENT_READINGS["IR-2618"], category="hitting", priority="none")
        problems = self.recipe.reading_problems(reading, report)
        self.assertTrue(any("category must be one of" in p for p in problems))
        self.assertTrue(any("needs priority" in p for p in problems))

    def test_report_orders_by_deadline(self):
        report = self.recipe.report_markdown(self.results)
        self.assertIn("6 incident reports read. 3 Priority 1, 2 Priority 2, 1 not reportable", report)
        self.assertLess(report.index("| Thu 15 Oct 2026, 3:05pm | P1 | R.T."), report.index("| Sat 14 Nov 2026"))
        self.assertIn("## What the checks caught", report)
        self.assertIn("agedcarequality.gov.au", report)


if __name__ == "__main__":
    unittest.main()
