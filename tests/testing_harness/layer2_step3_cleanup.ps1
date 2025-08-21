# Filename: tests/testing_harness/layer2_step3_cleanup.ps1
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
Write-Host "--- Layer 2: Data Pipeline Orchestration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan

Remove-Item -Path "temp_mock_test" -Recurse -Force
Write-Host "`nMock test environment cleaned up successfully." -ForegroundColor Green
Write-Host ""