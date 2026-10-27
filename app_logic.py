# The non-window jobs the app needs: opening a statement, remembering CSV column choices,
# checking the AI is ready and turning payments into table rows. The window (spending_app.py)
# only calls these, so they can be tested without opening it.
import filecmp
import math
import os
import shutil
import ollama
import banks
import payday
import storage
from banks import chase_uk, revolut, general_csv
from categorise import MODEL, category_of

AUTO = "Auto-detect"
NAMED_READERS = {chase_uk.NAME: chase_uk, revolut.NAME: revolut}

def bank_choices():
    return [AUTO, *NAMED_READERS, general_csv.NAME]

def load_csv_formats():
    return storage.load_json(storage.CSV_FORMATS_FILE, {})

def save_csv_format(path, settings, csv_formats):
    # Remembers your column choices, so the next statement from the same bank opens straight away
    csv_formats[banks.csv_key(path)] = settings
    storage.save_json(storage.CSV_FORMATS_FILE, csv_formats)

def load_statement(path, choice, csv_formats):
    # Returns the payments in the file, or None if it's a CSV that needs its columns picking first.
    # Raises ValueError with a plain-English message if the file can't be read.
    if choice == AUTO:
        transactions = banks.read_file(path, csv_formats)
    elif choice in NAMED_READERS:
        reader = NAMED_READERS[choice]
        if not path.lower().endswith(reader.FILE_TYPES):
            raise ValueError(f"{choice} statements are {' or '.join(reader.FILE_TYPES)} files. "
                             "Pick a different file, or change the bank.")
        try:
            transactions = reader.read(path)
        except (KeyError, IndexError):   # the file doesn't have the columns this bank uses
            transactions = []
    else:
        if not path.lower().endswith(".csv"):
            raise ValueError("The general reader only opens .csv files.")
        settings = csv_formats.get(banks.csv_key(path))
        transactions = general_csv.read(path, settings) if settings else None
    if transactions == []:
        raise ValueError("No payments were found in this file. Is the bank right?")
    return transactions

def file_stamp(folder, name):
    # Changes if a file is replaced or edited, so "Check for new statements" reads it again
    info = os.stat(os.path.join(folder, name))
    return f"{name}|{info.st_size}|{info.st_mtime_ns}"

def new_statements(folder, seen):
    # The statement files in the folder that haven't been read yet this session
    return [name for name in banks.statement_files(folder) if file_stamp(folder, name) not in seen]

def keep_copy(path, folder):
    # Copies a statement you opened into the statements folder, so it loads by itself next time.
    # It's copied, never moved, and nothing is overwritten. Returns the copy's name, or None if
    # the file is already in the folder.
    if os.path.dirname(os.path.abspath(path)) == os.path.abspath(folder):
        return None
    os.makedirs(folder, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(path))
    name, number = stem + ext, 2
    while os.path.exists(os.path.join(folder, name)):
        if filecmp.cmp(path, os.path.join(folder, name), shallow=False):
            return None   # the same file is already there
        name, number = f"{stem} ({number}){ext}", number + 1
    shutil.copy2(path, os.path.join(folder, name))
    return name

# ----- Budgets and small settings, saved in data/ (which Git ignores) -----
def load_budgets():
    return storage.load_json(storage.BUDGETS_FILE, {})

def read_budget_boxes(boxes):
    # Turns what you typed in the budget boxes into numbers: ({category: amount}, problems).
    # A blank box or 0 means no budget. "£50", "50" and "1,200.50" all work.
    budgets, problems = {}, []
    for category, text in boxes.items():
        text = text.strip().replace("£", "").replace(",", "")
        if not text:
            continue
        try:
            amount = round(float(text), 2)
        except ValueError:
            problems.append(f"{category}: \"{boxes[category].strip()}\" isn't a number")
            continue
        if amount < 0 or not math.isfinite(amount):
            problems.append(f"{category}: a budget can't be below £0")
        elif amount > 0:
            budgets[category] = amount
    return budgets, problems

def save_budgets(budgets):
    storage.save_json(storage.BUDGETS_FILE, budgets)

def load_settings():
    return storage.load_json(storage.SETTINGS_FILE, {})

def save_setting(key, value):
    settings = load_settings()
    settings[key] = value
    storage.save_json(storage.SETTINGS_FILE, settings)

def guess_columns(headers):
    # Best first guesses for the column picker, e.g. "Posted" for the date, "Merchant" for the description
    def find(*words):
        return next((h for h in headers if any(w in h.lower() for w in words)), headers[0] if headers else "")
    return {"date": find("date", "posted", "when"),
            "description": find("description", "merchant", "details", "payee", "name", "narrative"),
            "amount": find("amount", "value", "paid", "money")}

def ai_problem():
    # None if the local AI is ready, otherwise a message saying what to do
    try:
        models = [m.model for m in ollama.list().models]
    except Exception:
        return ("Can't reach Ollama, so your shops weren't sorted. Start Ollama from the Start menu, "
                "wait a few seconds, then click Try again.")
    if not any(name == MODEL or name.startswith(MODEL + ":") for name in models):
        return f"Ollama is running but the {MODEL} model isn't installed. Run: ollama pull {MODEL}"
    return None

def money(amount):
    return f"-£{-amount:,.2f}" if amount < 0 else f"+£{amount:,.2f}"

def table_rows(transactions, memory, month=None):
    # One row per payment for the table, newest first: (date, description, amount, category, bank).
    # month is a pay month, e.g. "2026-09" = 25 Sep – 26 Oct 2026
    chosen = [t for t in transactions if month is None or payday.pay_month_of(t.date) == month]
    return [(t.date.strftime("%d %b %Y"), t.description, money(t.amount), category_of(t, memory), t.bank)
            for t in sorted(chosen, key=lambda t: t.date, reverse=True)]
