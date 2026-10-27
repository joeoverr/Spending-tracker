# Checks the category memory and batching. The fake AI here means no Ollama is needed,
# and everything is saved to a temporary file, never your real data folder.
import json
import os
import tempfile
import unittest
from datetime import date
from unittest import mock
import categorise
from banks.common import Transaction

def t(description, amount=-5.0):
    return Transaction(date(2026, 8, 1), description, amount, "Test")

class TestMerchantKey(unittest.TestCase):
    def test_same_shop_different_branch(self):
        self.assertEqual(categorise.merchant_key("TESCO STORES 3021"), "TESCO STORES")
        self.assertEqual(categorise.merchant_key("TESCO STORES 1187"), "TESCO STORES")
        self.assertEqual(categorise.merchant_key("UBER *TRIP"), "UBER TRIP")
        self.assertEqual(categorise.merchant_key("CARD PAYMENT TO Greggs 4410"), "GREGGS")

class TestMemory(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.file = os.path.join(self.folder, "categories.json")
        patcher = mock.patch.object(categorise, "CATEGORIES_FILE", self.file)
        patcher.start()
        self.addCleanup(patcher.stop)

    def fake_ai(self, batch):
        self.batches.append([key for key, _ in batch])
        return {key: "Groceries" for key, _ in batch}

    def test_each_shop_asked_once_in_batches(self):
        self.batches = []
        shops = [t(f"SHOP {chr(65 + i // 26)}{chr(65 + i % 26)} 123") for i in range(60)]
        memory = {}
        with mock.patch.object(categorise, "ask_ai", self.fake_ai):
            result = categorise.categorise_new(shops + shops, memory)   # every shop twice
            self.assertEqual(result, (60, []))
            self.assertEqual([len(b) for b in self.batches], [25, 25, 10])
            # Second run: everything is remembered, so the AI isn't asked at all
            self.assertEqual(categorise.categorise_new(shops, memory), (0, []))
        self.assertEqual(len(self.batches), 3)
        with open(self.file) as f:
            self.assertEqual(len(json.load(f)), 60)

    def test_your_correction_is_remembered_and_wins(self):
        self.batches = []
        memory = {}
        with mock.patch.object(categorise, "ask_ai", self.fake_ai):
            categorise.categorise_new([t("ALDI 4410 LEEDS")], memory)
        categorise.set_category(memory, "ALDI LEEDS", "Eating out")
        reloaded = categorise.load_memory()
        self.assertEqual(reloaded["ALDI LEEDS"], {"category": "Eating out", "by": "you"})
        self.assertEqual(categorise.category_of(t("ALDI 9999 LEEDS"), reloaded), "Eating out")

    def test_one_awkward_shop_does_not_stop_the_others(self):
        # A pretend AI that trips up on any batch containing "AWKWARD": the batch is split until
        # only that one shop fails, and every other shop still gets sorted
        self.batches = []
        def picky_ai(batch):
            self.batches.append(len(batch))
            if any(key == "AWKWARD" for key, _ in batch):
                raise ValueError("garbled answer")
            return {key: "Groceries" for key, _ in batch}
        shops = [t(f"SHOP {chr(65 + i)}") for i in range(9)] + [t("AWKWARD")] + [t(f"SHOP Z{chr(65 + i)}") for i in range(15)]
        memory, done = {}, []
        with mock.patch.object(categorise, "ask_ai", picky_ai):
            result = categorise.categorise_new(shops, memory, lambda d, total: done.append((d, total)))
        self.assertEqual(result, (24, ["AWKWARD"]))
        self.assertEqual(len(memory), 24)
        self.assertNotIn("AWKWARD", memory)
        self.assertEqual(done, [(25, 25)])
        self.assertEqual(self.batches[:3], [25, 12, 6])    # tried whole, then halves, then quarters...
        self.assertIn(1, self.batches)                     # ...down to the one awkward shop on its own

    def test_shops_the_ai_skips_are_reported(self):
        with mock.patch.object(categorise, "ask_ai", lambda batch: {"SHOP A": "Groceries"}):
            self.assertEqual(categorise.categorise_new([t("SHOP A"), t("SHOP B")], {}), (1, ["SHOP B"]))

    def test_ollama_stopping_part_way_is_not_hidden(self):
        with mock.patch.object(categorise, "ask_ai", side_effect=ConnectionError("Failed to connect")):
            with self.assertRaises(ConnectionError):
                categorise.categorise_new([t("SHOP A")], {})

    def test_answer_length_is_capped(self):
        reply = {"message": {"content": json.dumps({"1": "Groceries"})}}
        with mock.patch.object(categorise.ollama, "chat", return_value=reply) as chat:
            categorise.ask_ai([("TESCO STORES", False)])
        self.assertEqual(chat.call_args.kwargs["options"]["num_predict"], categorise.TOKENS_PER_SHOP + 40)

    def test_unknown_shop_is_uncategorised(self):
        self.assertEqual(categorise.category_of(t("NEW PLACE"), {}), categorise.UNSORTED)

    def test_bad_ai_answers_are_ignored(self):
        reply = {"message": {"content": json.dumps({"1": "Groceries", "2": "Not a category"})}}
        with mock.patch.object(categorise.ollama, "chat", return_value=reply):
            self.assertEqual(categorise.ask_ai([("TESCO STORES", False), ("ODD", False)]),
                             {"TESCO STORES": "Groceries"})

class TestRealAI(unittest.TestCase):
    # Only runs if Ollama is switched on. Uses made-up shop names only.
    def test_local_ai_sorts_obvious_shops(self):
        try:
            categorise.ollama.list()
        except Exception:
            self.skipTest("Ollama isn't running")
        answer = categorise.ask_ai([("TESCO STORES", False), ("NETFLIX.COM", False),
                                    ("TOP-UP BY", True), ("ACME WIDGETS LTD SALARY", True)])
        self.assertEqual(answer, {"TESCO STORES": "Groceries", "NETFLIX.COM": "Subscriptions",
                                  "TOP-UP BY": "Transfers", "ACME WIDGETS LTD SALARY": "Income"})

if __name__ == "__main__":
    unittest.main()
