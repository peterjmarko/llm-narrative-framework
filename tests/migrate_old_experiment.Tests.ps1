# Filename: migrate_old_experiment.Tests.ps1

# Import the shared test harness
. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Mock Functions ---
$script:FailOnStep = $null
$script:ArtifactsToClean = @()
function Invoke-PythonScript {
    param([string]$StepName)
    if ($script:FailOnStep -and $StepName -like "*$($script:FailOnStep)*") { throw "Simulated failure" }
}
function Clean-Artifacts-Mock {
    if ($script:FailOnStep -and "3/4" -like "*$($script:FailOnStep)*") { throw "Simulated failure" }
}

# --- Main Logic to Test (Mirrors migrate_old_experiment.ps1) ---
function Invoke-Migration {
    Invoke-PythonScript -StepName "1/4: Patch Configs"
    Invoke-PythonScript -StepName "2/4: Rebuild Reports"
    Clean-Artifacts-Mock
    Invoke-PythonScript -StepName "4/4: Final Reprocess"
    return "SUCCESS"
}

# --- TEST CASES (Restored to original count of 4) ---

Run-Test "Successful migration" {
    $script:FailOnStep = $null
    Invoke-Migration
} @("SUCCESS")

Run-Test "Failure during step 1 (Patch Configs)" {
    $script:FailOnStep = "1/4"
    try { Invoke-Migration; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

Run-Test "Failure during step 3 (Clean Artifacts)" {
    $script:FailOnStep = "3/4"
    try { Invoke-Migration; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

Run-Test "Failure during step 4 (Final Reprocess)" {
    $script:FailOnStep = "4/4"
    try { Invoke-Migration; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

# --- Finalize the run ---
Finalize-Test-Run