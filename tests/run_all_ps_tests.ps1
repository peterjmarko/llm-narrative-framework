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
# Filename: tests/run_all_ps_tests.ps1

$TestSuites = @(
    "run_experiment.Tests.ps1",
    "audit_experiment.Tests.ps1",
    "update_experiment.Tests.ps1",
    "migrate_experiment.Tests.ps1",
    "analyze_study.Tests.ps1"
)

$allResults = @()

Write-Host "--- Starting All PowerShell Test Suites ---" -ForegroundColor Magenta

# --- Main Execution Loop ---
foreach ($suite in $TestSuites) {
    $suitePath = Join-Path $PSScriptRoot $suite
    Write-Host "`n======================================================" -ForegroundColor Cyan
    Write-Host "  EXECUTING SUITE: $suite" -ForegroundColor Cyan
    Write-Host "======================================================`n" -ForegroundColor Cyan

    # Use Tee-Object to both display the live (colored) output and capture it.
    $capturedOutput = "" # Initialize variable to receive the tee'd output
    pwsh -File $suitePath -ErrorAction SilentlyContinue | Tee-Object -Variable capturedOutput
    $exitCode = $LASTEXITCODE

    # Join the array of lines from Tee-Object into a single string for parsing
    $outputString = $capturedOutput -join "`n"

    # Parse the captured output to get detailed results
    $testsPassed = ($outputString | Select-String "Tests Passed: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) | Select-Object -First 1
    $testsFailed = ($outputString | Select-String "Tests Failed: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) | Select-Object -First 1
    $totalTests  = ($outputString | Select-String "Total Tests: (\d+)" | ForEach-Object { $_.Matches.Groups[1].Value }) | Select-Object -First 1

    $allResults += [PSCustomObject]@{
        TestSuite = $suite
        Status    = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
        Passed    = if ($testsPassed) { [int]$testsPassed } else { 0 }
        Failed    = if ($testsFailed) { [int]$testsFailed } else { 0 }
        Total     = if ($totalTests)  { [int]$totalTests }  else { 0 }
    }
}

# --- Final Consolidated Summary ---
Write-Host "`n--- PowerShell Test Suite Summary ---" -ForegroundColor Cyan

$maxNameLen = ($allResults.TestSuite | ForEach-Object { $_.Length } | Measure-Object -Maximum).Maximum
# Use right-alignment for numeric columns to match Python output
$header = "{0,-$maxNameLen} {1,8} {2,8} {3,8} {4,8}" -f "Test Suite", "Status", "Passed", "Failed", "Total"
Write-Host $header -ForegroundColor Cyan
$divider = "-" * $maxNameLen + " " + "-" * 8 + " " + "-" * 8 + " " + "-" * 8 + " " + "-" * 8
Write-Host $divider -ForegroundColor Cyan

$overallTotalFailures = 0
$overallTotalTests = 0

foreach ($result in $allResults) {
    $statusColor = if ($result.Status -eq "PASS") { "`e[92m" } else { "`e[91m" }
    $resetColor = "`e[0m"
    $statusStr = "$($statusColor)$($result.Status)$($resetColor)"
    # Right-align numeric columns, adjust spacing for colored status
    Write-Host ("{0,-$maxNameLen} {1,-15} {2,8} {3,8} {4,8}" -f $result.TestSuite, $statusStr, $result.Passed, $result.Failed, $result.Total)
    $overallTotalFailures += $result.Failed
    $overallTotalTests += $result.Total
}

# --- Overall Totals ---
Write-Host $divider -ForegroundColor Cyan
$overallPassed = $overallTotalTests - $overallTotalFailures
# Right-align the totals, skip the status column
$summaryStr = "{0,-$maxNameLen} {1,8} {2,8} {3,8} {4,8}" -f "OVERALL TOTALS", "", $overallPassed, $overallTotalFailures, $overallTotalTests
Write-Host $summaryStr -ForegroundColor Cyan
Write-Host ""

# --- Exit with a non-zero code if any suite failed ---
if ($overallTotalFailures -gt 0) {
    Write-Host "One or more test suites failed." -ForegroundColor Red
    exit 1
} else {
    Write-Host "All test suites passed successfully." -ForegroundColor Green
    exit 0
}

# === End of tests/run_all_ps_tests.ps1 ===
