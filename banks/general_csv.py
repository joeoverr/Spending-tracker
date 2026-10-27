# Reads a CSV from any other bank. You tell it which column is which.
import csv
from .common import Transaction, parse_amount, parse_date, tidy

NAME = "Other bank (CSV)"
FILE_TYPES = (".csv",)
DATE_FORMATS = {  # what you see in the file -> how Python reads it
    "31/12/2026": "%d/%m/%Y",
    "31/12/26": "%d/%m/%y",
    "2026-12-31": "%Y-%m-%d",
    "12/31/2026": "%m/%d/%Y",
    "31 Dec 2026": "%d %b %Y",
    "31-12-2026": "%d-%m-%Y",
}

def looks_like(path, first_text):
    return path.lower().endswith(".csv")

def headers(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return next(csv.reader(f), [])

def read(path, settings):
    # settings = {"bank": "My Bank", "date": column, "description": column, "amount": column,
    #             "date_format": "31/12/2026", "spending_is_positive": False}
    fmt = DATE_FORMATS.get(settings["date_format"], settings["date_format"])
    flip = -1 if settings.get("spending_is_positive") else 1
    transactions = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            when = parse_date(row.get(settings["date"], ""), [fmt])
            amount = parse_amount(row.get(settings["amount"], ""))
            if when and amount is not None:
                transactions.append(Transaction(when, tidy(row.get(settings["description"], "")),
                                                flip * amount, settings.get("bank") or NAME))
    return transactions
