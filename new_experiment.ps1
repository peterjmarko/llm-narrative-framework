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
# Filename: new_experiment.ps1

<#
.SYNOPSIS
  Creates and runs a new experiment from scratch based on the global config.ini.

.DESCRIPTION
  This script is the primary entry point for CREATING a new experiment. It reads the
  main 'config.ini' file, calls the Python backend to generate a new, timestamped
  experiment directory, and executes the full set of replications.

  Upon successful completion, it automatically runs a final verification audit to
  provide immediate confirmation of the new experiment's status.

.PARAMETER Notes
    A string of notes to embed in the new experiment's reports and logs.

.PARAMETER Verbose
    A switch to enable detailed, real-time output from all underlying Python scripts.
    By default, output is a high-level summary.

.EXAMPLE
  # Run a new experiment using the settings from 'config.ini'.
  .\new_experiment.ps1

.EXAMPLE
  # Run a new experiment with notes and detailed logging.
  .\new_experiment.ps1 -Notes "First run with Llama 3 70B" -Verbose
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$Notes,

    [Parameter(Mandatory=$false)]
    [Alias('config-path')]
    [string]$ConfigPath
)

function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

function Write-Header { param([string[]]$Lines, [string]$Color = "White"); $s = "#" * 80; Write-Host "`n$s" -F $Color; foreach ($l in $Lines) { $pL = [math]::Floor((80 - $l.Length - 6) / 2); $pR = [math]::Ceiling((80 - $l.Length - 6) / 2); Write-Host "###$(' ' * $pL)$l$(' ' * $pR)###" -F $Color }; Write-Host $s -F $Color; Write-Host "" }

function Read-StudyParameters {
    param([string]$ConfigPath)
    
    $studyParams = @{
        mapping_strategy = @()
        group_size = @()
        num_replications = @()
        num_trials = @()
        model_name = @()
        temperature = @()
        max_tokens = @()
    }
    
    if (-not (Test-Path $ConfigPath)) {
        return $null
    }
    
    $inStudySection = $false
    Get-Content $ConfigPath | ForEach-Object {
        $line = $_.Trim()
        if ($line -match '^\[Study\]') {
            $inStudySection = $true
        }
        elseif ($line -match '^\[') {
            $inStudySection = $false
        }
        elseif ($inStudySection -and $line -match '^(mapping_strategy|group_size|num_replications|num_trials|model_name|temperature|max_tokens)\s*=\s*(.+)$') {
            $key = $matches[1]
            $values = $matches[2] -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
            if ($values.Count -gt 0) {
                $studyParams[$key] = $values
            }
        }
    }
    
    # Return null if all arrays are empty (no study parameters defined)
    $hasAnyParams = $false
    foreach ($key in $studyParams.Keys) {
        if ($studyParams[$key].Count -gt 0) {
            $hasAnyParams = $true
            break
        }
    }
    
    if (-not $hasAnyParams) {
        return $null
    }
    
    return $studyParams
}

function Show-StudyParameterSelection {
    param($StudyParams)
    
    Write-Host "`nStudy Experimental Design" -ForegroundColor Magenta
    Write-Host ("=" * 80) -ForegroundColor Magenta
    
    $paramOrder = @('mapping_strategy', 'group_size', 'num_replications', 'num_trials', 'model_name', 'temperature', 'max_tokens')
    $paramLabels = @{
        mapping_strategy = "Mapping Strategies"
        group_size = "Group Sizes"
        num_replications = "Number of Replications"
        num_trials = "Number of Trials"
        model_name = "Models"
        temperature = "Temperature Values"
        max_tokens = "Max Tokens"
    }
    
    foreach ($param in $paramOrder) {
        if ($StudyParams[$param].Count -gt 1) {
            Write-Host "`n$($paramLabels[$param]):" -ForegroundColor Yellow
            for ($i = 0; $i -lt $StudyParams[$param].Count; $i++) {
                Write-Host "  [$($i+1)] $($StudyParams[$param][$i])"
            }
        }
    }
    
    Write-Host ""
}

function Get-UserSelection {
    param(
        [string]$ParameterName,
        [array]$Options,
        [bool]$IsFirstPrompt = $false
    )
    
    # Single value: use it without prompting
    if ($Options.Count -eq 1) {
        return $Options[0]
    }
    
    while ($true) {
        $promptText = "Select $ParameterName [1-$($Options.Count)]"
        if ($IsFirstPrompt) {
            $promptText += " or 'e' to use [Experiment] defaults"
        }
        
        try {
            $selection = Read-Host $promptText
        } catch {
            # Ctrl+C pressed - throw to outer catch block
            throw
        }
        
        # Check for 'e' option (only on first prompt)
        if ($IsFirstPrompt -and $selection -eq 'e') {
            return 'USE_EXPERIMENT_DEFAULTS'
        }
        
        if ($selection -match '^\d+$') {
            $index = [int]$selection - 1
            if ($index -ge 0 -and $index -lt $Options.Count) {
                return $Options[$index]
            }
        }
        
        Write-Host "Invalid selection. Please enter a number between 1 and $($Options.Count)." -ForegroundColor Red
    }
}

function Update-ConfigParameter {
    param($Lines, $Section, $Key, $Value)
    
    $inSection = $false
    $updated = $false
    $result = @()
    
    foreach ($line in $Lines) {
        if ($line -match "^\[$Section\]") {
            $inSection = $true
            $result += $line
        } elseif ($line -match "^\[.*\]") {
            if ($inSection -and -not $updated) {
                $result += "$Key = $Value"
                $updated = $true
            }
            $inSection = $false
            $result += $line
        } elseif ($inSection -and $line -match "^\s*$Key\s*=") {
            $result += "$Key = $Value"
            $updated = $true
        } else {
            $result += $line
        }
    }
    
    # Add section if it doesn't exist
    if (-not $updated) {
        $sectionExists = $Lines | Where-Object { $_ -match "^\[$Section\]" }
        if (-not $sectionExists) {
            $result += "[$Section]"
        }
        $result += "$Key = $Value"
    }
    
    return $result
}

function Write-StudyLog {
    param(
        [string]$StudyDirectory,
        [hashtable]$Selections,
        [string]$ExperimentPath
    )
    
    $logPath = Join-Path $StudyDirectory "study_creation_log.txt"
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $experimentName = Split-Path $ExperimentPath -Leaf
    
    $logEntry = @"
[$timestamp]
Experiment: $experimentName
Mapping Strategy: $($Selections.mapping_strategy)
Group Size: $($Selections.group_size)
Model: $($Selections.model_name)
Path: $ExperimentPath

"@
    
    # Create study directory if it doesn't exist
    if (-not (Test-Path $StudyDirectory)) {
        New-Item -ItemType Directory -Path $StudyDirectory -Force | Out-Null
    }
    
    Add-Content -Path $logPath -Value $logEntry -Encoding UTF8
}

$ProjectRoot = Get-ProjectRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Determine config path
$configPath = if ($ConfigPath) { $ConfigPath } else { Join-Path $ProjectRoot "config.ini" }

# Check for Study section and handle interactive selection
$studyParams = Read-StudyParameters -ConfigPath $configPath
$script:configBackup = $null
$script:userSelections = $null
$script:configRestored = $false

try {
    if ($studyParams) {
        Write-Header -Lines "NEW EXPERIMENT SETUP" -Color Cyan
        
        # Create backup directory if it doesn't exist
        $backupDir = Join-Path $ProjectRoot "backup"
        if (-not (Test-Path $backupDir)) {
            New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
        }
        
        # Create backup before any modifications
        $script:configBackup = Join-Path $backupDir "config.ini.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
        Copy-Item $configPath $script:configBackup -Force
        # Helper function to read Experiment defaults
        function Get-ExperimentDefault {
            param([string]$Section, [string]$Key)
            $configContent = Get-Content $configPath -Encoding UTF8
            $inSection = $false
            foreach ($line in $configContent) {
                if ($line -match "^\[$Section\]") { $inSection = $true }
                elseif ($line -match "^\[") { $inSection = $false }
                elseif ($inSection -and $line -match "^\s*$Key\s*=\s*(.+)$") {
                    return $matches[1].Trim()
                }
            }
            return $null
        }
        
        # Define parameter order and metadata
        $paramOrder = @(
            @{Key='mapping_strategy'; Label='Mapping Strategy'; Section='Experiment'},
            @{Key='group_size'; Label='Group Size'; Section='Experiment'},
            @{Key='num_replications'; Label='Number of Replications'; Section='Experiment'},
            @{Key='num_trials'; Label='Number of Trials'; Section='Experiment'},
            @{Key='model_name'; Label='Model'; Section='LLM'},
            @{Key='temperature'; Label='Temperature'; Section='LLM'},
            @{Key='max_tokens'; Label='Max Tokens'; Section='LLM'}
        )
        
        while ($true) { # Main loop to allow restarting selection
            Show-StudyParameterSelection -StudyParams $studyParams
            
            $userSelections = @{}
            $isFirstPrompt = $true
            $useExperimentDefaults = $false
            
            foreach ($param in $paramOrder) {
                $key = $param.Key
                $options = $studyParams[$key]
                
                # Skip if empty in Study section (use Experiment default)
                if ($options.Count -eq 0) {
                    $userSelections[$key] = Get-ExperimentDefault -Section $param.Section -Key $key
                    continue
                }
                
                # Get selection (handles single values automatically)
                $selection = Get-UserSelection -ParameterName $param.Label -Options $options -IsFirstPrompt $isFirstPrompt
                
                # Check if user chose to use Experiment defaults
                if ($selection -eq 'USE_EXPERIMENT_DEFAULTS') {
                    $useExperimentDefaults = $true
                    break
                }
                
                $userSelections[$key] = $selection
                $isFirstPrompt = $false
            }
            
            # If user chose 'e', fill remaining with Experiment defaults
            if ($useExperimentDefaults) {
                Write-Host "`nUsing [Experiment] section defaults..." -ForegroundColor Yellow
                foreach ($param in $paramOrder) {
                    if (-not $userSelections.ContainsKey($param.Key)) {
                        $userSelections[$param.Key] = Get-ExperimentDefault -Section $param.Section -Key $param.Key
                    }
                }
            }
            
            Write-Host "`nSelected Configuration:" -ForegroundColor Green
            foreach ($param in $paramOrder) {
                if ($userSelections.ContainsKey($param.Key)) {
                    Write-Host "  $($param.Label): $($userSelections[$param.Key])" -ForegroundColor White
                }
            }
            Write-Host ""

            # --- Confirmation Prompt ---
            $userConfirmed = $false
            while ($true) {
                try {
                    $confirmation = Read-Host -Prompt "Proceed with this configuration? (Y/N, Ctrl+C to exit)"
                    if ($confirmation.ToLower() -eq 'y') {
                        $userConfirmed = $true
                        break 
                    }
                    elseif ($confirmation.ToLower() -eq 'n') {
                        break
                    }
                    else {
                        Write-Host "Invalid input. Please enter 'y' for yes or 'n' for no." -ForegroundColor Red
                    }
                } catch { throw } # Re-throw Ctrl+C to be caught by the main handler
            }

            if ($userConfirmed) {
                break # Exit the main selection loop and proceed
            } else {
                Write-Host "`nConfiguration rejected. Restarting selection...`n" -ForegroundColor Yellow
                # The loop will automatically restart
            }
        } # End of main selection loop

        # Update config.ini with selections only AFTER confirmation
        $configLines = Get-Content $configPath -Encoding UTF8
        foreach ($param in $paramOrder) {
            if ($userSelections.ContainsKey($param.Key)) {
                $configLines = Update-ConfigParameter $configLines $param.Section $param.Key $userSelections[$param.Key]
            }
        }
        Set-Content -Path $configPath -Value $configLines -Encoding UTF8
        
        # Mark config as successfully updated
        $script:configRestored = $true
    }
    
    # Display banner after selections are complete
    Write-Header -Lines "CREATING NEW EXPERIMENT FROM CONFIG.INI" -Color Cyan

    $pythonScriptPath = Join-Path $ProjectRoot "src/experiment_manager.py"
    $pythonArgs = @($pythonScriptPath)
    if (-not [string]::IsNullOrEmpty($Notes)) { $pythonArgs += "--notes", $Notes }
    if ($PSBoundParameters.ContainsKey('Verbose') -and $PSBoundParameters['Verbose']) { $pythonArgs += "--verbose" }
    if ($Host.UI.SupportsVirtualTerminal) { $pythonArgs += "--force-color" }
    if (-not [string]::IsNullOrEmpty($ConfigPath)) { $pythonArgs += "--config-path", $ConfigPath }

    & pdm run python $pythonArgs
    $pythonExitCode = $LASTEXITCODE

    if ($pythonExitCode -ne 0) {
        Write-Host "`nExperiment creation failed. Check configuration and try again.`n" -ForegroundColor Yellow
        exit $pythonExitCode
    }

# Read the output directory from config instead of hardcoding
    $basePath = Join-Path $ProjectRoot "output/new_experiments"  # Default fallback
    
    if (-not [string]::IsNullOrEmpty($ConfigPath) -and (Test-Path $ConfigPath)) {
        # Parse config to get the actual output directory
        $configContent = Get-Content $ConfigPath -Raw
        if ($configContent -match '(?m)^base_output_dir\s*=\s*(.+)$') {
            $baseOutputDir = $matches[1].Trim()
            if ($configContent -match '(?m)^new_experiments_subdir\s*=\s*(.+)$') {
                $newExperimentsSubdir = $matches[1].Trim()
                $basePath = Join-Path $ProjectRoot (Join-Path $baseOutputDir $newExperimentsSubdir)
            }
        }
    }
    
    $latestExperiment = Get-ChildItem -Path $basePath -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
    if ($null -ne $latestExperiment) {
        # Write to study log if selections were made
        if ($userSelections) {
            $studyDir = Join-Path $ProjectRoot "output/studies"
            Write-StudyLog -StudyDirectory $studyDir -Selections $userSelections -ExperimentPath $latestExperiment.FullName
        }
        
        Write-Header -Lines "Verifying Final Experiment State" -Color Cyan
        $auditScriptPath = Join-Path $ProjectRoot "audit_experiment.ps1"
        
        # Use a hashtable for splatting to ensure named parameters are passed robustly.
        $auditSplat = @{
            ExperimentDirectory = $latestExperiment.FullName
        }
        if (-not [string]::IsNullOrEmpty($ConfigPath)) {
            $auditSplat['ConfigPath'] = $ConfigPath
        }
        & $auditScriptPath @auditSplat
    }
} catch {
    # Catch any errors during the entire execution
    Write-Warning "An error occurred: $($_.Exception.Message)"
} finally {
    # CRITICAL: Restore config on ANY termination (including Ctrl+C)
    if ($script:configBackup -and (Test-Path $script:configBackup) -and -not $script:configRestored) {
        Move-Item $script:configBackup $configPath -Force
        Write-Host "`nOperation interrupted. Configuration restored." -ForegroundColor Yellow
        $script:configRestored = $true
    } elseif ($script:configBackup -and (Test-Path $script:configBackup)) {
        # Normal cleanup - experiment completed successfully
        Remove-Item $script:configBackup -Force
    }
}

# === End of new_experiment.ps1 ===
