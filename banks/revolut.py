# Reads Revolut's CSV export (Type, Product, Started Date, Completed Date, Description, Amount, Fee, ...)
import csv
from .common import Transaction, parse_amount, parse_date, tidy

NAME = "Revolut"
FILE_TYPES = (".csv",)
DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y")

def looks_like(path, first_text):
    header = first_text.splitlines()[0] if first_text else ""
    return path.lower().endswith(".csv") and "Started Date" in header and "Description" in header

def read(path):
    transactions = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            # Skip payments that were cancelled or are still pending
            if row.get("State", "COMPLETED").upper() != "COMPLETED":
                continue
            when = parse_date(row.get("Completed Date") or row["Started Date"], DATE_FORMATS)
            amount = parse_amount(row["Amount"])
            fee = parse_amount(row.get("Fee") or "0") or 0
            if when and amount is not None:
                transactions.append(Transaction(when, tidy(row["Description"]), round(amount - fee, 2), NAME))
    return transactions
