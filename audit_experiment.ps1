#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: audit_experiment.ps1

<#
.SYNOPSIS
    Provides a read-only, detailed completeness report for an experiment.

.DESCRIPTION
    This script is a simple wrapper that calls 'experiment_manager.py' with the
    --verify-only flag. It audits the specified experiment directory and prints a
    comprehensive report without making any changes.

.PARAMETER TargetDirectory
    The path to the experiment directory to audit. This is a mandatory parameter.

.PARAMETER Verbose
    Enables verbose output from the verification process.

.EXAMPLE
    # Run a standard audit on an experiment.
    .\audit_experiment.ps1 -TargetDirectory "output/reports/My_Experiment"

.EXAMPLE
    # Run a detailed audit.
    .\audit_experiment.ps1 "output/reports/My_Experiment" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to audit.")]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [switch]$Verbose
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

# --- Main Script Logic ---
try {
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop

    $scriptName = "src/experiment_manager.py"
    $arguments = @("--verify-only", $ResolvedPath)
    if ($Verbose) {
        $arguments += "--verbose"
    }

    $finalArgs = $prefixArgs + $scriptName + $arguments

    # No need for a verbose summary; this script's purpose is to show the output.
    & $executable $finalArgs

    if ($LASTEXITCODE -ne 0) {
        throw "ERROR: Audit process failed with exit code ${LASTEXITCODE}."
    }
}
catch {
    Write-Host "`nAUDIT FAILED" -ForegroundColor Red
    Write-Error $_.Exception.Message
    exit 1
}