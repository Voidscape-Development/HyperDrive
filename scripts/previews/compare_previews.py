"""Compares two renders of the layouts (render_previews.py --out) and reports
the pages that look different, as Markdown.

Usage:
    python scripts/previews/compare_previews.py BASE NEW [--diff DIR] [--min PCT]

A page differs when more than --min percent (default 0.1) of its pixels
changed noticeably. With --diff, each one is saved there as BASE above NEW,
with the changed pixels in magenta in between.
"""

import argparse
import os
import sys

from PIL import Image, ImageChops

# A channel moving less than this is antialiasing or GPU noise
NOISE = 24


def changed_mask(a, b):
    """1-bit image of the pixels where a and b differ beyond the noise."""
    diff = ImageChops.difference(a, b).split()
    # A pixel changed when any of its channels did
    mask = diff[0]
    for channel in diff[1:]:
        mask = ImageChops.lighter(mask, channel)
    return mask.point(lambda v: 255 if v > NOISE else 0).convert("1")


def side_by_side(a, b, mask):
    """a over the changes over b, at half size."""
    w, h = a.size
    sheet = Image.new("RGBA", (w, h * 3), (40, 40, 40, 255))
    sheet.paste(a, (0, 0), a)
    sheet.paste(Image.new("RGBA", a.size, (255, 0, 255, 255)), (0, h), mask)
    sheet.paste(b, (0, h * 2), b)
    return sheet.resize((w // 2, h * 3 // 2))


def pngs(folder):
    return {
        os.path.relpath(os.path.join(d, f), folder).replace(os.sep, "/")
        for d, _, files in os.walk(folder)
        for f in files
        if f.endswith(".png")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("base")
    parser.add_argument("new")
    parser.add_argument("--diff", help="Folder for images of the pages that differ")
    parser.add_argument("--min", type=float, default=0.1, help="Percent of pixels that counts")
    args = parser.parse_args()

    base, new = pngs(args.base), pngs(args.new)
    rows = [(None, page, "new page") for page in sorted(new - base)]
    rows += [(None, page, "no longer renders") for page in sorted(base - new)]
    for page in sorted(base & new):
        a = Image.open(os.path.join(args.base, page)).convert("RGBA")
        b = Image.open(os.path.join(args.new, page)).convert("RGBA")
        if a.size != b.size:
            rows.append((None, page, "size changed"))
            continue
        mask = changed_mask(a, b)
        percent = 100 * mask.histogram()[-1] / (a.width * a.height)
        if percent <= args.min:
            continue
        rows.append((percent, page, ""))
        if args.diff:
            out = os.path.join(args.diff, page)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            side_by_side(a, b, mask).save(out)

    if not rows:
        print(f"No visual changes in {len(base | new)} pages.")
        return 0
    rows.sort(key=lambda r: -1 if r[0] is None else -r[0])
    print(f"{len(rows)} of {len(base | new)} pages look different:\n")
    print("| Page | Pixels changed |\n| --- | --- |")
    for percent, page, note in rows:
        print(f"| `{page}` | {note or f'{percent:.2f}%'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
