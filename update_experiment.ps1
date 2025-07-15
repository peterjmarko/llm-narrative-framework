<#
.SYNOPSIS
    Updates an existing experiment by re-running its data processing and analysis stages.

.DESCRIPTION
    This script serves as a user-friendly wrapper for 'src/experiment_manager.py' with the '--reprocess' flag.
    It forces the pipeline to regenerate analysis artifacts (like reports and summary CSVs) for a
    specified experiment directory. This is useful for applying updates to analysis logic without
    repeating expensive LLM API calls.

.PARAMETER TargetDirectory
    (Required) The full path to the experiment directory that you want to update. This is a positional
    parameter, so you can provide the path directly after the script name.

.PARAMETER Notes
    (Optional) A string containing notes to embed in the run logs and reports. This is useful for
    documenting why the reprocessing was performed.

.PARAMETER Verbose
    (Optional) A switch parameter that enables detailed, real-time logging from the underlying Python
    scripts.

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
    $auditArgs = @("src/experiment_manager.py","--verify-only",$TargetDirectory)
    if ($Verbose.IsPresent) { $auditArgs += "--verbose" }

    & $executable $prefixArgs $auditArgs        # ---- 1. audit only
    switch ($LASTEXITCODE) {
        0 {
            Write-Host "UPDATE: experiment already COMPLETE - nothing to do." -ForegroundColor Green
            return
        }
        1 { }   # state = REPROCESS_NEEDED
        default {
            throw "Audit failed unexpectedly - see above."
        }
    }

    $procArgs = @("src/experiment_manager.py","--reprocess",$TargetDirectory)
    if ($Verbose.IsPresent) { $procArgs += "--verbose" }
    if ($Notes) { $procArgs += "--notes",$Notes }

    & $executable $prefixArgs $procArgs
    if ($LASTEXITCODE -ne 0) { throw "Re-processing failed - exit code $LASTEXITCODE" }

    Write-Host "Experiment update completed successfully." -ForegroundColor Green
} catch {
    Write-Error "An error occurred during the update process: $($_.Exception.Message)"
    exit 1
}