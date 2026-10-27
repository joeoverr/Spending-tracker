# Sorts payments into categories. Each shop is asked about once (in batches) using the
# local AI, then remembered in data/categories.json. Nothing is sent over the internet.
import json
import re
import ollama
from storage import CATEGORIES_FILE, load_json, save_json

MODEL = "llama3.1:8b"
CATEGORIES = ["Groceries", "Eating out", "Transport", "Bills", "Subscriptions", "Gaming", "Gym",
              "Shopping", "Entertainment", "Health", "Travel", "Cash", "Income", "Transfers", "Other"]
NOT_SPENDING = {"Income", "Transfers"}   # left out of spending totals
UNSORTED = "Uncategorised"
BATCH_SIZE = 25
TOKENS_PER_SHOP = 15   # an answer like  "12": "Eating out",  is about 8 tokens, so this leaves room

SYSTEM = ("You sort UK bank statement entries into budget categories. "
          "Each entry is a merchant name as printed on a statement. "
          "Use Transfers for money moved between the person's own accounts or to/from people: "
          "anything with 'top-up', 'top up' or 'transfer' in it is always Transfers. "
          "Use Income only for salary, wages and benefits. A refund goes in the same category "
          "as the shop it came from (an Amazon refund is Shopping). Use Subscriptions for "
          "streaming, music and software plans, Bills for energy, council tax, phone and rent, "
          "Gaming for games and game stores, Travel for hotels, flights and trains. "
          f"Allowed categories: {', '.join(CATEGORIES)}.")

def merchant_key(description):
    # "TESCO STORES 3021" and "TESCO STORES 1187" are the same shop, so drop numbers and symbols
    text = description.upper().replace("*", " ")
    text = re.sub(r"^(CARD PAYMENT TO|PAYMENT TO|DIRECT DEBIT TO|DD|SO|FASTER PAYMENT TO)\s+", "", text)
    words = [w.strip(".,:;/-") for w in text.split() if not re.search(r"\d", w)]
    key = " ".join(w for w in words if w)[:40]
    return " ".join(key.split()[:4]) or description.upper()

def load_memory():
    return load_json(CATEGORIES_FILE, {})

def category_of(transaction, memory):
    saved = memory.get(merchant_key(transaction.description))
    return saved["category"] if saved else UNSORTED

def set_category(memory, key, category):
    # Your own choice always wins and is never overwritten by the AI
    memory[key] = {"category": category, "by": "you"}
    save_json(CATEGORIES_FILE, memory)

def unknown_merchants(transactions, memory):
    found = {}
    for t in transactions:
        key = merchant_key(t.description)
        if key not in memory and key not in found:
            found[key] = t.amount > 0
    return list(found.items())   # [(key, is_money_in), ...]

def ask_ai(batch):
    lines = [f"{i}. {key}" + (" (money in)" if money_in else "")
             for i, (key, money_in) in enumerate(batch, 1)]
    # The answer has to be one allowed category per number, nothing else
    schema = {"type": "object", "required": [str(i) for i in range(1, len(batch) + 1)],
              "properties": {str(i): {"type": "string", "enum": CATEGORIES} for i in range(1, len(batch) + 1)}}
    # num_predict caps the answer's length, so a confused AI fails in seconds instead of
    # writing forever (a known hiccup with structured answers)
    options = {"temperature": 0, "num_ctx": 4096, "num_predict": TOKENS_PER_SHOP * len(batch) + 40}
    response = ollama.chat(model=MODEL, format=schema, options=options,
                           messages=[{"role": "system", "content": SYSTEM},
                                     {"role": "user", "content": "Categorise each entry:\n" + "\n".join(lines)}])
    answer = json.loads(response["message"]["content"])
    return {key: answer.get(str(i)) for i, (key, _) in enumerate(batch, 1) if answer.get(str(i)) in CATEGORIES}

def sort_batch(batch, memory):
    # Sorts one batch into memory and returns the shops that couldn't be sorted. If the AI trips up
    # on a batch, it's split in half and each half tried again, down to one shop at a time, so one
    # awkward shop can't stop all the others. If Ollama can't be reached at all, that's raised.
    try:
        answers = ask_ai(batch)
    except ConnectionError:
        raise
    except Exception:
        if len(batch) == 1:
            return [batch[0][0]]
        half = len(batch) // 2
        return sort_batch(batch[:half], memory) + sort_batch(batch[half:], memory)
    for key, category in answers.items():
        memory[key] = {"category": category, "by": "ai"}
    return [key for key, _ in batch if key not in answers]

def categorise_new(transactions, memory, progress=None):
    # Asks the AI about every shop not seen before, saving after each batch.
    # Returns (how many shops were sorted, [shops that couldn't be sorted]).
    # progress(done, total) is called after each batch.
    todo = unknown_merchants(transactions, memory)
    failed = []
    for start in range(0, len(todo), BATCH_SIZE):
        failed += sort_batch(todo[start:start + BATCH_SIZE], memory)
        save_json(CATEGORIES_FILE, memory)
        if progress:
            progress(min(start + BATCH_SIZE, len(todo)), len(todo))
    return len(todo) - len(failed), failed
