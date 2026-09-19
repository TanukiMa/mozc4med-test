#!/usr/bin/env python3
"""Merge mozc4med-dic-csv vocabulary CSVs into a mozc4med.tsv dictionary file.

mozc4med-dic-csv (private repo) ships per-source CSV files shaped like:

    #読み,品詞1,品詞2,コスト,単語,付随情報

品詞1/品詞2 are literal line numbers into data/dictionary_oss/id.def -- the
same POS ids Mozc's own dictionary0*.txt files use (see makedic.py in that
repo) -- so no POS translation table is needed here. The columns already
line up with the tab-separated "key lid rid cost value" format that
data/dictionary_oss/BUILD.bazel's base_dictionary_data filegroup expects.

mozc4med.tsv is wired into that filegroup (as a raw dictionary0*.txt-style
entry file), not into the 3-column words.tsv/places.tsv "manual dictionary"
filegroup, so unlike the CSV inputs, the generated file has NO header row:
gen_aux_dictionary.py's Entry.Parse would crash on int("コスト") if one
were present.

Fetching mozc4med-dic-csv itself is left to the caller (a workflow step
checks the private repo out to a local directory); this script only merges
whatever CSVs are already on disk, so it stays runnable/testable locally
exactly like mozc4med-dic-csv's own makedic.py:

  python mozc4med/tool/generate_mozc4med_dictionary.py \
      --input "../mozc4med-dic-csv/example/*.csv" \
      --output src/data/dictionary_manual/mozc4med.tsv
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import sys
from typing import List, Tuple

MIN_COLUMNS = 5  # 読み, 品詞1, 品詞2, コスト, 単語 (付随情報 is optional)
DEFAULT_INPUT = os.path.join("mozc4med-dic-csv", "example", "*.csv")
DEFAULT_OUTPUT = os.path.join("src", "data", "dictionary_manual", "mozc4med.tsv")

# The optional CSV note is preserved while reading/deduping, but the generated
# raw dictionary output must stay 5 columns.
# (reading, lid, rid, cost, value, note)
Row = Tuple[str, str, str, str, str, str]


def read_csv(path: str) -> List[Row]:
  """Parses one mozc4med-dic-csv CSV file into rows, failing fast on bad data."""
  rows: List[Row] = []
  with open(path, encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    header = next(reader, None)
    if header is None:
      return rows
    if not header[0].lstrip().startswith("#"):
      print(f"error: {path}: expected a '#...' header row, got: {header}",
            file=sys.stderr)
      sys.exit(1)

    for lineno, fields in enumerate(reader, start=2):
      if not fields or not any(field.strip() for field in fields):
        continue  # skip blank lines

      if len(fields) < MIN_COLUMNS:
        print(f"error: {path}:{lineno}: expected at least {MIN_COLUMNS} "
              f"columns (reading, lid, rid, cost, value), got {len(fields)}: "
              f"{fields}", file=sys.stderr)
        sys.exit(1)

      reading, lid, rid, cost, value = (field.strip() for field in fields[:5])
      note = fields[5].strip() if len(fields) > 5 else ""

      if not reading or not value:
        print(f"error: {path}:{lineno}: reading/value must not be empty: "
              f"{fields}", file=sys.stderr)
        sys.exit(1)
      for name, num in (("品詞1", lid), ("品詞2", rid), ("コスト", cost)):
        if not num.isdigit():
          print(f"error: {path}:{lineno}: {name} must be a numeric id.def "
                f"line number, got {num!r}: {fields}", file=sys.stderr)
          sys.exit(1)

      rows.append((reading, lid, rid, cost, value, note))
  return rows


def parse_args(argv: List[str]) -> argparse.Namespace:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-i", "--input", default=DEFAULT_INPUT,
                       help=f"Input CSV glob pattern (default: {DEFAULT_INPUT})")
  parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT,
                       help=f"Output TSV path (default: {DEFAULT_OUTPUT})")
  return parser.parse_args(argv)


def main(argv: List[str]) -> int:
  args = parse_args(argv)

  files = sorted(glob.glob(args.input))
  if not files:
    print(f"error: no files matched: {args.input}", file=sys.stderr)
    return 1

  print(f"[DEBUG] merging {len(files)} CSV file(s) matching {args.input}")
  rows: List[Row] = []
  seen = set()
  for path in files:
    loaded = 0
    for row in read_csv(path):
      dedupe_key = row[:5]  # ignore 付随情報 when deduping
      if dedupe_key in seen:
        continue
      seen.add(dedupe_key)
      rows.append(row)
      loaded += 1
    print(f"[DEBUG] loaded {loaded} entries from {path}")

  if not rows:
    print(f"error: no entries found in matched files: {args.input}",
          file=sys.stderr)
    return 1

  # Sort for reproducible output regardless of filesystem glob order.
  rows.sort()

  out_dir = os.path.dirname(args.output)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)

  # No header row: this file is consumed as a raw dictionary0*.txt-style
  # entry file (see data/dictionary_oss/BUILD.bazel's base_dictionary_data),
  # not as the 3-column words.tsv/places.tsv "manual dictionary" format.
  # Emit exactly 5 columns even when the source CSV has optional metadata.
  with open(args.output, "w", encoding="utf-8", newline="\n") as f:
    for reading, lid, rid, cost, value, _note in rows:
      f.write("\t".join([reading, lid, rid, cost, value]) + "\n")

  print(f"[DEBUG] wrote {len(rows)} entries to {args.output}")
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
