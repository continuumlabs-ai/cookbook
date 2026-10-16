import sys
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from au import checks  # noqa: E402


class AustralianChecksTest(unittest.TestCase):
    def test_abn(self):
        self.assertTrue(checks.abn_valid("51 824 753 556"))  # the ATO's published example
        self.assertTrue(checks.abn_valid("51824753556"))
        self.assertFalse(checks.abn_valid("51 824 753 557"))  # one digit wrong
        self.assertFalse(checks.abn_valid("1234"))
        self.assertEqual(checks.format_abn("51824753556"), "51 824 753 556")

    def test_acn_tfn_medicare(self):
        self.assertTrue(checks.acn_valid("000 000 019"))
        self.assertFalse(checks.acn_valid("000 000 018"))
        self.assertTrue(checks.tfn_valid("123 456 782"))
        self.assertFalse(checks.tfn_valid("123 456 789"))
        self.assertTrue(checks.medicare_valid("2123 45670 1"))
        self.assertFalse(checks.medicare_valid("2123 45671 1"))

    def test_tfn_redaction_leaves_other_numbers_alone(self):
        text, count = checks.redact_tfns("TFN 123 456 782. Phone 0400 123 456. Invoice 123456789. ABN 51 824 753 556.")
        self.assertEqual(count, 1)
        self.assertIn("[TFN REDACTED]", text)
        self.assertIn("0400 123 456", text)
        self.assertIn("123456789", text)
        self.assertIn("51 824 753 556", text)

    def test_gst(self):
        self.assertEqual(checks.money("$1,234.50"), Decimal("1234.50"))
        self.assertIsNone(checks.money("TBC"))
        self.assertEqual(checks.gst_on("2597.00"), Decimal("259.70"))
        self.assertEqual(checks.gst_in("110.00"), Decimal("10.00"))
        self.assertEqual(checks.gst_problems("2597.00", "259.70", "2856.70"), [])
        self.assertEqual(len(checks.gst_problems("2597.00", "259.70", "2866.70")), 1)
        self.assertIn("$125.00", checks.gst_problems("1250", "132", "1382")[0])
        # Part of the invoice is GST-free.
        self.assertEqual(checks.gst_problems("150.00", "10.00", "160.00", gst_free_amount="50.00"), [])

    def test_places_and_dates(self):
        self.assertEqual(checks.state_for_postcode("3101"), "VIC")
        self.assertEqual(checks.state_for_postcode("2600"), "ACT")
        self.assertEqual(checks.state_for_postcode("0800"), "NT")
        self.assertTrue(checks.postcode_matches_state("6000", "wa"))
        self.assertFalse(checks.postcode_matches_state("6000", "NSW"))
        self.assertTrue(checks.bsb_valid("062-000"))
        self.assertFalse(checks.bsb_valid("62000"))
        self.assertEqual(checks.au_date("03/10/2026"), date(2026, 10, 3))  # 3 October, not 10 March
        self.assertEqual(checks.au_date("3rd October 2026"), date(2026, 10, 3))
        self.assertIsNone(checks.au_date("next Tuesday"))


if __name__ == "__main__":
    unittest.main()
