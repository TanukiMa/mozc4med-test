#!/usr/bin/env python3

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mozc4med.tool import generate_icon_from_svg


class GenerateIconFromSvgTest(unittest.TestCase):
  """Covers the pure-Python argument validation and --png-out copy logic.

  Does not exercise render_png()/pack_ico()/the final `magick identify`
  call themselves (they shell out to ImageMagick); those are stubbed out,
  matching this repo's convention of not unit-testing the ImageMagick-
  dependent tools' actual image processing (see colorize_icons.py and
  hue_shift_svg.py, which have no test files at all).
  """

  def _fake_render_png(self, svg, size, out_png):
    # Write a small marker instead of actually invoking ImageMagick, so the
    # --png-out copy logic can be verified against known content.
    with open(out_png, "w", encoding="utf-8") as f:
      f.write(f"fake-png-{size}")

  def test_png_out_without_png_size_is_an_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      svg = Path(temp_dir) / "icon.svg"
      svg.write_text("<svg/>", encoding="utf-8")

      rc = generate_icon_from_svg.main([
          "--svg", str(svg),
          "--out", str(Path(temp_dir) / "out.ico"),
          "--png-out", str(Path(temp_dir) / "out.png"),
      ])

      self.assertEqual(rc, 1)

  def test_png_size_not_in_sizes_is_an_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      svg = Path(temp_dir) / "icon.svg"
      svg.write_text("<svg/>", encoding="utf-8")

      rc = generate_icon_from_svg.main([
          "--svg", str(svg),
          "--out", str(Path(temp_dir) / "out.ico"),
          "--png-out", str(Path(temp_dir) / "out.png"),
          "--png-size", "999",
      ])

      self.assertEqual(rc, 1)

  def test_png_out_copies_the_matching_size_render(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      svg = Path(temp_dir) / "icon.svg"
      svg.write_text("<svg/>", encoding="utf-8")
      out_ico = Path(temp_dir) / "win" / "product_icon.ico"
      png_out = Path(temp_dir) / "product_icon_32bpp-128.png"

      with mock.patch.object(
          generate_icon_from_svg, "render_png", side_effect=self._fake_render_png
      ) as mock_render, mock.patch.object(
          generate_icon_from_svg, "pack_ico"
      ) as mock_pack, mock.patch.object(
          generate_icon_from_svg, "run"
      ) as mock_run:
        rc = generate_icon_from_svg.main([
            "--svg", str(svg),
            "--out", str(out_ico),
            "--png-out", str(png_out),
            "--png-size", "128",
        ])

      self.assertEqual(rc, 0)
      # render_png was called once per SIZES entry.
      self.assertEqual(mock_render.call_count, len(generate_icon_from_svg.SIZES))
      # pack_ico received one PNG per SIZES entry, in order.
      packed_pngs = mock_pack.call_args[0][0]
      self.assertEqual(len(packed_pngs), len(generate_icon_from_svg.SIZES))
      # --png-out was written from the 128px render, not just touched empty.
      self.assertEqual(png_out.read_text(encoding="utf-8"), "fake-png-128")
      mock_run.assert_called_once()

  def test_without_png_out_no_extra_file_is_written(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      svg = Path(temp_dir) / "icon.svg"
      svg.write_text("<svg/>", encoding="utf-8")
      out_ico = Path(temp_dir) / "out.ico"

      with mock.patch.object(
          generate_icon_from_svg, "render_png", side_effect=self._fake_render_png
      ), mock.patch.object(
          generate_icon_from_svg, "pack_ico"
      ), mock.patch.object(
          generate_icon_from_svg, "run"
      ):
        rc = generate_icon_from_svg.main([
            "--svg", str(svg),
            "--out", str(out_ico),
        ])

      self.assertEqual(rc, 0)
      # Nothing besides --out (mocked away) and the svg fixture should exist.
      self.assertEqual(sorted(os.listdir(temp_dir)), ["icon.svg"])

  def test_missing_svg_returns_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      rc = generate_icon_from_svg.main([
          "--svg", str(Path(temp_dir) / "missing.svg"),
          "--out", str(Path(temp_dir) / "out.ico"),
      ])

      self.assertEqual(rc, 1)


if __name__ == "__main__":
  unittest.main()
