#!/usr/bin/env pwsh
# --- Layer 4: Main Workflow Integration Testing ---
# --- Step 1: Automated Setup ---

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer4_sandbox"
$TestConfigPath = Join-Path $SandboxDir "config.ini"
$TestDbPath = Join-Path $SandboxDir "personalities_db.txt"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"

# --- Cleanup from previous failed runs ---
if (Test-Path $SandboxDir) {
    Write-Host "Cleaning up previous Layer 4 sandbox..."
    Remove-Item -Path $SandboxDir -Recurse -Force
}
$testExperiments = Get-ChildItem -Path $NewExperimentsDir -Directory "experiment_*" -ErrorAction SilentlyContinue
if ($testExperiments) {
    Write-Host "Cleaning up leftover test experiments from 'output/new_experiments'..."
    $testExperiments | Remove-Item -Recurse -Force
}

# --- Create the test environment ---
New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
New-Item -ItemType Directory -Path $SandboxDir -Force | Out-Null

# --- Create a minimal, test-specific personalities database ---
$dbContent = @"
1,Biography 1,Personality Text 1
2,Biography 2,Personality Text 2
3,Biography 3,Personality Text 3
4,Biography 4,Personality Text 4
"@
$dbContent | Set-Content -Path $TestDbPath -Encoding UTF8

# --- Create a minimal, test-specific config.ini ---
# IMPORTANT: The personalities_db_file path must be relative to the project root.
$configContent = @"
[Study]
num_replications = 1
num_trials = 2
group_size = 4
mapping_strategy = random

[LLM]
model_name = google/gemini-flash-1.5
temperature = 0.2

[Filenames]
personalities_db_file = $($TestDbPath -replace [regex]::Escape($ProjectRoot + "\"), "" -replace "\\", "/")
"@
$configContent | Set-Content -Path $TestConfigPath -Encoding UTF8

Write-Host ""
Write-Host "--- Layer 4: Main Workflow Integration Testing ---" -ForegroundColor Cyan
Write-Host "--- Step 1: Automated Setup ---" -ForegroundColor Cyan
Write-Host ""
Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'."
Write-Host "Your next action is Step 2: Execute the Test Workflow."