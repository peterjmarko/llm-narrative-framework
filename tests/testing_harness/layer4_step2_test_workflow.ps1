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
Write-Host "--- Layer 4: Main Workflow Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 2: Execute the Test Workflow ---" -ForegroundColor Cyan

# a. Activate the venv from the project root
. .\.venv\Scripts\Activate.ps1

# b. Run a new experiment from scratch.
Write-Host "`n--- Running new_experiment.ps1 ---" -ForegroundColor Cyan
.\new_experiment.ps1

# c. Find the new experiment directory and append its path to the state file
$expDir = Get-ChildItem -Path "output/new_experiments" -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
$stateFilePath = Join-Path $ProjectRoot "tests/testing_harness/.l4_test_dir.txt"
Add-Content -Path $stateFilePath -Value $expDir.FullName
$relativeExpDir = Resolve-Path -Path $expDir.FullName -Relative
Write-Host "`n--- Test will be performed on: $relativeExpDir ---" -ForegroundColor Yellow

# d. Audit the new experiment (should be VALIDATED)
Write-Host "`n--- Auditing new experiment (should be VALIDATED) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -ExperimentDirectory $expDir.FullName

# e. Intentionally "break" the experiment
Write-Host "`n--- Simulating failure by deleting a response file ---" -ForegroundColor Cyan
$runDir = Get-ChildItem -Path $script:expDir.FullName -Directory "run_*" | Select-Object -First 1
$responseFile = Get-ChildItem -Path (Join-Path $runDir.FullName "session_responses") -Include "llm_response_*.txt" -Recurse | Select-Object -First 1
if ($null -ne $responseFile) {
    Write-Host "Intentionally deleting response file: $($responseFile.Name)" -ForegroundColor Yellow
    Remove-Item -Path $responseFile.FullName
} else {
    Write-Warning "Could not find a response file to delete for the test. The experiment may have failed to generate one."
}

# f. Audit the broken experiment (should report NEEDS REPAIR)
Write-Host "`n--- Auditing broken experiment (should be NEEDS REPAIR) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -ExperimentDirectory $script:expDir.FullName

# g. Run the fix script to automatically repair the experiment
Write-Host "`n--- Running fix_experiment.ps1 ---" -ForegroundColor Cyan
.\fix_experiment.ps1 -ExperimentDirectory $script:expDir.FullName -NonInteractive

# h. Run a final audit to confirm the repair (should be VALIDATED again)
Write-Host "`n--- Final audit (should be VALIDATED) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -ExperimentDirectory $script:expDir.FullName

# i. Deactivate the virtual environment
Write-Host "`n--- Test workflow complete. You may now inspect the artifacts. ---" -ForegroundColor Green
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
Write-Host "This completes Step 2. You can re-run this script for debugging or proceed to Step 3 for cleanup." -ForegroundColor Yellow
Write-Host ""