#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from mozc4med.tool import check_no_upstream_identifiers as checker


class CheckNoUpstreamIdentifiersTest(unittest.TestCase):

  def test_clean_binary_passes(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "mozc_tip64.dll"
      path.write_bytes("Mozc4medCandidateWindow".encode("utf-16le"))

      rc = checker.main([str(path)])

      self.assertEqual(rc, 0)

  def test_upstream_registry_key_text_hard_fails(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "mozc_tip64.dll"
      # Embedded as UTF-16LE, matching how a wchar_t[] literal is stored.
      path.write_bytes("Software\\Mozc Project\\Mozc".encode("utf-16le"))

      rc = checker.main([str(path)])

      self.assertEqual(rc, 1)

  def test_old_guid_struct_bytes_hard_fail(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "mozc_tip64.dll"
      old_guid = checker.OLD_GUIDS[0]
      # Pad around the marker the way a real binary would.
      path.write_bytes(b"\x00" * 16 + old_guid.le_bytes + b"\x00" * 16)

      rc = checker.main([str(path)])

      self.assertEqual(rc, 1)

  def test_old_guid_hex_text_hard_fails(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "mozc_tip64.dll"
      old_guid = checker.OLD_GUIDS[0]
      path.write_bytes(f"// {{{old_guid.hex_text}}}".encode("ascii"))

      rc = checker.main([str(path)])

      self.assertEqual(rc, 1)

  def test_report_only_marker_does_not_fail(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "mozc_broker.exe"
      path.write_bytes("mozc_server.exe".encode("ascii"))

      rc = checker.main([str(path)])

      self.assertEqual(rc, 0)

  def test_new_isolated_value_does_not_collide_with_old_marker(self):
    # Regression guard for the checker itself: the post-isolation values
    # must not be accidental substrings of any HARD_DENY marker (this is
    # what mozc4med/common/0001_brand_isolation.patch actually produces).
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "mozc_tip64.dll"
      isolated_values = "\n".join([
          "Local\\Mozc4med.event.",
          "Local\\Mozc4med.mutex.",
          "mozc4med.renderer.message",
          "mozc4med.renderer.window",
          "Mozc4medCandidateWindow",
          "Mozc4medCompositionWindow",
          "Mozc4medIndicatorWindow",
          "Mozc4medInfolistWindow",
          "Mozc4medUIWindow",
          "\\\\.\\pipe\\mozc4med.",
          "Mozc4medCandidateUI",
          "Mozc4med Configuration",
          "Software\\MATANUKI\\Mozc4med",
          "Software\\Policies\\MATANUKI\\Mozc4med\\Preferences",
      ])
      path.write_bytes(isolated_values.encode("utf-16le"))

      rc = checker.main([str(path)])

      self.assertEqual(rc, 0)

  def test_report_and_step_summary_are_written(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      path = temp_path / "mozc_tip64.dll"
      path.write_bytes("Mozc Configuration".encode("utf-16le"))
      report = temp_path / "report.tsv"
      summary = temp_path / "summary.md"

      rc = checker.main([
          str(path),
          "--report", str(report),
          "--step-summary", str(summary),
      ])

      self.assertEqual(rc, 1)
      self.assertIn("HARD_DENY", report.read_text(encoding="utf-8"))
      self.assertIn("upstream identifier collision", summary.read_text(encoding="utf-8"))

  def test_no_targets_found_is_not_an_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      rc = checker.main(["--root", str(Path(temp_dir) / "does-not-exist")])

      self.assertEqual(rc, 0)


if __name__ == "__main__":
  unittest.main()
