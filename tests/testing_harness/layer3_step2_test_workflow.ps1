# Filename: tests/testing_harness/layer3_step2_test_workflow.ps1
# NOTE: This is an interactive test that requires user input.
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

$testDir = "temp_integration_test"
if (-not (Test-Path $testDir)) { throw "FATAL: Test directory '$testDir' not found. Please run Step 1 first." }

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 2: Execute the Test Workflow (Interactive) ---" -ForegroundColor Cyan

. .\.venv\Scripts\Activate.ps1
Set-Location $testDir

try {
    # Part 1: Run the pipeline until it pauses for the manual step.
    Write-Host "`n--- Running pipeline (Part 1)... ---" -ForegroundColor Yellow
    Write-Host "This will take several minutes and will pause when it requires manual input."
    .\prepare_data.ps1

    # Part 2: Guide user through the manual step.
    $manualFile = "data/foundational_assets/sf_chart_export.csv"
    if (-not (Test-Path $manualFile)) {
        Write-Host "`n--- User Action Required ---" -ForegroundColor Yellow
        Write-Host "The pipeline has paused as expected. To continue the test:"
        Write-Host "1. Run the following command to simulate the manual step:"
        Write-Host "`n   .\tests\testing_harness\layer3_simulate_manual_step.ps1`n" -ForegroundColor White
        Write-Host "2. After the file is created, re-run this script (layer3_step2_test_workflow.ps1) to complete the test."
        exit
    }

    # Part 3: Run the pipeline again to completion.
    Write-Host "`n--- Manual step complete. Resuming pipeline (Part 2)... ---" -ForegroundColor Yellow
    .\prepare_data.ps1

    # Part 4: Verification
    Write-Host "`n--- Verifying final output... ---" -ForegroundColor Yellow
    if (-not (Test-Path -Path "personalities_db.txt")) {
        Write-Host "`nFAIL: personalities_db.txt was not created." -ForegroundColor Red
    } elseif ((Get-Content "personalities_db.txt" | Measure-Object -Line).Lines -ne 4) {
        Write-Host "`nFAIL: personalities_db.txt has the wrong number of lines." -ForegroundColor Red
    } else {
        Write-Host "`nPASS: The final personalities_db.txt was created successfully with 3 subject records." -ForegroundColor Green
    }

} finally {
    Set-Location $ProjectRoot
    if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
}

Write-Host "`nTest workflow complete. You may now inspect the artifacts." -ForegroundColor Green
Write-Host "This completes Step 2. Proceed to Step 3 for cleanup." -ForegroundColor Yellow
Write-Host ""