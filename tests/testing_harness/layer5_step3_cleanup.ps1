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
# Filename: tests/testing_harness/layer5_step3_cleanup.ps1

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$SandboxDir = Join-Path $ProjectRoot "temp_test_environment/layer5_sandbox"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"
$MigratedExperimentsDir = Join-Path $ProjectRoot "output/migrated_experiments"

Write-Host ""
Write-Host "--- Layer 5: Migration Workflow Integration Testing ---" -ForegroundColor Cyan
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $SandboxDir) {
    Write-Host "Removing Layer 5 sandbox directory..."
    Remove-Item -Path $SandboxDir -Recurse -Force
    Write-Host "  -> Done."
} else {
    Write-Host "Layer 5 sandbox directory not found. Nothing to remove."
}

$corruptedExp = Get-ChildItem -Path $NewExperimentsDir -Directory "l5_test_exp_*" -ErrorAction SilentlyContinue
if ($corruptedExp) {
    Write-Host "Removing corrupted test experiment..."
    $corruptedExp | Remove-Item -Recurse -Force
    Write-Host "  -> Done."
}

$migratedExp = Get-ChildItem -Path $MigratedExperimentsDir -Directory "l5_test_exp_*" -ErrorAction SilentlyContinue
if ($migratedExp) {
    Write-Host "Removing migrated test experiment..."
    $migratedExp | Remove-Item -Recurse -Force
    Write-Host "  -> Done."
}

Write-Host "`nCleanup complete." -ForegroundColor Green

# === End of tests/testing_harness/layer5_step3_cleanup.ps1 ===
