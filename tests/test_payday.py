# Checks paydays and pay months against dates worked out by hand from a calendar
import unittest
from datetime import date
import payday

class TestPayday(unittest.TestCase):
    def test_paid_on_the_27th_when_it_is_a_working_day(self):
        self.assertEqual(payday.payday(2026, 10), date(2026, 10, 27))   # Tuesday
        self.assertEqual(payday.payday(2026, 11), date(2026, 11, 27))   # Friday

    def test_weekend_moves_back_to_friday(self):
        self.assertEqual(payday.payday(2026, 9), date(2026, 9, 25))     # Sun 27 Sep -> Fri 25 Sep
        self.assertEqual(payday.payday(2027, 2), date(2027, 2, 26))     # Sat 27 Feb -> Fri 26 Feb

    def test_bank_holidays_are_skipped_too(self):
        self.assertEqual(payday.payday(2026, 12), date(2026, 12, 24))   # Sun 27 Dec, Fri 25 is Christmas -> Thu 24
        self.assertEqual(payday.payday(2027, 3), date(2027, 3, 25))     # Sat 27 Mar, Fri 26 is Good Friday -> Thu 25
        self.assertEqual(payday.payday(2027, 12), date(2027, 12, 24))   # Mon 27 Dec is a bank holiday -> Fri 24

    def test_pay_months(self):
        self.assertEqual(payday.pay_month_of(date(2026, 9, 24)), "2026-08")
        self.assertEqual(payday.pay_month_of(date(2026, 9, 25)), "2026-09")   # payday starts the new pay month
        self.assertEqual(payday.pay_month_of(date(2026, 10, 26)), "2026-09")
        self.assertEqual(payday.pay_month_of(date(2027, 1, 5)), "2026-12")    # across New Year
        self.assertEqual(payday.dates("2026-09"), (date(2026, 9, 25), date(2026, 10, 26)))

    def test_names(self):
        self.assertEqual(payday.name("2026-09"), "25 Sep – 26 Oct 2026")
        self.assertEqual(payday.name("2026-12"), "24 Dec 2026 – 26 Jan 2027")
        self.assertEqual(payday.short_name("2026-12"), "Dec–Jan")

    def test_reminder_shows_the_2_days_before_payday(self):
        self.assertIsNone(payday.reminder_due(date(2026, 9, 22)))
        self.assertEqual(payday.reminder_due(date(2026, 9, 23)), date(2026, 9, 25))
        self.assertEqual(payday.reminder_due(date(2026, 9, 24)), date(2026, 9, 25))
        self.assertIsNone(payday.reminder_due(date(2026, 9, 25)))             # it's payday
        self.assertEqual(payday.reminder_due(date(2026, 12, 22)), date(2026, 12, 24))

if __name__ == "__main__":
    unittest.main()
