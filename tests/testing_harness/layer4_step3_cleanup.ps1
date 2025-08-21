function Get-ProjectRoot {
    $currentDir = Get-Location
    while ($currentDir -ne $null -and $currentDir.Path -ne "") {
        if (Test-Path (Join-Path $currentDir.Path "pyproject.toml")) { return $currentDir.Path }
        $currentDir = Split-Path -Parent -Path $currentDir.Path
    }
    throw "FATAL: Could not find project root (pyproject.toml)."
}

$ProjectRoot = Get-ProjectRoot
Set-Location $ProjectRoot

Write-Host ""
Write-Host "--- Layer 4: Main Workflow Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan

# Read the target directory path from the state file created by Step 2.
$stateFilePath = Join-Path $ProjectRoot "tests/testing_harness/.l4_test_dir.txt"
if (-not (Test-Path $stateFilePath)) {
    Write-Host ""
    Write-Host "FATAL: State file '.l4_test_dir.txt' not found." -ForegroundColor Red
    Write-Host "Please run Step 2 (layer4_step2_test_workflow.ps1) first to generate the test data." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
$expDirPaths = Get-Content -Path $stateFilePath

Write-Host "Cleaning up test artifacts..." -ForegroundColor Yellow

# Loop through all experiment directories created during this test session and remove them.
foreach ($expDirPath in $expDirPaths) {
    $relativeExpDir = Resolve-Path -Path $expDirPath -Relative -ErrorAction SilentlyContinue
    if (Test-Path $expDirPath -PathType Container) {
        Write-Host "Removing test experiment directory: $relativeExpDir"
        Remove-Item -Path $expDirPath -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Write-Warning "Test experiment directory not found at path: $relativeExpDir. It may have been deleted already."
    }
}

# Clean up other test artifacts from the project root
Remove-Item -Path "config.ini" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "data/personalities_db.txt" -Force -ErrorAction SilentlyContinue

# Restore original files from the latest backups using a non-destructive COPY
$latestConfigBackup = Get-ChildItem -Path "test_backups" -Filter "config.ini.*.bak" | Sort-Object Name -Descending | Select-Object -First 1
if ($latestConfigBackup) {
    Write-Host "Restoring original config.ini from $($latestConfigBackup.Name)"
    Copy-Item -Path $latestConfigBackup.FullName -Destination "config.ini" -Force
}
$latestDbBackup = Get-ChildItem -Path "test_backups" -Filter "personalities_db.txt.*.bak" | Sort-Object Name -Descending | Select-Object -First 1
if ($latestDbBackup) {
    Write-Host "Restoring original personalities_db.txt from $($latestDbBackup.Name)"
    Copy-Item -Path $latestDbBackup.FullName -Destination "data/personalities_db.txt" -Force
}

Write-Host "`nMain workflow test environment cleaned up." -ForegroundColor Green
Write-Host "The 'test_backups' directory still contains all backups for safety. You can delete it manually when ready." -ForegroundColor Yellow
# Final cleanup: remove the state file itself.
Remove-Item $stateFilePath -Force

Write-Host "This completes Step 3 of Layer 4 (Automated Cleanup). End-to-End Integration Testing of the Main Experiment Workflows is complete." -ForegroundColor Green
Write-Host ""