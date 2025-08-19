# Testing Strategy for the LLM Personality Matching Project

This document outlines the testing philosophy, procedures, and coverage strategy for the framework. It serves as a guide for developers and a record of the project's quality assurance standards.

## How to Run Automated Tests

The project uses `pytest` for Python unit tests. All automated tests are managed via PDM.

-   **Run all Python unit tests:**
    ```bash
    pdm run test
    ```
-   **Run unit tests with a console coverage report:**
    ```bash
    pdm run cov
    ```
-   **Run coverage for a specific file by its base name:**
    ```bash
    pdm run cov-file validate_wikipedia_pages
    ```

## A Guide to Manual & Integration Testing

> **Warning:** The test procedures below involve creating temporary files and backing up your main `config.ini`. You **must** complete the entire "Setup -> Test -> Cleanup" workflow for each test case. Running only the setup step will leave your project in a modified state.

This section provides a unified, step-by-step guide to the project's validation process, from developing a single script to performing a full end-to-end integration test of the data preparation pipeline.

### The Three Layers of Validation

The framework is validated using a multi-layered strategy to ensure correctness at all levels:

1.  **Unit Testing:** Validating a single Python script in isolation.
2.  **Orchestration Logic Testing:** Validating a PowerShell orchestrator's logic using mock scripts.
3.  **End-to-End Integration Testing:** Validating the entire pipeline with real scripts and a controlled seed dataset.

---

### Layer 1: Unit Testing (A Single Python Script)

This is the iterative workflow for developing or modifying any individual Python script in the `src/` directory.

#### **The Iterative Development Workflow**

The process involves alternating between quick manual checks and building a permanent automated test suite.

**A. Manual Testing (Initial Validation)**
Before writing formal tests, perform a quick manual run to confirm the script's core logic. The commands below provide a template for creating a safe, temporary environment for this.

1.  **Setup:** Create a temporary directory, copy the script, and create minimal dummy input files.
    ```powershell
    # Replace <script_name.py> and <input_file> with actual filenames
    $script = "<script_name.py>"; $testDir = "temp_manual_test"
    New-Item $testDir -ItemType Directory -Force | Out-Null
    Copy-Item "src/$script" $testDir
    # Example: Create a dummy input file the script needs
    # Set-Content -Path (Join-Path $testDir "<input_file>") -Value "..."
    ```

2.  **Test:** Activate the venv, run the script, and inspect the output.
    ```powershell
    # Activate venv (use source .venv/bin/activate on macOS/Linux)
    . .\.venv\Scripts\Activate.ps1
    cd $testDir
    # Run the script with any necessary arguments
    python $script
    # Manually check the files created by the script
    Get-ChildItem .
    cd ..
    # Deactivate the venv when done
    deactivate
    ```

3.  **Cleanup:** Remove the temporary directory.
    ```powershell
    Remove-Item $testDir -Recurse -Force
    ```

**B. Automated Unit Testing (`pytest`)**
Once manual testing confirms the logic is sound, create a permanent, automated test for it. This test will cover its functions and edge cases, ensuring future changes don't break it.

-   **Run the specific test file with code coverage:**
    ```powershell
    # Replace <script_name> with the base name of the script (e.g., fetch_adb_data)
    pdm run cov-file <script_name>
    ```

**C. Iteration and Final Validation**
Repeat steps A and B as you develop. If you modify the script's code while writing automated tests, you **must** perform a final manual test (Step A) to ensure the changes did not introduce unintended side effects.

---

### Layer 2: Orchestration Logic Testing (`prepare_data.ps1` with Mocks)

This procedure validates the state machine logic of the `prepare_data.ps1` orchestrator (resumability, manual step handling) quickly and predictably by using mock Python scripts that create empty files.

*This test has been successfully completed, and the procedure is preserved here for reference.*

#### Step 1: Automated Setup
Run this command from the **project root** to create the test environment with all necessary mock scripts.
```powershell
# Create the test directory and all required subdirectories
$testDir = "temp_mock_test"; New-Item -Path $testDir -ItemType Directory -Force | Out-Null
$srcDir = (Join-Path $testDir "src"); New-Item -Path $srcDir -ItemType Directory | Out-Null
@("sources", "reports", "processed", "intermediate", "foundational_assets/neutralized_delineations") | ForEach-Object { New-Item -Path (Join-Path $testDir "data/$_") -ItemType Directory | Out-Null }

# Copy the orchestrator
Copy-Item -Path "prepare_data.ps1" -Destination $testDir

# Create all mock Python scripts
Set-Content -Path (Join-Path $srcDir "find_wikipedia_links.py") -Value 'from pathlib import Path; Path("data/processed/adb_wiki_links.csv").touch()'
Set-Content -Path (Join-Path $srcDir "select_eligible_candidates.py") -Value 'from pathlib import Path; Path("data/processed/adb_eligible_candidates.txt").touch()'
Set-Content -Path (Join-Path $srcDir "generate_eminence_scores.py") -Value 'from pathlib import Path; Path("data/foundational_assets/eminence_scores.csv").touch()'
Set-Content -Path (Join-Path $srcDir "generate_ocean_scores.py") -Value 'from pathlib import Path; Path("data/foundational_assets/ocean_scores.csv").touch()'
Set-Content -Path (Join-Path $srcDir "select_final_candidates.py") -Value 'from pathlib import Path; Path("data/processed/adb_final_candidates.txt").touch()'
Set-Content -Path (Join-Path $srcDir "prepare_sf_import.py") -Value 'from pathlib import Path; Path("data/intermediate/sf_data_import.txt").touch()'
Set-Content -Path (Join-Path $srcDir "neutralize_delineations.py") -Value 'from pathlib import Path; p = Path("data/foundational_assets/neutralized_delineations/aspects.csv"); p.parent.mkdir(exist_ok=True); p.touch()'
Set-Content -Path (Join-Path $srcDir "create_subject_db.py") -Value 'from pathlib import Path; Path("data/processed/subject_db.csv").touch()'
Set-Content -Path (Join-Path $srcDir "generate_personalities_db.py") -Value 'from pathlib import Path; Path("personalities_db.txt").touch()'

# Create the seed data files
Set-Content -Path (Join-Path $testDir "data/sources/adb_raw_export.txt") -Value "..." # (Content doesn't matter for this test)
Set-Content -Path (Join-Path $testDir "data/reports/adb_validation_report.csv") -Value "..." # (Content doesn't matter for this test)

Write-Host "Mock test environment created in 'temp_mock_test'." -ForegroundColor Green
```

#### Step 2: Execute the Test Workflow
This is a multi-stage process. Run each command block and wait for it to complete before proceeding to the next.
```powershell
# a. Activate the venv from the project root and navigate to the test directory
. .\.venv\Scripts\Activate.ps1
cd temp_mock_test

# b. Run the clean run test. It will pause at the first manual step.
.\prepare_data.ps1

# c. Simulate the first manual step, then re-run the orchestrator. It will pause at the second.
New-Item -Path "data/foundational_assets/sf_chart_export.csv" -ItemType File
.\prepare_data.ps1

# d. Simulate the second manual step, then re-run the orchestrator. It will complete successfully.
New-Item -Path "data/foundational_assets/sf_delineations_library.txt" -ItemType File
.\prepare_data.ps1
```

#### Step 3: Automated Verification
Run this command from inside `temp_mock_test` to confirm the pipeline completed.
```powershell
if (Test-Path -Path "personalities_db.txt") {
    Write-Host "PASS: Orchestrator logic test completed successfully." -ForegroundColor Green
} else {
    Write-Host "FAIL: Final output file was not created." -ForegroundColor Red
}
```

#### Step 4: Automated Cleanup
Run this command from the **project root** to delete the test directory.
```powershell
Remove-Item -Path "temp_mock_test" -Recurse -Force
Write-Host "Mock test environment cleaned up." -ForegroundColor Yellow
```

---

### Layer 3: End-to-End Integration Testing (`prepare_data.ps1`)

This is the final validation phase for the data preparation pipeline. This procedure runs the **real** `prepare_data.ps1` orchestrator with the **real** Python scripts on a small, controlled seed dataset to verify that the data handoffs between each live script are correct.

**Prerequisites:**
*   A configured `.env` file in the project root with a valid API key.
*   The virtual environment is **not** active yet.

#### Step 1: Automated Setup
Run this command from the **project root** to create the test environment.
```powershell
# Create the test directory and all required subdirectories
$testDir = "temp_integration_test"; New-Item -Path $testDir -ItemType Directory -Force | Out-Null
@("sources", "reports", "processed", "intermediate", "foundational_assets/neutralized_delineations") | ForEach-Object { New-Item -Path (Join-Path $testDir "data/$_") -ItemType Directory | Out-Null }
# Copy the orchestrator, real source code, and required assets
Copy-Item -Path "prepare_data.ps1" -Destination $testDir
Copy-Item -Path "src" -Destination $testDir -Recurse
Copy-Item -Path ".env" -Destination $testDir
Copy-Item -Path "data/foundational_assets/country_codes.csv", "data/foundational_assets/point_weights.csv", "data/foundational_assets/balance_thresholds.csv", "data/foundational_assets/sf_delineations_library.txt" -Destination (Join-Path $testDir "data/foundational_assets/")
# Create the seed data files inside the test directory
Set-Content -Path (Join-Path $testDir "data/sources/adb_raw_export.txt") -Value @"
Index`tidADB`tLastName`tFirstName`tGender`tDay`tMonth`tYear`tTime`tZoneAbbr`tZoneTimeOffset`tCity`tCountryState`tLongitude`tLatitude`tRating`tBio`tCategories`tLink
5404`t6790`tConnery`tSean`tM`t25`t8`t1930`t18:05`t...`t-01:00`tEdinburgh`tSCOT (UK)`t3W13`t55N57`tAA`tScottish actor and film icon, he was the first to play the role of agent 007 in`tVoice/Speech, Entertain Producer, Knighted, Philanthropist, Kids - Noted, Hobbies, games, Hair, Kids 1-3, Top 5% of Profession, Rags to riches, Sex-symbol, Size, Order of birth, Foster, Step, or Adopted Kids, Number of Divorces, American Book, Number of Marriages, Vocational award, Live Stage, Oscar, Expatriate, Appearance gorgeous, Mate - Noted, Actor/ Actress, Long life >80 yrs`thttps://www.astro.com/astro-databank/Connery,_Sean
5459`t90566`tHernán`tAarón`tM`t20`t11`t1930`t04:10`t...`t-07:00`tCamargo (Chihuahua)`tMEX`t105W10`t27N40`tAA`tMexican stage and screen actor most famous for his work in ’’telenovelas’’ (TV`tVocational award, Heart disease/attack, Illness/ Disease, Clerical/ Secretarial, Kids 1-3, TV series/ Soap star, Actor/ Actress, Long life >80 yrs`thttps://www.astro.com/astro-databank/Hernán,_Aarón
5482`t24013`tOdetta`t`tF`t31`t12`t1930`t09:20`t...`t-06:00`tBirmingham`tAL (US)`t86W48`t33N31`tAA`tAmerican singer known for vocal power and clarity with a rich intensity of`tRace, Illness/ Disease, Heart disease/attack, Kidney, Top 5% of Profession, Profiles Of Women, Travel for work, Vocalist/ Pop, Rock, etc., Number of Marriages`thttps://www.astro.com/astro-databank/Odetta
"@
Set-Content -Path (Join-Path $testDir "data/reports/adb_validation_report.csv") -Value @"
Index,idADB,ADB_Name,Entry_Type,WP_URL,WP_Name,Name_Match_Score,Death_Date_Found,Status,Notes
5404,6790,"Connery, Sean",Person,https://en.wikipedia.org/wiki/Sean_Connery,Sean Connery,100,True,OK,
5459,90566,"Hernán, Aarón",Person,https://en.wikipedia.org/wiki/Aar%C3%B3n_Hern%C3%A1n,Aarón Hernán,100,True,OK,
5482,24013,Odetta,Person,https://en.wikipedia.org/wiki/Odetta,Odetta,100,True,OK,
"@
Write-Host "Test environment created in 'temp_integration_test'." -ForegroundColor Green
```

#### Step 2: Activate Environment and Run Pipeline (Part 1)
```powershell
# Activate the venv from the project root
. .\.venv\Scripts\Activate.ps1
# Navigate into the test directory
cd temp_integration_test
# Run the orchestrator
.\prepare_data.ps1
# The script will pause after several minutes.
```

#### Step 3: Simulate Manual Solar Fire Export
```powershell
# Run this command from inside temp_integration_test
Set-Content -Path "data/foundational_assets/sf_chart_export.csv" -Value @"
"Connery Sean","25 August 1930","18:05","3fS1bTfA","+1:00","Edinburgh","SCOT (UK)","55n57","3w13"
"Body Name","Body Abbr","Longitude"
"Sun","Su","152.05"
"Moon","Mo","333.15"
"Mercury","Me","168.97"
"Venus","Ve","180.82"
"Mars","Ma","162.77"
"Jupiter","Ju","97.02"
"Saturn","Sa","298.50"
"Uranus","Ur","12.82"
"Neptune","Ne","151.02"
"Pluto","Pl","110.12"
"Ascendant","Asc","322.25"
"Midheaven","MC","251.58"
"Hernán Aarón","20 November 1930","4:10","6sYw24nF","-7:00","Camargo (Chihuahua)","MEX","27n40","105w10"
"Body Name","Body Abbr","Longitude"
"Sun","Su","237.58"
"Moon","Mo","126.70"
"Mercury","Me","254.83"
"Venus","Ve","220.52"
"Mars","Ma","143.20"
"Jupiter","Ju","104.53"
"Saturn","Sa","298.88"
"Uranus","Ur","13.78"
"Neptune","Ne","155.07"
"Pluto","Pl","110.75"
"Ascendant","Asc","216.92"
"Midheaven","MC","127.35"
"Odetta","31 December 1930","9:20","cTSo2","-6:00","Birmingham","AL (US)","33n31","86w48"
"Body Name","Body Abbr","Longitude"
"Sun","Su","279.17"
"Moon","Mo","289.02"
"Mercury","Me","293.45"
"Venus","Ve","258.97"
"Mars","Ma","153.25"
"Jupiter","Ju","107.57"
"Saturn","Sa","300.73"
"Uranus","Ur","13.88"
"Neptune","Ne","155.85"
"Pluto","Pl","111.08"
"Ascendant","Asc","329.58"
"Midheaven","MC","252.75"
"@
```

#### Step 4: Run Pipeline (Part 2)
```powershell
# Run the orchestrator again to complete the pipeline
.\prepare_data.ps1
```

#### Step 5: Automated Verification
```powershell
# Run this from inside temp_integration_test
if (-not (Test-Path -Path "personalities_db.txt")) { Write-Host "FAIL: personalities_db.txt was not created." -ForegroundColor Red } elseif ((Get-Content "personalities_db.txt" | Measure-Object -Line).Lines -ne 4) { Write-Host "FAIL: personalities_db.txt has the wrong number of lines." -ForegroundColor Red } else { Write-Host "PASS: The final personalities_db.txt was created successfully with 3 subject records." -ForegroundColor Green }
```

#### Step 6: Automated Cleanup
```powershell
# Run this from the project root
Remove-Item -Path "temp_integration_test" -Recurse -Force
Write-Host "Test environment cleaned up." -ForegroundColor Yellow
```

### Layer 4: End-to-End Integration Testing (Main Experiment Workflows)

This procedure validates the core user-facing experiment lifecycle: creating a new experiment, auditing it, simulating a failure, and repairing it. It uses a minimal `config.ini` and a small, 3-subject `personalities_db.txt` to ensure the test is fast and makes minimal API calls.

> **Troubleshooting:** If any step in this procedure fails, your recovery action is always the same: **re-run the "Step 1: Automated Setup and Reset" command.** This will safely clean up any failed artifacts and restore your project from the latest backups.

#### Step 0: (CRITICAL) Manual Project Backup
This automated test procedure is designed to be safe, but it will perform several actions that modify your project's state:
*   It will temporarily replace your main `config.ini` and `data/personalities_db.txt` files. These will be restored during the cleanup phase.
*   It will create a new experiment directory inside `output/new_experiments`, which will be deleted during the cleanup phase.

To provide a complete safety net, it is critical that you first create a manual backup of these specific assets. The backup is intentionally selective; these are the only files and directories the test will touch. This ensures your project can be fully restored to its original state if anything unexpected happens.

**Instructions:**

1.  Create a new folder outside of the project directory (e.g., on your Desktop) and name it something like `project_backup`.
2.  Using your file explorer, manually copy the following files and folders into your new `project_backup` folder:
    *   The `config.ini` file from the project root.
    *   The `personalities_db.txt` file from the `data/` directory.
    *   The entire `output/new_experiments` directory.

**Do not proceed until you have manually verified that these files are safely backed up.**

#### Step 1: Automated Setup and Reset
Run this command from the **project root**. It will safely clean up any artifacts from a previous run and create a fresh test environment by creating timestamped backups of your critical files.

```powershell
# --- A. Reset Environment (Idempotent Cleanup) ---
Write-Host "Resetting test environment..." -ForegroundColor Yellow
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }
# NOTE: We do NOT delete the 'output/new_experiments' directory.
# The cleanup at the end of the test will surgically remove only the test-generated experiment.
# Clean up any leftover test files before restoring backups
Remove-Item -Path "config.ini" -Force -ErrorAction SilentlyContinue
Remove-Item -Path "data/personalities_db.txt" -Force -ErrorAction SilentlyContinue

# Restore original files from the latest backups to ensure a clean start
$backupDir = "test_backups"; New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
$latestConfigBackup = Get-ChildItem -Path $backupDir -Filter "config.ini.*.bak" | Sort-Object Name -Descending | Select-Object -First 1
if ($latestConfigBackup) {
    Copy-Item -Path $latestConfigBackup.FullName -Destination "config.ini" -Force
}
$latestDbBackup = Get-ChildItem -Path $backupDir -Filter "personalities_db.txt.*.bak" | Sort-Object Name -Descending | Select-Object -First 1
if ($latestDbBackup) {
    Copy-Item -Path $latestDbBackup.FullName -Destination "data/personalities_db.txt" -Force
}

# --- B. Backup and Setup ---
$backupDir = "test_backups"; New-Item -Path $backupDir -ItemType Directory -Force | Out-Null
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
# Backup original config.ini using a non-destructive COPY
if (Test-Path -Path "config.ini") {
    $backupFile = Join-Path $backupDir "config.ini.$timestamp.bak"
    Write-Host "Backing up existing config.ini to $backupFile"
    Copy-Item -Path "config.ini" -Destination $backupFile -Force
}
# Backup original personalities_db.txt using a non-destructive COPY
if (Test-Path -Path "data/personalities_db.txt") {
    $backupFile = Join-Path $backupDir "personalities_db.txt.$timestamp.bak"
    Write-Host "Backing up existing data/personalities_db.txt to $backupFile"
    Copy-Item -Path "data/personalities_db.txt" -Destination $backupFile -Force
}

# --- C. Create Test-Specific Artifacts ---
# Create a minimal but complete config.ini for the test
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
# --- Create the minimal personalities database in the DATA directory
Set-Content -Path "data/personalities_db.txt" -Value @"
Index`tidADB`tName`tBirthYear`tDescriptionText
1`t1001`tSean Connery`t1930`tDescription for Connery.
2`t1002`tAarón Hernán`t1930`tDescription for Hernan.
3`t1003`tOdetta`t1930`tDescription for Odetta.
"@ -Encoding utf8

Write-Host "Main workflow test environment created successfully." -ForegroundColor Green
```

#### Step 2: Execute the Test and Clean Up
This is a single, continuous workflow. **All commands must now be run from the project root.**

```powershell
# a. Activate the venv from the project root
. .\.venv\Scripts\Activate.ps1

# b. Run a new experiment from scratch.
Write-Host "`n--- Running new_experiment.ps1 ---" -ForegroundColor Cyan
.\new_experiment.ps1 -Verbose

# c. Find the new experiment directory and audit it
Write-Host "`n--- Auditing new experiment (should be VALIDATED) ---" -ForegroundColor Cyan
$expDir = Get-ChildItem -Path "output/new_experiments" -Directory | Sort-Object CreationTime -Descending | Select-Object -First 1
.\audit_experiment.ps1 -TargetDirectory $expDir.FullName

# d. Intentionally "break" the experiment
Write-Host "`n--- Simulating failure by deleting a response file ---" -ForegroundColor Cyan
$runDir = Get-ChildItem -Path $expDir.FullName -Directory "run_*" | Select-Object -First 1
$responseFile = Get-ChildItem -Path (Join-Path $runDir.FullName "session_responses") -Include "llm_response_*.txt" -Recurse | Select-Object -First 1
if ($null -ne $responseFile) {
    Write-Host "Intentionally deleting response file: $($responseFile.Name)" -ForegroundColor Yellow
    Remove-Item -Path $responseFile.FullName
} else {
    Write-Warning "Could not find a response file to delete for the test. The experiment may have failed to generate one."
}

# e. Audit the broken experiment (should report NEEDS REPAIR)
Write-Host "`n--- Auditing broken experiment (should be NEEDS REPAIR) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -TargetDirectory $expDir.FullName

# f. Run the fix script to automatically repair the experiment
Write-Host "`n--- Running fix_experiment.ps1 ---" -ForegroundColor Cyan
.\fix_experiment.ps1 -TargetDirectory $expDir.FullName -NonInteractive

# g. Run a final audit to confirm the repair (should be VALIDATED again)
Write-Host "`n--- Final audit (should be VALIDATED) ---" -ForegroundColor Cyan
.\audit_experiment.ps1 -TargetDirectory $expDir.FullName

# h. Final Cleanup
Write-Host "`n--- Test complete. Cleaning up... ---" -ForegroundColor Yellow
if (Get-Command deactivate -ErrorAction SilentlyContinue) { deactivate }

# Surgically remove ONLY the experiment directory created during this test
if ($expDir -and (Test-Path $expDir.FullName)) {
    Write-Host "Removing test experiment directory: $($expDir.FullName)"
    Remove-Item -Path $expDir.FullName -Recurse -Force -ErrorAction SilentlyContinue
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
```

## Testing Status

### Data Preparation Pipeline

The following table details the testing status for each script in the data preparation pipeline.

--------------------------------------------------------------------------------------------------------------------
Module                              Cov. (%)        Status & Justification
----------------------------------- --------------- -----------------------------------------------------------------
`src/fetch_adb_data.py`             `~37%`          **COMPLETE.** Unit tests cover critical offline logic. Live
                                                    network code is validated via integration testing.

`src/find_wikipedia_links.py`       `~38%`          **COMPLETE.** Unit tests cover key logic, including HTML parsing
                                                    and mocked API calls. Orchestration is validated via integration.

`src/validate_wikipedia_pages.py`   `~38%`          **COMPLETE.** Manual validation of the refactored script is
                                                    complete. Unit tests cover all critical validation logic.

`src/select_eligible_candidates.py` `~72%`          **COMPLETE.** The script was fully refactored and manually
                                                    validated. Unit tests cover all core filtering and resumability
                                                    logic.

`src/generate_eminence_scores.py`   `~55%`          **COMPLETE.** Unit tests cover the critical offline logic,
                                                    including LLM response parsing, resumability, and a mocked
                                                    orchestrator loop. Live LLM calls are validated via integration.

`src/generate_ocean_scores.py`      `~17%`          **COMPLETE.** Unit tests cover the critical offline logic,
                                                    including LLM response parsing, variance calculation, and the
                                                    data-driven cutoff logic. Live LLM calls are validated via
                                                    integration testing.

`src/select_final_candidates.py`    `~65%`          **COMPLETE.** The script was fully refactored and manually
                                                    validated. Unit tests cover the entire data transformation
                                                    workflow, including filtering, mapping, and sorting.

`src/prepare_sf_import.py`          `~58%`          **COMPLETE.** The script was fully refactored and manually
                                                    validated. Unit tests cover the core data transformation and
                                                    CQD formatting logic.

`src/create_subject_db.py`          `~50%`          **COMPLETE.** The script was fully refactored and manually
                                                    validated. Unit tests cover the core data integration logic,
                                                    including Base58 decoding, file merging, and data flattening.

`src/neutralize_delineations.py`    `~19%`          **COMPLETE.** Unit tests cover the critical offline logic for parsing
                                                    the esoteric input file format and correctly grouping items into
                                                    LLM tasks. The live LLM calls are validated via integration testing.

`src/generate_personalities_db.py`  `~75%`          **COMPLETE.** The script was fully refactored and manually
                                                    validated. Unit tests cover the entire data assembly algorithm,
                                                    including all calculations and text lookups.

`prepare_data.ps1`                  `N/A`           **IN PROGRESS.** Orchestration logic has been fully validated
                                                    via mock script testing. Full end-to-end integration testing is
                                                    now pending.
--------------------------------------------------------------------------------------------------------------------

### Main Experiment & Analysis Pipeline

The following table details the testing status for each script in the main experimental and analysis workflows.

--------------------------------------------------------------------------------------------------------------------
Module                              Cov. (%)        Status & Justification
----------------------------------- --------------- -----------------------------------------------------------------
`src/experiment_manager.py`         `~56%`          **COMPLETE.** Unit tests are complete, and the core `new`/`audit`/`fix`
                                                    workflows have been successfully validated via the scripted
                                                    end-to-end integration test.

`src/experiment_auditor.py`         `PENDING`       **PENDING.** Unit testing will be performed next.

`src/compile_*.py` (aggregators)    `PENDING`       **PENDING.** Unit tests will be written for the aggregation scripts.

`src/study_analyzer.py`             `PENDING`       **PENDING.** Unit tests will be written for the statistical analysis
                                                    script.

PowerShell Wrappers (`*.ps1`)       `N/A`           **IN PROGRESS.** The core `new`, `audit`, and `fix` wrappers are
                                                    validated. The `migrate` and `study`-level wrappers are pending.
--------------------------------------------------------------------------------------------------------------------