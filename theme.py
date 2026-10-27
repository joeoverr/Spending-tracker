# The app's look in one place. Change a colour, font or size here and the window
# and the charts both pick it up. Light, clean "banking app" style.

# ----- Colours -----
BG = "#F4F5F7"        # window background (light grey)
PANEL = "#FFFFFF"     # cards, table and chart background (white)
BORDER = "#E3E5E8"    # thin card borders and dividers
BUTTON = "#EEF0F3"    # normal buttons and menus
HOVER = "#E2E5EA"     # buttons when the mouse is over them
STRIPE = "#F8F9FA"    # every other row in the transactions table
TEXT = "#191C1F"      # main text (dark charcoal)
MUTED = "#5F6672"     # secondary text, e.g. the status line
ACCENT = "#2F6BFF"    # main buttons and selected rows
ACCENT_HOVER = "#1F57E0"
ON_ACCENT = "#FFFFFF"   # text on top of the accent colour
GOOD = "#0B7F3B"      # money in, budget fine, spent less than last month
WARN = "#B45309"      # budget close to the limit
BAD = "#C8262C"       # budget gone over, spent more than last month, error messages
YOUR_BUBBLE = ACCENT        # your messages in the assistant chat
YOUR_BUBBLE_TEXT = ON_ACCENT
AI_BUBBLE = "#EEF0F3"       # the assistant's replies
AI_BUBBLE_TEXT = TEXT

# Every category always has the same colour: in the table, the totals, the charts and the cards
CATEGORY_COLOURS = {
    "Groceries": "#2FB45A",
    "Eating out": "#FF8A3D",
    "Transport": "#19A0E6",
    "Bills": "#7C5CFF",
    "Subscriptions": "#E5487F",
    "Gaming": "#4F46E5",
    "Gym": "#12B5A6",
    "Shopping": "#F5A524",
    "Entertainment": "#FF6B57",
    "Health": "#D946EF",
    "Travel": "#2F6BFF",
    "Cash": "#84CC16",
    "Income": "#0B7F3B",
    "Transfers": "#94A3B8",
    "Other": "#A1A1AA",
    "Uncategorised": "#CBD5E1",
}
SPARE_COLOURS = ["#0EA5E9", "#F43F5E", "#A3E635", "#FB923C"]   # for any category added later

def colour_for(category):
    # The category's colour, or a spare one (always the same for the same name) if it's not listed above
    if category in CATEGORY_COLOURS:
        return CATEGORY_COLOURS[category]
    return SPARE_COLOURS[sum(map(ord, category)) % len(SPARE_COLOURS)]

# Calendar heatmap: no spending, then light to dark for more spent that day
HEATMAP_COLOURS = ["#EEF0F3", "#D3E0FF", "#9DB8FF", "#5C89FF", "#2F6BFF", "#1A47C2"]

# ----- Fonts -----
FONT = "Segoe UI"
HEADLINE_FONT = (FONT, 34, "bold")   # the big "£1,028 spent in September 2026"
TITLE_FONT = (FONT, 22, "bold")
INSIGHT_FONT = (FONT, 16, "bold")    # the main line on each insight card
HEADING_FONT = (FONT, 15, "bold")
BODY_FONT = (FONT, 13)
BOLD_FONT = (FONT, 13, "bold")
SMALL_FONT = (FONT, 12)
CHART_FONT = "Segoe UI"
CHART_FONT_SIZE = 10
CHART_TITLE_SIZE = 12
DONUT_TOTAL_SIZE = 22                # the total in the middle of the donut

# ----- Sizes -----
WINDOW_SIZE = "1200x840"
PAD = 20              # space around the edges of cards
GAP = 10              # space between things inside a card
CORNER = 16           # how rounded the cards are
BORDER_WIDTH = 1      # thickness of the card borders
BUTTON_HEIGHT = 36
BUTTON_CORNER = 10
ROW_HEIGHT = 32       # height of each row in the transactions table
DOT_SIZE = 12         # the coloured category dots, in pixels
ICON_SIZE = 36        # the round icons on the insight cards, in pixels
CHART_SIZE = (6.6, 4.0)   # default chart width and height in inches (100 pixels each)
MONTH_MENU_WIDTH = 220    # wide enough for "24 Dec 2026 – 26 Jan 2027"
BUDGET_BAR_HEIGHT = 12    # the rounded progress bars on the Budgets tab
BUDGET_BOX_WIDTH = 100    # the £ boxes you type your budgets into
BUDGET_NAME_WIDTH = 150   # the category names on the Budgets tab
BUDGET_WORDS_WIDTH = 230  # "£60.50 of £70 · £9.50 left"
BUBBLE_WRAP = 620         # chat bubbles wrap their text at this width, in pixels
BUBBLE_PAD = 12           # space inside each chat bubble

# ----- Chart style -----
BAR_ROUNDNESS = 0.5   # 0 = square bar ends, 0.5 = fully round ends
GRADIENT_START = 0.45 # how pale each bar starts on the left (0 = full colour, 1 = white)
DONUT_WIDTH = 0.32    # thickness of the donut ring (1 = a full pie)
