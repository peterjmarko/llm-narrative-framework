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
# Filename: tests/testing_harness/experiment_lifecycle/layer4/layer4_phase1_setup.ps1

param(
    [switch]$Interactive
)

# --- Define ANSI Color Codes ---
$C_RESET = "`e[0m"
$C_ORANGE = "`e[38;5;208m"
$C_GREEN = "`e[92m"
$C_CYAN = "`e[96m"
$C_YELLOW = "`e[93m"
$C_MAGENTA = "`e[95m"

$ProjectRoot = $PSScriptRoot | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent | Split-Path -Parent
$TestEnvRoot = Join-Path $ProjectRoot "temp_test_environment"
$SandboxDir = Join-Path $TestEnvRoot "layer4_sandbox"
$SandboxDataDir = Join-Path $SandboxDir "data"
$TestConfigPath = Join-Path $SandboxDir "config.ini"
$TestDbPath = Join-Path $SandboxDataDir "personalities_db.txt"
$NewExperimentsDir = Join-Path $ProjectRoot "output/new_experiments"

try {
    if ($Interactive) {
        Write-Host "Setting up the test environment..." -ForegroundColor White
    }

    # --- Cleanup from previous failed runs ---
    if (Test-Path $SandboxDir) {
        if ($Interactive) {
            Write-Host "Cleaning up previous Layer 4 sandbox..." -ForegroundColor Yellow
        } else {
            Write-Host "`nCleaning up previous Layer 4 sandbox..." -ForegroundColor Yellow
        }
        Remove-Item -Path $SandboxDir -Recurse -Force
    }
    # Note: The test will create an experiment in the production 'output/new_experiments' directory.
    # This is intentional to test the real workflow, and the experiment will be preserved.

    # --- Create the test environment ---
    New-Item -ItemType Directory -Path $TestEnvRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $SandboxDataDir -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $SandboxDir "output/new_experiments") -Force | Out-Null

    # --- Create a minimal, test-specific personalities database ---
$dbContent = @"
Index	idADB	Name	BirthYear	DescriptionText
1	1001	Test Person 1	1980	Personality description for test person 1
2	1002	Test Person 2	1985	Personality description for test person 2
3	1003	Test Person 3	1990	Personality description for test person 3
4	1004	Test Person 4	1995	Personality description for test person 4
5	1005	Test Person 5	1975	Personality description for test person 5
6	1006	Test Person 6	1988	Personality description for test person 6
7	1007	Test Person 7	1992	Personality description for test person 7
8	1008	Test Person 8	1987	Personality description for test person 8
9	1009	Test Person 9	1983	Personality description for test person 9
10	1010	Test Person 10	1991	Personality description for test person 10
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
max_parallel_sessions = 10

[General]
base_output_dir = output
new_experiments_subdir = new_experiments
experiment_dir_prefix = experiment_
default_log_level = INFO

[Filenames]
personalities_src = $("../" + ($TestDbPath -replace [regex]::Escape($ProjectRoot + "\"), "" -replace "\\", "/"))

[Schema]
csv_header_order = run_directory,replication,n_valid_responses,model,mapping_strategy,temperature,k,m,db,mean_mrr,mrr_p,mean_top_1_acc,top_1_acc_p,mean_top_3_acc,top_3_acc_p,mean_mrr_lift,mean_top_1_acc_lift,mean_top_3_acc_lift,mean_rank_of_correct_id,rank_of_correct_id_p,top1_pred_bias_std,true_false_score_diff,bias_slope,bias_intercept,bias_r_value,bias_p_value,bias_std_err
"@
$configContent.Trim() | Set-Content -Path $TestConfigPath -Encoding UTF8

if ($Interactive) {
        Write-Host ""
        Write-Host "--- Layer 4: Experiment Lifecycle Integration Testing ---" -ForegroundColor Magenta
        Write-Host "--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'." -ForegroundColor Green
        Write-Host ""
        Write-Host "Setup components created:" -ForegroundColor White
        Write-Host "  ✓ Isolated test sandbox" -ForegroundColor Green
        Write-Host "  ✓ Minimal test database (10 subjects)" -ForegroundColor Green
        Write-Host "  ✓ Test configuration (1 replication, 2 trials)" -ForegroundColor Green
        Write-Host "  ✓ Safe experiment output directory" -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host "--- Layer 4: Experiment Lifecycle Integration Testing ---" -ForegroundColor Magenta
        Write-Host "--- Phase 1: Automated Setup ---" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "Integration test sandbox created successfully in '$((Resolve-Path $SandboxDir -Relative).TrimStart(".\"))'." -ForegroundColor Green
    }

}
catch {
    Write-Host "`nERROR: Layer 4 setup script failed.`n$($_.Exception.Message)" -ForegroundColor Red
    # Re-throw the original exception to the master runner.
    throw
}

# === End of tests/testing_harness/experiment_lifecycle/layer4/layer4_phase1_setup.ps1 ===
