# The one standard shape every bank's statement is turned into
import re
from dataclasses import dataclass
from datetime import date, datetime

@dataclass
class Transaction:
    date: date
    description: str
    amount: float      # money out is negative, money in is positive
    bank: str

def parse_amount(text):
    # Turns "-£1,234.56", "+£3.00", "(12.50)", "12.50-" or "£4" into a number
    text = str(text).strip().replace("£", "").replace(",", "").replace(" ", "")
    if not text:
        return None
    negative = text.startswith("-") or text.endswith("-") or (text.startswith("(") and text.endswith(")"))
    digits = text.strip("+-()")
    if not re.fullmatch(r"\d+(\.\d+)?", digits):
        return None
    value = round(float(digits), 2)
    return -value if negative else value

def parse_date(text, formats):
    text = str(text).strip()
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None

def tidy(text):
    # Statements sometimes split a description over two lines
    return " ".join(str(text).split())
