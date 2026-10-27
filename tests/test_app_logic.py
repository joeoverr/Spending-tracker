# Checks the jobs the window relies on, using the made-up samples only.
# Column choices are saved to a temporary file, never your real data folder.
import os
import shutil
import tempfile
import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock
import app_logic
import banks
import storage
from banks.common import Transaction
from tests.test_banks import CHASE, REVOLUT, OTHER, OTHER_SETTINGS

def models(*names):
    return SimpleNamespace(models=[SimpleNamespace(model=n) for n in names])

class TestLoadStatement(unittest.TestCase):
    def test_auto_detect(self):
        self.assertEqual(len(app_logic.load_statement(CHASE, app_logic.AUTO, {})), 103)
        self.assertEqual(app_logic.load_statement(REVOLUT, app_logic.AUTO, {})[0].bank, "Revolut")

    def test_other_bank_needs_columns_until_they_are_picked(self):
        self.assertIsNone(app_logic.load_statement(OTHER, app_logic.AUTO, {}))
        formats = {banks.csv_key(OTHER): OTHER_SETTINGS}
        self.assertEqual(len(app_logic.load_statement(OTHER, app_logic.AUTO, formats)), 18)
        self.assertEqual(len(app_logic.load_statement(OTHER, "Other bank (CSV)", formats)), 18)

    def test_choosing_the_bank_yourself(self):
        self.assertEqual(len(app_logic.load_statement(REVOLUT, "Revolut", {})), 34 - 1)  # one is pending
        # Revolut's CSV read as a general CSV once you've picked its columns
        settings = {"bank": "Revolut", "date": "Started Date", "description": "Description",
                    "amount": "Amount", "date_format": "%Y-%m-%d %H:%M:%S"}
        formats = {banks.csv_key(REVOLUT): settings}
        self.assertTrue(app_logic.load_statement(REVOLUT, "Other bank (CSV)", formats))

    def test_wrong_file_type_gives_a_clear_message(self):
        with self.assertRaisesRegex(ValueError, "Chase UK statements are .pdf files"):
            app_logic.load_statement(REVOLUT, "Chase UK", {})
        with self.assertRaisesRegex(ValueError, "only opens .csv"):
            app_logic.load_statement(CHASE, "Other bank (CSV)", {})

    def test_wrong_bank_with_no_payments_gives_a_clear_message(self):
        with self.assertRaisesRegex(ValueError, "No payments were found"):
            app_logic.load_statement(OTHER, "Revolut", {})

    def test_bank_menu(self):
        self.assertEqual(app_logic.bank_choices(), ["Auto-detect", "Chase UK", "Revolut", "Other bank (CSV)"])

class TestCsvFormats(unittest.TestCase):
    def test_column_choices_are_remembered(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with mock.patch.object(storage, "CSV_FORMATS_FILE", os.path.join(folder, "csv_formats.json")):
            formats = app_logic.load_csv_formats()
            app_logic.save_csv_format(OTHER, OTHER_SETTINGS, formats)
            reloaded = app_logic.load_csv_formats()
        self.assertEqual(len(app_logic.load_statement(OTHER, app_logic.AUTO, reloaded)), 18)

    def test_guess_columns(self):
        self.assertEqual(app_logic.guess_columns(banks.general_csv.headers(OTHER)),
                         {"date": "Posted", "description": "Merchant", "amount": "Value"})
        self.assertEqual(app_logic.guess_columns(["Date", "Details", "Paid out"]),
                         {"date": "Date", "description": "Details", "amount": "Paid out"})

class TestMerge(unittest.TestCase):
    def test_opening_the_same_statement_twice_adds_nothing(self):
        once = app_logic.load_statement(REVOLUT, app_logic.AUTO, {})
        self.assertEqual(len(banks.merge(once, once)), len(once))

    def test_two_identical_coffees_in_one_statement_both_count(self):
        coffee = Transaction(date(2026, 8, 1), "COSTA", -3.0, "Test")
        self.assertEqual(len(banks.merge([coffee, coffee], [coffee])), 2)

class TestAiProblem(unittest.TestCase):
    def test_ready(self):
        with mock.patch.object(app_logic.ollama, "list", return_value=models("llama3.1:8b", "llama3.2:latest")):
            self.assertIsNone(app_logic.ai_problem())

    def test_ollama_not_running(self):
        with mock.patch.object(app_logic.ollama, "list", side_effect=ConnectionError("refused")):
            self.assertIn("Start Ollama", app_logic.ai_problem())

    def test_model_missing(self):
        with mock.patch.object(app_logic.ollama, "list", return_value=models("llama3.2:latest")):
            self.assertIn("ollama pull llama3.1:8b", app_logic.ai_problem())

class TestStatementsFolder(unittest.TestCase):
    # A temporary folder stands in for statements/, filled with copies of the samples
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.folder)

    def check_for_new(self, seen, formats=None):
        # What the window does on startup and for "Check for new statements"
        names = app_logic.new_statements(self.folder, seen)
        found, needs_setup, failed = banks.read_folder(self.folder, formats or {}, only=names)
        seen.update(app_logic.file_stamp(self.folder, n) for n in names)
        return found, needs_setup, failed

    def test_new_files_are_found_once_and_never_double_counted(self):
        shutil.copy(CHASE, self.folder)
        seen = set()
        loaded, _, _ = self.check_for_new(seen)
        self.assertEqual(len(loaded), 103)
        self.assertEqual(app_logic.new_statements(self.folder, seen), [])   # nothing new the second time
        # A second copy of the same statement under another name adds nothing once merged
        shutil.copy(CHASE, os.path.join(self.folder, "chase again.pdf"))
        shutil.copy(REVOLUT, self.folder)
        found, _, _ = self.check_for_new(seen)
        self.assertEqual(len(banks.merge(loaded, found)), 103 + 33)

    def test_unknown_bank_and_broken_files_are_reported(self):
        shutil.copy(OTHER, self.folder)
        with open(os.path.join(self.folder, "broken.pdf"), "w") as f:
            f.write("not really a PDF")
        found, needs_setup, failed = self.check_for_new(set())
        self.assertEqual(found, [])
        self.assertEqual([os.path.basename(p) for p in needs_setup], ["sample_other_bank.csv"])
        self.assertEqual([name for name, _ in failed], ["broken.pdf"])

    def test_opened_files_are_copied_never_overwritten(self):
        self.assertEqual(app_logic.keep_copy(REVOLUT, self.folder), "sample_revolut.csv")
        self.assertTrue(os.path.exists(REVOLUT))                                  # copied, not moved
        self.assertIsNone(app_logic.keep_copy(REVOLUT, self.folder))              # same file: no second copy
        self.assertIsNone(app_logic.keep_copy(os.path.join(self.folder, "sample_revolut.csv"), self.folder))
        different = os.path.join(tempfile.mkdtemp(), "sample_revolut.csv")
        self.addCleanup(shutil.rmtree, os.path.dirname(different))
        shutil.copy(OTHER, different)                                              # same name, other contents
        self.assertEqual(app_logic.keep_copy(different, self.folder), "sample_revolut (2).csv")

class TestBudgets(unittest.TestCase):
    def test_reading_the_boxes(self):
        budgets, problems = app_logic.read_budget_boxes(
            {"Groceries": "£250", "Gym": "", "Bills": "1,200.50", "Gaming": "0", "Travel": "lots", "Cash": "-5"})
        self.assertEqual(budgets, {"Groceries": 250.0, "Bills": 1200.5})
        self.assertEqual(problems, ['Travel: "lots" isn\'t a number', "Cash: a budget can't be below £0"])

    def test_budgets_and_settings_are_saved(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        with mock.patch.object(storage, "BUDGETS_FILE", os.path.join(folder, "budgets.json")), \
             mock.patch.object(storage, "SETTINGS_FILE", os.path.join(folder, "settings.json")):
            self.assertEqual(app_logic.load_budgets(), {})
            app_logic.save_budgets({"Groceries": 250.0})
            self.assertEqual(app_logic.load_budgets(), {"Groceries": 250.0})
            app_logic.save_setting("reminder_done", "2026-09-25")
            self.assertEqual(app_logic.load_settings(), {"reminder_done": "2026-09-25"})

    def test_budget_files_stay_out_of_git(self):
        with open(os.path.join(os.path.dirname(storage.__file__), ".gitignore")) as f:
            ignored = f.read().split()
        self.assertIn("data/", ignored)
        self.assertIn("statements/", ignored)

class TestTable(unittest.TestCase):
    def test_rows_newest_first_with_categories(self):
        rows = [Transaction(date(2026, 8, 1), "TESCO STORES 3021", -12.5, "Chase UK"),
                Transaction(date(2026, 9, 2), "SALARY ACME", 2000.0, "Chase UK")]
        memory = {"TESCO STORES": {"category": "Groceries", "by": "ai"}}
        self.assertEqual(app_logic.table_rows(rows, memory), [
            ("02 Sep 2026", "SALARY ACME", "+£2,000.00", "Uncategorised", "Chase UK"),
            ("01 Aug 2026", "TESCO STORES 3021", "-£12.50", "Groceries", "Chase UK")])
        self.assertEqual(len(app_logic.table_rows(rows, memory, month="2026-08")), 1)

if __name__ == "__main__":
    unittest.main()
