#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: run_replications.ps1

# --- (Preamble and comments are unchanged) ---

#!/usr/bin/env pwsh
# -*-
# Filename: run_replications.ps1

<#
.SYNOPSIS
    A simple launcher script for the main Python-based batch runner.

.DESCRIPTION
    This script's primary role is to start the `run_batch.py` script, which contains
    the core logic for running a full experimental batch. All configuration is handled
    within Python via the `config.ini` file.
#>

[CmdletBinding()]
param(
    # Optional starting replication number.
    [Parameter(Mandatory=$false)]
    [int]$StartRep,

    # Optional ending replication number.
    [Parameter(Mandatory=$false)]
    [int]$EndRep
)

# Ensure console output uses UTF-8 to correctly display any special characters.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "--- Launching Python Batch Runner ---" -ForegroundColor Green

# Build the argument list for the Python script dynamically.
$pythonArgs = @("src/run_batch.py")
if ($PSBoundParameters.ContainsKey('StartRep')) {
    $pythonArgs += "--start-rep", $StartRep
}
if ($PSBoundParameters.ContainsKey('EndRep')) {
    $pythonArgs += "--end-rep", $EndRep
}

# Execute the main Python batch script with the specified arguments.
& python $pythonArgs

# Check the exit code from the Python script.
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n!!! The Python batch runner exited with an error. Check the output above. !!!" -ForegroundColor Red
} else {
    Write-Host "`n--- PowerShell launcher script finished. ---"
}