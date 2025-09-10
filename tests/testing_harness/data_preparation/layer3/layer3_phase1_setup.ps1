#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 1: Automated Setup ---

function Get-ProjectRoot {
    param($StartPath)
    $currentDir = $StartPath
    while ($currentDir -ne $null -and $currentDir -ne "") {
        if (Test-Path (Join-Path $currentDir "pyproject.toml")) { return $currentDir }
        $currentDir = Split-Path -Parent -Path $currentDir
    }
    throw "FATAL: Could not find project root (pyproject.toml) by searching up from '$StartPath'."
}

$ProjectRoot = Get-ProjectRoot -StartPath $PSScriptRoot
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer3_sandbox"

# --- Cleanup from previous failed runs ---
if (Test-Path $SandboxDir) {
    Write-Host "Cleaning up previous Layer 3 sandbox..."
    try {
        Remove-Item -Path $SandboxDir -Recurse -Force -ErrorAction Stop
    }
    catch {
        Write-Host ""
        Write-Host "FATAL: Failed to clean up the previous test sandbox at '$SandboxDir'." -ForegroundColor Red
        Write-Host "This is likely because a file is locked by another process (e.g., VS Code, terminal, file explorer)."
        Write-Host "Please close any applications that might be using these files and re-run the test." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Original error: $($_.Exception.Message)"

        Write-Host "`n--- Attempting to identify the locking process ---" -ForegroundColor Cyan
        $handleExe = Get-Command handle.exe -ErrorAction SilentlyContinue
        if ($handleExe) {
            Write-Host "Found handle.exe. Querying for open handles in the sandbox directory..."
            try {
                # -accepteula prevents the script from hanging on first run
                $handleOutput = & handle.exe -accepteula -nobanner $SandboxDir 2>&1
                if ($handleOutput -match "No matching handles found.") {
                    Write-Host "  -> handle.exe found no open handles. The lock may be on a parent directory or was just released." -ForegroundColor Yellow
                } else {
                    Write-Host "  -> The following processes have open file handles:" -ForegroundColor Yellow
                    $handleOutput | ForEach-Object { "    $_" }
                }
            } catch {
                Write-Host "  -> An error occurred while running handle.exe: $($_.Exception.Message)" -ForegroundColor Red
            }
        } else {
            Write-Host "Diagnostic tool 'handle.exe' not found in your PATH." -ForegroundColor Yellow
            Write-Host "To automatically identify locking processes, download the Sysinternals Suite from the Microsoft Store."
           Write-Host "  -> Download: https://learn.microsoft.com/en-us/sysinternals/downloads/sysinternals-suite" -ForegroundColor Yellow
        }
        throw "HANDLED_ERROR"
     }
}

# --- Create the test environment ---
New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
New-Item -ItemType Directory -Path $SandboxDir -Force | Out-Null
# Create the complete data scaffolding required by the pipeline scripts
@("data/sources", "data/processed", "data/intermediate", "data/reports", "data/foundational_assets", "data/config") | ForEach-Object {
    New-Item -Path (Join-Path $SandboxDir $_) -ItemType Directory -Force | Out-Null
}

# Copy config files from main project
$mainConfigDir = Join-Path $ProjectRoot "data/config"
$sandboxConfigDir = Join-Path $SandboxDir "data/config"
if (Test-Path $mainConfigDir) {
    Copy-Item "$mainConfigDir/*" $sandboxConfigDir -Force
    Write-Host "Copied config files from main project."
}

# --- Copy and Validate All Foundational Test Assets ---
$testsAssetsDir = Join-Path $ProjectRoot "tests/assets"
$sandboxDataDir = Join-Path $SandboxDir "data"

# This manifest defines validation rules for each static asset.
# - Number only (e.g., 144): Exact line count.
# - Plus suffix (e.g., "160+"): Minimum line count.
# - 'h' character (e.g., "12h"): Skips header row for counting.
$assetManifest = @{
    "data/foundational_assets/country_codes.csv" = "160h+";
    "data/foundational_assets/adb_category_map.csv" = "806h+";
    "data/foundational_assets/point_weights.csv" = "12h";
    "data/foundational_assets/balance_thresholds.csv" = "5h";

}

Write-Host "Copying and validating foundational test assets..."
foreach ($entry in $assetManifest.GetEnumerator()) {
    $relativePath = $entry.Name
    $validationRule = "$($entry.Value)" # Ensure it's a string

    $sourcePath = Join-Path $testsAssetsDir $relativePath
    # The destination path inside the sandbox's 'data' dir should not include the 'data/' prefix from the asset path.
    $destinationRelativePath = $relativePath -replace '^data[\\/]'
    $destinationPath = Join-Path $sandboxDataDir $destinationRelativePath

    if (-not (Test-Path $sourcePath)) { throw "FATAL: Required test asset not found at '$sourcePath'." }

    New-Item -Path (Split-Path $destinationPath) -ItemType Directory -Force | Out-Null
    Copy-Item $sourcePath $destinationPath -Force
    
    # --- Validation Logic ---
    $fileContent = Get-Content $destinationPath
    $actualLineCount = $fileContent.Count
    $skipHeader = $false
    if ($validationRule -match "h") {
        $skipHeader = $true
        $validationRule = $validationRule -replace 'h'
        if ($actualLineCount -gt 0) {
            $actualLineCount-- # Decrement count for header
        }
    }

    $isValid = $false
    $errorMessage = ""
    $countType = if ($skipHeader) { "data lines" } else { "lines" }
    
    if ($validationRule -match "\+$") { # Minimum
        $targetCount = [int]($validationRule -replace '\+')
        if ($actualLineCount -ge $targetCount) { $isValid = $true }
        $errorMessage = "Expected at least $targetCount $countType, but found $actualLineCount."
    } else { # Exact
        $targetCount = [int]$validationRule
        if ($actualLineCount -eq $targetCount) { $isValid = $true }
        $errorMessage = "Expected exactly $targetCount $countType, but found $actualLineCount."
    }

    if (-not $isValid) {
        throw "FATAL: Asset validation failed for '$relativePath'. $errorMessage"
    }
}
Write-Host "  -> Successfully copied and validated $($assetManifest.Count) assets." -ForegroundColor Green

# Remove any stale generated files from previous failed runs to ensure a clean state
$sandboxFoundationalDir = Join-Path $sandboxDataDir "foundational_assets"
$dynamicAssets = @("eminence_scores.csv", "ocean_scores.csv", "eminence_scores_summary.txt")
foreach ($asset in $dynamicAssets) {
    $assetPath = Join-Path $sandboxFoundationalDir $asset
    if (Test-Path $assetPath) { Remove-Item $assetPath -Force; Write-Host "  -> Removed stale generated asset: $asset" -ForegroundColor Yellow }
}

# Create a minimal config.ini file in the sandbox for the test
$configContent = @"
[Study]
# This is a minimal config file for integration testing.
num_replications = 1
"@
Set-Content -Path (Join-Path $SandboxDir "config.ini") -Value $configContent

# Copy other test assets from tests/assets into sandbox
# Copy SF interpretation reports 
$reportsSource = Join-Path $testsAssetsDir "data/sf_reports"
$reportsTarget = Join-Path $SandboxDir "data/sf_reports_test_subjects"
if (Test-Path $reportsSource) {
    New-Item -Path $reportsTarget -ItemType Directory -Force | Out-Null
    Copy-Item "$reportsSource/*" $reportsTarget -Force
    Write-Host "Copied SF interpretation reports from tests/assets."
}

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'." -ForegroundColor Green
Write-Host ""