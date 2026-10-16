"""Every recipe must run end to end in demo mode, exactly as a new visitor would run it."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
RECIPES = {
    "agents/contract-review": "report.md",
    "agents/research-analyst": "answer.md",
    "batch/announcement-monitor": "digest.md",
    "jobs/bookkeeper-invoices": "report.md",
    "jobs/aged-care-incidents": "triage.md",
}


class DemoModeTest(unittest.TestCase):
    def test_every_recipe_runs_in_demo_mode(self):
        for recipe, report in RECIPES.items():
            with self.subTest(recipe=recipe), tempfile.TemporaryDirectory() as out:
                result = subprocess.run(
                    [sys.executable, str(ROOT / recipe / "recipe.py"), "--demo", "--out", out],
                    capture_output=True, text=True, cwd=ROOT, env={"PATH": ""},
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("DEMO MODE", result.stdout)
                text = (Path(out) / report).read_text()
                self.assertTrue(text.startswith("> Demonstration output."))

    def test_example_outputs_are_committed(self):
        for recipe, report in RECIPES.items():
            with self.subTest(recipe=recipe):
                self.assertTrue((ROOT / recipe / "example-output" / report).exists())


if __name__ == "__main__":
    unittest.main()
