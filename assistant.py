# The AI money assistant and the monthly rundown. The app works out every number itself
# (using summary.py) and hands the AI a list of facts; the AI only puts them into friendly words.
# Chats are never saved. Rundowns are saved in data/rundowns/, which Git ignores.
import os
import re
from datetime import date
import ollama
import app_logic
import payday
import storage
import summary
from categorise import MODEL

RUNDOWN_DAYS = 3        # the rundown is made in the 3 days before payday
HISTORY = 10            # how many earlier chat messages the AI is shown
DISCLAIMER = "A helper, not professional financial advice."
CHECK_NOTE = "This answer includes a number the app didn't work out. Double-check it."
OPTIONS = {"temperature": 0.3}   # lower = sticks closer to the facts

SYSTEM = """You are the money assistant inside the user's Spending Tracker app on their own computer.
Talk like a kind, honest and encouraging financial adviser: short answers in plain English
(2 to 5 sentences, or a few short bullet points). Be warm, never preachy, and be honest about slips.

Rules about numbers, which matter most:
- Only use numbers that appear in the FACTS below, copied exactly as written.
- Never do any maths yourself: no adding, subtracting, multiplying, dividing, averaging or estimating.
- If a question needs a number that isn't in the FACTS, say the app hasn't worked that out, and point
  the user to the Summary, Budgets or Transactions tab instead.
- Each category is separate: never say one category includes another.

You are a helper, not a professional financial adviser. For big decisions (debt, loans, investments,
pensions) suggest a qualified adviser or the free UK service MoneyHelper.
Don't use headings, bold text or tables.

Today is {today}.

FACTS:
{facts}"""

RUNDOWN_REQUEST = """Using only the FACTS, write a short end-of-month summary in exactly this shape:
Wins:
- (one or two things that went well)
Slips:
- (one or two things that didn't go so well, said kindly)
Tips:
- (one or two practical tips for next month)
Each bullet is one short sentence. If there are no slips, say so kindly."""

def gbp(amount):
    return f"£{amount:,.2f}"

def clean_markdown(text):
    # The chat can't show bold, so strip the markdown symbols instead (the same as FPL Bot)
    text = re.sub(r"^[ \t]*([*_-])([ \t]*\1){2,}[ \t]*$", "", text, flags=re.MULTILINE)  # --- rules
    text = re.sub(r"^[ \t]*#{1,6}[ \t]*", "", text, flags=re.MULTILINE)                  # # headings
    text = re.sub(r"^([ \t]*)[*+-][ \t]+", r"\1• ", text, flags=re.MULTILINE)             # bullets
    text = re.sub(r"`([^`\n]+)`", r"\1", text)                                           # `code`
    text = re.sub(r"(\*{1,3}|_{2,3})(?=\S)(.+?)(?<=\S)\1", r"\2", text)                  # *, **, __
    return text.replace("*", "")

# ----- The facts: every number the AI is allowed to use -----
def rundown_sections(transactions, memory, budgets, month):
    # The rundown for one pay month as [(heading, [lines])]. Also the main facts for the chat.
    totals = summary.by_category(transactions, memory, month)
    spent = round(sum(totals.values()), 2)
    payments = sum(t.amount < 0 for t, _ in summary.spending(transactions, memory, month))
    sections = [("Totals", [f"Spent: {gbp(spent)} over {payments} payments",
                            f"Money in: {gbp(summary.money_in(transactions, memory, month))}"])]
    top = [f"{c}: {gbp(v)} ({v / spent:.0%} of spending)" for c, v in list(totals.items())[:3]]
    sections.append(("Top categories", top or ["No spending yet"]))
    rows = summary.budget_status(totals, budgets)
    if rows:
        kept = [f"{c} ({gbp(left)} left of {gbp(budget)})" for c, budget, _, left, state in rows if state != "over"]
        broken = [f"{c} ({gbp(-left)} over {gbp(budget)})" for c, budget, _, left, state in rows if state == "over"]
        sections.append(("Budgets", [f"Kept: {', '.join(kept) or 'none'}", f"Broken: {', '.join(broken) or 'none'}"]))
    else:
        sections.append(("Budgets", ["No budgets set yet"]))
    compared = summary.compare(transactions, memory, month)
    heading = "Compared with last month"
    if compared:
        heading += f" ({summary.month_name(compared['before'])})"
        change = compared["change"]
        lines = [f"Last month: {gbp(compared['last_total'])} spent",
                 "About the same as last month" if abs(change) < 1 else
                 f"{gbp(abs(change))} {'more' if change > 0 else 'less'} than last month "
                 f"({compared['share']:.0%} {'up' if change > 0 else 'down'})"]
        if compared["rises"]:
            lines.append("Went up most: " + ", ".join(f"{c} (up {gbp(d)})" for c, d in compared["rises"]))
        if compared["drops"]:
            lines.append("Went down most: " + ", ".join(f"{c} (down {gbp(-d)})" for c, d in compared["drops"]))
        sections.append((heading, lines))
    else:
        sections.append((heading, ["Nothing to compare: last pay month's statements aren't all loaded"]))
    return sections

def chat_facts(transactions, memory, budgets, month, today):
    # Everything the assistant may talk about, as plain text
    if not transactions:
        return "No statements are loaded yet, so there are no numbers."
    sections = [(f"This pay month: {summary.month_name(month)}", [])]
    sections += rundown_sections(transactions, memory, budgets, month)
    totals = summary.by_category(transactions, memory, month)
    sections.append(("Every category this pay month (categories with no spending: £0.00)",
                     [f"{c}: {gbp(v)}" for c, v in totals.items()]))
    shops = summary.top_merchants(transactions, memory, month, count=3)
    if shops:
        sections.append(("Top shops this pay month",
                         [f"{key.title()}: {gbp(total)} over {visits} payments" for key, total, visits in shops]))
    per_month = summary.by_month(transactions, memory)
    spending_months = [v for v in per_month.values() if v > 0]
    lines = [f"{summary.month_name(m)}: {gbp(v)}" for m, v in per_month.items()]
    if spending_months:
        lines.append(f"Average per pay month: {gbp(round(sum(spending_months) / len(spending_months), 2))}")
    sections.append(("Every loaded pay month", lines))
    next_pay = payday.next_payday(today)
    days = (next_pay - today).days
    sections.append(("Payday", [f"Next payday: {next_pay:%a} {next_pay.day} {next_pay:%b %Y} "
                                f"({'today' if days == 0 else f'{days} days away'})"]))
    return as_text(sections)

def as_text(sections):
    return "\n\n".join(heading + ("\n" if lines else "") + "\n".join(f"- {line}" for line in lines)
                       for heading, lines in sections)

# ----- Checking the AI didn't make up a number -----
NUMBERS = re.compile(r"£\s?(\d[\d,]*(?:\.\d+)?)|(\d+(?:\.\d+)?)\s?%")

def numbers_in(text):
    # {("£", 12.5), ("%", 27.0), ...} for every £ amount and percentage in the text
    found = set()
    for pounds, percent in NUMBERS.findall(text):
        found.add(("£", float(pounds.replace(",", ""))) if pounds else ("%", float(percent)))
    return found

def made_up_numbers(reply, facts, question=""):
    # £ amounts and percentages in the reply that aren't in the facts (or the question).
    # Rounding a fact to whole pounds, e.g. £292.36 as £292, is fine.
    allowed = numbers_in(facts + "\n" + question)
    allowed |= {(kind, float(round(value))) for kind, value in allowed} | {("£", 0.0), ("%", 0.0)}
    return sorted(f"£{v:,.2f}".replace(".00", "") if kind == "£" else f"{v:g}%"
                  for kind, v in numbers_in(reply) - allowed)

# ----- Talking to the local AI -----
def problem():
    # None if the assistant can work, otherwise a friendly message
    issue = app_logic.ai_problem()
    if issue and issue.startswith("Can't reach"):
        return ("I can't reach Ollama at the moment, so I can't answer just yet. Open Ollama from the "
                "Start menu, wait a few seconds, then ask me again.")
    if issue:
        return f"I'm not quite ready: the {MODEL} model isn't installed. Ask for help running: ollama pull {MODEL}"
    return None

def system_message(facts, today):
    return {"role": "system", "content": SYSTEM.format(today=f"{today:%A} {today.day} {today:%B %Y}", facts=facts)}

def stream_reply(question, history, facts, today):
    # Yields the reply a few words at a time. history: earlier [{"role", "content"}] messages
    messages = [system_message(facts, today), *history[-HISTORY:], {"role": "user", "content": question}]
    for chunk in ollama.chat(model=MODEL, messages=messages, stream=True, options=OPTIONS):
        yield chunk["message"]["content"]

def ai_rundown(facts, today):
    # The wins, slips and tips part of a rundown: (text, made-up numbers)
    messages = [system_message(facts, today), {"role": "user", "content": RUNDOWN_REQUEST}]
    text = clean_markdown(ollama.chat(model=MODEL, messages=messages, options=OPTIONS)["message"]["content"]).strip()
    return text, made_up_numbers(text, facts)

# ----- Rundowns: made, saved and read back -----
def rundown_file(month):
    return os.path.join(storage.RUNDOWNS_DIR, f"{month}.json")

def make_rundown(transactions, memory, budgets, month, today):
    return {"month": month, "made": today.isoformat(),
            "latest_payment": max(t.date for t in transactions).isoformat(),
            "sections": rundown_sections(transactions, memory, budgets, month), "ai": None, "ai_note": None}

def save_rundown(rundown):
    storage.save_json(rundown_file(rundown["month"]), rundown)

def load_rundown(month):
    return storage.load_json(rundown_file(month), None)

def saved_rundowns():
    # Pay months with a saved rundown, newest first
    if not os.path.isdir(storage.RUNDOWNS_DIR):
        return []
    return sorted((n[:-5] for n in os.listdir(storage.RUNDOWNS_DIR) if re.fullmatch(r"\d{4}-\d{2}\.json", n)),
                  reverse=True)

def rundown_due(transactions, today):
    # The pay month to make a rundown for now, or None. In the 3 days before payday, a rundown is made
    # once, and made again whenever a statement with newer payments than the last rundown is loaded.
    if not transactions or not 0 < (payday.next_payday(today) - today).days <= RUNDOWN_DAYS:
        return None
    month = payday.pay_month_of(today)
    if not any(summary.month_of(t) == month for t in transactions):
        return None
    last = load_rundown(month)
    newest = max(t.date for t in transactions)
    return month if last is None or newest > date.fromisoformat(last["latest_payment"]) else None

def rundown_text(rundown):
    made = date.fromisoformat(rundown["made"])
    latest = date.fromisoformat(rundown["latest_payment"])
    text = (f"Rundown for {summary.month_name(rundown['month'])}\n"
            f"Made on {made:%a} {made.day} {made:%b %Y}, with payments up to {latest.day} {latest:%b}.\n\n")
    text += as_text(rundown["sections"]).replace("\n- ", "\n• ")
    if rundown["ai"]:
        text += f"\n\nFrom your assistant ({DISCLAIMER[0].lower() + DISCLAIMER[1:-1]})\n{rundown['ai']}"
    if rundown["ai_note"]:
        text += f"\n\n{rundown['ai_note']}"
    return text
