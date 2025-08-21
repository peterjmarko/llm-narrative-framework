# Filename: tests/testing_harness/layer5_step2_test_workflow.ps1
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

# --- State File Management ---
$l5StateFile = Join-Path $ProjectRoot "tests/testing_harness/.l5_test_dir.txt"
$l5MigratedStateFile = Join-Path $ProjectRoot "tests/testing_harness/.l5_migrated_dir.txt"
if (-not (Test-Path $l5StateFile)) { throw "FATAL: State file '.l5_test_dir.txt' not found. Please run Step 1 first." }
$corruptedExpDir = Get-Content -Path $l5StateFile | Select-Object -Last 1
Remove-Item $l5MigratedStateFile -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "--- Layer 5: Migration Workflow Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 2: Execute the Migration Test Workflow ---" -ForegroundColor Cyan
$relativeCorruptedDir = Resolve-Path -Path $corruptedExpDir -Relative
Write-Host "Targeting corrupted experiment: $relativeCorruptedDir" -ForegroundColor Yellow

# --- a. Activate venv ---
. .\.venv\Scripts\Activate.ps1

# --- b. Audit the corrupted experiment ---
Write-Host "`n--- Auditing corrupted experiment (should recommend MIGRATION) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -ExperimentDirectory $corruptedExpDir

# --- c. Run the migration script ---
Write-Host "`n--- Running migrate_experiment.ps1 ---" -ForegroundColor Cyan
.\migrate_experiment.ps1 -ExperimentDirectory $corruptedExpDir -NonInteractive -ErrorAction Stop

# --- d. Find the new migrated directory ---
$migratedDir = Get-ChildItem -Path "output/migrated_experiments" -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
if (-not $migratedDir) { throw "FATAL: Could not find the new migrated experiment directory." }
Add-Content -Path $l5MigratedStateFile -Value $migratedDir.FullName
$relativeMigratedDir = Resolve-Path -Path $migratedDir.FullName -Relative
Write-Host "`n--- Migration created new experiment: $relativeMigratedDir ---" -ForegroundColor Yellow

# --- e. Run a final audit on the NEW directory ---
Write-Host "`n--- Final audit on migrated result (should be VALIDATED) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -ExperimentDirectory $migratedDir.FullName -ErrorAction Stop

# --- f. Deactivate venv ---
Write-Host "`n--- Migration test workflow complete. You may now inspect the artifacts. ---" -ForegroundColor Green
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
Write-Host "This completes Step 2. You can re-run for debugging or proceed to Step 3 for cleanup." -ForegroundColor Yellow
Write-Host ""