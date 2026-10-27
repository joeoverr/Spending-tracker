# Makes the MADE-UP sample statements in the samples folder.
# Every name, amount and date here is invented, for testing and the GitHub demo only.
# Run it again any time with:  py make_samples.py
import csv
import random
from datetime import date, timedelta
from fpdf import FPDF

random.seed(42)  # same "random" data every time
MONTHS = [(2026, 8), (2026, 9), (2026, 10)]

# (description as the bank shows it, lowest price, highest price, times per month)
SHOPS = [
    ("TESCO STORES 3021", 8, 45, 5),
    ("SAINSBURYS S/MKT 0871", 10, 60, 3),
    ("ALDI 4410 LEEDS", 15, 50, 2),
    ("PRET A MANGER 0442", 3, 9, 4),
    ("NANDOS LEEDS", 14, 32, 1),
    ("DELIVEROO", 12, 30, 2),
    ("UBER *TRIP", 6, 18, 2),
    ("TFL TRAVEL CH", 3, 9, 3),
    ("STEAMGAMES.COM 4259522", 5, 40, 1),
    ("AMAZON MKTPLACE PMTS", 8, 60, 2),
]
BILLS = [  # (day of month, description, amount)
    (1, "OCTOPUS ENERGY", 78.40),
    (3, "LEEDS CITY COUNCIL TAX", 132.00),
    (5, "NETFLIX.COM", 10.99),
    (8, "SPOTIFY UK", 11.99),
    (10, "PUREGYM LTD", 24.99),
    (15, "THREE MOBILE", 18.00),
    (20, "XBOX GAME PASS", 14.99),
]

def chase_transactions():
    rows = []
    for year, month in MONTHS:
        rows.append((date(year, month, 28), "ACME WIDGETS LTD SALARY", 1850.00))
        rows.append((date(year, month, 2), "TRANSFER TO REVOLUT", -150.00))
        for day, name, amount in BILLS:
            rows.append((date(year, month, day), name, -amount))
        for name, low, high, times in SHOPS:
            for _ in range(times):
                day = random.randint(1, 28)
                rows.append((date(year, month, day), name, -round(random.uniform(low, high), 2)))
    rows.append((date(2026, 9, 14), "AMAZON MKTPLACE PMTS REFUND", 19.99))
    return sorted(rows)

def money(value, sign=True):
    text = f"£{abs(value):,.2f}"
    return ("-" if value < 0 else "+") + text if sign else text

def make_chase_pdf(path):
    rows = chase_transactions()
    pdf = FPDF()
    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "SAMPLE statement - made-up data, not a real bank", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, "Layout styled loosely on a Chase UK current account statement", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Account holder: A. Sample    Account: 00000000    Sort code: 00-00-00", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Period: 01 Aug 2026 to 31 Oct 2026", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    balance = 1200.00
    with pdf.table(col_widths=(28, 92, 35, 35), text_align=("LEFT", "LEFT", "RIGHT", "RIGHT")) as table:
        table.row(["Date", "Transaction details", "Amount", "Balance"])
        table.row(["01 Aug 2026", "Opening balance", "", money(balance, sign=False)])
        for day, name, amount in rows:
            balance += amount
            table.row([day.strftime("%d %b %Y"), name, money(amount), money(balance, sign=False)])
        table.row(["31 Oct 2026", "Closing balance", "", money(balance, sign=False)])
    pdf.output(path)
    return len(rows)

def make_revolut_csv(path):
    header = ["Type", "Product", "Started Date", "Completed Date", "Description",
              "Amount", "Fee", "Currency", "State", "Balance"]
    rows, balance = [], 20.00
    def add(when, kind, name, amount, fee=0.0, state="COMPLETED"):
        nonlocal balance
        if state == "COMPLETED":
            balance += amount - fee
        stamp = when.strftime("%Y-%m-%d") + f" {random.randint(8, 21):02d}:{random.randint(0, 59):02d}:12"
        rows.append([kind, "Current", stamp, stamp if state == "COMPLETED" else "", name,
                     f"{amount:.2f}", f"{fee:.2f}", "GBP", state, f"{balance:.2f}" if state == "COMPLETED" else ""])
    for year, month in MONTHS:
        add(date(year, month, 2), "TOPUP", "Top-up by *0000", 150.00)
        for name, low, high, times in [("Costa Coffee", 3, 6, 4), ("Greggs", 2, 6, 3),
                                       ("Trainline", 12, 45, 1), ("Game Store Online", 10, 35, 1)]:
            for _ in range(times):
                when = date(year, month, random.randint(3, 28))
                add(when, "CARD_PAYMENT", name, -round(random.uniform(low, high), 2))
        add(date(year, month, 18), "CARD_PAYMENT", "Holiday Hotel Lisbon", -round(random.uniform(40, 90), 2), fee=0.50)
    add(date(2026, 10, 25), "CARD_PAYMENT", "Costa Coffee", -4.20, state="REVERTED")
    rows.sort(key=lambda r: r[2])
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return len(rows)

def make_general_csv(path):
    # A pretend "other bank": day/month/year dates and spending shown as negative
    rows = []
    for year, month in MONTHS:
        start = date(year, month, 1)
        for _ in range(6):
            when = start + timedelta(days=random.randint(0, 27))
            name, low, high = random.choice([("SHELL PETROL 22", 30, 60), ("BOOTS 1182", 4, 20),
                                             ("ODEON CINEMAS", 8, 15), ("WAGAMAMA", 15, 30)])
            rows.append([when.strftime("%d/%m/%Y"), name, f"REF{random.randint(10000, 99999)}",
                         f"{-random.uniform(low, high):.2f}"])
    rows.sort(key=lambda r: (r[0][6:], r[0][3:5], r[0][:2]))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Posted", "Merchant", "Reference", "Value"])
        writer.writerows(rows)
    return len(rows)

if __name__ == "__main__":
    print("Chase-style PDF rows:", make_chase_pdf("samples/sample_chase_uk.pdf"))
    print("Revolut CSV rows:", make_revolut_csv("samples/sample_revolut.csv"))
    print("General CSV rows:", make_general_csv("samples/sample_other_bank.csv"))
