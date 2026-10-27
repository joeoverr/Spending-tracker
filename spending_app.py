# The desktop window. It only shows things and reacts to clicks: reading statements,
# sorting shops and adding up totals are done by the other files, which this one calls.
# Run it with:  py spending_app.py
import os
import threading
from datetime import date
from tkinter import ttk, filedialog
import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import ImageTk
import app_logic
import assistant
import banks
import categorise
import charts
import icons
import payday
import storage
import summary
from banks import general_csv
from theme import (BG, PANEL, BORDER, BUTTON, HOVER, STRIPE, TEXT, MUTED, ACCENT, ACCENT_HOVER, ON_ACCENT,
                   GOOD, WARN, BAD, FONT, HEADLINE_FONT, TITLE_FONT, INSIGHT_FONT, HEADING_FONT, BODY_FONT, BOLD_FONT,
                   SMALL_FONT, WINDOW_SIZE, PAD, GAP, CORNER, BORDER_WIDTH, BUTTON_HEIGHT, BUTTON_CORNER,
                   ROW_HEIGHT, DOT_SIZE, ICON_SIZE, MONTH_MENU_WIDTH, BUDGET_BAR_HEIGHT, BUDGET_BOX_WIDTH,
                   BUDGET_NAME_WIDTH, BUDGET_WORDS_WIDTH, YOUR_BUBBLE, YOUR_BUBBLE_TEXT, AI_BUBBLE, AI_BUBBLE_TEXT,
                   BUBBLE_WRAP, BUBBLE_PAD, colour_for)

ALL_MONTHS = "All months"
CHARTS = ["Bars", "Donut", "Calendar"]
CARD_COLOURS = {"good": GOOD, "bad": BAD, "warn": WARN, "neutral": ACCENT}   # any other card colour is a category's
BUDGET_COLOURS = {"ok": GOOD, "close": WARN, "over": BAD}

def card(parent, **options):
    # A white panel with rounded corners and a thin grey border
    return ctk.CTkFrame(parent, fg_color=PANEL, corner_radius=CORNER, border_width=BORDER_WIDTH,
                        border_color=BORDER, **options)

def button(parent, text, command, width=140, main=False):
    # main=True makes the bright accent-coloured button; the rest are soft grey
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=BUTTON_HEIGHT,
                         corner_radius=BUTTON_CORNER, font=BOLD_FONT,
                         fg_color=ACCENT if main else BUTTON, hover_color=ACCENT_HOVER if main else HOVER,
                         text_color=ON_ACCENT if main else TEXT, text_color_disabled=MUTED)

def menu(parent, values, command=None, width=170):
    return ctk.CTkOptionMenu(parent, values=values, command=command, width=width, height=BUTTON_HEIGHT,
                             corner_radius=BUTTON_CORNER, fg_color=BUTTON, button_color=BUTTON,
                             button_hover_color=HOVER, text_color=TEXT, font=BODY_FONT,
                             dropdown_font=BODY_FONT, dropdown_fg_color=PANEL, dropdown_hover_color=HOVER,
                             dropdown_text_color=TEXT)

def switch(parent, values, command):
    # A row of options where the chosen one shows as a white "pill", like a phone app
    return ctk.CTkSegmentedButton(parent, values=values, command=command, height=BUTTON_HEIGHT - 4,
                                  corner_radius=BUTTON_CORNER, font=BOLD_FONT, fg_color=BUTTON,
                                  selected_color=PANEL, selected_hover_color=PANEL,
                                  unselected_color=BUTTON, unselected_hover_color=HOVER, text_color=TEXT)

def label(parent, text, font=BODY_FONT, colour=TEXT, **options):
    return ctk.CTkLabel(parent, text=text, font=font, text_color=colour, **options)

def ctk_icon(image):
    # Turns a drawn icon into one CustomTkinter can show (it sharpens it on high-resolution screens)
    return ctk.CTkImage(light_image=image, size=image.size)

def insight_card(parent, insight):
    # A white card with a round icon, a bold line and a smaller grey line under it
    colour = CARD_COLOURS.get(insight["colour"]) or colour_for(insight["colour"])
    box = card(parent)
    label(box, "", image=ctk_icon(icons.badge(insight["icon"], colour, ICON_SIZE))).pack(
        side="left", padx=(PAD - 4, GAP), pady=PAD - 6)
    words = ctk.CTkFrame(box, fg_color="transparent")
    words.pack(side="left", fill="x", expand=True, padx=(0, GAP), pady=PAD - 6)
    label(words, insight["title"], INSIGHT_FONT, anchor="w").pack(fill="x")
    label(words, insight["caption"], SMALL_FONT, MUTED, anchor="w").pack(fill="x")
    return box

def banner(parent, insight, action=None):
    # A slimmer, one-line card for notices (the payday reminder and the budget warning).
    # action: an optional (button text, what it does) shown on the right
    colour = CARD_COLOURS.get(insight["colour"]) or colour_for(insight["colour"])
    box = card(parent)
    label(box, "", image=ctk_icon(icons.badge(insight["icon"], colour, ICON_SIZE))).pack(
        side="left", padx=(PAD - 4, GAP), pady=GAP - 2)
    label(box, insight["title"], BOLD_FONT).pack(side="left", padx=(0, GAP))
    if action:
        button(box, action[0], action[1], width=90).pack(side="right", padx=(0, GAP + 2))
    label(box, insight["caption"], SMALL_FONT, MUTED, anchor="w").pack(side="left", fill="x", expand=True, padx=(0, GAP))
    return box

class SpendingApp(ctk.CTk):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.title("Spending Tracker")
        self.geometry(WINDOW_SIZE)
        self.today = date.today()
        self.transactions = []
        self.memory = categorise.load_memory()
        self.csv_formats = app_logic.load_csv_formats()
        self.budgets = app_logic.load_budgets()
        self.settings = app_logic.load_settings()
        self.seen_files = set()   # statements already read this session, so they're never read twice
        self.sorting = False
        self.loading = False
        self.load_message = None
        self.asking = False         # the assistant is answering
        self.writing_rundown = False   # the assistant is writing a rundown's wins, slips and tips
        self.chat_history = []      # this session's chat, forgotten when the app closes
        self.failed_shops = set()   # shops the AI couldn't sort this session
        self.sort_banner = None     # the "sorting..." or "couldn't sort" banner, when it's showing
        self.chart = None
        self.chart_size = None
        self.table_dots = {}   # the table's dot pictures, kept here so Tk doesn't throw them away
        self.month_keys = {ALL_MONTHS: None}   # "25 Sep – 26 Oct 2026" -> "2026-09"
        self.build_top_bar()
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=PAD, pady=(0, GAP))
        self.check_button = button(status_row, "Check for new statements", self.check_for_new_statements, width=200)
        self.check_button.pack(side="right")
        self.status = label(status_row, "Click Open statement to start.", SMALL_FONT, MUTED, anchor="w")
        self.status.pack(side="left", fill="x", expand=True, padx=(6, GAP))
        self.notice = None   # the payday reminder card, when it's showing
        self.tabs = ctk.CTkTabview(self, fg_color=PANEL, corner_radius=CORNER, border_width=BORDER_WIDTH,
                                   border_color=BORDER, segmented_button_fg_color=BUTTON,
                                   segmented_button_selected_color=PANEL, segmented_button_selected_hover_color=PANEL,
                                   segmented_button_unselected_color=BUTTON,
                                   segmented_button_unselected_hover_color=HOVER, segmented_button_font=BOLD_FONT,
                                   text_color=TEXT)
        self.tabs.pack(fill="both", expand=True, padx=PAD, pady=(0, PAD))
        self.build_table(self.tabs.add("Transactions"))
        self.build_summary(self.tabs.add("Summary"))
        self.build_budgets(self.tabs.add("Budgets"))
        self.build_assistant(self.tabs.add("Assistant"))
        self.refresh()
        self.after(300, self.check_for_new_statements)   # load the statements folder on startup

    # ----- Building the window -----
    def build_top_bar(self):
        bar = card(self)
        bar.pack(fill="x", padx=PAD, pady=(PAD, GAP))
        label(bar, "Spending Tracker", TITLE_FONT).pack(side="left", padx=PAD, pady=14)
        self.sort_button = button(bar, "Sort shops", lambda: self.start_sorting(retry=True), width=110)
        self.sort_button.pack(side="right", padx=(6, PAD))
        self.month_menu = menu(bar, [ALL_MONTHS], command=lambda _: self.refresh(), width=MONTH_MENU_WIDTH)
        self.month_menu.pack(side="right", padx=6)
        button(bar, "Open statement", self.open_statement, main=True).pack(side="right", padx=6)
        self.bank_menu = menu(bar, app_logic.bank_choices())
        self.bank_menu.pack(side="right", padx=6)
        label(bar, "Bank", colour=MUTED).pack(side="right", padx=(0, 2))

    def build_table(self, tab):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT,
                        rowheight=ROW_HEIGHT, font=SMALL_FONT, borderwidth=0,
                        bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure("Treeview.Heading", background=PANEL, foreground=MUTED, font=(FONT, 12, "bold"),
                        borderwidth=0, relief="flat", padding=(4, 6), bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", ON_ACCENT)])
        style.map("Treeview.Heading", background=[("active", BUTTON)])
        # The first column ("#0") can show a picture, so it holds the category dot and the description
        columns = {"category": ("Category", 150), "date": ("Date", 120), "bank": ("Bank", 130), "amount": ("Amount", 120)}
        self.table = ttk.Treeview(tab, columns=list(columns), show="tree headings")
        self.table.heading("#0", text="Description", anchor="w")
        self.table.column("#0", width=400, stretch=True)
        for key, (title, width) in columns.items():
            self.table.heading(key, text=title, anchor="e" if key == "amount" else "w")
            self.table.column(key, width=width, anchor="e" if key == "amount" else "w", stretch=False)
        self.table.tag_configure("stripe", background=STRIPE)
        self.table.tag_configure("money_in", foreground=GOOD)
        scroll = ctk.CTkScrollbar(tab, command=self.table.yview, fg_color=PANEL, button_color=BUTTON,
                                  button_hover_color=HOVER)
        self.table.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.table.pack(fill="both", expand=True, padx=(GAP, 0), pady=(0, GAP))

    def build_summary(self, tab):
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=GAP)
        self.headline = label(top, "", HEADLINE_FONT, anchor="w")
        self.headline.pack(fill="x")
        self.subline = label(top, "", BODY_FONT, MUTED, anchor="w")
        self.subline.pack(fill="x")
        self.warning_row = ctk.CTkFrame(tab, fg_color="transparent", height=0)   # the budget warning card
        self.warning_row.pack(fill="x", padx=GAP)
        self.cards_row = ctk.CTkFrame(tab, fg_color="transparent")
        self.cards_row.pack(fill="x", padx=GAP, pady=(GAP + 4, GAP + 4))
        for column in range(3):
            self.cards_row.grid_columnconfigure(column, weight=1, uniform="cards")
        body = ctk.CTkFrame(tab, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self.totals_frame = ctk.CTkScrollableFrame(body, fg_color=BG, corner_radius=CORNER, width=270,
                                                   scrollbar_button_color=BUTTON)
        self.totals_frame.pack(side="left", fill="y", padx=(GAP, PAD), pady=(0, GAP))
        right = ctk.CTkFrame(body, fg_color=PANEL)
        right.pack(side="left", fill="both", expand=True, pady=(0, GAP))
        self.chart_switch = switch(right, CHARTS, lambda _: self.refresh())
        self.chart_switch.set(CHARTS[0])
        self.chart_switch.pack(anchor="e", padx=GAP)
        self.chart_frame = ctk.CTkFrame(right, fg_color=PANEL)
        self.chart_frame.pack(fill="both", expand=True, pady=(GAP, 0))
        self.chart_frame.pack_propagate(False)   # the chart fits the space, not the other way round
        self.chart_frame.bind("<Configure>", self.chart_resized)

    def build_budgets(self, tab):
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=GAP, pady=(0, GAP))
        button(top, "Save", self.save_budgets, width=100, main=True).pack(side="right")
        button(top, "Suggest from past spending", self.suggest_budgets, width=220).pack(side="right", padx=GAP)
        words = ctk.CTkFrame(top, fg_color="transparent")
        words.pack(side="left", fill="x", expand=True)
        label(words, "Monthly budgets", HEADING_FONT, anchor="w").pack(fill="x")
        self.budget_month_label = label(words, "", SMALL_FONT, MUTED, anchor="w")
        self.budget_month_label.pack(fill="x")
        rows = ctk.CTkScrollableFrame(tab, fg_color=PANEL, scrollbar_button_color=BUTTON)
        rows.pack(fill="both", expand=True, padx=GAP, pady=(0, GAP))
        rows.grid_columnconfigure(2, weight=1)
        self.budget_boxes, self.budget_bars = {}, {}
        for row, category in enumerate(summary.BUDGET_CATEGORIES):
            label(rows, f"  {category}", image=ctk_icon(icons.dot(colour_for(category), DOT_SIZE)), compound="left",
                  anchor="w", width=BUDGET_NAME_WIDTH).grid(row=row, column=0, sticky="w", padx=(GAP, 0), pady=6)
            box = ctk.CTkEntry(rows, width=BUDGET_BOX_WIDTH, height=BUTTON_HEIGHT - 4, corner_radius=BUTTON_CORNER,
                               fg_color=PANEL, border_color=BORDER, text_color=TEXT, font=BODY_FONT,
                               placeholder_text="£ no budget", placeholder_text_color=MUTED)
            box.grid(row=row, column=1, padx=GAP, pady=6)
            self.budget_boxes[category] = box
            bar = ctk.CTkProgressBar(rows, height=BUDGET_BAR_HEIGHT, corner_radius=BUDGET_BAR_HEIGHT // 2,
                                     fg_color=BUTTON, progress_color=GOOD)
            bar.grid(row=row, column=2, sticky="ew", padx=GAP, pady=6)
            words = label(rows, "", SMALL_FONT, MUTED, anchor="e", width=BUDGET_WORDS_WIDTH)
            words.grid(row=row, column=3, sticky="e", padx=(GAP, PAD), pady=6)
            self.budget_bars[category] = (bar, words)
        self.fill_budget_boxes(self.budgets)

    def build_assistant(self, tab):
        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.pack(fill="x", padx=GAP, pady=(0, GAP))
        self.assistant_switch = ctk.CTkSwitch(top, text="Assistant", command=self.toggle_assistant, font=BOLD_FONT,
                                              text_color=TEXT, fg_color=BORDER, progress_color=ACCENT,
                                              button_color=PANEL, button_hover_color=BUTTON)
        if self.settings.get("assistant_on"):
            self.assistant_switch.select()
        self.assistant_switch.pack(side="left")
        label(top, assistant.DISCLAIMER, SMALL_FONT, MUTED).pack(side="left", padx=PAD)
        self.assistant_view = switch(top, ["Chat", "Rundowns"], lambda _: self.show_assistant_page())
        self.assistant_view.set("Chat")
        self.assistant_view.pack(side="right")
        # The chat page
        self.chat_page = ctk.CTkFrame(tab, fg_color="transparent")
        self.chat_log = ctk.CTkScrollableFrame(self.chat_page, fg_color=PANEL, scrollbar_button_color=BUTTON)
        self.chat_log.pack(fill="both", expand=True, padx=GAP)
        ask_row = ctk.CTkFrame(self.chat_page, fg_color="transparent")
        ask_row.pack(fill="x", padx=GAP, pady=GAP)
        self.send_button = button(ask_row, "Send", self.ask, width=100, main=True)
        self.send_button.pack(side="right")
        self.question = ctk.CTkEntry(ask_row, height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER, fg_color=PANEL,
                                     border_color=BORDER, text_color=TEXT, font=BODY_FONT, placeholder_text_color=MUTED,
                                     placeholder_text="Ask about your spending, e.g. How am I doing on my budgets?")
        self.question.pack(side="left", fill="x", expand=True, padx=(0, GAP))
        self.question.bind("<Return>", lambda _: self.ask())
        # The rundowns page
        self.rundown_page = ctk.CTkFrame(tab, fg_color="transparent")
        row = ctk.CTkFrame(self.rundown_page, fg_color="transparent")
        row.pack(fill="x", padx=GAP, pady=(0, GAP))
        self.rundown_keys = {}
        self.rundown_menu = menu(row, ["No rundowns yet"], command=lambda _: self.show_rundowns(), width=MONTH_MENU_WIDTH)
        self.rundown_menu.pack(side="left")
        button(row, "Make rundown now", self.make_rundown_now, width=170).pack(side="right")
        self.rundown_box = ctk.CTkTextbox(self.rundown_page, fg_color=BG, corner_radius=CORNER, text_color=TEXT,
                                          font=BODY_FONT, wrap="word", border_spacing=PAD)
        self.rundown_box.pack(fill="both", expand=True, padx=GAP, pady=(0, GAP))
        inner = self.rundown_box._textbox   # CustomTkinter doesn't allow fonts on tags, so set them on the Tk box
        inner.tag_configure("title", font=ctk.CTkFont(*HEADING_FONT[:2], weight="bold"))
        inner.tag_configure("heading", font=ctk.CTkFont(*BOLD_FONT[:2], weight="bold"), spacing1=4)
        inner.tag_configure("muted", foreground=MUTED)
        inner.tag_configure("note", foreground=WARN)
        self.show_assistant_page()
        self.toggle_assistant(save=False)
        self.show_rundowns()

    def show_assistant_page(self):
        chat = self.assistant_view.get() == "Chat"
        (self.rundown_page if chat else self.chat_page).pack_forget()
        (self.chat_page if chat else self.rundown_page).pack(fill="both", expand=True)

    # ----- The assistant's chat -----
    def assistant_on(self):
        return bool(self.assistant_switch.get())

    def toggle_assistant(self, save=True):
        on = self.assistant_on()
        if save:
            self.settings["assistant_on"] = on
            app_logic.save_setting("assistant_on", on)
        self.question.configure(state="normal" if on else "disabled")
        self.send_button.configure(state="normal" if on and not self.asking else "disabled")
        if on:
            self.bubble("Hi! I'm your money assistant. Ask me anything about your spending, like \"How am I doing "
                        "on my budgets?\" I only use numbers the app has worked out, and I'm "
                        f"{assistant.DISCLAIMER[0].lower() + assistant.DISCLAIMER[1:]}", mine=False)
        else:
            self.bubble("The assistant is off. Turn it on with the switch above to ask questions about your "
                        "spending. Everything stays on your computer.", mine=False)

    def bubble(self, text, mine):
        # Adds a chat bubble (yours on the right in blue, the assistant's on the left in grey) and returns
        # its label, so a reply can be filled in as it arrives
        holder = ctk.CTkFrame(self.chat_log, fg_color=YOUR_BUBBLE if mine else AI_BUBBLE, corner_radius=CORNER)
        holder.pack(anchor="e" if mine else "w", padx=GAP, pady=(GAP, 0))
        words = label(holder, text, BODY_FONT, YOUR_BUBBLE_TEXT if mine else AI_BUBBLE_TEXT,
                      wraplength=BUBBLE_WRAP, justify="left")
        words.pack(padx=BUBBLE_PAD, pady=BUBBLE_PAD - 4)
        self.scroll_chat()
        return words

    def scroll_chat(self):
        self.chat_log.update_idletasks()
        self.chat_log._parent_canvas.yview_moveto(1.0)

    def ask(self):
        question = self.question.get().strip()
        if not question or self.asking or not self.assistant_on():
            return
        self.question.delete(0, "end")
        self.bubble(question, mine=True)
        reply = self.bubble("Thinking...", mine=False)
        self.asking = True
        self.send_button.configure(state="disabled")
        # The app works out the numbers now; the AI only gets to put them into words
        facts = assistant.chat_facts(self.transactions, self.memory, self.budgets, self.budget_month(), self.today)
        history, today = list(self.chat_history), self.today

        def work():
            issue = assistant.problem()
            text = ""
            if not issue:
                try:
                    for piece in assistant.stream_reply(question, history, facts, today):
                        text += piece
                        self.after(0, lambda shown=text: (reply.configure(text=assistant.clean_markdown(shown)),
                                                          self.scroll_chat()))
                except Exception:
                    issue = "Sorry, I stopped part-way. Check Ollama is running, then ask me again."
            self.after(0, self.finish_answer, question, issue or text, reply, facts, bool(issue))
        threading.Thread(target=work, daemon=True).start()

    def finish_answer(self, question, text, reply, facts, failed):
        self.asking = False
        self.send_button.configure(state="normal" if self.assistant_on() else "disabled")
        reply.configure(text=assistant.clean_markdown(text).strip())
        if not failed:
            self.chat_history += [{"role": "user", "content": question}, {"role": "assistant", "content": text}]
            if assistant.made_up_numbers(text, facts, question):
                label(self.chat_log, assistant.CHECK_NOTE, SMALL_FONT, WARN).pack(anchor="w", padx=GAP + BUBBLE_PAD)
        self.scroll_chat()

    # ----- Monthly rundowns -----
    def show_rundowns(self, month=None):
        months = assistant.saved_rundowns()
        self.rundown_keys = {summary.month_name(m): m for m in months}
        self.rundown_menu.configure(values=list(self.rundown_keys) or ["No rundowns yet"])
        if month:
            self.rundown_menu.set(summary.month_name(month))
        elif self.rundown_menu.get() not in self.rundown_keys:
            self.rundown_menu.set(next(iter(self.rundown_keys), "No rundowns yet"))
        chosen = self.rundown_keys.get(self.rundown_menu.get())
        rundown = assistant.load_rundown(chosen) if chosen else None
        text = assistant.rundown_text(rundown) if rundown else (
            "No rundowns yet. One is made by itself in the 3 days before payday, or click Make rundown now "
            "to make one for the pay month picked at the top.")
        self.rundown_box.configure(state="normal")
        self.rundown_box.delete("1.0", "end")
        note = rundown and rundown["ai_note"]
        for number, line in enumerate(text.split("\n")):
            # Bold title and headings, a grey "Made on" line, and any note from the assistant in amber
            style = ("title" if number == 0 else "muted" if number == 1 else "note" if line == note
                     else "heading" if rundown and line and not line.startswith("• ") else "")
            self.rundown_box.insert("end", line + "\n", style)
        self.rundown_box.configure(state="disabled")

    def make_rundown_now(self):
        month = self.budget_month()
        if not month:
            return self.say("Load a statement first, then make a rundown.", error=True)
        if self.writing_rundown:
            return self.say("The assistant is still writing the last rundown.")
        self.create_rundown(month)
        self.say(f"Made a rundown for {summary.month_name(month)}.")

    def create_rundown(self, month):
        # The app's numbers are saved straight away; if the assistant is on, it adds wins, slips and tips
        rundown = assistant.make_rundown(self.transactions, self.memory, self.budgets, month, self.today)
        if not self.assistant_on():
            rundown["ai_note"] = "Turn the assistant on to add wins, slips and tips to your rundowns."
            assistant.save_rundown(rundown)
            return self.show_rundowns(month)
        rundown["ai_note"] = "Your assistant is writing a summary of wins, slips and tips..."
        assistant.save_rundown(rundown)
        self.show_rundowns(month)
        self.writing_rundown = True
        facts = f"Pay month: {summary.month_name(month)}\n\n" + assistant.as_text(rundown["sections"])
        today = self.today

        def work():
            issue = assistant.problem()
            text, made_up = "", []
            if not issue:
                try:
                    text, made_up = assistant.ai_rundown(facts, today)
                except Exception:
                    issue = True
            self.after(0, self.finish_rundown, rundown, text, made_up, issue)
        threading.Thread(target=work, daemon=True).start()

    def finish_rundown(self, rundown, text, made_up, issue):
        self.writing_rundown = False
        if issue:
            rundown["ai_note"] = ("Your assistant couldn't be reached, so there's no summary from it this time. "
                                  "Start Ollama, then click Make rundown now.")
        else:
            rundown["ai"], rundown["ai_note"] = text, assistant.CHECK_NOTE if made_up else None
        assistant.save_rundown(rundown)
        self.show_rundowns(rundown["month"])

    # ----- Budgets -----
    def fill_budget_boxes(self, amounts):
        for category, box in self.budget_boxes.items():
            box.delete(0, "end")
            if amounts.get(category):
                box.insert(0, f"{amounts[category]:g}")

    def save_budgets(self):
        budgets, problems = app_logic.read_budget_boxes({c: box.get() for c, box in self.budget_boxes.items()})
        if problems:
            return self.say("Not saved. " + "; ".join(problems) + ".", error=True)
        self.budgets = budgets
        app_logic.save_budgets(budgets)
        self.fill_budget_boxes(budgets)
        self.say(f"Saved {len(budgets)} budget{'' if len(budgets) == 1 else 's'}.")
        self.refresh()

    def suggest_budgets(self):
        suggestions, used = summary.suggest_budgets(self.transactions, self.memory)
        if not used:
            return self.say("To suggest budgets, the app needs at least one whole pay month of statements.", error=True)
        self.fill_budget_boxes(suggestions)
        self.say(f"Suggested from your last {used} complete pay month{'' if used == 1 else 's'}. "
                 "Change any you like, then click Save to keep them.")

    def budget_month(self):
        # The pay month the budgets and assistant look at: the one picked at the top, or else
        # the one you're in today (or the latest loaded, if today's has no payments yet)
        months = summary.months(self.transactions)
        now = payday.pay_month_of(self.today)
        return self.chosen_month() or (now if now in months else months[-1] if months else None)

    def budget_rows(self, month):
        return summary.budget_status(summary.by_category(self.transactions, self.memory, month), self.budgets)

    def show_budgets(self):
        month = self.budget_month()
        self.budget_month_label.configure(
            text=f"Checked against {summary.month_name(month)}. Pick another pay month at the top to look back."
            if month else "Type a limit for any category you want to keep an eye on, then click Save.")
        spent = summary.by_category(self.transactions, self.memory, month) if month else {}
        states = {row[0]: row for row in self.budget_rows(month)} if month else {}
        for category, (bar, words) in self.budget_bars.items():
            if category in states:
                _, budget, used, left, state = states[category]
                bar.configure(progress_color=BUDGET_COLOURS[state])
                bar.set(min(used / budget, 1))
                words.configure(text_color=TEXT if state == "ok" else BUDGET_COLOURS[state],
                                text=f"£{used:,.2f} of £{budget:,.0f} · " +
                                     (f"£{-left:,.2f} over" if state == "over" else f"£{left:,.2f} left"))
            else:
                bar.configure(progress_color=BUTTON)
                bar.set(0)
                words.configure(text_color=MUTED, text=f"£{spent.get(category, 0):,.2f} spent · no budget")

    def show_budget_warning(self, month):
        for widget in self.warning_row.winfo_children():
            widget.destroy()
        month = month or self.budget_month()
        warning = summary.budget_warning(self.budget_rows(month)) if month else None
        if warning:
            if not self.chosen_month():   # "All months" is picked, so say which pay month this is about
                warning["title"] += f" ({payday.short_name(month)})"
            banner(self.warning_row, warning).pack(fill="x", pady=(GAP + 4, 0))
        self.warning_row.configure(height=1)   # shrink back to nothing when there's no card

    # ----- The payday reminder -----
    def show_reminder(self):
        due = payday.reminder_due(self.today)
        wanted = due is not None and self.settings.get("reminder_done") != due.isoformat()
        if self.notice and not wanted:
            self.notice.destroy()
            self.notice = None
        if wanted and not self.notice:
            self.notice = banner(self, {
                "icon": "download", "colour": "neutral", "title": "Download your latest statement.",
                "caption": f"Payday is {due:%a} {due.day} {due:%b}. Save it in the statements folder, "
                           "then click Check for new statements."}, action=("Got it", lambda: self.reminder_done(due)))
            self.notice.pack(fill="x", padx=PAD, pady=(0, GAP), before=self.tabs)

    def reminder_done(self, due):
        self.settings["reminder_done"] = due.isoformat()
        app_logic.save_setting("reminder_done", due.isoformat())
        self.show_reminder()

    # ----- Loading the statements folder, in the background -----
    def check_for_new_statements(self):
        if self.loading:
            return
        folder = storage.STATEMENTS_DIR
        names = app_logic.new_statements(folder, self.seen_files)
        if not names:
            if self.transactions or banks.statement_files(folder):
                return self.say("No new statements in the statements folder.")
            return self.say("No statements yet. Click Open statement, or save one in the statements folder.")
        self.loading = True
        self.check_button.configure(state="disabled", text="Reading...")
        self.say(f"Reading {len(names)} statement{'' if len(names) == 1 else 's'} from the statements folder...")
        csv_formats = dict(self.csv_formats)

        def work():
            try:
                found = banks.read_folder(folder, csv_formats, only=names)
            except Exception as error:   # e.g. a file was removed while it was being read
                found = ([], [], [("the statements folder", str(error))])
            self.after(0, self.finish_loading, folder, names, *found)
        threading.Thread(target=work, daemon=True).start()

    def finish_loading(self, folder, names, found, needs_setup, failed):
        self.loading = False
        self.check_button.configure(state="normal", text="Check for new statements")
        waiting = {os.path.basename(path) for path in needs_setup}   # asked about again next time
        self.seen_files.update(app_logic.file_stamp(folder, n) for n in names
                               if n not in waiting and os.path.exists(os.path.join(folder, n)))
        before = len(self.transactions)
        self.transactions = banks.merge(self.transactions, found)
        added = len(self.transactions) - before
        read = len(names) - len(needs_setup) - len(failed)
        message = f"Read {read} statement{'' if read == 1 else 's'}: {added} new payment{'' if added == 1 else 's'}."
        if failed:
            message += " Couldn't read: " + ", ".join(name for name, _ in failed) + "."
        if len(needs_setup) > 1:
            message += f" {len(needs_setup) - 1} more file(s) from a new bank will be asked about next time."
        self.say(message, error=bool(failed))
        self.refresh()
        self.load_message = message   # shown again after the AI has sorted any new shops
        self.start_sorting()
        if needs_setup:
            path = needs_setup[0]
            ColumnPicker(self, path, lambda chosen: self.open_path(path, chosen))

    # ----- Opening statements -----
    def open_statement(self):
        path = filedialog.askopenfilename(
            title="Pick a bank statement", initialdir=storage.STATEMENTS_DIR,
            filetypes=[("Bank statements", "*.pdf *.csv"), ("PDF statements", "*.pdf"), ("CSV files", "*.csv")])
        if path:
            self.open_path(path)

    def open_path(self, path, settings=None):
        if settings:
            app_logic.save_csv_format(path, settings, self.csv_formats)
        choice = self.bank_menu.get()
        try:
            new = app_logic.load_statement(path, choice, self.csv_formats)
        except Exception as error:
            return self.say(f"Couldn't read that file: {error}", error=True)
        if new is None:   # a CSV from a bank we don't know yet
            return ColumnPicker(self, path, lambda chosen: self.open_path(path, chosen))
        before = len(self.transactions)
        self.transactions = banks.merge(self.transactions, new)
        added = len(self.transactions) - before
        message = f"Added {added} payments from {new[0].bank}" + (" (the rest were already loaded)." if added < len(new) else ".")
        # Keep a copy in the statements folder so it loads by itself next time (copied, never moved)
        folder = storage.STATEMENTS_DIR
        try:
            copied = app_logic.keep_copy(path, folder)
        except OSError:
            copied = None
            message += " Couldn't save a copy in the statements folder."
        if copied or os.path.dirname(os.path.abspath(path)) == os.path.abspath(folder):
            self.seen_files.add(app_logic.file_stamp(folder, copied or os.path.basename(path)))
        if copied:
            message += " A copy is saved in the statements folder."
        self.say(message)
        self.refresh()
        self.start_sorting()

    # ----- Sorting shops with the AI, in the background so the window doesn't freeze -----
    def start_sorting(self, retry=False):
        # retry=True when you click Sort shops or Try again: shops that failed before are tried again.
        # Otherwise (after a statement loads) only shops that haven't failed this session start a sort,
        # so one shop the AI can't manage never makes it sort over and over.
        if self.sorting or not self.transactions:
            return
        if retry:
            self.failed_shops.clear()
        unknown = [key for key, _ in categorise.unknown_merchants(self.transactions, self.memory)
                   if key not in self.failed_shops]
        if not unknown:
            self.load_message = None
            return self.maybe_make_rundown()
        self.sorting = True
        self.sort_button.configure(state="disabled", text="Working...")
        self.say("Checking the AI is ready...")
        self.show_sort_banner({"icon": "shop", "colour": "neutral", "title": "Sorting your shops with the AI...",
                               "caption": "Starting the AI. The first answer can take a little while."})
        transactions, memory = list(self.transactions), dict(self.memory)

        def progress(done, total):
            self.after(0, self.sorting_progress, done, total, dict(memory))

        def work():
            problem, count, failed = app_logic.ai_problem(), 0, []
            if not problem:
                try:
                    count, failed = categorise.categorise_new(transactions, memory, progress)
                except ConnectionError:
                    problem = ("Ollama stopped answering part-way, so some shops weren't sorted. "
                               "Check Ollama is running, then click Try again.")
                except Exception as error:
                    problem = (f"The AI stopped part-way ({type(error).__name__}), so some shops weren't sorted. "
                               "Click Try again.")
            self.after(0, self.finish_sorting, memory, count, failed, problem)
        threading.Thread(target=work, daemon=True).start()

    def sorting_progress(self, done, total, memory):
        # Show each batch's categories straight away, rather than all at the end
        self.memory = memory
        self.say(f"Sorting shops with the AI... {done} of {total} done")
        self.show_sort_banner({"icon": "shop", "colour": "neutral", "title": "Sorting your shops with the AI...",
                               "caption": f"{done} of {total} shops done. Categories appear as each batch finishes."})
        self.refresh()

    def finish_sorting(self, memory, count, failed, problem):
        self.memory = memory
        self.sorting = False
        self.failed_shops.update(failed)
        self.sort_button.configure(state="normal", text="Sort shops")
        left = sum(categorise.category_of(t, memory) == categorise.UNSORTED for t in self.transactions)
        if problem:
            message = problem
            banner_title = "Shops weren't sorted" if not count else f"Only {count} shops were sorted"
        elif failed:
            message = (f"Sorted {count} shops, but the AI couldn't manage {len(failed)}. "
                       "Click Try again, or leave them as Uncategorised.")
            banner_title = f"{len(failed)} shop{'' if len(failed) == 1 else 's'} couldn't be sorted"
        else:
            message, banner_title = f"Sorted {count} new shop{'' if count == 1 else 's'}.", None
        self.show_sort_banner(banner_title and {
            "icon": "alert", "colour": "bad", "title": banner_title,
            "caption": message + f" {left} payment{'' if left == 1 else 's'} still Uncategorised."})
        if self.load_message:
            message, self.load_message = f"{self.load_message} {message}", None
        self.say(message, error=bool(problem or failed))
        self.refresh()
        if problem or failed:
            self.maybe_make_rundown()   # shops that couldn't be sorted show as Uncategorised
        else:
            self.start_sorting()   # a statement opened while the AI was busy (or, if none, the rundown)

    def show_sort_banner(self, insight):
        # The banner above the tabs saying how sorting is going, with Try again if it failed
        if self.sort_banner:
            self.sort_banner.destroy()
            self.sort_banner = None
        if insight:
            action = ("Try again", lambda: self.start_sorting(retry=True)) if insight["icon"] == "alert" else None
            self.sort_banner = banner(self, insight, action)
            self.sort_banner.pack(fill="x", padx=PAD, pady=(0, GAP), before=self.tabs)

    # ----- Showing the results -----
    def say(self, message, error=False):
        self.status.configure(text=message, text_color=BAD if error else MUTED)

    def chosen_month(self):
        return self.month_keys.get(self.month_menu.get())

    def refresh(self):
        months = summary.months(self.transactions)[::-1]
        self.month_keys = {ALL_MONTHS: None, **{summary.month_name(m): m for m in months}}
        self.month_menu.configure(values=list(self.month_keys))
        month = self.chosen_month()
        self.fill_table(month)
        totals = summary.by_category(self.transactions, self.memory, month)
        self.show_headline(month)
        self.show_budget_warning(month)
        self.show_insights(month)
        self.show_totals(totals)
        self.show_chart()
        self.show_budgets()
        self.show_reminder()

    def maybe_make_rundown(self):
        # Called once statements are loaded and the shops sorted, so the rundown's numbers are right
        if self.sorting or self.loading or self.writing_rundown:
            return
        month = assistant.rundown_due(self.transactions, self.today)
        if month:
            self.create_rundown(month)
            self.say(f"Your monthly rundown for {summary.month_name(month)} is ready on the Assistant tab.")

    def fill_table(self, month):
        self.table.delete(*self.table.get_children())
        for i, (when, description, amount, category, bank) in enumerate(
                app_logic.table_rows(self.transactions, self.memory, month)):
            colour = colour_for(category)
            if colour not in self.table_dots:
                self.table_dots[colour] = ImageTk.PhotoImage(icons.dot(colour, DOT_SIZE))
            tags = ("stripe",) * (i % 2) + (("money_in",) if amount.startswith("+") else ())
            self.table.insert("", "end", text=f"  {description}", image=self.table_dots[colour],
                              values=(category, when, bank, amount), tags=tags)

    def show_headline(self, month):
        if not self.transactions:
            self.headline.configure(text="£0 spent")
            self.subline.configure(text="Open a statement to see where your money goes.")
            return
        big, small = summary.headline(self.transactions, self.memory, month)
        self.headline.configure(text=big)
        self.subline.configure(text=small)

    def show_insights(self, month):
        for widget in self.cards_row.winfo_children():
            widget.destroy()
        cards = summary.insights(self.transactions, self.memory, month)
        for column, insight in enumerate(cards):
            last = column == len(cards) - 1
            # A single card (e.g. "Nothing sorted yet") uses the whole row, so its words aren't cut off
            insight_card(self.cards_row, insight).grid(
                row=0, column=column, columnspan=3 if len(cards) == 1 else 1, sticky="nsew",
                padx=(0 if column == 0 else GAP // 2, 0 if last else GAP // 2))

    def show_totals(self, totals):
        for widget in self.totals_frame.winfo_children():
            widget.destroy()
        label(self.totals_frame, "By category", HEADING_FONT, anchor="w").pack(fill="x", padx=6, pady=(8, GAP))
        total = sum(totals.values())
        for category, amount in totals.items():
            colour = colour_for(category)
            row = ctk.CTkFrame(self.totals_frame, fg_color="transparent")
            row.pack(fill="x", padx=6, pady=(4, 0))
            label(row, f"  {category}", image=ctk_icon(icons.dot(colour, DOT_SIZE)), compound="left").pack(side="left")
            label(row, f"£{amount:,.2f}", BOLD_FONT).pack(side="right")
            # A thin bar showing this category's share of the total
            share = ctk.CTkProgressBar(self.totals_frame, height=4, corner_radius=2, fg_color=BUTTON,
                                       progress_color=colour)
            share.set(amount / total)
            share.pack(fill="x", padx=6, pady=(2, 4))
        if not totals:
            label(self.totals_frame, "Nothing yet", colour=MUTED, anchor="w").pack(fill="x", padx=6)

    def chart_resized(self, event):
        # Redraw the chart to fit when the window changes size (after a short pause, not on every pixel)
        if self.chart_size and abs(event.width - self.chart_size[0]) + abs(event.height - self.chart_size[1]) > 20:
            if hasattr(self, "resize_job"):
                self.after_cancel(self.resize_job)
            self.resize_job = self.after(250, self.show_chart)

    def show_chart(self):
        if self.chart:
            self.chart.get_tk_widget().destroy()
            self.chart = None
        for widget in self.chart_frame.winfo_children():
            widget.destroy()
        month = self.chosen_month()
        totals = summary.by_category(self.transactions, self.memory, month)
        if not totals or summary.nothing_sorted(totals):
            card_words = summary.NOTHING_SORTED_CARD if totals else summary.NO_SPENDING_CARD
            label(self.chart_frame, f"{card_words['title']}.\n{card_words['caption']}", colour=MUTED,
                  wraplength=420, justify="center").pack(expand=True)
            return
        self.chart_frame.update_idletasks()
        width, height = self.chart_frame.winfo_width(), self.chart_frame.winfo_height()
        self.chart_size = (width, height)
        size = (max(width, 300) / 100, max(height, 200) / 100)
        name = summary.month_name(month) if month else "all months"
        kind = self.chart_switch.get()
        if kind == "Donut":
            figure = charts.donut_chart(totals, f"Share of spending, {name}", size)
        elif kind == "Calendar":
            first, last = self.date_range(month)
            figure = charts.calendar_chart(summary.by_day(self.transactions, self.memory, month),
                                           f"Spending per day, {name}", first, last, size)
        else:
            figure = charts.category_chart(totals, f"Spending by category, {name}", size)
        self.chart = FigureCanvasTkAgg(figure, master=self.chart_frame)
        self.chart.draw()
        widget = self.chart.get_tk_widget()
        widget.configure(background=PANEL, highlightthickness=0)
        widget.pack(fill="both", expand=True)

    def date_range(self, month):
        # The first and last day the calendar should show: the chosen pay month, or every loaded one
        months = [month] if month else summary.months(self.transactions)
        return payday.dates(months[0])[0], payday.dates(months[-1])[1]

class ColumnPicker(ctk.CTkToplevel):
    # Pops up for a CSV from a bank the app doesn't know, so you can say which column is which
    def __init__(self, app, path, on_save):
        super().__init__(app, fg_color=BG)
        self.title("Which column is which?")
        self.resizable(False, False)
        self.on_save = on_save
        headers = general_csv.headers(path)
        guess = app_logic.guess_columns(headers)
        label(self, "This bank is new to the app. Pick its columns once and they'll be remembered.",
              wraplength=420, justify="left").pack(padx=PAD, pady=(PAD, GAP), anchor="w")
        form = card(self)
        form.pack(fill="x", padx=PAD)
        self.bank_name = ctk.CTkEntry(form, width=200, height=BUTTON_HEIGHT, corner_radius=BUTTON_CORNER,
                                      fg_color=PANEL, border_color=BORDER, text_color=TEXT,
                                      font=BODY_FONT, placeholder_text="e.g. Monzo", placeholder_text_color=MUTED)
        self.menus = {key: menu(form, headers) for key in ("date", "description", "amount")}
        for key, chosen in guess.items():
            self.menus[key].set(chosen)
        self.date_format = menu(form, list(general_csv.DATE_FORMATS))
        rows = [("Bank name", self.bank_name), ("Date column", self.menus["date"]),
                ("Description column", self.menus["description"]), ("Amount column", self.menus["amount"]),
                ("Dates look like", self.date_format)]
        for row, (text, widget) in enumerate(rows):
            label(form, text, colour=MUTED).grid(
                row=row, column=0, sticky="w", padx=(PAD, GAP), pady=(PAD if row == 0 else 6, 6))
            widget.grid(row=row, column=1, sticky="w", padx=(GAP, PAD), pady=(PAD if row == 0 else 6, 6))
        self.flip = ctk.CTkCheckBox(form, text="Spending is shown as a positive number", font=BODY_FONT,
                                    text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER)
        self.flip.grid(row=len(rows), column=0, columnspan=2, sticky="w", padx=PAD, pady=(6, PAD))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=PAD, pady=PAD)
        button(buttons, "Open statement", self.save, main=True).pack(side="right")
        button(buttons, "Cancel", self.destroy, width=90).pack(side="right", padx=GAP)
        self.after(100, self.lift)   # make sure it opens in front of the main window
        self.grab_set()

    def save(self):
        settings = {"bank": self.bank_name.get().strip() or general_csv.NAME,
                    **{key: m.get() for key, m in self.menus.items()},
                    "date_format": self.date_format.get(), "spending_is_positive": bool(self.flip.get())}
        self.destroy()
        self.on_save(settings)

if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    SpendingApp().mainloop()
