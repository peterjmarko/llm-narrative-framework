#!/usr/bin/env pwsh
[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [switch]$Interactive
)

$ErrorActionPreference = 'Stop'

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"
$C_RED = "`e[91m"
$C_ORANGE = "`e[38;5;208m"
$C_YELLOW = "`e[93m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"

# --- Helper Functions ---
function Get-ProjectRoot {
    param($StartPath)
    $currentDir = $StartPath
    while ($currentDir -ne $null -and $currentDir -ne "") {
        if (Test-Path (Join-Path $currentDir "pyproject.toml")) { return $currentDir }
        $currentDir = Split-Path -Parent -Path $currentDir
    }
    throw "FATAL: Could not find project root (pyproject.toml) by searching up from '$StartPath'."
}

$ProjectRoot = Get-ProjectRoot -StartPath $PSScriptRoot
$SandboxParentDir = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $SandboxParentDir "large_seed_sandbox"
$largeSeedDir = Join-Path $ProjectRoot "tests/assets/large_seed"

Write-Host "`n--- Running Large-Scale Algorithm Validation ---" -ForegroundColor Magenta
Write-Host "Validates core data filtering and selection algorithms at scale." -ForegroundColor Yellow

if (-not (Test-Path (Join-Path $largeSeedDir "data/sources/adb_raw_export.txt"))) {
    Write-Host "`nSKIPPED: Large seed data for algorithm validation not found at 'tests/assets/large_seed'." -ForegroundColor Yellow
    Write-Host "Please see TESTING.md for instructions on how to generate and place these assets." -ForegroundColor Yellow
    exit 0
}

try {
    # --- 1. Setup ---
    Write-Host "`n--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
    if (Test-Path $SandboxDir) { Remove-Item -Path $SandboxDir -Recurse -Force }
    @("data/sources", "data/reports", "data/intermediate", "data/foundational_assets") | ForEach-Object {
        New-Item -Path (Join-Path $SandboxDir $_) -ItemType Directory -Force | Out-Null
    }
    $displayPath = (Resolve-Path $SandboxDir -Relative).TrimStart(".\").Replace('\', '/')
    Write-Host "Validation sandbox created successfully in '$displayPath'." -ForegroundColor Green

    # --- 2. Execute: Validate Eligible Candidate Selection ---
    $stepHeader4a = ">>> Validate Eligible Candidate Logic <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader4a -ForegroundColor Cyan; Write-Host "Validates the deterministic filtering logic using a large seed dataset." -ForegroundColor Cyan
    Copy-Item -Path (Join-Path $largeSeedDir "data/sources/adb_raw_export.txt") -Destination (Join-Path $SandboxDir "data/sources/")
    Copy-Item -Path (Join-Path $largeSeedDir "data/reports/adb_validation_report.csv") -Destination (Join-Path $SandboxDir "data/reports/")
    
    $eligibleCandidatesScript = Join-Path $ProjectRoot "src/select_eligible_candidates.py"
    & pdm run python -u $eligibleCandidatesScript --sandbox-path $SandboxDir
    
    $largeInput4a = (Get-Content (Join-Path $SandboxDir "data/sources/adb_raw_export.txt") | Select-Object -Skip 1).Length
    $largeOutput4a = Join-Path $SandboxDir "data/intermediate/adb_eligible_candidates.txt"
    if (-not (Test-Path $largeOutput4a)) { throw "Eligible candidate logic test failed: Output file was not created." }
    $largeOutputCount4a = (Get-Content $largeOutput4a | Select-Object -Skip 1).Length
    if ($largeOutputCount4a -ge $largeInput4a) { throw "Eligible candidate logic test failed: The number of eligible candidates ($largeOutputCount4a) was not less than the input ($largeInput4a)." }
    Write-Host "`n  -> ✓ Eligible Candidate Logic: Successfully validated ($largeInput4a -> $largeOutputCount4a subjects)." -ForegroundColor Green

    # --- 3. Execute: Validate Final Candidate Cutoff Logic ---
    $stepHeader7a = "`n>>> Validate Cutoff Logic <<<"
    Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray; Write-Host $stepHeader7a -ForegroundColor Cyan; Write-Host "Validates the subject cutoff algorithm using a large seed dataset." -ForegroundColor Cyan
    Copy-Item -Path (Join-Path $largeSeedDir "data/foundational_assets/eminence_scores.csv") -Destination (Join-Path $SandboxDir "data/foundational_assets/")
    Copy-Item -Path (Join-Path $largeSeedDir "data/foundational_assets/ocean_scores.csv") -Destination (Join-Path $SandboxDir "data/foundational_assets/")
    Copy-Item -Path (Join-Path $ProjectRoot "tests/assets/data/foundational_assets/country_codes.csv") -Destination (Join-Path $SandboxDir "data/foundational_assets/")

    $selectCandidatesScript = Join-Path $ProjectRoot "src/select_final_candidates.py"
    & pdm run python $selectCandidatesScript --sandbox-path $SandboxDir --plot

    $largeInput7a = (Get-Content (Join-Path $SandboxDir "data/foundational_assets/ocean_scores.csv") | Select-Object -Skip 1).Length
    $largeOutput7a = Join-Path $SandboxDir "data/intermediate/adb_final_candidates.txt"
    if (-not (Test-Path $largeOutput7a)) { throw "Cutoff logic test failed: Output file was not created." }
    $largeOutputCount7a = (Get-Content $largeOutput7a | Select-Object -Skip 1).Length
    if ($largeOutputCount7a -ge $largeInput7a) { throw "Cutoff logic test failed: The number of final candidates ($largeOutputCount7a) was not less than the input ($largeInput7a)." }
    Write-Host "`n  -> ✓ Cutoff Logic: Successfully validated ($largeInput7a -> $largeOutputCount7a subjects)." -ForegroundColor Green

    Write-Host "`nSUCCESS: Large-scale algorithm validation completed successfully." -ForegroundColor Green
}
catch {
    Write-Host "`nERROR: Large-scale algorithm validation failed." -ForegroundColor Red
    Write-Host "$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    # --- 4. Cleanup ---
    Write-Host "`n--- Phase 3: Automated Cleanup ---" -ForegroundColor Cyan
    if (Test-Path $SandboxDir) {
        $ProgressPreference = 'SilentlyContinue'
        Remove-Item -Path $SandboxDir -Recurse -Force
        $ProgressPreference = 'Continue'
        Write-Host "Validation sandbox removed." -ForegroundColor Green
    }
}