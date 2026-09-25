#!/usr/bin/env python3
"""Render an SVG into a multi-resolution Windows .ico using ImageMagick.

Replaces the previous Wand opaque_paint() approach (mozc4med/tool/colorize_icons.py):
instead of recoloring pixels in an existing raster icon by fuzzy color-distance
matching, this renders the SVG -- whose colors are the actual source of truth --
at each target resolution and packs the results into a multi-resolution .ico.

Used for both product_icon_langbar.ico (from icon_base.svg) and
product_icon.ico (from icon.svg).

--png-out/--png-size additionally save one of the already-rendered
per-size PNGs to a persistent path, instead of discarding every
intermediate render along with the temp directory. This is how
src/data/images/product_icon_32bpp-128.png -- the source for
src/gui/about_dialog/about_dialog.qrc's "product_logo.png" (the "About
Mozc4med" dialog's logo) and src/unix/build_icons.py's mozc.png -- is
kept in sync with the same red-hue-shifted icon.svg that
product_icon.ico is packed from, instead of staying at its original,
un-recolored color (colorize_icons.py's .ico recoloring never touched
it: it globs only src/data/images/win/*.ico, and this PNG lives
directly under src/data/images/, outside that directory).

Run locally to debug:

  python mozc4med/tool/generate_icon_from_svg.py --svg src/data/images/icon.svg \
      --out src/data/images/win/product_icon.ico \
      --png-out src/data/images/product_icon_32bpp-128.png --png-size 128

Requires ImageMagick's `magick` on PATH. No Python image library needed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import List

DEFAULT_SVG = os.path.join("src", "data", "images", "icon_base.svg")
DEFAULT_OUT = os.path.join("src", "data", "images", "win", "product_icon_langbar.ico")
SIZES = (16, 20, 24, 32, 48, 64, 128, 256)
DENSITY = 400


def run(cmd: List[str]) -> None:
    print(f"[DEBUG] $ {' '.join(cmd)}")
    subprocess.run(cmd, check=True)


def render_png(svg: str, size: int, out_png: str) -> None:
    run([
        "magick",
        "-background", "none",
        "-density", str(DENSITY),
        svg,
        "-alpha", "on",
        "-depth", "8",
        "-resize", f"{size}x{size}",
        out_png,
    ])


def pack_ico(pngs: List[str], out_ico: str) -> None:
    run(["magick", *pngs, "-type", "TrueColorAlpha", out_ico])


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--svg", default=DEFAULT_SVG,
                         help=f"Source SVG (default: {DEFAULT_SVG})")
    parser.add_argument("--out", default=DEFAULT_OUT,
                         help=f"Output .ico path (default: {DEFAULT_OUT})")
    parser.add_argument(
        "--png-out", default=None,
        help="Optional: also save one of the per-size PNG renders here "
             "(requires --png-size). E.g. to refresh "
             "src/data/images/product_icon_32bpp-128.png alongside the .ico "
             "so it uses the same recolored SVG.")
    parser.add_argument(
        "--png-size", type=int, default=None,
        help=f"Pixel size for --png-out; must be one of {SIZES} (the sizes "
             f"already rendered for the .ico)")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if not os.path.isfile(args.svg):
        print(f"error: SVG not found: {args.svg}", file=sys.stderr)
        return 1

    if bool(args.png_out) != bool(args.png_size):
        print("error: --png-out and --png-size must be given together",
              file=sys.stderr)
        return 1
    if args.png_size is not None and args.png_size not in SIZES:
        print(f"error: --png-size {args.png_size} is not one of {SIZES}",
              file=sys.stderr)
        return 1

    tmpdir = tempfile.mkdtemp(prefix="svg_icon_")
    try:
        pngs = []
        for size in SIZES:
            out_png = os.path.join(tmpdir, f"temp_{size}.png")
            render_png(args.svg, size, out_png)
            pngs.append(out_png)
            if size == args.png_size:
                png_out_dir = os.path.dirname(args.png_out)
                if png_out_dir:
                    os.makedirs(png_out_dir, exist_ok=True)
                shutil.copyfile(out_png, args.png_out)
                print(f"[DEBUG] also wrote {args.png_out} (size={size}, "
                      f"same render used in {args.out})")

        out_dir = os.path.dirname(args.out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        pack_ico(pngs, args.out)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    print(f"[DEBUG] wrote {args.out}")
    run(["magick", "identify", args.out])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
