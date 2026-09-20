#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from mozc4med.tool import rm_dictionary_entries


class RmDictionaryEntriesTest(unittest.TestCase):

  def _write_fixture(self, temp_path: Path, mozc4med_text: str, dict_text: str):
    mozc4med_path = temp_path / "mozc4med.tsv"
    dict_dir = temp_path / "dictionary_oss"
    dict_dir.mkdir()
    dict_path = dict_dir / "dictionary00.txt"
    mozc4med_path.write_text(mozc4med_text, encoding="utf-8")
    dict_path.write_text(dict_text, encoding="utf-8")
    return mozc4med_path, dict_dir, dict_path

  def test_dry_run_reports_matches_but_leaves_files_untouched(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      original = "かな\t7\t8\t9\t仮名\n" "あい\t1\t2\t3\t愛\n"
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          Path(temp_dir), "かな\t7\t8\t9\t仮名\n", original)

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(dict_path.read_text(encoding="utf-8"), original)

  def test_apply_removes_only_matching_reading_word_pairs(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          Path(temp_dir),
          "かな\t7\t8\t9\t仮名\n",
          "かな\t7\t8\t9\t仮名\n" "あい\t1\t2\t3\t愛\n",
      )

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          dict_path.read_text(encoding="utf-8").splitlines(),
          ["あい\t1\t2\t3\t愛"],
      )

  def test_apply_ignores_lid_rid_cost_when_matching(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          Path(temp_dir),
          "かな\t1\t1\t1\t仮名\n",
          "かな\t99\t99\t9999\t仮名\n",
      )

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
          "--apply",
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(dict_path.read_text(encoding="utf-8"), "")

  def test_missing_mozc4med_file_returns_error(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      dict_dir = temp_path / "dictionary_oss"
      dict_dir.mkdir()
      (dict_dir / "dictionary00.txt").write_text("かな\t1\t1\t1\t仮名\n", encoding="utf-8")

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(temp_path / "missing.tsv"),
          "--dict-dir", str(dict_dir),
      ])

      self.assertEqual(rc, 1)

  def test_removed_report_lists_every_removed_entry(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          temp_path,
          "かな\t7\t8\t9\t仮名\n",
          "かな\t7\t8\t9\t仮名\n" "あい\t1\t2\t3\t愛\n",
      )
      report_path = temp_path / "removed.tsv"

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
          "--apply",
          "--removed-report", str(report_path),
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          report_path.read_text(encoding="utf-8").splitlines(),
          [
              "dict_file\tline\treading\tlid\trid\tcost\tword",
              "dictionary00.txt\t1\tかな\t7\t8\t9\t仮名",
          ],
      )

  def test_removed_report_is_written_even_in_dry_run(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          temp_path, "かな\t7\t8\t9\t仮名\n", "かな\t7\t8\t9\t仮名\n")
      report_path = temp_path / "removed.tsv"

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
          "--removed-report", str(report_path),
      ])

      self.assertEqual(rc, 0)
      # dry-run: dictionary file itself is untouched...
      self.assertEqual(dict_path.read_text(encoding="utf-8"), "かな\t7\t8\t9\t仮名\n")
      # ...but the report still previews what would be removed.
      self.assertIn("かな", report_path.read_text(encoding="utf-8"))

  def test_step_summary_appends_markdown_table_with_removed_entries(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          temp_path,
          "かな\t7\t8\t9\t仮名\n",
          "かな\t7\t8\t9\t仮名\n" "あい\t1\t2\t3\t愛\n",
      )
      summary_path = temp_path / "step_summary.md"
      summary_path.write_text("### earlier step\n\n", encoding="utf-8")

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
          "--apply",
          "--step-summary", str(summary_path),
      ])

      self.assertEqual(rc, 0)
      content = summary_path.read_text(encoding="utf-8")
      self.assertIn("earlier step", content)  # existing content preserved (append mode)
      self.assertIn("dictionary00.txt", content)
      self.assertIn("かな", content)
      self.assertIn("仮名", content)
      self.assertIn("Total removed: 1", content)

  def test_step_summary_reports_zero_when_nothing_removed(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      mozc4med_path, dict_dir, dict_path = self._write_fixture(
          temp_path, "かな\t7\t8\t9\t仮名\n", "あい\t1\t2\t3\t愛\n")
      summary_path = temp_path / "step_summary.md"

      rc = rm_dictionary_entries.main([
          "--mozc4med", str(mozc4med_path),
          "--dict-dir", str(dict_dir),
          "--apply",
          "--step-summary", str(summary_path),
      ])

      self.assertEqual(rc, 0)
      self.assertIn("Total removed: 0", summary_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
  unittest.main()
