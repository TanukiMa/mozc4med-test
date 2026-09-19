#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path

from mozc4med.tool import generate_mozc4med_dictionary


class GenerateMozc4medDictionaryTest(unittest.TestCase):

  def test_main_omits_sixth_column_and_preserves_first_five(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      input_path = temp_path / "input.csv"
      output_path = temp_path / "mozc4med.tsv"
      input_path.write_text(
          "#読み,品詞1,品詞2,コスト,単語,付随情報\n"
          "べーちぇっとびょう,10,20,3000,ベーチェット病,=ベーチェット病\n"
          "あい,1,2,3,藍,\n",
          encoding="utf-8",
      )

      rc = generate_mozc4med_dictionary.main([
          "--input",
          str(input_path),
          "--output",
          str(output_path),
      ])

      self.assertEqual(rc, 0)
      lines = output_path.read_text(encoding="utf-8").splitlines()
      self.assertEqual(lines, [
          "あい\t1\t2\t3\t藍",
          "べーちぇっとびょう\t10\t20\t3000\tベーチェット病",
      ])
      for line in lines:
        self.assertEqual(len(line.split("\t")), 5)

  def test_main_keeps_five_column_input_and_dedupes_by_first_five_columns(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      first_input_path = temp_path / "a.csv"
      second_input_path = temp_path / "b.csv"
      output_path = temp_path / "mozc4med.tsv"
      first_input_path.write_text(
          "#読み,品詞1,品詞2,コスト,単語\n"
          "かな,7,8,9,仮名\n",
          encoding="utf-8",
      )
      second_input_path.write_text(
          "#読み,品詞1,品詞2,コスト,単語,付随情報\n"
          "かな,7,8,9,仮名,重複メモ\n",
          encoding="utf-8",
      )

      rc = generate_mozc4med_dictionary.main([
          "--input",
          str(temp_path / "*.csv"),
          "--output",
          str(output_path),
      ])

      self.assertEqual(rc, 0)
      self.assertEqual(
          output_path.read_text(encoding="utf-8").splitlines(),
          ["かな\t7\t8\t9\t仮名"],
      )


if __name__ == "__main__":
  unittest.main()
