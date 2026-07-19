#!/usr/bin/env python3
"""Recolor Windows .ico files in place by replacing one color with another.

Wraps Wand/ImageMagick's opaque_paint. Can be run locally to debug why a
given icon didn't recolor as expected:

  python mozc4med/tool/colorize_icons.py --verbose

Requires the `wand` package and an ImageMagick install with `magick` on PATH.
"""

from __future__ import annotations

import argparse
import glob
import os
import subprocess
import sys
from typing import List

from wand.color import Color
from wand.image import Image

DEFAULT_DIR = os.path.join("src", "data", "images", "win")
DEFAULT_TARGET_COLOR = "#FF6600"
DEFAULT_FILL_COLOR = "#FF0000"
DEFAULT_FUZZ_PERCENT = 30.0


def show_colors(path: str, label: str) -> None:
    print(f"::group::[DEBUG] {label} magick identify -verbose {path}")
    subprocess.run(["magick", "identify", "-verbose", path], check=False)
    print("::endgroup::")


def _count_exact(img: Image, color: str) -> int:
    """Number of pixels exactly equal to `color` in the image's histogram."""
    target = Color(color)
    return sum(count for pixel, count in img.histogram.items() if pixel == target)


def colorize(path: str, target: str, fill: str, fuzz_percent: float,
             verbose: bool) -> bool:
    """Recolor a single icon in place.

    Returns whether any pixel actually matched `target` and got repainted.
    Note: Wand's own opaque_paint() return value is just an ImageMagick call
    status flag -- it is True even when zero pixels matched -- so matching
    must be verified separately via the pixel histogram.
    """
    if verbose:
        show_colors(path, "BEFORE")
    with Image(filename=path) as img:
        fill_before = _count_exact(img, fill)
        # Wand's fuzz is an absolute value in [0, quantum_range], not a
        # percentage, so it must be scaled by quantum_range here.
        fuzz = img.quantum_range * fuzz_percent / 100
        img.opaque_paint(target, fill, fuzz=fuzz)
        fill_after = _count_exact(img, fill)
        img.save(filename=path)
    matched_pixels = fill_after - fill_before
    print(f"[DEBUG] {path}: {matched_pixels} pixel(s) repainted to {fill}")
    if verbose:
        show_colors(path, "AFTER")
    return matched_pixels > 0


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dir", default=DEFAULT_DIR,
        help=f"Directory containing .ico files to recolor (default: {DEFAULT_DIR})")
    parser.add_argument("--target", default=DEFAULT_TARGET_COLOR,
                         help="Color to replace")
    parser.add_argument("--fill", default=DEFAULT_FILL_COLOR,
                         help="Replacement color")
    parser.add_argument(
        "--fuzz-percent", type=float, default=DEFAULT_FUZZ_PERCENT,
        help="Color match tolerance, as a percentage of quantum_range")
    parser.add_argument(
        "--verbose", action="store_true",
        help="Dump `magick identify -verbose` output before/after each file")
    parser.add_argument(
        "--exclude", action="append", default=[], metavar="FILENAME",
        help="Base filename to skip (e.g. an icon generated separately from an "
             "SVG source). May be repeated.")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    all_files = sorted(glob.glob(os.path.join(args.dir, "*.ico")))
    excluded = set(args.exclude)
    files = [f for f in all_files if os.path.basename(f) not in excluded]
    if excluded:
        print(f"[DEBUG] excluding {sorted(excluded)}")
    print(f"[DEBUG] {len(files)} .ico file(s) to colorize in {args.dir}: {files}")
    if not files:
        print(f"error: no .ico files found in {args.dir}", file=sys.stderr)
        return 1

    changed = [
        f for f in files
        if colorize(f, args.target, args.fill, args.fuzz_percent, args.verbose)
    ]
    unchanged = [f for f in files if f not in changed]

    # Not every icon contains the target color (e.g. grayscale/disabled-state
    # variants), so an unchanged file is not necessarily a bug. Report both
    # lists so it's obvious at a glance which files were actually rewritten.
    print(f"[DEBUG] repainted ({len(changed)}): {changed}")
    print(f"[DEBUG] unchanged ({len(unchanged)}): {unchanged}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
