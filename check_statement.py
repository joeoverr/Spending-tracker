# Checks whether the Chase reader understands a real statement WITHOUT showing what's in it.
# It prints only counts, column names, date ranges, the two totals (to compare with your statement's
# summary box) and the "shape" of lines it couldn't read (letters become A and numbers become 9).
# It never prints shop names or single payments, and saves nothing.
# Run it with:  py check_statement.py statements\your-statement.pdf
import re
import sys
from collections import Counter
import pdfplumber
from banks import chase_uk

def shape(text):
    return re.sub(r"\d", "9", re.sub(r"[A-Za-z]", "A", text))

def main(path):
    with pdfplumber.open(path) as pdf:
        print(f"Pages: {len(pdf.pages)}")
        headers = []
        for page in pdf.pages:
            for table in page.extract_tables():
                headers += [" | ".join(c or "" for c in row) for row in table if chase_uk.find_columns(row)]
        print(f"Header rows found: {len(headers)}")
        for header in dict.fromkeys(headers):
            print(f"   {header}")
        from_tables, from_text = chase_uk.from_tables(pdf), chase_uk.from_text(pdf)
        print(f"Payments found by reading tables: {len(from_tables)}")
        print(f"Payments found by reading text lines: {len(from_text)}")
        unread, signed, unsigned = Counter(), 0, 0
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                match = chase_uk.LINE.match(line.strip())
                if match and "balance" in match.group(2).lower():
                    continue   # an opening or closing balance line, not a payment
                if match:
                    # Does the amount say plainly whether money went out or came in?
                    if match.group(3)[0] in "+-" or match.group(3).endswith("-"):
                        signed += 1
                    else:
                        unsigned += 1
                elif re.match(r"^\d{1,2}[ /]", line.strip()):
                    unread[shape(line.strip())] += 1
    best = from_tables or from_text
    if best:
        money_in = [t.amount for t in best if t.amount > 0]
        money_out = [-t.amount for t in best if t.amount < 0]
        print(f"Dates run from {min(t.date for t in best):%d %b %Y} to {max(t.date for t in best):%d %b %Y}")
        print(f"Money out: {len(money_out)} payments, money in: {len(money_in)} payments")
        print(f"Amounts with a + or - sign: {signed}, without one: {unsigned}")
        print()
        print("Compare these two totals with the summary box on your statement.")
        print("You only need to tell me whether they match. Please don't paste them.")
        print(f"   Total money out: £{sum(money_out):,.2f}")
        print(f"   Total money in:  £{sum(money_in):,.2f}")
        print()
    print(f"Lines starting with a number that couldn't be read: {sum(unread.values())}")
    for line, count in unread.most_common():
        print(f"   {count} x  {line}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: py check_statement.py statements\\your-statement.pdf")
    main(sys.argv[1])
