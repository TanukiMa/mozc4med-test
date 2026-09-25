#!/usr/bin/env python3
"""Compare two dictionary_oss evaluation.tsv snapshots and gate on regressions.

src/data/dictionary_oss/BUILD.bazel's `evaluation_diff_test` fails with a raw
byte-diff whenever the Bazel-generated evaluation.tsv no longer matches the
checked-in baseline. That is exactly what happens once mozc4med's own Track C
tools (rm_dictionary_entries.py, append_collocation_entries.py) edit the CI
runner's dictionary_oss/collocation working copy: the generated evaluation
changes, but the raw diff gives reviewers no idea whether that is a harmless
side effect or an actual quality regression.

This script fills that gap. It classifies every (reading, mode, expected)
test identity shared between --before (the checked-in baseline) and --after
(the freshly Bazel-generated evaluation_updated.tsv) into:

  - regressions:      OK -> FAILED                      (always fails the run)
  - improvements:     FAILED -> OK
  - ok_output_changes: OK -> OK, output text differs      (fails unless
                        --allow-output-change is passed)
  - failed_output_changes: FAILED -> FAILED, output text differs
  - added / removed:  identity only present on one side

Every changed identity is always logged at INFO (never DEBUG-only), so
--log-file alone is enough to audit what changed; --verbose only adds
DEBUG-level detail for identities whose status AND output are unchanged.

Unlike rm_dictionary_entries.py / append_collocation_entries.py, this tool
does not merge new content into the target file -- it can only ever copy
--after over --before verbatim. --apply therefore means: "if (and only if)
nothing failed the gate, overwrite --before with --after so that Bazel's
evaluation_diff_test passes against the now-current CI working copy." A
bare/dry-run invocation never touches --before, matching the Track C
interface contract that a bare local run is side-effect-free.

Usage:
    # 1. Build the Bazel-generated evaluation snapshot first.
    #    (bazel-bin path shown is the usual oss_windows layout; adjust for
    #    your platform's output_base.)
    bazelisk build //data/dictionary_oss:evaluation --config oss_windows

    # 2. Dry-run (default): report and gate, change nothing.
    python mozc4med/tool/compare_evaluation_quality.py \
        --before src/data/dictionary_oss/evaluation.tsv \
        --after bazel-bin/data/dictionary_oss/evaluation_updated.tsv

    # 3. In CI: gate, and if it passes, sync the baseline so the Bazel
    #    diff_test that runs later in the same job also passes.
    python mozc4med/tool/compare_evaluation_quality.py \
        --before src/data/dictionary_oss/evaluation.tsv \
        --after bazel-bin/data/dictionary_oss/evaluation_updated.tsv \
        --apply \
        --log-file compare_evaluation_quality.log \
        --quality-report compare_evaluation_quality.tsv \
        --step-summary "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from typing import Dict, List, NamedTuple, Optional, Tuple

logger = logging.getLogger("compare_evaluation_quality")

DEFAULT_BEFORE = os.path.join("src", "data", "dictionary_oss", "evaluation.tsv")

Identity = Tuple[str, str, str]  # (key, mode, expected)


class EvalRow(NamedTuple):
  status: str  # "OK" or "FAILED", without the trailing ':'
  key: str
  output: str
  mode: str
  expected: str
  version: str
  raw: str


# One diff entry: (category, identity, old_row_or_None, new_row_or_None).
DiffRow = Tuple[str, Identity, Optional[EvalRow], Optional[EvalRow]]


def setup_logging(log_file: Optional[str], verbose: bool) -> None:
  level = logging.DEBUG if verbose else logging.INFO
  logger.setLevel(level)
  logger.handlers.clear()

  fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

  # Non-UTF-8 console code pages (e.g. Windows cp1252/cp932) would otherwise
  # crash on Japanese evaluation rows once those are logged at INFO.
  if hasattr(sys.stdout, "reconfigure"):
    try:
      sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
      pass

  console = logging.StreamHandler(sys.stdout)
  console.setFormatter(fmt)
  logger.addHandler(console)

  if log_file:
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)


def parse_row(line: str) -> Optional[EvalRow]:
  """Parses one evaluation.tsv line, or None for blank/header/malformed lines."""
  line = line.rstrip("\r\n")
  if not line:
    return None

  cols = line.split("\t")
  if len(cols) < 6:
    return None

  status = cols[0].strip()
  if status not in ("OK:", "FAILED:"):
    return None

  return EvalRow(
      status=status[:-1],
      key=cols[1],
      output=cols[2],
      mode=cols[3],
      expected=cols[4],
      version=cols[5],
      raw=line,
  )


def load(path: str) -> Dict[Identity, EvalRow]:
  """Loads evaluation.tsv, keyed by (key, mode, expected) test identity."""
  rows: Dict[Identity, EvalRow] = {}
  with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
    for line in f:
      row = parse_row(line)
      if row is None:
        continue
      rows[(row.key, row.mode, row.expected)] = row
  logger.info("Loaded %d evaluation row(s) from %s", len(rows), path)
  return rows


def classify(
    before: Dict[Identity, EvalRow], after: Dict[Identity, EvalRow]
) -> List[DiffRow]:
  """Classifies every identity change between before and after."""
  diffs: List[DiffRow] = []

  for identity, old in before.items():
    new = after.get(identity)
    if new is None:
      diffs.append(("removed", identity, old, None))
      continue

    if old.status == "OK" and new.status == "FAILED":
      diffs.append(("regression", identity, old, new))
    elif old.status == "FAILED" and new.status == "OK":
      diffs.append(("improvement", identity, old, new))
    elif old.status == "OK" and old.output != new.output:
      diffs.append(("ok_output_change", identity, old, new))
    elif old.status == "FAILED" and old.output != new.output:
      diffs.append(("failed_output_change", identity, old, new))
    else:
      diffs.append(("unchanged", identity, old, new))

  for identity, new in after.items():
    if identity not in before:
      diffs.append(("added", identity, None, new))

  return diffs


# Categories that always fail the run, independent of --allow-output-change.
GATING_CATEGORIES = frozenset({"regression"})
# Categories that fail the run unless --allow-output-change is passed.
SOFT_GATING_CATEGORIES = frozenset({"ok_output_change"})
# Categories logged at INFO (per CLAUDE.md 3.7: every changed line, not just
# a count). "unchanged" is intentionally excluded and only shown at DEBUG.
INFO_CATEGORIES = frozenset({
    "regression", "improvement", "ok_output_change", "failed_output_change",
    "added", "removed",
})


def describe(category: str, identity: Identity, old: Optional[EvalRow],
             new: Optional[EvalRow]) -> str:
  key, mode, expected = identity
  if category == "removed":
    return f"removed: key={key!r} mode={mode!r} expected={expected!r} was={old.raw!r}"
  if category == "added":
    return f"added: key={key!r} mode={mode!r} expected={expected!r} now={new.raw!r}"
  return (f"{category}: key={key!r} mode={mode!r} expected={expected!r} "
          f"status {old.status}->{new.status} output {old.output!r}->{new.output!r}")


def write_quality_report(path: str, diffs: List[DiffRow]) -> None:
  """Writes every changed identity as a machine-readable TSV report."""
  out_dir = os.path.dirname(path)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)
  with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("category\tkey\tmode\texpected\told_status\tnew_status\t"
             "old_output\tnew_output\told_version\tnew_version\n")
    for category, (key, mode, expected), old, new in diffs:
      if category == "unchanged":
        continue
      old_status = old.status if old else ""
      new_status = new.status if new else ""
      old_output = old.output if old else ""
      new_output = new.output if new else ""
      old_version = old.version if old else ""
      new_version = new.version if new else ""
      f.write(f"{category}\t{key}\t{mode}\t{expected}\t{old_status}\t{new_status}\t"
               f"{old_output}\t{new_output}\t{old_version}\t{new_version}\n")


def write_step_summary(path: str, diffs: List[DiffRow], counts: Dict[str, int]) -> None:
  """Appends a Markdown summary table (e.g. to $GITHUB_STEP_SUMMARY)."""
  lines = ["### mozc4med: evaluation.tsv quality comparison", ""]
  lines.append("| category | count |")
  lines.append("|---|---|")
  for category in ("regression", "improvement", "ok_output_change",
                    "failed_output_change", "added", "removed"):
    lines.append(f"| {category} | {counts.get(category, 0)} |")
  lines.append("")

  regressions = [d for d in diffs if d[0] == "regression"]
  if regressions:
    lines.append("**Regressions (OK -> FAILED):**")
    lines.append("")
    lines.append("| key | expected | old output | new output |")
    lines.append("|---|---|---|---|")
    for _category, (key, _mode, expected), old, new in regressions:
      lines.append(f"| {key} | {expected} | {old.output} | {new.output} |")
    lines.append("")

  with open(path, "a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")


def parse_args(argv: List[str]) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--before", default=DEFAULT_BEFORE,
                       help=f"Checked-in baseline evaluation.tsv "
                            f"(default: {DEFAULT_BEFORE})")
  parser.add_argument("--after", required=True,
                       help="Bazel-generated evaluation_updated.tsv to compare against")
  parser.add_argument("--allow-output-change", action="store_true",
                       help="Allow OK->OK output changes. OK->FAILED regressions "
                            "always fail regardless of this flag.")
  parser.add_argument("--apply", action="store_true",
                       help="If the gate passes, overwrite --before with --after "
                            "(default: dry-run only, --before is never modified)")
  parser.add_argument("--log-file", default=None,
                       help="Optional path to also write the log to")
  parser.add_argument("--quality-report", default=None,
                       help="Optional TSV path listing every changed identity "
                            "(category, key, mode, expected, old/new status, "
                            "old/new output, old/new version)")
  parser.add_argument("--step-summary", default=None,
                       help="Optional path to append a Markdown summary table to "
                            "(e.g. $GITHUB_STEP_SUMMARY); ignored if empty")
  parser.add_argument("-v", "--verbose", action="store_true",
                       help="Also log unchanged identities (same status and "
                            "output), at DEBUG level")
  return parser.parse_args(argv)


def main(argv: List[str]) -> int:
  args = parse_args(argv)
  setup_logging(args.log_file, args.verbose)

  mode = "APPLY" if args.apply else "DRY-RUN"
  logger.info("Mode: %s", mode)
  logger.info("before: %s", args.before)
  logger.info("after: %s", args.after)

  if not os.path.isfile(args.before):
    logger.error("--before file not found: %s", args.before)
    return 1
  if not os.path.isfile(args.after):
    logger.error("--after file not found: %s", args.after)
    return 1

  before = load(args.before)
  after = load(args.after)
  diffs = classify(before, after)

  counts: Dict[str, int] = {}
  for category, identity, old, new in diffs:
    counts[category] = counts.get(category, 0) + 1
    if category in INFO_CATEGORIES:
      logger.info(describe(category, identity, old, new))
    else:
      logger.debug(describe(category, identity, old, new))

  logger.info("=== Summary ===")
  for category in ("regression", "improvement", "ok_output_change",
                    "failed_output_change", "added", "removed", "unchanged"):
    logger.info("  %s: %d", category, counts.get(category, 0))

  if args.quality_report:
    write_quality_report(args.quality_report, diffs)
    logger.info("Wrote quality report to %s", args.quality_report)

  if args.step_summary:
    write_step_summary(args.step_summary, diffs, counts)
    logger.info("Appended Markdown summary to %s", args.step_summary)

  gate_failed = False
  if counts.get("regression", 0):
    logger.error("FAIL: %d OK->FAILED regression(s) found.", counts["regression"])
    gate_failed = True
  if counts.get("ok_output_change", 0) and not args.allow_output_change:
    logger.error(
        "FAIL: %d OK->OK output change(s) found. Inspect them or pass "
        "--allow-output-change.", counts["ok_output_change"])
    gate_failed = True

  if gate_failed:
    return 1

  if args.apply:
    if os.path.abspath(args.before) != os.path.abspath(args.after):
      shutil.copyfile(args.after, args.before)
      logger.info("Synced %s from %s (gate passed)", args.before, args.after)
    else:
      logger.info("--before and --after already refer to the same file; nothing to sync.")
  else:
    logger.info("Dry-run: %s was not modified. Pass --apply to sync it from --after.",
                args.before)

  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
