# Filename: tests/testing_harness/layer5_step3_cleanup.ps1
function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

$ProjectRoot = Get-ProjectRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "--- Layer 5: Migration Workflow Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 3: Automated Cleanup for Migration Test ---" -ForegroundColor Cyan

# --- A. Identify Test Directories ---
$l5StateFile = Join-Path $ProjectRoot "tests/testing_harness/.l5_test_dir.txt"
$l5MigratedStateFile = Join-Path $ProjectRoot "tests/testing_harness/.l5_migrated_dir.txt"

if (-not (Test-Path $l5StateFile)) { throw "FATAL: State file '.l5_test_dir.txt' not found. Cannot perform cleanup." }
$corruptedExpDir = Get-Content -Path $l5StateFile | Select-Object -Last 1

# --- B. Delete Test-Specific Artifacts ---
Write-Host "Cleaning up migration test artifacts..." -ForegroundColor Yellow

# Delete original corrupted directory
if (Test-Path $corruptedExpDir) {
    Write-Host "  - Removing original corrupted experiment: $(Resolve-Path $corruptedExpDir -Relative)"
    Remove-Item -Path $corruptedExpDir -Recurse -Force
}

# Delete new migrated directory
if (Test-Path $l5MigratedStateFile) {
    $migratedDir = Get-Content -Path $l5MigratedStateFile | Select-Object -Last 1
    if (Test-Path $migratedDir) {
        Write-Host "  - Removing new migrated experiment: $(Resolve-Path $migratedDir -Relative)"
        Remove-Item -Path $migratedDir -Recurse -Force
    }
}

# --- C. Use Layer 4 Cleanup to Restore Project State ---
Write-Host "`nRestoring project to original state..." -ForegroundColor Yellow
& (Join-Path $ProjectRoot "tests/testing_harness/layer4_step3_cleanup.ps1")

# --- D. Final Cleanup ---
Remove-Item $l5StateFile, $l5MigratedStateFile -Force -ErrorAction SilentlyContinue
Write-Host "`nMigration workflow test environment cleaned up successfully." -ForegroundColor Green
Write-Host ""