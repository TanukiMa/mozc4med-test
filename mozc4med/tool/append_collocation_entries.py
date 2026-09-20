#!/usr/bin/env python3
"""Append mozc4med-curated entries into a Mozc collocation data file.

Track C (see CLAUDE.md 3.7): both
src/data/dictionary_oss/collocation.txt and
src/data/dictionary_oss/collocation_suppression.txt are simple line-based
existence-filter sources (see rewriter/gen_collocation_data_main.cc and
rewriter/gen_collocation_suppression_data_main.cc) -- duplicates and line
order do not matter, so merging is just "append every new, not-yet-present
line". Unlike dictionary*.txt's filegroup, Bazel wires each of these in as
a single-file label (collocation_src / collocation_suppression_src in
data_manager/mozc_data.bzl), so it cannot simply be extended with another
list entry; instead this script edits the CI runner's *working copy* of
the target file directly, exactly like rm_dictionary_entries.py does for
dictionary*.txt. The change is never committed and no BUILD.bazel /
mozc_data.bzl patch is required, because Bazel just reads whatever bytes
are on disk at build time.

Every appended line is always logged at INFO level, so --log-file alone is
enough to audit what was added.

Usage:
    # collocation.txt: 1 data column (phrase), optional trailing note column
    # is ignored.
    python mozc4med/tool/append_collocation_entries.py --apply \
        --input "mozc4med-dic-csv/collocation/*.csv" \
        --target src/data/dictionary_oss/collocation.txt \
        --columns 1

    # collocation_suppression.txt: 2 data columns (word1, word2).
    python mozc4med/tool/append_collocation_entries.py --apply \
        --input "mozc4med-dic-csv/collocation_suppression/*.csv" \
        --target src/data/dictionary_oss/collocation_suppression.txt \
        --columns 2

    # Also write the log to a file, a TSV report, and a step summary.
    python mozc4med/tool/append_collocation_entries.py --apply \
        --input "mozc4med-dic-csv/collocation/*.csv" \
        --target src/data/dictionary_oss/collocation.txt \
        --columns 1 \
        --log-file append_collocation_entries.log \
        --added-report append_collocation_entries_added.tsv \
        --step-summary "$GITHUB_STEP_SUMMARY"

CSV format (mozc4med-dic-csv):
    A '#...' header row is required (as in generate_mozc4med_dictionary.py).
    The first --columns fields are the data columns; any further field is
    an optional note and is ignored. Blank lines are skipped.

Custom collocation data is optional: if no file matches --input, this is a
soft no-op (pass --required to fail instead), so builds still succeed
before mozc4med-dic-csv grows a collocation/ or collocation_suppression/
directory.
"""

from __future__ import annotations

import argparse
import csv
import glob
import logging
import os
import sys
from typing import List, Optional, Set, Tuple

logger = logging.getLogger("append_collocation_entries")

Row = Tuple[str, ...]
# (source_csv, target_file, row)
AddedRow = Tuple[str, str, Row]


def setup_logging(log_file: Optional[str], verbose: bool) -> None:
  level = logging.DEBUG if verbose else logging.INFO
  logger.setLevel(level)
  logger.handlers.clear()

  fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

  # Non-UTF-8 console code pages (e.g. Windows cp1252/cp932) would otherwise
  # crash on Japanese collocation entries logged at INFO.
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


def read_csv(path: str, columns: int) -> List[Row]:
  """Parses one mozc4med-dic-csv CSV file into `columns`-tuples, failing fast on bad data."""
  rows: List[Row] = []
  with open(path, encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    if header is None:
      return rows
    if not header[0].lstrip().startswith("#"):
      logger.error("%s: expected a '#...' header row, got: %r", path, header)
      sys.exit(1)

    for lineno, fields in enumerate(reader, start=2):
      if not fields or not any(field.strip() for field in fields):
        continue  # skip blank lines

      if len(fields) < columns:
        logger.error("%s:%d: expected at least %d column(s), got %d: %r",
                      path, lineno, columns, len(fields), fields)
        sys.exit(1)

      values = tuple(field.strip() for field in fields[:columns])
      if any(not value for value in values):
        logger.error("%s:%d: data column(s) must not be empty: %r", path, lineno, fields)
        sys.exit(1)

      rows.append(values)
  return rows


def load_existing_lines(path: str) -> Set[str]:
  if not os.path.isfile(path):
    return set()
  with open(path, encoding="utf-8") as f:
    return {line.rstrip("\r\n") for line in f if line.strip()}


def ensure_trailing_newline(path: str) -> None:
  """Avoids accidentally merging the last existing line with the first appended one."""
  with open(path, "rb") as f:
    f.seek(0, os.SEEK_END)
    size = f.tell()
    if size == 0:
      return
    f.seek(-1, os.SEEK_END)
    last_byte = f.read(1)
  if last_byte != b"\n":
    with open(path, "a", encoding="utf-8", newline="\n") as f:
      f.write("\n")


def write_added_report(path: str, columns: int, rows: List[AddedRow]) -> None:
  """Writes every appended entry as a machine-readable TSV report."""
  out_dir = os.path.dirname(path)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)
  header = ["source_csv", "target_file"] + [f"col{i + 1}" for i in range(columns)]
  with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("\t".join(header) + "\n")
    for source_csv, target_file, row in rows:
      f.write("\t".join([source_csv, target_file, *row]) + "\n")


def write_step_summary(path: str, target: str, rows: List[AddedRow], total_added: int) -> None:
  """Appends a Markdown table of added entries (e.g. to $GITHUB_STEP_SUMMARY)."""
  lines = [f"### mozc4med: entries appended to {os.path.basename(target)}", ""]
  if rows:
    lines.append("| source CSV | entry |")
    lines.append("|---|---|")
    for source_csv, _target_file, row in rows:
      lines.append(f"| {source_csv} | {', '.join(row)} |")
    lines.append("")
  lines.append(f"**Total appended: {total_added}**")
  lines.append("")
  with open(path, "a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")


def parse_args(argv: List[str]) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("--input", required=True,
                       help="Input CSV glob pattern (mozc4med-dic-csv source)")
  parser.add_argument("--target", required=True,
                       help="Target file to append into, e.g. "
                            "src/data/dictionary_oss/collocation.txt")
  parser.add_argument("--columns", type=int, default=1,
                       help="Number of tab-separated data columns per line "
                            "(1 for collocation.txt, 2 for collocation_suppression.txt; "
                            "default: 1)")
  parser.add_argument("--apply", action="store_true",
                       help="Rewrite --target (default: dry-run only)")
  parser.add_argument("--required", action="store_true",
                       help="Fail if no file matches --input (default: soft no-op, "
                            "since custom collocation data is optional)")
  parser.add_argument("--log-file", default=None,
                       help="Optional path to also write the log to")
  parser.add_argument("--added-report", default=None,
                       help="Optional TSV path listing every appended entry")
  parser.add_argument("--step-summary", default=None,
                       help="Optional path to append a Markdown summary table to "
                            "(e.g. $GITHUB_STEP_SUMMARY); ignored if empty")
  parser.add_argument("-v", "--verbose", action="store_true",
                       help="Log extra detail (e.g. already-present entries) at DEBUG level")
  return parser.parse_args(argv)


def main(argv: List[str]) -> int:
  args = parse_args(argv)
  setup_logging(args.log_file, args.verbose)

  mode = "APPLY" if args.apply else "DRY-RUN"
  logger.info("Mode: %s", mode)
  logger.info("input: %s", args.input)
  logger.info("target: %s (%d column(s))", args.target, args.columns)

  files = sorted(glob.glob(args.input))
  if not files:
    message = f"No input files matched: {args.input}"
    if args.required:
      logger.error(message)
      return 1
    logger.warning("%s (skipping -- custom collocation data is optional)", message)
    return 0

  if not os.path.isfile(args.target):
    logger.error("Target file not found: %s", args.target)
    return 1

  existing = load_existing_lines(args.target)
  seen: Set[str] = set(existing)
  added_rows: List[AddedRow] = []
  new_lines: List[str] = []

  for path in files:
    for row in read_csv(path, args.columns):
      line = "\t".join(row)
      if line in seen:
        logger.debug("%s: already present, skipping -> %s", os.path.basename(path), line)
        continue
      seen.add(line)
      new_lines.append(line)
      added_rows.append((os.path.basename(path), os.path.basename(args.target), row))
      logger.info("%s: appending -> %s", os.path.basename(args.target), line)

  logger.info("=== Summary ===")
  logger.info("%s: %d new line(s) to append (%d already present)",
              os.path.basename(args.target), len(new_lines), len(existing))

  if args.apply and new_lines:
    ensure_trailing_newline(args.target)
    with open(args.target, "a", encoding="utf-8", newline="\n") as f:
      for line in new_lines:
        f.write(line + "\n")
    logger.info("%s: appended %d line(s)", os.path.basename(args.target), len(new_lines))

  if args.added_report:
    write_added_report(args.added_report, args.columns, added_rows)
    logger.info("Wrote added-entry report to %s (%d row(s))",
                args.added_report, len(added_rows))

  if args.step_summary:
    write_step_summary(args.step_summary, args.target, added_rows, len(new_lines))
    logger.info("Appended Markdown summary to %s", args.step_summary)

  if not args.apply:
    logger.info("Dry-run: no files were modified. Pass --apply to rewrite them.")

  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
