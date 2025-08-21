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

### The Five Layers of Validation

The framework is validated using a multi-layered strategy to ensure correctness at all levels:

1.  **Layer 1: Unit Testing:** Validating a single Python script in isolation.
2.  **Layer 2: Data Pipeline Orchestration Testing:** Validating the `prepare_data.ps1` orchestrator's logic using mock scripts.
3.  **Layer 3: Data Pipeline Integration Testing:** Validating the full `prepare_data.ps1` pipeline with a controlled seed dataset.
4.  **Layer 4: Main Workflow Integration Testing:** Validating the core `new -> audit -> fix` experiment lifecycle.
5.  **Layer 5: Migration Workflow Integration Testing:** Validating the `migrate_experiment.ps1` workflow.

---

### Layer 1: Unit Testing (A Single Python Script)

This is the iterative workflow for developing or modifying any individual Python script. It follows a clean `Develop -> Test -> Finalize` pattern.

#### A. The Smoke Test
After making any significant changes to the codebase, perform a quick **smoke test** by running the main `new_experiment.ps1` workflow. This catches critical bugs immediately.
```powershell
# Run a quick, minimal experiment to ensure the main pipeline is functional
.\new_experiment.ps1
```
If this fails, fix the issue before proceeding.

#### B. The Iterative Development Workflow
The core process involves alternating between quick manual checks and building a permanent automated test suite.

1.  **Manual Testing (Initial Check):** Before writing formal tests, perform a quick manual run in a temporary directory to confirm the script's core logic.
2.  **Automated Unit Testing (`pytest`):** Once the logic seems sound, create a permanent, automated unit test for it. Use this to validate all functions and edge cases.
    ```powershell
    # Run the specific test file with code coverage
    pdm run cov-file <script_name>
    ```
3.  **Final Manual Validation:** If you modify the script's code while writing automated tests, you **must** perform a final manual test to ensure the changes did not introduce unintended side effects.

---

### Layer 2: Data Pipeline Orchestration Testing (`prepare_data.ps1` with Mocks)

This procedure validates the state machine logic of the `prepare_data.ps1` orchestrator by using mock scripts. It follows a clean `Setup -> Test -> Cleanup` pattern.

#### Step 1: Automated Setup
Run this script to create the test environment with all necessary mock scripts.
```powershell
.\tests\testing_harness\layer2_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
This script fully automates the multi-stage test, including simulating the manual steps, and verifies the final output.
```powershell
.\tests\testing_harness\layer2_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After inspecting the artifacts, run this script to delete the test directory.
```powershell
.\tests\testing_harness\layer2_step3_cleanup.ps1
```

---

### Layer 3: Data Pipeline Integration Testing (`prepare_data.ps1`)

This procedure validates the real data preparation pipeline with a controlled seed dataset. This is an **interactive** test that requires manual steps.

**Prerequisites:** A configured `.env` file in the project root with a valid API key.

#### Step 1: Automated Setup
Run this script to create the test environment with all required scripts and seed data.
```powershell
.\tests\testing_harness\layer3_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow (Interactive)
This script guides you through the interactive test. It will run the first part of the pipeline, then pause and provide instructions for the required manual step.
```powershell
# Run this once to start the pipeline
.\tests\testing_harness\layer3_step2_test_workflow.ps1
```
When prompted, run the helper script to simulate the manual data creation:
```powershell
# Run this when instructed by the main workflow script
.\tests\testing_harness\layer3_simulate_manual_step.ps1
```
Finally, re-run the main workflow script to complete the pipeline and verify the results:
```powershell
# Run this again to complete the test
.\tests\testing_harness\layer3_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After inspecting the artifacts, run this script to delete the test directory.
```powershell
.\tests\testing_harness\layer3_step3_cleanup.ps1
```

### Layer 4: Main Workflow Integration Testing

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
.\tests\testing_harness\layer4_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
After setup is complete, run this script to execute the full `new -> audit -> fix` workflow. At the end, the test artifacts (e.g., the new experiment directory and its logs) are left intact for your inspection.

> **Important:** You can re-run this script multiple times for debugging before proceeding to the final cleanup.

```powershell
.\tests\testing_harness\layer4_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After you have finished inspecting the experiment directory and its log files, run this script from the project root to restore your project to its original, clean state.

```powershell
.\tests\testing_harness\layer4_step3_cleanup.ps1
```

### Layer 5: Migration Workflow Integration Testing

This procedure validates the `migrate_experiment.ps1` workflow. It automatically creates a severely corrupted experiment, runs the migration, and validates the final, repaired output.

#### Step 1: Automated Setup
Run this script from the project root. It will generate a new experiment and then deliberately corrupt it to a state that requires migration.

```powershell
.\tests\testing_harness\layer5_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
This script will audit the corrupted experiment, run the migration, and perform a final validation audit on the newly created, repaired experiment.

```powershell
.\tests\testing_harness\layer5_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After inspecting the artifacts, run this script to remove all test-related directories and restore your project to its original state.

```powershell
.\tests\testing_harness\layer5_step3_cleanup.ps1
```

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
.\tests\testing_harness\layer4_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
After setup is complete, run this script to execute the full `new -> audit -> fix` workflow. At the end, the test artifacts (e.g., the new experiment directory and its logs) are left intact for your inspection.

> **Important:** You can re-run this script multiple times for debugging before proceeding to the final cleanup.

```powershell
.\tests\testing_harness\layer4_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After you have finished inspecting the experiment directory and its log files, run this script from the project root to restore your project to its original, clean state.

```powershell
.\tests\testing_harness\layer4_step3_cleanup.ps1
```

## Testing Status

### Data Preparation Pipeline

The following table details the testing status for each script in the data preparation pipeline.

--------------------------------------------------------------------------------------------------------------------
Module                              Cov. (%)        Status & Justification
----------------------------------- --------------- -----------------------------------------------------------------
**Sourcing**

`src/fetch_adb_data.py`             `37%`           COMPLETE. Unit tests cover critical offline logic. Live
                                                    network code is validated via integration testing.

`src/find_wikipedia_links.py`       `38%`           COMPLETE. Unit tests cover key logic, including HTML parsing
                                                    and mocked API calls. Orchestration is validated via integration.

`src/validate_wikipedia_pages.py`   `38%`           COMPLETE. Manual validation of the refactored script is
                                                    complete. Unit tests cover all critical validation logic.

`src/select_eligible_candidates.py` `72%`           COMPLETE. The script was fully refactored and manually
                                                    validated. Unit tests cover all core filtering and resumability
                                                    logic.

**Scoring**

`src/generate_eminence_scores.py`   `55%`           COMPLETE. Unit tests cover the critical offline logic,
                                                    including LLM response parsing, resumability, and a mocked
                                                    orchestrator loop. Live LLM calls are validated via integration.

`src/generate_ocean_scores.py`      `17%`           COMPLETE. Unit tests cover the critical offline logic,
                                                    including LLM response parsing, variance calculation, and the
                                                    data-driven cutoff logic. Live LLM calls are validated via
                                                    integration testing.

`src/select_final_candidates.py`    `65%`           COMPLETE. The script was fully refactored and manually
                                                    validated. Unit tests cover the entire data transformation
                                                    workflow, including filtering, mapping, and sorting.

**Generation**

`src/prepare_sf_import.py`          `58%`           COMPLETE. The script was fully refactored and manually
                                                    validated. Unit tests cover the core data transformation and
                                                    CQD formatting logic.

`src/create_subject_db.py`          `50%`           COMPLETE. The script was fully refactored and manually
                                                    validated. Unit tests cover the core data integration logic,
                                                    including Base58 decoding, file merging, and data flattening.

`src/neutralize_delineations.py`    `19%`           COMPLETE. Unit tests cover the critical offline logic for parsing
                                                    the esoteric input file format and correctly grouping items into
                                                    LLM tasks. The live LLM calls are validated via integration testing.

`src/generate_personalities_db.py`  `75%`           COMPLETE. The script was fully refactored and manually
                                                    validated. Unit tests cover the entire data assembly algorithm,
                                                    including all calculations and text lookups.

`prepare_data.ps1`                  `N/A`           IN PROGRESS. Orchestration logic has been fully validated
                                                    via mock script testing. Full end-to-end integration testing is
                                                    now pending.
--------------------------------------------------------------------------------------------------------------------

### Main Experiment & Analysis Pipeline

The following table details the testing status for each script in the main experimental and analysis workflows.

-----------------------------------------------------------------------------------------------------------------------------------------
Module                                  Cov. (%)        Status & Justification
--------------------------------------- --------------- ----------------------------------------------------------------------------------
**EXPERIMENT LIFECYCLE MANAGEMENT**
**Primary Orchestrators**

`src/experiment_manager.py`             `56%`           COMPLETE. Unit tests are complete, and the core `new`/`audit`/`fix`
                                                        workflows have been successfully validated via the scripted
                                                        end-to-end integration test.

`src/experiment_auditor.py`             `71%`           COMPLETE. The unit test suite validates the auditor's
                                                        ability to correctly identify all major experiment states
                                                        (New, Complete, Aggregation Needed, Reprocess Needed, Repair
                                                        Needed, and Migration Needed) by using a mocked file system
                                                        to simulate various data completeness scenarios.

**Finalization Scripts**

`src/manage_experiment_log.py`          `79%`           COMPLETE. The unit test suite validates all core commands
                                                        (`rebuild`, `finalize`, `start`) and their file I/O
                                                        operations. It confirms correct CSV parsing, generation, and
                                                        the idempotency of the `finalize` command.

`src/compile_experiment_results.py`     `74%`           COMPLETE. Unit tests cover the main aggregation workflow and
                                                        robustly handle edge cases like empty or missing replication
                                                        files.

**SINGLE REPLICATION PIPELINE**
**Primary Orchestrator**

`src/replication_manager.py`            `77%`           COMPLETE. Unit tests cover the core control flow for both
                                                        "new run" and "reprocess" modes, including failure handling.

**Pipeline Stages**

`src/build_llm_queries.py`              `68%`           COMPLETE. Unit tests cover the core orchestration logic,
                                                        including new runs, continued runs, and key failure modes.

`src/query_generator.py`                `74%`           COMPLETE. Unit tests cover both 'correct' and 'random'
                                                        mapping strategies, edge cases (e.g., k=max), and key
                                                        failure modes like missing or insufficient input data.

`src/llm_prompter.py`                   `53%`           COMPLETE. Unit tests cover the core logic for successful API
                                                        calls, error conditions (HTTP, timeout), and file I/O failures.
`src/process_llm_responses.py`          `67%`           COMPLETE. Unit tests cover the core parsing logic, including
                                                        markdown, fallback, flexible spacing, reordered columns, and
                                                        key failure modes.

`src/analyze_llm_performance.py`        `63%`           COMPLETE. Unit tests cover the main orchestrator, all core
                                                        statistical calculations (including edge cases), and the robust
                                                        parsing of complex file formats (e.g., Markdown).

`src/run_bias_analysis.py`              `86%`           COMPLETE. Unit tests cover the main orchestrator workflow,
                                                        core bias calculations, and robust handling of empty or
                                                        malformed data files.

`src/generate_replication_report.py`    `90%`           COMPLETE. Unit tests cover the main workflow, including
                                                        robust error handling for missing/corrupted files and correct
                                                        fallback for optional data sources.

`src/compile_replication_results.py`    `78%`           COMPLETE. Unit tests cover the main workflow, data merging
                                                        logic, and robust error handling for missing or invalid input
                                                        files.

**Study-Level & Analysis**

`src/compile_study_results.py`          `76%`           COMPLETE. Unit tests cover the recursive aggregation
                                                        workflow and robustly handle edge cases like empty or missing
                                                        experiment files.

`src/analyze_study_results.py`          `66%`           COMPLETE. The unit test suite fully validates the script's
                                                        core logic, including data filtering, control flow for different
                                                        analysis scenarios (e.g., zero variance), and graceful
                                                        shutdowns. Key statistical and plotting functions are mocked
                                                        to ensure isolated validation.

**Utility & Other Scripts**

`src/upgrade_legacy_experiment.py`      `75%`           COMPLETE. The unit test suite validates the script's core
                                                        batch-processing logic, ensuring it correctly finds all
                                                        target directories and halts immediately if its worker
                                                        script reports an error.

`src/restore_experiment_config.py`      `83%`           COMPLETE. The unit test suite validates the script's ability
                                                        to parse legacy report files and correctly generate a new,
                                                        valid `config.ini.archived` file. It also confirms that the
                                                        script exits gracefully if the target directory or report
                                                        files are missing.

`src/config_loader.py`                  `51%`           COMPLETE. Unit tests cover the core `get_config_value`
                                                        helper, including successful parsing, type conversions,
                                                        fallbacks, and robust error handling for missing sections or
                                                        keys.

**PowerShell Wrappers (Experiments)**

`new_experiment.ps1`                    `N/A`           COMPLETE. Validated via end-to-end integration testing.

`audit_experiment.ps1`                  `N/A`           COMPLETE. Validated via end-to-end integration testing.

`fix_experiment.ps1`                    `N/A`           COMPLETE. Validated via end-to-end integration testing.

`migrate_experiment.ps1`                `N/A`           COMPLETE. Validated via the scripted end-to-end integration
                                                        test (Layer 5), which confirms the script correctly handles a
                                                        severely corrupted experiment and produces a valid, repaired output.

**PowerShell Wrappers (Studies)**

`evaluate_study.ps1`                    `N/A`           PENDING. Manual validation is pending.

`new_study.ps1`                         `N/A`           PENDING. Manual validation is pending.

`audit_study.ps1`                       `N/A`           PENDING. Manual validation is pending.

`fix_study.ps1`                         `N/A`           PENDING. Manual validation is pending.

`migrate_study.ps1`                     `N/A`           PENDING. Manual validation is pending.
-----------------------------------------------------------------------------------------------------------------------------------------