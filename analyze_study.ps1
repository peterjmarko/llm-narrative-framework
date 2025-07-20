#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
# Filename: analyze_study.ps1

<#
.SYNOPSIS
    Audits, compiles, and analyzes a full study, providing a clean, high-level summary.

.DESCRIPTION
    This script is the main entry point for the entire post-processing workflow. It
    orchestrates three key scripts in sequence:
    1.  `audit_study.ps1`: To perform a full audit of the study. The script will halt
        with an error if any experiment is not in a validated state.
    2.  `experiment_aggregator.py`: To aggregate all individual run data into a master CSV.
    3.  `study_analysis.py`: To perform statistical analysis on the master CSV.

    By default, it provides a clean, high-level summary. For detailed, real-time
    output, use the -Verbose switch.

.PARAMETER StudyDirectory
    The path to the top-level study directory containing experiment folders that need
    to be analyzed (e.g., 'output/studies'). This is a mandatory parameter.

.EXAMPLE
    # Run analysis with the default high-level summary.
    .\analyze_study.ps1 "output/studies/My_Full_Study"

.EXAMPLE
    # Run analysis with detailed, real-time output for debugging.
    .\analyze_study.ps1 "output/studies/My_Full_Study" -Verbose
#>
[CmdletBinding()]
param (
    [Parameter(Mandatory = $true, Position = 0, HelpMessage = "Path to the top-level study directory.")]
    [string]$StudyDirectory
)

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

# --- Function to run the pre-analysis study audit ---
function Invoke-StudyAudit {
    param ([string]$StudyDirectory)

    $auditScriptPath = Join-Path $PSScriptRoot "audit_study.ps1"
    if (-not (Test-Path $auditScriptPath)) {
        throw "FATAL: audit_study.ps1 script not found at '$auditScriptPath'. Cannot verify study."
    }

    # Execute the audit script. It will print its own summary report.
    & $auditScriptPath $StudyDirectory

    if ($LASTEXITCODE -ne 0) {
        # The audit script's exit code signals the study state.
        throw "Study audit FAILED. Data is not ready for analysis. Please review the audit report above and address the issues before proceeding."
    }
    
    Write-Host "`nAudit PASSED. Study is validated and ready for analysis. Note: this process is automatic." -ForegroundColor Green
}

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
    Write-Host "[${StepName}] Executing:"
    Write-Host "  $executable $($finalArgs -join ' ')" # Indent the command path

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
        if ($ScriptName -like "*experiment_aggregator.py*") {
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
        elseif ($ScriptName -like "*study_analysis.py*") {
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

    Write-Host "Step '${StepName}' completed successfully."
    Write-Host ""
}

# --- Main Script Logic ---
try {
    # Resolve the path to ensure it's absolute and check for existence
    $ResolvedPath = Resolve-Path -Path $StudyDirectory -ErrorAction Stop
    
    Write-Host "`n######################################################" -ForegroundColor Green
    Write-Host "### Starting Study Processing for:" -ForegroundColor Green
    Write-Host "### '$($ResolvedPath)'" -ForegroundColor Green
    Write-Host "######################################################`n"

    # --- Step 1: Run Pre-Analysis Audit ---
    Invoke-StudyAudit -StudyDirectory $ResolvedPath

    # --- Step 2: Aggregate All Results into a Master CSV ---
    Invoke-PythonScript -StepName "2/3: Aggregate Results" -ScriptName "src/experiment_aggregator.py" -Arguments $ResolvedPath

    # --- Step 3: Run Final Statistical Analysis ---
    Invoke-PythonScript -StepName "3/3: Run Final Analysis (ANOVA)" -ScriptName "src/study_analysis.py" -Arguments $ResolvedPath

    Write-Host "######################################################" -ForegroundColor Green
    Write-Host "### Study Processing Finished Successfully!" -ForegroundColor Green
    Write-Host "######################################################`n"
    Write-Host "Final analysis logs and plots are located in:`n'$($ResolvedPath)\anova'" # Newline before path

}
catch {
    Write-Host "`n######################################################" -ForegroundColor Red
    Write-Host "### STUDY PROCESSING FAILED" -ForegroundColor Red
    Write-Host "######################################################" -ForegroundColor Red
    Write-Error $_.Exception.Message
    # Exit with a non-zero status code to indicate failure to other automation tools
    exit 1
}

# === End of analyze_study.ps1 ===
