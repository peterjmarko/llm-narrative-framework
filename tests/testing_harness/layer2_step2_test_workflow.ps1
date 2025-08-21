# Filename: tests/testing_harness/layer2_step2_test_workflow.ps1
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

$testDir = "temp_mock_test"
if (-not (Test-Path $testDir)) { throw "FATAL: Test directory '$testDir' not found. Please run Step 1 first." }

Write-Host ""
Write-Host "--- Layer 2: Data Pipeline Orchestration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 2: Execute the Test Workflow ---" -ForegroundColor Cyan

. .\.venv\Scripts\Activate.ps1
Set-Location $testDir

try {
    Write-Host "`n--- Running initial pipeline (will pause for first manual step) ---" -ForegroundColor Yellow
    .\prepare_data.ps1

    Write-Host "`n--- Simulating first manual step (creating sf_chart_export.csv) ---" -ForegroundColor Yellow
    New-Item -Path "data/foundational_assets/sf_chart_export.csv" -ItemType File -Force | Out-Null
    .\prepare_data.ps1

    Write-Host "`n--- Simulating second manual step (creating sf_delineations_library.txt) ---" -ForegroundColor Yellow
    New-Item -Path "data/foundational_assets/sf_delineations_library.txt" -ItemType File -Force | Out-Null
    .\prepare_data.ps1

    Write-Host "`n--- Verifying final output... ---" -ForegroundColor Yellow
    if (Test-Path -Path "personalities_db.txt") {
        Write-Host "`nPASS: Orchestrator logic test completed successfully." -ForegroundColor Green
    } else {
        Write-Host "`nFAIL: Final output file was not created." -ForegroundColor Red
    }
} finally {
    Set-Location $ProjectRoot
    if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
}

Write-Host "`nTest workflow complete. You may now inspect the artifacts." -ForegroundColor Green
Write-Host "This completes Step 2. Proceed to Step 3 for cleanup." -ForegroundColor Yellow
Write-Host ""