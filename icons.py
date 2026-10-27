# Draws the small coloured dots and round icons used in the window. They're drawn 4 times
# bigger and then shrunk, which gives smooth edges. No emojis or image files needed.
from functools import lru_cache
from PIL import Image, ImageDraw
from theme import PANEL

SMOOTH = 4

def mix(colour, other, amount):
    # A colour part-way to another: amount 0 = colour, 1 = other
    a = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(other[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * amount):02X}" for x, y in zip(a, b))

@lru_cache(maxsize=None)
def dot(colour, size):
    big = Image.new("RGBA", (size * SMOOTH, size * SMOOTH), (0, 0, 0, 0))
    ImageDraw.Draw(big).ellipse((0, 0, size * SMOOTH - 1, size * SMOOTH - 1), fill=colour)
    return big.resize((size, size), Image.LANCZOS)

@lru_cache(maxsize=None)
def badge(kind, colour, size):
    # A soft-tinted circle with a simple symbol in the colour:
    # "up" / "down" arrows, "dot" (a category), "day" (a calendar page), "shop" (a bag), "average" (bars),
    # "alert" (an exclamation mark) and "download" (an arrow into a tray)
    s = size * SMOOTH
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.ellipse((0, 0, s - 1, s - 1), fill=mix(colour, PANEL, 0.85))
    c, w = s / 2, max(2, s // 14)
    if kind in ("up", "down"):
        tip, tail = (c - s * 0.2, c + s * 0.2) if kind == "up" else (c + s * 0.2, c - s * 0.2)
        draw.line((c, tail, c, tip), fill=colour, width=w)
        wing = s * 0.13 if kind == "up" else -s * 0.13
        draw.line((c - s * 0.15, tip + wing, c, tip, c + s * 0.15, tip + wing), fill=colour, width=w, joint="curve")
    elif kind == "dot":
        r = s * 0.17
        draw.ellipse((c - r, c - r, c + r, c + r), fill=colour)
    elif kind == "day":
        box = (c - s * 0.2, c - s * 0.17, c + s * 0.2, c + s * 0.21)
        draw.rounded_rectangle(box, radius=s * 0.05, outline=colour, width=w)
        draw.rectangle((box[0], box[1], box[2], box[1] + s * 0.09), fill=colour)
    elif kind == "alert":
        draw.rounded_rectangle((c - w * 0.6, c - s * 0.22, c + w * 0.6, c + s * 0.06), radius=w * 0.6, fill=colour)
        r = w * 0.75
        draw.ellipse((c - r, c + s * 0.16 - r, c + r, c + s * 0.16 + r), fill=colour)
    elif kind == "download":
        draw.line((c, c - s * 0.22, c, c + s * 0.06), fill=colour, width=w)
        draw.line((c - s * 0.12, c - s * 0.05, c, c + s * 0.07, c + s * 0.12, c - s * 0.05), fill=colour, width=w,
                  joint="curve")
        draw.line((c - s * 0.2, c + s * 0.08, c - s * 0.2, c + s * 0.2, c + s * 0.2, c + s * 0.2, c + s * 0.2, c + s * 0.08),
                  fill=colour, width=w, joint="curve")
    elif kind == "shop":
        draw.rounded_rectangle((c - s * 0.19, c - s * 0.08, c + s * 0.19, c + s * 0.22), radius=s * 0.04, fill=colour)
        draw.arc((c - s * 0.1, c - s * 0.24, c + s * 0.1, c + s * 0.04), 180, 360, fill=colour, width=w)
    else:   # "average"
        for i, height in enumerate((0.12, 0.22, 0.16)):
            x = c - s * 0.16 + i * s * 0.13
            draw.rounded_rectangle((x, c + s * 0.18 - s * height * 1.6, x + s * 0.08, c + s * 0.18),
                                   radius=s * 0.03, fill=colour)
    return image.resize((size, size), Image.LANCZOS)
