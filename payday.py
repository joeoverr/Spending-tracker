# Works out paydays and pay months. The payday rule: payday is PAY_DAY of each month (the 27th by
# default, so change it to suit), or the last working day before it if that day is a weekend or
# bank holiday. A pay month runs from one payday to the day before the next, and is named by the
# month its payday is in: with the default, "2026-09" = 25 Sep – 26 Oct 2026.
from datetime import date, timedelta

PAY_DAY = 27       # the day of the month payday falls on; change it to match your own
REMIND_DAYS = 2    # "Download your latest statement" shows this many days before payday

# England and Wales bank holidays (from gov.uk). Add next years' dates here when you need them;
# after the last one only weekends are skipped.
BANK_HOLIDAYS = {date(*d) for d in [
    (2026, 1, 1), (2026, 4, 3), (2026, 4, 6), (2026, 5, 4), (2026, 5, 25), (2026, 8, 31), (2026, 12, 25), (2026, 12, 28),
    (2027, 1, 1), (2027, 3, 26), (2027, 3, 29), (2027, 5, 3), (2027, 5, 31), (2027, 8, 30), (2027, 12, 27), (2027, 12, 28),
    (2028, 1, 3), (2028, 4, 14), (2028, 4, 17), (2028, 5, 1), (2028, 5, 29), (2028, 8, 28), (2028, 12, 25), (2028, 12, 26),
]}

def working_day(day):
    return day.weekday() < 5 and day not in BANK_HOLIDAYS

def payday(year, month):
    day = date(year, month, PAY_DAY)
    while not working_day(day):
        day -= timedelta(days=1)
    return day

def _next(year, month):
    return (year + 1, 1) if month == 12 else (year, month + 1)

def _before(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)

def pay_month_of(day):
    # Which pay month a date falls in, e.g. 3 Oct 2026 -> "2026-09"
    year, month = (day.year, day.month) if day >= payday(day.year, day.month) else _before(day.year, day.month)
    return f"{year}-{month:02d}"

def dates(key):
    # First and last day of a pay month: "2026-09" -> (25 Sep 2026, 26 Oct 2026)
    year, month = map(int, key.split("-"))
    return payday(year, month), payday(*_next(year, month)) - timedelta(days=1)

def name(key):
    # "2026-09" -> "25 Sep – 26 Oct 2026" (both years shown if it crosses New Year)
    first, last = dates(key)
    start = f"{first.day} {first:%b}" + ("" if first.year == last.year else f" {first.year}")
    return f"{start} – {last.day} {last:%b %Y}"

def short_name(key):
    # "2026-09" -> "Sep–Oct", for places with little room
    first, last = dates(key)
    return f"{first:%b}–{last:%b}"

def next_payday(today):
    # Today if today is payday, otherwise the next one
    day = payday(today.year, today.month)
    return day if day >= today else payday(*_next(today.year, today.month))

def reminder_due(today):
    # The coming payday if the "download your statement" reminder should show today, else None
    day = next_payday(today)
    return day if 0 < (day - today).days <= REMIND_DAYS else None
