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
# Filename: tests/testing_harness/layer4_step3_cleanup.ps1

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer4_sandbox"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"

Write-Host ""
Write-Host "--- Layer 4: Main Workflow Integration Testing ---" -ForegroundColor Cyan
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    Write-Host "Removing Layer 4 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "Layer 4 sandbox directory not found. Nothing to remove."
}

$testExperiments = Get-ChildItem -Path $NewExperimentsDir -Directory "experiment_*" -ErrorAction SilentlyContinue
if ($testExperiments) {
    Write-Host "Removing temporary experiment directories from 'output/new_experiments'..."
    $testExperiments | Remove-Item -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "No temporary experiment directories found. Nothing to remove."
}

Write-Host "`nCleanup complete." -ForegroundColor Green

# === End of tests/testing_harness/layer4_step3_cleanup.ps1 ===
