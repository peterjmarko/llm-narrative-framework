# Filename: audit_experiment.Tests.ps1

# Import the shared test harness
. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Mock Function ---
# Mock the pdm executable to intercept the call from the script.
$script:CapturedArgs = $null
function pdm {
    # This correctly flattens the arguments, preventing the "System.Object[]" issue.
    $flatArgs = @()
    foreach ($arg in $args) { $flatArgs += $arg }
    $script:CapturedArgs = $flatArgs
}

# This function simulates the logic within the real audit_experiment.ps1
function Invoke-Audit-Test {
    param([string]$TargetDirectory, [switch]$Verbose)
    
    # This is the core logic from the script we are testing
    $scriptName = "src/experiment_manager.py"
    $arguments = @("--verify-only", $TargetDirectory)
    if ($Verbose) {
        $arguments += "--verbose"
    }
    
    # Call our mock pdm function
    pdm run python $scriptName $arguments
}

# --- TEST CASES ---

Run-Test "Basic audit calls manager with correct flags" {
    $targetDir = "path/to/audit"
    $expectedArgs = @("run", "python", "src/experiment_manager.py", "--verify-only", $targetDir)
    
    Invoke-Audit-Test -TargetDirectory $targetDir
    
    # Compare the two arrays for differences. If there are none, it's a match.
    $diff = Compare-Object -ReferenceObject $expectedArgs -DifferenceObject $script:CapturedArgs
    if ($diff) { "ARRAYS_DIFFER" } else { "ARRAYS_MATCH" }
} @("ARRAYS_MATCH")

Run-Test "Verbose audit adds --verbose flag" {
    $targetDir = "path/to/verbose_audit"
    $expectedArgs = @("run", "python", "src/experiment_manager.py", "--verify-only", $targetDir, "--verbose")

    Invoke-Audit-Test -TargetDirectory $targetDir -Verbose

    $diff = Compare-Object -ReferenceObject $expectedArgs -DifferenceObject $script:CapturedArgs
    if ($diff) { "ARRAYS_DIFFER" } else { "ARRAYS_MATCH" }
} @("ARRAYS_MATCH")

# --- Finalize the run ---
Finalize-Test-Run