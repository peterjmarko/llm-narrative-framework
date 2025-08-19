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

### The Four Layers of Validation

The framework is validated using a multi-layered strategy to ensure correctness at all levels:

1.  **Layer 1: Unit Testing:** Validating a single Python script in isolation.
2.  **Layer 2: Orchestration Logic Testing:** Validating a PowerShell orchestrator's logic using mock scripts.
3.  **Layer 3: Data Pipeline Integration Testing:** Validating the `prepare_data.ps1` pipeline from end to end with real scripts and a controlled seed dataset.
4.  **Layer 4: Main Workflow Integration Testing:** Validating the core `new -> audit -> fix` experiment lifecycle with real scripts and a controlled seed dataset.

---

### Layer 1: Unit Testing (A Single Python Script)

This is the iterative workflow for developing or modifying any individual Python script in the `src/` directory.

#### **A Note on Workflow: The Smoke Test**
After making any significant changes to the codebase—especially to core modules like `experiment_manager.py` or `orchestrate_replication.py`—it is highly recommended to perform a quick **smoke test** before proceeding with more detailed validation.

This test simply runs the main `new_experiment.ps1` workflow. Its purpose is to catch obvious, critical bugs immediately.
```powershell
# Run a quick, minimal experiment to ensure the main pipeline is functional
.\new_experiment.ps1
```
If this command completes successfully, you can proceed with confidence to the more detailed testing steps below. If it fails, you have found a major issue that should be fixed before continuing.

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

This procedure validates the core `new -> audit -> fix` experiment lifecycle using a set of dedicated, easy-to-use scripts. It follows a clean `Setup -> Test -> Cleanup` pattern.

> **Troubleshooting:** If any step fails, your recovery action is always the same: re-run the `Step 1: Automated Setup` script. This will safely clean up any failed artifacts and restore your project from the latest backups.

#### Step 0: (CRITICAL) Manual Project Backup
This procedure is designed to be safe, but it will temporarily modify core project files. To provide a complete safety net, it is critical that you first create a manual backup of these specific assets:
*   The `config.ini` file from the project root.
*   The `personalities_db.txt` file from the `data/` directory.
*   The entire `output/new_experiments` directory.

**Do not proceed until you have manually verified that these files are safely backed up.**

#### Step 1: Automated Setup
Run this script from the **project root**. It will safely clean up any artifacts from a previous run and create a fresh test environment by creating timestamped backups of your critical files.

```powershell
.\scripts\testing_harness\layer4_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
After setup is complete, run this script to execute the full `new -> audit -> fix` workflow. At the end, the test artifacts (e.g., the new experiment directory and its logs) are left intact for your inspection.

> **Important:** You can re-run this script multiple times for debugging before proceeding to the final cleanup.

```powershell
.\scripts\testing_harness\layer4_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After you have finished inspecting the experiment directory and its log files, run this script from the project root to restore your project to its original, clean state.

```powershell
.\scripts\testing_harness\layer4_step3_cleanup.ps1
```

## Testing Status

### Data Preparation Pipeline

The following table details the testing status for each script in the data preparation pipeline.

--------------------------------------------------------------------------------------------------------------------
Module                              Cov. (%)        Status & Justification
----------------------------------- --------------- -----------------------------------------------------------------
**Sourcing**

`src/fetch_adb_data.py`             `~37%`          **COMPLETE.** Unit tests cover critical offline logic. Live
                                                    network code is validated via integration testing.

`src/find_wikipedia_links.py`       `~38%`          **COMPLETE.** Unit tests cover key logic, including HTML parsing
                                                    and mocked API calls. Orchestration is validated via integration.

`src/validate_wikipedia_pages.py`   `~38%`          **COMPLETE.** Manual validation of the refactored script is
                                                    complete. Unit tests cover all critical validation logic.

`src/select_eligible_candidates.py` `~72%`          **COMPLETE.** The script was fully refactored and manually
                                                    validated. Unit tests cover all core filtering and resumability
                                                    logic.

**Scoring**

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

**Generation**

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

-----------------------------------------------------------------------------------------------------------------------------------------
Module                                  Cov. (%)        Status & Justification
--------------------------------------- --------------- ----------------------------------------------------------------------------------
**Core Orchestrators**

`src/experiment_manager.py`             `~56%`          **COMPLETE.** Unit tests are complete, and the core `new`/`audit`/`fix`
                                                        workflows have been successfully validated via the scripted
                                                        end-to-end integration test.
`src/orchestrate_replication.py`        `~77%`          **COMPLETE.** Unit tests cover the core control flow for both
                                                        "new run" and "reprocess" modes, including failure handling.

**Single-Replication Pipeline**

`src/build_llm_queries.py`              `~68%`          **COMPLETE.** Unit tests cover the core orchestration logic,
                                                        including new runs, continued runs, and key failure modes.
`src/llm_prompter.py`                   `PENDING`       **IN PROGRESS.** Unit testing will be performed next.

`src/process_llm_responses.py`          `PENDING`       **PENDING.** Unit testing will be performed next.

`src/analyze_llm_performance.py`        `PENDING`       **PENDING.** Unit testing will be performed next.

`src/run_bias_analysis.py`              `PENDING`       **PENDING.** Unit testing will be performed next.

`src/generate_replication_report.py`    `PENDING`       **PENDING.** Unit testing will be performed next.

**Auditing & Utility Scripts**

`src/experiment_auditor.py`             `PENDING`       **PENDING.** Unit testing will be performed next.

`src/replication_log_manager.py`        `PENDING`       **PENDING.** Unit testing will be performed next.

`src/patch_old_experiment.py`           `PENDING`       **PENDING.** Unit testing will be performed next.

`src/restore_config.py`                 `PENDING`       **PENDING.** Unit testing will be performed next.

**Aggregation & Analysis Scripts**

`src/compile_replication_results.py`    `PENDING`       **PENDING.** Unit tests will be written for the aggregation scripts.

`src/compile_experiment_results.py`     `PENDING`       **PENDING.** Unit tests will be written for the aggregation scripts.

`src/compile_study_results.py`          `PENDING`       **PENDING.** Unit tests will be written for the aggregation scripts.

`src/study_analyzer.py`                 `PENDING`       **PENDING.** Unit tests will be written for the statistical analysis script.

**PowerShell Wrappers (Experiments)**

`new_experiment.ps1`                    `N/A`           **COMPLETE.** Validated via end-to-end integration testing.

`audit_experiment.ps1`                  `N/A`           **COMPLETE.** Validated via end-to-end integration testing.

`fix_experiment.ps1`                    `N/A`           **COMPLETE.** Validated via end-to-end integration testing.

`migrate_experiment.ps1`                `N/A`           **PENDING.** Manual validation is pending.

**PowerShell Wrappers (Studies)**

`audit_study.ps1`                       `N/A`           **PENDING.** Manual validation is pending.

`fix_study.ps1`                         `N/A`           **PENDING.** Manual validation is pending.

`migrate_study.ps1`                     `N/A`           **PENDING.** Manual validation is pending.

`process_study.ps1`                     `N/A`           **PENDING.** Manual validation is pending.
-----------------------------------------------------------------------------------------------------------------------------------------