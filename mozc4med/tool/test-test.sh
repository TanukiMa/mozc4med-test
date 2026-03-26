#!/usr/bin/env bash
# run_tests_linux.sh
# ------------------------------------------------------------
# Replicates the `.github/workflows/windows-mozc4med.yaml` → test: job
# (checkout, git config, patch application, deps install, test run)
# ------------------------------------------------------------

set -euo pipefail   # abort on errors, undefined variables, and failed pipelines
IFS=$'\n\t'

# ----------------------------------------------------------------
# 1️⃣  Git configuration (local to this repo – does not affect global config)
# ----------------------------------------------------------------
git config --local user.email "local@dev.example.com"
git config --local user.name  "Local Dev"

# ----------------------------------------------------------------
# 2️⃣  Helper: apply all *.patch files in a directory (mirrors YAML logic)
# ----------------------------------------------------------------
apply_patch() {
  local pattern="$1"
  shopt -s nullglob
  local files=($pattern)
  shopt -u nullglob
  [[ ${#files[@]} -eq 0 ]] && return 0

  for p in "${files[@]}"; do
    if git apply --check "$p" >/dev/null 2>&1; then
      echo "Applying $p"
      git apply "$p"
    else
      echo "Skipping $p (does not apply cleanly)"
    fi
  done
}

# ----------------------------------------------------------------
# 3️⃣  Apply the repository’s patches (common + windows‑specific)
# ----------------------------------------------------------------
apply_patch "mozc4med/common/*.patch"
apply_patch "mozc4med/windows/*.patch"

# ----------------------------------------------------------------
# 4️⃣  (Optional) Restore the `src/third_party_cache` if you have a
#     previous cache directory.  The CI step uses GitHub Actions cache;
#     locally you can simply skip it – Bazel will download what it needs.
# ----------------------------------------------------------------
# if [[ -d "src/third_party_cache" ]]; then
#   echo "Re‑using existing third_party_cache"
# else
#   echo "No cache directory found – Bazel will populate it automatically."
# fi

# ----------------------------------------------------------------
# 5️⃣  Install / update third‑party dependencies
# ----------------------------------------------------------------
# The Windows workflow runs this via `cmd` with `python`.  Here we invoke
# the same script directly with the system Python (ensure you have Python 3).

echo "Installing/updating third‑party dependencies …"
python3 build_tools/update_deps.py   # Add `--cache_only` if you only want the cache

# ----------------------------------------------------------------
# 6️⃣  Run the test suite
# ----------------------------------------------------------------
# The original CI uses:
#   bazelisk test ... --config oss_windows -c dbg --build_tests_only
# Replace `...` with the actual test targets you care about.
# For a generic “run everything” you can use `//...` (all targets) or a
# narrower pattern like `//src/...`.
#
# NOTE: Bazelisk must be on your PATH.  On many systems you can install it
# via the `bazelisk` package or by downloading the binary.
#
# Example – run all tests in the repository:

echo "Running tests …"
bazelisk test //... \
  --config oss_windows \
  -c dbg \
  --build_tests_only

# ----------------------------------------------------------------
# 7️⃣  Finish
# ----------------------------------------------------------------
echo "✅ Test job completed successfully."
