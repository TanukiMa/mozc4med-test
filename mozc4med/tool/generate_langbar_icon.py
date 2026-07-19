#!/usr/bin/env python3
"""Generate product_icon_langbar.ico from icon_base.svg using ImageMagick.

Replaces the previous Wand opaque_paint() approach (mozc4med/tool/colorize_icons.py):
instead of recoloring pixels in an existing raster icon by fuzzy color-distance
matching, this renders the SVG -- whose colors are the actual source of truth --
at each target resolution and packs the results into a multi-resolution .ico.

Run locally to debug:

  python mozc4med/tool/generate_langbar_icon.py

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
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if not os.path.isfile(args.svg):
        print(f"error: SVG not found: {args.svg}", file=sys.stderr)
        return 1

    tmpdir = tempfile.mkdtemp(prefix="langbar_icon_")
    try:
        pngs = []
        for size in SIZES:
            out_png = os.path.join(tmpdir, f"temp_{size}.png")
            render_png(args.svg, size, out_png)
            pngs.append(out_png)

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
