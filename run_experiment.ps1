#!/usr/bin/env pwsh
# -*-
# Filename: run_experiment.ps1

<#
.SYNOPSIS
    Main entry point for the experiment pipeline. Runs a full batch of replications
    with clean, high-level output by default.

.DESCRIPTION
    This script is the main entry point for running a full experimental batch. It calls
    the `experiment_manager.py` script, which contains the core logic for the run.

    By default, this launcher runs in a "quiet" mode, showing only major progress
    headers and a final summary for each replication. This is ideal for standard runs.

    Use the -Verbose switch to see detailed, real-time logs from all underlying
    Python scripts, which is useful for debugging.

.PARAMETER TargetDirectory
    Optional. The target directory for the experiment. Can be an existing directory
    or one to be created. If not provided, a new timestamped directory is created
    in the `output/` folder. This is the first positional parameter.

.PARAMETER Notes
    Optional. A string of notes to be included in the experiment's final report
    and logs for documentation purposes.

.PARAMETER StartRep
    Optional. The starting replication number (inclusive). Defaults to 1.

.PARAMETER EndRep
    Optional. The ending replication number (inclusive). Defaults to the value
    in config.ini.

.PARAMETER Verbose
    Optional. Use this switch to enable verbose output, showing detailed logs
    from all child scripts.

.EXAMPLE
    # Run the full batch with standard (quiet) output.
    # Results will be in a new timestamped folder.
    .\run_experiment.ps1

.EXAMPLE
    # Run a full batch into a specific directory with descriptive notes.
    .\run_experiment.ps1 -TargetDirectory "output/reports/My_Llama3_Study" -Notes "First run with Llama 3"

.EXAMPLE
    # Run only replications 5 through 10 with detailed logging for debugging.
    .\run_experiment.ps1 -StartRep 5 -EndRep 10 -Verbose
#>

# This is the main execution function. It uses [CmdletBinding()] to be a robust
# "advanced function" for command-line use.
function Invoke-Experiment {
    [CmdletBinding()] # Keep this, it adds common parameters like -Verbose
    param(
        # The target directory for the experiment. Can be an existing directory
        # or one to be created. This is the first positional parameter.
        [Parameter(Position=0, Mandatory=$false)]
        [string]$TargetDirectory,

        # Optional starting replication number.
        [Parameter(Mandatory=$false)]
        [int]$StartRep,

        # Optional ending replication number.
        [Parameter(Mandatory=$false)]
        [int]$EndRep,

        # Optional notes for the run.
        [Parameter(Mandatory=$false)]
        [string]$Notes
    )

    # --- Auto-detect execution environment ---
    $executable = "python"
    $prefixArgs = @()
    if (Get-Command pdm -ErrorAction SilentlyContinue) {
        Write-Host "PDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
        $executable = "pdm"
        $prefixArgs = "run", "python"
    }
    else {
        Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
    }

    # Ensure console output uses UTF-8 to correctly display any special characters.
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    Write-Host "--- Launching Python Batch Runner ---" -ForegroundColor Green

    # Construct the Python arguments directly here (logic formerly in ArgBuilder.ps1).
    $pythonArgs = @("src/experiment_manager.py")
    if (-not [string]::IsNullOrEmpty($TargetDirectory)) { $pythonArgs += $TargetDirectory }
    if ($StartRep) { $pythonArgs += "--start-rep", $StartRep }
    if ($EndRep) { $pythonArgs += "--end-rep", $EndRep }
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
    
    # Translate the common -Verbose parameter to the internal --verbose for the Python script.
    # $PSBoundParameters contains common parameters when CmdletBinding is used.
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) {
        $pythonArgs += "--verbose"
    }

    # Combine prefix arguments with the script and its arguments
    $finalArgs = $prefixArgs + $pythonArgs

    # Execute the command with its final argument list
    & $executable $finalArgs

    # Check the exit code from the Python script.
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n!!! The Python batch runner exited with an error. Check the output above. !!!" -ForegroundColor Red
    } else {
        Write-Host "`n--- PowerShell launcher script finished. ---"
    }
}

# Define a private helper function to encapsulate the actual script execution logic
# that should ONLY run when the script is invoked directly, not when dot-sourced.
function _Run-ScriptMain {
    param(
        [Parameter(ValueFromRemainingArguments=$true)]
        $ScriptArgs
    )
    # The actual call to Invoke-Experiment. We pass along the parameters the script received.
    Invoke-Experiment @ScriptArgs
}

# This invocation guard ensures the main execution logic is only triggered
# when the script is run directly (not dot-sourced).
if ($MyInvocation.InvocationName -ne '.') {
    # Call the helper function to run the main logic, passing all original script parameters
    _Run-ScriptMain @PSBoundParameters
}
# === End of run_experiment.ps1 ===
