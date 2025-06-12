#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: run_replications.ps1

<#
.SYNOPSIS
    Runs a batch of N experimental replications, automatically attempts to repair
    failures, and compiles the final results.

.DESCRIPTION
    This master script calls the main Python orchestrator multiple times to conduct a
    series of seeded, reproducible experiments. It manages the replication count
    and seeding, creating a unique, self-contained output directory for each run.
    It logs the outcome of each replication to `output/batch_run_log.csv`.

    This script is the primary entry point for conducting a definitive study. It runs
    quietly by default. After all replications are complete, it automatically
    initiates a multi-attempt repair cycle that calls 'retry_failed_sessions.py'
    to fix any runs that failed due to intermittent errors. Finally, it calls the
    compiler script to generate a final summary CSV.

.PARAMETER Start
    The global replication number to start the batch run from (inclusive).
    Defaults to 1.

.PARAMETER End
    The global replication number to end the batch run at (inclusive).
    Defaults to 30.

.PARAMETER Trials
    The number of trials (m) to run within each experiment.
    Passed to orchestrate_experiment.py as the -m argument. Defaults to 100.

.PARAMETER GroupSize
    The number of subjects (k) per trial.
    Passed to orchestrate_experiment.py as the -k argument. Defaults to 10.

.PARAMETER Verbose
    A switch to run the entire pipeline in verbose mode for debugging.
    If omitted, the pipeline runs quietly.

.EXAMPLE
    # Run the default study quietly and compile results at the end.
    .\run_replications.ps1

.EXAMPLE
    # Run the first 5 replications with detailed logging for debugging.
    .\run_replications.ps1 -Start 1 -End 5 -Verbose

.EXAMPLE
    # Run the second half of a 30-rep study, with custom k and m values.
    .\run_replications.ps1 -Start 16 -End 30 -Trials 50 -GroupSize 8
#>

# === Start of run_replications.ps1 ===

param(
    [int]$Start = 1,
    [int]$End = 30,
    [int]$Trials = 100,
    [int]$GroupSize = 10,
    [switch]$Verbose = $false
)

# Set the output encoding for this script session to UTF-8 to prevent Unicode errors
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'

# --- Initialization ---
$batchStartTime = Get-Date
$completedReplications = 0
$totalReplicationsInBatch = $End - $Start + 1
$errorsEncountered = 0
$replicationLogs = @()

# Prepare paths and create the batch log file with a header only if it doesn't exist
$outputDir = "output"
if (-not (Test-Path -Path $outputDir)) {
    New-Item -Path $outputDir -ItemType Directory | Out-Null
}
$batchLogPath = Join-Path -Path $outputDir -ChildPath "batch_run_log.csv"

if (-not (Test-Path -Path $batchLogPath)) {
    Write-Host "Creating new batch run log file: $batchLogPath"
    $logHeader = "ReplicationNum,Status,StartTime,EndTime,Duration,MeanMRR,MeanTop1Acc,RunDirectory,ErrorMessage"
    Set-Content -Path $batchLogPath -Value $logHeader
} else {
    Write-Host "Appending to existing batch run log file: $batchLogPath"
}

# --- Main Loop ---
Write-Host "Starting batch run for replications $Start to $End..." -ForegroundColor Green
Write-Host "Parameters per run: Trials (m) = $Trials, Group Size (k) = $GroupSize"

# Build the base list of arguments for the Python script
$pythonArgs = @(
    "src/orchestrate_experiment.py",
    "-m", $Trials,
    "-k", $GroupSize
)
# Default to quiet mode unless -Verbose is specified.
if (-not $Verbose) {
    $pythonArgs += "--quiet"
    Write-Host "Running in QUIET mode. Use -Verbose switch for detailed logs." -ForegroundColor Yellow
} else {
    Write-Host "Running in VERBOSE mode." -ForegroundColor Yellow
}

for ($i = $Start; $i -le $End; $i++) {
    $repStartTime = Get-Date
    # Calculate unique, deterministic seeds directly from the replication number ($i)
    $currentBaseSeed = 1000 * $i
    $currentQgenSeed = $currentBaseSeed + 500 # Keep a fixed offset for the second seed

    # Write a clear header for each replication's output
    Write-Host "`n"
    Write-Host "================================================================================" -ForegroundColor Cyan
    Write-Host "### RUNNING GLOBAL REPLICATION $i of $End (Seed: $currentBaseSeed) ###" -ForegroundColor Cyan
    Write-Host "================================================================================" -ForegroundColor Cyan
    
    $currentRunArgs = $pythonArgs + @("--replication_num", $i, "--base_seed", $currentBaseSeed, "--qgen_base_seed", $currentQgenSeed)
    
    # Run the orchestrator. This allows stdout to pass through to the console.
    # We check $LASTEXITCODE immediately after to determine success or failure.
    python $currentRunArgs
    $exitCode = $LASTEXITCODE
    
    $repEndTime = Get-Date
    $repDuration = $repEndTime - $repStartTime
    $logEntry = [PSCustomObject]@{
        ReplicationNum = $i
        Status = "FAILED"
        StartTime = $repStartTime.ToString("yyyy-MM-dd HH:mm:ss")
        EndTime = $repEndTime.ToString("yyyy-MM-dd HH:mm:ss")
        Duration = $repDuration.ToString("hh\:mm\:ss")
        MeanMRR = "N/A"
        MeanTop1Acc = "N/A"
        RunDirectory = "N/A"
        ErrorMessage = "N/A"
    }

    if ($exitCode -ne 0) {
        $errorsEncountered++
        # Since we are not capturing stderr directly anymore, we log a generic failure message.
        # The detailed error will be in the replication_report.txt inside the failed run's directory.
        $logEntry.ErrorMessage = "Orchestrator script failed with exit code $exitCode. See the run's report for details."
        Write-Host "`n!!! Orchestrator failed on replication $i. Check batch_run_log.csv for details. Continuing... !!!" -ForegroundColor Red
    } else {
        $logEntry.Status = "COMPLETED"
        $completedReplications++

        # --- Parse the report from this replication for a summary ---
        $latestRunDir = Get-ChildItem -Path $outputDir -Directory | Where-Object { $_.Name -like "run_*" } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($latestRunDir) {
            $logEntry.RunDirectory = $latestRunDir.Name
            $reportFile = Get-ChildItem -Path $latestRunDir.FullName -Filter "replication_report_*.txt" | Select-Object -First 1
            if ($reportFile) {
                $reportContent = Get-Content -Path $reportFile.FullName -Raw
                $jsonMatch = [regex]::Match($reportContent, '(?s)<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>')
                if ($jsonMatch.Success) {
                    try {
                        $metrics = $jsonMatch.Groups[1].Value.Trim() | ConvertFrom-Json
                        $logEntry.MeanMRR = "{0:N4}" -f $metrics.mean_mrr
                        $logEntry.MeanTop1Acc = "{0:P2}" -f $metrics.mean_top_1_acc
                    } catch { $logEntry.ErrorMessage = "Could not parse metrics JSON." }
                } else { $logEntry.ErrorMessage = "Metrics JSON block not found in report." }
            } else { $logEntry.ErrorMessage = "Replication report file not found." }
        } else { $logEntry.ErrorMessage = "Could not find latest run directory." }
    }
    
    # Add the log entry for this replication to the CSV file
    $logEntry | ConvertTo-Csv -NoTypeInformation | Select-Object -Skip 1 | Add-Content -Path $batchLogPath

    # --- Update and display batch progress ---
    $batchTotalElapsedTime = (Get-Date) - $batchStartTime
    $averageTimePerRepSeconds = if ($completedReplications -gt 0) { $batchTotalElapsedTime.TotalSeconds / $completedReplications } else { 0 }
    $repsLeftInLoop = $End - $i
    $estimatedTimeRemainingSeconds = $averageTimePerRepSeconds * $repsLeftInLoop
    
    $formattedTotalElapsed = "{0:hh\:mm\:ss}" -f $batchTotalElapsedTime
    $formattedETR = "{0:hh\:mm\:ss}" -f ([TimeSpan]::FromSeconds($estimatedTimeRemainingSeconds))

    Write-Host "--- Replication $i finished. Batch progress: $($i - $Start + 1)/$totalReplicationsInBatch | Elapsed: $formattedTotalElapsed | ETR: $formattedETR ---" -ForegroundColor Green
    Start-Sleep -Seconds 2
}

# --- Automatic Retry/Repair Phase ---
function Invoke-RetryAndRepair {
    param(
        [string]$TargetDir
    )
    Write-Host "`n================================================================================" -ForegroundColor Magenta
    Write-Host "### AUTO-REPAIR: Scanning for and retrying failed sessions... ###" -ForegroundColor Magenta
    Write-Host "================================================================================" -ForegroundColor Magenta

    # Run the retry script and capture its output
    $retryOutput = python src/retry_failed_sessions.py --parent_dir $TargetDir 2>&1 | Tee-Object -Variable retryOutputString
    if ($LASTEXITCODE -ne 0) {
        Write-Host "!!! Auto-repair script failed to execute. Please check logs. !!!" -ForegroundColor Red
        return $false # Indicate failure
    }
    
    # Check the output to see if failures were found and if they were all fixed.
    if ($retryOutputString -match "No failed sessions found") {
        Write-Host "Auto-repair check complete: No failures found." -ForegroundColor Green
        return $true # Indicate success (no failures)
    } elseif ($retryOutputString -match "Retry Phase Complete: \d+ successful, 0 failed") {
        Write-Host "Auto-repair successful: All detected failures were fixed." -ForegroundColor Green
        return $true # Indicate success (all failures fixed)
    } else {
        Write-Host "!!! Auto-repair finished, but some failures may remain. Check logs above. !!!" -ForegroundColor Yellow
        return $false # Indicate potential remaining failures
    }
}

$maxRepairAttempts = 3
$repairAttempt = 1
$repairSuccessful = $false

while ($repairAttempt -le $maxRepairAttempts -and -not $repairSuccessful) {
    Write-Host "`n--- Starting automatic repair attempt $repairAttempt of $maxRepairAttempts... ---"
    $repairSuccessful = Invoke-RetryAndRepair -TargetDir $outputDir
    if (-not $repairSuccessful -and $repairAttempt -lt $maxRepairAttempts) {
        Write-Host "Retrying repair in 5 seconds..."
        Start-Sleep -Seconds 5
    }
    $repairAttempt++
}

if (-not $repairSuccessful) {
    Write-Host "`n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" -ForegroundColor Red
    Write-Host "!!! CRITICAL: Automatic repair failed after $maxRepairAttempts attempts.            !!!"
    Write-Host "!!! Please review the logs and run 'python src/retry_failed_sessions.py' manually. !!!"
    Write-Host "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!" -ForegroundColor Red
}

# --- Final Compilation and Summary ---
Write-Host "`n================================================================================" -ForegroundColor Yellow
Write-Host "### BATCH RUN COMPLETE - COMPILING FINAL RESULTS ###" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Yellow

python src/compile_results.py $outputDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n!!! Failed to compile final results. Check the output above for errors. !!!" -ForegroundColor Red
} else {
    Write-Host "--- Final summary created at $($outputDir)\final_summary_results.csv ---"
}

# --- Final Batch Summary ---
$batchEndTime = Get-Date
$finalTotalDuration = "{0:hh\:mm\:ss}" -f ($batchEndTime - $batchStartTime)
Add-Content -Path $batchLogPath -Value ""
Add-Content -Path $batchLogPath -Value "BatchSummary,StartTime,EndTime,TotalDuration,Completed,Failed"
Add-Content -Path $batchLogPath -Value "Totals,$($batchStartTime.ToString('yyyy-MM-dd HH:mm:ss')),$($batchEndTime.ToString('yyyy-MM-dd HH:mm:ss')),$finalTotalDuration,$completedReplications,$errorsEncountered"

Write-Host "`n--- Batch run finished. ---"
Write-Host "Total duration: $finalTotalDuration"
Write-Host "Successful replications: $completedReplications"
Write-Host "Failed replications: $errorsEncountered"
Write-Host "See $($batchLogPath) for a detailed log of the batch run."

# === End of run_replications.ps1 ===