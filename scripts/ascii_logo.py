#!/usr/bin/env python3
"""Render the Arooohi logo (Misc./logo2.png) as ANSI half-block terminal art.

Usage: python3 scripts/ascii_logo.py [path-to-png] [width-in-cols]

The logo is a grey mark on a white background. Near-white pixels are treated as
transparent so the mark renders on the terminal's own background colour.
"""

import sys

from PIL import Image

WHITE_EDGE = 235


def is_bg(pixel):
    r, g, b, a = pixel
    return a < 40 or (r > WHITE_EDGE and g > WHITE_EDGE and b > WHITE_EDGE)


def fg24(c):
    r, g, b, _ = c
    return f"\x1b[38;2;{r};{g};{b}m"


def bg24(c):
    r, g, b, _ = c
    return f"\x1b[48;2;{r};{g};{b}m"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "Misc./logo2.png"
    width = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 48

    im = Image.open(path).convert("RGBA")
    w, h = im.size
    new_w = max(8, width)
    new_h = max(2, round(new_w * h / w / 2) * 2)
    im = im.resize((new_w, new_h), Image.LANCZOS)
    px = im.load()

    lines = []
    for y in range(0, new_h, 2):
        cells = []
        for x in range(new_w):
            top = px[x, y]
            bot = px[x, y + 1] if y + 1 < new_h else (0, 0, 0, 0)
            t_bg, b_bg = is_bg(top), is_bg(bot)
            if t_bg and b_bg:
                cells.append(" ")
            elif b_bg:
                cells.append(f"{fg24(top)}\u2580\x1b[0m")
            elif t_bg:
                cells.append(f"{fg24(bot)}\u2584\x1b[0m")
            else:
                cells.append(f"{fg24(top)}{bg24(bot)}\u2580\x1b[0m")
        lines.append("".join(cells).rstrip())

    for line in lines:
        print(line)


if __name__ == "__main__":
    main()
