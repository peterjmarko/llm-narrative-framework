# Filename: tests/update_experiment.Tests.ps1

# Import the shared test harness
. (Join-Path $PSScriptRoot "Test-Harness.ps1")

# --- Test-Specific Function Definitions ---

# This function mirrors the argument-building logic inside update_experiment.ps1
function Invoke-Update-Experiment {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$TargetDirectory,

        [string]$Notes
    )

    $prefixArgs = "run", "python" # Assume PDM for testing consistency
    $pythonScriptPath = "src/experiment_manager.py"

    $pythonArgs = @(
        $pythonScriptPath,
        '--reprocess',
        $TargetDirectory
    )

    if ($PSBoundParameters.ContainsKey('Notes')) {
        $pythonArgs += '--notes', $Notes
    }

    # Check for the common parameter 'Verbose' without explicitly defining it.
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += '--verbose'
    }

    # Return the final arguments that would be passed to the external command.
    return $prefixArgs + $pythonArgs
}


# --- TEST CASES ---

# Test 1: Basic call with only required directory
Run-Test "should call manager with --reprocess flag and target directory" {
    Invoke-Update-Experiment -TargetDirectory "output/my_dir"
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--reprocess",
    "output/my_dir"
)

# Test 2: Call with --notes
Run-Test "should add --notes flag when provided" {
    Invoke-Update-Experiment -TargetDirectory "output/my_dir" -Notes "Test Note"
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--reprocess",
    "output/my_dir",
    "--notes",
    "Test Note"
)

# Test 3: Call with --verbose
Run-Test "should add --verbose flag when specified" {
    Invoke-Update-Experiment -TargetDirectory "output/my_dir" -Verbose
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--reprocess",
    "output/my_dir",
    "--verbose"
)

# Test 4: Call with all parameters
Run-Test "should handle a combination of all parameters correctly" {
    Invoke-Update-Experiment -TargetDirectory "output/my_dir" -Notes "Combo Test" -Verbose
} @(
    "run", "python",
    "src/experiment_manager.py",
    "--reprocess",
    "output/my_dir",
    "--notes",
    "Combo Test",
    "--verbose"
)

# --- Finalize the run ---
Finalize-Test-Run