#!/usr/bin/env python3
"""Shift every color in an SVG to a target hue, in place.

Replaces the previous `sed -e "s/F80/FF0000/g"` approach, which only
touched the single literal substring "F80" and silently left every other
orange color in icon_base.svg (#DA5B07, #EA7104, #FBB13A, #FDC976,
#FFE57E, ...) unchanged -- so the generated icon still looked orange.

Each color's hue is replaced while its saturation and lightness are kept
as-is, so gradients, highlights, and shadows keep their relative shading;
only the hue changes. Near-grayscale colors (low saturation, e.g. white
highlights or black shadows) are barely affected, since hue has little
effect when saturation is near zero.

Run locally to debug:

  python mozc4med/tool/hue_shift_svg.py --verbose
"""

from __future__ import annotations

import argparse
import colorsys
import os
import re
import sys
from typing import List, Match

DEFAULT_SVG = os.path.join("src", "data", "images", "icon_base.svg")
DEFAULT_HUE_DEGREES = 0.0  # red

# Matches fill="#abc" / stroke="#abc" / stop-color="#abc" (and their 6-digit
# forms). Gradient/filter references like url(#c) use a bare 1-letter id,
# never 3 or 6 hex digits, so they never match this pattern.
_COLOR_ATTR_RE = re.compile(
    r'(fill|stroke|stop-color)="(#[0-9A-Fa-f]{3}|#[0-9A-Fa-f]{6})"'
)


def _expand_hex(digits: str) -> str:
    """Expand a 3-digit hex color to 6 digits (e.g. "f80" -> "ff8800")."""
    if len(digits) == 3:
        return "".join(c * 2 for c in digits)
    return digits


def shift_hue(hex_color: str, hue_degrees: float) -> str:
    """Return `hex_color` with its hue replaced by `hue_degrees`.

    Saturation and lightness are preserved, so only the hue changes.
    """
    digits = _expand_hex(hex_color.lstrip("#"))
    r, g, b = (int(digits[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    new_r, new_g, new_b = colorsys.hls_to_rgb(hue_degrees / 360.0, l, s)
    return "#{:02X}{:02X}{:02X}".format(
        round(new_r * 255), round(new_g * 255), round(new_b * 255))


def process(svg_text: str, hue_degrees: float, verbose: bool) -> str:
    def _replace(match: Match[str]) -> str:
        attr, color = match.group(1), match.group(2)
        new_color = shift_hue(color, hue_degrees)
        if verbose:
            print(f"[DEBUG] {attr}: {color} -> {new_color}")
        return f'{attr}="{new_color}"'

    return _COLOR_ATTR_RE.sub(_replace, svg_text)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--svg", default=DEFAULT_SVG,
        help=f"SVG to recolor in place (default: {DEFAULT_SVG})")
    parser.add_argument(
        "--hue-degrees", type=float, default=DEFAULT_HUE_DEGREES,
        help="Target hue in degrees on the HSL color wheel (default: 0 = red)")
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print each color attribute before/after")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if not os.path.isfile(args.svg):
        print(f"error: SVG not found: {args.svg}", file=sys.stderr)
        return 1

    with open(args.svg, "r", encoding="utf-8") as f:
        original = f.read()

    matches = _COLOR_ATTR_RE.findall(original)
    if not matches:
        print(f"error: no fill/stop-color hex attributes found in {args.svg}",
              file=sys.stderr)
        return 1

    updated = process(original, args.hue_degrees, args.verbose)

    with open(args.svg, "w", encoding="utf-8") as f:
        f.write(updated)

    print(f"[DEBUG] recolored {len(matches)} color attribute(s) in {args.svg} "
          f"to hue={args.hue_degrees} degrees")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
