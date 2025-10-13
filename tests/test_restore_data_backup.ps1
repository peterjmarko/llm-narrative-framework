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
# Filename: tests/test_restore_data_backup.ps1

Write-Host "`nTesting prepare_data.ps1 Backup and Restore Functionality" -ForegroundColor Cyan
Write-Host ("=" * 60)

# Get project root
$testScript = $PSCommandPath
$projectRoot = Split-Path -Parent (Split-Path -Parent $testScript)
$prepDataScript = Join-Path $projectRoot "prepare_data.ps1"

if (-not (Test-Path $prepDataScript)) {
    Write-Host "ERROR: Cannot find prepare_data.ps1 at $prepDataScript" -ForegroundColor Red
    exit 1
}

# Define the test directory path, but don't create or announce it yet
$testDir = Join-Path $projectRoot "temp_test_restore_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

try {
    # 1. Create the directory structure FIRST
    New-Item -ItemType Directory -Path "$testDir/data/sources" -Force | Out-Null
    New-Item -ItemType Directory -Path "$testDir/data/backup" -Force | Out-Null
    
    # 2. NOW that the directory exists, resolve its path and announce it
    $relativeTestDir = (Resolve-Path -Path $testDir -Relative).Replace('\', '/')
    Write-Host "`n1. Creating test environment: $relativeTestDir" -ForegroundColor Yellow

    # Create test file with known content
    $testFile = "$testDir/data/sources/test_adb_raw_export.txt"
    $testContent = "Test Data Line 1`nTest Data Line 2`nTest Data Line 3"
    $testContent | Out-File $testFile -Encoding utf8
    $testFileName = Split-Path -Leaf $testFile
    Write-Host "   Created test file '$testFileName' with 3 lines" -ForegroundColor Green
    
    # Manually create a timestamped backup (simulating what prepare_data.ps1 does)
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Start-Sleep -Seconds 1  # Ensure timestamp is distinct
    $testFileItem = Get-Item $testFile
    $backupFile = Join-Path "$testDir/data/backup" "$($testFileItem.BaseName).$timestamp$($testFileItem.Extension).bak"
    Copy-Item $testFile $backupFile
    Write-Host "   Created backup with timestamp: $timestamp" -ForegroundColor Green
    
    # Delete the original file
    Remove-Item $testFile
    Write-Host "`n2. Deleted original file to simulate data loss" -ForegroundColor Yellow
    
    if (Test-Path $testFile) {
        throw "ERROR: Original file still exists after deletion"
    }
    
    # Now test the actual Restore-Recent-Backup function by calling prepare_data.ps1
    Write-Host "`n3. Calling prepare_data.ps1 -RestoreBackup..." -ForegroundColor Yellow
    
    # Set in current process environment (for child processes)
    $env:PROJECT_SANDBOX_PATH = $testDir
    
    # Call with explicit path parameter
    $result = & $prepDataScript -RestoreBackup -RestoreFromPath $testDir 2>&1
    Write-Host "   Full script output:" -ForegroundColor Cyan
    $result | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
    
    # Check results
    Write-Host "`n4. Verifying restoration..." -ForegroundColor Yellow
    
    if (-not (Test-Path $testFile)) {
        Write-Host "   ✗ FAILED: File was not restored" -ForegroundColor Red
        Write-Host "   Script output:" -ForegroundColor Gray
        $result | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }
        throw "Restore failed"
    }
    
    $restoredContent = Get-Content $testFile -Raw
    if ($restoredContent.Trim() -ne $testContent.Trim()) {
        Write-Host "   ✗ FAILED: Restored content doesn't match original" -ForegroundColor Red
        Write-Host "   Expected: $testContent" -ForegroundColor Gray
        Write-Host "   Got: $restoredContent" -ForegroundColor Gray
        throw "Content mismatch"
    }
    
    Write-Host "   ✓ File successfully restored" -ForegroundColor Green
    Write-Host "   ✓ Content verified (3 lines)" -ForegroundColor Green
    
    # Verify the backup file still exists (should not be deleted)
    if (-not (Test-Path $backupFile)) {
        Write-Host "   ⚠ WARNING: Backup file was deleted (should be preserved)" -ForegroundColor Yellow
    } else {
        Write-Host "   ✓ Backup file preserved" -ForegroundColor Green
    }
    
    Write-Host "`n" + ("=" * 60) -ForegroundColor Green
    Write-Host "ALL TESTS PASSED!" -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green
    
} catch {
    Write-Host "`n" + ("=" * 60) -ForegroundColor Red
    Write-Host "TEST FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ("=" * 60) -ForegroundColor Red
    exit 1
} finally {
    # Cleanup
    Write-Host "`n5. Cleaning up test environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $testDir -ErrorAction SilentlyContinue
    Remove-Item Env:PROJECT_SANDBOX_PATH -ErrorAction SilentlyContinue
    Write-Host "   Cleanup complete`n" -ForegroundColor Green
}

# === End of tests/test_restore_data_backup.ps1 ===
