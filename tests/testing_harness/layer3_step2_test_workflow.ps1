#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 2: Execute the Test Workflow ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer3_sandbox"

if (-not (Test-Path $SandboxDir)) { throw "FATAL: Test sandbox not found. Please run Step 1 first." }

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 2: Execute the Test Workflow ---" -ForegroundColor Cyan

try {
    Set-Location $SandboxDir
    
    Write-Host "`n--- Running the full data preparation pipeline... ---" -ForegroundColor Yellow
    # The pipeline will be run with the -Force flag to ensure it is non-interactive
    # and re-validates every step against the current source code, rather than just
    # skipping based on file existence.
    & (Join-Path $ProjectRoot "prepare_data.ps1") -Force
    if ($LASTEXITCODE -ne 0) { throw "prepare_data.ps1 failed." }

    Write-Host "`n--- Verifying final output... ---" -ForegroundColor Cyan
    $finalDbPath = "data/personalities_db.txt"
    if (-not (Test-Path $finalDbPath)) {
        throw "FAIL: The final 'personalities_db.txt' file was not created."
    }
    
    $lineCount = (Get-Content $finalDbPath | Measure-Object -Line).Lines
    if ($lineCount -ne 4) { # Header + 3 subjects
        throw "FAIL: The final 'personalities_db.txt' has an incorrect number of lines (Expected 4, Found $lineCount)."
    }
    
    Write-Host "`nSUCCESS: The data pipeline integration test completed successfully." -ForegroundColor Green
    Write-Host "The final 'personalities_db.txt' was created with the correct number of records."
    Write-Host "Inspect the artifacts, then run Step 3 to clean up."
    Write-Host ""
}
catch {
    Write-Host "`nERROR: Layer 3 test workflow failed.`n$($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
finally {
    Set-Location $ProjectRoot
}