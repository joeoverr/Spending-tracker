# Picks the right reader for each statement file.
# To add a bank: make a new file in this folder (copy revolut.py) and add it to READERS below.
import os
from collections import Counter
from . import chase_uk, revolut, general_csv
from .common import Transaction

READERS = [chase_uk, revolut]   # checked in this order; any other CSV uses general_csv

def first_text(path):
    if path.lower().endswith(".pdf"):
        return ""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read(2000)

def detect(path):
    text = first_text(path)
    return next((reader for reader in READERS if reader.looks_like(path, text)), None)

def csv_key(path):
    # Files from the same bank share a header row, so it's used to remember your column choices
    return ",".join(general_csv.headers(path))

def read_file(path, csv_formats):
    reader = detect(path)
    if reader:
        return reader.read(path)
    if path.lower().endswith(".csv") and csv_key(path) in csv_formats:
        return general_csv.read(path, csv_formats[csv_key(path)])
    return None   # a CSV we haven't been told how to read yet

def merge(*statements):
    # Joins several statements' payments. If two statements overlap, each payment is kept once,
    # but two identical payments on the same day in one statement (e.g. two coffees) both stay.
    counts = Counter()
    for transactions in statements:
        file_counts = Counter((t.date, t.description, t.amount, t.bank) for t in transactions)
        for key, count in file_counts.items():
            counts[key] = max(counts[key], count)
    transactions = [Transaction(*key) for key, count in counts.items() for _ in range(count)]
    return sorted(transactions, key=lambda t: t.date)

def statement_files(folder):
    # The PDF and CSV files in a folder, by name (an empty list if the folder doesn't exist yet)
    if not os.path.isdir(folder):
        return []
    return [name for name in sorted(os.listdir(folder)) if name.lower().endswith((".pdf", ".csv"))]

def read_folder(folder, csv_formats, only=None):
    # Returns (transactions, files that need column setup, files that failed).
    # only: a list of file names to read, instead of every statement in the folder.
    statements, needs_setup, failed = [], [], []
    for name in statement_files(folder) if only is None else only:
        path = os.path.join(folder, name)
        try:
            transactions = read_file(path, csv_formats)
        except Exception as error:
            failed.append((name, str(error)))
            continue
        if transactions is None:
            needs_setup.append(path)
            continue
        statements.append(transactions)
    return merge(*statements), needs_setup, failed
