# Checks the totals with a tiny made-up set of payments where the right answers are easy to work out
import unittest
from datetime import date
import summary
from banks.common import Transaction

MEMORY = {key: {"category": cat, "by": "you"} for key, cat in [
    ("TESCO STORES", "Groceries"), ("PRET A MANGER", "Eating out"), ("ACME LTD SALARY", "Income"),
    ("TRANSFER TO REVOLUT", "Transfers"), ("AMAZON", "Shopping"), ("AMAZON REFUND", "Shopping")]}

# Pay months: 27 Jul - 26 Aug 2026 is "2026-07", and 27 Aug - 24 Sep 2026 is "2026-08"
# (27 Sep 2026 is a Sunday, so that payday is Fri 25 Sep)
ROWS = [
    Transaction(date(2026, 7, 27), "ACME LTD SALARY", 1850.00, "Test"),   # so July's pay month is fully loaded
    Transaction(date(2026, 8, 1), "TESCO STORES 3021", -40.00, "Test"),
    Transaction(date(2026, 8, 9), "TESCO STORES 1187", -20.50, "Test"),
    Transaction(date(2026, 8, 3), "PRET A MANGER 0442", -6.25, "Test"),
    Transaction(date(2026, 8, 28), "ACME LTD SALARY", 1850.00, "Test"),
    Transaction(date(2026, 8, 2), "TRANSFER TO REVOLUT", -150.00, "Test"),
    Transaction(date(2026, 8, 5), "AMAZON", -30.00, "Test"),
    Transaction(date(2026, 8, 7), "AMAZON REFUND", 10.00, "Test"),
    Transaction(date(2026, 9, 1), "TESCO STORES 3021", -15.00, "Test"),
    Transaction(date(2026, 9, 2), "MYSTERY SHOP", -9.99, "Test"),
]

class TestSummary(unittest.TestCase):
    def test_by_category_skips_income_and_transfers_and_nets_refunds(self):
        self.assertEqual(summary.by_category(ROWS, MEMORY, "2026-07"),
                         {"Groceries": 60.50, "Shopping": 20.00, "Eating out": 6.25})

    def test_unsorted_shops_still_count(self):
        self.assertEqual(summary.by_category(ROWS, MEMORY, "2026-08"),
                         {"Groceries": 15.00, "Uncategorised": 9.99})

    def test_by_month(self):
        self.assertEqual(summary.by_month(ROWS, MEMORY), {"2026-07": 86.75, "2026-08": 24.99})

    def test_top_merchants_groups_branches(self):
        top = summary.top_merchants(ROWS, MEMORY)
        self.assertEqual(top[0], ("TESCO STORES", 75.50, 3))
        self.assertEqual(len(top), 5)

    def test_by_day_skips_income_and_transfers_and_nets_refunds(self):
        self.assertEqual(summary.by_day(ROWS, MEMORY, "2026-07"), {
            date(2026, 8, 1): 40.00, date(2026, 8, 3): 6.25, date(2026, 8, 5): 30.00, date(2026, 8, 9): 20.50})
        # 2 Aug was only a transfer, 7 Aug only a refund and 28 Aug only salary, so they're left out
        self.assertEqual(sum(summary.by_day(ROWS, MEMORY).values()), 86.75 + 24.99 + 10.00)

    def test_month_names(self):
        self.assertEqual(summary.month_name("2026-08"), "27 Aug – 24 Sep 2026")
        self.assertEqual(summary.previous_month("2026-08"), "2026-07")
        self.assertEqual(summary.previous_month("2027-01"), "2026-12")

    def test_headline(self):
        self.assertEqual(summary.headline(ROWS, MEMORY, "2026-08"),
                         ("£25 spent 27 Aug – 24 Sep 2026", "2 payments · 2 categories"))
        self.assertEqual(summary.headline(ROWS, MEMORY), ("£112 spent across all pay months", "6 payments · 4 categories"))

    def test_insights_for_a_month(self):
        cards = summary.insights(ROWS, MEMORY, "2026-08")
        self.assertEqual([(c["icon"], c["colour"], c["title"]) for c in cards], [
            ("down", "good", "£62 less than last month"),        # 86.75 last pay month, 24.99 this one
            ("dot", "Groceries", "Biggest: Groceries"),
            ("day", "neutral", "Biggest day: Tue 1 Sep")])
        self.assertEqual(cards[0]["caption"], "71% down on 27 Jul – 26 Aug 2026")

    def test_first_month_has_nothing_to_compare(self):
        self.assertEqual(summary.insights(ROWS, MEMORY, "2026-07")[0]["title"], "Nothing to compare yet")

    def test_half_loaded_last_month_is_not_compared(self):
        # Without the 27 Jul salary, the statements start on 1 Aug, so 27 Jul – 26 Aug isn't fully loaded
        self.assertEqual(summary.insights(ROWS[1:], MEMORY, "2026-08")[0]["title"], "Nothing to compare yet")

    def test_insights_for_all_months(self):
        self.assertEqual([c["title"] for c in summary.insights(ROWS, MEMORY)],
                         ["£56 a month", "Biggest month: Jul–Aug", "Top shop: Tesco Stores"])
        self.assertEqual(summary.insights([], MEMORY), [])

    def test_nothing_sorted_yet(self):
        # Before sorting, salary is just an unsorted payment. It used to be taken off the month's
        # spending, leaving no month to call "biggest" and crashing the Summary tab
        rows = [Transaction(date(2026, 9, 1), "ACME LTD SALARY 99", 1850.00, "Test"),
                Transaction(date(2026, 9, 2), "NEW CAFE", -6.00, "Test"),
                Transaction(date(2026, 9, 3), "NEW SHOP", -14.00, "Test")]
        for month in (None, "2026-08"):
            self.assertEqual(summary.insights(rows, {}, month), [summary.NOTHING_SORTED_CARD])
        self.assertEqual(summary.by_month(rows, {}), {"2026-08": 20.00})   # the salary doesn't cancel it out
        self.assertEqual(summary.headline(rows, {}, "2026-08")[0], "£20 spent 27 Aug – 24 Sep 2026")
        # Once just one shop is sorted, the normal cards come back, and nothing crashes
        sorted_one = {"NEW CAFE": {"category": "Eating out", "by": "ai"}}
        self.assertEqual([c["title"] for c in summary.insights(rows, sorted_one)],
                         ["£20 a month", "Biggest month: Aug–Sep", "Top shop: New Shop"])
        self.assertEqual(summary.insights(rows, sorted_one, "2026-08")[1]["title"], "Biggest: Uncategorised")

    def test_month_with_no_spending(self):
        only_money_in = [Transaction(date(2026, 9, 1), "ACME LTD SALARY", 1850.00, "Test")]
        self.assertEqual(summary.insights(only_money_in, MEMORY, "2026-08"), [summary.NO_SPENDING_CARD])
        self.assertEqual(summary.insights(only_money_in, MEMORY), [summary.NO_SPENDING_CARD])
        self.assertEqual(summary.by_month(only_money_in, MEMORY), {"2026-08": 0})
        self.assertEqual(summary.insights([], MEMORY), [])   # nothing loaded at all: no cards

    def test_refund_bigger_than_the_days_spending(self):
        # £20 at Tesco and a £30 Amazon refund on the same day: Groceries counts £20, but that day
        # nets to money in, so there's no "biggest day" card (and no crash)
        rows = [Transaction(date(2026, 9, 1), "TESCO STORES 1", -20.00, "Test"),
                Transaction(date(2026, 9, 1), "AMAZON REFUND", 30.00, "Test")]
        cards = summary.insights(rows, MEMORY, "2026-08")
        self.assertEqual([c["title"] for c in cards], ["Nothing to compare yet", "Biggest: Groceries"])
        self.assertEqual(summary.by_month(rows, MEMORY), {"2026-08": 20.00})

    def test_charts_cope_with_an_empty_month(self):
        import io
        import charts
        figure = charts.calendar_chart({}, "Empty", date(2026, 8, 27), date(2026, 9, 24))
        figure.savefig(io.BytesIO(), format="png")

    def test_complete_months(self):
        self.assertEqual(summary.complete_months(ROWS), ["2026-07"])   # data stops 2 Sep, before 24 Sep
        self.assertEqual(summary.complete_months(ROWS[1:]), [])

    def test_suggest_budgets(self):
        # Only 27 Jul – 26 Aug is complete: Groceries 60.50 -> £65, Shopping 20 -> £20, Eating out 6.25 -> £10
        self.assertEqual(summary.suggest_budgets(ROWS, MEMORY),
                         ({"Groceries": 65, "Eating out": 10, "Shopping": 20}, 1))
        self.assertEqual(summary.suggest_budgets(ROWS[1:], MEMORY), ({}, 0))

    def test_budget_warning_card(self):
        rows = [("Groceries", 70, 60.50, 9.50, "close"), ("Eating out", 50, 6.25, 43.75, "ok")]
        card = summary.budget_warning(rows)
        self.assertEqual((card["colour"], card["title"], card["caption"]),
                         ("warn", "Groceries is close to its budget", "Groceries 86% used"))
        rows.append(("Shopping", 15, 20.00, -5.00, "over"))
        card = summary.budget_warning(rows)
        self.assertEqual((card["colour"], card["title"], card["caption"]),
                         ("bad", "2 budgets need a look", "Shopping £5.00 over · Groceries 86% used"))
        self.assertIsNone(summary.budget_warning(rows[1:2]))
        # Long lists are cut short, and a budget that isn't over never says 100%
        rows = [(c, 25, 24.99, 0.01, "close") for c in ("Gym", "Bills", "Cash", "Travel", "Health")]
        self.assertEqual(summary.budget_warning(rows)["caption"],
                         "Gym 99% used · Bills 99% used · Cash 99% used · and 2 more on the Budgets tab")

    def test_budget_warnings(self):
        spent = {"Groceries": 60.50, "Eating out": 6.25, "Shopping": 20.00}
        rows = summary.budget_status(spent, {"Groceries": 70, "Eating out": 50, "Shopping": 15, "Gym": 0})
        self.assertEqual(rows, [("Groceries", 70, 60.50, 9.50, "close"),
                                ("Eating out", 50, 6.25, 43.75, "ok"),
                                ("Shopping", 15, 20.00, -5.00, "over")])

class TestCharts(unittest.TestCase):
    def test_calendar_squares(self):
        import charts
        daily = {date(2026, 9, 1): 10.0, date(2026, 9, 2): 50.0, date(2026, 9, 30): 1.0}
        cells = charts.calendar_cells(daily, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(len(cells), 30)
        by_day = {day: (column, row, shade) for day, column, row, shade in cells}
        self.assertEqual(by_day[date(2026, 9, 1)], (0, 1, 1))   # a Tuesday in the first week, a little spent
        self.assertEqual(by_day[date(2026, 9, 2)], (0, 2, 5))   # the biggest day gets the darkest shade
        self.assertEqual(by_day[date(2026, 9, 7)], (1, 0, 0))   # next Monday starts a new column, nothing spent
        self.assertEqual(by_day[date(2026, 9, 30)], (4, 2, 1))

    def test_label_colours_are_readable(self):
        import charts
        self.assertEqual(charts.text_on("#2F6BFF"), "#FFFFFF")   # white on the dark blue
        self.assertEqual(charts.text_on("#D3E0FF"), charts.TEXT)  # dark text on the pale blue

    def test_charts_draw(self):
        import io
        import charts
        totals = summary.by_category(ROWS, MEMORY, "2026-08")
        for figure in (charts.category_chart(totals, "Aug"),
                       charts.month_chart(summary.by_month(ROWS, MEMORY), "By month"),
                       charts.donut_chart(totals, "Aug"),
                       charts.calendar_chart(summary.by_day(ROWS, MEMORY, "2026-07"), "Aug",
                                             date(2026, 8, 1), date(2026, 8, 31)),
                       charts.calendar_chart(summary.by_day(ROWS, MEMORY), "All",
                                             date(2026, 8, 1), date(2026, 9, 30))):
            buffer = io.BytesIO()
            figure.savefig(buffer, format="png")   # drawn in memory, nothing saved to disk
            self.assertGreater(len(buffer.getvalue()), 1000)

if __name__ == "__main__":
    unittest.main()
