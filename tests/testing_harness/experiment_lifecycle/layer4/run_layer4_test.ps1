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
# Filename: tests/testing_harness/experiment_lifecycle/layer4/run_layer4_test.ps1

param (
    [switch]$SkipCleanup
)

$ErrorActionPreference = "Stop"
$ScriptDir = $PSScriptRoot

try {
    # Phase 1: Setup
    & "$ScriptDir\layer4_phase1_setup.ps1"

    # Phase 2: Run the test workflow
    & "$ScriptDir\layer4_phase2_run.ps1"
}
catch {
    Write-Host "`nFATAL: Layer 4 test run failed." -ForegroundColor Red
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    # Exit with a non-zero status code to fail CI/CD pipelines
    exit 1
}
finally {
    # Phase 3: Cleanup
    if (-not $SkipCleanup) {
        & "$ScriptDir\layer4_phase3_cleanup.ps1"
    } else {
        Write-Host "`nCleanup skipped due to -SkipCleanup flag." -ForegroundColor Yellow
    }
    
    # Final success message (only if we got this far without exceptions)
    if (-not $Error) {
        Write-Host "Layer 4 test completed successfully.`n" -ForegroundColor Green
    }
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/run_layer4_test.ps1 ===
