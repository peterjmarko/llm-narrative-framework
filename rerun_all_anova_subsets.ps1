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
# Filename: rerun_all_anova_subsets.ps1

<#
.SYNOPSIS
    Reruns all existing subset analyses found in anova_subsets/

.DESCRIPTION
    Scans the anova_subsets directory to identify all existing subset analyses
    and reruns each one using analyze_study_subsets.ps1. Useful after updating
    the analysis script to regenerate all plots with new naming conventions.

.PARAMETER StudyDirectory
    Path to study directory

.PARAMETER DryRun
    Show what would be run without actually executing

.EXAMPLE
    .\rerun_all_anova_subsets.ps1 -StudyDirectory "output/studies/publication_run"
    
.EXAMPLE
    .\rerun_all_anova_subsets.ps1 -StudyDirectory "output/studies/publication_run" -DryRun
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$StudyDirectory,
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [switch]$CompileOnly
)

$ErrorActionPreference = "Stop"

# Validate study directory
$subsetsDir = Join-Path $StudyDirectory "anova_subsets"
if (-not (Test-Path $subsetsDir)) {
    Write-Error "Subsets directory not found: $subsetsDir"
    exit 1
}

# Will initialize summary log after displaying banner
$summaryLog = Join-Path $subsetsDir "ANOVA_SUBSETS_SUMMARY.txt"

# Parse subset names to extract filters
# Naming convention examples:
#   1.1_k7_analysis          -> k == 7
#   2.1_claude_k10           -> model contains 'claude' and k == 10
#   3.1_traj_gpt4o_k7        -> mapping_strategy == 'correct' and model contains 'gpt4o' and k == 7
#   4.1_traj_claude_k7       -> mapping_strategy == 'correct' and model contains 'claude' and k == 7

function Parse-SubsetName {
    param([string]$Name)
    
    $filters = @()
    
    # Extract k value
    if ($Name -match '_k(\d+)') {
        $k = $matches[1]
        $filters += "k == $k"
    }
    
    # Check for trajectory (traj) indicator -> correct mapping
    if ($Name -match '_traj_') {
        $filters += "mapping_strategy == 'correct'"
    }
    
    # Extract model keywords
    $modelKeywords = @{
        'claude' = 'anthropic/claude-sonnet-4'
        'llama' = 'meta-llama/llama-3.3-70b-instruct'
        'deepseek' = 'deepseek/deepseek-chat-v3.1'
        'gemini' = 'google/gemini-2.0-flash-lite-001'
        'mistral' = 'mistralai/mistral-large-2411'
        'gpt4o' = 'openai/gpt-4o'
        'qwen' = 'qwen/qwen-2.5-72b-instruct'
    }
    
    foreach ($keyword in $modelKeywords.Keys) {
        if ($Name -match $keyword) {
            $modelName = $modelKeywords[$keyword]
            $filters += "model == '$modelName'"
            break
        }
    }
    
    if ($filters.Count -eq 0) {
        return $null
    }
    
    return ($filters -join ' and ')
}

# Get all subset directories (exclude 'archive' directory)
$subsetDirs = Get-ChildItem -Path $subsetsDir -Directory | Where-Object { $_.Name -ne 'archive' } | Sort-Object Name

if ($subsetDirs.Count -eq 0) {
    Write-Host "No subset directories found in: $subsetsDir" -ForegroundColor Yellow
    exit 0
}

# If CompileOnly mode, skip to log compilation
if ($CompileOnly) {
    Write-Host ""
    Write-Host ("="*80) -ForegroundColor Cyan
    Write-Host ("COMPILING ANALYSIS LOGS".PadLeft(50).PadRight(80)) -ForegroundColor Cyan
    Write-Host ("="*80) -ForegroundColor Cyan
    Write-Host "Found $($subsetDirs.Count) subset(s)" -ForegroundColor Green
    Write-Host ""
    
    $consolidatedLog = Join-Path $subsetsDir "CONSOLIDATED_ANALYSIS_LOG.txt"
    $header = @"
================================================================================
CONSOLIDATED ANOVA SUBSET ANALYSIS LOG
================================================================================
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Study Directory: $StudyDirectory

This file contains all detailed analysis logs from all subset analyses.
Each subset's log is separated by a clear divider.

Total Subsets: $($subsetDirs.Count)
================================================================================

"@
    Set-Content -Path $consolidatedLog -Value $header
    
    foreach ($dir in $subsetDirs) {
        $subsetName = $dir.Name
        $logPath = Join-Path $subsetsDir $subsetName "anova" "STUDY_analysis_log.txt"
        
        if (Test-Path $logPath) {
            $divider = @"

################################################################################
### SUBSET: $subsetName
################################################################################

"@
            Add-Content -Path $consolidatedLog -Value $divider
            $logContent = Get-Content -Path $logPath -Raw
            Add-Content -Path $consolidatedLog -Value $logContent
            Write-Host "  Added: $subsetName" -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    Write-Host "Consolidated log saved to:" -ForegroundColor Green
    Write-Host "  anova_subsets/CONSOLIDATED_ANALYSIS_LOG.txt" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host ("="*80) -ForegroundColor Cyan
Write-Host ("RERUNNING ALL ANOVA SUBSET ANALYSES".PadLeft(52).PadRight(80)) -ForegroundColor Cyan
Write-Host ("="*80) -ForegroundColor Cyan
Write-Host "Study Directory: $StudyDirectory" -ForegroundColor White
Write-Host "Found $($subsetDirs.Count) subset(s) to rerun" -ForegroundColor Green

# Archive existing consolidated summary log
if (Test-Path $summaryLog) {
    $logsArchive = Join-Path $StudyDirectory "anova" "archive"
    New-Item -Path $logsArchive -ItemType Directory -Force | Out-Null
    
    $timestamp = (Get-Item $summaryLog).LastWriteTime.ToString("yyyyMMdd_HHmmss")
    $archiveName = "ANOVA_SUBSETS_SUMMARY_$timestamp.txt"
    Move-Item -Path $summaryLog -Destination (Join-Path $logsArchive $archiveName) -Force
    
    Write-Host "Archived previous summary log to:" -ForegroundColor White
    Write-Host "  anova/archive/$archiveName" -ForegroundColor Cyan
}

# Initialize new consolidated summary log
$summaryContent = @"
================================================================================
ANOVA SUBSETS ANALYSIS SUMMARY
================================================================================
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Study Directory: $StudyDirectory

This file provides a consolidated summary of all subset analyses.
For detailed results, see the individual log files linked below.

================================================================================

"@
Set-Content -Path $summaryLog -Value $summaryContent

Write-Host ""

$successful = 0
$failed = 0
$skipped = 0

foreach ($dir in $subsetDirs) {
    $subsetName = $dir.Name
    $filter = Parse-SubsetName -Name $subsetName
    
    if (-not $filter) {
        Write-Host "[$subsetName] SKIPPED - Could not parse filter from name" -ForegroundColor Yellow
        $skipped++
        continue
    }
    
    Write-Host "`n[$subsetName]" -ForegroundColor Cyan
    
    # Parse and display each factor as a bullet point
    $filterParts = $filter -split ' and '
    foreach ($part in $filterParts) {
        Write-Host "  • $part" -ForegroundColor Gray
    }
    
    if ($DryRun) {
        Write-Host "  Note: Existing files will be archived to anova/archive/" -ForegroundColor Gray
        Write-Host "  Status: [DRY RUN]" -ForegroundColor Yellow
        $successful++
    }
    else {
        try {
            # Run the subset analysis - show archiving messages even in quiet mode
            $archiveMessageShown = $false
            $output = & .\analyze_study_subsets.ps1 -StudyDir $StudyDirectory -Filter $filter -OutputName $subsetName 2>&1 | ForEach-Object {
                if ($_ -match 'Archiving.*file\(s\)' -and -not $archiveMessageShown) {
                    Write-Host "  $_" -ForegroundColor Gray
                    $archiveMessageShown = $true
                }
                elseif ($_ -match 'Previous results moved' -or $_ -match 'Could not archive') {
                    Write-Host "  $_" -ForegroundColor Gray
                }
                $_  # Pass through for error checking
            }
            
            if ($LASTEXITCODE -eq 0) {
                # Append to consolidated summary log
                $detailedLog = Join-Path $subsetsDir $subsetName "anova" "STUDY_analysis_log.txt"
                $relativeLogPath = "$subsetName/anova/STUDY_analysis_log.txt"
                
                # Extract key statistics from the detailed log
                $logSummary = @"

[$subsetName]
Filter: $filter
Detailed Log: $relativeLogPath
Status: ✓ SUCCESS
Analysis Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

"@
                Add-Content -Path $summaryLog -Value $logSummary
                
                Write-Host "  Status: ✓" -ForegroundColor Green
                $successful++
            }
            else {
                # Log failure to consolidated summary
                $logSummary = @"

[$subsetName]
Filter: $filter
Status: ✗ FAILED (exit code: $LASTEXITCODE)
Analysis Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

"@
                Add-Content -Path $summaryLog -Value $logSummary
                
                Write-Host "  Status: ✗ FAILED" -ForegroundColor Red
                $failed++
            }
        }
        catch {
            # Log exception to consolidated summary
            $logSummary = @"

[$subsetName]
Filter: $filter
Status: ✗ FAILED (exception: $($_.Exception.Message))
Analysis Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

"@
            Add-Content -Path $summaryLog -Value $logSummary
            
            Write-Host "  Status: ✗ FAILED" -ForegroundColor Red
            $failed++
        }
    }
}

# Summary
Write-Host ""
Write-Host ("="*80) -ForegroundColor Cyan
Write-Host ("SUMMARY".PadLeft(43).PadRight(80)) -ForegroundColor Cyan
Write-Host ("="*80) -ForegroundColor Cyan
Write-Host "Successful: $successful" -ForegroundColor Green
Write-Host "Failed:     $failed" -ForegroundColor $(if ($failed -gt 0) { 'Red' } else { 'Gray' })
Write-Host "Skipped:    $skipped" -ForegroundColor $(if ($skipped -gt 0) { 'Yellow' } else { 'Gray' })
Write-Host ""

# Finalize consolidated summary log
$finalSummary = @"

================================================================================
FINAL SUMMARY
================================================================================
Total Subsets: $($successful + $failed + $skipped)
Successful: $successful
Failed: $failed
Skipped: $skipped

Completed: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
================================================================================
"@
Add-Content -Path $summaryLog -Value $finalSummary

Write-Host "Consolidated summary saved to:" -ForegroundColor Gray
Write-Host "  anova_subsets/ANOVA_SUBSETS_SUMMARY.txt" -ForegroundColor Cyan

# Concatenate all detailed analysis logs
if (-not $DryRun -and $successful -gt 0) {
    Write-Host ""
    Write-Host "Creating consolidated detailed analysis log..." -ForegroundColor Cyan
    
    $consolidatedLog = Join-Path $subsetsDir "CONSOLIDATED_ANALYSIS_LOG.txt"
    $header = @"
================================================================================
CONSOLIDATED ANOVA SUBSET ANALYSIS LOG
================================================================================
Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
Study Directory: $StudyDirectory

This file contains all detailed analysis logs from all subset analyses.
Each subset's log is separated by a clear divider.

Total Subsets Analyzed: $successful
================================================================================

"@
    Set-Content -Path $consolidatedLog -Value $header
    
    foreach ($dir in $subsetDirs) {
        $subsetName = $dir.Name
        $logPath = Join-Path $subsetsDir $subsetName "anova" "STUDY_analysis_log.txt"
        
        if (Test-Path $logPath) {
            $divider = @"

################################################################################
### SUBSET: $subsetName
################################################################################

"@
            Add-Content -Path $consolidatedLog -Value $divider
            $logContent = Get-Content -Path $logPath -Raw
            Add-Content -Path $consolidatedLog -Value $logContent
        }
    }
    
    Write-Host "Consolidated analysis log saved to:" -ForegroundColor Gray
    Write-Host "  anova_subsets/CONSOLIDATED_ANALYSIS_LOG.txt" -ForegroundColor Cyan
}

Write-Host ""

if ($DryRun) {
    Write-Host "This was a DRY RUN. Use without -DryRun to actually execute." -ForegroundColor Yellow
    Write-Host ""
}

exit $(if ($failed -gt 0) { 1 } else { 0 })

# === End of rerun_all_anova_subsets.ps1 ===
