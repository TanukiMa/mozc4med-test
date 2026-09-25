#!/usr/bin/env python3
"""Phase 2 guard: fail CI if built mozc4med artifacts still carry upstream
Mozc identity markers that must not collide with a side-by-side install of
plain OSS Mozc (CLAUDE.md Phase 2: "Isolate data paths, IPC names, and
Registry keys" / "Refresh all Windows CLSIDs/GUIDs").

This mirrors the pattern of Mozkey's tools/check_no_network_strings.py: scan
built binaries (ASCII + UTF-16LE decoded text, plus a raw byte scan for
compiled GUID structs), classify hits as HARD_DENY (fails the build) or
REPORT_ONLY (printed for audit, does not fail), and exit non-zero on any
HARD_DENY hit.

Unlike check_no_network_strings.py's markers (Google Update/telemetry
strings that should never appear at all), every HARD_DENY marker here is a
literal *upstream* value that mozc4med/common/0001_brand_isolation.patch,
0002_path_isolation.patch, or windows/0008_windows_guid_refresh.patch is
supposed to have already replaced. A hit means one of those patches failed
to apply, was reverted, or a new code path reintroduced the old literal
(e.g. via an upstream merge) -- so this check is a regression guard for
patches that already exist, not a substitute for writing them.

This is a read-only verification gate, not a Track C data-mutation tool:
there is nothing to --apply, and a bare run never writes anything except
the optional --log-file/--report/--step-summary outputs.

Usage:
    # Scan every mozc*.exe/mozc*.dll under src/bazel-bin (default root).
    python mozc4med/tool/check_no_upstream_identifiers.py

    # Scan explicit files (e.g. after an MSI administrative extract).
    python mozc4med/tool/check_no_upstream_identifiers.py \
        extracted/mozc_tip64.dll extracted/mozc_server.exe

    # CI: full audit trail.
    python mozc4med/tool/check_no_upstream_identifiers.py \
        --log-file check_no_upstream_identifiers.log \
        --report check_no_upstream_identifiers.tsv \
        --step-summary "$GITHUB_STEP_SUMMARY"
"""

from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import re
import struct
import sys
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("check_no_upstream_identifiers")

DEFAULT_ROOT = os.path.join("src", "bazel-bin")
RUNTIME_BINARY_PATTERN = re.compile(r"^mozc.*\.(exe|dll)$", re.IGNORECASE)


def guid_le_bytes(data1: int, data2: int, data3: int, data4: bytes) -> bytes:
  """Little-endian byte layout of a `constexpr GUID {data1, data2, data3,
  data4}` literal, i.e. exactly what a compiler emits for the struct."""
  return struct.pack("<LHH", data1, data2, data3) + data4


# --- Text markers -----------------------------------------------------
#
# Literal identifiers from the *upstream* (pre-mozc4med) src/base/const.h
# MOZC_BUILD branch. mozc4med/common/0001_brand_isolation.patch and
# 0002_path_isolation.patch replace every one of these with a mozc4med- or
# MATANUKI-scoped equivalent; see that patch for the current values.
HARD_DENY_TEXT_MARKERS: Dict[str, str] = {
    # Windows: mutex/event/IPC/window-class isolation (const.h, MOZC_BUILD,
    # _WIN32 branch).
    "Local\\Mozc.event.": "kEventPathPrefix -> Local\\Mozc4med.event.",
    "Local\\Mozc.mutex.": "kMutexPathPrefix -> Local\\Mozc4med.mutex.",
    "mozc.renderer.message": "kMessageReceiverMessageName -> mozc4med.renderer.message",
    "mozc.renderer.window": "kMessageReceiverClassName -> mozc4med.renderer.window",
    "MozcCandidateWindow": "kCandidateWindowClassName -> Mozc4medCandidateWindow",
    "MozcCompositionWindow": "kCompositionWindowClassName -> Mozc4medCompositionWindow",
    "MozcIndicatorWindow": "kIndicatorWindowClassName -> Mozc4medIndicatorWindow",
    "MozcInfolistWindow": "kInfolistWindowClassName -> Mozc4medInfolistWindow",
    "MozcUIWindow": "kIMEUIWndClassName -> Mozc4medUIWindow",
    "\\\\.\\pipe\\mozc.": "kIPCPrefix -> \\\\.\\pipe\\mozc4med.",
    "MozcCandidateUI": "kCandidateUIDescription -> Mozc4medCandidateUI",
    "Mozc Configuration": "kConfigurationDisplayname -> Mozc4med Configuration",
    "Software\\Mozc Project\\Mozc": "kMozcRegKey -> Software\\MATANUKI\\Mozc4med",
    "Software\\Policies\\Mozc Project\\Mozc\\Preferences":
        "kElevatedProcessDisabledKey -> "
        "Software\\Policies\\MATANUKI\\Mozc4med\\Preferences",
    # macOS / Linux event path prefixes (const.h, other platform branches).
    "Mozc.event.": "kEventPathPrefix (macOS) -> Mozc4med.event.",
    # NOTE: Linux's bare "mozc.event." is intentionally NOT listed here: it
    # is not a distinguishable substring once isolated (the isolated value
    # "mozc4med.event." does not contain it, so no false negative), but the
    # bare 3-letter "mozc" prefix used elsewhere makes an exact-substring
    # HARD_DENY too fragile to maintain by hand; audit Linux path isolation
    # via mozc4med/common/0002_path_isolation.patch and 0004_ibus_install_path
    # coverage instead of a binary string scan.

    # Old TSF LangBar IIDs (win32/tip/tip_lang_bar_menu.h): stored as plain
    # #define string literals, not GUID structs, so only the text form can
    # leak into a binary.
    "75B2153A-504B-48C9-9257-BA8D60E523E6":
        "IIDSTR_IMozcLangBarItem -> 2E9C8D7A-1F54-42E8-9D62-6A9B8C7D5E31",
    "9ABF0C3B-4AC6-4DED-9EF6-97E728852CF3":
        "IIDSTR_IMozcLangBarToggleItem -> 4B7E6C10-3D92-4F4B-8A71-C5D2E9F0412A",
}

REPORT_ONLY_TEXT_MARKERS: Dict[str, str] = {
    # Phase 1 explicitly keeps these binary/DLL filenames unchanged (see
    # mozc4med/readme-mozc4med.md); they are expected to appear as literal
    # spawn-target strings and are not, by themselves, an isolation defect.
    "mozc_server.exe": "kMozcServerName (unchanged in Phase 1/2 by design)",
    "mozc_tip32.dll": "kMozcTIP32 (unchanged in Phase 1/2 by design)",
    "mozc_tip64.dll": "kMozcTIP64 (unchanged in Phase 1/2 by design)",
    "mozc_tip64x.dll": "kMozcTIP64X (unchanged in Phase 1/2 by design)",
    "mozc_broker.exe": "kMozcBroker (unchanged in Phase 1/2 by design)",
    "mozc_tool.exe": "kMozcTool (unchanged in Phase 1/2 by design)",
    "mozc_renderer.exe": "kMozcRenderer (unchanged in Phase 1/2 by design)",
    "mozc_cache_service.exe": "kMozcCacheServiceExeName (unchanged in Phase 1/2 by design)",
    "mozc_ja.ime": "kIMEFile (unchanged in Phase 1/2 by design)",
    # kCompanyNameInEnglish became "Mozc Project, MATANUKI" (0001 appends
    # rather than replaces), so the substring "Mozc Project" legitimately
    # still occurs; audit it, don't hard-fail on it.
    "Mozc Project": "kCompanyNameInEnglish is now 'Mozc Project, MATANUKI'",
}


# --- GUID markers -------------------------------------------------------
#
# Every CLSID/IID that mozc4med/windows/0008_windows_guid_refresh.patch
# refreshed, in both forms a leftover copy could take:
#   - hex_text: the hyphenated form, e.g. leaking into .rc/.wxs comments,
#     debug strings, or a registry export.
#   - le_bytes: the little-endian byte layout a compiled `constexpr GUID`
#     literal actually produces -- the form that matters most, since a
#     stale CLSID still *registered* is what would collide with a
#     side-by-side upstream Mozc/TIP installation.
@dataclasses.dataclass(frozen=True)
class OldGuid:
  name: str
  hex_text: str
  le_bytes: bytes


OLD_GUIDS: Tuple[OldGuid, ...] = (
    OldGuid("kMozcTextService (tsf_profile.cc)",
            "10A67BC8-22FA-4A59-90DC-2546652C56BF",
            guid_le_bytes(0x10a67bc8, 0x22fa, 0x4a59,
                          bytes([0x90, 0xdc, 0x25, 0x46, 0x65, 0x2c, 0x56, 0xbf]))),
    OldGuid("kMozcProfile (tsf_profile.cc)",
            "186F700C-71CF-43FE-A00E-AACB1D9E6D3D",
            guid_le_bytes(0x186f700c, 0x71cf, 0x43fe,
                          bytes([0xa0, 0x0e, 0xaa, 0xcb, 0x1d, 0x9e, 0x6d, 0x3d]))),
    OldGuid("kMozcTipClsid (system_util.cc, same value as kMozcTextService)",
            "10A67BC8-22FA-4A59-90DC-2546652C56BF",
            guid_le_bytes(0x10a67bc8, 0x22fa, 0x4a59,
                          bytes([0x90, 0xdc, 0x25, 0x46, 0x65, 0x2c, 0x56, 0xbf]))),
    OldGuid("kDisplayAttributeInput (tip_display_attributes.cc)",
            "84CA1E7E-3020-4D1C-8968-DDA372D1E067",
            guid_le_bytes(0x84ca1e7e, 0x3020, 0x4d1c,
                          bytes([0x89, 0x68, 0xdd, 0xa3, 0x72, 0xd1, 0xe0, 0x67]))),
    OldGuid("kDisplayAttributeConverted (tip_display_attributes.cc)",
            "8A4028E5-2DCD-4365-A5DC-71F67E797437",
            guid_le_bytes(0x8a4028e5, 0x2dcd, 0x4365,
                          bytes([0xa5, 0xdc, 0x71, 0xf6, 0x7e, 0x79, 0x74, 0x37]))),
    OldGuid("kTipLangBarItem_Button (tip_lang_bar.cc)",
            "FC8E2486-F5BA-4863-91C3-8D166B454604",
            guid_le_bytes(0xfc8e2486, 0xf5ba, 0x4863,
                          bytes([0x91, 0xc3, 0x8d, 0x16, 0x6b, 0x45, 0x46, 0x04]))),
    OldGuid("kTipLangBarItem_ToolButton (tip_lang_bar.cc)",
            "1BA637CA-7521-4F21-B51E-6516271A9FE3",
            guid_le_bytes(0x1ba637ca, 0x7521, 0x4f21,
                          bytes([0xb5, 0x1e, 0x65, 0x16, 0x27, 0x1a, 0x9f, 0xe3]))),
    OldGuid("kTipLangBarItem_HelpMenu (tip_lang_bar.cc)",
            "F78AD6B1-49D3-400E-8218-896F22A70011",
            guid_le_bytes(0xf78ad6b1, 0x49d3, 0x400e,
                          bytes([0x82, 0x18, 0x89, 0x6f, 0x22, 0xa7, 0x00, 0x11]))),
    OldGuid("kTipPreservedKey_Kanji (tip_text_service.cc)",
            "F16B7D92-84B0-4AC6-A35B-06EA77180A18",
            guid_le_bytes(0xf16b7d92, 0x84b0, 0x4ac6,
                          bytes([0xa3, 0x5b, 0x06, 0xea, 0x77, 0x18, 0x0a, 0x18]))),
    OldGuid("kTipPreservedKey_F10 (tip_text_service.cc)",
            "80DAD291-1981-46FA-998D-B84D6C1BA02C",
            guid_le_bytes(0x80dad291, 0x1981, 0x46fa,
                          bytes([0x99, 0x8d, 0xb8, 0x4d, 0x6c, 0x1b, 0xa0, 0x2c]))),
    OldGuid("kTipPreservedKey_Romaji (tip_text_service.cc)",
            "95571C08-B05A-4ABA-B038-F3DEAE532F91",
            guid_le_bytes(0x95571c08, 0xb05a, 0x4aba,
                          bytes([0xb0, 0x38, 0xf3, 0xde, 0xae, 0x53, 0x2f, 0x91]))),
    OldGuid("kTipFunctionProvider (tip_text_service.cc)",
            "ECFB2528-E7D2-4CA0-BBE4-32FE08C148F4",
            guid_le_bytes(0xecfb2528, 0xe7d2, 0x4ca0,
                          bytes([0xbb, 0xe4, 0x32, 0xfe, 0x08, 0xc1, 0x48, 0xf4]))),
    OldGuid("KGuidNonobservableSuggestWindow (tip_ui_element_delegate.cc)",
            "AD2489FB-D4C4-4632-85A9-7F9F917AB0FD",
            guid_le_bytes(0xad2489fb, 0xd4c4, 0x4632,
                          bytes([0x85, 0xa9, 0x7f, 0x9f, 0x91, 0x7a, 0xb0, 0xfd]))),
    OldGuid("KGuidObservableSuggestWindow (tip_ui_element_delegate.cc)",
            "0E2D447F-9B4A-490C-9C4D-61A6A707BE26",
            guid_le_bytes(0x0e2d447f, 0x9b4a, 0x490c,
                          bytes([0x9c, 0x4d, 0x61, 0xa6, 0xa7, 0x07, 0xbe, 0x26]))),
    OldGuid("KGuidCandidateWindow (tip_ui_element_delegate.cc)",
            "ED70ECDE-C8AA-4170-96CC-0090DEA8AEC2",
            guid_le_bytes(0xed70ecde, 0xc8aa, 0x4170,
                          bytes([0x96, 0xcc, 0x00, 0x90, 0xde, 0xa8, 0xae, 0xc2]))),
    OldGuid("KGuidIndicatorWindow (tip_ui_element_delegate.cc)",
            "0090BF80-5F33-41B1-843C-E3EC79ED25F9",
            guid_le_bytes(0x0090bf80, 0x5f33, 0x41b1,
                          bytes([0x84, 0x3c, 0xe3, 0xec, 0x79, 0xed, 0x25, 0xf9]))),
)


def setup_logging(log_file: Optional[str], verbose: bool) -> None:
  level = logging.DEBUG if verbose else logging.INFO
  logger.setLevel(level)
  logger.handlers.clear()

  fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

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


def collect_targets(root: str, explicit_paths: List[str]) -> List[str]:
  if explicit_paths:
    return explicit_paths

  if not os.path.isdir(root):
    return []

  targets: List[str] = []
  for dirpath, _dirnames, filenames in os.walk(root):
    if ".runfiles" in dirpath.replace("\\", "/").split("/"):
      continue
    for name in filenames:
      if RUNTIME_BINARY_PATTERN.match(name):
        targets.append(os.path.join(dirpath, name))
  return sorted(targets)


def decode_binary(path: str) -> Tuple[bytes, str, str]:
  with open(path, "rb") as f:
    data = f.read()
  ascii_text = data.decode("ascii", errors="ignore")
  utf16le_text = data.decode("utf-16le", errors="ignore")
  return data, ascii_text, utf16le_text


def find_text_markers(haystacks: Tuple[str, str],
                       markers: Dict[str, str]) -> List[Tuple[str, str]]:
  """Returns [(marker, note), ...] for every marker found in either haystack."""
  found = []
  for marker, note in markers.items():
    marker_l = marker.lower()
    if any(marker_l in haystack for haystack in haystacks):
      found.append((marker, note))
  return sorted(found)


def find_guid_markers(raw: bytes, ascii_text: str) -> List[Tuple[str, str]]:
  """Returns [(old_guid_name, form), ...] for every OLD_GUIDS hit."""
  found = []
  ascii_lower = ascii_text.lower()
  for guid in OLD_GUIDS:
    if guid.le_bytes in raw:
      found.append((guid.name, f"raw struct bytes ({guid.hex_text})"))
    elif guid.hex_text.lower() in ascii_lower:
      found.append((guid.name, f"text form ({guid.hex_text})"))
  return found


@dataclasses.dataclass
class ScanResult:
  path: str
  hard_hits: List[Tuple[str, str]]
  report_hits: List[Tuple[str, str]]
  guid_hits: List[Tuple[str, str]]

  @property
  def failed(self) -> bool:
    return bool(self.hard_hits or self.guid_hits)


def scan_file(path: str) -> ScanResult:
  raw, ascii_text, utf16le_text = decode_binary(path)
  haystacks = (ascii_text.lower(), utf16le_text.lower())
  return ScanResult(
      path=path,
      hard_hits=find_text_markers(haystacks, HARD_DENY_TEXT_MARKERS),
      report_hits=find_text_markers(haystacks, REPORT_ONLY_TEXT_MARKERS),
      guid_hits=find_guid_markers(raw, ascii_text),
  )


def write_report(path: str, results: List[ScanResult]) -> None:
  out_dir = os.path.dirname(path)
  if out_dir:
    os.makedirs(out_dir, exist_ok=True)
  with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write("file\tcategory\tmarker\tnote\n")
    for result in results:
      for marker, note in result.hard_hits:
        f.write(f"{result.path}\tHARD_DENY\t{marker}\t{note}\n")
      for name, form in result.guid_hits:
        f.write(f"{result.path}\tHARD_DENY_GUID\t{name}\t{form}\n")
      for marker, note in result.report_hits:
        f.write(f"{result.path}\tREPORT_ONLY\t{marker}\t{note}\n")


def write_step_summary(path: str, results: List[ScanResult]) -> None:
  lines = ["### mozc4med: upstream identifier collision check (Phase 2)", ""]
  failing = [r for r in results if r.failed]
  lines.append(f"Scanned {len(results)} file(s); {len(failing)} failed.")
  lines.append("")
  if failing:
    lines.append("| file | marker | note |")
    lines.append("|---|---|---|")
    for result in failing:
      for marker, note in result.hard_hits:
        lines.append(f"| {result.path} | {marker} | {note} |")
      for name, form in result.guid_hits:
        lines.append(f"| {result.path} | {name} | {form} |")
    lines.append("")
  with open(path, "a", encoding="utf-8", newline="\n") as f:
    f.write("\n".join(lines) + "\n")


def parse_args(argv: List[str]) -> argparse.Namespace:
  parser = argparse.ArgumentParser(
      description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument("paths", nargs="*",
                       help="Explicit .exe/.dll files to inspect")
  parser.add_argument("--root", default=DEFAULT_ROOT,
                       help=f"Root directory to recursively scan when no explicit "
                            f"paths are given (default: {DEFAULT_ROOT})")
  parser.add_argument("--log-file", default=None,
                       help="Optional path to also write the log to")
  parser.add_argument("--report", default=None,
                       help="Optional TSV path listing every marker hit "
                            "(file, category, marker, note)")
  parser.add_argument("--step-summary", default=None,
                       help="Optional path to append a Markdown summary table to "
                            "(e.g. $GITHUB_STEP_SUMMARY); ignored if empty")
  parser.add_argument("-v", "--verbose", action="store_true",
                       help="Also log clean files (no hits at all) at DEBUG level")
  return parser.parse_args(argv)


def main(argv: List[str]) -> int:
  args = parse_args(argv)
  setup_logging(args.log_file, args.verbose)

  targets = collect_targets(args.root, args.paths)
  if not targets:
    logger.info("No targets found under %s; nothing to check.", args.root)
    return 0

  logger.info("Scanning %d file(s)", len(targets))

  results: List[ScanResult] = []
  for path in targets:
    if not os.path.isfile(path):
      logger.error("Target not found: %s", path)
      results.append(ScanResult(path, [("<missing>", "file not found")], [], []))
      continue
    result = scan_file(path)
    results.append(result)

    if result.hard_hits:
      for marker, note in result.hard_hits:
        logger.info("%s: HARD_DENY marker %r (%s)", path, marker, note)
    for name, form in result.guid_hits:
      logger.info("%s: HARD_DENY old CLSID %s [%s]", path, name, form)
    for marker, note in result.report_hits:
      logger.info("%s: REPORT_ONLY marker %r (%s)", path, marker, note)

    if not result.failed:
      logger.debug("%s: clean", path)

  failed_count = sum(1 for r in results if r.failed)
  logger.info("=== Summary ===")
  logger.info("Scanned: %d, failed: %d", len(results), failed_count)

  if args.report:
    write_report(args.report, results)
    logger.info("Wrote report to %s", args.report)

  if args.step_summary:
    write_step_summary(args.step_summary, results)
    logger.info("Appended Markdown summary to %s", args.step_summary)

  if failed_count:
    logger.error("FAIL: %d file(s) still carry upstream Mozc identity markers.",
                  failed_count)
    return 1

  logger.info("PASS: no upstream identity markers found.")
  return 0


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
