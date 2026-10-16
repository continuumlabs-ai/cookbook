import importlib.util
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from demo.fake_model import FakeClient, reply, tool_call  # noqa: E402

ROOT = Path(__file__).parent.parent
RECIPE = ROOT / "agents" / "contract-review"


def load_recipe():
    spec = importlib.util.spec_from_file_location("contract_review", RECIPE / "recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# What a careful reviewer would conclude about the sample contract.
EXPECTED = {
    "liability": ("7", "exception", "high"),
    "data_location": ("5", "exception", "high"),
    "payment_terms": ("2", "exception", "low"),
    "termination_for_convenience": ("4", "exception", "medium"),
    "auto_renewal": ("3", "exception", "medium"),
    "governing_law": ("9", "exception", "medium"),
    "intellectual_property": ("6", "exception", "high"),
    "confidentiality": ("8", "compliant", "low"),
}


class ContractReviewTest(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()
        self.contract = (RECIPE / "data" / "contract.md").read_text()
        self.playbook = json.loads((RECIPE / "data" / "playbook.json").read_text())

    def test_splits_every_clause(self):
        clauses = self.recipe.split_clauses(self.contract)
        self.assertEqual(list(clauses), [str(n) for n in range(1, 10)])
        self.assertEqual(clauses["7"]["title"], "Liability")
        self.assertIn("3 months", clauses["7"]["text"])

    def test_full_review(self):
        script = [
            reply(tool_calls=[tool_call("get_policy", topic="liability"), tool_call("read_clause", number="7")]),
            # A bad finding the code must reject.
            reply(tool_calls=[tool_call("record_finding", topic="liability", clause="77", status="bad",
                                        risk="high", explanation="x", suggested_redline="")]),
            # Trying to finish too early must be refused.
            reply(tool_calls=[tool_call("finish", summary="Done.")]),
        ]
        findings = [
            tool_call("record_finding", topic=t, clause=c, status=s, risk=r,
                      explanation=f"Clause {c} checked against the {t} rule.",
                      suggested_redline="" if s == "compliant" else "Replacement wording.")
            for t, (c, s, r) in EXPECTED.items()
        ]
        script.append(reply(tool_calls=findings))
        script.append(reply(tool_calls=[tool_call("finish", summary="Seven exceptions. Three are high risk. Do not sign as drafted.")]))

        client = FakeClient(script)
        review, usage = self.recipe.review_contract(client, "test-model", self.contract, self.playbook)

        self.assertTrue(review.done)
        self.assertEqual(len(review.findings), 8)
        for topic, (clause, status, risk) in EXPECTED.items():
            self.assertEqual(review.findings[topic]["clause"], clause)
            self.assertEqual(review.findings[topic]["status"], status)
            self.assertEqual(review.findings[topic]["risk"], risk)

        tool_results = [m["content"] for m in client.requests[-1]["messages"] if m["role"] == "tool"]
        self.assertTrue(any("Clause 7. Liability" in r for r in tool_results))
        self.assertTrue(any(r.startswith("Error: finding not recorded") for r in tool_results))
        self.assertTrue(any(r.startswith("Error: cannot finish yet") for r in tool_results))
        self.assertEqual(usage["prompt_tokens"], 500)

        report = self.recipe.report_markdown(review)
        self.assertIn("7 of 8 policy topics need attention.", report)
        self.assertIn("Do not sign as drafted.", report)

    def test_flags_topics_the_agent_skipped(self):
        script = [
            reply(tool_calls=[tool_call("record_finding", topic="liability", clause="7", status="exception",
                                        risk="high", explanation="Cap is 3 months.", suggested_redline="12 months.")]),
            reply(content="I think that is enough."),
            reply(content="Still done."),
        ]
        review, _ = self.recipe.review_contract(FakeClient(script), "test-model", self.contract, self.playbook,
                                                max_turns=3)
        self.assertFalse(review.done)
        self.assertEqual(review.findings["liability"]["status"], "exception")
        self.assertEqual(review.findings["governing_law"]["status"], "not_reviewed")
        self.assertEqual(sum(f["status"] == "not_reviewed" for f in review.findings.values()), 7)


if __name__ == "__main__":
    unittest.main()
