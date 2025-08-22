#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
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
# Filename: fix_experiment.ps1

<#
.SYNOPSIS
    Fixes or updates an existing experiment. It intelligently applies the safest,
    cheapest fix required.

.DESCRIPTION
    This is the main "fix-it" tool for any experiment. It automatically performs
    a full audit to diagnose the experiment's state and then applies the most
    appropriate action.

    - If it finds critical data issues (e.g., missing LLM responses), it performs
      a data-level REPAIR.
    - If it finds only outdated analysis files, it performs a safe, local
      analysis-only UPDATE.
    - If the experiment is already valid, it becomes interactive, allowing the user
      to force a specific action (e.g., a full data repair or analysis update).
    - If the experiment is found to be unfixable (i.e., requires migration), the
      script will halt with a clear message and recommendation.

.PARAMETER ExperimentDirectory
    (Required) The path to the existing experiment directory that needs to be
    fixed or updated.

.PARAMETER Notes
    A string of notes to embed in the reports and logs of any newly generated
    or repaired replications.

.PARAMETER StartRep
    For data repairs, the replication number to start from.

.PARAMETER EndRep
    For data repairs, the replication number to end at.

.PARAMETER Verbose
    A switch to enable detailed, real-time output from all underlying Python scripts.

.EXAMPLE
    # Automatically find and fix any issues in the specified experiment.
    .\fix_experiment.ps1 -ExperimentDirectory "output/studies/MyStudy/Exp1"

.EXAMPLE
    # Run on a valid experiment to bring up the interactive "force action" menu.
    .\fix_experiment.ps1 "output/studies/MyStudy/Exp1"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false, HelpMessage = "Path to a specific config.ini file to use for this operation.")]
    [Alias('config-path')]
    [string]$ConfigPath,
    
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to repair or update.")]
    [ValidateScript({
        if (-not (Test-Path $_ -PathType Container)) {
            throw "The specified ExperimentDirectory does not exist or is not a directory: $_"
        }
        return $true
    })]
    [string]$ExperimentDirectory,

    [Parameter(Mandatory = $false)]
    [int]$StartRep,

    [Parameter(Mandatory = $false)]
    [int]$EndRep,

    [Parameter(Mandatory = $false)]
    [string]$Notes,

    [Parameter(Mandatory=$false)]
    [switch]$Force,

    [Parameter(Mandatory=$false, HelpMessage="Run in non-interactive mode, suppressing user prompts for confirmation.")]
    [switch]$NonInteractive,

    [Parameter(Mandatory=$false, HelpMessage="Non-interactively forces a full analysis update on a valid experiment.")]
    [switch]$ForceUpdate,
    
    [Parameter(Mandatory=$false, HelpMessage="Non-interactively forces re-aggregation on a valid experiment.")]
    [switch]$ForceAggregate,

    [Parameter(Mandatory=$false, HelpMessage="Suppresses the initial PDM detection message.")]
    [switch]$NoHeader
)

function Get-ProjectRoot {
    # This robust method works even when the script is pasted into a terminal.
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) {
            return $currentDir.Path
        }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml). Please run this script from within the project directory."
}

function Write-Header($message, $color, $C_RESET) {
    $line = '#' * 80
    $bookend = "###"
    $contentWidth = $line.Length - ($bookend.Length * 2)
    $paddingNeeded = $contentWidth - $message.Length
    $leftPad = [Math]::Floor($paddingNeeded / 2)
    $rightPad = [Math]::Ceiling($paddingNeeded / 2)
    $centeredMsg = "$bookend$(' ' * $leftPad)$message$(' ' * $rightPad)$bookend"
    
    Write-Host "`n$color$line"
    Write-Host "$color$centeredMsg"
    Write-Host "$color$line$C_RESET"
}

function Invoke-FinalizeExperiment-Local {
    param($ProjectRoot, $ExperimentDirectory, $LogFilePath)

    $pyScripts = @(
        @{ Path=(Join-Path $ProjectRoot "src/manage_experiment_log.py"); Args=@("rebuild", $ExperimentDirectory); Msg="Log rebuild failed" },
        @{ Path=(Join-Path $ProjectRoot "src/compile_experiment_results.py"); Args=@($ExperimentDirectory); Msg="Aggregation failed" },
        @{ Path=(Join-Path $ProjectRoot "src/manage_experiment_log.py"); Args=@("finalize", $ExperimentDirectory); Msg="Log finalization failed" }
    )

    foreach($script in $pyScripts) {
        $finalArgs = @("python", $script.Path) + $script.Args
        & pdm run $finalArgs *>&1 | Tee-Object -FilePath $LogFilePath -Append
        if ($LASTEXITCODE -ne 0) {
            throw $script.Msg
        }
    }
}

# --- Main Execution ---
$ProjectRoot = Get-ProjectRoot
$C_CYAN = "`e[96m"; $C_GREEN = "`e[92m"; $C_YELLOW = "`e[93m"; $C_RED = "`e[91m"; $C_RESET = "`e[0m"

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$logFilePath = Join-Path $ExperimentDirectory "experiment_repair_log.txt"

try {
    # Start with a clean log file for this run.
    if (Test-Path $logFilePath) { Remove-Item $logFilePath -Force }
    # Announce the intended log path using a standardized relative path.
    $relativeLogPath = Join-Path (Resolve-Path -Path $ExperimentDirectory -Relative) (Split-Path $logFilePath -Leaf)
    Write-Host "`nThe repair log will be saved to:`n$relativeLogPath" -ForegroundColor Gray

    if ($ForceUpdate.IsPresent) {
        $procArgs = @((Join-Path $ProjectRoot "src/experiment_manager.py"), "--reprocess", $ExperimentDirectory, "--non-interactive")
        $finalArgs = @("python") + $procArgs
        & pdm run $finalArgs *>&1 | Tee-Object -FilePath $logFilePath -Append
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 99) { throw "Forced update failed" }
        return
    }

    if ($ForceAggregate.IsPresent) {
        Invoke-FinalizeExperiment-Local -ProjectRoot $ProjectRoot -ExperimentDirectory $ExperimentDirectory -LogFilePath $logFilePath
        return
    }

    Write-Header "STEP 1: DIAGNOSING EXPERIMENT STATE" $C_CYAN $C_RESET
    $auditPyArgs = @((Join-Path $ProjectRoot "src/experiment_auditor.py"), $ExperimentDirectory, "--force-color")
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $auditPyArgs += "--config-path", $ConfigPath }
    $auditArgs = @("python") + $auditPyArgs
    & pdm run $auditArgs *>&1 | Tee-Object -FilePath $logFilePath -Append
    $auditExitCode = $LASTEXITCODE
    
    $actionTaken = $false
    $procArgs = $null

    switch ($auditExitCode) {
        0 { # AUDIT_ALL_VALID
            if ($NonInteractive) { return }
            $choice = Read-Host -Prompt "Experiment is valid. Choose action: (1) Full Repair, (2) Full Update, (3) Aggregation Only, (N) No Action"
            switch($choice.Trim().ToLower()) {
                '1' {
                    if ((Read-Host -Prompt "Type 'YES' to confirm OVERWRITE of LLM responses") -eq 'YES') {
                        Get-ChildItem -Path $ExperimentDirectory -Filter "llm_response_*.txt" -Recurse | Remove-Item -Force
                        $procArgs = @((Join-Path $ProjectRoot "src/experiment_manager.py"), $ExperimentDirectory, "--non-interactive")
                    } else { return }
                }
                '2' { $procArgs = @((Join-Path $ProjectRoot "src/experiment_manager.py"), "--reprocess", $ExperimentDirectory, "--non-interactive") }
                '3' { Invoke-FinalizeExperiment-Local -ProjectRoot $ProjectRoot -ExperimentDirectory $ExperimentDirectory -LogFilePath $logFilePath; $actionTaken = $true }
                'n' { return }
                default { return }
            }
        }
        1 { $procArgs = @((Join-Path $ProjectRoot "src/experiment_manager.py"), "--reprocess", $ExperimentDirectory, "--non-interactive") }
        2 { $procArgs = @((Join-Path $ProjectRoot "src/experiment_manager.py"), $ExperimentDirectory, "--non-interactive") }
        3 { Write-Host "Experiment needs migration. Run migrate_experiment.ps1." -ForegroundColor Yellow; exit 1 }
        4 { Invoke-FinalizeExperiment-Local -ProjectRoot $ProjectRoot -ExperimentDirectory $ExperimentDirectory -LogFilePath $logFilePath; $actionTaken = $true }
        default { throw "Audit failed with exit code $auditExitCode" }
    }

    if ($procArgs) {
        if ($StartRep) { $procArgs += "--start-rep", $StartRep }
        if ($EndRep) { $procArgs += "--end-rep", $EndRep }
        if ($Notes) { $procArgs += "--notes", $Notes }
        if ($Verbose) { $procArgs += "--verbose" }
        if (-not [string]::IsNullOrEmpty($ConfigPath)) { $procArgs += "--config-path", $ConfigPath }
        
        $finalArgs = @("python") + $procArgs
        & pdm run $finalArgs *>&1 | Tee-Object -FilePath $logFilePath -Append
        $exitCode = $LASTEXITCODE
        if ($exitCode -ne 0 -and $exitCode -ne 99) { throw "Repair process failed with exit code $exitCode" }
        $actionTaken = $true
    }

    if ($actionTaken) {
        Write-Header "STEP 3: FINAL VERIFICATION" $C_CYAN $C_RESET
        $finalAuditPyArgs = @((Join-Path $ProjectRoot "src/experiment_auditor.py"), $ExperimentDirectory, "--force-color", "--non-interactive")
        if (-not [string]::IsNullOrEmpty($ConfigPath)) { $finalAuditPyArgs += "--config-path", $ConfigPath }
        $finalAuditArgs = @("python") + $finalAuditPyArgs
        & pdm run $finalAuditArgs *>&1 | Tee-Object -FilePath $logFilePath -Append
        $finalAuditCode = $LASTEXITCODE
        if ($finalAuditCode -ne 0) { throw "Final verification failed." }
        Write-Header "REPAIR SUCCESSFUL: Experiment is now valid." $C_GREEN $C_RESET
        Write-Host "" # Add a single blank line for spacing
    }

} catch {
    Write-Header "REPAIR FAILED" $C_RED $C_RESET
    Write-Host "$($C_RED)$($_.Exception.Message)$($C_RESET)`n"
    # Write the error to the log file as well for completeness
    if ($logFilePath) {
        Add-Content -Path $logFilePath -Value "`nREPAIR FAILED: $($_.Exception.Message)"
    }
    exit 1
} finally {
    if (Test-Path -LiteralPath $logFilePath) {
        try {
            $c = Get-Content -Path $logFilePath -Raw
            $c = $c -replace "`e\[[0-9;]*m", ''
            Set-Content -Path $logFilePath -Value $c.Trim() -Force
        }
        catch {}
        Write-Host "`nThe repair log has been saved to:`n$(Resolve-Path -Path $logFilePath -Relative)`n" -ForegroundColor Gray
    }
}

# === End of fix_experiment.ps1 ===
