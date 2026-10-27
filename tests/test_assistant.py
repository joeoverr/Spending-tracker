# Checks the assistant's facts, the number check and the rundowns, using the tiny made-up
# payments from test_summary.py. The AI itself is replaced by a pretend one, so no Ollama is needed.
import os
import shutil
import tempfile
import unittest
from datetime import date
from unittest import mock
import assistant
import storage
from tests.test_summary import ROWS, MEMORY

BUDGETS = {"Groceries": 70, "Shopping": 15}

class TestFacts(unittest.TestCase):
    def test_rundown_sections(self):
        # 27 Jul – 26 Aug: Groceries 60.50, Shopping 20.00 (30 less a 10 refund), Eating out 6.25
        sections = dict(assistant.rundown_sections(ROWS, MEMORY, BUDGETS, "2026-07"))
        self.assertEqual(sections["Totals"], ["Spent: £86.75 over 4 payments", "Money in: £1,850.00"])
        self.assertEqual(sections["Top categories"][0], "Groceries: £60.50 (70% of spending)")
        self.assertEqual(sections["Budgets"], ["Kept: Groceries (£9.50 left of £70.00)",
                                               "Broken: Shopping (£5.00 over £15.00)"])
        self.assertIn("Nothing to compare", sections["Compared with last month"][0])

    def test_comparison_is_worked_out_by_the_app(self):
        sections = dict(assistant.rundown_sections(ROWS, MEMORY, {}, "2026-08"))
        compared = sections["Compared with last month (27 Jul – 26 Aug 2026)"]
        self.assertEqual(compared[:2], ["Last month: £86.75 spent", "£61.76 less than last month (71% down)"])
        self.assertEqual(compared[2], "Went up most: Uncategorised (up £9.99)")
        self.assertEqual(compared[3], "Went down most: Groceries (down £45.50), Shopping (down £20.00)")
        self.assertEqual(sections["Budgets"], ["No budgets set yet"])

    def test_chat_facts(self):
        facts = assistant.chat_facts(ROWS, MEMORY, BUDGETS, "2026-08", date(2026, 9, 23))
        self.assertIn("This pay month: 27 Aug – 24 Sep 2026", facts)
        self.assertIn("- Uncategorised: £9.99", facts)                   # every category, not just the top 3
        self.assertIn("- Average per pay month: £55.87", facts)          # (86.75 + 24.99) / 2
        self.assertIn("- Next payday: Fri 25 Sep 2026 (2 days away)", facts)
        self.assertIn("No statements", assistant.chat_facts([], MEMORY, {}, None, date(2026, 9, 23)))

class TestNumberCheck(unittest.TestCase):
    FACTS = "- Spent: £1,082.33 over 48 payments\n- Groceries: £292.36 (27% of spending)"

    def test_numbers_from_the_facts_are_fine(self):
        self.assertEqual(assistant.made_up_numbers("You spent £1,082.33, and groceries were 27%.", self.FACTS), [])
        self.assertEqual(assistant.made_up_numbers("Groceries came to about £292.", self.FACTS), [])  # rounded

    def test_made_up_numbers_are_caught(self):
        self.assertEqual(assistant.made_up_numbers("That's £36 a day, or 30% more.", self.FACTS), ["30%", "£36"])

    def test_numbers_from_your_question_are_fine(self):
        self.assertEqual(assistant.made_up_numbers("Spending £50 on a game is fine.", self.FACTS, "Can I spend £50?"), [])

    def test_markdown_is_cleaned(self):
        self.assertEqual(assistant.clean_markdown("## Wins\n* **Great** job"), "Wins\n• Great job")

class TestTalkingToTheAI(unittest.TestCase):
    def test_reply_streams_and_gets_the_facts(self):
        chunks = [{"message": {"content": "Nice "}}, {"message": {"content": "work!"}}]
        with mock.patch.object(assistant.ollama, "chat", return_value=iter(chunks)) as chat:
            reply = "".join(assistant.stream_reply("How am I doing?", [], "- Spent: £10.00", date(2026, 9, 23)))
        self.assertEqual(reply, "Nice work!")
        system = chat.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Never do any maths yourself", system)
        self.assertIn("- Spent: £10.00", system)
        self.assertIn("Wednesday 23 September 2026", system)

    def test_ollama_not_running_gives_a_friendly_message(self):
        with mock.patch.object(assistant.app_logic.ollama, "list", side_effect=ConnectionError("refused")):
            self.assertIn("Open Ollama from the Start menu", assistant.problem())

    def test_ai_rundown_part_is_checked(self):
        answer = {"message": {"content": "Wins:\n* **Spent £86.75**\nTips:\n* Save £100 next month"}}
        with mock.patch.object(assistant.ollama, "chat", return_value=answer):
            text, made_up = assistant.ai_rundown("- Spent: £86.75", date(2026, 9, 23))
        self.assertEqual(text, "Wins:\n• Spent £86.75\nTips:\n• Save £100 next month")
        self.assertEqual(made_up, ["£100"])

class TestRundowns(unittest.TestCase):
    def setUp(self):
        folder = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, folder)
        patcher = mock.patch.object(storage, "RUNDOWNS_DIR", os.path.join(folder, "rundowns"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_made_in_the_3_days_before_payday_only(self):
        # Payday is Fri 25 Sep 2026, so the rundown window is 22, 23 and 24 Sep
        self.assertIsNone(assistant.rundown_due(ROWS, date(2026, 9, 21)))
        self.assertEqual(assistant.rundown_due(ROWS, date(2026, 9, 22)), "2026-08")
        self.assertIsNone(assistant.rundown_due(ROWS, date(2026, 9, 25)))   # payday itself

    def test_made_again_only_when_newer_payments_arrive(self):
        today = date(2026, 9, 23)
        assistant.save_rundown(assistant.make_rundown(ROWS, MEMORY, BUDGETS, "2026-08", today))
        self.assertIsNone(assistant.rundown_due(ROWS, today))
        newer = ROWS + [ROWS[-1].__class__(date(2026, 9, 22), "TESCO STORES 3021", -5.0, "Test")]
        self.assertEqual(assistant.rundown_due(newer, today), "2026-08")

    def test_saved_and_read_back(self):
        rundown = assistant.make_rundown(ROWS, MEMORY, BUDGETS, "2026-08", date(2026, 9, 23))
        rundown["ai"] = "Wins:\n• Spending came down."
        assistant.save_rundown(rundown)
        self.assertEqual(assistant.saved_rundowns(), ["2026-08"])
        text = assistant.rundown_text(assistant.load_rundown("2026-08"))
        self.assertTrue(text.startswith("Rundown for 27 Aug – 24 Sep 2026\nMade on Wed 23 Sep 2026, with payments up to 2 Sep."))
        self.assertIn("• Spent: £24.99 over 2 payments", text)
        self.assertIn("From your assistant (a helper, not professional financial advice)\nWins:", text)

if __name__ == "__main__":
    unittest.main()
