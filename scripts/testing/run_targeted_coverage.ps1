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
# Filename: scripts/testing/run_targeted_coverage.ps1

param (
    [Parameter(Mandatory=$true, Position=0)]
    [string]$TestFilePath
)

# Validate that the input path points to a test file.
if (-not ($TestFilePath -like 'tests/*' -or $TestFilePath -like 'tests\*')) {
    Write-Error "Invalid input: This script requires the path to a test file (e.g., 'tests/utils/test_file_utils.py'), not a source file."
    exit 1
}

# Derive the source file path from the test file path.
# Assumes standard project structure:
# tests/utils/test_file_utils.py -> src/utils/file_utils.py
$SourceFilePath = $TestFilePath -replace '^tests[\\/]', 'src/' -replace 'test_', ''

Write-Host "--> Running tests for: $TestFilePath"
pdm run test-cov $TestFilePath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Test run failed. Aborting coverage report."
    exit $LASTEXITCODE
}

Write-Host "--> Generating coverage report for: $SourceFilePath"
pdm run report-cov $SourceFilePath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Coverage report generation failed."
    exit $LASTEXITCODE
}

Write-Host "[OK] Targeted coverage report complete."

# === End of scripts/testing/run_targeted_coverage.ps1 ===
