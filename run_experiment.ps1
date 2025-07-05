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

[CmdletBinding()]
param(
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

# Build the argument list for the Python script dynamically.
$pythonArgs = @("src/replication_manager.py")
if ($PSBoundParameters.ContainsKey('StartRep')) {
    $pythonArgs += "--start-rep", $StartRep
}
if ($PSBoundParameters.ContainsKey('EndRep')) {
    $pythonArgs += "--end-rep", $EndRep
}
if ($PSBoundParameters.ContainsKey('Notes')) {
    $pythonArgs += "--notes", $Notes
}

# Pass the --verbose flag to the Python script only if the PowerShell -Verbose switch is used.
# This aligns with replication_manager.py, which is quiet by default.
if ($PSBoundParameters.ContainsKey('Verbose')) {
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

# === End of run_experiment.ps1 ===