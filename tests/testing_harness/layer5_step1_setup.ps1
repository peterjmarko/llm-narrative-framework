# Filename: tests/testing_harness/layer5_step1_setup.ps1
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
Remove-Item $l5StateFile -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "--- Layer 5: Migration Workflow Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 1: Automated Setup ---" -ForegroundColor Cyan
Write-Host "This will create a deliberately corrupted experiment that requires migration."

# --- A. Use Layer 4 Setup to Create a Clean Environment ---
Write-Host "`nInitializing a clean test environment..." -ForegroundColor Yellow
& (Join-Path $ProjectRoot "tests/testing_harness/layer4_step1_setup.ps1")

# Create an empty L4 state file to satisfy the L4 cleanup script's dependency
$l4StateFile = Join-Path $ProjectRoot "tests/testing_harness/.l4_test_dir.txt"
New-Item -Path $l4StateFile -ItemType File -Force | Out-Null

# --- B. Create a Base Experiment to Corrupt ---
Write-Host "`nGenerating a small, valid experiment to serve as the corruption target..." -ForegroundColor Yellow
. .\.venv\Scripts\Activate.ps1
.\new_experiment.ps1 -ErrorAction Stop
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }

$expDir = Get-ChildItem -Path "output/new_experiments" -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
Add-Content -Path $l5StateFile -Value $expDir.FullName
$relativeExpDir = Resolve-Path -Path $expDir.FullName -Relative

Write-Host "`nSuccessfully created base experiment: $relativeExpDir" -ForegroundColor Green

# --- C. Deliberately Corrupt the Experiment ---
Write-Host "`n--- Layer 5: Corrupting Experiment ---" -ForegroundColor Magenta
Write-Host "`nCorrupting experiment to trigger migration requirement..." -ForegroundColor Yellow
$runDir = Get-ChildItem -Path $expDir.FullName -Directory "run_*" | Select-Object -First 1
if (-not $runDir) { throw "FATAL: Could not find a 'run_*' directory in the new experiment." }

# Corruption Action 1: Delete a response file (Error 1)
$responseFile = Get-ChildItem -Path (Join-Path $runDir.FullName "session_responses") -Filter "*.txt" | Select-Object -First 1
if ($responseFile) {
    Write-Host "  - Deleting response file: $($responseFile.Name)"
    Remove-Item -Path $responseFile.FullName -Force
} else {
    throw "FATAL: Could not find a response file to delete for the corruption step."
}

# Corruption Action 2: Delete the archived config (Error 2)
$archivedConfigFile = Join-Path $runDir.FullName "config.ini.archived"
if (Test-Path $archivedConfigFile) {
    Write-Host "  - Deleting archived config: $(Split-Path $archivedConfigFile -Leaf)"
    Remove-Item -Path $archivedConfigFile -Force
} else {
    throw "FATAL: Could not find 'config.ini.archived' to delete for the corruption step."
}

Write-Host "`nMigration test environment created successfully." -ForegroundColor Green
Write-Host "The experiment at '$relativeExpDir' is now corrupted and ready for testing."
Write-Host "Your next action is Step 2: Execute the Test Workflow." -ForegroundColor Yellow
Write-Host ""