#!/usr/bin/env python3
"""Regenerate the Windows mode/tool .ico files from the mozc4med icon design.

Replaces the previous "same icon for every .ico" step, which made the
language bar's input-mode indicators (hiragana, katakana, direct input, ...)
indistinguishable. Per file under src/data/images/win/:

  * ms_hiragana / ms_katakana / ms_katakana_half / ms_alpha / ms_alpha_half /
    ms_direct_input (+ their `_a` variants): the mozc4med base design
    (mozc4med/assets/icon.svg) with the upstream mode glyph overlaid. The
    glyph is taken from the upstream ms_<mode>.svg next to the .ico files
    (white glyph with a dark outline), so no glyph artwork is duplicated here.
  * ms_disabled / ms_disabled_a: the base design in grayscale.
  * everything else (tools_*.ico): the plain base design. Upstream has no
    glyph SVG for these.

`*_a.ico` keep their multi-resolution layout (SIZES); the other files stay
single 16x16 icons, matching upstream. Each distinct variant is rendered once
per size and packed into every .ico that uses it.

product_icon.ico / product_icon_langbar.ico are skipped: they are generated
by generate_icon_from_svg.py.

Run locally to debug (writes into --dir; use a copy of the directory):

  python mozc4med/tool/generate_win_mode_icons.py --dir <copy of win dir>

Requires ImageMagick's `magick` on PATH.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys
import tempfile
from typing import Dict, List, Optional, Tuple

try:
    from mozc4med.tool import generate_icon_from_svg as gen
except ImportError:  # run as a plain script from the repo root
    import generate_icon_from_svg as gen  # type: ignore[no-redef]

DEFAULT_DIR = os.path.join("src", "data", "images", "win")
DEFAULT_BASE_SVG = os.path.join("mozc4med", "assets", "icon.svg")
SKIP = frozenset({"product_icon.ico", "product_icon_langbar.ico"})
SMALL_SIZES = (16,)

# .ico stem (without the `_a` suffix) -> upstream glyph SVG in --dir.
GLYPH_SVGS = {
    "ms_alpha": "ms_alpha.svg",
    "ms_alpha_half": "ms_alpha_half.svg",
    "ms_direct_input": "ms_direct_input.svg",
    "ms_hiragana": "ms_hiragana.svg",
    "ms_katakana": "ms_katakana.svg",
    "ms_katakana_half": "ms_katakana_half.svg",
}
DISABLED_STEM = "ms_disabled"

# Glyph placement inside the 1024x1024 base design. Upstream glyph SVGs are
# 16x16 with no viewBox.
#   large sizes: glyph inset so the full-strength circles stay visible around it.
#   small sizes (<= SMALL_MAX_SIZE px): glyph fills the icon and the circles are
#   faded, because a thin outlined glyph over saturated colors turns to mush
#   at 16-24px.
GLYPH_BOX_LARGE = (102, 102, 820)  # x, y, width/height
GLYPH_BOX_SMALL = (0, 0, 1024)
SMALL_CIRCLE_OPACITY = 0.35
SMALL_MAX_SIZE = 24
GLYPH_VIEWBOX = "0 0 16 16"

_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")


def split_name(ico_name: str) -> Tuple[str, bool]:
    """'ms_hiragana_a.ico' -> ('ms_hiragana', True); 'tools_icon.ico' -> ('tools_icon', False)."""
    stem = os.path.splitext(ico_name)[0]
    if stem.endswith("_a"):
        return stem[:-2], True
    return stem, False


def variant_for(stem: str) -> str:
    """Variant key shared by every .ico that renders identically."""
    if stem in GLYPH_SVGS:
        return stem
    if stem == DISABLED_STEM:
        return "disabled"
    return "plain"


def _gray_hex(match: "re.Match[str]") -> str:
    r, g, b = (int(match.group(1)[i:i + 2], 16) for i in (0, 2, 4))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    # Lift and compress so the disabled icon reads as "dimmed", not black.
    v = round(90 + lum * 0.6)
    return f"#{v:02x}{v:02x}{v:02x}"


def gray_svg(base_svg: str) -> str:
    """Replace every #rrggbb color with a dimmed gray of equal luminance."""
    return _HEX.sub(_gray_hex, base_svg)


def glyph_inner(glyph_svg: str) -> str:
    """Inner markup of the glyph SVG, with an explicit fill on every path.

    The upstream root carries fill="none" and some outline paths rely on
    inheriting it; ImageMagick's renderer does not inherit it through a nested
    <svg>, so those paths would otherwise be painted solid black.
    """
    m = re.search(r"<svg\b[^>]*>(.*)</svg>", glyph_svg, re.DOTALL)
    if not m:
        raise ValueError("glyph SVG has no <svg> root")
    return re.sub(r"<path(?![^>]*\bfill=)", '<path fill="none"', m.group(1))


def overlay_glyph(base_svg: str, glyph_svg: str, small: bool = False) -> str:
    """Return base_svg with the glyph nested on top (before the closing tag)."""
    if "</svg>" not in base_svg:
        raise ValueError("base SVG has no closing </svg>")
    if small:
        x, y, size = GLYPH_BOX_SMALL
        base_svg = base_svg.replace(
            "<circle ", f'<circle opacity="{SMALL_CIRCLE_OPACITY}" ')
    else:
        x, y, size = GLYPH_BOX_LARGE
    nested = (
        f'<svg x="{x}" y="{y}" width="{size}" height="{size}" '
        f'viewBox="{GLYPH_VIEWBOX}" fill="none">{glyph_inner(glyph_svg)}</svg>\n'
    )
    idx = base_svg.rfind("</svg>")
    return base_svg[:idx] + nested + base_svg[idx:]


def build_variant_svg(variant: str, base_svg: str, win_dir: str,
                      small: bool = False) -> str:
    if variant == "plain":
        return base_svg
    if variant == "disabled":
        return gray_svg(base_svg)
    glyph_path = os.path.join(win_dir, GLYPH_SVGS[variant])
    with open(glyph_path, encoding="utf-8") as f:
        return overlay_glyph(base_svg, f.read(), small=small)


def plan(ico_names: List[str]) -> Dict[str, List[Tuple[str, Tuple[int, ...]]]]:
    """variant -> [(ico filename, sizes)], skipping the product icons."""
    result: Dict[str, List[Tuple[str, Tuple[int, ...]]]] = {}
    for name in sorted(ico_names):
        if name in SKIP:
            continue
        stem, multi = split_name(name)
        sizes = gen.SIZES if multi else SMALL_SIZES
        result.setdefault(variant_for(stem), []).append((name, sizes))
    return result


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=DEFAULT_DIR,
                        help=f"Directory of .ico files to regenerate in place (default: {DEFAULT_DIR})")
    parser.add_argument("--base-svg", default=DEFAULT_BASE_SVG,
                        help=f"mozc4med base icon design (default: {DEFAULT_BASE_SVG})")
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if not os.path.isfile(args.base_svg):
        print(f"error: base SVG not found: {args.base_svg}", file=sys.stderr)
        return 1
    ico_paths = sorted(glob.glob(os.path.join(args.dir, "*.ico")))
    if not ico_paths:
        print(f"error: no .ico files found in {args.dir}", file=sys.stderr)
        return 1
    with open(args.base_svg, encoding="utf-8") as f:
        base_svg = f.read()

    groups = plan([os.path.basename(p) for p in ico_paths])
    tmpdir = tempfile.mkdtemp(prefix="win_mode_icons_")
    try:
        for variant, targets in sorted(groups.items()):
            # One SVG per layout (small sizes fade the circles); plain and
            # disabled variants are identical in both.
            svg_paths: Dict[bool, str] = {}
            for small in (False, True):
                layout = "small" if small else "large"
                svg_path = os.path.join(tmpdir, f"{variant}_{layout}.svg")
                try:
                    svg_text = build_variant_svg(variant, base_svg, args.dir, small)
                except (OSError, ValueError) as e:
                    print(f"error: cannot build variant {variant!r}: {e}",
                          file=sys.stderr)
                    return 1
                with open(svg_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(svg_text)
                svg_paths[small] = svg_path

            rendered: Dict[int, str] = {}
            for size in sorted({s for _, sizes in targets for s in sizes}):
                png = os.path.join(tmpdir, f"{variant}_{size}.png")
                gen.render_png(svg_paths[size <= SMALL_MAX_SIZE], size, png)
                rendered[size] = png

            for name, sizes in targets:
                out = os.path.join(args.dir, name)
                gen.pack_ico([rendered[s] for s in sizes], out)
                print(f"[INFO] {name}: variant={variant} sizes={list(sizes)}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
