# Reads Chase UK PDF statements
import re
import pdfplumber
from .common import Transaction, parse_amount, parse_date, tidy

NAME = "Chase UK"
FILE_TYPES = (".pdf",)
DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d/%m/%y")
MONEY = r"[+-]?£[\d,]+\.\d{2}-?"
LINE = re.compile(rf"^(\d{{1,2}} [A-Za-z]{{3,9}} \d{{4}}|\d{{2}}/\d{{2}}/\d{{2,4}})\s+(.+?)\s+({MONEY})(?:\s+{MONEY})?$")

def looks_like(path, first_text):
    return path.lower().endswith(".pdf")

def read(path):
    with pdfplumber.open(path) as pdf:
        transactions = from_tables(pdf)
        if not transactions:
            # No ruled table found, so fall back to reading the page text line by line
            transactions = from_text(pdf)
    return transactions

def find_columns(header):
    # Works out which column is which from the header row, e.g. Date | Transaction details | Amount | Balance
    names = [tidy(cell or "").lower() for cell in header]
    def pick(*words):
        return next((i for i, name in enumerate(names) if any(w in name for w in words)), None)
    columns = {"date": pick("date"), "description": pick("detail", "description"), "amount": pick("amount")}
    return columns if None not in columns.values() else None

def from_tables(pdf):
    transactions, columns = [], None
    for page in pdf.pages:
        for table in page.extract_tables():
            for row in table:
                columns = find_columns(row) or columns
                if not columns:
                    continue
                cell = lambda key: row[columns[key]] if columns[key] < len(row) else ""
                when = parse_date(cell("date") or "", DATE_FORMATS)
                amount = parse_amount(cell("amount") or "")
                if when and amount is not None:
                    transactions.append(Transaction(when, tidy(cell("description")), amount, NAME))
    return transactions

def from_text(pdf):
    transactions = []
    for page in pdf.pages:
        for line in (page.extract_text() or "").splitlines():
            match = LINE.match(line.strip())
            if match and "balance" not in match.group(2).lower():
                when = parse_date(match.group(1), DATE_FORMATS)
                amount = parse_amount(match.group(3))
                if when and amount is not None:
                    transactions.append(Transaction(when, tidy(match.group(2)), amount, NAME))
    return transactions
