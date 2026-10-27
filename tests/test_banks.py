# Checks every bank reader against the made-up sample statements.
# Run all tests with:  py -m unittest
import os
import random
import shutil
import tempfile
import unittest
from datetime import date
import pdfplumber
import banks
import make_samples
from banks import chase_uk, revolut, general_csv
from banks.common import parse_amount

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")
CHASE = os.path.join(SAMPLES, "sample_chase_uk.pdf")
REVOLUT = os.path.join(SAMPLES, "sample_revolut.csv")
OTHER = os.path.join(SAMPLES, "sample_other_bank.csv")
OTHER_SETTINGS = {"bank": "Other Bank", "date": "Posted", "description": "Merchant", "amount": "Value",
                  "date_format": "31/12/2026", "spending_is_positive": False}

class TestAmounts(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_amount("-£1,234.56"), -1234.56)
        self.assertEqual(parse_amount("+£3.00"), 3.0)
        self.assertEqual(parse_amount("(12.50)"), -12.5)
        self.assertEqual(parse_amount("12.50-"), -12.5)
        self.assertIsNone(parse_amount(""))
        self.assertIsNone(parse_amount("Amount"))

class TestChase(unittest.TestCase):
    def expected(self):
        random.seed(42)   # rebuild the exact list the sample PDF was made from
        return [(d, name, amount) for d, name, amount in make_samples.chase_transactions()]

    def test_table_reader_matches_sample(self):
        got = [(t.date, t.description, t.amount) for t in chase_uk.read(CHASE)]
        self.assertEqual(got, self.expected())

    def test_text_fallback_matches_sample(self):
        with pdfplumber.open(CHASE) as pdf:
            got = [(t.date, t.description, t.amount) for t in chase_uk.from_text(pdf)]
        self.assertEqual(got, self.expected())

    def test_no_balance_rows(self):
        self.assertFalse(any("balance" in t.description.lower() for t in chase_uk.read(CHASE)))

class TestRevolut(unittest.TestCase):
    def test_reads_completed_only_and_takes_off_fees(self):
        rows = revolut.read(REVOLUT)
        self.assertEqual(len(rows), 33)   # 34 rows in the file, one was REVERTED
        hotel = [t for t in rows if t.description == "Holiday Hotel Lisbon"]
        self.assertEqual(len(hotel), 3)
        self.assertEqual(hotel[0].amount, -70.83)   # -70.33 plus the 0.50 fee
        self.assertTrue(all(t.bank == "Revolut" for t in rows))

class TestGeneralCsv(unittest.TestCase):
    def test_reads_with_chosen_columns(self):
        rows = general_csv.read(OTHER, OTHER_SETTINGS)
        self.assertEqual(len(rows), 18)
        self.assertEqual(rows[0].date, date(2026, 8, 6))
        self.assertEqual(rows[0].amount, -29.78)
        self.assertEqual(rows[0].bank, "Other Bank")

    def test_spending_is_positive_flips_signs(self):
        rows = general_csv.read(OTHER, dict(OTHER_SETTINGS, spending_is_positive=True))
        self.assertEqual(rows[0].amount, 29.78)

class TestFolder(unittest.TestCase):
    def test_detects_banks_and_skips_duplicates(self):
        folder = tempfile.mkdtemp()
        try:
            for path in (CHASE, REVOLUT, OTHER):
                shutil.copy(path, folder)
            shutil.copy(REVOLUT, os.path.join(folder, "revolut_again.csv"))  # overlapping statement

            rows, needs_setup, failed = banks.read_folder(folder, {})
            self.assertEqual([os.path.basename(p) for p in needs_setup], ["sample_other_bank.csv"])
            self.assertEqual(len(rows), 103 + 33)
            self.assertEqual(failed, [])

            formats = {banks.csv_key(os.path.join(folder, "sample_other_bank.csv")): OTHER_SETTINGS}
            rows, needs_setup, failed = banks.read_folder(folder, formats)
            self.assertEqual(needs_setup, [])
            self.assertEqual(len(rows), 103 + 33 + 18)
            self.assertEqual(rows, sorted(rows, key=lambda t: t.date))
        finally:
            shutil.rmtree(folder)

if __name__ == "__main__":
    unittest.main()
