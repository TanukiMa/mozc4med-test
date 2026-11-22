#!/usr/bin/env python3

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


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

  def test_windows_clang_version_patch(self):
    git = shutil.which("git")
    if not git:
      self.skipTest("git is required for patch-application coverage")

    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir)
      for relative_path in (
          "mozc4med/windows/0010_windows_clang_version_detection.patch",
          "src/bazel/rules_cc_windows_cc_configure.bzl.patch",
      ):
        _copy_into_tempdir(temp_path, relative_path)
      outer_patch = "mozc4med/windows/0010_windows_clang_version_detection.patch"
      subprocess.run([git, "apply", "--check", outer_patch], cwd=temp_path, check=True)
      subprocess.run([git, "apply", outer_patch], cwd=temp_path, check=True)

      source = temp_path / "cc/private/toolchain/windows_cc_configure.bzl"
      source.parent.mkdir(parents=True)
      source.write_text('''\
def _get_clang_version(repository_ctx, clang_cl):
    result = repository_ctx.execute([clang_cl, "-v"])
    first_line = result.stderr.strip().splitlines()[0].strip()

    # The first line of stderr should look like "[vendor ]clang version X.X.X"
    if result.return_code != 0 or first_line.find("clang version ") == -1:
        auto_configure_fail("Failed to get clang version by running \\"%s -v\\"" % clang_cl)
    return first_line.split(" ")[-1]

def _get_clang_dir(repository_ctx, llvm_path, clang_version):
    """Get the clang installation directory."""

def configure_windows_toolchain(repository_ctx):

    template_vars = dict()
    msvc_vars_x64 = _get_msvc_vars(repository_ctx, paths, "x64")
    template_vars.update(msvc_vars_x64)
    template_vars.update(_get_clang_cl_vars(repository_ctx, paths, msvc_vars_x64, "x64"))
    template_vars.update(_get_msys_mingw_vars(repository_ctx))
    template_vars.update(_get_copts(repository_ctx))
    template_vars.update(_get_msvc_vars(repository_ctx, paths, "x86", msvc_vars_x64))
    template_vars.update(_get_msvc_vars(repository_ctx, paths, "arm", msvc_vars_x64))
    msvc_vars_arm64 = _get_msvc_vars(repository_ctx, paths, "arm64", msvc_vars_x64)
    template_vars.update(msvc_vars_arm64)
''', encoding="utf-8")
      inner_patch = "src/bazel/rules_cc_windows_cc_configure.bzl.patch"
      subprocess.run([git, "apply", "-p0", "--check", inner_patch], cwd=temp_path, check=True)
      subprocess.run([git, "apply", "-p0", inner_patch], cwd=temp_path, check=True)

      def fail(message):
        raise ValueError(message)

      namespace = {"auto_configure_fail": fail}
      version_function = source.read_text(encoding="utf-8").split("def _get_clang_dir")[0]
      exec(version_function, namespace)
      get_version = namespace["_get_clang_version"]
      for output, expected in (
          ("clang version 20.1.1", "20.1.1"),
          ("clang version 23.1.6 (https://github.com/llvm/llvm-project abc123)", "23.1.6"),
          ("vendor clang version 23.1.6 (vendor build)", "23.1.6"),
      ):
        with self.subTest(output=output):
          ctx = SimpleNamespace(execute=lambda args: SimpleNamespace(stderr=output, return_code=0))
          self.assertEqual(get_version(ctx, "clang-cl.exe"), expected)
      ctx = SimpleNamespace(execute=lambda args: SimpleNamespace(stderr="unknown compiler", return_code=0))
      with self.assertRaises(ValueError):
        get_version(ctx, "clang-cl.exe")
      ctx = SimpleNamespace(execute=lambda args: SimpleNamespace(stderr="clang version 23.1.6", return_code=1))
      with self.assertRaises(ValueError):
        get_version(ctx, "clang-cl.exe")

  def test_common_dictionary_patch_wires_raw_mozc4med_tsv_once(self):
    git = shutil.which("git")
    python = sys.executable
    if not git or not python:
      self.skipTest("git and Python are required for patch-application coverage")

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

      subprocess.run([git, "init"], cwd=temp_path, check=True)
      subprocess.run([git, "checkout", "-b", "dev"], cwd=temp_path, check=True)
      subprocess.run([git, "add", "."], cwd=temp_path, check=True)
      subprocess.run(
          [
              git,
              "-c",
              "user.name=Test User",
              "-c",
              "user.email=test@example.com",
              "commit",
              "-m",
              "Initial commit",
          ],
          cwd=temp_path,
          check=True,
          stdout=subprocess.DEVNULL,
          stderr=subprocess.DEVNULL,
      )
      subprocess.run(
          [python, "mozc4med/tool/validate_and_apply_patches.py",
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
