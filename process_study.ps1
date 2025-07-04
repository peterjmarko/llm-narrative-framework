<#
.SYNOPSIS
    Automates the final analysis of a full study.

.DESCRIPTION
    This script runs the two main post-processing steps on a completed study,
    which consists of one or more experiment directories.
    1.  It calls `compile_results.py` to recursively scan all subdirectories,
        aggregating results into a single master 'final_summary_results.csv' file
        at the top level of the study directory.
    2.  It then calls `run_anova.py` to perform a full statistical analysis (ANOVA,
        Tukey's HSD) on that master CSV, generating final plots and logs.

.PARAMETER StudyDirectory
    The path to the top-level study directory containing one or more experiment
    directories to be compiled and analyzed (e.g., 'output/reports').

.EXAMPLE
    # Run by providing the path as a positional argument (recommended):
    .\process_study.ps1 "output/reports"

    # Alternatively, run using the named parameter for added clarity:
    .\process_study.ps1 -StudyDirectory "output/reports"
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the top-level study directory.")]
    [string]$StudyDirectory
)

# --- Function to execute a Python script and check for errors ---
function Invoke-PythonScript {
    param (
        [string]$StepName,
        [string]$ScriptName,
        [string[]]$Arguments
    )
    
    Write-Host "[${StepName}] Executing: python ${ScriptName} ${Arguments}"
    
    # Execute the Python script
    python $ScriptName $Arguments
    
    # Check the exit code of the last command
    if ($LASTEXITCODE -ne 0) {
        throw "ERROR: Step '${StepName}' failed with exit code ${LASTEXITCODE}. Aborting."
    }
    
    Write-Host "Step '${StepName}' completed successfully."
    Write-Host ""
}

# --- Main Script Logic ---
try {
    # Resolve the path to ensure it's absolute and check for existence
    $ResolvedPath = Resolve-Path -Path $StudyDirectory -ErrorAction Stop
    
    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Starting Study Processing for: '$($ResolvedPath)'" -ForegroundColor Green
    Write-Host "######################################################`n"

    # --- Step 1: Compile All Results into a Master CSV ---
    Invoke-PythonScript -StepName "1/2: Compile Results" -ScriptName "src/compile_results.py" -Arguments $ResolvedPath

    # --- Step 2: Run Final Statistical Analysis ---
    Invoke-PythonScript -StepName "2/2: Run Final Analysis (ANOVA)" -ScriptName "src/run_anova.py" -Arguments $ResolvedPath

    Write-Host "######################################################" -ForegroundColor Green
    Write-Host "### Study Processing Finished Successfully!" -ForegroundColor Green
    Write-Host "######################################################`n"
    Write-Host "Final analysis logs and plots are located in: '$($ResolvedPath)\anova'"

}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### STUDY PROCESSING FAILED" -ForegroundColor Red
    Write-Host "######################################################" -ForegroundColor Red
    Write-Error $_.Exception.Message
    # Exit with a non-zero status code to indicate failure to other automation tools
    exit 1
}
