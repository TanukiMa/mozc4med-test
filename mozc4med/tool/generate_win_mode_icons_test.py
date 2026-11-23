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
# Mirrors the structure of upstream ms_hiragana.svg: a clip square and a mask
# (both with white paths of their own), the drawn white glyph, and the outline.
GLYPH_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none">'
    '<g clip-path="url(#a)">'
    '<mask id="b" width="13" height="13" fill="#000"><path fill="#fff" d="M0 0h13v13H0z"/></mask>'
    '<path fill="#fff" fill-rule="evenodd" d="M1 1h2z" clip-rule="evenodd"/>'
    '<path fill="#000" fill-opacity=".75" d="M0 0h2z" mask="url(#b)"/>'
    '</g>'
    '<defs><clipPath id="a"><path fill="#fff" d="M0 0h16v16H0z"/></clipPath></defs></svg>'
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

  def test_glyph_silhouette_keeps_only_the_drawn_white_glyph_path(self):
    out = g.glyph_silhouette_svg(GLYPH_SVG)
    self.assertEqual(out.count("<path"), 1)
    self.assertIn('d="M1 1h2z"', out)
    # Not the clip square / mask paths, and not the black outline.
    self.assertNotIn("M0 0h13v13H0z", out)
    self.assertNotIn("M0 0h16v16H0z", out)
    self.assertNotIn("#000", out)
    self.assertNotIn("opacity", out)

  def test_glyph_silhouette_is_rescaled_and_has_no_base_design(self):
    out = g.glyph_silhouette_svg(GLYPH_SVG)
    self.assertIn(f'width="{g.RENDER_SIZE}" height="{g.RENDER_SIZE}"', out)
    self.assertIn('viewBox="0 0 16 16"', out)
    self.assertNotIn("<circle", out)
    self.assertEqual(out.count("<svg"), 1)
    self.assertTrue(out.rstrip().endswith("</svg>"))

  def test_glyph_silhouette_without_svg_root_is_an_error(self):
    with self.assertRaises(ValueError):
      g.glyph_silhouette_svg("<g/>")

  def test_glyph_silhouette_without_exactly_one_white_path_is_an_error(self):
    with self.assertRaises(ValueError):
      g.glyph_silhouette_svg('<svg><path fill="#000" d="M0 0z"/></svg>')
    with self.assertRaises(ValueError):
      g.glyph_silhouette_svg(
          '<svg><path fill="#fff" d="M0 0z"/><path fill="#fff" d="M1 1z"/></svg>')

  def test_border_px_is_at_least_one_and_grows_with_size(self):
    self.assertEqual([g.border_px(s) for s in (16, 24, 32, 48, 64)], [1] * 5)
    self.assertEqual(g.border_px(128), 2)
    self.assertEqual(g.border_px(256), 3)

  def test_render_glyph_png_draws_glyph_inset_by_the_border(self):
    with mock.patch.object(g.gen, "run") as run:
      g.render_glyph_png("in.svg", 16, "out.png")
    cmd = run.call_args[0][0]
    self.assertEqual(cmd[cmd.index("-resize") + 1], "14x14")  # 16 - 2*1px
    self.assertEqual(cmd[cmd.index("-extent") + 1], "16x16")
    self.assertIn("Dilate", cmd)
    self.assertEqual(cmd[cmd.index("Dilate") + 1], "Disk:1.5")
    self.assertEqual(cmd[-1], "out.png")

  def test_build_variant_svg_glyph_does_not_use_base_design(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      (Path(temp_dir) / "ms_hiragana.svg").write_text(GLYPH_SVG, encoding="utf-8")
      out = g.build_variant_svg("ms_hiragana", BASE_SVG, temp_dir)
    self.assertNotIn("<circle", out)
    self.assertNotIn("#006633", out)

  def test_build_variant_svg_plain_and_disabled(self):
    self.assertEqual(g.build_variant_svg("plain", BASE_SVG, "."), BASE_SVG)
    self.assertEqual(
        g.build_variant_svg("disabled", BASE_SVG, "."), g.gray_svg(BASE_SVG))

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
           mock.patch.object(g, "render_glyph_png", side_effect=fake_render) as glyph, \
           mock.patch.object(g.gen, "pack_ico") as pack:
        rc = g.main(["--dir", str(win), "--base-svg", str(base)])

      self.assertEqual(rc, 0)
      # ms_hiragana (glyph renderer): 8 sizes shared by the 16px-only and
      # multi-size ico; plain (tools_icon.ico only, 16px): 1 plain render.
      self.assertEqual(glyph.call_count, len(generate_icon_from_svg.SIZES))
      self.assertEqual(render.call_count, 1)
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
           mock.patch.object(g, "render_glyph_png"), \
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
