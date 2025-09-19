#!/usr/bin/env pwsh
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: tests/testing_harness/validate_query_generation.ps1

<#
.SYNOPSIS
    Core Algorithm Validation Test for Query Generation.

.DESCRIPTION
    This script provides a standalone validation test for the query_generator.py
    script. It generates a large sample of trial manifests for both 'correct' and
    'random' mapping strategies and then runs a Python analyzer to perform a
    statistical validation of the output.

    - The 'correct' strategy is validated for determinism.
    - The 'random' strategy is validated for non-determinism, approximating a
      uniform distribution.

    This test runs in an isolated sandbox and is non-destructive.
#>
param(
    [double]$Beta = 0.000001 # Acceptable Type II error rate (default: 0.0001%)
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$projectRoot = Resolve-Path (Join-Path $scriptRoot "..\..")

# --- Test Configuration ---
$sandboxDir = Join-Path $projectRoot "temp_test_environment"
$assetsDir = Join-Path $projectRoot "tests\assets\query_gen_seed"
$manifestOutputDir = Join-Path $sandboxDir "manifest_output"
$groupSize = 3 # Fixed based on the test asset data

# --- Calculate Required Iterations for Statistical Power ---
# H₀: The 'random' strategy is deterministic. We reject H₀ if we see > 1 unique output.
# A Type II error (β) occurs if the strategy is truly random but produces the
# same output N times in a row by chance. We calculate N to make this chance β.
# Formula: N = 1 - (ln(β) / ln(k!))
Function Factorial ([int]$n) {
    if ($n -le 1) { return 1 }
    return $n * (Factorial ($n - 1))
}
$kFactorial = Factorial $groupSize
$NumIterations = [int][Math]::Ceiling(1 - ([Math]::Log($Beta) / [Math]::Log($kFactorial)))
$Power = (1 - $Beta) * 100

# --- Main ---
# Set UTF-8 encoding to prevent PDM's TOML parser from crashing.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"

$originalLocation = Get-Location

# --- Helper Function for Custom Progress Bar ---
Function Update-CustomProgress {
    param(
        [int]$Current,
        [int]$Total,
        [datetime]$StartTime
    )
    $elapsed = (Get-Date) - $StartTime
    $elapsedStr = $elapsed.ToString("mm\:ss")

    $etaStr = "..."
    if ($Current -gt 0 -and $Current -lt $Total) {
        $avgTimePerItem = $elapsed.TotalSeconds / $Current
        $remainingItems = $Total - $Current
        $etaSeconds = $remainingItems * $avgTimePerItem
        $etaStr = [timespan]::FromSeconds($etaSeconds).ToString("mm\:ss")
    } elseif ($Current -eq $Total) {
        $etaStr = "00:00"
    }

    $percent = if ($Total -gt 0) { [int](($Current / $Total) * 100) } else { 100 }
    $countStr = "[{0,3}/{1,-3}]" -f $Current, $Total
    $timeStr = "Elapsed: {0} | ETA: {1}" -f $elapsedStr, $etaStr

    # Use Unicode block characters for a cleaner progress bar
    $barWidth = 25
    $filledChars = [int](($Current / $Total) * $barWidth)
    $emptyChars = $barWidth - $filledChars
    $progressBar = "[{0}{1}]" -f ('█' * $filledChars), ('░' * $emptyChars)

    $fullLine = "`rGenerating Manifests {0} {1}% {2} {3}" -f $countStr, $percent, $progressBar, $timeStr
    $paddedLine = $fullLine.PadRight(80)

    Write-Host -NoNewline $paddedLine
}

$originalLocation = Get-Location

try {
    Write-Host ""
    Write-Host "--- VALIDATING QUERY GENERATION ALGORITHM ---" -ForegroundColor Yellow
    Write-Host "STATISTICAL RIGOR: To achieve $($Power)% power (β = $Beta) for k=$($groupSize), the test will run $NumIterations iterations." -ForegroundColor Magenta

    # --- STAGE 1: SETUP ---
    Write-Host "`n--- STAGE 1: Preparing Test Sandbox ---`n" -ForegroundColor Cyan
    if (Test-Path $sandboxDir) { Remove-Item -Recurse -Force $sandboxDir }
    New-Item -ItemType Directory -Path $sandboxDir | Out-Null
    Copy-Item -Path (Join-Path $assetsDir "personalities_db.txt") -Destination $sandboxDir

    $pythonWriteDir = Join-Path $projectRoot "output/qgen_standalone_output"
    if (Test-Path $pythonWriteDir) {
        Remove-Item -Recurse -Force $pythonWriteDir
    }

    # --- STAGE 2: GENERATION ---
    Write-Host "--- STAGE 2: Generating $NumIterations Manifest Sets ---" -ForegroundColor Cyan
    $startTime = Get-Date
    try {
        foreach ($i in 1..$NumIterations) {
            Update-CustomProgress -Current $i -Total $NumIterations -StartTime $startTime

            $inputFile = Join-Path $sandboxDir "personalities_db.txt"
            $baseArgs = @("python", "-m", "src.query_generator", "-k", $groupSize, "--personalities_file", $inputFile)
            $deterministicSeed = 42

            $correctPrefix = "trial_correct_$($i)_"
            $correctArgs = $baseArgs + @("--mapping_strategy", "correct", "--output_basename_prefix", $correctPrefix, "--seed", $deterministicSeed)
            pdm run --project $projectRoot -- $correctArgs 2>$null

            $randomPrefix = "trial_random_$($i)_"
            $randomArgs = $baseArgs + @("--mapping_strategy", "random", "--output_basename_prefix", $randomPrefix, "--seed", $i)
            pdm run --project $projectRoot -- $randomArgs 2>$null
        }
    }
    catch [System.Management.Automation.PipelineStoppedException] {
        Write-Host "" # Move to next line after progress bar
        throw
    }
    finally {
        # Ensure the progress bar is always finalized
        if ($LASTEXITCODE -eq 0) {
             Update-CustomProgress -Current $NumIterations -Total $NumIterations -StartTime $startTime
        }
        Write-Host "" # Final newline after progress bar
    }

    # --- STAGE 3: ANALYSIS ---
    Write-Host "`n--- STAGE 3: Analyzing Results ---" -ForegroundColor Cyan
    $analyzerScript = Join-Path $projectRoot "tests/testing_harness/analyzers/analyze_query_generation_results.py"
    pdm run --project $projectRoot python $analyzerScript --manifest-dir $pythonWriteDir
    if ($LASTEXITCODE -ne 0) {
        throw "The Python analyzer script reported a failure."
    }
}
catch [System.Management.Automation.PipelineStoppedException] {
    Write-Host "`nOperation cancelled by user." -ForegroundColor Yellow
}
catch {
    Write-Host "`nERROR: Test failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
finally {
    # --- STAGE 4: CLEANUP ---
    Write-Host "`n--- STAGE 4: Cleaning Up Sandbox ---" -ForegroundColor Cyan
    Set-Location $originalLocation
    if (Test-Path $sandboxDir) { Remove-Item -Recurse -Force $sandboxDir }
    $pythonWriteDir = Join-Path $projectRoot "output/qgen_standalone_output"
    if (Test-Path $pythonWriteDir) { Remove-Item -Recurse -Force $pythonWriteDir }

    # Final success/failure message
    Write-Host ""
    if ($?) { # Checks if the last command in the try block was successful
        Write-Host "✅ OVERALL RESULT: SUCCESS" -ForegroundColor Green
    } else {
        Write-Host "❌ OVERALL RESULT: FAILED" -ForegroundColor Red
    }
    Write-Host ""
}

# === End of tests/testing_harness/validate_query_generation.ps1 ===
