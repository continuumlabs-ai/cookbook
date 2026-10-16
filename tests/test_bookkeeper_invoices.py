import csv
import importlib.util
import io
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
from demo import scripts  # noqa: E402

RECIPE = ROOT / "jobs" / "bookkeeper-invoices"


def load_recipe():
    spec = importlib.util.spec_from_file_location("bookkeeper_invoices", RECIPE / "recipe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BookkeeperInvoicesTest(unittest.TestCase):
    def setUp(self):
        self.recipe = load_recipe()
        self.client = scripts.bookkeeper_client()
        self.results = self.recipe.process_folder(self.client, "test-model", RECIPE / "data" / "invoices", workers=3)
        self.by_file = {r["source"][:2]: r for r in self.results}

    def test_tax_file_numbers_never_reach_the_model(self):
        sent = " ".join(m["content"] for r in self.client.requests for m in r["messages"])
        self.assertNotIn("123 456 782", sent)
        self.assertIn("[TFN REDACTED]", sent)
        self.assertEqual(self.by_file["05"]["tfns_redacted"], 1)

    def test_each_invoice_lands_in_the_right_place(self):
        status = {k: r["status"] for k, r in self.by_file.items()}
        self.assertEqual(status, {"01": "ready", "02": "ready", "03": "hold", "04": "hold", "05": "hold", "06": "duplicate"})
        self.assertIn("check digit", self.by_file["03"]["findings"][0])
        self.assertIn("$125.00", self.by_file["04"]["findings"][0])
        self.assertIn("47%", self.by_file["05"]["findings"][0])
        self.assertEqual(self.by_file["06"]["duplicate_of"], "01-ironbark-plumbing.txt")

    def test_misread_figure_is_sent_back_and_corrected(self):
        self.assertTrue(self.by_file["02"]["corrected"])
        gumleaf = [r for r in self.client.requests if "Gumleaf" in r["messages"][1]["content"]]
        self.assertEqual(len(gumleaf), 2)
        self.assertIn("$285.07", gumleaf[1]["messages"][-1]["content"])

    def test_import_file_holds_only_clean_invoices(self):
        rows = list(csv.DictReader(io.StringIO(self.recipe.import_csv(self.results))))
        self.assertEqual({r["ContactName"] for r in rows}, {"Ironbark Plumbing Pty Ltd", "Gumleaf Office Supplies"})
        self.assertEqual(len([r for r in rows if r["InvoiceNumber"] == "INV-20417"]), 4)  # one copy only
        milk = next(r for r in rows if r["Description"].startswith("Milk"))
        self.assertEqual(milk["TaxType"], "GST Free Expenses")
        gumleaf = next(r for r in rows if r["ContactName"] == "Gumleaf Office Supplies")
        self.assertEqual(gumleaf["DueDate"], "05/11/2026")  # no due date on the invoice, so 30 days

    def test_report(self):
        report = self.recipe.report_markdown(self.results)
        self.assertIn("6 files read. 2 ready to import, 3 to query before paying, 1 duplicate", report)
        self.assertIn("$284.00 GST", report)
        self.assertIn("## What the checks caught", report)


if __name__ == "__main__":
    unittest.main()
