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
    - Supports a highly polished "interactive" mode that provides a step-by-step
      guided tour of the entire pipeline, complete with detailed explanations
      and color-coded feedback, making it an excellent learning tool.

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
    [switch]$SilentHalt,

    [Parameter(Mandatory=$false)]
    [switch]$TestMode,

    [Parameter(Mandatory=$false)]
    [switch]$SuppressConfigDisplay,

    [Parameter(Mandatory=$false)]
    [switch]$Plot,

    [Parameter(Mandatory=$false)]
    [int]$StopAfterStep = 0
)

# --- Pre-flight Cleanup ---
# Unset any lingering sandbox path from a previous test run to ensure correct context detection.
Remove-Item -Path "Env:PROJECT_SANDBOX_PATH" -ErrorAction SilentlyContinue

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_GRAY = "`e[90m"
$C_MAGENTA = "`e[95m"
$C_RED = "`e[91m"
$C_ORANGE = "`e[38;5;208m" # A specific orange from the 256-color palette
$C_YELLOW = "`e[93m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"
$C_BLUE = "`e[94m"

# Set UTF-8 encoding for console output to handle Unicode characters
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

# --- Define Pipeline Steps and Artifacts ---
# This data structure drives the entire orchestration logic.
$PipelineSteps = @(
    @{ Stage="1. Data Sourcing";        Name="Fetch Raw ADB Data";         Script="src/fetch_adb_data.py";             Inputs=@("Live Astro-Databank Website");            Output="data/sources/adb_raw_export.txt";                   Type="Automated"; Description="Fetches the initial raw dataset from the live Astro-Databank database." },
    @{ Stage="2. Candidate Qualification"; Name="Find Wikipedia Links";       Script="src/find_wikipedia_links.py";        Inputs=@("data/sources/adb_raw_export.txt");        Output="data/processed/adb_wiki_links.csv";                Type="Automated"; Description="Finds a best-guess Wikipedia URL for each subject." },
    @{ Stage="2. Candidate Qualification"; Name="Validate Wikipedia Pages";   Script="src/validate_wikipedia_pages.py";   Inputs=@("data/processed/adb_wiki_links.csv");      Output="data/reports/adb_validation_report.csv";           Type="Automated"; Description="Validates each Wikipedia page for content, language, and redirects." },
    @{ Stage="2. Candidate Qualification"; Name="Select Eligible Candidates"; Script="src/select_eligible_candidates.py"; Inputs=@("data/sources/adb_raw_export.txt", "data/reports/adb_validation_report.csv"); Output="data/intermediate/adb_eligible_candidates.txt";      Type="Automated"; Description="Applies deterministic data quality filters to create a pool of eligible candidates." },
    @{ Stage="3. Candidate Selection";   Name="Generate Eminence Scores";   Script="src/generate_eminence_scores.py";   Inputs=@("data/intermediate/adb_eligible_candidates.txt"); Output="data/foundational_assets/eminence_scores.csv";   Type="Automated"; Description="Generates a calibrated eminence score for each eligible candidate using an LLM." },
    @{ Stage="3. Candidate Selection";   Name="Generate OCEAN Scores";      Script="src/generate_ocean_scores.py";      Inputs=@("data/foundational_assets/eminence_scores.csv"); Output="data/foundational_assets/ocean_scores.csv";        Type="Automated"; Description="Generates OCEAN personality scores for each eligible candidate using an LLM." },
    @{ Stage="3. Candidate Selection";   Name="Select Final Candidates";    Script="src/select_final_candidates.py";    Inputs=@("data/intermediate/adb_eligible_candidates.txt", "data/foundational_assets/eminence_scores.csv", "data/foundational_assets/ocean_scores.csv"); Output="data/intermediate/adb_final_candidates.txt";        Type="Automated"; Description="Determines the final subject set based on the LLM scoring." },
    @{ Stage="4. Profile Generation";    Name="Prepare SF Import File";     Script="src/prepare_sf_import.py";          Inputs=@("data/intermediate/adb_final_candidates.txt"); Output="data/intermediate/sf_data_import.txt";            Type="Automated"; Description="Formats the final subject list for import into the Solar Fire software." },
    @{ Stage="4. Profile Generation";    Name="Astrology Data Export (Manual)"; Inputs=@("data/intermediate/sf_data_import.txt"); Output="data/foundational_assets/sf_chart_export.csv"; Type="Manual"; Description="The pipeline is paused. Please perform the manual Solar Fire import, calculation, and chart export process." },
    @{ Stage="4. Profile Generation";    Name="Delineation Library Export (Manual)";    Inputs=@("Solar Fire Software"); Output="data/foundational_assets/sf_delineations_library.txt"; Type="Manual"; Description="The pipeline is paused. Please perform the one-time Solar Fire delineation library export." },
    @{ Stage="4. Profile Generation";    Name="Neutralize Delineations";    Script="src/neutralize_delineations.py";    Inputs=@("data/foundational_assets/sf_delineations_library.txt"); Output="data/foundational_assets/neutralized_delineations/balances_quadrants.csv"; Type="Automated"; Description="Rewrites esoteric texts into neutral psychological descriptions using an LLM." },
    @{ Stage="4. Profile Generation";    Name="Create Subject Database";    Script="src/create_subject_db.py";          Inputs=@("data/foundational_assets/sf_chart_export.csv", "data/intermediate/adb_final_candidates.txt"); Output="data/processed/subject_db.csv";                  Type="Automated"; Description="Integrates chart data with the final subject list to create a master database." },
    @{ Stage="4. Profile Generation";    Name="Generate Personalities DB";  Script="src/generate_personalities_db.py";  Inputs=@("data/processed/subject_db.csv", "data/foundational_assets/neutralized_delineations/"); Output="data/personalities_db.txt";            Type="Automated"; Description="Assembles the final personalities database from subject data and the neutralized text library." }
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

function Get-ScriptDocstringSummary {
    param([string]$ScriptPath)
    try {
        $helperScript = Join-Path $ProjectRoot "scripts/analysis/get_docstring_summary.py"
        $summary = & python $helperScript $ScriptPath 2>$null
        return $summary.Trim()
    }
    catch {
        return "" # Return empty string on any error
    }
}

function Get-StepStatus {
    param([hashtable]$Step, [string]$BaseDirectory)
    $outputFile = Join-Path $BaseDirectory $Step.Output
    
    switch ($Step.Name) {
        "Generate Eminence Scores" {
            $summaryFile = Join-Path $BaseDirectory "data/reports/eminence_scores_summary.txt"
            if (-not (Test-Path $summaryFile)) {
                if (Test-Path $outputFile) { return "Incomplete" } else { return "Missing" }
            }
            try {
                $content = Get-Content $summaryFile -Raw
                $scored = ($content | Select-String -Pattern "Total Scored:\s+([\d,]+)").Matches[0].Groups[1].Value -replace ",", ""
                $total = ($content | Select-String -Pattern "Total in Source:\s+([\d,]+)").Matches[0].Groups[1].Value -replace ",", ""
                if ($scored -eq $total -and (Test-Path $outputFile)) { return "Complete" }
            } catch {
                # Fallback in case of parsing error
            }
            return "Incomplete"
        }
        "Generate OCEAN Scores" {
            $summaryFile = Join-Path $BaseDirectory "data/reports/ocean_scores_summary.txt"
            if (-not (Test-Path $summaryFile)) {
                if (Test-Path $outputFile) { return "Incomplete" } else { return "Missing" }
            }
            try {
                $content = Get-Content $summaryFile -Raw
                $scored = ($content | Select-String -Pattern "Total Scored:\s+([\d,]+)").Matches[0].Groups[1].Value -replace ",", ""
                $total = ($content | Select-String -Pattern "Total in Source:\s+([\d,]+)").Matches[0].Groups[1].Value -replace ",", ""
                if ($scored -eq $total -and (Test-Path $outputFile)) { return "Complete" }
            } catch {
                # Fallback in case of parsing error
            }
            return "Incomplete"
        }
        "Neutralize Delineations" {
            # This step's "Output" is one of its files, but it represents the whole directory.
            $delineationDir = Split-Path (Join-Path $BaseDirectory $Step.Output) -Parent
            if (-not (Test-Path $delineationDir)) { return "Missing" }
            $expectedFiles = @(
                "balances_elements.csv", "balances_modes.csv", "balances_hemispheres.csv",
                "balances_quadrants.csv", "balances_signs.csv", "points_in_signs.csv"
            )
            foreach ($file in $expectedFiles) {
                if (-not (Test-Path (Join-Path $delineationDir $file))) { return "Incomplete" }
            }
            return "Complete"
        }
        default {
            if (Test-Path $outputFile) { return "Complete" } else { return "Missing" }
        }
    }
}

function Backup-And-Remove {
    param([string]$ItemPath)
    # Convert to relative path for display
    $relativePath = $ItemPath.Replace($ProjectRoot, "").Replace("\", "/").TrimStart("/")
    
    if (-not (Test-Path $ItemPath)) {
        Write-Host "No file to backup at '$relativePath'" -ForegroundColor Gray
        return
    }

    try {
        $item = Get-Item $ItemPath
        $backupDir = Join-Path $ProjectRoot "data/backup"
        New-Item -ItemType Directory -Path $backupDir -ErrorAction SilentlyContinue | Out-Null
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

        if ($item.PSIsContainer) {
            $backupName = "$($item.Name)_$timestamp.zip"
            $backupPath = Join-Path $backupDir $backupName
            $relativeBackupPath = $backupPath.Replace($ProjectRoot, "").Replace("\", "/").TrimStart("/")
            Compress-Archive -Path $item.FullName -DestinationPath $backupPath -ErrorAction Stop
            Write-Host "Backed up directory '$relativePath' to '$relativeBackupPath'" -ForegroundColor Cyan
            Remove-Item -Recurse -Force -Path $item.FullName
        } else {
            $backupName = "$($item.BaseName).$timestamp$($item.Extension).bak"
            $backupPath = Join-Path $backupDir $backupName
            $relativeBackupPath = $backupPath.Replace($ProjectRoot, "").Replace("\", "/").TrimStart("/")
            Copy-Item -Path $item.FullName -Destination $backupPath
            Write-Host "Backed up file '$relativePath' to '$relativeBackupPath'" -ForegroundColor Cyan
            Remove-Item -Path $item.FullName
        }
    } catch {
        Write-Host "ERROR: Failed to back up and remove '$relativePath'. Reason: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

function Show-PipelineStatus {
    param([array]$Steps, [string]$BaseDirectory = ".")
    Format-Banner "Data Preparation Pipeline Status" $C_CYAN
    $nameWidth = 40; $statusWidth = 12
    Write-Host ("{0,-$nameWidth} {1}" -f "Step", "Status"); Write-Host ("-" * $nameWidth + " " + "-" * $statusWidth)
    $filesExist = $false
    $stepNumber = 0
    foreach ($step in $Steps) {
        $stepNumber++
        $stepStatus = Get-StepStatus -Step $step -BaseDirectory $BaseDirectory
        
        switch ($stepStatus) {
            "Complete"   { $status = "$($C_GREEN)[COMPLETE]$($C_RESET)"; $filesExist = $true }
            "Incomplete" { $status = "$($C_YELLOW)[INCOMPLETE]$($C_RESET)"; $filesExist = $true }
            default      { $status = if ($step.Type -eq 'Manual') { "$($C_YELLOW)[PENDING]$($C_RESET)" } else { "$($C_RED)[MISSING]$($C_RESET)" } }
        }
        $stepNameFormatted = "$($stepNumber). $($step.Name)"
        Write-Host ("{0,-$nameWidth} {1}" -f $stepNameFormatted, $status)
    }
    Write-Host ""; return $filesExist
}

function Show-DataCompletenessReport {
    param([string]$BaseDirectory = ".")
    
    $completionInfoPath = Join-Path $BaseDirectory "data/reports/pipeline_completion_info.json"
    
    if (Test-Path $completionInfoPath) {
        try {
            $completionInfo = Get-Content $completionInfoPath | ConvertFrom-Json
            
            # Check if any steps have missing data
            $hasIssues = $false
            foreach ($step in $completionInfo.PSObject.Properties) {
                if ($step.Value.missing_count -gt 0) {
                    $hasIssues = $true
                    break
                }
            }
            
            if ($hasIssues) {
                Write-Host "`n${C_YELLOW}--- Data Completeness Report ---${C_RESET}"
                Write-Host "The following steps had missing subjects:"
                
                foreach ($step in $completionInfo.PSObject.Properties) {
                    $info = $step.Value
                    if ($info.missing_count -gt 0) {
                        $statusColor = if ($info.completion_rate -ge 99) { $C_GREEN }
                                       elseif ($info.completion_rate -ge 95) { $C_YELLOW }
                                       else { $C_RED }
                        
                        Write-Host "  - $($info.step_name): $($info.completion_rate.ToString('F1'))% complete ($($info.missing_count) missing)" -ForegroundColor $statusColor
                        
                        if ($info.missing_report_path) {
                            $relativePath = $info.missing_report_path -replace [regex]::Escape($BaseDirectory), "." -replace "\\", "/"
                            Write-Host "    Details: $relativePath" -ForegroundColor $C_GRAY
                        }
                    }
                }
                
                Write-Host ""
                Write-Host "${C_YELLOW}To retry missing subjects for a specific step, run:${C_RESET}"
                Write-Host "  .\\prepare_data.ps1 -StopAfterStep <step_number>"
                Write-Host ""
                Write-Host "${C_CYAN}Step numbers:${C_RESET}"
                Write-Host "  5: Generate Eminence Scores"
                Write-Host "  6: Generate OCEAN Scores"
                Write-Host ""
            }
        }
        catch {
            Write-Host "${C_YELLOW}Warning: Could not read data completeness information.${C_RESET}"
        }
    }
}

function Show-DataGenerationParameters {
    param([string]$ConfigFilePath)
    
    Write-Host "`n${C_CYAN}Data Generation Configuration Parameters:${C_RESET}"
    Write-Host ("-" * 59)
    
    # Get the critical parameters from DataGeneration section
    $bypassSelection = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "bypass_candidate_selection" -DefaultValue "false"
    $eminenceModel = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "eminence_model" -DefaultValue "Not configured"
    $oceanModel = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "ocean_model" -DefaultValue "Not configured"
    $neutralizationModel = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "neutralization_model" -DefaultValue "Not configured"
    
    # Helper function to get display name for a model
    function Get-ModelDisplayName {
        param([string]$ModelName, [string]$ConfigFilePath)
        
        if ($ModelName -eq "Not configured" -or $ModelName -eq "") {
            return "Not configured"
        }
        
        # Convert the full OpenRouter ID to canonical format with dashes
        # Replace all non-alphanumeric characters (except dash) with dashes
        $canonicalName = $ModelName -replace '[^a-zA-Z0-9-]', '-'
        
        # Try to get the display name from ModelDisplayNames section
        $displayName = Get-ConfigValue -FilePath $ConfigFilePath -Section "ModelDisplayNames" -Key $canonicalName -DefaultValue $null
        
        if ($displayName) {
            return $displayName
        } else {
            # Try with just the model part (after the last slash)
            if ($ModelName -match '/') {
                $modelOnly = $ModelName.Split('/')[-1]
                $modelOnlyCanonical = $modelOnly -replace '[^a-zA-Z0-9-]', '-'
                $displayName = Get-ConfigValue -FilePath $ConfigFilePath -Section "ModelDisplayNames" -Key $modelOnlyCanonical -DefaultValue $null
                if ($displayName) {
                    return $displayName
                }
            }
            
            # If still no display name found, return a cleaned version of the original name
            # Just replace slashes with a space for better readability
            return $ModelName -replace '/', ' '
        }
    }
    
    # Get display names for the models
    $eminenceDisplayName = Get-ModelDisplayName -ModelName $eminenceModel -ConfigFilePath $ConfigFilePath
    $oceanDisplayName = Get-ModelDisplayName -ModelName $oceanModel -ConfigFilePath $ConfigFilePath
    $neutralizationDisplayName = Get-ModelDisplayName -ModelName $neutralizationModel -ConfigFilePath $ConfigFilePath
    
    # Display parameters with appropriate formatting (second column shifted by 2 spaces)
    Write-Host ("{0,-30}  {1}" -f "Bypass Candidate Selection:", "$($C_YELLOW)$bypassSelection$($C_RESET)")
    Write-Host ("{0,-30}  {1}" -f "Eminence Scoring Model:", "$($C_BLUE)$eminenceDisplayName$($C_RESET)")
    Write-Host ("{0,-30}  {1}" -f "OCEAN Scoring Model:", "$($C_BLUE)$oceanDisplayName$($C_RESET)")
    Write-Host ("{0,-30}  {1}" -f "Neutralization Model:", "$($C_BLUE)$neutralizationDisplayName$($C_RESET)")
    Write-Host ""
}

function Show-Parameters-And-Confirm {
    param(
        [string]$ConfigFilePath,
        [bool]$PauseForConfirmation = $true,
        [bool]$SuppressDisplay = $false
    )
    
    # Only display the parameters if not suppressed
    if (-not $SuppressDisplay) {
        # Display the parameters
        Show-DataGenerationParameters -ConfigFilePath $ConfigFilePath
    }
    
    # Pause for confirmation if required
    if ($PauseForConfirmation) {
        if ($env:UNDER_TEST_HARNESS -eq "true") {
            # Signal to test harness and wait for response
            $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
            if (-not $SuppressDisplay) {
                Write-Host "HARNESS_PROMPT:Review the configuration parameters above, then press Enter to continue...:$waitFile"
            } else {
                Write-Host "HARNESS_PROMPT:Press Enter to continue...:$waitFile"
            }
            # Wait for test harness to create the response file
            while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
            Remove-Item $waitFile -ErrorAction SilentlyContinue
        } else {
            # Standard Read-Host for normal operation
            if (-not $SuppressDisplay) {
                Read-Host -Prompt "${C_ORANGE}Review the configuration parameters above, then press Enter to continue...${C_RESET}" | Out-Null
            } else {
                Read-Host -Prompt "${C_ORANGE}Press Enter to continue...${C_RESET}" | Out-Null
            }
        }
    }
}

# --- Main Script Logic ---
$ProjectRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
$WorkingDirectory = $ProjectRoot
$SandboxMode = $false

# Check if we're running in a sandbox environment
if ($TestMode.IsPresent) {
    $SandboxMode = $true
    $WorkingDirectory = Get-Location # Layer 2 tests operate in a temp current dir
}
elseif ($env:PROJECT_SANDBOX_PATH -and (Test-Path $env:PROJECT_SANDBOX_PATH)) {
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
    $runCompletedSuccessfully = $false
    if (-not (Get-Command pdm -ErrorAction SilentlyContinue)) { throw "PDM not found. Please ensure PDM is installed and in your PATH." }

    # An "interactive force overwrite" is when a user, not a test script, forces a re-run.
    $isInteractiveForceOverwrite = $Force.IsPresent -and -not $TestMode.IsPresent

    # Display DataGeneration parameters for all modes (unless suppressed)
    if ($ReportOnly.IsPresent) {
        # In ReportOnly mode, show parameters first without pausing (unless suppressed)
        Show-Parameters-And-Confirm -ConfigFilePath $configFile -PauseForConfirmation $false -SuppressDisplay $SuppressConfigDisplay.IsPresent
        
        # Then show the pipeline status
        $anyFileExists = $false
        if (-not $SandboxMode) {
            $anyFileExists = Show-PipelineStatus -Steps $PipelineSteps -BaseDirectory $WorkingDirectory
        } else {
            # In sandbox mode, we just need to know if any files exist to potentially prompt the user.
            $anyFileExists = (Get-ChildItem -Path $WorkingDirectory -Recurse -File | Select-Object -First 1) -ne $null
        }
        
        Write-Host "${C_CYAN}Report-only mode enabled. Exiting.${C_RESET}"; return
    }
    
    # For Interactive and Normal modes, check if files exist without displaying the status table
    $anyFileExists = $false
    if (-not $SandboxMode) {
        # Check if any output files exist without showing the status table
        foreach ($step in $PipelineSteps) {
            $outputFile = Join-Path $WorkingDirectory $step.Output
            if ((Get-StepStatus -Step $step -BaseDirectory $WorkingDirectory) -eq "Complete") {
                $anyFileExists = $true
                break
            }
        }
    } else {
        # In sandbox mode, we just need to know if any files exist to potentially prompt the user.
        $anyFileExists = (Get-ChildItem -Path $WorkingDirectory -Recurse -File | Select-Object -First 1) -ne $null
    }

    # Show parameters for Interactive mode and Normal mode BEFORE any other operations
    # This ensures users see the configuration first, then the -Force warning, then backup
    # (unless suppressed for test modes)
    # In test modes with SuppressConfigDisplay, we also skip the pause to avoid halting automated tests
    Show-Parameters-And-Confirm -ConfigFilePath $configFile -PauseForConfirmation (-not $SuppressConfigDisplay.IsPresent) -SuppressDisplay $SuppressConfigDisplay.IsPresent
    
    # --- Pre-run Cleanup for an INTERACTIVE force flag ---
    # This is now moved after displaying the parameters
    if ($isInteractiveForceOverwrite) {
        Write-Host "`n${C_YELLOW}WARNING: The -Force flag is active."
        Write-Host "This will back up and delete all existing data artifacts to re-run the entire pipeline from scratch.${C_RESET}"
        $confirm = Read-Host "Are you sure you want to proceed? (Y/N)"
        if ($confirm.Trim().ToLower() -ne 'y') { throw "USER_CANCELLED: Operation cancelled by user." }

        Write-Host "`n${C_YELLOW}Backing up and removing existing data files...${C_RESET}`n"
        
        try {
            # Special handling for neutralization directory, which contains multiple files
            $neutralizationStep = $PipelineSteps | Where-Object { $_.Name -eq "Neutralize Delineations" }
            if ($neutralizationStep) {
                $repFile = Join-Path $WorkingDirectory $neutralizationStep.Output
                $outputDir = Split-Path $repFile -Parent
                Backup-And-Remove -ItemPath $outputDir
            }
            
            # Handle all other individual files from pipeline steps
            foreach ($step in $PipelineSteps) {
                if ($step.Name -ne "Neutralize Delineations") {
                    Backup-And-Remove -ItemPath (Join-Path $WorkingDirectory $step.Output)
                }
            }
            
            # Also backup summary files that will be overwritten
            $summaryFiles = @(
                "data/reports/eminence_scores_summary.txt",
                "data/reports/ocean_scores_summary.txt"
            )
            
            foreach ($summaryFile in $summaryFiles) {
                Backup-And-Remove -ItemPath (Join-Path $WorkingDirectory $summaryFile)
            }
            
            # Backup additional files that are not part of pipeline steps but should be removed
            $additionalFiles = @(
                "data/reports/adb_validation_summary.txt",
                "data/reports/delineation_coverage_map.csv",
                "data/reports/missing_eminence_scores.txt",
                "data/reports/missing_ocean_scores.txt",
                "data/reports/missing_sf_subjects.csv"
            )
            
            foreach ($additionalFile in $additionalFiles) {
                Backup-And-Remove -ItemPath (Join-Path $WorkingDirectory $additionalFile)
            }
            
            # Handle sf_chart_export files with any extension (safest approach)
            $sfChartExportPattern = Join-Path $WorkingDirectory "data/foundational_assets/sf_chart_export.*"
            $sfChartExportFiles = Get-ChildItem -Path $sfChartExportPattern -ErrorAction SilentlyContinue
            foreach ($file in $sfChartExportFiles) {
                Backup-And-Remove -ItemPath $file.FullName
            }
            
            # List of files to preserve (do not remove)
            $preserveFiles = @(
                "data/config/adb_research_categories.json",
                "data/foundational_assets/adb_category_map.csv",
                "data/foundational_assets/balance_thresholds.csv",
                "data/foundational_assets/country_codes.csv",
                "data/foundational_assets/point_weights.csv",
                "data/base_query.txt",
                "data/foundational_assets/assembly_logic/personalities_db.assembly_logic.txt",
                "data/foundational_assets/assembly_logic/subject_db.assembly_logic.csv",
                "data/reports/cutoff_parameter_analysis_results.csv",
                "data/reports/variance_curve_analysis.png"
            )
            
            Write-Host "${C_CYAN}Preserving the following essential files:${C_RESET}" -ForegroundColor Cyan
            foreach ($preserveFile in $preserveFiles) {
                $preservePath = Join-Path $WorkingDirectory $preserveFile
                if (Test-Path $preservePath) {
                    $relativePath = $preserveFile.Replace("\", "/")
                    Write-Host "  Preserving: $relativePath" -ForegroundColor Green
                }
            }
            
            Write-Host "" # Add a blank line for spacing
        }
        catch [System.Management.Automation.PipelineStoppedException] {
            # Handle Ctrl+C interrupt during backup operation
            Write-Host "`n${C_YELLOW}WARNING: Backup operation was interrupted by user.${C_RESET}"
            Write-Host "${C_YELLOW}Some files may have been backed up while others were not.${C_RESET}"
            Write-Host "${C_YELLOW}Please check the data/backup directory and manually remove any remaining files if needed.${C_RESET}"
            throw "USER_CANCELLED: Backup operation interrupted by user."
        }
        catch {
            # Handle other errors during backup
            Write-Host "`n${C_RED}ERROR: Backup operation failed.${C_RESET}"
            Write-Host "${C_RED}Reason: $($_.Exception.Message)${C_RESET}"
            throw "BACKUP_FAILED: Backup operation failed. $($_.Exception.Message)"
        }
    }
    
    if ($anyFileExists -and -not $Force.IsPresent -and -not $Interactive -and -not $SandboxMode) {
        Write-Host "${C_YELLOW}`nWARNING: One or more data files already exist."
        Write-Host "The pipeline will resume from the first incomplete step."
        $confirm = Read-Host "Do you wish to proceed? (Y/N)"
        if ($confirm.Trim().ToLower() -ne 'y') { throw "USER_CANCELLED: Operation cancelled by user." }
    }

    # Determine the first step of each stage for clean banner logging
    $firstStepNamesOfStages = ($PipelineSteps | Group-Object Stage | ForEach-Object { $_.Group[0].Name }) -as [string[]]

    # Track whether we've shown the overwrite instruction
    $overwriteInstructionShown = $false

    $totalSteps = $PipelineSteps.Count; $stepCounter = 0
    foreach ($step in $PipelineSteps) {
        $stepCounter++
        $outputFile = Join-Path $WorkingDirectory $step.Output
        
        # --- Determine if the step should be skipped ---
        $isSkipped = $false
        if ($bypassScoring -and ($step.Name -in "Generate Eminence Scores", "Generate OCEAN Scores")) {
            if (-not $Resumed.IsPresent) {
                # Print the detailed step header for bypassed steps in Interactive mode
                if ($Interactive) {
                    $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
                    Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
                    Write-Host "$C_BLUE$stepHeader$C_RESET"
                    Write-Host "$C_BLUE$($step.Description)$C_RESET"
                    Write-Host "`n${C_YELLOW}Bypass mode is active. Skipping step.${C_RESET}"
                    
                    # Show inputs and output information
                    $infoBlock = New-Object System.Text.StringBuilder
                    [void]$infoBlock.AppendLine("`n${C_RESET}  INPUTS:")
                    $Step.Inputs | ForEach-Object { [void]$infoBlock.AppendLine("    - $_") }
                    [void]$infoBlock.AppendLine("`n  OUTPUT:")
                    [void]$infoBlock.Append("    - $($Step.Output)")
                    [void]$infoBlock.AppendLine("`n${C_YELLOW}NOTE: This step will be skipped because bypass_candidate_selection is enabled in config.ini.${C_RESET}")
                    
                    # Piping to Out-Host forces the multi-line info block to flush immediately
                    $infoBlock.ToString() | Out-Host
                    
                    # Handle interactive prompt
                    if ($env:UNDER_TEST_HARNESS -eq "true") {
                        # Signal to test harness and wait for response
                        $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
                        Write-Host "HARNESS_PROMPT:Step will be skipped due to bypass mode. Press Enter to continue...:$waitFile"
                        # Wait for test harness to create the response file
                        while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
                        Remove-Item $waitFile -ErrorAction SilentlyContinue
                    } else {
                        # Standard Read-Host for normal operation
                        Read-Host -Prompt "${C_ORANGE}Step will be skipped due to bypass mode. Press Enter to continue...${C_RESET}" | Out-Null
                    }
                } else {
                    # Non-interactive mode just shows a simple message
                    $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
                    Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
                    Write-Host "$C_BLUE$stepHeader$C_RESET"
                    Write-Host "$C_BLUE$($step.Description)$C_RESET"
                    Write-Host "`n${C_YELLOW}Bypass mode is active. Skipping step.${C_RESET}"
                }
            }
            $isSkipped = $true
        }

        # Skip if the step is complete AND we are not in force-overwrite mode.
        if ((Get-StepStatus -Step $step -BaseDirectory $WorkingDirectory) -eq "Complete" -and -not $isInteractiveForceOverwrite) {
            if (-not $Resumed.IsPresent) {
                # Print the detailed step header even for skipped steps in Interactive mode
                if ($Interactive) {
                    $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
                    Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
                    Write-Host "$C_BLUE$stepHeader$C_RESET"
                    Write-Host "$C_BLUE$($step.Description)$C_RESET"
                    
                    # Show inputs and output information
                    $infoBlock = New-Object System.Text.StringBuilder
                    [void]$infoBlock.AppendLine("`n${C_RESET}  INPUTS:")
                    $Step.Inputs | ForEach-Object { [void]$infoBlock.AppendLine("    - $_") }
                    [void]$infoBlock.AppendLine("`n  OUTPUT:")
                    [void]$infoBlock.Append("    - $($Step.Output)")
                    [void]$infoBlock.AppendLine("")
                    [void]$infoBlock.AppendLine("")
                    [void]$infoBlock.AppendLine("${C_YELLOW}NOTE: This step will be skipped because the output file already exists.${C_RESET}")
                    if (-not $overwriteInstructionShown) {
                        [void]$infoBlock.AppendLine("If you wish to overwrite existing files, abort this run with Ctrl+C and execute the script with an added '-Force' parameter. For example: 'pdm run prep-data -Interactive -Force'.")
                        $overwriteInstructionShown = $true
                    }
                    
                    # Piping to Out-Host forces the multi-line info block to flush immediately
                    $infoBlock.ToString() | Out-Host
                    
                    # Handle interactive prompt
                    if ($env:UNDER_TEST_HARNESS -eq "true") {
                        # Signal to test harness and wait for response
                        $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
                        Write-Host "HARNESS_PROMPT:Step will be skipped. Press Enter to continue...:$waitFile"
                        # Wait for test harness to create the response file
                        while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
                        Remove-Item $waitFile -ErrorAction SilentlyContinue
                    } else {
                        # Standard Read-Host for normal operation
                        Read-Host -Prompt "${C_ORANGE}Step will be skipped. Press Enter to continue...${C_RESET}" | Out-Null
                    }
                } else {
                    Write-Host "Output exists for step '$($step.Name)'. Skipping." -ForegroundColor Yellow
                }
            }
            $isSkipped = $true
        }
        if ($isSkipped) { continue }
        
        # --- If we reach here, the step will be executed. ---
        # Print the stage banner only if this is the very first step of the stage.
        if ($step.Name -in $firstStepNamesOfStages) {
            Format-Banner "BEGIN STAGE: $($step.Stage.ToUpper())" $C_CYAN
        }
        
        # Print the detailed step header.
        $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
        Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
        Write-Host "$C_BLUE$stepHeader$C_RESET"
        
        $description = $step.Description
        if ($TestMode.IsPresent -and $step.Type -eq 'Manual') {
            if ($step.Name -eq "Astrology Data Export (Manual)") {
                $description = "Simulating the manual Solar Fire import, calculation, and chart export process."
            } elseif ($step.Name -eq "Delineation Library Export (Manual)") {
                $description = "Simulating the one-time Solar Fire delineation library export."
            }
        }
        Write-Host "$C_BLUE$description$C_RESET"
        
        # For manual steps, halt the pipeline. The behavior differs for tests vs. users.
        if ($step.Type -eq 'Manual') {
            if ($TestMode.IsPresent) {
                # In test mode, set the exit code and break the loop.
                # The 'finally' block will handle the actual exit.
                $exitCode = 1
                break
            } else {
                # For an interactive user, throw an error to display the guided 'HALTED' message.
                throw $step.Description
            }
        }

        if ($Interactive) {
            # In interactive mode, use the [Console] class to write directly to the console.
            # This bypasses PowerShell's output streams and solves complex buffering issues when scripts are nested.
            $infoBlock = New-Object System.Text.StringBuilder

            if ($step.Script) {
                $summary = Get-ScriptDocstringSummary -ScriptPath (Join-Path $ProjectRoot $step.Script)
                if ($summary) {
                    [void]$infoBlock.AppendLine("`n${C_BLUE}Script Summary: $summary${C_RESET}")
                }
            }

            if ($SandboxMode) {
                $normalizedPath = $WorkingDirectory.ToString().Replace('\', '/')
                [void]$infoBlock.AppendLine("`n${C_GRAY}  BASE DIRECTORY: $normalizedPath${C_RESET}")
            }
            # Add an explicit color reset to ensure INPUTS/OUTPUT block uses the default terminal color.
            [void]$infoBlock.Append($C_RESET)
            [void]$infoBlock.AppendLine("`n  INPUTS:")
            $Step.Inputs | ForEach-Object { [void]$infoBlock.AppendLine("    - $_") }
            [void]$infoBlock.AppendLine("`n  OUTPUT:")
            [void]$infoBlock.Append("    - $($Step.Output)")

            if (-not $TestMode.IsPresent) {
                if ($Step.Name -eq "Fetch Raw ADB Data") {
                    [void]$infoBlock.AppendLine("`n${C_YELLOW}WARNING: This process quickly downloads a large amount of data from the Astro-Databank website.${C_RESET}")
                } elseif ($Step.Name -eq "Generate Eminence Scores") {
                    [void]$infoBlock.AppendLine("`n${C_YELLOW}WARNING: This process will make LLM calls that will incur API transaction costs and could take some time (2 minutes or more for each set of 1,000 records).${C_RESET}")
                } elseif ($Step.Name -eq "Generate OCEAN Scores") {
                    [void]$infoBlock.AppendLine("`n${C_YELLOW}WARNING: This process will make LLM calls that will incur API transaction costs and could take some time (15 minutes or more for each set of 1,000 records).${C_RESET}")
                }
            }

            # Piping to Out-Host forces the multi-line info block to flush immediately,
            # solving console buffering issues in nested script calls.
            $infoBlock.ToString() | Out-Host

            # Handle interactive prompt differently when running under test harness
            if ($env:UNDER_TEST_HARNESS -eq "true") {
                # Signal to test harness and wait for response
                $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
                Write-Host "HARNESS_PROMPT:Press Enter to execute this step (Ctrl+C to exit)...:$waitFile"
                # Wait for test harness to create the response file
                while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
                Remove-Item $waitFile -ErrorAction SilentlyContinue
            } else {
                # Standard Read-Host for normal operation
                Read-Host -Prompt "${C_ORANGE}Press Enter to execute this step (Ctrl+C to exit)...${C_RESET}" | Out-Null
            }
        } else {
            # Non-interactive mode just needs the basic info.
            Write-Host "`n  INPUTS:"; $Step.Inputs | ForEach-Object { Write-Host "    - $_" }; Write-Host "`n  OUTPUT:"; Write-Host "    - $($Step.Output)"
        }

        $scriptPath = Join-Path $ProjectRoot $step.Script
        # Use python -u for unbuffered output to see progress bars in real-time
        $arguments = "run", "python", "-u", $scriptPath
        if ($Force.IsPresent) {
            $arguments += "--force"
        }
        # Pass the --plot flag ONLY to the script that uses it.
        if ($step.Name -eq "Select Final Candidates" -and $Plot.IsPresent) {
            $arguments += "--plot"
        }

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
        }
        
        # Suppress redundant warnings from Python scripts in ALL modes
        if ($step.Name -eq "Fetch Raw ADB Data") {
            $arguments += "--no-network-warning"
        }
        if ($step.Name -in "Generate Eminence Scores", "Generate OCEAN Scores") {
            $arguments += "--no-api-warning"
        }

        # For the final step, explicitly pass the correct output path in all modes
        if ($step.Name -eq "Generate Personalities DB") {
            $arguments += "-o", $outputFile
        }

        # Execute the python script within the correct working directory
        # Use Invoke-Expression to preserve progress bar output
        $originalLocation = Get-Location
        try {
            Set-Location $WorkingDirectory
            
            # Build command string and execute directly to preserve carriage returns
            $commandString = "pdm " + ($arguments -join " ")
            Invoke-Expression $commandString
            $exitCode = $LASTEXITCODE
        }
        finally {
            Set-Location $originalLocation
        }
        
        if ($exitCode -ne 0) { 
            Write-Host "Script failed with exit code $exitCode" -ForegroundColor Red
            throw "Script '$($step.Script)' failed with exit code $exitCode. Halting pipeline." 
        }
        if ($Interactive) { 
            Write-Host ""   # This line cannot be removed without breaking the flow!
            if ($env:UNDER_TEST_HARNESS -eq "true") {
                $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
                Write-Host "HARNESS_PROMPT:Step complete. Inspect the output, then press Enter to continue...:$waitFile"
                # Wait for test harness to create the response file
                while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
                Remove-Item $waitFile -ErrorAction SilentlyContinue
            } else {
                Read-Host -Prompt "${C_ORANGE}Step complete. Inspect the output, then press Enter to continue...${C_RESET}"
            }
        }
        
        # If a stop point is specified by the harness, halt with the special exit code.
        if ($StopAfterStep -gt 0 -and $stepCounter -eq $StopAfterStep) {
            Write-Host "`n${C_MAGENTA}HARNESS DIRECTIVE: Halting after Step $stepCounter as requested.${C_RESET}"
            $exitCode = 1
            break
        }
    }
    
    # The run is only successful if the loop finishes and the exit code is still 0.
    if ($exitCode -eq 0) {
        $runCompletedSuccessfully = $true
    }
}
catch [System.Management.Automation.PipelineStoppedException] {
    # Handle Ctrl+C interrupt
    $exitCode = 0
    
    if (-not $SilentHalt.IsPresent) {
        Format-Banner "PIPELINE HALTED" $C_ORANGE
        Write-Host "${C_ORANGE}REASON: Operation cancelled by user (Ctrl+C)${C_RESET}"
        Write-Host ""
    }
}
catch {
    $errorMessage = ""
    if ($_ -is [System.Management.Automation.ErrorRecord]) {
        $errorMessage = $_.Exception.Message
    } else {
        $errorMessage = $_
    }

    $isCancellation = $errorMessage -match "USER_CANCELLED"
    $isManualPause = $errorMessage -match "The pipeline is paused"

    if ($isCancellation) {
        $exitCode = 0
    } else {
        $exitCode = 1
    }

    if (-not $SilentHalt.IsPresent) {
        # A user cancellation or a planned manual pause are warnings (orange), not errors (red).
        $bannerColor = if ($isCancellation -or $isManualPause) { $C_ORANGE } else { $C_RED }
        $messageColor = $bannerColor

        # For cancellations, clean up the message for a more user-friendly display.
        if ($isCancellation) {
            $errorMessage = $errorMessage -replace "USER_CANCELLED: ", ""
        }

        Format-Banner "PIPELINE HALTED" $bannerColor
        Write-Host "${messageColor}REASON: $errorMessage${C_RESET}"
        Write-Host ""

        if ($isManualPause) {
            Write-Host "`n${C_YELLOW}NEXT STEPS:${C_RESET}"
            Write-Host "1. Complete the manual step described in the message above."
            Write-Host "2. Once the required output file is in place, re-run this script."
            Write-Host "   The pipeline will automatically resume from where it stopped."
            Write-Host ""
        }
    }
}
finally {
    # Only show the "Completed" banner and final status report if the entire pipeline finished successfully.
    if ($runCompletedSuccessfully) {
        Format-Banner "Data Preparation Pipeline Completed Successfully" $C_GREEN
        if (-not $NoFinalReport.IsPresent) {
            Write-Host "`n${C_YELLOW}--- Final Pipeline Status ---${C_RESET}"; Show-PipelineStatus -Steps $PipelineSteps -BaseDirectory $WorkingDirectory | Out-Null
            
            # Add data completeness report
            Show-DataCompletenessReport -BaseDirectory $WorkingDirectory
        }
    }
    exit $exitCode
}

# === End of prepare_data.ps1 ===
