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
    Orchestrates the entire data preparation pipeline, from "Data Sourcing"
    to final "Profile Generation".

.DESCRIPTION
    This script is a master controller for the multi-stage data preparation
    workflow. It intelligently manages the entire pipeline, making it resumable,
    interrupt-safe, and user-friendly.

    Key Features:
    - Manages all four stages of the pipeline: Data Sourcing, Candidate
      Qualification, LLM-based Candidate Selection, and Profile Generation.
    - Is aware of the 'bypass_candidate_selection' flag in config.ini and will
      efficiently skip the two LLM-based scoring steps when it is active.
    - Automatically checks the state of the pipeline and resumes from the first
      incomplete step.
    - Pauses with clear instructions when a manual user action is required.
    - Provides a clear summary report of which data files exist or are missing.
    - Can be run in a read-only "report-only" mode to check the pipeline's status.
    - Supports an "interactive" mode that pauses for user confirmation before
      executing each step, perfect for learning the pipeline.

.PARAMETER ReportOnly
    If specified, the script will only display the current status of the data
    pipeline and then exit without running any scripts.

.PARAMETER Force
    If specified, the script will bypass the interactive confirmation prompt and
    proceed with the run.

.PARAMETER Interactive
    If specified, the script will pause for confirmation before each step,
    allowing the user to inspect the state of the pipeline.

.EXAMPLE
    # Run the full pipeline, resuming from the first incomplete step.
    .\prepare_data.ps1

.EXAMPLE
    # Run the pipeline in interactive "guided tour" mode.
    .\prepare_data.ps1 -Interactive

.EXAMPLE
    # Get a read-only status report of the data pipeline.
    .\prepare_data.ps1 -ReportOnly
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [switch]$ReportOnly,

    [Parameter(Mandatory=$false)]
    [Alias('NonInteractive')]
    [switch]$Force,

    [Parameter(Mandatory=$false)]
    [switch]$Interactive,

    [Parameter(Mandatory=$false)]
    [switch]$NoFinalReport,

    [Parameter(Mandatory=$false)]
    [switch]$Resumed,

    [Parameter(Mandatory=$false)]
    [switch]$SilentHalt
)

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GREEN = "`e[92m"
$C_YELLOW = "`e[93m"
$C_RED = "`e[91m"
$C_CYAN = "`e[96m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"
$C_BLUE = "`e[94m"

# Set UTF-8 encoding for console output to handle Unicode characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# --- Define Pipeline Steps and Artifacts ---
# This data structure drives the entire orchestration logic.
$PipelineSteps = @(
    @{ Stage="1. Data Sourcing";        Name="Fetch Raw ADB Data";         Script="src/fetch_adb_data.py";             Inputs=@("Live Astro-Databank Website");            Output="data/sources/adb_raw_export.txt";                   Type="Automated"; Description="Fetches the initial raw dataset from the live Astro-Databank." },
    @{ Stage="2. Candidate Qualification"; Name="Find Wikipedia Links";       Script="src/find_wikipedia_links.py";        Inputs=@("data/sources/adb_raw_export.txt");        Output="data/processed/adb_wiki_links.csv";                Type="Automated"; Description="Finds a best-guess Wikipedia URL for each subject." },
    @{ Stage="2. Candidate Qualification"; Name="Validate Wikipedia Pages";   Script="src/validate_wikipedia_pages.py";   Inputs=@("data/processed/adb_wiki_links.csv");      Output="data/reports/adb_validation_report.csv";           Type="Automated"; Description="Validates each Wikipedia page for content, language, and redirects." },
    @{ Stage="2. Candidate Qualification"; Name="Select Eligible Candidates"; Script="src/select_eligible_candidates.py"; Inputs=@("data/sources/adb_raw_export.txt", "data/reports/adb_validation_report.csv"); Output="data/intermediate/adb_eligible_candidates.txt";      Type="Automated"; Description="Applies deterministic data quality filters to create a pool of eligible candidates." },
    @{ Stage="3. Candidate Selection";   Name="Generate Eminence Scores";   Script="src/generate_eminence_scores.py";   Inputs=@("data/intermediate/adb_eligible_candidates.txt"); Output="data/foundational_assets/eminence_scores.csv";   Type="Automated"; Description="Generates a calibrated eminence score for each eligible candidate using an LLM." },
    @{ Stage="3. Candidate Selection";   Name="Generate OCEAN Scores";      Script="src/generate_ocean_scores.py";      Inputs=@("data/foundational_assets/eminence_scores.csv"); Output="data/foundational_assets/ocean_scores.csv";        Type="Automated"; Description="Generates OCEAN personality scores and determines the final dataset size based on diversity." },
    @{ Stage="3. Candidate Selection";   Name="Select Final Candidates";    Script="src/select_final_candidates.py";    Inputs=@("data/intermediate/adb_eligible_candidates.txt", "data/foundational_assets/eminence_scores.csv", "data/foundational_assets/ocean_scores.csv"); Output="data/intermediate/adb_final_candidates.txt";        Type="Automated"; Description="Filters, transforms, and sorts the final subject set based on the LLM scoring." },
    @{ Stage="4. Profile Generation";    Name="Prepare SF Import File";     Script="src/prepare_sf_import.py";          Inputs=@("data/intermediate/adb_final_candidates.txt"); Output="data/intermediate/sf_data_import.txt";            Type="Automated"; Description="Formats the final subject list for import into the Solar Fire software." },
    @{ Stage="4. Profile Generation";    Name="Solar Fire Processing"; Inputs=@("data/intermediate/sf_data_import.txt"); Output="data/foundational_assets/sf_chart_export.csv"; Type="Manual"; Description="The pipeline is paused. Please perform the manual Solar Fire import, calculation, and chart export process." },
    @{ Stage="4. Profile Generation";    Name="Delineation Export";    Inputs=@("Solar Fire Software"); Output="data/foundational_assets/sf_delineations_library.txt"; Type="Manual"; Description="The pipeline is paused. Please perform the one-time Solar Fire delineation library export." },
    @{ Stage="4. Profile Generation";    Name="Neutralize Delineations";    Script="src/neutralize_delineations.py";    Inputs=@("data/foundational_assets/sf_delineations_library.txt"); Output="data/foundational_assets/neutralized_delineations/balances_quadrants.csv"; Type="Automated"; Description="Rewrites esoteric texts into neutral psychological descriptions using an LLM." },
    @{ Stage="4. Profile Generation";    Name="Create Subject Database";    Script="src/create_subject_db.py";          Inputs=@("data/foundational_assets/sf_chart_export.csv", "data/intermediate/adb_final_candidates.txt"); Output="data/processed/subject_db.csv";                  Type="Automated"; Description="Integrates chart data with the final subject list to create a master database." },
    @{ Stage="4. Profile Generation";    Name="Generate Personalities DB";  Script="src/generate_personalities_db.py";  Inputs=@("data/processed/subject_db.csv", "data/foundational_assets/neutralized_delineations/"); Output="data/processed/personalities_db.txt";            Type="Automated"; Description="Assembles the final personalities database from subject data and the neutralized text library." }
)

# --- Helper Functions ---
function Format-Banner {
    param([string]$Message, [string]$Color = $C_CYAN)
    $line = '#' * 80; $bookend = "###"; $contentWidth = $line.Length - ($bookend.Length * 2)
    $paddingNeeded = $contentWidth - $Message.Length - 2; $leftPad = [Math]::Floor($paddingNeeded / 2); $rightPad = [Math]::Ceiling($paddingNeeded / 2)
    $centeredMsg = "$bookend $(' ' * $leftPad)$Message$(' ' * $rightPad) $bookend"
    Write-Host "`n$Color$line"; Write-Host "$Color$centeredMsg"; Write-Host "$Color$line$C_RESET`n"
}

function Get-ConfigValue {
    param([string]$FilePath, [string]$Section, [string]$Key, [string]$DefaultValue)
    if (-not (Test-Path $FilePath)) {
        return $DefaultValue
    }
    
    $currentSection = ""
    $config = @{}
    
    Get-Content $FilePath | ForEach-Object {
        if ($_ -match '^\s*\[(.+)\]\s*$') {
            $currentSection = $matches[1]
            if (-not $config.ContainsKey($currentSection)) {
                $config[$currentSection] = @{}
            }
        } elseif ($_ -match '^\s*([^#;=]+)\s*=\s*(.*)') {
            if ($currentSection) {
                $config[$currentSection][$matches[1].Trim()] = $matches[2].Trim()
            }
        }
    }
    
    if ($config[$Section] -and $config[$Section].ContainsKey($Key)) {
        return $config[$Section][$Key]
    } else {
        return $DefaultValue
    }
}

function Show-PipelineStatus {
    param([array]$Steps, [string]$BaseDirectory = ".")
    Format-Banner "Data Preparation Pipeline Status" $C_CYAN
    $nameWidth = 40; $statusWidth = 12
    Write-Host ("{0,-$nameWidth} {1}" -f "Step", "Status"); Write-Host ("-" * $nameWidth + " " + "-" * $statusWidth)
    $filesExist = $false
    foreach ($step in $Steps) {
        $outputFile = Join-Path $BaseDirectory $step.Output
        if (Test-Path $outputFile) {
            $status = "$($C_GREEN)[EXISTS]$($C_RESET)"; $filesExist = $true
        } else {
            $status = if ($step.Type -eq 'Manual') { "${C_YELLOW}[PENDING]${C_RESET}" } else { "${C_RED}[MISSING]${C_RESET}" }
        }
        Write-Host ("{0,-$nameWidth} {1}" -f $step.Name, $status)
    }
    Write-Host ""; return $filesExist
}

# --- Main Script Logic ---
$ProjectRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$WorkingDirectory = $ProjectRoot
$SandboxMode = $false

# Check if we're running in a sandbox environment
if ($env:PROJECT_SANDBOX_PATH -and (Test-Path $env:PROJECT_SANDBOX_PATH)) {
    Write-Host "${C_YELLOW}Sandbox mode detected. Operating in: $env:PROJECT_SANDBOX_PATH${C_RESET}"
    $WorkingDirectory = $env:PROJECT_SANDBOX_PATH
    $SandboxMode = $true
} else {
    # Check if current directory contains a config.ini (indicating we're in a sandbox)
    if ((Test-Path "config.ini") -and ((Get-Location).Path -ne $ProjectRoot)) {
        Write-Host "${C_YELLOW}Sandbox mode detected. Operating in current directory.${C_RESET}"
        $WorkingDirectory = Get-Location
        $SandboxMode = $true
    }
}

$exitCode = 0
$configFile = Join-Path $WorkingDirectory "config.ini"
$bypassConfigValue = Get-ConfigValue -FilePath $configFile -Section "DataGeneration" -Key "bypass_candidate_selection" -DefaultValue "false"
$bypassScoring = $bypassConfigValue.ToLower() -eq "true"
if ($SandboxMode) {
    Write-Host "${C_CYAN}Config: bypass_candidate_selection = $bypassConfigValue (parsed as: $bypassScoring)${C_RESET}"
}

try {
    if (-not (Get-Command pdm -ErrorAction SilentlyContinue)) { throw "PDM not found. Please ensure PDM is installed and in your PATH." }

    $anyFileExists = $false
    if (-not $SandboxMode) {
        $anyFileExists = Show-PipelineStatus -Steps $PipelineSteps -BaseDirectory $WorkingDirectory
    } else {
        # In sandbox mode, we just need to know if any files exist to potentially prompt the user.
        $anyFileExists = (Get-ChildItem -Path $WorkingDirectory -Recurse -File | Select-Object -First 1) -ne $null
    }
    if ($ReportOnly.IsPresent) { Write-Host "${C_CYAN}Report-only mode enabled. Exiting.${C_RESET}"; return }

    if ($anyFileExists -and -not $Force.IsPresent -and -not $Interactive -and -not $SandboxMode) {
        Write-Host "${C_YELLOW}WARNING: One or more data files already exist."
        Write-Host "The pipeline will resume from the first incomplete step."
        $confirm = Read-Host "Do you wish to proceed? (Y/N)"
        if ($confirm.Trim().ToLower() -ne 'y') { throw "Operation cancelled by user." }
    }

    $totalSteps = $PipelineSteps.Count; $stepCounter = 0; $lastStage = ""
    foreach ($step in $PipelineSteps) {
        $stepCounter++
        
        $outputFile = Join-Path $WorkingDirectory $step.Output
        if ($step.Stage -ne $lastStage) {
            $lastStage = $step.Stage
            # Don't print the banner for a new stage if its very first step's output already exists.
            if (-not (Test-Path $outputFile)) {
                Format-Banner "BEGIN STAGE: $($lastStage.ToUpper())" $C_CYAN
            }
        }

        if ($bypassScoring -and ($step.Name -in "Generate Eminence Scores", "Generate OCEAN Scores")) {
            Write-Host "${C_YELLOW}Bypass mode is active. Skipping step: $($step.Name)${C_RESET}"; continue
        }
        $outputFile = Join-Path $WorkingDirectory $step.Output
        if (Test-Path $outputFile) {
            # In resumed sandbox mode, we want silent skipping.
            # Otherwise, inform the user why a step is being skipped.
            if (-not ($SandboxMode -and $Resumed.IsPresent)) {
                Write-Host "Output exists for step '$($step.Name)'. Skipping." -ForegroundColor Yellow
            }
            continue
        }

        # For manual steps, halt the pipeline *before* printing the header.
        if ($step.Type -eq 'Manual') { throw $step.Description }

        $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
        Write-Host "`n" + ("-"*80) -ForegroundColor DarkGray
        Write-Host $stepHeader -ForegroundColor Blue
        Write-Host $step.Description -ForegroundColor Blue
        if ($SandboxMode) {
            Write-Host "`n  BASE DIRECTORY: $WorkingDirectory" -ForegroundColor DarkGray
        }
        Write-Host "`n  INPUTS:"; $step.Inputs | ForEach-Object { Write-Host "    - $_" }; Write-Host "`n  OUTPUT:"; Write-Host "    - $($step.Output)`n"
        if ($Interactive) { Read-Host -Prompt "Press Enter to execute this step (Ctrl+C to exit)..." }

        $scriptPath = Join-Path $ProjectRoot $step.Script
        $arguments = "run", "python", $scriptPath, "--force"
        if ($SandboxMode) {
            $arguments += "--sandbox-path", $WorkingDirectory
            # For neutralization step, bypass LLM in test mode
            if ($step.Name -eq "Neutralize Delineations") {
                $arguments += "--bypass-llm"
            }
            # Add flags to reduce log noise in test/sandbox mode
            if ($step.Name -in "Find Wikipedia Links", "Validate Wikipedia Pages") {
                $arguments += "--quiet"
            }
            if ($step.Name -in "Generate Eminence Scores", "Generate OCEAN Scores") {
                $arguments += "--no-summary"
            }
        }
        
        # For the final step, explicitly pass the correct output path in all modes
        if ($step.Name -eq "Generate Personalities DB") {
            $arguments += "-o", $outputFile
        }

        $scriptOutput = & pdm @arguments 2>&1
        $exitCode = $LASTEXITCODE
        
        if ($scriptOutput) {
            # Pass through the Python script's own output, preserving its color codes.
            $scriptOutput | ForEach-Object { Write-Host $_ }
        }
        
        if ($exitCode -ne 0) { 
            Write-Host "Script failed with exit code $exitCode" -ForegroundColor Red
            throw "Script '$($step.Script)' failed with exit code $exitCode. Halting pipeline." 
        }
        if ($Interactive) { Write-Host ""; Read-Host -Prompt "Step complete. Inspect the output, then press Enter to continue..." }
    }
    Format-Banner "Data Preparation Pipeline Completed Successfully" $C_GREEN
}
catch {
    $errorMessage = ""
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        $errorMessage = $_.Exception.Message
    } else {
        $errorMessage = $_
    }

    if (-not $SilentHalt.IsPresent) {
        Format-Banner "PIPELINE HALTED" $C_RED
        Write-Host "${C_RED}REASON: $errorMessage${C_RESET}"

        if ($errorMessage -match "The pipeline is paused") {
            Write-Host "`n${C_YELLOW}NEXT STEPS:${C_RESET}"
            Write-Host "1. Complete the manual step described in the message above."
            Write-Host "2. Once the required output file is in place, re-run this script."
            Write-Host "   The pipeline will automatically resume from where it stopped."
        }
    }
    $exitCode = 1
}
finally {
    if (-not $NoFinalReport.IsPresent) {
        Write-Host "`n${C_GRAY}--- Final Pipeline Status ---${C_RESET}"; Show-PipelineStatus -Steps $PipelineSteps -BaseDirectory $WorkingDirectory | Out-Null
    }
    exit $exitCode
}

# === End of prepare_data.ps1 ===
