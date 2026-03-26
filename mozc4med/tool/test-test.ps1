# test-test.ps1
# Replicates the `.github/workflows/windows-mozc4med.yaml` test job on Windows PowerShell.
# ------------------------------------------------------------
# 1️⃣  Git configuration (local to this repo – does not affect global config)
# ------------------------------------------------------------

# Abort on errors and enable strict mode (similar to `set -euo pipefail`)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Change to the src directory
Set-Location src

# Configure a local git user for this repo
git config --local user.email "local@dev.example.com"
git config --local user.name  "Local Dev"

# ------------------------------------------------------------
# 2️⃣  Helper: apply all *.patch files in a directory (mirrors YAML logic)
# ------------------------------------------------------------
function Apply-Patch {
    param([string]$Pattern)
    # Get matching files; silently continue if none are found
    $files = Get-ChildItem -Path $Pattern -File -ErrorAction SilentlyContinue
    if (-not $files) { return }
    foreach ($p in $files) {
        if (git apply --check $p.FullName > $null 2>&1) {
            Write-Host "Applying $($p.Name)"
            git apply $p.FullName
        } else {
            Write-Host "Skipping $($p.Name) (does not apply cleanly)"
        }
    }
}

# ------------------------------------------------------------
# 3️⃣  Apply the repository’s patches (common + windows‑specific)
# ------------------------------------------------------------
Apply-Patch "mozc4med/common/*.patch"
Apply-Patch "mozc4med/windows/*.patch"

# ------------------------------------------------------------
# 4️⃣  Install / update third‑party dependencies
# ------------------------------------------------------------
Write-Host "Installing/updating third‑party dependencies …"
python build_tools/update_deps.py   # Add `--cache_only` if you only want the cache

# ------------------------------------------------------------
# 5️⃣  Run the test suite
# ------------------------------------------------------------
Write-Host "Running tests …"
& bazelisk test //... `
    --config oss_windows `
    -c dbg `
    --build_tests_only

# ------------------------------------------------------------
# 6️⃣  Finish
# ------------------------------------------------------------
Write-Host "✅ Test job completed successfully."
