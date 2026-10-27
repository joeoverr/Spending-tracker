# Finds out why shops in your statements aren't being sorted, WITHOUT showing what's in them.
# It reads the statements folder the same way the app does, then asks the local AI about the
# shops the app doesn't know yet, batch by batch. It prints only counts, timings, error types and
# category names, never shop names or amounts, and saves nothing (your categories file is untouched).
# Run it with:  py check_sorting.py
import time
from collections import Counter
import app_logic
import banks
import categorise
import storage

def main():
    transactions, needs_setup, failed = banks.read_folder(storage.STATEMENTS_DIR, app_logic.load_csv_formats())
    print(f"Statements read: payments found: {len(transactions)}; files needing column setup: {len(needs_setup)}; "
          f"files that failed: {len(failed)}")
    memory = categorise.load_memory()
    print(f"Shops already remembered: {len(memory)} "
          f"(sorted by the AI: {sum(v.get('by') == 'ai' for v in memory.values())}, "
          f"by you: {sum(v.get('by') == 'you' for v in memory.values())})")
    keys = Counter(categorise.merchant_key(t.description) for t in transactions)
    print(f"Different shops in your statements: {len(keys)}")
    print(f"   Most payments sharing one shop name: {max(keys.values(), default=0)}")
    print(f"   Shop names longer than 30 letters: {sum(len(k) > 30 for k in keys)}")
    print(f"   Shop names that still contain numbers: {sum(any(c.isdigit() for c in k) for k in keys)}")
    print(f"   Payments whose shop is already sorted: {sum(n for k, n in keys.items() if k in memory)}")
    todo = categorise.unknown_merchants(transactions, memory)
    print(f"Shops the AI still needs to sort: {len(todo)}")
    problem = app_logic.ai_problem()
    print(f"Ollama check: {problem or 'ready'}")
    if problem or not todo:
        return
    answers = Counter()
    for start in range(0, len(todo), categorise.BATCH_SIZE):
        batch = todo[start:start + categorise.BATCH_SIZE]
        began = time.perf_counter()
        try:
            result = categorise.ask_ai(batch)
            answers.update(result.values())
            print(f"   Batch {start // categorise.BATCH_SIZE + 1}: {len(result)} of {len(batch)} sorted "
                  f"in {time.perf_counter() - began:.0f}s")
        except Exception as error:
            print(f"   Batch {start // categorise.BATCH_SIZE + 1}: FAILED after {time.perf_counter() - began:.0f}s "
                  f"with {type(error).__name__}")
    print("Categories the AI chose: " + ", ".join(f"{c} {n}" for c, n in answers.most_common()))

if __name__ == "__main__":
    main()
