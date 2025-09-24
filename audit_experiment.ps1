#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
# Copyright (C) 2025 Peter J. Marko
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
    Provides a read-only, detailed completeness report for an existing experiment.

.DESCRIPTION
    This script is the primary diagnostic tool for CHECKING the status of any
    experiment. It calls the `experiment_auditor.py` backend to perform a
    comprehensive, read-only audit and prints a detailed report, including a
    final recommendation for the next appropriate action (e.g., 'fix_experiment.ps1'
    or 'migrate_experiment.ps1').

    It never makes any changes to the data. The full, detailed output is also
    saved to an 'experiment_audit_log.txt' file inside the target directory.

.PARAMETER ExperimentDirectory
    The path to the experiment directory to audit. This is a mandatory parameter.

.PARAMETER Verbose
    Enables verbose output from the verification process.

.EXAMPLE
    # Run a standard audit on an experiment.
    .\audit_experiment.ps1 -ExperimentDirectory "output/reports/My_Experiment"

.EXAMPLE
    # Run a detailed audit.
    .\audit_experiment.ps1 "output/reports/My_Experiment" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $false, HelpMessage = "Path to a specific config.ini file to use for this operation.")]
    [Alias('config-path')]
    [string]$ConfigPath,

    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to audit.")]
    [string]$ExperimentDirectory
)

function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

$ProjectRoot = Get-ProjectRoot
$scriptExitCode = 0
$LogFilePath = $null

try {
    if (-not (Test-Path $ExperimentDirectory -PathType Container)) { throw "Directory '$ExperimentDirectory' does not exist." }
    $ResolvedPath = Resolve-Path -Path $ExperimentDirectory -ErrorAction Stop
    $scriptName = Join-Path $ProjectRoot "src/experiment_auditor.py"
    
    $pythonScriptArgs = @($ResolvedPath, "--force-color")
    if ($PSBoundParameters['Verbose']) { $pythonScriptArgs += "--verbose" }
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $pythonScriptArgs += "--config-path", $ConfigPath }

    $LogFilePath = Join-Path $ResolvedPath "experiment_audit_log.txt"
    $relativeLogPath = Join-Path (Resolve-Path -Path $ExperimentDirectory -Relative) (Split-Path $LogFilePath -Leaf)
    Write-Host "`nThe audit log will be saved to: $relativeLogPath"
    if (Test-Path $LogFilePath) { Remove-Item $LogFilePath -Force }

    $finalArgs = @("python", $scriptName) + $pythonScriptArgs
    & pdm run $finalArgs *>&1 | Tee-Object -FilePath $LogFilePath
    $scriptExitCode = $LASTEXITCODE
} catch {
    Write-Host "`nAUDIT FAILED: $($_.Exception.Message)" -ForegroundColor Red
    $scriptExitCode = 1
} finally {
    if ($LogFilePath -and (Test-Path -LiteralPath $LogFilePath)) {
        try { $c = Get-Content -Path $LogFilePath -Raw; $c = $c -replace "`e\[[0-9;]*m", ''; Set-Content -Path $LogFilePath -Value $c.Trim() -Force } catch {}
        $relativeLogPath = Resolve-Path -Path $LogFilePath -Relative
        Write-Host "`nLog saved to:`n$relativeLogPath`n" -ForegroundColor Cyan
    }
}
exit $scriptExitCode

# === End of audit_experiment.ps1 ===
