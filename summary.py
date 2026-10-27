# Adds up the categorised payments: per category, per month, top shops and budgets.
# "Spending" leaves out Income and Transfers, and a refund takes money off its category.
# Money coming in from a shop that isn't sorted yet is left out too: before sorting, a salary
# payment is just another unsorted payment, and it would wipe out the whole month's spending.
# A "month" is a pay month (payday to the day before the next), keyed like "2026-09": see payday.py.
import math
from collections import defaultdict
import payday
from categorise import CATEGORIES, NOT_SPENDING, UNSORTED, category_of, merchant_key

WARN_AT = 0.8   # warn when 80% of a budget is used
SUGGEST_FROM = 3   # "Suggest from past spending" averages this many complete pay months
ROUND_TO = 5       # ...and rounds up to the next £5
WARNING_LIMIT = 3  # the budget warning card names this many budgets, then says "and N more"
BUDGET_CATEGORIES = [c for c in CATEGORIES if c not in NOT_SPENDING]

def month_of(transaction):
    return payday.pay_month_of(transaction.date)

def months(transactions):
    return sorted({month_of(t) for t in transactions})

def spending(transactions, memory, month=None):
    # Payments that count as spending, with their category: [(transaction, category), ...]
    rows = []
    for t in transactions:
        category = category_of(t, memory)
        if category in NOT_SPENDING or (category == UNSORTED and t.amount > 0):
            continue
        if month is None or month_of(t) == month:
            rows.append((t, category))
    return rows

def nothing_sorted(totals):
    # True when there's spending but none of it has a category yet (all "Uncategorised")
    return bool(totals) and set(totals) == {UNSORTED}

def by_category(transactions, memory, month):
    totals = defaultdict(float)
    for t, category in spending(transactions, memory, month):
        totals[category] -= t.amount
    totals = {c: round(v, 2) for c, v in totals.items() if round(v, 2) > 0}
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))

def by_month(transactions, memory):
    # Each pay month's total is the sum of its category totals, so the two always agree
    # (a category whose refunds outweigh its spending counts as £0, never below)
    return {m: round(sum(by_category(transactions, memory, m).values()), 2) for m in months(transactions)}

def by_day(transactions, memory, month=None):
    # Spending on each day that had any, for the calendar: {date: amount}
    totals = defaultdict(float)
    for t, _ in spending(transactions, memory, month):
        totals[t.date] -= t.amount
    return {day: round(v, 2) for day, v in sorted(totals.items()) if round(v, 2) > 0}

def top_merchants(transactions, memory, month=None, count=10):
    totals, visits = defaultdict(float), defaultdict(int)
    for t, _ in spending(transactions, memory, month):
        key = merchant_key(t.description)
        totals[key] -= t.amount
        visits[key] += 1
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:count]
    return [(key, round(total, 2), visits[key]) for key, total in ranked]

def budget_status(spent, budgets):
    # For each budgeted category: (category, budget, spent, left, "ok" / "close" / "over")
    rows = []
    for category, budget in budgets.items():
        if not budget:
            continue
        used = spent.get(category, 0.0)
        left = round(budget - used, 2)
        state = "over" if used > budget else "close" if used >= budget * WARN_AT else "ok"
        rows.append((category, budget, used, left, state))
    return rows

def money_in(transactions, memory, month=None):
    # Income received (salary and so on), not counting transfers between your own accounts
    return round(sum(t.amount for t in transactions if t.amount > 0 and category_of(t, memory) == "Income"
                     and (month is None or month_of(t) == month)), 2)

def compare(transactions, memory, month):
    # This pay month against the one before, or None if the one before isn't fully loaded.
    # Returns {before, total, last_total, change, share (of last month), rises, drops};
    # rises and drops are the 2 categories that went up / down the most: [(category, £ difference)]
    before = previous_month(month)
    now, then = by_category(transactions, memory, month), by_category(transactions, memory, before)
    last_total = round(sum(then.values()), 2)
    if last_total <= 0 or before not in complete_months(transactions):
        return None
    total = round(sum(now.values()), 2)
    diffs = {c: round(now.get(c, 0) - then.get(c, 0), 2) for c in set(now) | set(then)}
    ranked = sorted(diffs.items(), key=lambda item: item[1])
    return {"before": before, "total": total, "last_total": last_total, "change": round(total - last_total, 2),
            "share": abs(total - last_total) / last_total,
            "rises": [(c, d) for c, d in ranked[::-1][:2] if d > 0], "drops": [(c, d) for c, d in ranked[:2] if d < 0]}

def complete_months(transactions):
    # Pay months your loaded statements cover from start to end, oldest first
    if not transactions:
        return []
    first, last = min(t.date for t in transactions), max(t.date for t in transactions)
    return [m for m in months(transactions) if first <= payday.dates(m)[0] and payday.dates(m)[1] <= last]

def suggest_budgets(transactions, memory):
    # For "Suggest from past spending": each category's average over your last 3 complete
    # pay months, rounded up to the next £5. Returns ({category: amount}, how many months were used)
    used = complete_months(transactions)[-SUGGEST_FROM:]
    if not used:
        return {}, 0
    totals = defaultdict(float)
    for month in used:
        for category, amount in by_category(transactions, memory, month).items():
            totals[category] += amount
    suggestions = {c: math.ceil(round(totals[c] / len(used), 2) / ROUND_TO) * ROUND_TO
                   for c in BUDGET_CATEGORIES if totals[c] > 0}
    return suggestions, len(used)

def budget_warning(rows):
    # The Summary tab's warning card for budgets that are close or over, or None if all are fine
    over = [r for r in rows if r[4] == "over"]
    close = [r for r in rows if r[4] == "close"]
    if not over and not close:
        return None
    # Rounded down, so a budget that isn't over never says "100% used"
    parts = [f"{c} £{-left:,.2f} over" for c, _, _, left, _ in over] + \
            [f"{c} {math.floor(used / budget * 100)}% used" for c, budget, used, _, _ in close]
    if len(parts) == 1:
        title = f"{over[0][0]} is over budget" if over else f"{close[0][0]} is close to its budget"
    else:
        title = f"{len(parts)} budgets need a look"
    caption = " · ".join(parts[:WARNING_LIMIT]) + \
              (f" · and {len(parts) - WARNING_LIMIT} more on the Budgets tab" if len(parts) > WARNING_LIMIT else "")
    return {"icon": "alert", "colour": "bad" if over else "warn", "title": title, "caption": caption}

# ----- Words for the Summary tab: the headline, month names and the insight cards -----
def month_name(month):
    # "2026-09" -> "25 Sep – 26 Oct 2026"
    return payday.name(month)

def previous_month(month):
    year, number = map(int, month.split("-"))
    return f"{year - 1}-12" if number == 1 else f"{year}-{number - 1:02d}"

def headline(transactions, memory, month=None):
    # ("£1,028 spent 25 Sep – 26 Oct 2026", "98 payments · 10 categories")
    totals = by_category(transactions, memory, month)
    payments = sum(t.amount < 0 for t, _ in spending(transactions, memory, month))
    where = month_name(month) if month else "across all pay months"
    return (f"£{sum(totals.values()):,.0f} spent {where}",
            f"{payments} payment{'' if payments == 1 else 's'} · "
            f"{len(totals)} categor{'y' if len(totals) == 1 else 'ies'}")

NOTHING_SORTED_CARD = {"icon": "dot", "colour": "neutral", "title": "Nothing sorted yet",
                       "caption": "Your shops haven't been put into categories yet. Wait for sorting to "
                                  "finish, or click Sort shops."}
NO_SPENDING_CARD = {"icon": "dot", "colour": "neutral", "title": "No spending to show yet",
                    "caption": "Nothing was spent in this pay month, or it was all money coming in."}

def insights(transactions, memory, month=None):
    # Up to three short facts for the cards. Each is a dict: icon, colour key (a category or
    # "good"/"bad"/"neutral"), title and caption. A month with nothing to show gets one friendly card.
    if not transactions:
        return []
    totals = by_category(transactions, memory, month)
    if not totals:
        return [NO_SPENDING_CARD]
    if nothing_sorted(totals):
        return [NOTHING_SORTED_CARD]
    total = sum(totals.values())
    if month is None:
        cards = []
        per_month = {m: v for m, v in by_month(transactions, memory).items() if v > 0}
        if per_month:
            biggest = max(per_month, key=per_month.get)
            cards += [
                {"icon": "average", "colour": "neutral", "title": f"£{total / len(per_month):,.0f} a month",
                 "caption": f"Average over {len(per_month)} pay months"},
                {"icon": "day", "colour": "neutral", "title": f"Biggest month: {payday.short_name(biggest)}",
                 "caption": f"£{per_month[biggest]:,.0f} spent, {month_name(biggest)}"}]
        shops = top_merchants(transactions, memory, count=1)
        if shops and shops[0][1] > 0:
            shop, shop_total, visits = shops[0]
            cards.append({"icon": "shop", "colour": "neutral", "title": f"Top shop: {shop.title()}",
                          "caption": f"£{shop_total:,.0f} over {visits} payments"})
        return cards
    cards = []
    compared = compare(transactions, memory, month)
    if compared:
        change, before = compared["change"], compared["before"]
        if abs(change) < 1:
            cards.append({"icon": "dot", "colour": "neutral", "title": "Same as last month",
                          "caption": f"Less than £1 difference from {month_name(before)}"})
        else:
            cards.append({"icon": "up" if change > 0 else "down", "colour": "bad" if change > 0 else "good",
                          "title": f"£{abs(change):,.0f} {'more' if change > 0 else 'less'} than last month",
                          "caption": f"{compared['share']:.0%} {'up' if change > 0 else 'down'} "
                                     f"on {month_name(before)}"})
    else:
        cards.append({"icon": "dot", "colour": "neutral", "title": "Nothing to compare yet",
                      "caption": "Last pay month's statements aren't all loaded"})
    category, amount = next(iter(totals.items()))
    cards.append({"icon": "dot", "colour": category, "title": f"Biggest: {category}",
                  "caption": f"£{amount:,.0f} · {amount / total:.0%} of your spending"})
    days = by_day(transactions, memory, month)
    if days:   # empty if every day's refunds outweighed its spending
        day = max(days, key=days.get)
        cards.append({"icon": "day", "colour": "neutral", "title": f"Biggest day: {day:%a} {day.day} {day:%b}",
                      "caption": f"£{days[day]:,.2f} spent"})
    return cards
