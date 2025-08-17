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
# Filename: prepare_data.ps1

<#
.SYNOPSIS
    Orchestrates the entire data preparation pipeline, from raw data fetching
    to final database generation.

.DESCRIPTION
    This script is a master controller for the multi-stage data preparation
    workflow. It intelligently manages the entire pipeline, making it resumable,
    interrupt-safe, and user-friendly.

    Key Features:
    - Automatically checks the state of the pipeline and resumes from the first
      incomplete step.
    - Pauses with clear instructions when a manual user action (e.g., using
      Solar Fire) is required.
    - Provides a clear summary report of which data files exist or are missing.
    - Can be run in a read-only "report-only" mode to check the pipeline's status
      without making any changes.
    - Supports a '--force' flag for non-interactive, automated execution.

.PARAMETER ReportOnly
    If specified, the script will only display the current status of the data
    pipeline and then exit without running any scripts.

.PARAMETER Force
    If specified, the script will bypass the interactive confirmation prompt and
    proceed with the run.

.EXAMPLE
    # Run the full pipeline interactively. It will check for existing files and prompt
    # for confirmation if any are found.
    .\prepare_data.ps1

.EXAMPLE
    # Get a read-only status report of the data pipeline.
    .\prepare_data.ps1 -ReportOnly

.EXAMPLE
    # Run the pipeline non-interactively, resuming from the last completed step.
    .\prepare_data.ps1 -Force
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [switch]$ReportOnly,

    [Parameter(Mandatory=$false)]
    [switch]$Force
)

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GREEN = "`e[92m"
$C_YELLOW = "`e[93m"
$C_RED = "`e[91m"
$C_CYAN = "`e[96m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"

# --- Define Pipeline Steps and Artifacts ---
$PipelineSteps = @(
    @{ Name="Fetch Raw ADB Data";         Script="src/fetch_adb_data.py";             OutputFile="data/sources/adb_raw_export.txt";                   Type="Automated" },
    @{ Name="Find Wikipedia Links";       Script="src/find_wikipedia_links.py";        OutputFile="data/processed/adb_wiki_links.csv";                Type="Automated" },
    @{ Name="Validate Wikipedia Pages";   Script="src/validate_wikipedia_pages.py";   OutputFile="data/reports/adb_validation_report.csv";           Type="Automated" },
    @{ Name="Select Eligible Candidates"; Script="src/select_eligible_candidates.py"; OutputFile="data/processed/adb_eligible_candidates.txt";        Type="Automated" },
    @{ Name="Generate Eminence Scores";   Script="src/generate_eminence_scores.py";   OutputFile="data/foundational_assets/eminence_scores.csv";     Type="Automated" },
    @{ Name="Generate OCEAN Scores";      Script="src/generate_ocean_scores.py";      OutputFile="data/foundational_assets/ocean_scores.csv";        Type="Automated" },
    @{ Name="Select Final Candidates";    Script="src/select_final_candidates.py";    OutputFile="data/processed/adb_final_candidates.txt";          Type="Automated" },
    @{ Name="Prepare SF Import File";     Script="src/prepare_sf_import.py";          OutputFile="data/intermediate/sf_data_import.txt";             Type="Automated" },
    @{ Name="MANUAL: Solar Fire Processing"; OutputFile="data/foundational_assets/sf_chart_export.csv"; Type="Manual"; Instructions=@"
The script is paused. Please perform the manual Solar Fire import, calculation, and chart export process. The required output file is:
$($C_CYAN)data/foundational_assets/sf_chart_export.csv$($C_RESET)
"@
    },
    @{ Name="MANUAL: Delineation Export";    OutputFile="data/foundational_assets/sf_delineations_library.txt"; Type="Manual"; Instructions=@"
The script is paused. Please perform the one-time Solar Fire delineation library export. The required output file is:
$($C_CYAN)data/foundational_assets/sf_delineations_library.txt$($C_RESET)
"@
    },
    @{ Name="Neutralize Delineations";    Script="src/neutralize_delineations.py";    OutputFile="data/foundational_assets/neutralized_delineations/aspects.csv"; Type="Automated" },
    @{ Name="Create Subject Database";    Script="src/create_subject_db.py";          OutputFile="data/processed/subject_db.csv";                    Type="Automated" },
    @{ Name="Generate Personalities DB";  Script="src/generate_personalities_db.py";  OutputFile="personalities_db.txt";                             Type="Automated" }
)

# --- Helper Functions ---
function Format-Banner {
    param([string]$Message, [string]$Color = $C_CYAN)
    $line = '#' * 80
    $bookend = "###"
    $contentWidth = $line.Length - ($bookend.Length * 2)
    $paddingNeeded = $contentWidth - $Message.Length - 2
    $leftPad = [Math]::Floor($paddingNeeded / 2)
    $rightPad = [Math]::Ceiling($paddingNeeded / 2)
    $centeredMsg = "$bookend $(' ' * $leftPad)$Message$(' ' * $rightPad) $bookend"

    Write-Host ""
    Write-Host "$Color$line"
    Write-Host "$Color$centeredMsg"
    Write-Host "$Color$line$C_RESET"
    Write-Host ""
}

function Show-PipelineStatus {
    param([array]$Steps)

    Format-Banner "Data Preparation Pipeline Status" $C_YELLOW

    $nameWidth = 40
    $statusWidth = 12
    Write-Host ("{0,-$nameWidth} {1}" -f "Step", "Status")
    Write-Host ("-" * $nameWidth + " " + "-" * $statusWidth)

    $filesExist = $false
    foreach ($step in $Steps) {
        if (Test-Path $step.OutputFile) {
            $status = "$($C_GREEN)[EXISTS]$($C_RESET)"
            $filesExist = $true
        } else {
            if ($step.Type -eq 'Manual') {
                $status = "$($C_MAGENTA)[PENDING]$($C_RESET)"
            } else {
                $status = "$($C_RED)[MISSING]$($C_RESET)"
            }
        }
        Write-Host ("{0,-$nameWidth} {1}" -f $step.Name, $status)
    }
    Write-Host ""
    return $filesExist
}

# --- Main Script Logic ---
$ScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$exitCode = 0

try {
    # Auto-detect execution environment
    $executable = "pdm"
    $prefixArgs = @("run", "python")
    if (-not (Get-Command pdm -ErrorAction SilentlyContinue)) {
        throw "PDM not found. Please ensure PDM is installed and in your PATH."
    }

    # --- Step 1: Initial State Check and User Confirmation ---
    $anyFileExists = Show-PipelineStatus -Steps $PipelineSteps

    if ($ReportOnly.IsPresent) {
        Write-Host "${C_CYAN}Report-only mode enabled. Exiting.${C_RESET}"
        return
    }

    if ($anyFileExists -and -not $Force.IsPresent) {
        Write-Host "${C_YELLOW}WARNING: One or more data files already exist."
        Write-Host "The pipeline will resume from the first incomplete step."
        $confirm = Read-Host "Do you wish to proceed? (Y/N)"
        if ($confirm.Trim().ToLower() -ne 'y') {
            Write-Host "`nOperation cancelled by user."
            Show-PipelineStatus -Steps $PipelineSteps # Show status again on exit
            return
        }
    }

    # --- Step 2: Sequential Execution ---
    $totalSteps = $PipelineSteps.Count
    $stepCounter = 0
    foreach ($step in $PipelineSteps) {
        $stepCounter++
        $stepName = $step.Name
        $outputFile = $step.OutputFile

        Format-Banner "Step ${stepCounter}/${totalSteps}: ${stepName}"

        if (Test-Path $outputFile) {
            Write-Host "${C_GREEN}Output file '$outputFile' already exists. Skipping step.$($C_RESET)"
            continue
        }

        # Handle manual vs automated steps
        if ($step.Type -eq 'Manual') {
            throw "Manual step required. $($step.Instructions)`n`nAfter completing this step, re-run this script to continue the pipeline."
        }

        # This is an automated step
        $scriptPath = $step.Script
        $fullScriptPath = Join-Path $ScriptRoot $scriptPath
        $arguments = $prefixArgs + $fullScriptPath

        & $executable @arguments
        $exitCode = $LASTEXITCODE

        if ($exitCode -ne 0) {
            throw "Script '$scriptPath' failed with exit code $exitCode. Halting pipeline."
        }
    }

    Format-Banner "Data Preparation Pipeline Completed Successfully" $C_GREEN
}
catch {
    $errorMessage = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.Exception.Message } else { $_ }
    Format-Banner "PIPELINE HALTED" $C_RED
    Write-Host "${C_RED}REASON: $errorMessage${C_RESET}`n"
    $exitCode = 1
}
finally {
    Write-Host "${C_GRAY}--- Final Pipeline Status ---${C_RESET}"
    Show-PipelineStatus -Steps $PipelineSteps | Out-Null
    exit $exitCode
}

# === End of prepare_data.ps1 ===
