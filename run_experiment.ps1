#!/usr/bin/env pwsh
# -*-
# Filename: run_experiment.ps1

<#
.SYNOPSIS
    Main entry point for the experiment pipeline. Runs a full batch of replications
    with clean, high-level output by default.

.DESCRIPTION
    This script is the main entry point for running a full experimental batch. It calls
    the `replication_manager.py` script, which contains the core logic for the run.

    By default, this launcher runs in a "quiet" mode, showing only major progress
    headers and a final summary for each replication. This is ideal for standard runs.

    Use the -Verbose switch to see detailed, real-time logs from all underlying
    Python scripts, which is useful for debugging.

.PARAMETER StartRep
    Optional. The starting replication number (inclusive). Defaults to 1.

.PARAMETER EndRep
    Optional. The ending replication number (inclusive). Defaults to the value
    in config.ini.

.PARAMETER Verbose
    Optional. Use this switch to enable verbose output, showing detailed logs
    from all child scripts.

.EXAMPLE
    # Run the full batch with standard (quiet) output
    .\run_experiment.ps1

.EXAMPLE
    # Run the full batch with detailed logging for debugging
    .\run_experiment.ps1 -Verbose

.EXAMPLE
    # Run only replications 5 through 10
    .\run_experiment.ps1 -StartRep 5 -EndRep 10
#>

# Load the testable argument-building logic from a separate file.
. "$PSScriptRoot/src/ArgBuilder.ps1"

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
        [string]$Notes # Removed explicit [switch]$Verbose here, as [CmdletBinding()] provides it
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

    # Build the argument list by calling the simple, testable helper function.
    # We must manually copy the special $PSBoundParameters dictionary to a regular
    # hashtable that we can modify.
    $helperParams = @{}
    foreach ($key in $PSBoundParameters.Keys) {
        $helperParams[$key] = $PSBoundParameters[$key]
    }

    # Now, safely translate the user-facing -Verbose parameter to the internal -ShowDetails parameter.
    # This logic correctly handles the implicit -Verbose common parameter.
    if ($helperParams.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) { # Added -and $PSBoundParameters['Verbose']
        $helperParams.Remove('Verbose')
        $helperParams['ShowDetails'] = $true
    }
    $pythonArgs = Build-ExperimentArgs @helperParams

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
# when the script is run directly (not dot-sourced) AND it is not running within a Pester context.
# A Pester context is detected by checking for $PesterContext variable or by checking the call stack.
$isPesterContext = $false
try {
    # Check for $PesterContext variable (standard Pester v5+ method)
    if (Get-Variable -Name 'PesterContext' -ErrorAction SilentlyContinue) {
        $isPesterContext = $true
    }
    # Fallback: Check the call stack for Pester modules, if $PesterContext isn't reliable
    elseif ($MyInvocation.ScriptStackTrace -match "Pester.psm1") {
        $isPesterContext = $true
    }
}
catch {} # Suppress errors if variables/stacks are not available in strange contexts

# The primary invocation guard for the script's main execution.
if (($MyInvocation.InvocationName -ne '.') -and (-not $isPesterContext)) {
    # Call the helper function to run the main logic, passing all original script parameters
    _Run-ScriptMain @PSBoundParameters
}
# === End of run_experiment.ps1 ===