"""
VYTA - Make the logo files the dashboard uses
----------------------------------------------
Run with:   py make_logo_assets.py

Reads  assets\\vyta_logo.png  (the master logo: navy mark and navy "vyta" on a light background) and writes:
  assets\\vyta_logo_dark.png   - background removed, wordmark turned white (for the dark navy sidebar)
  assets\\vyta_mark.png        - just the round mark, background removed (browser-tab icon)
Run it again if the master logo changes.
"""

from pathlib import Path

from PIL import Image

ASSETS = Path("assets")
MASTER = ASSETS / "vyta_logo.png"


def main():
    im = Image.open(MASTER).convert("RGB")
    w, h = im.size
    bg = im.getpixel((2, 2))
    px = im.load()

    def differs(x, y):
        return sum(abs(a - b) for a, b in zip(px[x, y], bg)) > 60

    # The round mark is the first block of non-background columns from the left; the wordmark follows a gap
    cols = [x for x in range(w) if any(differs(x, y) for y in range(h))]
    mark_right = cols[-1]
    for a, b in zip(cols, cols[1:]):
        if b - a > 1:
            mark_right = a
            break
    mark_cols = [x for x in cols if x <= mark_right]
    rows = [y for y in range(h) if any(differs(x, y) for x in mark_cols)]
    left, right, top, bottom = min(mark_cols), max(mark_cols), min(rows), max(rows)
    cx, cy, r = (left + right) / 2, (top + bottom) / 2, (right - left + 1) / 2
    word = [x for x in cols if x > mark_right]

    bg_lum = sum(bg) / 3
    navy = px[int(cx - r * 0.85), int(cy)]
    navy_lum = sum(navy) / 3
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    o = out.load()
    for y in range(h):
        for x in range(w):
            if x <= mark_right:
                # Inside the circle: keep the pixel, with a soft one-pixel edge
                dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                alpha = max(0.0, min(1.0, r - dist + 0.5))
                if alpha:
                    o[x, y] = (*px[x, y], round(alpha * 255))
            elif word and x >= min(word):
                # Wordmark: darkness becomes opacity, colour becomes white
                alpha = max(0.0, min(1.0, (bg_lum - sum(px[x, y]) / 3) / (bg_lum - navy_lum)))
                if alpha:
                    o[x, y] = (255, 255, 255, round(alpha * 255))

    box = out.getbbox()
    out.crop(box).save(ASSETS / "vyta_logo_dark.png")
    out.crop((left, top, right + 1, bottom + 1)).save(ASSETS / "vyta_mark.png")
    print(f"[DONE] Saved {ASSETS / 'vyta_logo_dark.png'} and {ASSETS / 'vyta_mark.png'}")


if __name__ == "__main__":
    main()
