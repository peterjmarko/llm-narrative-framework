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
# Filename: generate_factorial_commands.ps1

<#
.SYNOPSIS
    Generates PowerShell commands to create a factorial study design.
    
.DESCRIPTION
    Reads factorial design specification from config.ini and generates the
    new_experiment.ps1 commands needed to create all experimental conditions.
    Does NOT execute commands - only generates them for review and manual execution.
    
.PARAMETER ConfigPath
    Path to the configuration file. Default: "config.ini"
    
.PARAMETER OutputScript
    If specified, writes commands to a .ps1 file that can be executed later.
    
.PARAMETER StudyName
    Custom name for the study. If not provided, generates from factors and timestamp.
    
.PARAMETER DryRun
    Show what would be generated without creating any files.
    
.EXAMPLE
    ./generate_factorial_commands.ps1
    # Displays commands to console
    
.EXAMPLE
    ./generate_factorial_commands.ps1 -OutputScript "run_study.ps1"
    # Saves commands to executable script
    
.EXAMPLE
    ./generate_factorial_commands.ps1 -StudyName "pilot_study_v2" -OutputScript "create_pilot.ps1"
    # Creates named study with saved script
#>

param(
    [string]$ConfigPath = "config.ini",
    [string]$OutputScript = "",
    [string]$StudyName = "",
    [switch]$DryRun
)

# ============================================================================
# Helper Functions
# ============================================================================

function Get-IniContent {
    param([string]$FilePath)
    
    $ini = @{}
    $section = ""
    
    foreach ($line in Get-Content $FilePath) {
        $line = $line.Trim()
        
        if ($line -match '^\[(.+)\]$') {
            $section = $matches[1]
            $ini[$section] = @{}
        }
        elseif ($line -match '^([^=]+)=(.*)$' -and $section) {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            $ini[$section][$key] = $value
        }
    }
    
    return $ini
}

function Parse-FactorialDesign {
    param($StudyConfig)
    
    if (-not $StudyConfig.factors) {
        throw "No 'factors' defined in [Study] section"
    }
    
    $factors = @{}
    $factorPairs = $StudyConfig.factors -split '\|'
    
    foreach ($pair in $factorPairs) {
        if ($pair -match '^([^:]+):(.+)$') {
            $factorName = $matches[1].Trim()
            $levels = $matches[2] -split ',' | ForEach-Object { $_.Trim() }
            $factors[$factorName] = $levels
        }
        else {
            throw "Invalid factor format: $pair. Expected 'name:level1,level2'"
        }
    }
    
    return $factors
}

function Get-FactorialCombinations {
    param($Factors)
    
    $factorNames = @($Factors.Keys)
    $combinations = @()
    
    # Generate all combinations using recursive approach
    function Generate-Combinations {
        param(
            [int]$FactorIndex,
            [hashtable]$Current
        )
        
        if ($FactorIndex -eq $factorNames.Count) {
            $combinations += ,$Current.Clone()
            return
        }
        
        $factorName = $factorNames[$FactorIndex]
        foreach ($level in $Factors[$factorName]) {
            $Current[$factorName] = $level
            Generate-Combinations -FactorIndex ($FactorIndex + 1) -Current $Current
        }
    }
    
    Generate-Combinations -FactorIndex 0 -Current @{}
    return $combinations
}

function Format-ExperimentName {
    param($Combination, $Index)
    
    # Create descriptive name from factor levels
    $parts = @()
    foreach ($factor in $Combination.Keys | Sort-Object) {
        $value = $Combination[$factor]
        # Shorten common values for readability
        $shortValue = switch ($value) {
            "correct" { "cor" }
            "random" { "ran" }
            "true" { "T" }
            "false" { "F" }
            default { 
                if ($value -match '^\d+$') { "k$value" }
                else { $value.Substring(0, [Math]::Min(3, $value.Length)) }
            }
        }
        $parts += $shortValue
    }
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $descriptor = $parts -join "_"
    return "experiment_${timestamp}_${Index}_${descriptor}"
}

function Generate-ExperimentCommand {
    param(
        $ExperimentName,
        $Combination,
        $StudyDir,
        $BaseConfig
    )
    
    # Build the command with parameter overrides
    $overrides = @()
    foreach ($factor in $Combination.Keys | Sort-Object) {
        $value = $Combination[$factor]
        
        # Map factor names to config sections and keys
        # This mapping should be customized based on your config structure
        $configMapping = @{
            "mapping_strategy" = "Model:mapping_strategy"
            "group_size" = "Model:k"
            "temperature" = "Model:temperature"
            "num_trials" = "Experiment:num_trials"
            "model_name" = "Model:model_name"
        }
        
        if ($configMapping.ContainsKey($factor)) {
            $overrides += "-Override ""$($configMapping[$factor])=$value"""
        }
        else {
            # Default: assume it's in the Model section
            $overrides += "-Override ""Model:$factor=$value"""
        }
    }
    
    # Build the full command
    $outputPath = Join-Path $StudyDir $ExperimentName
    $command = ".\new_experiment.ps1 -ConfigPath `"$BaseConfig`" -OutputDir `"$outputPath`""
    
    if ($overrides.Count -gt 0) {
        $command += " " + ($overrides -join " ")
    }
    
    return $command
}

# ============================================================================
# Main Script
# ============================================================================

try {
    Write-Host "`n=== Factorial Study Command Generator ===" -ForegroundColor Cyan
    
    # Load configuration
    if (-not (Test-Path $ConfigPath)) {
        throw "Config file not found: $ConfigPath"
    }
    
    $config = Get-IniContent -FilePath $ConfigPath
    
    if (-not $config.Study) {
        throw "No [Study] section found in config file"
    }
    
    # Parse factorial design
    Write-Host "`nParsing factorial design from config..." -ForegroundColor Yellow
    $factors = Parse-FactorialDesign -StudyConfig $config.Study
    
    # Display design summary
    Write-Host "`nFactorial Design:" -ForegroundColor Green
    foreach ($factor in $factors.Keys | Sort-Object) {
        $levels = $factors[$factor] -join ", "
        Write-Host "  $factor: [$levels]" -ForegroundColor Cyan
    }
    
    # Generate all combinations
    $combinations = Get-FactorialCombinations -Factors $factors
    $totalExperiments = $combinations.Count
    
    Write-Host "`nTotal experimental conditions: $totalExperiments" -ForegroundColor Green
    
    # Generate study name and directory
    if (-not $StudyName) {
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $factorNames = ($factors.Keys | Sort-Object) -join "_"
        $StudyName = "study_${timestamp}_${factorNames}_factorial"
    }
    
    $studyDir = Join-Path "output" "new_studies" $StudyName
    
    Write-Host "`nStudy directory: $studyDir" -ForegroundColor Yellow
    
    # Generate commands
    $commands = @()
    $commands += "# Factorial Study Generation Script"
    $commands += "# Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    $commands += "# Study: $StudyName"
    $commands += "# Design: $($factors.Count) factors, $totalExperiments conditions"
    $commands += ""
    $commands += "# Create study directory"
    $commands += "New-Item -ItemType Directory -Path `"$studyDir`" -Force | Out-Null"
    $commands += ""
    
    # Generate metadata
    $metadata = @{
        study_name = $StudyName
        study_type = "factorial"
        factors = $factors
        total_conditions = $totalExperiments
        generated_date = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        config_file = $ConfigPath
        num_trials = $config.Study.num_trials ?? $config.Experiment.num_trials ?? "10"
    }
    
    $metadataJson = $metadata | ConvertTo-Json -Depth 3
    $commands += "# Create study metadata"
    $commands += "@'"
    $commands += $metadataJson
    $commands += "'@ | Set-Content -Path `"$studyDir\STUDY_metadata.json`" -Encoding UTF8"
    $commands += ""
    $commands += "# Copy base config to study directory"
    $commands += "Copy-Item -Path `"$ConfigPath`" -Destination `"$studyDir\study_config.ini`""
    $commands += ""
    
    # Generate experiment commands
    $commands += "# Create individual experiments"
    $index = 1
    foreach ($combination in $combinations) {
        $expName = Format-ExperimentName -Combination $combination -Index $index
        $command = Generate-ExperimentCommand -ExperimentName $expName `
                                              -Combination $combination `
                                              -StudyDir $studyDir `
                                              -BaseConfig $ConfigPath
        
        $commands += ""
        $commands += "# Condition $index/$totalExperiments - " + 
                     ($combination.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join ", "
        $commands += "Write-Host `"Creating experiment $index of $totalExperiments...`" -ForegroundColor Cyan"
        $commands += $command
        
        $index++
    }
    
    $commands += ""
    $commands += "# Study creation complete"
    $commands += "Write-Host `"`nFactorial study created successfully!`" -ForegroundColor Green"
    $commands += "Write-Host `"Study location: $studyDir`" -ForegroundColor Yellow"
    
    # Output or save commands
    if ($DryRun) {
        Write-Host "`n--- DRY RUN - No files will be created ---" -ForegroundColor Magenta
        Write-Host "`nGenerated commands preview:" -ForegroundColor Yellow
        $commands[0..10] | ForEach-Object { Write-Host $_ }
        Write-Host "... ($($commands.Count) total lines)" -ForegroundColor Gray
    }
    elseif ($OutputScript) {
        $scriptContent = $commands -join "`r`n"
        Set-Content -Path $OutputScript -Value $scriptContent -Encoding UTF8
        
        Write-Host "`nCommands saved to: $OutputScript" -ForegroundColor Green
        Write-Host "`nTo create the study, run:" -ForegroundColor Yellow
        Write-Host "  ./$OutputScript" -ForegroundColor Cyan
        
        # Also create a batch file for convenience
        $batchFile = [System.IO.Path]::ChangeExtension($OutputScript, ".bat")
        $batchContent = "@echo off`r`npowershell.exe -ExecutionPolicy Bypass -File `"$OutputScript`"`r`npause"
        Set-Content -Path $batchFile -Value $batchContent -Encoding UTF8
        Write-Host "`nBatch file also created: $batchFile" -ForegroundColor Gray
    }
    else {
        Write-Host "`n--- GENERATED COMMANDS ---" -ForegroundColor Yellow
        $commands | ForEach-Object { Write-Host $_ }
        Write-Host "`n--- END OF COMMANDS ---" -ForegroundColor Yellow
        
        Write-Host "`nTip: Use -OutputScript parameter to save these commands to a file" -ForegroundColor Gray
        Write-Host "Example: .\$($MyInvocation.MyCommand.Name) -OutputScript `"create_study.ps1`"" -ForegroundColor Gray
    }
    
    # Display summary
    Write-Host "`n=== Summary ===" -ForegroundColor Cyan
    Write-Host "Study Name: $StudyName" -ForegroundColor White
    Write-Host "Total Experiments: $totalExperiments" -ForegroundColor White
    Write-Host "Factors: $($factors.Count)" -ForegroundColor White
    
    if ($OutputScript -and -not $DryRun) {
        Write-Host "`nNext steps:" -ForegroundColor Yellow
        Write-Host "1. Review the generated script: $OutputScript" -ForegroundColor White
        Write-Host "2. Modify any commands if needed" -ForegroundColor White
        Write-Host "3. Run the script to create your factorial study" -ForegroundColor White
        Write-Host "4. Use audit_study.ps1 to validate the created study" -ForegroundColor White
    }
}
catch {
    Write-Host "`n[ERROR] $_" -ForegroundColor Red
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    exit 1
}

# === End of generate_factorial_commands.ps1 ===
