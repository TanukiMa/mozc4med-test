#!/usr/bin/env python3
"""Regenerate the Windows mode/tool .ico files from SVG sources.

Per file under src/data/images/win/:

  * ms_hiragana / ms_katakana / ms_katakana_half / ms_alpha / ms_alpha_half /
    ms_direct_input (+ their `_a` variants): the upstream mode glyph
    (ms_<mode>.svg next to the .ico files) on its own -- a white glyph with a
    solid black outline on a transparent background. These are NOT drawn over
    the mozc4med icon: the language bar can sit on any color, so the glyph has
    to be readable by itself (white fill + black border works on light and
    dark bars alike). Only the glyph's white shape is taken from upstream; the
    black border is synthesized by dilating that shape by a whole number of
    pixels (>= 1) at every size, instead of rasterizing upstream's hairline
    (0.4px at 16px, 75% black) outline, which blurs to gray at 16-24px.
  * ms_disabled / ms_disabled_a: the mozc4med icon (mozc4med/assets/icon.svg)
    in grayscale.
  * everything else (tools_*.ico): the plain mozc4med icon. Upstream has no
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
from typing import Dict, List, Tuple

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

# Upstream glyph SVGs are 16x16 with no viewBox; the silhouette is rescaled to
# this size so ImageMagick rasterizes it at high resolution before downsizing.
RENDER_SIZE = 1024
GLYPH_VIEWBOX = "0 0 16 16"
# Border thickness in pixels = max(1, round(size * BORDER_RATIO)): 1px up to
# 79px icons, 2px at 128px, 3px at 256px.
BORDER_RATIO = 0.0125

_HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
_NON_DRAWING = re.compile(r"<(mask|defs)\b.*?</\1>", re.DOTALL)
_PATH = re.compile(r"<path\b[^>]*/>")
_WHITE_FILL = re.compile(r'\bfill="#fff(?:fff)?"', re.IGNORECASE)


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


def glyph_silhouette_svg(glyph_svg: str) -> str:
    """The glyph's white shape only, scaled up to RENDER_SIZE.

    Upstream glyph SVGs draw one white <path> (the glyph) plus a black outline
    <path>, and carry <mask>/<defs> helper shapes that include white paths of
    their own (a clip square, a mask); only the drawn white glyph path is
    kept.
    """
    if "<svg" not in glyph_svg or "</svg>" not in glyph_svg:
        raise ValueError("glyph SVG has no <svg> root")
    drawn = _NON_DRAWING.sub("", glyph_svg)
    paths = [p for p in _PATH.findall(drawn) if _WHITE_FILL.search(p)]
    if len(paths) != 1:
        raise ValueError(
            f"expected exactly one white glyph path, found {len(paths)}")
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{RENDER_SIZE}" '
        f'height="{RENDER_SIZE}" viewBox="{GLYPH_VIEWBOX}" fill="none">'
        f"{paths[0]}</svg>\n"
    )


def border_px(size: int) -> int:
    return max(1, round(size * BORDER_RATIO))


def render_glyph_png(svg: str, size: int, out_png: str) -> None:
    """White glyph with a black border of whole pixels, on transparency.

    The silhouette is drawn `border` px smaller than the icon on every side,
    then a copy dilated by `border` px and painted black is placed underneath.
    """
    border = border_px(size)
    inner = size - 2 * border
    gen.run([
        "magick",
        "-background", "none",
        "-density", str(gen.DENSITY),
        svg,
        "-resize", f"{inner}x{inner}",
        "-alpha", "on",
        "-gravity", "center",
        "-extent", f"{size}x{size}",
        "(", "+clone",
        "-morphology", "Dilate", f"Disk:{border + 0.5}",
        "-channel", "RGB", "-evaluate", "set", "0", "+channel",
        ")",
        "+swap", "-composite",
        "-depth", "8",
        out_png,
    ])


def build_variant_svg(variant: str, base_svg: str, win_dir: str) -> str:
    if variant == "plain":
        return base_svg
    if variant == "disabled":
        return gray_svg(base_svg)
    glyph_path = os.path.join(win_dir, GLYPH_SVGS[variant])
    with open(glyph_path, encoding="utf-8") as f:
        return glyph_silhouette_svg(f.read())


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
            svg_path = os.path.join(tmpdir, f"{variant}.svg")
            try:
                svg_text = build_variant_svg(variant, base_svg, args.dir)
            except (OSError, ValueError) as e:
                print(f"error: cannot build variant {variant!r}: {e}", file=sys.stderr)
                return 1
            with open(svg_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(svg_text)

            render = render_glyph_png if variant in GLYPH_SVGS else gen.render_png
            rendered: Dict[int, str] = {}
            for size in sorted({s for _, sizes in targets for s in sizes}):
                png = os.path.join(tmpdir, f"{variant}_{size}.png")
                render(svg_path, size, png)
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
