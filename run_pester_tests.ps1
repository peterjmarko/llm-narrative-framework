# Filename: run_pester_tests.ps1
# This script ensures the correct Pester module is loaded and then invokes tests.

# --- Configuration ---
$TestFilePath = Join-Path (Get-Location).Path 'tests/run_experiment.Tests.ps1'

# --- Load Pester Module ---
Write-Host "Attempting to load Pester module..." -ForegroundColor Cyan
try {
    # Since Pester 3.4.0 is confirmed uninstalled, this should load 5.7.1.
    # We explicitly do not use -RequiredVersion or -FullyQualifiedPath here,
    # as these caused "parameter not found" errors in the PDM context.
    Import-Module Pester -Force -ErrorAction Stop
    Write-Host "Pester module loaded successfully." -ForegroundColor Green
}
catch {
    Write-Error "FATAL: Failed to load Pester module. Error: $($_.Exception.Message)"
    exit 1 # Exit with an error code if Pester can't be loaded
}

# --- Validate Test File Existence ---
if (-not (Test-Path $TestFilePath)) {
    Write-Error "FATAL: Pester test file not found at '$TestFilePath'. Please check the path."
    exit 1
}
Write-Host "Pester test file found: $TestFilePath" -ForegroundColor Green

# --- Invoke Pester Tests ---
Write-Host "Invoking Pester tests..." -ForegroundColor Cyan
try {
    # Using a PesterConfiguration object is the most robust way to invoke tests.
    # It explicitly disables discovery and forces Pester to run only the specified file.
    $pesterConfig = [PesterConfiguration]@{
        Run = @{
            Path = $TestFilePath # Tell Pester exactly which file to run
            Exit = $true         # Make Pester exit with a status code for automation
        }
        Discovery = @{
            # Explicitly disable automatic discovery of any other test files
            ExcludePath = '*'
        }
    }

    # Invoke Pester with the explicit and unambiguous configuration.
    Invoke-Pester -Configuration $pesterConfig
}
catch {
    Write-Error "FATAL: Pester test run encountered an unhandled error: $($_.Exception.Message)"
    exit 1 # Indicate a general failure of the test runner
}