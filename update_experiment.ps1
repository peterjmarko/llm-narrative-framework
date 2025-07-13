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
    [string]$Notes,

    [Parameter(Mandatory = $false)]
    [switch]$Verbose
)

try {
    # Get the directory of the current script to reliably locate the Python script
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $PythonScriptPath = Join-Path -Path $ScriptDir -ChildPath "..\src\experiment_manager.py"

    # Assemble the arguments for the Python script
    $pythonArgs = @(
        $PythonScriptPath,
        '--reprocess',
        $TargetDirectory
    )

    if ($PSBoundParameters.ContainsKey('Notes')) {
        $pythonArgs += '--notes', $Notes
    }

    if ($Verbose.IsPresent) {
        $pythonArgs += '--verbose'
    }

    Write-Host "Starting experiment update for: $TargetDirectory" -ForegroundColor Green
    
    # Execute the Python script with the assembled arguments
    & python @pythonArgs

    if ($LASTEXITCODE -ne 0) {
        throw "The Python script exited with an error (Exit Code: $LASTEXITCODE)."
    }

    Write-Host "Experiment update completed successfully." -ForegroundColor Green
}
catch {
    Write-Error "An error occurred during the update process: $_"
    # Exit with a non-zero status code to indicate failure to calling processes
    exit 1
}