import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_model import FakeClient, reply, tool_call  # noqa: E402

ROOT = Path(__file__).parent.parent
RECIPE = ROOT / "agents" / "research-analyst"


def load_recipe():
    spec = importlib.util.spec_from_file_location("research_analyst", RECIPE / "recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GOOD_CITATIONS = [
    {"doc_id": "risk-committee-2026-09", "quote": "must answer at least 95% of a test set of 500 real member enquiries correctly"},
    {"doc_id": "pilot-results-2026-10", "quote": "467 were correct, an accuracy of 93.4%"},
]
ANSWER = (
    "Not yet. The Risk Committee requires at least 95% accuracy on 500 enquiries [1]. "
    "The pilot scored 93.4% [2], so the threshold is not met."
)


class ResearchAnalystTest(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()
        self.library = self.recipe.Library(RECIPE / "data" / "docs")

    def test_search_finds_the_right_passages(self):
        hits = self.library.search("accuracy threshold 95%")
        self.assertEqual(hits[0]["doc_id"], "risk-committee-2026-09")
        hits = self.library.search("Chatwell data residency")
        self.assertEqual(hits[0]["doc_id"], "vendor-review-chatwell")

    def test_research_rejects_bad_quotes_then_accepts(self):
        invented = [{"doc_id": "pilot-results-2026-10", "quote": "accuracy reached 97%"}]
        script = [
            reply(tool_calls=[tool_call("search_documents", query="accuracy threshold launch"),
                              tool_call("search_documents", query="pilot accuracy results")]),
            reply(tool_calls=[tool_call("read_document", doc_id="pilot-results-2026-10")]),
            # An invented quote and a dangling [2] must be rejected by code.
            reply(tool_calls=[tool_call("submit_answer", answer="Ready [1] [2].", citations=invented)]),
            reply(tool_calls=[tool_call("submit_answer", answer=ANSWER, citations=GOOD_CITATIONS)]),
        ]
        client = FakeClient(script)
        session = self.recipe.research(client, "test-model", self.library, "Is the pilot ready?")

        self.assertEqual(session.answer, ANSWER)
        tool_results = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
        rejection = next(r for r in tool_results if r.startswith("Error: answer not accepted"))
        self.assertIn("does not appear word for word", rejection)
        self.assertIn("no citation 2", rejection)
        self.assertTrue(any("risk-committee-2026-09" in r for r in tool_results))

    def test_verification_report(self):
        session = self.recipe.Session(self.library)
        self.assertEqual(session.handle("submit_answer", {"answer": ANSWER, "citations": GOOD_CITATIONS}), "Answer accepted.")
        verdict = {"claims": [
            {"claim": "The threshold is 95%.", "citations": [1], "supported": True, "reason": "Stated directly."},
            {"claim": "The pilot scored 93.4%.", "citations": [2], "supported": True, "reason": "Stated directly."},
            {"claim": "So the threshold is not met.", "citations": [1, 2], "supported": False, "reason": "Test only."},
        ]}
        client = FakeClient([reply(content=json.dumps(verdict))])
        claims = self.recipe.verify(client, "test-model", session.answer, session.citations)
        self.assertEqual(client.requests[0]["response_format"], {"type": "json_object"})
        report = self.recipe.report_markdown("Is the pilot ready?", session, claims)
        self.assertIn("2 of 3 claims are supported", report)
        self.assertIn("Not supported: So the threshold is not met.", report)

    def test_unreadable_verification_is_reported_not_hidden(self):
        session = self.recipe.Session(self.library)
        session.handle("submit_answer", {"answer": ANSWER, "citations": GOOD_CITATIONS})
        claims = self.recipe.verify(FakeClient([reply(content="not json")]), "m", session.answer, session.citations)
        self.assertIsNone(claims)
        self.assertIn("could not run", self.recipe.report_markdown("q", session, claims))


if __name__ == "__main__":
    unittest.main()
