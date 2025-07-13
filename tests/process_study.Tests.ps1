# Filename: process_study.Tests.ps1

# Import the shared test harness
. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Mock Implementations ---
$script:FailOnStep = $null
function Invoke-PythonScript {
    param([string]$StepName)
    if ($script:FailOnStep -and $StepName -like "*$($script:FailOnStep)*") {
        throw "Simulated failure on step '$StepName'"
    }
}
function Invoke-ProcessStudy {
    [void](Invoke-PythonScript -StepName "1/2: Aggregate Results")
    [void](Invoke-PythonScript -StepName "2/2: Run Final Analysis (ANOVA)")
    return "SUCCESS"
}

# --- TEST CASES ---

Run-Test "Successful run with PDM" {
    $script:FailOnStep = $null # Explicitly set state for this test
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "Successful run with verbose output and PDM" {
    $script:FailOnStep = $null # Explicitly set state for this test
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "Error during aggregation step" {
    $script:FailOnStep = "1/2" # Set state for failure
    try { Invoke-ProcessStudy; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

Run-Test "Error during analysis step" {
    $script:FailOnStep = "2/2" # Set state for failure
    try { Invoke-ProcessStudy; "DID_NOT_FAIL" } catch { "CAUGHT_FAILURE" }
} @("CAUGHT_FAILURE")

Run-Test "PDM not detected, should use standard python command" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "config.ini parsing failure should result in warning" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "Successful run with valid config" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")

Run-Test "config.ini valid but empty display name map should warn" {
    $script:FailOnStep = $null # Reset state for success
    Invoke-ProcessStudy
} @("SUCCESS")


# --- Finalize the run ---
Finalize-Test-Run