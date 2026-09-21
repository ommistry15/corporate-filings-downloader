"""Regenerates assets/icon.ico and assets/icon.png (pixel-art document + download arrow).

Run from the repo root:  python tools/make_icon.py   (needs Pillow)

Design notes: drawn on a small logical pixel grid and only ever scaled with
NEAREST so edges stay crisp. The 16px frame is drawn separately (simpler
silhouette, 1px lines) because the 32px design turns to mud at 16px.

Pillow's ICO writer filters the requested sizes against the BASE image's own
size, so the base must be the largest frame, and every other frame must be
passed in append_images at exactly the requested pixel size - otherwise
Pillow silently drops sizes or LANCZOS-resamples the base instead.
"""
import os

from PIL import Image, ImageDraw

INK = (46, 43, 38, 255)
CREAM = (251, 248, 242, 255)
ACCENT = (217, 119, 87, 255)
ACCENT_DARK = (184, 92, 63, 255)
TRANSPARENT = (0, 0, 0, 0)

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")


def draw_large(n=32):
    img = Image.new("RGBA", (n, n), TRANSPARENT)
    d = ImageDraw.Draw(img)
    page = [(5, 2), (18, 2), (23, 7), (23, 20), (5, 20)]
    d.polygon(page, fill=CREAM, outline=INK, width=1)
    d.polygon([(18, 2), (23, 7), (18, 7)], fill=ACCENT_DARK, outline=INK, width=1)
    arrow = [(12, 16), (20, 16), (20, 22), (24, 22), (16, 30), (8, 22), (12, 22)]
    d.polygon(arrow, fill=ACCENT, outline=INK, width=1)
    return img


def draw_small16():
    img = Image.new("RGBA", (16, 16), TRANSPARENT)
    d = ImageDraw.Draw(img)
    page = [(2, 1), (9, 1), (12, 4), (12, 9), (2, 9)]
    d.polygon(page, fill=CREAM, outline=INK, width=1)
    d.polygon([(9, 1), (12, 4), (9, 4)], fill=ACCENT_DARK, outline=INK, width=1)
    arrow = [(5, 8), (9, 8), (9, 11), (11, 11), (7, 15), (3, 11), (5, 11)]
    d.polygon(arrow, fill=ACCENT, outline=INK, width=1)
    return img


def main():
    base32 = draw_large(32)
    frame16 = draw_small16()
    frame48 = base32.resize((48, 48), Image.NEAREST)
    frame256 = base32.resize((256, 256), Image.NEAREST)

    ico_path = os.path.join(ASSETS, "icon.ico")
    frame256.save(ico_path, format="ICO",
                  sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
                  append_images=[frame16, base32, frame48])
    frame256.save(os.path.join(ASSETS, "icon.png"))
    print("wrote", os.path.normpath(ico_path))


if __name__ == "__main__":
    main()
