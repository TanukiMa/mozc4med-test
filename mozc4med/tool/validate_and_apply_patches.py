#!/usr/bin/env python3
"""Validate patch metadata, detect overlaps, then apply patches in order."""

from __future__ import annotations

import glob
import os
import subprocess
import sys
from typing import Dict, List, Set, Tuple


def parse_patch_header(patch_path: str) -> Tuple[str, str, str]:
    depends_on = ""
    touch_files = ""
    scope = ""
    with open(patch_path, encoding="utf-8", newline="") as patch_file:
        for raw_line in patch_file:
            line = raw_line.rstrip("\n")
            if line.startswith("--- "):
                break
            if line.startswith("Depends-On:"):
                depends_on = line.split(":", 1)[1].strip()
            elif line.startswith("Touch-Files:"):
                touch_files = line.split(":", 1)[1].strip()
            elif line.startswith("Scope:"):
                scope = line.split(":", 1)[1].strip()
    return depends_on, touch_files, scope


def dependency_refs(depends_on: str) -> Set[str]:
    refs: Set[str] = set()
    for token in depends_on.split(","):
        normalized = token.strip()
        if not normalized or normalized.lower() == "none":
            continue
        refs.add(normalized)
        refs.add(os.path.basename(normalized))
    return refs


def run_git_apply_check(patch_path: str) -> None:
    patch_name = os.path.basename(patch_path)
    print(f"Checking {patch_name}")
    try:
        subprocess.run(["git", "apply", "--check", patch_path], check=True)
    except subprocess.CalledProcessError:
        print(f"::error file={patch_path}::git apply --check failed for {patch_name}")
        raise


def run_git_apply(patch_path: str) -> None:
    patch_name = os.path.basename(patch_path)
    print(f"Applying {patch_name}")
    subprocess.run(["git", "apply", patch_path], check=True)


def run_git_apply_reverse(patch_path: str) -> None:
    patch_name = os.path.basename(patch_path)
    print(f"Reverting {patch_name} (check phase)")
    subprocess.run(["git", "apply", "-R", patch_path], check=True)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_and_apply_patches.py <patch_dir> [<patch_dir> ...]")
        return 1

    patch_series: List[Tuple[str, List[str]]] = []
    for patch_dir in sys.argv[1:]:
        patches = sorted(glob.glob(os.path.join(patch_dir, "*.patch")))
        if patches:
            patch_series.append((patch_dir, patches))

    if not patch_series:
        print("No patches found in the specified directories.")
        return 0

    for patch_dir, patches in patch_series:
        print(f"Validating metadata and overlap rules in {patch_dir}")
        owners_by_file: Dict[str, str] = {}
        deps_by_patch: Dict[str, Set[str]] = {}

        for patch_path in patches:
            patch_name = os.path.basename(patch_path)
            depends_on, touch_files, scope = parse_patch_header(patch_path)

            if not depends_on or not touch_files or not scope:
                print(
                    f"::error file={patch_path}::Missing required patch header "
                    f"metadata (Depends-On, Touch-Files, Scope)"
                )
                return 1

            deps_by_patch[patch_name] = dependency_refs(depends_on)

            files = [item.strip() for item in touch_files.split(",") if item.strip()]
            if not files:
                print(f"::error file={patch_path}::Touch-Files must list at least one file")
                return 1

            for touched_file in files:
                owner = owners_by_file.get(touched_file)
                if owner and owner != patch_name:
                    owner_depends_on_patch = patch_name in deps_by_patch.get(owner, set())
                    patch_depends_on_owner = owner in deps_by_patch[patch_name]
                    if not owner_depends_on_patch and not patch_depends_on_owner:
                        print(
                            f"::error file={patch_path}::Touch-Files overlap for "
                            f"'{touched_file}' between '{owner}' and '{patch_name}' "
                            f"without dependency chain"
                        )
                        return 1
                owners_by_file[touched_file] = patch_name

        print(f"Running ordered git apply --check in {patch_dir}")
        applied_for_check: List[str] = []
        try:
            for patch_path in patches:
                run_git_apply_check(patch_path)
                run_git_apply(patch_path)
                applied_for_check.append(patch_path)
        finally:
            for patch_path in reversed(applied_for_check):
                run_git_apply_reverse(patch_path)

    for patch_dir, patches in patch_series:
        print(f"Applying ordered patch series in {patch_dir}")
        for patch_path in patches:
            run_git_apply(patch_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
