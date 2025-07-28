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
# Filename: repair_experiment.ps1

<#
.SYNOPSIS
    Repairs or updates an existing experiment. Runs automatically on broken
    experiments or interactively on valid ones.

.DESCRIPTION
    This is the main "fix-it" tool for any existing experiment. It first runs a
    comprehensive audit to diagnose the experiment's state.

    - If issues are found, it proceeds to automatically apply the correct repair
      (e.g., re-running a failed LLM session or restoring a missing config file).
    - If the experiment is already complete and valid, it displays the audit
      report and presents an interactive menu to allow the user to optionally
      force a full data repair, an analysis update, or re-aggregation.

    To create a new experiment from scratch, use 'new_experiment.ps1'.

.PARAMETER TargetDirectory
    (Required) The path to the existing experiment directory that needs to be
    repaired or updated.

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
    .\repair_experiment.ps1 -TargetDirectory "output/studies/MyStudy/Exp1"

.EXAMPLE
    # Run on a valid experiment to bring up the interactive "force action" menu.
    .\repair_experiment.ps1 "output/studies/MyStudy/Exp1"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to repair or update.")]
    [ValidateScript({
        if (-not (Test-Path $_ -PathType Container)) {
            throw "The specified TargetDirectory does not exist or is not a directory: $_"
        }
        return $true
    })]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [int]$StartRep,

    [Parameter(Mandatory = $false)]
    [int]$EndRep,

    [Parameter(Mandatory = $false)]
    [string]$Notes,

    [Parameter(Mandatory=$false)]
    [switch]$Force
)

function Invoke-RepairExperiment {
    function Invoke-FinalizeExperiment-Local {
        # This nested function handles the three-step finalization process.
        # It uses variables from the parent scope ($TargetDirectory, $executable, $prefixArgs).
        Write-Host "`n--- Rebuilding batch run log from replication data... ---" -ForegroundColor Cyan
        $logRebuildArgs = @("src/replication_log_manager.py", "rebuild", $TargetDirectory)
        & $executable $prefixArgs $logRebuildArgs
        if ($LASTEXITCODE -ne 0) { throw "Log rebuild failed with exit code $LASTEXITCODE" }

        Write-Host "`n--- Compiling final experiment summary... ---" -ForegroundColor Cyan
        $aggArgs = @("src/compile_experiment_results.py", $TargetDirectory)
        & $executable $prefixArgs $aggArgs
        if ($LASTEXITCODE -ne 0) { throw "Result aggregation failed with exit code $LASTEXITCODE" }

        Write-Host "`n--- Finalizing batch run log with summary... ---" -ForegroundColor Cyan
        $logFinalizeArgs = @("src/replication_log_manager.py", "finalize", $TargetDirectory)
        & $executable $prefixArgs $logFinalizeArgs
        if ($LASTEXITCODE -ne 0) { throw "Log finalization failed with exit code $LASTEXITCODE" }
        
        # The calling function is responsible for the final success message/audit.
    }
    
    $nonInteractive = $false
    # --- Auto-detect execution environment ---
    $executable = "python"
    $prefixArgs = @()
    if (Get-Command pdm -ErrorAction SilentlyContinue) {
        $executable = "pdm"
        $prefixArgs = "run", "python"
    }

    # Ensure console output uses UTF-8.
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

    try {
        Write-Host "--- Auditing experiment to determine required action... ---" -ForegroundColor Cyan
        # In an automatic flow, the audit result determines the action.
        # If the audit is valid (exit code 0), it becomes an interactive flow.
        $isInteractive = $false
        $auditArgs = @("src/experiment_manager.py", "--verify-only", $TargetDirectory, "--force-color")
        
        # We need to peek at the exit code first to decide if we should suppress the recommendation
        # on the *first* audit display.
        $peekResult = & $executable $prefixArgs $auditArgs | Out-Null
        $auditExitCode = $LASTEXITCODE

        if ($auditExitCode -ne 0) {
            # This is an automatic repair flow. Re-run the audit with the recommendation suppressed.
            $auditArgs += "--non-interactive"
        } else {
            # This is an interactive flow.
            $isInteractive = $true
        }
        
        # Now display the correctly formatted audit report.
        & $executable $prefixArgs $auditArgs

        $actionTaken = $false
        $procArgs = $null

        switch ($auditExitCode) {
            0 { # AUDIT_ALL_VALID
                # The audit report is already on screen.
                $prompt = @"

Experiment is already complete and valid.
Do you still want to proceed with repair?

(1) Full Repair: Deletes all LLM responses and re-runs all API calls. (Expensive & Destructive)
(2) Full Update: Re-runs analysis on existing data for all replications. (Quick & Safe)
(3) Aggregation Only: Re-creates only the top-level summary files. (Fastest)
(N) No Action

Enter your choice (1, 2, 3, or N)
"@
                $choice = Read-Host -Prompt $prompt
                switch ($choice.Trim().ToLower()) {
                    '1' { # Force Full Repair
                        Write-Host "WARNING: This will delete all LLM responses in '$TargetDirectory' and re-run them." -ForegroundColor Red
                        Write-Host "Are you absolutely sure that you want to OVERWRITE the existing LLM responses? (Type 'YES' to confirm): " -NoNewline -ForegroundColor Red
                        $confirm = Read-Host
                        if ($confirm.Trim() -ceq 'YES') {
                            Write-Host ""; Write-Host "Deleting LLM responses..." -ForegroundColor Yellow
                            Get-ChildItem -Path $TargetDirectory -Filter "llm_response_*.txt" -Recurse | Remove-Item -Force
                            Write-Host "`n--- Starting experiment repair/resumption... ---" -ForegroundColor Cyan
                            $procArgs = @("src/experiment_manager.py", $TargetDirectory, "--non-interactive")
                        } else { Write-Host "`nAction aborted by user." -ForegroundColor Yellow; return }
                    }
                    '2' { # Force Full Update
                        Write-Host "`n--- Starting experiment reprocessing... ---" -ForegroundColor Cyan
                        $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory, "--non-interactive")
                    }
                    '3' { # Force Aggregation
                        Write-Host "`n--- Starting experiment finalization... ---" -ForegroundColor Cyan
                        Invoke-FinalizeExperiment-Local
                        $actionTaken = $true
                    }
                    'n' { Write-Host "No action taken." -ForegroundColor Yellow; return }
                    default { Write-Warning "Invalid choice. No action taken."; return }
                }
            }
            1 { # AUDIT_NEEDS_REPROCESS
                Write-Host "`n--- Starting experiment reprocessing... ---" -ForegroundColor Cyan
                $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory, "--non-interactive")
            }
            2 { # AUDIT_NEEDS_REPAIR
                Write-Host "`n--- Starting experiment repair/resumption... ---" -ForegroundColor Cyan
                $procArgs = @("src/experiment_manager.py", $TargetDirectory, "--non-interactive")
            }
            3 { # AUDIT_NEEDS_MIGRATION
                Write-Error "This experiment is a legacy version and requires migration. Please run 'migrate_experiment.ps1' on this directory."; exit 1
            }
            4 { # AUDIT_NEEDS_AGGREGATION
                Write-Host "`n--- Starting experiment finalization... ---" -ForegroundColor Cyan
                Invoke-FinalizeExperiment-Local
                $actionTaken = $true
            }
            default { throw "Audit script failed unexpectedly with exit code $auditExitCode. Cannot proceed." }
        }

        # If a python process was configured, run it now.
        if ($procArgs) {
            if ($StartRep) { $procArgs += "--start-rep", $StartRep }
            if ($EndRep) { $procArgs += "--end-rep", $EndRep }
            if ($Notes) { $procArgs += "--notes", $Notes }
            if ($Verbose.IsPresent) { $procArgs += "--verbose" }
            
            & $executable $prefixArgs $procArgs
            if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 99) { throw "Repair process failed with exit code $LASTEXITCODE" }
            $actionTaken = $true
        }

        # If any action was successfully taken, run a final verification to confirm the new state.
        if ($actionTaken) {
            Write-Host "`n--- Verifying final experiment state... ---" -ForegroundColor Cyan
            $finalAuditArgs = @("src/experiment_manager.py", "--verify-only", $TargetDirectory, "--force-color")
            & $executable $prefixArgs $finalAuditArgs
        }

    } catch {
        Write-Error "An error occurred during the repair/update process: $($_.Exception.Message)"
        exit 1
    }
}

# This invocation guard ensures the main execution logic is only triggered
# when the script is run directly (not dot-sourced).
if ($MyInvocation.InvocationName -ne '.') {
    Invoke-RepairExperiment
}

# === End of repair_experiment.ps1 ===