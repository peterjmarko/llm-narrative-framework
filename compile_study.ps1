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
# Filename: compile_study.ps1

<#
.SYNOPSIS
    Audits, compiles, and evaluates a full study.

.DESCRIPTION
    This script is the main entry point for the entire study evaluation workflow. It
    orchestrates three key scripts in sequence:
    1.  `audit_study.ps1`: Performs a full audit of the study. The script will halt
        if any experiment is not in a validated state.
    2.  `compile_study_results.py`: Compiles all experiment data into a master CSV.
    3.  `analyze_study_results.py`: Performs statistical analysis on the master CSV.

    By default, it provides a clean, high-level summary. For detailed, real-time
    output, use the -Verbose switch.

.PARAMETER StudyDirectory
    The path to the top-level study directory containing experiment folders that need
    to be evaluated (e.g., 'output/studies'). This is a mandatory parameter.

.EXAMPLE
    # Evaluate a study with the default high-level summary.
    .\evaluate_study.ps1 -StudyDirectory "output/studies/My_Full_Study"

.EXAMPLE
    # Evaluate a study with detailed, real-time output for debugging.
    .\evaluate_study.ps1 -StudyDirectory "output/studies/My_Full_Study" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $false, HelpMessage = "Path to a specific config.ini file to use for this operation.")]
    [Alias('config-path')]
    [string]$ConfigPath,

    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the target top-level study directory.")]
    [string]$StudyDirectory,

    [Parameter(Mandatory=$false)]
    [switch]$NoLog
)

# --- Helper Functions ---
function Format-Banner {
    param(
        [string]$Message,
        [int]$TotalWidth = 80
    )
    $prefix = "###"
    $suffix = "###"
    $contentWidth = $TotalWidth - $prefix.Length - $suffix.Length
    $paddedMessage = " $Message "
    
    # Simple centering logic
    $paddingTotal = $contentWidth - $paddedMessage.Length
    if ($paddingTotal -lt 0) { $paddingTotal = 0 }
    $paddingLeft = [Math]::Floor($paddingTotal / 2)
    $paddingRight = $contentWidth - $paddedMessage.Length - $paddingLeft
    
    $content = (" " * $paddingLeft) + $paddedMessage + (" " * $paddingRight)
    
    return "$prefix$content$suffix"
}

# --- Auto-detect execution environment ---
$executable = "python"
$prefixArgs = @()
if (Get-Command pdm -ErrorAction SilentlyContinue) {
    Write-Host "`nPDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
    $executable = "pdm"
    $prefixArgs = "run", "python"
}
else {
    Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
}

# --- Load and parse model display names from config.ini ---
$modelNameMap = @{}
try {
    # Use the provided ConfigPath if it exists, otherwise default to the project root's config.ini.
    $effectiveConfigPath = if (-not [string]::IsNullOrEmpty($ConfigPath) -and (Test-Path $ConfigPath)) { $ConfigPath } else { Join-Path $PSScriptRoot "config.ini" }
    
    if (-not (Test-Path $effectiveConfigPath)) {
        throw "config.ini not found at '$effectiveConfigPath'"
    }
    $configContent = Get-Content -Path $effectiveConfigPath -Raw

    # Use [regex]::Match to correctly extract the section content as a string.
    $normalizationSection = ([regex]::Match($configContent, '(?msi)^\[ModelNormalization\]\r?\n(.*?)(?=\r?\n^\[)')).Groups[1].Value
    $displaySection = ([regex]::Match($configContent, '(?msi)^\[ModelDisplayNames\]\r?\n(.*?)(?=\r?\n^\[)')).Groups[1].Value

    if ([string]::IsNullOrWhiteSpace($normalizationSection) -or [string]::IsNullOrWhiteSpace($displaySection)) {
        throw "Could not find or parse [ModelNormalization] or [ModelDisplayNames] sections."
    }

    # Build map from canonical name to display name
    $displayNameMap = @{}
    $displaySection -split '\r?\n' | ForEach-Object {
        # Ignore comments and blank lines
        if ($_ -match "^\s*([^=\s#][^=]*?)\s*=\s*(.+?)\s*$") {
            $canonical = $matches[1].Trim()
            $display = $matches[2].Trim()
            $displayNameMap[$canonical] = $display
        }
    }

    # Build final map from keyword to display name
    $normalizationSection -split '\r?\n' | ForEach-Object {
        # Ignore comments and blank lines
        if ($_ -match "^\s*([^=\s#][^=]*?)\s*=\s*(.+?)\s*$") {
            $canonical = $matches[1].Trim()
            $keywords = $matches[2].Split(',') | ForEach-Object { $_.Trim() }
            if ($displayNameMap.ContainsKey($canonical)) {
                $displayName = $displayNameMap[$canonical]
                foreach ($keyword in $keywords) {
                    $modelNameMap[$keyword] = $displayName
                }
            }
        }
    }

    if ($modelNameMap.Count -eq 0) {
        throw "Model name map was created but is empty. Check config.ini formatting."
    }
}
catch {
    Write-Warning "Could not read or parse model names from config.ini. Full paths will be shown instead. Error: $($_.Exception.Message)"
    $modelNameMap = @{} # Ensure it's an empty hashtable on failure
}

# This helper function has been removed. The audit logic is now integrated
# directly into the main script body for improved clarity and robustness.

# --- Function to execute a Python script and check for errors ---
function Invoke-PythonScript {
    param (
        [string]$StepName,
        [string]$ScriptName,
        [string[]]$Arguments
    )

    # --- Display Logic (using relative path for cleanliness) ---
    $displayArguments = $Arguments.Clone()
    if ($displayArguments.Count -gt 0 -and (Test-Path -Path $displayArguments[0])) {
        $displayArguments[0] = Resolve-Path -Path $displayArguments[0] -Relative
    }
    $displayFinalArgs = $prefixArgs + $ScriptName + $displayArguments
    
    Write-Host "  Executing:" -ForegroundColor Gray
    Write-Host "  $executable $($displayFinalArgs -join ' ')"

    # --- Execution Logic (using original absolute path for robustness) ---
    $finalArgs = $prefixArgs + $ScriptName + $Arguments
    $output = & $executable $finalArgs 2>&1

    # Check the exit code of the last command immediately
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n--- Full script output on failure ---" -ForegroundColor Yellow
        $output | Write-Host
        throw "ERROR: Step '${StepName}' failed with exit code ${LASTEXITCODE}. Aborting."
    }

    if ($PSBoundParameters.ContainsKey('Verbose')) {
        $output | Write-Host
    }
    else {
                # By default, parse the output and show a clean, high-level summary.
        if ($ScriptName -like "*compile_study_results.py*") {
            # The Python script is expected to print its own clean summary.
            # This just prints lines that look like summary lines (starting with 'Found' or '->').
            $output | Select-String -Pattern "^(Found|  ->)" | ForEach-Object { "  $($_.Line)" }
            $output | Select-String -Pattern "Study compilation complete." | ForEach-Object { "  $($_.Line)" }
        }
        elseif ($ScriptName -like "*study_analyzer.py*") {
            $metricName = $null
            $conclusion = $null

            $output | Select-String -Pattern "^Full analysis log", "^Applying filter", "^Excluding", "^Analysis will proceed" | ForEach-Object { "  - $($_.Line)" }

            foreach ($line in $output) {
                if ($line -match "ANALYSIS FOR METRIC: '(.*)'") {
                    if ($metricName) {
                        Write-Host "  - METRIC '$metricName': $conclusion. Plots saved."
                    }
                    $metricName = $matches[1]
                    $conclusion = "summary not found"
                }
                elseif ($line -match "^Conclusion: (.*)") {
                    $conclusion = $matches[1].Trim()
                }
            }
            if ($metricName) {
                Write-Host "  - METRIC '$metricName': $conclusion. Plots saved."
            }
        }
        else {
            $output | Write-Host
        }
    }

    Write-Host "Step '${StepName}' completed successfully." -ForegroundColor Green
}

# --- Main Script Logic ---
$LogFilePath = $null
try {
    if (-not $NoLog.IsPresent) {
        $LogFilePath = Join-Path -Path $StudyDirectory -ChildPath "study_evaluation_log.txt"
        Start-Transcript -Path $LogFilePath -Force | Out-Null
        
        Write-Host ""
        Write-Host "The evaluation log will be saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $LogFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
    }

    # Resolve the path to ensure it's absolute and check for existence
    $ResolvedPath = Resolve-Path -Path $StudyDirectory -ErrorAction Stop
    
    $headerLine = "#" * 80
    $relativePath = Resolve-Path -Path $StudyDirectory -Relative
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Starting Study Evaluation for:") -ForegroundColor Green
    Write-Host (Format-Banner "'$($relativePath)'") -ForegroundColor Green
    Write-Host "$headerLine" -ForegroundColor Green

    # --- Step 1/5: Run Pre-Analysis Audit ---
    Write-Host "[1/5: Pre-Analysis Audit] Verifying study readiness..." -ForegroundColor Cyan
    $auditScriptPath = Join-Path $PSScriptRoot "audit_study.ps1"
    
    # Use a hashtable for splatting to ensure named parameters are used correctly.
    $auditSplat = @{
        StudyDirectory = $StudyDirectory
        NoHeader       = $true
        ErrorAction    = "Stop"
    }
    if (-not [string]::IsNullOrEmpty($ConfigPath)) {
        $auditSplat['ConfigPath'] = $ConfigPath
    }
    $auditOutput = & $auditScriptPath @auditSplat
    if ($LASTEXITCODE -ne 0) {
        Write-Host "`n--- Audit Report on Failure ---" -ForegroundColor Yellow
        $auditOutput | Write-Host # Display the captured report from the audit script
        throw "Pre-analysis audit failed. See report above. Evaluation cannot continue."
    }
    Write-Host "Step '1/5: Pre-Analysis Audit' completed successfully." -ForegroundColor Green

    # --- Step 2/5: Check for Existing Results & Staleness ---
    Write-Host "`n[2/5: Staleness Check] Checking for existing analysis results..." -ForegroundColor Cyan
    $inputFiles = Get-ChildItem -Path $StudyDirectory -Recurse -Filter "EXPERIMENT_results.csv"
    $studyCsvPath = Join-Path $StudyDirectory "STUDY_results.csv"
    $anovaDirPath = Join-Path $StudyDirectory "anova"
    $outputArtifacts = @( (Get-Item -Path $studyCsvPath -ErrorAction SilentlyContinue), (Get-Item -Path $anovaDirPath -ErrorAction SilentlyContinue) ) | Where-Object { $_ }

    if ($outputArtifacts.Count -eq 0) {
        Write-Host "  - No existing analysis artifacts found. Proceeding automatically." -ForegroundColor Green
    }
    else {
        $newestInputTimestamp = ($inputFiles | Measure-Object -Property LastWriteTime -Maximum).Maximum
        $oldestOutputTimestamp = ($outputArtifacts | Measure-Object -Property LastWriteTime -Minimum).Minimum

        if ($newestInputTimestamp -gt $oldestOutputTimestamp) {
            Write-Host "  - STALE DATA: Input experiment files are newer than existing analysis." -ForegroundColor Yellow
            Write-Host "  - Automatically re-running..." -ForegroundColor Cyan
        }
        else {
            Write-Host "  - WARNING: This study has already been evaluated, and the results are up to date. ✨" -ForegroundColor Yellow
            Write-Host "  - If you choose to proceed, a backup of the existing results will be created first." -ForegroundColor Yellow
            $choice = Read-Host "  - Do you wish to re-run the evaluation? (Y/N)"
            if ($choice.Trim().ToLower() -ne 'y') {
                Write-Host "`nEvaluation aborted by user.`n" -ForegroundColor Yellow
                Write-Host "[3/5: Backup Previous Results] SKIPPED" -ForegroundColor Cyan
                Write-Host "[4/5: Compile Study Results] SKIPPED" -ForegroundColor Cyan
                Write-Host "[5/5: Run Final Analysis (ANOVA)] SKIPPED" -ForegroundColor Cyan
                return
            }
             Write-Host "  - Proceeding with re-analysis as requested." -ForegroundColor Cyan
        }
    }
    Write-Host "Step '2/5: Staleness Check' completed successfully." -ForegroundColor Green

    # --- Step 3/5: Backup Previous Results ---
    if ($outputArtifacts.Count -gt 0) {
        Write-Host "`n[3/5: Backup] Backing up previous analysis results..." -ForegroundColor Cyan
        $archiveDir = Join-Path $StudyDirectory "archive"
        New-Item -Path $archiveDir -ItemType Directory -Force | Out-Null
        foreach ($artifact in $outputArtifacts) {
            $destination = Join-Path $archiveDir $artifact.Name
            if (Test-Path $destination) {
                Write-Host "  - Removing previous backup: $($artifact.Name)"
                Remove-Item -Path $destination -Recurse -Force
            }
            Write-Host "  - Archiving: $($artifact.Name)"
            Move-Item -Path $artifact.FullName -Destination $destination -Force
        }
        Write-Host "Step '3/5: Backup' completed successfully." -ForegroundColor Green
    }
    else {
        Write-Host "`n[3/5: Backup] No previous results to back up. SKIPPED" -ForegroundColor Cyan
    }

    # --- Step 4/5: Compile All Results into a Master CSV ---
    $step4Header = "[4/5: Compile Study Results] Compiling all experiment data..."
    Write-Host "`n$step4Header" -ForegroundColor Cyan
    $compileArgs = @($ResolvedPath)
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $compileArgs += "--config-path", $ConfigPath }
    Invoke-PythonScript -StepName "4/5: Compile Study Results" -ScriptName "src/compile_study_results.py" -Arguments $compileArgs

    # --- Step 5/5: Run Final Analysis (ANOVA) ---
    $step5Header = "[5/5: Run Final Analysis (ANOVA)] Performing statistical analysis..."
    Write-Host "`n$step5Header" -ForegroundColor Cyan
    $analyzeArgs = @($ResolvedPath)
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $analyzeArgs += "--config-path", $ConfigPath }
    Invoke-PythonScript -StepName "5/5: Run Final Analysis (ANOVA)" -ScriptName "src/analyze_study_results.py" -Arguments $analyzeArgs

    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Evaluation Finished Successfully!") -ForegroundColor Green
    Write-Host "$headerLine" -ForegroundColor Green

}
catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY EVALUATION FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "`nERROR: $($_.Exception.Message)`n" -ForegroundColor Red # Print the captured exception message cleanly
    # Exit with a non-zero status code to indicate failure to other automation tools
    exit 1
}
finally {
    if (-not $NoLog.IsPresent -and (Test-Path -LiteralPath $LogFilePath)) {
        Stop-Transcript | Out-Null
        
        try {
            $logContent = Get-Content -Path $LogFilePath -Raw
            $cleanedContent = $logContent -replace '(?s)\*+\r?\nPowerShell transcript start.*?\*+\r?\n\r?\n', ''
            $cleanedContent = $cleanedContent -replace '(?s)\*+\r?\nPowerShell transcript end.*', ''
            Set-Content -Path $LogFilePath -Value $cleanedContent.Trim() -Force
        }
        catch {
            Write-Warning "Could not clean the transcript log file: $($_.Exception.Message)"
        }

        Write-Host "`nThe evaluation log has been saved to:" -ForegroundColor Gray
        $relativePath = Resolve-Path -Path $LogFilePath -Relative
        Write-Host $relativePath -ForegroundColor Gray
        Write-Host "" # Add a final blank line for spacing
    }
}

# === End of compile_study.ps1 ===
