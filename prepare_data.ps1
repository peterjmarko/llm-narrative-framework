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

.PARAMETER StopAfterStep
    If specified, the script will stop after completing the specified step number.
    WARNING: This parameter is intended for testing purposes only. Using it in
    production may result in inconsistent data, as downstream steps that depend
    on the executed steps will not be run.

.PARAMETER StartWithStep
    If specified, the script will start execution from the specified step number.
    When a step executes, all downstream steps will automatically be forced to
    re-run to maintain data consistency.

.EXAMPLE
    # Run the full pipeline, resuming from the first incomplete step.
    .\prepare_data.ps1

.EXAMPLE
    # Run the pipeline in interactive "guided tour" mode.
    .\prepare_data.ps1 -Interactive

.EXAMPLE
    # Get a read-only status report of the data pipeline.
    .\prepare_data.ps1 -ReportOnly

.EXAMPLE
    # Start the pipeline from a specific step.
    .\prepare_data.ps1 -StartWithStep 5

.EXAMPLE
    # Run only a specific step and then stop.
    .\prepare_data.ps1 -StartWithStep 5 -StopAfterStep 5
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
    [int]$StopAfterStep = 0,

    [Parameter(Mandatory=$false)]
    [int]$StartWithStep = 0,

    [Parameter(Mandatory=$false)]
    [switch]$RestoreBackup,
    
    [Parameter(Mandatory=$false)]
    [string]$RestoreFromPath
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
    @{ Stage="2. Candidate Qualification"; Name="Validate Wikipedia Pages";   Script="src/validate_wikipedia_pages.py";   Inputs=@("data/processed/adb_wiki_links.csv");      Output="data/processed/adb_validated_subjects.csv";           Type="Automated"; Description="Validates each Wikipedia page for content, language, and redirects." },
    @{ Stage="2. Candidate Qualification"; Name="Select Eligible Candidates"; Script="src/select_eligible_candidates.py"; Inputs=@("data/sources/adb_raw_export.txt", "data/processed/adb_validated_subjects.csv"); Output="data/intermediate/adb_eligible_candidates.txt";      Type="Automated"; Description="Applies deterministic data quality filters to create a pool of eligible candidates." },
    @{ Stage="3. Candidate Selection";   Name="Generate Eminence Scores";   Script="src/generate_eminence_scores.py";   Inputs=@("data/intermediate/adb_eligible_candidates.txt"); Output="data/foundational_assets/eminence_scores.csv";   Type="Automated"; Description="Generates a calibrated eminence score for each eligible candidate using an LLM." },
    @{ Stage="3. Candidate Selection";   Name="Generate OCEAN Scores";      Script="src/generate_ocean_scores.py";      Inputs=@("data/foundational_assets/eminence_scores.csv"); Output="data/foundational_assets/ocean_scores.csv";        Type="Automated"; Description="Generates OCEAN personality scores for each eligible candidate using an LLM." },
    @{ Stage="3. Candidate Selection";   Name="Analyze Cutoff Parameters";  Script="src/analyze_cutoff_parameters.py"; Inputs=@("data/foundational_assets/ocean_scores.csv"); Output="data/foundational_assets/cutoff_parameter_analysis_results.csv"; Type="Automated"; Description="Performs grid search analysis to find optimal cutoff parameters for final candidate selection." },
    @{ Stage="3. Candidate Selection";   Name="Select Final Candidates";    Script="src/select_final_candidates.py";    Inputs=@("data/intermediate/adb_eligible_candidates.txt", "data/foundational_assets/eminence_scores.csv", "data/foundational_assets/ocean_scores.csv"); Output="data/intermediate/adb_final_candidates.txt";        Type="Automated"; Description="Determines the final subject set based on the LLM scoring." },
    @{ Stage="4. Profile Generation";    Name="Prepare Solar Fire Import File";     Script="src/prepare_sf_import.py";          Inputs=@("data/intermediate/adb_final_candidates.txt"); Output="data/intermediate/sf_data_import.txt";            Type="Automated"; Description="Formats the final subject list for import into the Solar Fire software." },
    @{ Stage="4. Profile Generation";    Name="Delineations Library Export (Manual)";    Inputs=@("Solar Fire Software"); Output="data/foundational_assets/sf_delineations_library.txt"; Type="Manual"; Description="The pipeline is paused. Please perform the one-time Solar Fire delineation library export." },
    @{ Stage="4. Profile Generation";    Name="Astrology Data Export (Manual)"; Inputs=@("data/intermediate/sf_data_import.txt"); Output="data/foundational_assets/sf_chart_export.csv"; Type="Manual"; Description="The pipeline is paused. Please perform the manual Solar Fire import, calculation, and chart export process." },
    @{ Stage="4. Profile Generation";    Name="Neutralize Delineations";    Script="src/neutralize_delineations.py";    Inputs=@("data/foundational_assets/sf_delineations_library.txt"); Output="data/foundational_assets/neutralized_delineations/ (6 files)"; Type="Automated"; Description="Rewrites esoteric texts into neutral psychological descriptions using an LLM." },
    @{ Stage="4. Profile Generation";    Name="Create Subject Database";    Script="src/create_subject_db.py";          Inputs=@("data/foundational_assets/sf_chart_export.csv", "data/intermediate/adb_final_candidates.txt"); Output="data/processed/subject_db.csv";                  Type="Automated"; Description="Integrates chart data with the final subject list to create a master database." },
    @{ Stage="4. Profile Generation";    Name="Generate Personalities Database";  Script="src/generate_personalities_db.py";  Inputs=@("data/processed/subject_db.csv", "data/foundational_assets/neutralized_delineations/"); Output="data/personalities_db.txt";            Type="Automated"; Description="Assembles the final personalities database from subject data and the neutralized text library." }
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
    param([hashtable]$Step, [string]$BaseDirectory, [string]$ConfigFilePath)
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
        "Astrology Data Export (Manual)" {
            # Special case: Check for the file in the Solar Fire export directory using config parameters
            # This is a manual step, but the create_subject_db.py script will fetch the file
            $documentsFolder = [System.Environment]::GetFolderPath('Personal')
            $userFilesBase = Get-ConfigValue -FilePath $ConfigFilePath -Section "SolarFire" -Key "user_files_base" -DefaultValue "Solar Fire User Files"
            $chartExportSubdir = Get-ConfigValue -FilePath $ConfigFilePath -Section "SolarFire" -Key "chart_export_subdir" -DefaultValue "Export"
            $chartExportFilename = Get-ConfigValue -FilePath $ConfigFilePath -Section "SolarFire" -Key "chart_export_filename" -DefaultValue "sf_chart_export.csv"
            
            # Check if userFilesBase already includes the Documents folder
            if ($userFilesBase.StartsWith("Documents\", [StringComparison]::OrdinalIgnoreCase)) {
                # Remove "Documents\" prefix since we're already joining with the Documents folder
                $userFilesBase = $userFilesBase.Substring(9)
            }
            
            $sfExportPath = Join-Path $documentsFolder (Join-Path $userFilesBase (Join-Path $chartExportSubdir $chartExportFilename))
            $projectFile = Join-Path $BaseDirectory $Step.Output
            
            if (Test-Path $sfExportPath) {
                # File exists in Solar Fire directory, copy it to project directory if not already there
                if (-not (Test-Path $projectFile)) {
                    # Ensure the target directory exists
                    $targetDir = Split-Path $projectFile -Parent
                    if (-not (Test-Path $targetDir)) {
                        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
                    }
                    Copy-Item -Path $sfExportPath -Destination $projectFile -Force
                }
                return "Complete"
            } else {
                # File doesn't exist anywhere
                return "Pending"
            }
        }
        "Delineations Library Export (Manual)" {
            # Special case: Check for the file in the Solar Fire Export directory
            # Users export Standard.def from Interpretations, then copy and rename it to sf_delineations_library.txt in Export
            $documentsFolder = [System.Environment]::GetFolderPath('Personal')
            $userFilesBase = Get-ConfigValue -FilePath $ConfigFilePath -Section "SolarFire" -Key "user_files_base" -DefaultValue "Solar Fire User Files"
            $exportSubdir = Get-ConfigValue -FilePath $ConfigFilePath -Section "SolarFire" -Key "delin_lib_subdir" -DefaultValue "Export"
            $delinLibFilename = Get-ConfigValue -FilePath $ConfigFilePath -Section "SolarFire" -Key "delin_lib_filename" -DefaultValue "sf_delineations_library.txt"
            
            # Check if userFilesBase already includes the Documents folder
            if ($userFilesBase.StartsWith("Documents\", [StringComparison]::OrdinalIgnoreCase)) {
                # Remove "Documents\" prefix since we're already joining with the Documents folder
                $userFilesBase = $userFilesBase.Substring(9)
            }
            
            $sfExportPath = Join-Path $documentsFolder (Join-Path $userFilesBase (Join-Path $exportSubdir $delinLibFilename))
            $projectFile = Join-Path $BaseDirectory $Step.Output
            
            if ((Test-Path $sfExportPath)) {
                # File exists in Solar Fire Export directory, copy it to project directory if not already there
                if (-not (Test-Path $projectFile)) {
                    # Ensure the target directory exists
                    $targetDir = Split-Path $projectFile -Parent
                    if (-not (Test-Path $targetDir)) {
                        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
                    }
                    Copy-Item -Path $sfExportPath -Destination $projectFile -Force
                }
                return "Complete"
            } else {
                # File doesn't exist anywhere
                return "Pending"
            }
        }
        "Neutralize Delineations" {
            # TEMPORARY DEBUG - Remove after testing
            $sourceFile = Join-Path $BaseDirectory "data/foundational_assets/sf_delineations_library.txt"
            if (Test-Path $sourceFile) {
                $sourceLMTS = (Get-Item $sourceFile).LastWriteTime
            }
            # This step's "Output" is one of its files, but it represents the whole directory.
            $delineationDir = Split-Path (Join-Path $BaseDirectory $Step.Output) -Parent
            $sourceFile = Join-Path $BaseDirectory "data/foundational_assets/sf_delineations_library.txt"
            
            # Get current LLM from config
            $currentLLM = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "neutralization_model" -DefaultValue ""
            
            # Define expected files and their line count requirements
            $expectedFiles = @{
                "balances_elements.csv" = 8
                "balances_hemispheres.csv" = 4
                "balances_modes.csv" = 6
                "balances_quadrants.csv" = 4
                "balances_signs.csv" = 12
                "points_in_signs.csv" = 144
            }
            
            # Check if source file exists
            if (-not (Test-Path $sourceFile)) {
                return "Missing"
            }
            
            # Check if output directory exists
            if (-not (Test-Path $delineationDir)) {
                return "Missing"
            }
            
            # Get last modified timestamps
            $sourceLMTS = (Get-Item $sourceFile).LastWriteTime
            
            # Check if any output files exist
            $outputFilesExist = $false
            $earliestOutputLMTS = $null
            foreach ($file in $expectedFiles.Keys) {
                $filePath = Join-Path $delineationDir $file
                if (Test-Path $filePath) {
                    $outputFilesExist = $true
                    $fileLMTS = (Get-Item $filePath).LastWriteTime
                    if ($null -eq $earliestOutputLMTS -or $fileLMTS -lt $earliestOutputLMTS) {
                        $earliestOutputLMTS = $fileLMTS
                    }
                }
            }
            
            # If no output files exist, return Missing
            if (-not $outputFilesExist) {
                return "Missing"
            }
            
            # Check if we need to re-process the entire step
            # Rule 3: Re-process if source is newer than output OR LLM has changed
            $lastLLM = ""
            $completionInfoPath = Join-Path $BaseDirectory "data/reports/pipeline_completion_info.json"
            if (Test-Path $completionInfoPath) {
                try {
                    $completionInfo = Get-Content $completionInfoPath | ConvertFrom-Json
                    if ($completionInfo.PSObject.Properties.Name -contains "neutralize_delineations") {
                        $lastLLM = $completionInfo.neutralize_delineations.llm_used
                    }
                } catch {
                    # If we can't read the completion info, assume LLM has changed
                    $lastLLM = ""
                }
            }
            
            if ($sourceLMTS -gt $earliestOutputLMTS -or $currentLLM -ne $lastLLM) {
                # Source is newer or LLM changed, need to re-process
                return "Stale"  # This will trigger a full re-run
            }
            
            # Rule 4: Check if all files are complete
            $allFilesComplete = $true
            $incompleteFiles = @()
            
            foreach ($file in $expectedFiles.Keys) {
                $filePath = Join-Path $delineationDir $file
                if (Test-Path $filePath) {
                    # Check line count
                    $lineCount = (Get-Content $filePath | Where-Object { $_.Trim() -ne "" }).Count
                    if ($lineCount -lt $expectedFiles[$file]) {
                        $allFilesComplete = $false
                        $incompleteFiles += $file
                    }
                } else {
                    $allFilesComplete = $false
                    $incompleteFiles += $file
                }
            }
            
            if ($allFilesComplete) {
                # Rule 5: All files complete, skip
                return "Complete"
            } else {
                # Rule 4: Some files incomplete, return Partial
                return "Partial"
            }
        }

        "Analyze Cutoff Parameters" {
            # Check if output file exists
            if (-not (Test-Path $outputFile)) {
                return "Missing"
            }
            
            # Read current parameters from config
            $currentStartPoint = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "cutoff_search_start_point" -DefaultValue "0"
            $currentSmoothingWindow = Get-ConfigValue -FilePath $ConfigFilePath -Section "DataGeneration" -Key "smoothing_window_size" -DefaultValue "0"
            
            # Read the optimal parameters from the analysis CSV
            try {
                $csvContent = Import-Csv $outputFile
                if ($csvContent.Count -gt 0) {
                    $optimalStartPoint = $csvContent[0].'Start Point'
                    $optimalSmoothingWindow = $csvContent[0].'Smoothing Window'
                    
                    # If current config doesn't match the optimal parameters from the analysis, mark as stale
                    if ($currentStartPoint -ne $optimalStartPoint -or $currentSmoothingWindow -ne $optimalSmoothingWindow) {
                        return "Stale"
                    }
                }
            } catch {
                # If we can't read the CSV, treat it as incomplete
                return "Incomplete"
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

# Find and replace this function in prepare_data.ps1

function Restore-Recent-Backup {
    <#
    .SYNOPSIS
    Restores the most recent backup files to their original locations.
    #>
    param(
        [string]$BackupTimestamp = $null,
        [string]$BaseDir = $ProjectRoot
    )
    
    $baseDir = $BaseDir
    $backupDir = Join-Path $baseDir "data/backup"
    
    if (-not (Test-Path $backupDir)) {
        Write-Host "No backup directory found at '$backupDir'" -ForegroundColor Yellow
        return
    }
    
    # If no timestamp provided, find the most recent one
    if (-not $BackupTimestamp) {
        $allBackups = Get-ChildItem -Path $backupDir -File
        if ($allBackups.Count -eq 0) {
            Write-Host "No backup files found in '$backupDir'" -ForegroundColor Yellow
            return
        }
        
        # Extract timestamps from filenames (format: YYYYMMDD_HHMMSS)
        # Wrap in @() to ensure the result is always an array
        $timestamps = @($allBackups | ForEach-Object {
            if ($_.Name -match '\.(\d{8}_\d{6})\.') {
                $matches[1]
            }
        } | Select-Object -Unique | Sort-Object -Descending)
        
        if ($timestamps.Count -eq 0) {
            Write-Host "Could not find any timestamped backup files" -ForegroundColor Yellow
            return
        }
        
        $BackupTimestamp = $timestamps[0]
    }
    
    Write-Host "`nRestoring backups from timestamp: $BackupTimestamp" -ForegroundColor Cyan
    
    # Find all files with this timestamp
    $backupFiles = Get-ChildItem -Path $backupDir -File | Where-Object { $_.Name -match [regex]::Escape($BackupTimestamp) }
    
    if ($backupFiles.Count -eq 0) {
        Write-Host "No backup files found with timestamp '$BackupTimestamp'" -ForegroundColor Yellow
        return
    }
    
    $restoredCount = 0
    foreach ($backupFile in $backupFiles) {
        # Parse the original path from the backup filename
        # Format: basename.YYYYMMDD_HHMMSS.extension.bak
        $originalName = $backupFile.Name -replace "\.$BackupTimestamp", "" -replace "\.bak$", ""
        
        # Determine original location based on file type
        $originalPath = $null
        # Use a wildcard to match both 'adb_raw_export.txt' and 'test_adb_raw_export.txt'
        if ($originalName -like "*adb_raw_export.*") {
            $originalPath = Join-Path $baseDir "data/sources/$originalName"
        }
        elseif ($originalName -like "adb_wiki_links.*" -or $originalName -like "adb_validation_report.*" -or $originalName -like "subject_db.*") {
            $originalPath = Join-Path $baseDir "data/processed/$originalName"
        }
        elseif ($originalName -like "adb_eligible_candidates.*" -or $originalName -like "adb_final_candidates.*" -or $originalName -like "sf_data_import.*") {
            $originalPath = Join-Path $baseDir "data/intermediate/$originalName"
        }
        elseif ($originalName -like "eminence_scores.*" -or $originalName -like "ocean_scores.*" -or $originalName -like "sf_*") {
            $originalPath = Join-Path $baseDir "data/foundational_assets/$originalName"
        }
        elseif ($originalName -like "*_summary.*" -or $originalName -like "missing_*") {
            $originalPath = Join-Path $baseDir "data/reports/$originalName"
        }
        elseif ($originalName -like "personalities_db.*") {
            $originalPath = Join-Path $baseDir "data/$originalName"
        }
        
        if ($originalPath) {
            # Ensure parent directory exists
            $parentDir = Split-Path -Parent $originalPath
            if (-not (Test-Path $parentDir)) {
                New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
            }
            
            # Check if a file already exists at the destination
            if (Test-Path $originalPath) {
                Write-Host "  Skipping: $originalName (file already exists at destination)" -ForegroundColor Yellow
            }
            else {
                Copy-Item -Path $backupFile.FullName -Destination $originalPath
                Write-Host "  Restored: $originalName" -ForegroundColor Green
                $restoredCount++
            }
        }
        else {
            Write-Host "  Warning: Could not determine original location for '$originalName'" -ForegroundColor Yellow
        }
    }
    
    Write-Host "`nRestored $restoredCount file(s) from backup timestamp $BackupTimestamp" -ForegroundColor Green
}

function Show-PipelineStatus {
    param([array]$Steps, [string]$BaseDirectory = ".")
    Format-Banner "Data Preparation Pipeline Status" $C_CYAN
    $nameWidth = 45; $statusWidth = 13; $fileWidth = 60
    Write-Host ("{0,-$nameWidth} {1,-$statusWidth} {2}" -f "Step", "Status", "Output File");
    Write-Host ("-" * $nameWidth + " " + "-" * $statusWidth + " " + "-" * $fileWidth)
    $filesExist = $false
    $stepNumber = 0
    foreach ($step in $Steps) {
        $stepNumber++
        $configFile = Join-Path $BaseDirectory "config.ini"
        $stepStatus = Get-StepStatus -Step $step -BaseDirectory $BaseDirectory -ConfigFilePath $configFile
        
        switch ($stepStatus) {
            "Complete"   { $status = "$($C_GREEN)[COMPLETE]   $($C_RESET)"; $filesExist = $true }
            "Incomplete" { $status = "$($C_YELLOW)[INCOMPLETE]$($C_RESET)"; $filesExist = $true }
            "Partial"    { $status = "$($C_ORANGE)[PARTIAL]    $($C_RESET)"; $filesExist = $true }
            "Pending"    { $status = "$($C_YELLOW)[PENDING]    $($C_RESET)"; $filesExist = $true }
            "Stale"      { $status = "$($C_ORANGE)[STALE]      $($C_RESET)"; $filesExist = $true }
            "Missing"    { $status = "$($C_RED)[MISSING]    $($C_RESET)"; $filesExist = $false }
            default      { $status = if ($step.Type -eq 'Manual') { "$($C_RED)[MISSING]    $($C_RESET)" } else { "$($C_RED)[MISSING]    $($C_RESET)" } }
        }
        $stepNameFormatted = "$($stepNumber). $($step.Name)"
        
        # Special handling for step 11 (Neutralize Delineations) to show directory name with file count
        if ($step.Name -eq "Neutralize Delineations") {
            $outputFile = "data/foundational_assets/neutralized_delineations/ (6 files)"
        } else {
            # Show the full relative path from the output
            $outputFile = $step.Output
        }
        
        if ($outputFile.Length -gt $fileWidth) {
            $outputFile = $outputFile.Substring(0, $fileWidth - 3) + "..."
        }
        
        Write-Host ("{0,-$nameWidth} {1,-$statusWidth} {2}" -f $stepNameFormatted, $status, $outputFile)
    }
    Write-Host ""; return $filesExist
}

function Show-DataCompletenessReport {
    param([string]$BaseDirectory = ".", [switch]$TestMode)
    
    $completionInfoPath = Join-Path $BaseDirectory "data/reports/pipeline_completion_info.json"
    
    if (Test-Path $completionInfoPath) {
        try {
            $completionInfo = Get-Content $completionInfoPath | ConvertFrom-Json
            
            # Check if any steps have missing data
            $hasIssues = $false
            foreach ($step in $completionInfo.PSObject.Properties) {
                # Check if the step has missing_count property and if it's greater than 0
                if ($step.Value.PSObject.Properties.Name -contains "missing_count") {
                    $missingCount = $step.Value.missing_count
                    if ($missingCount -and $missingCount -gt 0) {
                        $hasIssues = $true
                        break
                    }
                }
            }
            
            if ($hasIssues) {
                Write-Host "`n${C_YELLOW}--- Data Completeness Report ---${C_RESET}"
                Write-Host "The following steps had missing subjects:"
                
                foreach ($step in $completionInfo.PSObject.Properties) {
                    $info = $step.Value
                    # Only show steps that have missing_count property and it's greater than 0
                    if ($info.PSObject.Properties.Name -contains "missing_count") {
                        $missingCount = $info.missing_count
                        if ($missingCount -and $missingCount -gt 0) {
                            # Ensure completion_rate is a valid number before using it
                            $completionRate = if ($info.completion_rate -and $info.completion_rate -is [double]) { $info.completion_rate } else { 0 }
                            # Use PowerShell ConsoleColor enum values, not ANSI codes
                            $statusColor = if ($completionRate -ge 99) { "Green" }
                                           elseif ($completionRate -ge 95) { "Yellow" }
                                           else { "Red" }
                            
                            Write-Host "  - $($info.step_name): $($completionRate.ToString('F1'))% complete ($($missingCount) missing)" -ForegroundColor $statusColor
                            
                            if ($info.missing_report_path) {
                                $relativePath = $info.missing_report_path -replace [regex]::Escape($BaseDirectory), "." -replace "\\", "/"
                                Write-Host "    Details: $relativePath" -ForegroundColor DarkGray
                            }
                        }
                    }
                }
                
                Write-Host ""
                Write-Host "${C_YELLOW}To retry missing subjects for a specific step, run:${C_RESET}"
                Write-Host "  .\\prepare_data.ps1 -StartWithStep <step_number>"
                Write-Host ""
                Write-Host "${C_CYAN}Step numbers:${C_RESET}"
                Write-Host "  5: Generate Eminence Scores"
                Write-Host "  6: Generate OCEAN Scores"
                Write-Host ""
            } else {
                # All steps are complete, no missing subjects
                Write-Host "`n${C_GREEN}--- Data Completeness Report ---${C_RESET}"
                Write-Host "All steps are complete with no missing subjects."
                Write-Host ""
            }
        }
        catch {
            Write-Host "${C_YELLOW}Warning: Could not read data completeness information. Error: $($_.Exception.Message)${C_RESET}"
        }
    } else {
        # No completion info file exists
        Write-Host "`n${C_YELLOW}--- Data Completeness Report ---${C_RESET}"
        Write-Host "No data completeness information available."
        if ($TestMode) {
            Write-Host "${C_CYAN}[TEST MODE] This report is not generated in test mode (expected behavior).${C_RESET}"
        } else {
            Write-Host "Run the pipeline to generate completion information."
        }
        Write-Host ""
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
        # Display an overview first
        Write-Host "`n${C_CYAN}Data Preparation Pipeline Overview${C_RESET}"
        Write-Host ("-" * 45)
        Write-Host "This pipeline consists of 14 steps, including 2 manual steps that"
        Write-Host "require your intervention. The entire process typically takes"
        Write-Host "3 hours or more to complete, depending on the size of your dataset"
        Write-Host "and the performance of the selected LLM models."
        Write-Host ""
        
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
                Read-Host -Prompt "${C_ORANGE}Review the configuration parameters above, then press Enter to continue (Ctrl+C to exit)...${C_RESET}" | Out-Null
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
    # Handle restore backup mode before anything else
    if ($RestoreBackup.IsPresent) {
        # Determine working directory for restore
        $restoreBaseDir = $ProjectRoot
        
        # Use explicit parameter if provided (for testing)
        if ($RestoreFromPath) {
            $restoreBaseDir = $RestoreFromPath
        }
        # Otherwise check environment variable
        elseif ($env:PROJECT_SANDBOX_PATH -and (Test-Path $env:PROJECT_SANDBOX_PATH)) {
            $restoreBaseDir = $env:PROJECT_SANDBOX_PATH
        }
        
        Restore-Recent-Backup -BaseDir $restoreBaseDir
        exit 0
    }
    
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
        
        # Show data completeness report
        Show-DataCompletenessReport -BaseDirectory $WorkingDirectory
        
        # Generate pipeline summary report (skip in test mode)
        if (-not $TestMode.IsPresent) {
            Write-Host "`n${C_YELLOW}Generating pipeline summary report...${C_RESET}"
            $summaryScriptPath = Join-Path $ProjectRoot "src/generate_data_preparation_summary.py"
        $summaryArgs = "run", "python", "-u", $summaryScriptPath
        if ($SandboxMode) {
            $summaryArgs += "--sandbox-path", $WorkingDirectory
        }
        $originalLocation = Get-Location
        try {
            Set-Location $WorkingDirectory
            $commandString = "pdm " + ($summaryArgs -join " ")
            Invoke-Expression $commandString | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "${C_GREEN}Pipeline summary report generated successfully.${C_RESET}"
            } else {
                Write-Host "${C_YELLOW}Warning: Pipeline summary report generation returned exit code $LASTEXITCODE${C_RESET}"
            }
        }
        catch {
            Write-Host "${C_YELLOW}Warning: Could not generate pipeline summary report. Error: $($_.Exception.Message)${C_RESET}"
        }
        finally {
            Set-Location $originalLocation
        }
        }    
        Write-Host "${C_CYAN}Report-only mode enabled. Exiting.${C_RESET}"; return
    }
    
    # For Interactive and Normal modes, check if files exist without displaying the status table
    $anyFileExists = $false
    if (-not $SandboxMode) {
        # Check if any output files exist without showing the status table
        foreach ($step in $PipelineSteps) {
            $stepStatus = Get-StepStatus -Step $step -BaseDirectory $WorkingDirectory -ConfigFilePath $configFile
            if ($stepStatus -eq "Complete" -or $stepStatus -eq "Partial" -or $stepStatus -eq "Pending") {
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
        if ($StartWithStep -eq 0) {
            Write-Host "`n${C_YELLOW}WARNING: The -Force flag is active."
            Write-Host "This will back up and delete all existing data artifacts to re-run the entire pipeline from scratch.${C_RESET}"
        } else {
            Write-Host "`n${C_YELLOW}WARNING: The -Force flag is active with -StartWithStep $StartWithStep."
            Write-Host "This will back up and delete data artifacts from Step $StartWithStep onwards.${C_RESET}"
        }
        $confirm = Read-Host "Are you sure you want to proceed? (Y/N)"
        if ($confirm.Trim().ToLower() -ne 'y') { throw "USER_CANCELLED: Operation cancelled by user." }

        Write-Host "`n${C_YELLOW}Backing up and removing existing data files...${C_RESET}`n"
        
        try {
            # Determine which steps to backup based on StartWithStep
            $startBackupFrom = if ($StartWithStep -gt 0) { $StartWithStep } else { 1 }
            
            # Special handling for neutralization directory, which contains multiple files
            $neutralizationStepIndex = ($PipelineSteps | ForEach-Object { $i = 0 } { $i++; if ($_.Name -eq "Neutralize Delineations") { $i } }).Where({$_})[0]
            if ($neutralizationStepIndex -ge $startBackupFrom) {
                $neutralizationStep = $PipelineSteps | Where-Object { $_.Name -eq "Neutralize Delineations" }
                if ($neutralizationStep) {
                    $repFile = Join-Path $WorkingDirectory $neutralizationStep.Output
                    $outputDir = Split-Path $repFile -Parent
                    Backup-And-Remove -ItemPath $outputDir
                }
            }
            
            # Handle all other individual files from pipeline steps
            $stepIndex = 0
            foreach ($step in $PipelineSteps) {
                $stepIndex++
                if ($stepIndex -ge $startBackupFrom -and $step.Name -ne "Neutralize Delineations") {
                    Backup-And-Remove -ItemPath (Join-Path $WorkingDirectory $step.Output)
                }
            }
            
            # Also backup and remove all other generated reports and intermediate files
            # to ensure a completely clean state.
            $otherGeneratedFiles = @(
                # Reports
                "data/reports/eminence_scores_summary.txt",
                "data/reports/ocean_scores_summary.txt",
                "data/reports/adb_validation_summary.txt",
                "data/reports/delineation_coverage_map.csv",
                "data/reports/missing_eminence_scores.txt",
                "data/reports/missing_ocean_scores.txt",
                "data/reports/missing_sf_subjects.csv",
                "data/reports/data_preparation_pipeline_summary.txt",
                "data/reports/pipeline_completion_info.json",
                # Foundational Assets (generated)
                "data/foundational_assets/variance_curve_analysis.png",
                # Processed Files (generated)
                "data/processed/adb_wiki_links.csv"
            )

            foreach ($file in $otherGeneratedFiles) {
                Backup-And-Remove -ItemPath (Join-Path $WorkingDirectory $file)
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
                "data/foundational_assets/assembly_logic/subject_db.assembly_logic.csv"
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
        Write-Host "${C_CYAN}`nINFO: One or more data files already exist."
        
        # Find the first incomplete step
        $firstIncompleteStep = $null
        $pendingManualStep = $null
        for ($i = 0; $i -lt $PipelineSteps.Count; $i++) {
            $stepStatus = Get-StepStatus -Step $PipelineSteps[$i] -BaseDirectory $WorkingDirectory -ConfigFilePath $configFile
            $stepName = $PipelineSteps[$i].Name
            
            # Check for pending manual steps first
            if ($stepStatus -eq "Pending" -and $PipelineSteps[$i].Type -eq "Manual") {
                $pendingManualStep = $i + 1  # +1 to convert to 1-based indexing
                break
            }
            
            # Then check for other incomplete steps
            if ($stepStatus -ne "Complete" -and $stepStatus -ne "Partial") {
                $firstIncompleteStep = $i + 1  # +1 to convert to 1-based indexing
                break
            }
        }
        
        if ($pendingManualStep) {
            # We found a pending manual step, which takes precedence
            $stepName = $PipelineSteps[$pendingManualStep - 1].Name
            $stepStatus = Get-StepStatus -Step $PipelineSteps[$pendingManualStep - 1] -BaseDirectory $WorkingDirectory -ConfigFilePath $configFile
            if ($StopAfterStep -gt 0 -and $pendingManualStep -gt $StopAfterStep) {
                Write-Host "The pipeline would resume at Step ${pendingManualStep}: $stepName"
                Write-Host "However, execution will stop after Step ${StopAfterStep} as requested."
            } elseif ($stepName -eq "Astrology Data Export (Manual)") {
                Write-Host "The pipeline will resume at Step ${pendingManualStep}: $stepName"
                Write-Host "The Solar Fire export file has been detected and will be automatically fetched."
            } else {
                Write-Host "The pipeline will resume at Step ${pendingManualStep}: $stepName"
            }
        } elseif ($firstIncompleteStep) {
            # We found an incomplete step that's not a pending manual step
            $stepName = $PipelineSteps[$firstIncompleteStep - 1].Name
            if ($StopAfterStep -gt 0 -and $firstIncompleteStep -gt $StopAfterStep) {
                Write-Host "The pipeline would resume at Step ${firstIncompleteStep}: $stepName"
                Write-Host "However, execution will stop after Step ${StopAfterStep} as requested."
            } else {
                Write-Host "The pipeline will resume at Step ${firstIncompleteStep}: $stepName"
            }
        } else {
            # All steps are complete, so inform the user
            Write-Host "All steps are already complete. Use -Force to re-run the entire pipeline."
            
            # Determine which adaptive steps are in the current run scope
            $runStart = if ($StartWithStep -gt 0) { $StartWithStep } else { 1 }
            $runEnd = if ($StopAfterStep -gt 0) { $StopAfterStep } else { $PipelineSteps.Count }
            
            $adaptiveStepsInScope = @()
            if ($runStart -le 7 -and $runEnd -ge 7) {
                $adaptiveStepsInScope += "Step 7 (Analyze Cutoff Parameters)"
            }
            if ($runStart -le 12 -and $runEnd -ge 12) {
                $adaptiveStepsInScope += "Step 12 (Neutralize Delineations)"
            }
            
            if ($adaptiveStepsInScope.Count -gt 0) {
                Write-Host "${C_YELLOW}Note: $($adaptiveStepsInScope -join ' and ') may trigger downstream updates if needed.${C_RESET}"
            }
        }
        
        Read-Host -Prompt "${C_ORANGE}Press Enter to continue (Ctrl+C to exit)...${C_RESET}" | Out-Null
    }

    # Determine the first step of each stage for clean banner logging
    $firstStepNamesOfStages = ($PipelineSteps | Group-Object Stage | ForEach-Object { $_.Group[0].Name }) -as [string[]]

    # Track whether we've shown the overwrite instruction
    $overwriteInstructionShown = $false

    # Initialize session tracking flags
    $script:AnyStepExecutedThisRun = $false
    $script:Step7ExecutedThisRun = $false
    $script:Step7ParametersChanged = $false
    
    # Warn if StopAfterStep is used (testing only)
    if ($StopAfterStep -gt 0 -and -not $TestMode.IsPresent) {
        Write-Host "`n${C_YELLOW}WARNING: -StopAfterStep is intended for testing purposes only.${C_RESET}"
        Write-Host "${C_YELLOW}Stopping before pipeline completion may result in inconsistent data.${C_RESET}"
        Write-Host "${C_YELLOW}Downstream steps that depend on executed steps will not be run.${C_RESET}`n"
    }
    
    $totalSteps = $PipelineSteps.Count; $stepCounter = 0
    foreach ($step in $PipelineSteps) {
        $stepCounter++
        
        # Skip steps before the StartWithStep if specified
        if ($StartWithStep -gt 0 -and $stepCounter -lt $StartWithStep) {
            continue
        }
        
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

        # Global rule: Any step that executes forces all downstream steps to re-run
        # This ensures data consistency throughout the pipeline
        # Track if any previous step executed in this session
        $shouldForceDownstream = $script:AnyStepExecutedThisRun
        
        $stepStatus = Get-StepStatus -Step $step -BaseDirectory $WorkingDirectory -ConfigFilePath $configFile
        
        # Exception 1: Step 7 (Analyze Cutoff Parameters) only forces downstream if parameters changed
        # If Step 7 executed but parameters didn't change, don't force Steps 8-11
        if ($stepCounter -ge 8 -and $stepCounter -le 11 -and $script:Step7ExecutedThisRun -and -not $script:Step7ParametersChanged) {
            $shouldForceDownstream = $false
        }
        
        # Exception 2: Step 12 (Neutralize Delineations) has its own state machine
        # It's independent and only re-runs based on staleness/partialness (handled by Get-StepStatus)
        # So we don't force it based on upstream execution
        if ($stepCounter -eq 12) {
            $shouldForceDownstream = $false
        }
        
        # Special handling: If Step 12 (Neutralize Delineations) is not COMPLETE, force reprocessing of steps 13 and 14
        if ($stepCounter -gt 12 -and $step.Name -in @("Create Subject Database", "Generate Personalities Database")) {
            $step12Status = Get-StepStatus -Step $PipelineSteps[11] -BaseDirectory $WorkingDirectory -ConfigFilePath $configFile
            if ($step12Status -ne "Complete") {
                $shouldForceDownstream = $true
            }
        }
        
        # For manual steps, halt the pipeline when status is PENDING
        if ($step.Type -eq 'Manual' -and $stepStatus -eq "Pending" -and -not $isInteractiveForceOverwrite -and -not $shouldForceDownstream) {
            # Always print the step header for pending manual steps, regardless of Resumed flag
            if ($Interactive) {
                $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
                Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
                Write-Host "$C_BLUE$stepHeader$C_RESET"
                Write-Host "$C_BLUE$($step.Description)$C_RESET"
                Write-Host "`n${C_YELLOW}MANUAL STEP PENDING: The required file has been detected but needs to be processed.${C_RESET}"
                
                # Show inputs and output information
                $infoBlock = New-Object System.Text.StringBuilder
                [void]$infoBlock.AppendLine("`n${C_RESET}  INPUTS:")
                $Step.Inputs | ForEach-Object { [void]$infoBlock.AppendLine("    - $_") }
                [void]$infoBlock.AppendLine("`n  OUTPUT:")
                [void]$infoBlock.Append("    - $($Step.Output)")
                [void]$infoBlock.AppendLine("")
                [void]$infoBlock.AppendLine("")
                [void]$infoBlock.AppendLine("${C_YELLOW}NOTE: The pipeline will halt at this manual step.
Please complete the required action and then re-run the script to continue.${C_RESET}")
                
                # Piping to Out-Host forces the multi-line info block to flush immediately
                $infoBlock.ToString() | Out-Host
                
                # Handle interactive prompt
                if ($env:UNDER_TEST_HARNESS -eq "true") {
                    # Signal to test harness and wait for response
                    $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
                    Write-Host "HARNESS_PROMPT:Manual step is pending. Press Enter to halt the pipeline...:$waitFile"
                    # Wait for test harness to create the response file
                    while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
                    Remove-Item $waitFile -ErrorAction SilentlyContinue
                } else {
                    # Standard Read-Host for normal operation
                    Read-Host -Prompt "${C_ORANGE}Manual step is pending. Press Enter to halt the pipeline...${C_RESET}" | Out-Null
                }
            } else {
                # In non-interactive mode (including TestMode), print full step header
                $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
                Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
                Write-Host "$C_BLUE$stepHeader$C_RESET"
                
                # Use the TestMode-modified description if available, otherwise use original
                $displayDescription = $step.Description
                if ($TestMode.IsPresent -and $step.Name -eq "Delineations Library Export (Manual)") {
                    $displayDescription = "Simulating the one-time Solar Fire delineation library export."
                } elseif ($TestMode.IsPresent -and $step.Name -eq "Astrology Data Export (Manual)") {
                    $displayDescription = "Simulating the manual Solar Fire import, calculation, and chart export process."
                }
                Write-Host "$C_BLUE$displayDescription$C_RESET"
                
                Write-Host "`n${C_RESET}  INPUTS:"
                $Step.Inputs | ForEach-Object { Write-Host "    - $_" }
                Write-Host "`n  OUTPUT:"
                Write-Host "    - $($Step.Output)"
                
                # Add test mode explanation
                if ($TestMode.IsPresent) {
                    Write-Host "`n${C_CYAN}[TEST MODE] This manual step is simulated for testing purposes.${C_RESET}"
                }
                Write-Host ""
                
                Write-Host "Step ${stepCounter}: '$($step.Name)' is pending. Halting pipeline." -ForegroundColor Yellow
            }
            # Halt the pipeline for pending manual steps
            throw "The pipeline is paused because a manual step is incomplete. Please refer to the Framework Manual for detailed instructions on completing Step ${stepCounter}: '$($step.Name)'."
        }
        
        # Special handling for Step 11 (Neutralize Delineations) when Partial
        if ($step.Name -eq "Neutralize Delineations" -and $stepStatus -eq "Partial" -and -not $isInteractiveForceOverwrite -and -not $shouldForceDownstream) {
            if (-not $Resumed.IsPresent) {
                # Print the detailed step header for partial completion
                if ($Interactive) {
                    $stepHeader = ">>> Step $stepCounter/${totalSteps}: $($step.Name) <<<"
                    Write-Host "`n$C_GRAY$('-'*80)$C_RESET"
                    Write-Host "$C_BLUE$stepHeader$C_RESET"
                    Write-Host "$C_BLUE$($step.Description)$C_RESET"
                    Write-Host "`n${C_YELLOW}PARTIAL COMPLETION DETECTED: Some output files are missing or incomplete.${C_RESET}"
                    
                    # Show inputs and output information
                    $infoBlock = New-Object System.Text.StringBuilder
                    [void]$infoBlock.AppendLine("`n${C_RESET}  INPUTS:")
                    $Step.Inputs | ForEach-Object { [void]$infoBlock.AppendLine("    - $_") }
                    [void]$infoBlock.AppendLine("`n  OUTPUT:")
                    [void]$infoBlock.Append("    - $($Step.Output)")
                    [void]$infoBlock.AppendLine("")
                    [void]$infoBlock.AppendLine("")
                    [void]$infoBlock.AppendLine("${C_YELLOW}NOTE: This step will continue processing only the missing or incomplete files.${C_RESET}")
                    
                    # Piping to Out-Host forces the multi-line info block to flush immediately
                    $infoBlock.ToString() | Out-Host
                    
                    # Handle interactive prompt
                    if ($env:UNDER_TEST_HARNESS -eq "true") {
                        # Signal to test harness and wait for response
                        $waitFile = Join-Path $env:TEMP "harness_wait_$PID.txt"
                        Write-Host "HARNESS_PROMPT:Step will process missing files. Press Enter to continue...:$waitFile"
                        # Wait for test harness to create the response file
                        while (-not (Test-Path $waitFile)) { Start-Sleep -Milliseconds 100 }
                        Remove-Item $waitFile -ErrorAction SilentlyContinue
                    } else {
                        # Standard Read-Host for normal operation
                        Read-Host -Prompt "${C_ORANGE}Step will process missing files. Press Enter to continue...${C_RESET}" | Out-Null
                    }
                } else {
                    Write-Host "Step ${stepCounter}: '$($step.Name)' is partially complete. Processing missing files only." -ForegroundColor Yellow
                }
            }
            # Don't skip - continue with execution to process missing files
        }
        # Skip if the step is complete AND we are not in force-overwrite mode AND we didn't start from a previous step
        # If we resumed from a previous step, we need to force re-execution of all downstream steps
        # Stale status is treated like Missing - it triggers re-processing
        elseif (($stepStatus -eq "Complete" -or ($stepStatus -eq "Partial" -and $step.Name -ne "Neutralize Delineations")) -and $stepStatus -ne "Stale" -and -not $isInteractiveForceOverwrite -and -not $shouldForceDownstream) {
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
                    if ($Step.Name -eq "Astrology Data Export (Manual)") {
                        [void]$infoBlock.AppendLine("${C_YELLOW}NOTE: This step will be skipped because the Solar Fire export file has been detected and will be automatically fetched by the next step.${C_RESET}")
                    } elseif ($stepStatus -eq "Partial") {
                        [void]$infoBlock.AppendLine("${C_YELLOW}NOTE: This step will be skipped because it has been partially completed. Re-run with --force to process all files.${C_RESET}")
                    } else {
                        [void]$infoBlock.AppendLine("${C_YELLOW}NOTE: This step will be skipped because the output file already exists.${C_RESET}")
                    }
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
                    if ($stepStatus -eq "Partial") {
                        Write-Host "Step ${stepCounter}: '$($step.Name)' is partially complete. Skipping. Use --force to process all files." -ForegroundColor Yellow
                    } else {
                        # Special messaging for adaptive steps
                        if ($step.Name -eq "Analyze Cutoff Parameters") {
                            # Read current parameters to show they're unchanged
                            $currentStartPoint = Get-ConfigValue -FilePath $configFile -Section "DataGeneration" -Key "cutoff_search_start_point" -DefaultValue "unknown"
                            $currentSmoothingWindow = Get-ConfigValue -FilePath $configFile -Section "DataGeneration" -Key "smoothing_window_size" -DefaultValue "unknown"
                            Write-Host "Step ${stepCounter}: '$($step.Name)' - Parameters unchanged (start=$currentStartPoint, window=$currentSmoothingWindow). Skipping." -ForegroundColor Cyan
                        }
                        elseif ($step.Name -eq "Neutralize Delineations") {
                            Write-Host "Step ${stepCounter}: '$($step.Name)' - Neutralized files are up to date and complete. Skipping." -ForegroundColor Cyan
                        }
                        else {
                            Write-Host "Output exists for Step ${stepCounter}: '$($step.Name)'. Skipping." -ForegroundColor Cyan
                        }
                    }
                }
            }
            $isSkipped = $true
        }
        if ($isSkipped) {
            # Check if we should stop after this skipped step
            if ($StopAfterStep -gt 0 -and $stepCounter -eq $StopAfterStep) {
                Write-Host "`n${C_MAGENTA}Stopping at Step $stepCounter as requested (step was skipped).${C_RESET}"
                $exitCode = 1
                break
            }
            continue
        }
        
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
                # In test mode, print step header before halting
                Write-Host "`n${C_RESET}  INPUTS:"
                $Step.Inputs | ForEach-Object { Write-Host "    - $_" }
                Write-Host "`n  OUTPUT:"
                Write-Host "    - $($Step.Output)"
                Write-Host ""
                
                # Set the exit code and break the loop
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
        # Only suppress API warnings in test/sandbox mode, not in normal operation
        if ($step.Name -in "Generate Eminence Scores", "Generate OCEAN Scores" -and ($TestMode.IsPresent -or $SandboxMode)) {
            $arguments += "--no-api-warning"
        }

        # For the final step, explicitly pass the correct output path in all modes
        if ($step.Name -eq "Generate Personalities Database") {
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
        
        # Mark that a step executed successfully (for downstream forcing logic)
        $script:AnyStepExecutedThisRun = $true
        
        # Special post-processing for Analyze Cutoff Parameters step
        if ($step.Name -eq "Analyze Cutoff Parameters") {
            Write-Host "`n${C_YELLOW}Updating config.ini with optimal cutoff parameters...${C_RESET}"
            $csvPath = Join-Path $WorkingDirectory $step.Output
            if (Test-Path $csvPath) {
                try {
                    # Read current parameters from config
                    $configPath = Join-Path $WorkingDirectory "config.ini"
                    $currentStartPoint = Get-ConfigValue -FilePath $configPath -Section "DataGeneration" -Key "cutoff_search_start_point" -DefaultValue "0"
                    $currentSmoothingWindow = Get-ConfigValue -FilePath $configPath -Section "DataGeneration" -Key "smoothing_window_size" -DefaultValue "0"
                    
                    # Read the CSV and get the top row (best parameters)
                    $csvContent = Import-Csv $csvPath
                    if ($csvContent.Count -gt 0) {
                        $bestParams = $csvContent[0]
                        $newStartPoint = $bestParams.'Start Point'
                        $newSmoothingWindow = $bestParams.'Smoothing Window'
                        
                        # Check if parameters actually changed
                        if ($newStartPoint -ne $currentStartPoint -or $newSmoothingWindow -ne $currentSmoothingWindow) {
                            # Update config.ini
                            $configContent = Get-Content $configPath -Raw
                            $configContent = $configContent -replace '(?m)^cutoff_search_start_point\s*=\s*\d+', "cutoff_search_start_point = $newStartPoint"
                            $configContent = $configContent -replace '(?m)^smoothing_window_size\s*=\s*\d+', "smoothing_window_size = $newSmoothingWindow"
                            $configContent | Set-Content $configPath -NoNewline
                            
                            Write-Host "${C_GREEN}Config updated: cutoff_search_start_point = $newStartPoint, smoothing_window_size = $newSmoothingWindow${C_RESET}"
                            Write-Host "${C_YELLOW}Parameters changed - downstream steps 8-11 will be re-executed${C_RESET}"
                            
                            # Set flags to force downstream steps 8-11 to re-run
                            $script:Step7ExecutedThisRun = $true
                            $script:Step7ParametersChanged = $true
                        } else {
                            Write-Host "${C_GREEN}Parameters unchanged: cutoff_search_start_point = $newStartPoint, smoothing_window_size = $newSmoothingWindow${C_RESET}"
                            Write-Host "${C_CYAN}No changes detected - downstream steps will not be forced to re-run${C_RESET}"
                            
                            # Mark that Step 7 ran but didn't change parameters
                            $script:Step7ExecutedThisRun = $true
                            $script:Step7ParametersChanged = $false
                        }
                    } else {
                        Write-Host "${C_YELLOW}Warning: CSV file is empty, config not updated${C_RESET}"
                    }
                } catch {
                    Write-Host "${C_YELLOW}Warning: Could not update config.ini. Error: $($_.Exception.Message)${C_RESET}"
                }
            } else {
                Write-Host "${C_YELLOW}Warning: Analysis results file not found at $csvPath${C_RESET}"
            }
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
        } elseif ($errorMessage -match "Script .* failed with exit code") {
            # This is a script failure, provide instructions to resume from the failed step
            $failedStep = $stepCounter
            Write-Host "`n${C_YELLOW}TO RESUME FROM THIS STEP:${C_RESET}"
            Write-Host "Run the following command to restart from the failed step:"
            Write-Host "  .\prepare_data.ps1 -StartWithStep $failedStep" -ForegroundColor Cyan
            Write-Host ""
            Write-Host "Alternatively, you can run the pipeline using pdm:"
            Write-Host "  pdm run prep-data -StartWithStep $failedStep" -ForegroundColor Cyan
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
            Show-DataCompletenessReport -BaseDirectory $WorkingDirectory -TestMode:$TestMode
            
            # Generate pipeline summary report (skip in test mode)
            if (-not $TestMode.IsPresent) {
                Write-Host "`n${C_YELLOW}Generating pipeline summary report...${C_RESET}"
                $summaryScriptPath = Join-Path $ProjectRoot "src/generate_data_preparation_summary.py"
                $summaryArgs = "run", "python", "-u", $summaryScriptPath
                if ($SandboxMode) {
                    $summaryArgs += "--sandbox-path", $WorkingDirectory
                }
                $originalLocation = Get-Location
                try {
                    Set-Location $WorkingDirectory
                    $commandString = "pdm " + ($summaryArgs -join " ")
                    Invoke-Expression $commandString | Out-Null
                    if ($LASTEXITCODE -eq 0) {
                        Write-Host "${C_GREEN}Pipeline summary report generated successfully.${C_RESET}"
                    } else {
                        Write-Host "${C_YELLOW}Warning: Pipeline summary report generation returned exit code $LASTEXITCODE${C_RESET}"
                    }
                }
                catch {
                    Write-Host "${C_YELLOW}Warning: Could not generate pipeline summary report. Error: $($_.Exception.Message)${C_RESET}"
                }
                finally {
                    Set-Location $originalLocation
                }
            }
        }
    }
    exit $exitCode
}

# === End of prepare_data.ps1 ===
