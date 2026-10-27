# Where the app keeps its files. The statements and data folders are in .gitignore,
# so nothing in them can be uploaded to GitHub.
import json
import os
import sys

if getattr(sys, "frozen", False):   # running as an .exe
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

STATEMENTS_DIR = os.path.join(APP_DIR, "statements")
SAMPLES_DIR = os.path.join(APP_DIR, "samples")
DATA_DIR = os.path.join(APP_DIR, "data")
CATEGORIES_FILE = os.path.join(DATA_DIR, "categories.json")
BUDGETS_FILE = os.path.join(DATA_DIR, "budgets.json")
CSV_FORMATS_FILE = os.path.join(DATA_DIR, "csv_formats.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")   # small choices, e.g. a reminder you've dismissed
RUNDOWNS_DIR = os.path.join(DATA_DIR, "rundowns")          # one saved rundown per pay month

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default

def save_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
