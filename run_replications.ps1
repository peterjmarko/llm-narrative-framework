#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: run_replications.ps1

# --- (Preamble and comments are unchanged) ---

[CmdletBinding(DefaultParameterSetName='NewRun')]
param(
    # --- (Parameters are unchanged) ---
    [Parameter(ParameterSetName='NewRun')]
    [int]$Start = 1,
    [Parameter(ParameterSetName='NewRun')]
    [int]$End = 30,
    [Parameter(ParameterSetName='NewRun')]
    [int]$Trials = 100,
    [Parameter(ParameterSetName='NewRun')]
    [int]$GroupSize = 10,
    [Parameter(ParameterSetName='Reprocess', Mandatory=$true)]
    [switch]$Reprocess,
    [Parameter(ParameterSetName='Reprocess', Mandatory=$true)]
    [string]$TargetDirectory
)

# --- (Initialization is unchanged) ---
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$PSDefaultParameterValues['Out-File:Encoding'] = 'utf8'
$batchStartTime = Get-Date
$Verbose = $PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters.Verbose

if ($PSCmdlet.ParameterSetName -eq 'Reprocess') {
    # --- (Reprocess mode logic is unchanged) ---
    Write-Host "--- REPROCESS MODE ACTIVATED for directory: $TargetDirectory ---" -ForegroundColor Magenta
    if (-not (Test-Path -Path $TargetDirectory -PathType Container)) {
        Write-Error "Error: Target directory does not exist: $TargetDirectory"
        return
    }
    $runDirectories = Get-ChildItem -Path $TargetDirectory -Directory -Filter "run_*" | Sort-Object Name
    Write-Host "Found $($runDirectories.Count) run directories to re-process."
    if ($runDirectories.Count -eq 0) {
        Write-Warning "No 'run_*' directories found in '$TargetDirectory'. Nothing to do."
        return
    }
    $pythonReprocessArgs = @("src/orchestrate_experiment.py", "--reprocess")
    if (-not $Verbose) { $pythonReprocessArgs += "--quiet" }
    foreach ($runDir in $runDirectories) {
        Write-Host "`n================================================================================" -ForegroundColor Cyan
        Write-Host "### RE-PROCESSING: $($runDir.Name) ###" -ForegroundColor Cyan
        Write-Host "================================================================================" -ForegroundColor Cyan
        $currentRunArgs = $pythonReprocessArgs + @("--run_output_dir", $runDir.FullName)
        & python $currentRunArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Orchestrator failed while reprocessing $($runDir.Name). Aborting."
            exit 1
        }
    }
    Write-Host "`n--- All runs re-processed successfully. ---" -ForegroundColor Green
    $outputDir = $TargetDirectory

} else {
    # --- (New Run Mode logic is unchanged) ---
    $completedReplications = 0
    $totalReplicationsInBatch = $End - $Start + 1
    $errorsEncountered = 0
    $outputDir = "output"
    if (-not (Test-Path -Path $outputDir)) { New-Item -Path $outputDir -ItemType Directory | Out-Null }
    $batchLogPath = Join-Path -Path $outputDir -ChildPath "batch_run_log.csv"
    if (-not (Test-Path -Path $batchLogPath)) {
        "ReplicationNum,Status,StartTime,EndTime,Duration,ParsingStatus,MeanMRR,MeanTop1Acc,RunDirectory,ErrorMessage" | Set-Content -Path $batchLogPath
    }
    Write-Host "Starting new batch run for replications $Start to $End..." -ForegroundColor Green
    $pythonArgs = @("src/orchestrate_experiment.py", "-m", $Trials, "-k", $GroupSize)
    if (-not $Verbose) { $pythonArgs += "--quiet" }
    for ($i = $Start; $i -le $End; $i++) {
        # --- (Loop logic is unchanged) ---
        $repStartTime = Get-Date
        $currentBaseSeed = 1000 * $i; $currentQgenSeed = $currentBaseSeed + 500
        Write-Host "`n================================================================================" -ForegroundColor Cyan
        Write-Host "### RUNNING GLOBAL REPLICATION $i of $End (Seed: $currentBaseSeed) ###" -ForegroundColor Cyan
        Write-Host "================================================================================" -ForegroundColor Cyan
        $currentRunArgs = $pythonArgs + @("--replication_num", $i, "--base_seed", $currentBaseSeed, "--qgen_base_seed", $currentQgenSeed)
        & python $currentRunArgs
        $exitCode = $LASTEXITCODE
        $repEndTime = Get-Date
        $logEntry = [PSCustomObject]@{ ReplicationNum = $i; Status = "FAILED"; StartTime = $repStartTime.ToString("u"); EndTime = $repEndTime.ToString("u"); Duration = ($repEndTime - $repStartTime).ToString("c"); ParsingStatus = "N/A"; MeanMRR = "N/A"; MeanTop1Acc = "N/A"; RunDirectory = "N/A"; ErrorMessage = "N/A" }
        $runDir = Get-ChildItem -Path $outputDir -Directory -Filter "run_*" | Sort-Object CreationTime -Descending | Select-Object -First 1
        if ($runDir) { $logEntry.RunDirectory = $runDir.Name }
        if ($exitCode -ne 0) {
            $errorsEncountered++
            $logEntry.ErrorMessage = "Orchestrator failed with exit code $exitCode."
            Write-Warning "Orchestrator failed on replication $i. See logs in $($logEntry.RunDirectory) for details."
        } else {
            $logEntry.Status = "COMPLETED"
            $completedReplications++
            Write-Host "Replication $i finished. Parsing report..."
            $reportFile = Get-ChildItem -Path $runDir.FullName -Filter "replication_report_*.txt" | Select-Object -First 1
            if ($reportFile) {
                $reportContent = Get-Content -Path $reportFile.FullName -Raw
                if ($reportContent -match 'Parsing Status:\s+(.+)') { $logEntry.ParsingStatus = $matches[1].Trim() }
                $jsonString = $reportContent | Select-String -Pattern '(?s)METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END' | ForEach-Object { $_.Matches[0].Groups[1].Value }
                if ($jsonString) {
                    try {
                        $metrics = $jsonString.Trim() | ConvertFrom-Json
                        $logEntry.MeanMRR = "{0:F4}" -f $metrics.mean_mrr
                        $logEntry.MeanTop1Acc = "{0:P2}" -f $metrics.mean_top_1_acc
                    } catch { $logEntry.ErrorMessage = "Failed to parse metrics from report." }
                }
            } else { $logEntry.ErrorMessage = "Orchestrator succeeded but report file was not found." }
        }
        $logEntry | ConvertTo-Csv -NoTypeInformation | Select-Object -Skip 1 | Add-Content -Path $batchLogPath
    }
    if ($totalReplicationsInBatch -gt 0) {
        $summaryLine = "Totals,,$completedReplications,$errorsEncountered"
        Add-Content -Path $batchLogPath -Value $summaryLine
    }
    # --- (Retry logic is unchanged) ---
    function Invoke-RetryAndRepair { param([string]$TargetDir)
        Write-Host "`n--- AUTO-REPAIR: Scanning for and retrying failed sessions... ---" -ForegroundColor Magenta
        $process = Start-Process python -ArgumentList "src/retry_failed_sessions.py", $TargetDir -Wait -NoNewWindow -PassThru
        if ($process.ExitCode -eq 0) { Write-Host "Repair complete: No failures found." -ForegroundColor Green; return $true }
        elseif ($process.ExitCode -eq 1) { Write-Host "Repair successful: All failures were fixed." -ForegroundColor Green; return $false }
        else { Write-Host "!!! Repair FAILED: Some sessions could not be repaired. !!!" -ForegroundColor Red; return $false }
    }
    $maxRepairAttempts = 3; $repairAttempt = 1; $repairSuccessful = $false
    while ($repairAttempt -le $maxRepairAttempts -and -not $repairSuccessful) {
        Write-Host "`n--- Starting automatic repair attempt $repairAttempt of $maxRepairAttempts... ---"
        $repairSuccessful = Invoke-RetryAndRepair -TargetDir $outputDir
        if (-not $repairSuccessful -and $repairAttempt -lt $maxRepairAttempts) { Start-Sleep -Seconds 5 }
        $repairAttempt++
    }
}

# --- Final Compilation and Summary ---
# [FIX] Change the console message to match the test assertion.
Write-Host "`n================================================================================" -ForegroundColor Yellow
Write-Host "### BATCH RUN COMPLETE - COMPILING FINAL RESULTS ###" -ForegroundColor Yellow
Write-Host "================================================================================" -ForegroundColor Yellow

& python src/compile_results.py $outputDir
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n!!! Failed to compile final results. Check the output above for errors. !!!" -ForegroundColor Red
} else {
    Write-Host "--- Final summary created successfully. ---"
}

Write-Host "Batch run finished"

# === End of run_replications.ps1 ===