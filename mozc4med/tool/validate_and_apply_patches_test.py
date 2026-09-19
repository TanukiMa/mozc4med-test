#!/usr/bin/env python3

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PATCH_PATH = REPO_ROOT / "mozc4med/common/0005_dictionary_oss_mozc4med_tsv.patch"


def _copy_into_tempdir(tempdir: Path, relative_path: str) -> None:
  source = REPO_ROOT / relative_path
  destination = tempdir / relative_path
  destination.parent.mkdir(parents=True, exist_ok=True)
  shutil.copy2(source, destination)


def _extract_named_rule(build_text: str, rule_name: str) -> str:
  lines = build_text.splitlines()
  start = None
  for index, line in enumerate(lines):
    if f'name = "{rule_name}",' not in line:
      continue
    for candidate in range(index, -1, -1):
      if lines[candidate].endswith("("):
        start = candidate
        break
    if start is not None:
      break

  if start is None:
    raise AssertionError(f'Could not find rule named "{rule_name}"')

  depth = 0
  block = []
  for line in lines[start:]:
    block.append(line)
    depth += line.count("(") - line.count(")")
    if depth == 0:
      return "\n".join(block)

  raise AssertionError(f'Could not extract complete rule named "{rule_name}"')


class ValidateAndApplyPatchesTest(unittest.TestCase):

  def test_common_dictionary_patch_wires_raw_mozc4med_tsv_once(self):
    patch_text = PATCH_PATH.read_text(encoding="utf-8")
    self.assertIn(
        "Touch-Files: src/data/dictionary_manual/BUILD.bazel, "
        "src/data/dictionary_oss/BUILD.bazel",
        patch_text,
    )

    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      for relative_path in (
          "mozc4med/tool/validate_and_apply_patches.py",
          "mozc4med/common/0005_dictionary_oss_mozc4med_tsv.patch",
          "src/data/dictionary_manual/BUILD.bazel",
          "src/data/dictionary_oss/BUILD.bazel",
      ):
        _copy_into_tempdir(temp_path, relative_path)

      subprocess.run(["git", "init"], cwd=temp_path, check=True)
      subprocess.run(
          ["python3", "mozc4med/tool/validate_and_apply_patches.py",
           "mozc4med/common"],
          cwd=temp_path,
          check=True,
      )

      manual_build = (temp_path / "src/data/dictionary_manual/BUILD.bazel"
                     ).read_text(encoding="utf-8")
      self.assertIn('"mozc4med.tsv"', manual_build)
      dictionary_manual = _extract_named_rule(manual_build, "dictionary_manual")
      self.assertNotIn("mozc4med.tsv", dictionary_manual)

      oss_build = (temp_path / "src/data/dictionary_oss/BUILD.bazel"
                  ).read_text(encoding="utf-8")
      base_dictionary_data = _extract_named_rule(oss_build, "base_dictionary_data")
      self.assertEqual(
          base_dictionary_data.count('"//data/dictionary_manual:mozc4med.tsv"'),
          1,
      )


if __name__ == "__main__":
  unittest.main()
