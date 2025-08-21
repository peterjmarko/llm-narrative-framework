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

# Ensure any state file from a previous test run is deleted.
$stateFilePath = Join-Path $ProjectRoot "scripts/testing_harness/.l4_test_dir.txt"
Remove-Item $stateFilePath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "--- Layer 4: Main Workflow Integration Testing ---" -ForegroundColor Magenta
Write-Host "--- Step 1: Automated Setup ---" -ForegroundColor Cyan

# --- A. Reset Environment (Idempotent Cleanup) ---
Write-Host "Resetting test environment..." -ForegroundColor Yellow
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
Remove-Item -Path "config.ini" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "data/personalities_db.txt" -Force -ErrorAction SilentlyContinue

$backupDir = "test_backups"; New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
$latestConfigBackup = Get-ChildItem -Path $backupDir -Filter "config.ini.*.bak" | Sort-Object Name -Descending | Select-Object -First 1
if ($latestConfigBackup) { Copy-Item -Path $latestConfigBackup.FullName -Destination "config.ini" -Force }
$latestDbBackup = Get-ChildItem -Path $backupDir -Filter "personalities_db.txt.*.bak" | Sort-Object Name -Descending | Select-Object -First 1
if ($latestDbBackup) { Copy-Item -Path $latestDbBackup.FullName -Destination "data/personalities_db.txt" -Force }

# --- B. Backup and Setup ---
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (Test-Path -Path "config.ini") {
    $backupFile = Join-Path $backupDir "config.ini.$timestamp.bak"; Write-Host "Backing up existing config.ini to $backupFile"
    Copy-Item -Path "config.ini" -Destination $backupFile -Force
}
if (Test-Path -Path "data/personalities_db.txt") {
    $backupFile = Join-Path $backupDir "personalities_db.txt.$timestamp.bak"; Write-Host "Backing up existing data/personalities_db.txt to $backupFile"
    Copy-Item -Path "data/personalities_db.txt" -Destination $backupFile -Force
}

# --- C. Create Test-Specific Artifacts ---
Set-Content -Path "config.ini" -Value @"
[Study]
num_replications = 1
num_trials = 1
group_size = 2
mapping_strategy = correct
[LLM]
model_name = google/gemini-flash-1.5
temperature = 0.2
max_tokens = 8192
max_parallel_sessions = 2
[API]
api_endpoint = https://openrouter.ai/api/v1/chat/completions
referer_header = http://localhost:3000
api_timeout_seconds = 120
[General]
base_output_dir = output
queries_subdir = session_queries
responses_subdir = session_responses
analysis_inputs_subdir = analysis_inputs
new_experiments_subdir = new_experiments
experiment_dir_prefix = experiment_
[Filenames]
personalities_src = personalities_db.txt
base_query_src = base_query.txt
all_scores_for_analysis = all_scores.txt
all_mappings_for_analysis = all_mappings.txt
successful_indices_log = successful_query_indices.txt
used_indices_log = used_personality_indices.txt
[MetaAnalysis]
default_top_k_accuracy = 3
analysis_input_delimiter = \t
[Schema]
factors = model, mapping_strategy, temperature, k, m
metrics = mean_mrr,mean_top_1_acc,mean_top_3_acc,mean_mrr_lift,mean_top_1_acc_lift,mean_top_3_acc_lift,mean_effect_size_r,mwu_stouffer_z,mwu_fisher_chi2,mean_rank_of_correct_id,n_valid_responses,top1_pred_bias_std,true_false_score_diff,bias_slope,bias_p_value
csv_header_order = run_directory,replication,n_valid_responses,model,mapping_strategy,temperature,k,m,db,mwu_stouffer_z,mwu_stouffer_p,mwu_fisher_chi2,mwu_fisher_p,mean_effect_size_r,effect_size_r_p,mean_mrr,mrr_p,mean_top_1_acc,top_1_acc_p,mean_top_3_acc,top_3_acc_p,mean_mrr_lift,mean_top_1_acc_lift,mean_top_3_acc_lift,mean_rank_of_correct_id,rank_of_correct_id_p,top1_pred_bias_std,true_false_score_diff,bias_slope,bias_intercept,bias_r_value,bias_p_value,bias_std_err
[Analysis]
min_valid_response_threshold = 0
"@ -Encoding utf8
Set-Content -Path "data/personalities_db.txt" -Value @"
Index`tidADB`tName`tBirthYear`tDescriptionText
1`t1001`tSean Connery`t1930`tDescription for Connery.
2`t1002`tAarón Hernán`t1930`tDescription for Hernan.
3`t1003`tOdetta`t1930`tDescription for Odetta.
"@ -Encoding utf8

Write-Host "Main workflow test environment created successfully." -ForegroundColor Green
Write-Host "This completes Step 1 of Layer 4 (Automated Setup). Your next action is Step 2: Execute the Test Workflow." -ForegroundColor Yellow
Write-Host ""