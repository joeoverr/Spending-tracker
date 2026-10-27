# Draws the charts with matplotlib, using the colours, fonts and sizes from theme.py.
# Each chart takes size=(width, height) in inches, so the window can draw it to fit exactly.
import math
from datetime import timedelta
import numpy as np
from matplotlib import rcParams
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.colors import to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch
from theme import (PANEL, TEXT, MUTED, ACCENT, HEATMAP_COLOURS, CHART_FONT, CHART_SIZE, CHART_FONT_SIZE,
                   CHART_TITLE_SIZE, DONUT_TOTAL_SIZE, BAR_ROUNDNESS, GRADIENT_START, DONUT_WIDTH, colour_for)

rcParams["font.family"] = [CHART_FONT, "DejaVu Sans"]   # DejaVu is matplotlib's backup font

def _figure(size):
    figure = Figure(figsize=size, dpi=100, facecolor=PANEL)
    axes = figure.add_subplot()
    axes.set_facecolor(PANEL)
    axes.tick_params(colors=MUTED, labelsize=CHART_FONT_SIZE)
    for side in ("top", "right", "left"):
        axes.spines[side].set_visible(False)
    axes.spines["bottom"].set_color(MUTED)
    return figure, axes

def _title(axes, title):
    axes.set_title(title, color=TEXT, fontsize=CHART_TITLE_SIZE, fontweight="bold", loc="left", pad=12)

def brightness(colour):
    # How bright a colour looks to the eye, from 0 (black) to 1 (white), using the standard web formula
    def channel(c):
        c = int(c, 16) / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(colour[i:i + 2]) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b

def contrast(a, b):
    # How easy text in one colour is to read on the other: 1 = invisible, 21 = black on white
    light, dark = sorted((brightness(a), brightness(b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)

def text_on(colour):
    # White or charcoal, whichever is easier to read on this colour
    return max(("#FFFFFF", TEXT), key=lambda text: contrast(text, colour))

# ----- Bar chart: rounded bars with a soft gradient, in each category's colour -----
def gradient(colour, steps=256):
    # A row of colours from pale (mixed with white) on the left to the full colour on the right
    full, white = np.array(to_rgb(colour)), np.ones(3)
    start = full + (white - full) * GRADIENT_START
    return np.linspace(start, full, steps)[np.newaxis, :, :]

def category_chart(totals, title, size=CHART_SIZE):
    figure, axes = _figure(size)
    names, values = list(totals), list(totals.values())
    most, height = max(values), 0.62
    right = most * 1.25   # room for the £ label after the longest bar
    axes.set_xlim(0, right)
    axes.set_ylim(len(names) - 0.4, -0.6)   # biggest bar at the top
    axes.set_yticks(range(len(names)), names)
    axes.tick_params(axis="y", colors=TEXT, length=0, pad=8)
    axes.set_xticks([])
    axes.spines["bottom"].set_visible(False)
    _title(axes, title)
    figure.tight_layout()
    # Measure the chart in pixels, so the round ends come out as circles rather than ovals
    FigureCanvasAgg(figure)
    box = axes.get_window_extent()
    x_per_pixel, y_per_pixel = right / box.width, len(names) / box.height
    for row, (name, value) in enumerate(zip(names, values)):
        radius = min(height / y_per_pixel * BAR_ROUNDNESS, value / x_per_pixel / 2)   # in pixels
        shape = FancyBboxPatch((0, row - height / 2), value, height, facecolor="none", edgecolor="none",
                               boxstyle=f"round,pad=0,rounding_size={radius * x_per_pixel}",
                               mutation_aspect=y_per_pixel / x_per_pixel)
        axes.add_patch(shape)
        image = axes.imshow(gradient(colour_for(name)), extent=(0, value, row + height / 2, row - height / 2),
                            aspect="auto", interpolation="bilinear")
        image.set_clip_path(shape)
        axes.text(value + most * 0.02, row, f"£{value:,.2f}", va="center", color=TEXT,
                  fontsize=CHART_FONT_SIZE, fontweight="bold")
    axes.set_xlim(0, right)   # drawing the gradients moves the edges, so put them back
    axes.set_ylim(len(names) - 0.4, -0.6)
    return figure

def month_chart(totals, title, size=CHART_SIZE):
    figure, axes = _figure(size)
    labels = [m[5:] + "/" + m[2:4] for m in totals]   # 2026-08 -> 08/26
    bars = axes.bar(labels, list(totals.values()), color=ACCENT, width=0.6)
    axes.bar_label(bars, labels=[f"£{v:,.0f}" for v in totals.values()], padding=3, color=TEXT, fontsize=CHART_FONT_SIZE)
    _title(axes, title)
    axes.set_yticks([])
    axes.margins(y=0.15)
    figure.tight_layout()
    return figure

# ----- Donut chart: a ring split by category, with the total in the middle -----
def donut_chart(totals, title, size=CHART_SIZE):
    figure = Figure(figsize=size, dpi=100, facecolor=PANEL)
    names, values = list(totals), list(totals.values())
    total = sum(values)
    ring = figure.add_axes([0.0, 0.04, 0.52, 0.82])
    ring.pie(values, colors=[colour_for(n) for n in names], startangle=90, counterclock=False, radius=1,
             wedgeprops={"width": DONUT_WIDTH, "edgecolor": PANEL, "linewidth": 2.5})
    ring.text(0, 0.1, f"£{total:,.0f}", ha="center", va="center", color=TEXT,
              fontsize=DONUT_TOTAL_SIZE, fontweight="bold")
    ring.text(0, -0.17, "spent", ha="center", va="center", color=MUTED, fontsize=CHART_FONT_SIZE + 1)
    ring.set_aspect("equal")
    # The key on the right: dot, category, amount and share, in neat columns
    key = figure.add_axes([0.54, 0.04, 0.44, 0.82])
    key.axis("off")
    key.set_xlim(0, 1)
    key.set_ylim(max(len(names), 8), 0)
    for row, (name, value) in enumerate(zip(names, values)):
        y = row + 0.5
        key.scatter(0.03, y, s=70, color=colour_for(name), edgecolors="none")
        key.text(0.09, y, name, va="center", color=TEXT, fontsize=CHART_FONT_SIZE)
        key.text(0.80, y, f"£{value:,.0f}", va="center", ha="right", color=TEXT, fontsize=CHART_FONT_SIZE, fontweight="bold")
        key.text(0.99, y, f"{value / total:.0%}", va="center", ha="right", color=MUTED, fontsize=CHART_FONT_SIZE)
    figure.text(0.02, 0.94, title, color=TEXT, fontsize=CHART_TITLE_SIZE, fontweight="bold", va="center")
    return figure

# ----- Calendar heatmap -----
def calendar_cells(daily, first, last):
    # One square per day from first to last: (day, column, row, shade). Columns are weeks,
    # rows are Monday (0) to Sunday (6). Shade 0 means nothing spent; 1-5 go from a little to the most.
    monday = first - timedelta(days=first.weekday())
    most = max(daily.values(), default=0)
    cells, day = [], first
    while day <= last:
        spent = daily.get(day, 0)
        shade = 0 if spent <= 0 else min(5, math.ceil(5 * spent / most))
        cells.append((day, (day - monday).days // 7, day.weekday(), shade))
        day += timedelta(days=1)
    return cells

def calendar_chart(daily, title, first, last, size=CHART_SIZE):
    # One pay month or less is drawn like a wall calendar (a row per week, Monday to Sunday across),
    # with the key on the right. Longer spans are drawn GitHub-style: a column per week, key below.
    figure, axes = _figure(size)
    cells = calendar_cells(daily, first, last)
    weeks = cells[-1][1] + 1 if cells else 1
    wall = (last - first).days < 42
    width, height = (7, weeks) if wall else (weeks, 7)
    # How many pixels each square gets, so day numbers are only written in squares big enough for them
    drawing = (width + 8.3, height + 1.0) if wall else (width + 1.5, height + 3.9)
    numbered = min(size[0] * 100 / drawing[0], size[1] * 100 * 0.85 / drawing[1]) >= 22
    biggest = max(daily, key=daily.get) if daily else None
    square = 0.86
    labelled = set()
    for day, week, weekday, shade in cells:
        x, y = (weekday, -week) if wall else (week, -weekday)
        colour = HEATMAP_COLOURS[shade]
        is_biggest = day == biggest
        axes.add_patch(FancyBboxPatch((x, y), square, square, boxstyle="round,pad=0,rounding_size=0.16",
                                      facecolor=colour, edgecolor=TEXT if is_biggest else "none",
                                      linewidth=2 if is_biggest else 0))
        if numbered:
            axes.text(x + square / 2, y + square / 2, str(day.day), ha="center", va="center",
                      color=text_on(colour) if shade else MUTED, fontsize=CHART_FONT_SIZE,
                      fontweight="bold" if is_biggest else "normal")
        if day.day == 1 or day == first:
            if wall:   # month name to the left of the week it starts in
                if week not in labelled:
                    axes.text(-0.25, y + square / 2, day.strftime("%b"), ha="right", va="center", color=TEXT,
                              fontsize=CHART_FONT_SIZE, fontweight="bold")
                    labelled.add(week)
            else:      # month name above its first full week (or the very first week), never two in one place
                spot = week + (1 if day != first and day.weekday() != 0 else 0)
                if spot not in labelled and spot - 1 not in labelled:
                    axes.text(spot, 1.25, day.strftime("%b"), color=TEXT, fontsize=CHART_FONT_SIZE, fontweight="bold")
                    labelled.add(spot)
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for i, name in enumerate(names):
        if wall:
            axes.text(i + square / 2, 1.25, name[:2], ha="center", va="center", color=MUTED, fontsize=CHART_FONT_SIZE)
        elif i % 2 == 0:
            axes.text(-0.25, -i + square / 2, name, ha="right", va="center", color=MUTED, fontsize=CHART_FONT_SIZE)
    # "£0 ■■■■■■ £142" key and the biggest day: on the right of a wall calendar, otherwise underneath
    if wall:
        key_x, key_y, caption = width + 1.4, 0.43, (width + 1.0, -1.0)
    else:
        key_x, key_y, caption = width - len(HEATMAP_COLOURS) * 0.6, -height - 0.2, (-1.3, -height - 1.45)
    axes.text(key_x - 0.25, key_y, "£0", ha="right", va="center", color=MUTED, fontsize=CHART_FONT_SIZE)
    for i, colour in enumerate(HEATMAP_COLOURS):
        axes.add_patch(FancyBboxPatch((key_x + i * 0.6, key_y - 0.25), 0.5, 0.5, boxstyle="round,pad=0,rounding_size=0.1",
                                      facecolor=colour, edgecolor="none"))
    axes.text(key_x + len(HEATMAP_COLOURS) * 0.6, key_y, f"£{max(daily.values(), default=0):,.0f}",
              va="center", color=MUTED, fontsize=CHART_FONT_SIZE)
    if biggest:
        words = f"Biggest day: {biggest:%a} {biggest.day} {biggest:%b}" + ("\n" if wall else "  ·  ") + f"£{daily[biggest]:,.2f}"
        axes.text(*caption, words, va="top" if wall else "center", color=TEXT, fontsize=CHART_FONT_SIZE,
                  fontweight="bold", linespacing=1.6)
    if wall:
        axes.set_xlim(-1.3, width + 7.0)
        axes.set_ylim(-height + 0.7, 1.8)
    else:
        axes.set_xlim(-1.3, width + 0.2)
        axes.set_ylim(-height - 1.9, 2.0)
    axes.set_aspect("equal")
    axes.axis("off")
    _title(axes, title)
    figure.tight_layout()
    return figure
