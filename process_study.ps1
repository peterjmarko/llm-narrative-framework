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
# Filename: process_study.ps1

<#
.SYNOPSIS
    Audits, compiles, and analyzes a full study.

.DESCRIPTION
    This script is the main entry point for the entire post-processing workflow. It
    orchestrates three key Python scripts in sequence:
    1.  `audit_study.ps1`: Performs a full audit of the study. The script will halt
        if any experiment is not in a validated state.
    2.  `compile_study_results.py`: Compiles all experiment data into a master CSV.
    3.  `study_analyzer.py`: Performs statistical analysis on the master CSV.

    By default, it provides a clean, high-level summary. For detailed, real-time
    output, use the -Verbose switch.

.PARAMETER TargetDirectory
    The path to the top-level study directory containing experiment folders that need
    to be processed (e.g., 'output/studies'). This is a mandatory parameter.

.EXAMPLE
    # Process a study with the default high-level summary.
    .\process_study.ps1 "output/studies/My_Full_Study"

.EXAMPLE
    # Process a study with detailed, real-time output for debugging.
    .\process_study.ps1 "output/studies/My_Full_Study" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the target top-level study directory.")]
    [string]$TargetDirectory
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
    Write-Host "PDM detected. Using 'pdm run' to execute Python scripts." -ForegroundColor Cyan
    $executable = "pdm"
    $prefixArgs = "run", "python"
}
else {
    Write-Host "PDM not detected. Using standard 'python' command." -ForegroundColor Yellow
}

# --- Load and parse model display names from config.ini ---
$modelNameMap = @{}
try {
    # Assume config.ini is in the project root (where the script is).
    $configPath = Join-Path $PSScriptRoot "config.ini"
    if (-not (Test-Path $configPath)) {
        throw "config.ini not found at '$configPath'"
    }
    $configContent = Get-Content -Path $configPath -Raw

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

    # Combine prefix arguments with the script and its arguments
    $finalArgs = $prefixArgs + $ScriptName + $Arguments

    # Use -join to correctly format the command for logging
    Write-Host "[${StepName}] Executing:" -ForegroundColor Yellow
    Write-Host "  $executable $($finalArgs -join ' ')"

    # Execute the command with its final argument list, capturing output
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
        if ($ScriptName -like "*aggregate_experiments.py*") {
            $processedExperiments = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
            $outputBlock = $output -join "`n"
            $uniqueDisplayNames = $script:modelNameMap.Values | Get-Unique

            foreach ($line in $output) {
                if ($line -match "-> Generated summary:.*EXPERIMENT_results\.csv") {
                    $experimentDirName = (Split-Path -Path $line -Parent | Split-Path -Leaf)

                    $foundDisplayName = $null
                    # Find the display name by checking which one matches the folder structure
                    foreach ($displayName in $uniqueDisplayNames) {
                        # Convert "Grok 3 Mini" to "Grok_3_Mini" to match folder name style
                        $folderSearchString = $displayName.Replace(' ', '_')
                        if ($experimentDirName -match $folderSearchString) {
                            $foundDisplayName = $displayName
                            break
                        }
                    }

                    if ($foundDisplayName) {
                        $mappingStrategy = "unknown"
                        if ($experimentDirName -match 'map=(correct|random)') {
                            $mappingStrategy = $matches[1]
                        }
                        $uniqueExperimentId = "$foundDisplayName-$mappingStrategy"

                        if (-not $processedExperiments.Contains($uniqueExperimentId)) {
                            Write-Host "  - Aggregating: $foundDisplayName ($($mappingStrategy) map)"
                            [void]$processedExperiments.Add($uniqueExperimentId)
                        }
                    }
                }
            }
            
            # After the loop, print the final overall summary line
            $finalSummaryMatch = [regex]::Match($outputBlock, "-> Generated summary:\s*(.*final_summary_results\.csv.*)")
            if ($finalSummaryMatch.Success) {
                $finalSummaryLine = $finalSummaryMatch.Groups[1].Value.Trim()
                Write-Host "  - Generated final study summary:`n    $finalSummaryLine" # Newline before path
            }

            $output | Select-String -Pattern "Aggregation process finished" | ForEach-Object { $_.Line }

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
    Write-Host ""
}

# --- Main Script Logic ---
try {
    # Resolve the path to ensure it's absolute and check for existence
    $ResolvedPath = Resolve-Path -Path $TargetDirectory -ErrorAction Stop
    
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Green
    Write-Host "### Starting Study Processing for:" -ForegroundColor Green
    Write-Host "### '$($ResolvedPath)'" -ForegroundColor Green
    Write-Host "$headerLine`n" -ForegroundColor Green

    # --- Step 1: Run Pre-Analysis Audit ---
    Write-Host "[1/3: Pre-Analysis Audit] Verifying study readiness..." -ForegroundColor Yellow
    $auditScriptPath = Join-Path $PSScriptRoot "audit_study.ps1"
    if (-not (Test-Path $auditScriptPath)) {
        throw "FATAL: audit_study.ps1 script not found at '$auditScriptPath'. Cannot verify study."
    }

    # Run the audit and capture its output to check the final status.
    # The audit script prints its own report, so we don't need to explicitly write the output here.
    $auditOutput = & $auditScriptPath -StudyDirectory $TargetDirectory -ErrorAction Stop
    
    if ($LASTEXITCODE -ne 0) {
        # The audit script already prints a clear banner with the error and recommendation.
        # We just need to halt the processing.
        throw "Study audit failed. Please address the issues reported above before proceeding."
    }

    # If the audit passed (exit code 0), check if the study is already fully processed.
    if (($auditOutput | Out-String) -match "Overall Study Status: COMPLETE") {
        Write-Host "`nWarning: This study is already marked as COMPLETE." -ForegroundColor Yellow
        $choice = Read-Host "Re-running will overwrite existing analysis files. Do you wish to proceed? (Y/N)"
        if ($choice.Trim().ToLower() -ne 'y') {
            # Throwing an error here is a clean way to exit through the catch block.
            throw "Processing aborted by user."
        }
        Write-Host "Proceeding with re-analysis..." -ForegroundColor Yellow
    }
    
    Write-Host "Step '1/3: Pre-Analysis Audit' completed successfully." -ForegroundColor Green
    Write-Host ""

    # --- Step 2: Compile All Results into a Master CSV ---
    Invoke-PythonScript -StepName "2/3: Compile Study Results" -ScriptName "src/compile_study_results.py" -Arguments $ResolvedPath

    # --- Step 3: Run Final Statistical Analysis ---
    Invoke-PythonScript -StepName "3/3: Run Final Analysis (ANOVA)" -ScriptName "src/study_analyzer.py" -Arguments $ResolvedPath

    $headerLine = "#" * 80
    Write-Host "$headerLine" -ForegroundColor Green
    Write-Host (Format-Banner "Study Processing Finished Successfully!") -ForegroundColor Green
    Write-Host "$headerLine`n" -ForegroundColor Green

}
catch {
    $headerLine = "#" * 80
    Write-Host "`n$headerLine" -ForegroundColor Red
    Write-Host (Format-Banner "STUDY PROCESSING FAILED") -ForegroundColor Red
    Write-Host "$headerLine" -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red # Print the captured exception message cleanly
    # Exit with a non-zero status code to indicate failure to other automation tools
    exit 1
}

# === End of process_study.ps1 ===
