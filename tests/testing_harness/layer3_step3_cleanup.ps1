# Filename: tests/testing_harness/layer3_step3_cleanup.ps1
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
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 3: Automated Cleanup ---" -ForegroundColor Cyan

Remove-Item -Path "temp_integration_test" -Recurse -Force
Write-Host "`nIntegration test environment cleaned up successfully." -ForegroundColor Green
Write-Host ""