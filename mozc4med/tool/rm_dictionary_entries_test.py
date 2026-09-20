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


if __name__ == "__main__":
  unittest.main()
