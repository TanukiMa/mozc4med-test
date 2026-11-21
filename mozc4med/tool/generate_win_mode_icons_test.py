#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mozc4med.tool import generate_icon_from_svg
from mozc4med.tool import generate_win_mode_icons as g

BASE_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024">\n'
    '  <circle cx="1" cy="1" r="1" fill="#006633"/>\n'
    '  <circle cx="2" cy="2" r="1" fill="#ff0000"/>\n'
    '</svg>\n'
)
GLYPH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none">'
    '<path fill="#fff" d="M0 0h1z"/><path stroke="#000" d="M0 0h2z"/></svg>'
)


class GenerateWinModeIconsTest(unittest.TestCase):
  """Pure-Python logic only; ImageMagick calls are stubbed out."""

  def test_split_name(self):
    self.assertEqual(g.split_name("ms_hiragana_a.ico"), ("ms_hiragana", True))
    self.assertEqual(g.split_name("ms_hiragana.ico"), ("ms_hiragana", False))
    self.assertEqual(g.split_name("tools_icon.ico"), ("tools_icon", False))

  def test_variant_for(self):
    self.assertEqual(g.variant_for("ms_katakana_half"), "ms_katakana_half")
    self.assertEqual(g.variant_for("ms_disabled"), "disabled")
    self.assertEqual(g.variant_for("tools_dictionary"), "plain")

  def test_plan_groups_by_variant_and_sizes_and_skips_product_icons(self):
    plan = g.plan([
        "ms_hiragana.ico", "ms_hiragana_a.ico", "ms_disabled.ico",
        "tools_icon_a.ico", "product_icon.ico", "product_icon_langbar.ico",
    ])
    self.assertEqual(sorted(plan), ["disabled", "ms_hiragana", "plain"])
    self.assertEqual(
        plan["ms_hiragana"],
        [("ms_hiragana.ico", (16,)),
         ("ms_hiragana_a.ico", generate_icon_from_svg.SIZES)])
    all_names = [n for targets in plan.values() for n, _ in targets]
    self.assertNotIn("product_icon.ico", all_names)
    self.assertNotIn("product_icon_langbar.ico", all_names)

  def test_every_glyph_variant_is_a_known_mode_stem(self):
    for stem in g.GLYPH_SVGS:
      self.assertEqual(g.variant_for(stem), stem)

  def test_gray_svg_removes_colors_and_keeps_structure(self):
    gray = g.gray_svg(BASE_SVG)
    self.assertNotIn("#006633", gray)
    self.assertNotIn("#ff0000", gray)
    self.assertEqual(gray.count("<circle"), 2)
    import re
    for hex6 in re.findall(r"#([0-9a-f]{6})", gray):
      self.assertEqual(hex6[0:2], hex6[2:4])
      self.assertEqual(hex6[2:4], hex6[4:6])

  def test_glyph_inner_adds_explicit_fill_only_where_missing(self):
    inner = g.glyph_inner(GLYPH_SVG)
    self.assertIn('<path fill="#fff" d="M0 0h1z"/>', inner)
    self.assertIn('<path fill="none" stroke="#000" d="M0 0h2z"/>', inner)

  def test_glyph_inner_without_svg_root_is_an_error(self):
    with self.assertRaises(ValueError):
      g.glyph_inner("<g/>")

  def test_overlay_large_keeps_circles_opaque_and_insets_glyph(self):
    out = g.overlay_glyph(BASE_SVG, GLYPH_SVG, small=False)
    self.assertNotIn("opacity", out)
    self.assertIn('x="102" y="102" width="820" height="820"', out)
    self.assertTrue(out.rstrip().endswith("</svg>"))
    # The glyph is drawn after (on top of) the circles.
    self.assertLess(out.rfind("<circle"), out.find('viewBox="0 0 16 16"'))

  def test_overlay_small_fades_circles_and_fills_icon(self):
    out = g.overlay_glyph(BASE_SVG, GLYPH_SVG, small=True)
    self.assertEqual(out.count(f'opacity="{g.SMALL_CIRCLE_OPACITY}"'), 2)
    self.assertIn('x="0" y="0" width="1024" height="1024"', out)

  def test_overlay_without_closing_tag_is_an_error(self):
    with self.assertRaises(ValueError):
      g.overlay_glyph("<svg>", GLYPH_SVG)

  def test_build_variant_svg_plain_and_disabled_ignore_layout(self):
    for small in (False, True):
      self.assertEqual(g.build_variant_svg("plain", BASE_SVG, ".", small), BASE_SVG)
      self.assertEqual(
          g.build_variant_svg("disabled", BASE_SVG, ".", small),
          g.gray_svg(BASE_SVG))

  def test_main_renders_each_variant_once_per_size_and_packs_every_ico(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      win = Path(temp_dir) / "win"
      win.mkdir()
      for name in ("ms_hiragana.ico", "ms_hiragana_a.ico", "tools_icon.ico"):
        (win / name).write_bytes(b"old")
      (win / "ms_hiragana.svg").write_text(GLYPH_SVG, encoding="utf-8")
      base = Path(temp_dir) / "icon.svg"
      base.write_text(BASE_SVG, encoding="utf-8")

      def fake_render(svg, size, out_png):
        Path(out_png).write_text(f"{Path(svg).name}:{size}", encoding="utf-8")

      with mock.patch.object(g.gen, "render_png", side_effect=fake_render) as render, \
           mock.patch.object(g.gen, "pack_ico") as pack:
        rc = g.main(["--dir", str(win), "--base-svg", str(base)])

      self.assertEqual(rc, 0)
      # ms_hiragana: 8 sizes (shared by the 16px-only and multi-size ico);
      # plain (tools_icon.ico only, 16px): 1 render.
      self.assertEqual(render.call_count, len(generate_icon_from_svg.SIZES) + 1)
      self.assertEqual(pack.call_count, 3)
      packed_outs = sorted(Path(c[0][1]).name for c in pack.call_args_list)
      self.assertEqual(
          packed_outs, ["ms_hiragana.ico", "ms_hiragana_a.ico", "tools_icon.ico"])

  def test_main_missing_glyph_svg_is_an_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      win = Path(temp_dir) / "win"
      win.mkdir()
      (win / "ms_hiragana.ico").write_bytes(b"old")
      base = Path(temp_dir) / "icon.svg"
      base.write_text(BASE_SVG, encoding="utf-8")

      with mock.patch.object(g.gen, "render_png"), \
           mock.patch.object(g.gen, "pack_ico"):
        rc = g.main(["--dir", str(win), "--base-svg", str(base)])

      self.assertEqual(rc, 1)

  def test_main_missing_base_svg_is_an_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      rc = g.main(["--dir", temp_dir, "--base-svg", str(Path(temp_dir) / "x.svg")])
      self.assertEqual(rc, 1)

  def test_main_no_ico_files_is_an_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      base = Path(temp_dir) / "icon.svg"
      base.write_text(BASE_SVG, encoding="utf-8")
      rc = g.main(["--dir", temp_dir, "--base-svg", str(base)])
      self.assertEqual(rc, 1)


if __name__ == "__main__":
  unittest.main()
