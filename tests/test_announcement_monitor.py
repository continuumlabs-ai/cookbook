import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fake_model import FakeClient, reply  # noqa: E402

ROOT = Path(__file__).parent.parent
RECIPE = ROOT / "batch" / "announcement-monitor"
FOLDER = RECIPE / "data" / "announcements"


def load_recipe():
    spec = importlib.util.spec_from_file_location("announcement_monitor", RECIPE / "recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ANSWERS = {
    "Ironbark": dict(company="Ironbark Minerals Ltd", category="guidance", material=True, direction="negative",
                     headline="Production guidance cut after pit wall failure",
                     summary="Copper output guidance falls and costs rise 12% while the haul road is closed.",
                     key_figures=["180-195kt", "12%", "A$4.85/lb", "$5.00/lb"]),  # the last one is invented
    "Coralwave": dict(company="Coralwave Health Ltd", category="capital_raising", material=True, direction="mixed",
                      headline="$85m placement to buy 14 day-surgery clinics",
                      summary="Dilutive raise at a 9.5% discount funds an acquisition expected to be accretive.",
                      key_figures=["$85m", "$1.42", "9.5%", "$120m"]),
    "Tasman": dict(company="Tasman Freight Group", category="management_change", material=True, direction="negative",
                   headline="Chief Executive resigns, effective 31 January 2027",
                   summary="Leadership transition after six years. Search under way.", key_figures=[]),
    "Wattle": dict(company="Wattle Energy Ltd", category="governance_routine", material=False, direction="neutral",
                   headline="All AGM resolutions passed", summary="Routine meeting result.", key_figures=[]),
    "Brindle": dict(company="Brindle Property Trust", category="governance_routine", material=False,
                    direction="neutral", headline="Director buys 50,000 units on market",
                    summary="Small director purchase.", key_figures=["50,000"]),
    "Quokka": dict(company="Quokka Software Ltd", category="results", material=True, direction="positive",
                   headline="Revenue up 31% and first positive operating cash flow",
                   summary="Strong half with ARR at $112m and guidance unchanged.",
                   key_figures=["$48.2m", "31%", "$112m", "$3.1m"]),
}


class AnnouncementMonitorTest(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()

    def model(self):
        seen = {}

        def respond(request):
            text = request["messages"][1]["content"]
            key = next(k for k in ANSWERS if k in text)
            seen[key] = seen.get(key, 0) + 1
            if key == "Tasman" and seen[key] == 1:
                # First reply breaks the rules. The recipe must ask for a correction.
                return reply(content=json.dumps({**ANSWERS[key], "category": "ceo_news"}))
            if key == "Wattle":
                return reply(content="Sorry, I cannot help with that.")  # never valid
            return reply(content=json.dumps(ANSWERS[key]))

        return respond

    def test_classifies_validates_and_digests(self):
        client = FakeClient(self.model())
        results = self.recipe.classify_folder(client, "test-model", FOLDER, workers=4)
        by_company = {r.get("company", r["source"]): r for r in results}

        self.assertEqual(len(results), 6)
        self.assertTrue(all(r["response_format"] == {"type": "json_object"} for r in client.requests))

        ironbark = by_company["Ironbark Minerals Ltd"]
        self.assertEqual(ironbark["key_figures"], ["180-195kt", "12%", "A$4.85/lb"])
        self.assertEqual(ironbark["dropped_figures"], ["$5.00/lb"])

        tasman = by_company["Tasman Freight Group"]
        self.assertEqual(tasman["category"], "management_change")
        tasman_requests = [r for r in client.requests if "Tasman" in r["messages"][1]["content"]]
        self.assertEqual(len(tasman_requests), 2)
        self.assertIn("category must be one of", tasman_requests[1]["messages"][-1]["content"])

        wattle = by_company["wattle-energy-agm.txt"]
        self.assertTrue(wattle["needs_review"])

        digest = self.recipe.digest_markdown(results, day="16 October 2026")
        self.assertIn("6 announcements read. 4 material. 1 need a person to check.", digest)
        # Bad news leads the digest.
        self.assertLess(digest.index("Ironbark"), digest.index("Quokka"))
        self.assertIn("Brindle Property Trust: Director buys 50,000 units on market", digest)
        self.assertIn("wattle-energy-agm.txt", digest)

    def test_batch_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "batch.jsonl"
            self.recipe.write_batch_file("test-model", FOLDER, out)
            lines = [json.loads(l) for l in out.read_text().splitlines()]
        self.assertEqual(len(lines), 6)
        self.assertEqual(lines[0]["url"], "/v1/chat/completions")
        self.assertEqual(lines[0]["body"]["model"], "test-model")
        self.assertEqual({l["custom_id"] for l in lines}, {p.stem for p in FOLDER.glob("*.txt")})


if __name__ == "__main__":
    unittest.main()
