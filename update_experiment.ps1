<#
.SYNOPSIS
    Updates an experiment by regenerating all analysis reports and summary files.

.DESCRIPTION
    This script serves as a user-friendly wrapper for 'src/experiment_manager.py' with the '--reprocess' flag.
    It first runs a preliminary audit to ensure the experiment is in a valid state for reprocessing.
    It then forces the pipeline to regenerate analysis artifacts for a specified experiment directory.
    This process involves two main steps:
    1. Regenerating the primary report ('replication_report.txt') for each individual run.
    2. Re-running the hierarchical aggregation to update all summary files ('REPLICATION_results.csv', 'EXPERIMENT_results.csv').

    This is the ideal tool for applying analysis updates or bug fixes without repeating expensive LLM API calls,
    as it ensures the entire data hierarchy is consistent.

.PARAMETER TargetDirectory
    (Required) The full path to the experiment directory that you want to update. This is a positional
    parameter, so you can provide the path directly after the script name.

.PARAMETER Notes
    (Optional) A string containing notes to embed in the run logs and reports. This is useful for
    documenting why the reprocessing was performed.

.PARAMETER Verbose
    (Optional) A switch parameter that enables detailed, real-time logging from the underlying Python
    scripts during the reprocessing phase.

.EXAMPLE
    # Reprocess the experiment located in 'output/reports/MyStudy/Experiment_1'
    .\update_experiment.ps1 -TargetDirectory "output/reports/MyStudy/Experiment_1"

.EXAMPLE
    # Reprocess the same experiment with verbose output and notes
    .\update_experiment.ps1 "output/reports/MyStudy/Experiment_1" -Notes "Applied fix to MRR calculation" -Verbose
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the experiment directory to update.")]
    [ValidateScript({
        if (-not (Test-Path $_ -PathType Container)) {
            throw "The specified TargetDirectory does not exist or is not a directory: $_"
        }
        return $true
    })]
    [string]$TargetDirectory,

    [Parameter(Mandatory = $false)]
    [string]$Notes
)

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    $executable = "pdm"
    $prefixArgs = "run", "python"
}

try {
    Write-Host "--- Auditing experiment before update... ---" -ForegroundColor Cyan
    # Always force color for consistent output handling from Python script
    $auditArgs = @("src/experiment_manager.py", "--verify-only", $TargetDirectory, "--force-color")

    # Execute and capture the output to display it, but crucially check $LASTEXITCODE
    & $executable $prefixArgs $auditArgs
    $auditExitCode = $LASTEXITCODE

    switch ($auditExitCode) {
        0 { # AUDIT_ALL_VALID
            # The Python script has already printed a "complete and valid" message. Exit successfully.
            return
        }
        1 { # AUDIT_NEEDS_REPROCESS
            # The Python script has already confirmed the experiment is ready. Proceed silently.
        }
        2 { # AUDIT_NEEDS_REPAIR
            # The audit script already printed the reason and recommendation. Exit with a failure code.
            exit 1
        }
        3 { # AUDIT_NEEDS_MIGRATION
            # The audit script already printed the reason and recommendation. Exit with a failure code.
            exit 1
        }
        default {
            throw "Audit script failed unexpectedly with exit code $auditExitCode. Cannot proceed."
        }
    }

    Write-Host "`n--- Starting experiment reprocessing... ---" -ForegroundColor Cyan
    $procArgs = @("src/experiment_manager.py", "--reprocess", $TargetDirectory)
    # The --verbose flag from the wrapper is passed here, not to the audit.
    if ($Verbose.IsPresent) {
        $procArgs += "--verbose"
    }
    if ($Notes) { $procArgs += "--notes", $Notes }

    # Add --force-color for the reprocessing step as well
    $procArgs += "--force-color"

    & $executable $prefixArgs $procArgs
    if ($LASTEXITCODE -ne 0) { throw "Re-processing failed with exit code $LASTEXITCODE" }

    Write-Host "`nExperiment update completed successfully." -ForegroundColor Green
} catch {
    # The 'throw' statements in the switch block will be caught here.
    Write-Error "An error occurred during the update process: $($_.Exception.Message)"
    exit 1
}