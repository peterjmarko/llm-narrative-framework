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
# Filename: tests/testing_harness/experiment_lifecycle/layer5/run_layer5_test.ps1

param (
    [switch]$SkipCleanup
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

Write-Host "--- Starting Layer 5: Migration Workflow Test ---" -ForegroundColor Yellow

try {
    # Phase 1: Setup
    & "$ScriptDir\layer5_phase1_setup.ps1"

    # Phase 2: Run the test workflow
    & "$ScriptDir\layer5_phase2_run.ps1"

    Write-Host "`nLayer 5 test completed successfully." -ForegroundColor Green
}
catch {
    Write-Host "`nFATAL: Layer 5 test run failed." -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    # Exit with a non-zero status code to fail CI/CD pipelines
    exit 1
}
finally {
    # Phase 3: Cleanup
    if (-not $SkipCleanup) {
        & "$ScriptDir\layer5_phase3_cleanup.ps1"
    } else {
        Write-Host "`nCleanup skipped due to -SkipCleanup flag." -ForegroundColor Yellow
    }
}

# === End of tests/testing_harness/experiment_lifecycle/layer5/run_layer5_test.ps1 ===
