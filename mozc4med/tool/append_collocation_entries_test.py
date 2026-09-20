#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from mozc4med.tool import append_collocation_entries


class AppendCollocationEntriesTest(unittest.TestCase):

  def test_apply_appends_new_lines_and_skips_existing_ones(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "collocation.csv"
      target_path = temp_path / "collocation.txt"
      input_path.write_text(
          "#表現\n"
          "きりがない\n"  # already present in target
          "一緒にいたい\n",  # new
          encoding="utf-8",
      )
      target_path.write_text("きりがない\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(target_path),
          "--columns", "1",
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          target_path.read_text(encoding="utf-8").splitlines(),
          ["きりがない", "一緒にいたい"],
      )

  def test_dry_run_leaves_target_untouched(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "collocation.csv"
      target_path = temp_path / "collocation.txt"
      input_path.write_text("#表現\n一緒にいたい\n", encoding="utf-8")
      target_path.write_text("きりがない\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(target_path),
          "--columns", "1",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(target_path.read_text(encoding="utf-8"), "きりがない\n")

  def test_two_column_suppression_format(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "suppression.csv"
      target_path = temp_path / "collocation_suppression.txt"
      input_path.write_text("#語1,語2\n重複,表現\n", encoding="utf-8")
      target_path.write_text("__DUMMY__\t__DUMMY__\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(target_path),
          "--columns", "2",
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          target_path.read_text(encoding="utf-8").splitlines(),
          ["__DUMMY__\t__DUMMY__", "重複\t表現"],
      )

  def test_trailing_note_column_is_ignored_and_deduped_by_data_columns(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "collocation.csv"
      target_path = temp_path / "collocation.txt"
      input_path.write_text(
          "#表現,付随情報\n" "一緒にいたい,メモ\n", encoding="utf-8")
      target_path.write_text("一緒にいたい\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(target_path),
          "--columns", "1",
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(target_path.read_text(encoding="utf-8"), "一緒にいたい\n")

  def test_missing_input_is_soft_no_op_by_default(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      target_path = temp_path / "collocation.txt"
      target_path.write_text("きりがない\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(temp_path / "no_such_dir" / "*.csv"),
          "--target", str(target_path),
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(target_path.read_text(encoding="utf-8"), "きりがない\n")

  def test_missing_input_fails_when_required(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      target_path = temp_path / "collocation.txt"
      target_path.write_text("きりがない\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(temp_path / "no_such_dir" / "*.csv"),
          "--target", str(target_path),
          "--apply",
          "--required",
      ])

      self.assertEqual(rc, 1)

  def test_missing_target_file_returns_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "collocation.csv"
      input_path.write_text("#表現\n一緒にいたい\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(temp_path / "missing.txt"),
          "--apply",
      ])

      self.assertEqual(rc, 1)

  def test_appends_newline_when_target_is_missing_trailing_newline(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "collocation.csv"
      target_path = temp_path / "collocation.txt"
      input_path.write_text("#表現\n一緒にいたい\n", encoding="utf-8")
      # No trailing newline after the existing line.
      target_path.write_bytes("きりがない".encode("utf-8"))

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(target_path),
          "--columns", "1",
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          target_path.read_text(encoding="utf-8").splitlines(),
          ["きりがない", "一緒にいたい"],
      )

  def test_added_report_and_step_summary_are_written(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "collocation.csv"
      target_path = temp_path / "collocation.txt"
      report_path = temp_path / "added.tsv"
      summary_path = temp_path / "step_summary.md"
      input_path.write_text("#表現\n一緒にいたい\n", encoding="utf-8")
      target_path.write_text("きりがない\n", encoding="utf-8")

      rc = append_collocation_entries.main([
          "--input", str(input_path),
          "--target", str(target_path),
          "--columns", "1",
          "--apply",
          "--added-report", str(report_path),
          "--step-summary", str(summary_path),
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          report_path.read_text(encoding="utf-8").splitlines(),
          [
              "source_csv\ttarget_file\tcol1",
              "collocation.csv\tcollocation.txt\t一緒にいたい",
          ],
      )
      summary = summary_path.read_text(encoding="utf-8")
      self.assertIn("一緒にいたい", summary)
      self.assertIn("Total appended: 1", summary)


if __name__ == "__main__":
  unittest.main()
