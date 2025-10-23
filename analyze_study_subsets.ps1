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
# Filename: analyze_study_subsets.ps1

<#
.SYNOPSIS
    Simple wrapper for flexible subset analysis using existing analyze_study_results.py

.DESCRIPTION
    Creates filtered subsets of STUDY_results.csv and runs the existing
    analyze_study_results.py script on them. No new Python code needed.
    
    Interactive mode is DEFAULT when no filter is provided.

.PARAMETER StudyDir
    Path to study directory containing STUDY_results.csv

.PARAMETER Filter
    Pandas query string to filter data
    Example: "k == 10"
    Example: "model == 'anthropic_claude_sonnet_4' and k == 14"

.PARAMETER OutputName
    Name for the output subdirectory (default: auto-generated)

.EXAMPLE
    .\analyze_study_subsets.ps1
    Interactive mode (default) - guided filter builder
    
.EXAMPLE
    .\analyze_study_subsets.ps1 -Filter "k == 10"
    Direct filter mode
    
.EXAMPLE
    .\analyze_study_subsets.ps1 -StudyDir "output/studies/publication_run" -Filter "model == 'anthropic_claude_sonnet_4'"

.EXAMPLE
    .\analyze_study_subsets.ps1 -Filter "k == 10" -OutputName "k10_analysis"
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$StudyDir = "output/studies/publication_run",
    
    [Parameter(Mandatory=$false)]
    [string]$Filter,
    
    [Parameter(Mandatory=$false)]
    [string]$OutputName
)

$ErrorActionPreference = "Stop"

# Validate study directory
$masterCsv = Join-Path $StudyDir "STUDY_results.csv"
if (-not (Test-Path $masterCsv)) {
    Write-Error "Master CSV not found: $masterCsv"
    exit 1
}

# Default to interactive mode if no filter provided
$Interactive = [string]::IsNullOrWhiteSpace($Filter)

# Interactive filter builder
if ($Interactive) {
    Write-Host "`nInteractive Filter Builder" -ForegroundColor Cyan
    Write-Host "="*50
    
    Write-Host "`nAvailable factors:" -ForegroundColor Yellow
    Write-Host "  1. model"
    Write-Host "  2. mapping_strategy"
    Write-Host "  3. k"
    Write-Host "  4. Custom filter"
    Write-Host ""
    Write-Host "Select factor to filter by [1-4]: " -NoNewline
    $choice = Read-Host
    
    switch ($choice) {
        '1' {
            Write-Host "`nAvailable models:" -ForegroundColor Yellow
            Write-Host "  1. anthropic_claude_sonnet_4"
            Write-Host "  2. meta_llama_3_3_70b"
            Write-Host "  3. deepseek_v3"
            Write-Host "  4. google_gemini_2_0_flash"
            Write-Host "  5. mistralai_mistral_large_2411"
            Write-Host "  6. openai_gpt_4o"
            Write-Host "  7. qwen_qwen_2_5_72b_instruct"
            Write-Host ""
            Write-Host "Select model [1-7]: " -NoNewline
            $modelChoice = Read-Host
            
            $models = @('anthropic_claude_sonnet_4', 'meta_llama_3_3_70b', 'deepseek_v3', 
                       'google_gemini_2_0_flash', 'mistralai_mistral_large_2411', 
                       'openai_gpt_4o', 'qwen_qwen_2_5_72b_instruct')
            $selectedModel = $models[[int]$modelChoice - 1]
            $Filter = "model == '$selectedModel'"
        }
        '2' {
            Write-Host "`nSelect mapping_strategy:" -ForegroundColor Yellow
            Write-Host "  1. correct"
            Write-Host "  2. random"
            Write-Host ""
            Write-Host "Select [1-2]: " -NoNewline
            $mpsChoice = Read-Host
            $mps = if ($mpsChoice -eq '1') { 'correct' } else { 'random' }
            $Filter = "mapping_strategy == '$mps'"
        }
        '3' {
            Write-Host "`nSelect k value:" -ForegroundColor Yellow
            Write-Host "  1. k=7"
            Write-Host "  2. k=10"
            Write-Host "  3. k=14"
            Write-Host ""
            Write-Host "Select [1-3]: " -NoNewline
            $kChoice = Read-Host
            $k = @(7, 10, 14)[[int]$kChoice - 1]
            $Filter = "k == $k"
        }
        '4' {
            Write-Host "`nEnter custom pandas query filter:" -ForegroundColor Yellow
            Write-Host "Examples:" -ForegroundColor Gray
            Write-Host "  k == 10 and model == 'anthropic_claude_sonnet_4'"
            Write-Host "  model.isin(['anthropic_claude_sonnet_4', 'meta_llama_3_3_70b'])"
            Write-Host "  k >= 10 and mapping_strategy == 'correct'"
            Write-Host ""
            Write-Host "Filter: " -NoNewline
            $Filter = Read-Host
        }
    }
    
    # Ask for additional filters
    Write-Host "`nAdd another filter condition? [y/N]: " -NoNewline
    $addMore = Read-Host
    if ($addMore -eq 'y' -or $addMore -eq 'Y') {
        Write-Host "Enter additional condition (will be AND'd): " -NoNewline
        $additional = Read-Host
        $Filter = "($Filter) and ($additional)"
    }
}

# After interactive mode or if filter was provided
if ([string]::IsNullOrWhiteSpace($Filter)) {
    Write-Error "No filter was created or provided"
    exit 1
}

# Generate output name if not provided
if ([string]::IsNullOrWhiteSpace($OutputName)) {
    $OutputName = "filtered_" + (Get-Date -Format 'yyyyMMdd_HHmmss')
}

$outputDir = Join-Path $StudyDir "anova_subsets" $OutputName

Write-Host "`n================================================" -ForegroundColor Cyan
Write-Host "Flexible Subset Analysis" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Study:       $StudyDir" -ForegroundColor White
Write-Host "Filter:      $Filter" -ForegroundColor Yellow
Write-Host "Output:      $outputDir" -ForegroundColor Green
Write-Host ""

# Create output directory
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$anovaDir = Join-Path $outputDir "anova"
New-Item -ItemType Directory -Path $anovaDir -Force | Out-Null

# Filter data using Python
Write-Host "Filtering data..." -NoNewline

$filterScript = @"
import pandas as pd
import sys

try:
    df = pd.read_csv(r'$masterCsv')
    print(f'\nLoaded: {len(df)} observations', file=sys.stderr)
    
    filtered = df.query('$Filter')
    print(f'Filtered to: {len(filtered)} observations ({len(filtered)/len(df)*100:.1f}%)', file=sys.stderr)
    
    if len(filtered) == 0:
        print('ERROR: Filter resulted in empty dataset', file=sys.stderr)
        sys.exit(1)
    
    # Show summary
    print('\nFactors in filtered data:', file=sys.stderr)
    for factor in ['model', 'mapping_strategy', 'k', 'm']:
        if factor in filtered.columns:
            unique = sorted(filtered[factor].unique())
            print(f'  {factor}: {len(unique)} levels - {unique}', file=sys.stderr)
    
    # Save filtered data
    output_csv = r'$outputDir\STUDY_results.csv'
    filtered.to_csv(output_csv, index=False)
    print(f'\nSaved to: {output_csv}', file=sys.stderr)
    
except Exception as e:
    print(f'ERROR: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
"@

# Execute Python script
$filterScript | pdm run python -

if ($LASTEXITCODE -ne 0) {
    Write-Host " FAILED" -ForegroundColor Red
    Write-Host "`nPython execution failed. Check that the PDM environment is set up:" -ForegroundColor Yellow
    Write-Host "  pdm install" -ForegroundColor Gray
    Write-Host "  pdm run python --version" -ForegroundColor Gray
    exit 1
}

Write-Host " Done" -ForegroundColor Green
Write-Host ""

# Create metadata file
$metadataFile = Join-Path $outputDir "subset_metadata.txt"
@"
Subset Analysis
===============

Filter Applied: $Filter
Source Study: $StudyDir
Master CSV: $masterCsv
Created: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

Output Directory: $outputDir
Results: $anovaDir\STUDY_analysis_log.txt
"@ | Set-Content $metadataFile

# Run existing analyze_study_results.py
Write-Host "Running analyze_study_results.py..." -ForegroundColor Cyan
Write-Host ""

pdm run python src/analyze_study_results.py $outputDir

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Green
    Write-Host "Analysis Complete" -ForegroundColor Green
    Write-Host "================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Results saved to:" -ForegroundColor White
    Write-Host "  $anovaDir\STUDY_analysis_log.txt" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Boxplots:" -ForegroundColor White
    Write-Host "  $anovaDir\boxplots\" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "Analysis failed - check output above" -ForegroundColor Red
    exit 1
}

# === End of analyze_study_subsets.ps1 ===
