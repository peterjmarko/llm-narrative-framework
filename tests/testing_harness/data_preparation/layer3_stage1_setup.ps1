#!/usr/bin/env pwsh
# --- Layer 3: Data Pipeline Integration Testing ---
# --- Step 1: Automated Setup ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer3_sandbox"

# --- Cleanup from previous failed runs ---
if (Test-Path $SandboxDir) {
    Write-Host "Cleaning up previous Layer 3 sandbox..."
    Remove-Item -Path $SandboxDir -Recurse -Force
}

# --- Create the test environment ---
New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
New-Item -ItemType Directory -Path $SandboxDir -Force | Out-Null
# Create the complete data scaffolding required by the pipeline scripts
@("data/sources", "data/processed", "data/intermediate", "data/reports", "data/foundational_assets") | ForEach-Object {
    New-Item -Path (Join-Path $SandboxDir $_) -ItemType Directory -Force | Out-Null
}

Write-Host ""
Write-Host "--- Layer 3: Data Pipeline Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Stage 1: Automated Setup ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'." -ForegroundColor Green
Write-Host "Your next action is Stage 2: Execute the Test Workflow." -ForegroundColor Yellow
Write-Host ""