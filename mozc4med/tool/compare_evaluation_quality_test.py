#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from mozc4med.tool import compare_evaluation_quality


HEADER = "# status\tinput\toutput\tcommand\targument\tversion\n"


class CompareEvaluationQualityTest(unittest.TestCase):

  def _write(self, path: Path, text: str) -> Path:
    path.write_text(HEADER + text, encoding="utf-8")
    return path

  def test_dry_run_with_no_changes_is_clean_and_leaves_before_untouched(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      row = "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.0\n"
      before = self._write(temp_path / "before.tsv", row)
      after = self._write(temp_path / "after.tsv", row)

      rc = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(after),
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(before.read_text(encoding="utf-8"), HEADER + row)

  def test_regression_fails_even_with_apply(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      before = self._write(
          temp_path / "before.tsv", "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.0\n")
      after = self._write(
          temp_path / "after.tsv", "FAILED:\tかな\tカナ\tConversion Match\t仮名\t1.0.1\n")

      rc = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(after),
          "--apply",
      ])

      self.assertEqual(rc, 1)
      # A regression must never be synced into the baseline.
      self.assertIn("OK:", before.read_text(encoding="utf-8"))

  def test_improvement_only_passes_and_apply_syncs_before(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      before = self._write(
          temp_path / "before.tsv", "FAILED:\tかな\tカナ\tConversion Match\t仮名\t1.0.0\n")
      after_text = "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.1\n"
      after = self._write(temp_path / "after.tsv", after_text)

      rc = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(after),
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(before.read_text(encoding="utf-8"), HEADER + after_text)

  def test_ok_output_change_fails_by_default_but_allowed_with_flag(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      before = self._write(
          temp_path / "before.tsv", "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.0\n")
      after = self._write(
          temp_path / "after.tsv", "OK:\tかな\t哉那\tConversion Match\t仮名\t1.0.1\n")

      rc_default = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(after),
      ])
      self.assertEqual(rc_default, 1)

      rc_allowed = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(after),
          "--allow-output-change",
      ])
      self.assertEqual(rc_allowed, 0)

  def test_missing_after_file_returns_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      before = self._write(
          temp_path / "before.tsv", "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.0\n")

      rc = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(temp_path / "missing.tsv"),
      ])

      self.assertEqual(rc, 1)

  def test_quality_report_lists_only_changed_identities(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      before = self._write(
          temp_path / "before.tsv",
          "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.0\n"
          "OK:\tあい\t愛\tConversion Match\t愛\t1.0.0\n",
      )
      after = self._write(
          temp_path / "after.tsv",
          "OK:\tかな\t仮名\tConversion Match\t仮名\t1.0.1\n"
          "FAILED:\tあい\t哀\tConversion Match\t愛\t1.0.1\n",
      )
      report = temp_path / "report.tsv"

      rc = compare_evaluation_quality.main([
          "--before", str(before),
          "--after", str(after),
          "--quality-report", str(report),
      ])

      self.assertEqual(rc, 1)
      report_lines = report.read_text(encoding="utf-8").splitlines()
      # Header + exactly one changed row (the unchanged "かな" identity is
      # intentionally excluded from the report).
      self.assertEqual(len(report_lines), 2)
      self.assertTrue(report_lines[1].startswith("regression\tあい\t"))


if __name__ == "__main__":
  unittest.main()
