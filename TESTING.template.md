# Testing Strategy for the LLM Personality Matching Project

This document outlines the testing philosophy, procedures, and coverage strategy for the framework. It serves as a guide for developers and a record of the project's quality assurance standards.

{{toc}}

## A Guide to Manual & Integration Testing

The project's validation strategy is built on a two-part philosophy that separates the validation of the core scientific methodology from the validation of the software's execution flow.

1.  **Core Algorithm Validation**: A set of standalone, high-precision tests that provide scientific proof for the framework's core methodological claims (e.g., bit-for-bit accuracy, statistical integrity at scale).
2.  **Lifecycle & Pipeline Validation**: A comprehensive, layered system that validates the end-to-end integrity of the software's execution flow, from the linear data pipeline to the cyclical experiment lifecycles.

This distinction ensures that we can independently verify that our *method is sound* and that our *implementation of that method is robust*.

{{diagram:docs/diagrams/test_philosophy_overview.mmd | scale=2.5 | width=100% | caption=The Two-Part Testing Philosophy: Separating the validation of the core scientific methodology from the software's execution flow.}}

### Core Algorithm Validation

This category includes standalone, high-precision tests designed to verify the scientific and logical integrity of the framework's most critical components. These tests are not part of the sequential 7-layer workflow but are essential for proving the validity of the experimental design.

#### Personality Assembly Algorithm

This is the project's most rigorous validation. It is a two-part process that combines a semi-automated **workflow** for generating a ground-truth dataset with a fully automated **test** that verifies our algorithm against it.

##### Part 1: The Ground Truth Generation Workflow

This is a developer-run, five-step workflow that uses the source expert system (Solar Fire) to generate a "ground truth" version of the personality database. This process is essential for creating the validation asset that the automated test relies on.

-   **Purpose:** To create a definitive, bit-for-bit accurate dataset for comparison.
-   **Location:** The scripts for this workflow are located in `scripts/workflows/assembly_logic/`.
-   **Guide:** The complete, step-by-step process is documented in the **[⚙️ Assembly Logic Workflow Guide](scripts/workflows/assembly_logic/README_ASSEMBLY.md)**.

##### Part 2: The Automated Verification Test

This is a standalone, push-button `pytest` script that provides the final scientific proof. It compares the output of our Python script (`generate_personalities_db.py`) against the pre-computed ground truth file from Part 1.

-   **Run the full test:**
    This test runs automatically as part of the main `pdm run test` suite. To run it in isolation:
    ```bash
    pdm run test-assembly
    ```
-   **Test a single record:**
    The test harness includes a flexible command-line option for focused debugging.
    ```bash
    # Test the 3rd record in the ground-truth set
    pdm run test-assembly -- --test-record-number=3
    ```

#### Large-Scale Selection Algorithms

This is a standalone test (`validate_selection_algorithms.ps1`) that validates the core data filtering and selection algorithms at a realistic scale. It uses a large, pre-generated dataset to verify the deterministic logic of `select_eligible_candidates.py` and the data-driven cutoff analysis in `select_final_candidates.py`.

-   **To run the test:**
    ```powershell
    pdm run test-l3-selection
    ```
-   **Prerequisites:**
    This test is optional and requires a one-time manual setup. You must place the required large-scale data assets in the `tests/assets/large_seed/` directory. If these files are not present, the test will be skipped automatically.

#### Query Generation & Randomization Integrity Test (Planned)

> **Note:** This is a planned validation test.

This standalone test will provide mathematical proof of the mapping and randomization logic in `query_generator.py`. The test will run the script in a loop to generate a large sample of trial manifests for both `correct` and `random` strategies. It will then perform statistical validation to confirm the `random` strategy approximates a uniform distribution and that the `correct` strategy is implemented as designed.

#### Statistical Analysis & Reporting Validation (Planned)

> **Note:** This is a planned validation test.

This standalone test will provide bit-for-bit verification of the entire data analysis and aggregation pipeline. The test will use a static, pre-generated set of mock LLM response files as input, run the full sequence of analysis and compilation scripts, and compare the final `STUDY_results.csv` and report JSON against a pre-computed, known-good ground truth.

### Lifecycle & Pipeline Validation (The 7 Layers)

This category uses a multi-layered strategy to ensure the correctness of the framework's end-to-end execution flow at all levels, from individual scripts to full data and experiment pipelines.

{{diagram:docs/diagrams/test_strategy_overview.mmd | scale=2.5 | width=100% | caption=The Seven Layers of Workflow Validation: A hierarchical strategy for testing the framework's execution pipelines.}}

#### Test Assets (`tests/assets/`)

All integration tests (Layers 3 and higher) rely on a set of static, version-controlled data assets to ensure they run in a predictable and isolated environment, completely decoupled from any user's locally generated data. These assets are organized within the `tests/assets/` directory.

-   **`tests/assets/data/`**: This is the primary directory for test assets. Its structure deliberately mirrors the main project `data/` folder for consistency. It contains a minimal, stable set of foundational files required for the test suite to run, such as `country_codes.csv`, the pre-neutralized delineation library, and sample Solar Fire chart exports. These files are part of the repository and are set up automatically when you clone the project.

-   **`tests/assets/large_seed/`**: This directory is used for an optional, large-scale validation of the candidate selection logic (see the Layer 3 `default` profile for details). Its contents are generated artifacts and are **not** included in the repository. This directory must be populated manually by the developer to enable the specific test that uses it.

This distinction is why the documentation treats them differently. The core test assets in `tests/assets/data/` are small, essential for all tests, and committed to the repository; they are set up automatically with a `git clone`. The `large_seed` assets are large, optional, and intentionally excluded from version control; they require a documented manual setup step to enable the specific advanced test that relies on them.

#### The Seven Layers of Validation Table

| Layer | Name | Scope | Purpose |
| :--- | :--- | :--- | :--- |
| **1** | Unit Testing | Individual Python Scripts | Validates the internal logic of each script in isolation. |
| **2** | Orchestration Testing | Data Pipeline (`prepare_data.ps1`) | Validates the orchestrator's state machine logic using mock scripts. |
| **3** | Integration Testing | Data Pipeline (End-to-End) | Validates the full, live data preparation pipeline with a seed dataset. |
| **4** | Integration Testing | Experiment Creation | Validates the core `new -> audit -> fix` lifecycle for a single experiment. |
| **5** | Integration Testing | Experiment Migration | Validates the `migrate_experiment.ps1` workflow on a corrupted experiment. |
| **6** | Integration Testing | Study Compilation | Validates the `compile_study.ps1` workflow on pre-existing experiments. |
| **7** | Integration Testing | Study Creation | Validates the full `new_study.ps1` lifecycle from creation to repair. |

---

### General Developer Workflow

For developing or modifying any individual script, we follow a robust `Modify -> Unit Test -> Integration Test` pattern. This workflow demonstrates how the different testing layers are used together in practice, ensuring quality from the component level to the fully integrated pipeline.

**Stage 1: Modify**
Make the necessary code changes to the target Python script (e.g., `src/generate_eminence_scores.py` or `src/analyze_llm_performance.py`).

**Stage 2: Unit Test (Layer 1)**
After modifying the code, run the script's dedicated unit test suite to verify its internal logic and catch any regressions.
```powershell
# Run coverage for the specific test file
pdm run cov-file tests/data_preparation/test_generate_eminence_scores.py
```
If the unit tests fail, fix the script before proceeding to the next stage.

**Stage 3: Integration Test**
Once unit tests pass, perform an integration test to validate that the script functions correctly within its live pipeline. The specific procedure depends on which pipeline the script belongs to.

*   **For a Data Preparation Script:**
    This validation uses the **Layer 3 Integration Test**.
    1.  **Identify Step Number:** Find the step number of the script you modified in the `prepare_data.ps1` orchestrator's `$PipelineSteps` definition.
    2.  **Add Checkpoint:** Temporarily modify the Layer 3 test harness (`run_layer3_test.ps1`). Add the `-StopAfterStep` parameter to the `test-l3-default` PDM command, targeting the step *before* your modified script. For example, to test Step 5, you would stop after Step 4.
    3.  **Run Test:** Execute the test profile from the project root (`pdm run test-l3-default`).
    4.  **Verify & Clean Up:** The test will run up to your checkpoint. You can now manually run your modified script in the sandbox (`temp_test_environment/layer3_sandbox/`) and inspect the output. Once verified, simply remove the `-StopAfterStep` parameter from the test harness.

*   **For an Experiment Lifecycle Script:**
    This validation uses the **Layer 4 Integration Test**.
    1.  **Add Checkpoint:** Modify the script's primary Python orchestrator (e.g., `src/replication_manager.py`). Import `sys` and add `sys.exit(0)` immediately after the call to your modified script.
    2.  **Run Test:** Execute the full Layer 4 workflow (`layer4_step1_setup.ps1`, `layer4_step2_test_workflow.ps1`).
    3.  **Verify & Clean Up:** The test will run the experiment up to your checkpoint. Inspect the artifacts in `temp_test_environment/output/test_experiments/` to confirm correctness. Once verified, remove the `sys.exit(0)` from the orchestrator and run the Layer 4 cleanup script.

**A Note on Other Testing Layers**
While the workflow above is typical for single-script development, the other layers serve distinct, higher-level validation purposes:
-   **Layer 2** is used to validate the state-machine logic of the `prepare_data.ps1` orchestrator itself, using mock scripts.
-   **Layers 5, 6, and 7** are used to validate the complete, end-to-end workflows for migration, study compilation, and new study generation after all individual components have been tested.

---

### Layer 1: Python Unit Testing

This layer focuses on validating the internal logic of the Python scripts. The project uses `pytest` for unit tests, which are managed via PDM.

#### Running Automated Tests
The project includes a suite of PDM scripts for running tests, defined in `pyproject.toml`. The most common commands are summarized below for quick reference.

| Command | Description |
| :--- | :--- |
| **`pdm run test`** | **Primary Entry Point:** Runs all Python and PowerShell tests. |
| `pdm run cov` | Runs all tests with a console coverage report. |
| `pdm run test-l3-default` | Runs the **Layer 3** Integration test for the data pipeline (default profile). |
| `pdm run test-l3-bypass` | Runs the Layer 3 test with `bypass_candidate_selection` enabled. |
| `pdm run test-l3-interactive` | Runs the Layer 3 test in interactive "guided tour" mode. |
| `pdm run test-l3-selection` | Runs the **Large-Scale Algorithm Validation** for the selection logic. |
| `pdm run test-l4` | Runs the **Layer 4** Integration test for the experiment lifecycle. |
| `pdm run test-l5` | Runs the **Layer 5** Integration test for the migration workflow. |

### Layer 2: Data Pipeline Orchestration Testing (`prepare_data.ps1` with Mocks)

This procedure validates the state machine logic of the `prepare_data.ps1` orchestrator in isolation, using fast, lightweight mock scripts. It verifies that the script correctly sequences automated steps, pauses for manual steps, and resumes properly. The test is fully automated, self-contained, and runs in milliseconds.

The test script is "self-healing": it programmatically parses the real `prepare_data.ps1` to determine the correct sequence of steps and required output files, ensuring the test never becomes outdated as the pipeline evolves.

**To run the test:**
```powershell
pdm run test-l2
```
The script handles all setup, execution of the test scenarios (including simulating manual steps), and cleanup automatically.

---

> **Note:** The integration test procedures below (Layers 3 and higher) create a temporary `temp_test_environment` directory at the project root to run in a safe, isolated sandbox. These tests are non-destructive and will not modify your main project files.

> **Note on the Integration Test Sandbox:**
> The integration test procedures below (Layers 3 and higher) create a temporary `temp_test_environment` directory at the project root to run in a safe, isolated sandbox. These tests are non-destructive and will not modify your main project files.

{{diagram:docs/diagrams/test_sandbox_architecture.mmd | scale=2.5 | width=100% | caption=The Integration Test Sandbox Architecture: All integration tests run in a temporary, isolated environment, ensuring the main project data is never modified.}}

### Layer 3: Data Pipeline Integration Testing (`prepare_data.ps1`)

This procedure validates the real data preparation pipeline using a robust, profile-driven test harness. The harness uses a controlled seed dataset from `tests/assets/` to ensure complete test isolation. It tests the main `prepare_data.ps1` orchestrator as the System Under Test, covering all four pipeline stages from Data Sourcing to Profile Generation.

This layer is split into two distinct types of tests: a lightweight **Workflow Integration Test** that validates the pipeline's plumbing with a small dataset, and a **Large-Scale Algorithm Validation** that validates the scientific integrity of the core filtering and selection logic using a much larger, pre-generated dataset.

#### Workflow Integration Testing (`run_layer3_test.ps1`)
This procedure validates the real data preparation pipeline using a small, controlled seed dataset from `tests/assets/` to ensure complete test isolation. It tests the main `prepare_data.ps1` orchestrator as the System Under Test, covering all four pipeline stages from Data Sourcing to Profile Generation. All test runs are fully automated, including setup and cleanup. Upon completion, the test sandbox is automatically archived as a timestamped `.zip` file in `data/backup/` for post-mortem analysis.

All workflow tests are run via PDM scripts from the project root:

*   **Default Profile (`default`):**
    This is the standard test case. It runs the full pipeline with LLM-based candidate selection active and injects controlled validation failures to test the script's resilience.
    ```powershell
    pdm run test-l3-default
    ```

*   **Bypass Profile (`bypass`):**
    This profile tests the pipeline with the `bypass_candidate_selection` flag enabled, ensuring the LLM-scoring stages are correctly skipped.
    ```powershell
    pdm run test-l3-bypass
    ```

*   **Interactive Mode (Guided Tour):**
    This profile provides a step-by-step guided tour of the pipeline. The script will pause before executing each Python script, explain what it is about to do, and wait for you to press Enter. This is an excellent way for new contributors to learn how the data pipeline works.
    ```powershell
    pdm run test-l3-interactive
    ```

**Prerequisites:** A configured `.env` file in the project root with a valid API key is required for the `default` and `interactive` profiles.

#### Large-Scale Algorithm Validation (`validate_selection_algorithms.ps1`)
This is a standalone test that validates the core data filtering and selection algorithms at a realistic scale. It uses a large, pre-generated dataset to verify the logic of `select_eligible_candidates.py` and the data-driven cutoff analysis in `select_final_candidates.py`.

This test is optional and requires a one-time manual setup to provide the necessary large-scale data assets.

*   **To run the test:**
    ```powershell
    pdm run test-l3-selection
    ```
*   **Prerequisites:**
    You must manually place the following four files in the `tests/assets/large_seed/` directory:
    ```
    tests/assets/large_seed/
    └── data/
        ├── foundational_assets/
        │   ├── eminence_scores.csv
        │   └── ocean_scores.csv
        ├── reports/
        │   └── adb_validation_report.csv
        └── sources/
            └── adb_raw_export.txt
    ```
    These files can be obtained by running the full data preparation pipeline on a large dataset. If these files are not present, the test will be skipped automatically.

### Layer 4 Integration Testing: Experiment Creation

This procedure validates the core `new -> audit -> break -> fix` experiment lifecycle in a safe, isolated sandbox. It follows a clean `Setup -> Test -> Cleanup` pattern.

#### Step 1: Automated Setup
Run this script to create the test environment, including a sandboxed `config.ini` and a minimal dataset.
```powershell
.\tests\testing_harness\layer4_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
This script fully automates the `new -> audit -> break -> fix` lifecycle and verifies the final output.
```powershell
.\tests\testing_harness\layer4_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After inspecting the artifacts, run this script to delete the test sandbox and all generated experiment files.
```powershell
.\tests\testing_harness\layer4_step3_cleanup.ps1
```

### Layer 5 Integration Testing: Experiment Migration

This procedure validates the `migrate_experiment.ps1` workflow in a safe, isolated sandbox. It automatically creates a valid experiment, corrupts it, runs the migration, and validates the final, repaired output.

#### Step 1: Automated Setup
Run this script to create a sandboxed test environment and a deliberately corrupted experiment.
```powershell
.\tests\testing_harness\layer5_step1_setup.ps1
```

#### Step 2: Execute the Test Workflow
This script fully automates the `audit -> migrate -> validate` lifecycle and verifies the final repaired experiment.
```powershell
.\tests\testing_harness\layer5_step2_test_workflow.ps1
```

#### Step 3: Automated Cleanup
After inspecting the artifacts, run this script to delete the test sandbox and all generated experiment files.
```powershell
.\tests\testing_harness\layer5_step3_cleanup.ps1
```

### Layer 6 Integration Testing: Study Compilation (Planned)

> **Note:** This is a planned testing layer. The harness scripts will be created as part of the study-level workflow development.

This procedure will validate the workflow for creating a formal study from a collection of pre-existing, independent experiments using the `compile_study.ps1` script.

#### Step 1: Automated Setup
The setup script will create a study directory and populate it with two small, independently generated, valid experiments.

#### Step 2: Execute the Test Workflow
This script will run `compile_study.ps1` on the prepared study directory and verify that the final analysis artifacts (`STUDY_results.csv`, `anova/` directory) are created successfully.

#### Step 3: Automated Cleanup
The cleanup script will delete the entire test study directory and restore the project's base files.

### Layer 7 Integration Testing: Study Creation (Planned)

> **Note:** This is a planned testing layer. The harness scripts will be created after the `new_study.ps1` script is developed.

This procedure will validate the entire lifecycle for a study generated from scratch using the `new_study.ps1` orchestrator.

#### Step 1: Automated Setup
The setup script will create a test-specific `config.ini` that includes the `[StudyFactors]` section, configured to generate a small study of two experiments.

#### Step 2: Execute the Test Workflow
This script will validate the full `create -> audit -> break -> fix` lifecycle for a study:
1.  **Create:** Run `new_study.ps1` to generate the test study.
2.  **Audit & Verify:** Run `audit_study.ps1` to confirm the new study is `VALIDATED`.
3.  **Break:** Deliberately break one of the experiments within the study.
4.  **Audit & Fix:** Run `audit_study.ps1` (to confirm the broken state) and then `fix_study.ps1` to repair it.
5.  **Final Verification:** Run `audit_study.ps1` a final time to confirm the study is `VALIDATED` again.

#### Step 3: Automated Cleanup
The cleanup script will delete the test study directory and restore the project.

## Testing Status

This section provides a summary of the validation status for both the high-level integration test layers and the individual code modules.

### Lifecycle & Pipeline Validation Layers

**Milestone Complete:** All core integration test layers for the data preparation pipeline (Layers 2-3) are complete and passing.

--------------------------------------------------------------------------------------------------------------------
Layer                               Name                        Status & Justification
----------------------------------- --------------------------- -----------------------------------------------------------------
**2**                               Data Pipeline               COMPLETE. Validated by a fast, self-healing test harness that 
                                    Orchestration               uses mock scripts to verify the orchestrator's state machine 
                                                                logic.

**3**                               Data Pipeline Integration   COMPLETE. Validated by a robust, profile-driven test harness that
                                                                runs the full, live pipeline in an isolated sandbox with a 
                                                                controlled seed dataset.

**4**                               Experiment Creation         PLANNED. The scripted test harness will validate the full 
                                                                `new -> audit -> break -> fix` lifecycle in an isolated sandbox.
                                                                

**5**                               Experiment Migration        PLANNED. Will be validated by a scripted test harness that 
                                                                creates, deliberately corrupts, and then successfully migrates a 
                                                                test experiment.

**6**                               Study Compilation           PLANNED. The test harness will validate the `compile_study.ps1`
                                                                workflow using a set of pre-generated, valid experiments.

**7**                               Study Creation              PLANNED. The test harness will validate the full lifecycle for a
                                                                study generated by `new_study.ps1`, including creation, auditing,
                                                                and repair.
--------------------------------------------------------------------------------------------------------------------

### Code Coverage Targets

To ensure the framework's reliability, we have established tiered code coverage targets based on the criticality of each module. These targets guide our testing efforts and provide a clear quality standard.

| Module Tier | Description                                                                                                                            | Coverage Target |
| :---------- | :------------------------------------------------------------------------------------------------------------------------------------- | :-------------- |
| **Critical**  | Core orchestrators, state-detection logic, and data validation/parsing modules whose failure could lead to data corruption or invalid scientific results. | **90%+**        |
| **Standard**  | Individual scripts within a pipeline that perform a discrete, well-defined task.                                                       | **80%+**        |
| **Utility**   | Shared helper modules, such as configuration loaders, that are foundational to many other scripts.                                       | **85%+**        |

PowerShell wrapper scripts are not measured by Python code coverage; their correctness is validated through the multi-layered integration tests (Layers 2-7).

### Module-Level Test Coverage: Data Preparation

In the tables below, modules designated as **Critical** are indicated with **bold text**.

**Milestone Complete:** All layers of testing for the data preparation pipeline (Core Algorithm, Unit, Orchestration, and Integration) are complete and passing. The status of individual components is detailed below.

--------------------------------------------------------------------------------------------------------------------
Module                              Cov. (%)        Status & Justification
----------------------------------- --------------- -----------------------------------------------------------------
**Core Algorithm Validation**

**`Personality Assembly Algorithm`**    `N/A`           COMPLETE. Standalone `pytest` suite provides bit-for-bit
                                                    validation of `generate_personalities_db.py` against a
                                                    pre-computed ground-truth dataset from the source expert system.

**`Selection Algorithms`**              `N/A`           COMPLETE. Standalone test harness validates the core filtering
                                                    and cutoff algorithms at scale using a large, pre-generated
                                                    seed dataset in an isolated sandbox.

**`Query Generation Algorithm`**        `N/A`           PLANNED. Standalone test to provide mathematical proof of the
                                                    mapping and randomization logic in `query_generator.py`.

**`Statistical Reporting Algorithm`**   `N/A`           PLANNED. Standalone test to provide bit-for-bit verification
                                                    of the entire data analysis and aggregation pipeline against a
                                                    known-good ground truth dataset.

**Stage 1: Data Sourcing**

`src/fetch_adb_data.py`             `84%`           COMPLETE. Unit tests cover all critical offline logic (data
                                                    parsing, timezone conversion) and use mocks to validate the main
                                                    workflow, including login, scraping, and pagination.

**Stage 2: Candidate Qualification**

`src/find_wikipedia_links.py`       `77%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    all helper functions, and critical error handling for input
                                                    validation, worker timeouts, and mocked API calls.

`src/validate_wikipedia_pages.py`   `82%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    all helper functions, and critical error handling for input
                                                    validation, network resiliency, and report generation.

`src/select_eligible_candidates.py` `84%`           COMPLETE. Comprehensive unit tests validate all core filtering,
                                                    deduplication, and resumability logic, including error
                                                    handling for stale and missing input files.

**Stage 3: LLM-based Selection**

`src/generate_eminence_scores.py`   `75%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    offline parsing, and critical error handling (stale data,
                                                    missing inputs, worker failures). Live LLM calls are validated
                                                    via integration testing.

`src/generate_ocean_scores.py`      `79%`           COMPLETE. Unit tests cover the main processing loop,
                                                    resumability, error handling, and the offline summary
                                                    regeneration feature.

`src/select_final_candidates.py`    `80%`           COMPLETE. Unit tests cover the entire data transformation
                                                    workflow for both default and bypass modes, including the
                                                    variance-based cutoff analysis.

**Stage 4: Profile Generation**

`src/prepare_sf_import.py`          `86%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    core data transformation, and error handling for stale data,
                                                    missing inputs, and invalid records.

`src/create_subject_db.py`          `76%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    core data integration, and error handling for stale data,
                                                    missing inputs, and mismatched subjects.

`src/neutralize_delineations.py`    `74%`           COMPLETE. Unit test suite validates the core orchestration
                                                    logic for default, fast, resume, and bypass modes, as well as
                                                    error handling.

**`src/generate_personalities_db.py`**  `87%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    core data assembly algorithm, and error handling for stale
                                                    data, missing inputs, and single-record debug runs.

**`prepare_data.ps1`**                  `N/A`           COMPLETE. As the primary orchestrator, this script is validated
                                                    at two layers. The **Layer 2** test uses mock scripts to validate
                                                    its core state machine and halt/resume logic. The **Layer 3**
                                                    integration test validates the full, live pipeline, including its
                                                    interactive and bypass features, using a profile-driven test harness.

--------------------------------------------------------------------------------------------------------------------

### Module-Level Test Coverage: Experiment Lifecycle & Analysis

The following table details the testing status for each script in the main experimental and analysis workflows.

-----------------------------------------------------------------------------------------------------------------------------------------
Module                                  Cov. (%)        Status & Justification
--------------------------------------- --------------- ----------------------------------------------------------------------------------
**EXPERIMENT LIFECYCLE MANAGEMENT**
**Primary Orchestrators**

**`src/experiment_manager.py`**             `80%`           COMPLETE. Comprehensive unit tests validate the core state
                                                        machine, all helper functions, argument parsing, and critical
                                                        failure paths. The end-to-end `new`/`audit`/`fix` workflows are
                                                        validated by the Layer 4 integration test.

**`src/experiment_auditor.py`**             `89%`           COMPLETE. The unit test suite validates the auditor's
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

**`src/replication_manager.py`**            `95%`           COMPLETE. The script was refactored for testability by
                                                        extracting the `session_worker` to the module level. This
                                                        enabled a simple, reliable testing strategy using direct
                                                        patching, replacing complex and brittle `ThreadPoolExecutor`
                                                        mocks. The test suite now robustly covers the core control
                                                        flow, all failure modes, and edge cases.

**Pipeline Stages**

`src/build_llm_queries.py`              `68%`           COMPLETE. Unit tests cover the core orchestration logic,
                                                        including new runs, continued runs, and key failure modes.

`src/query_generator.py`                `74%`           COMPLETE. Unit tests cover both 'correct' and 'random'
                                                        mapping strategies, edge cases (e.g., k=max), and key
                                                        failure modes like missing or insufficient input data.

`src/llm_prompter.py`                   `81%`           COMPLETE. Comprehensive unit tests validate the core API call
                                                        logic, all major failure modes (HTTP errors, timeouts,
                                                        malformed JSON, `KeyboardInterrupt`), file I/O contracts,
                                                        standalone interactive mode, and the internal testing hooks.
**`src/process_llm_responses.py`**          `95%`           COMPLETE. Comprehensive unit tests validate all core parsing
                                                        and validation logic, including markdown, fallback, flexible
                                                        spacing, reordered columns, rank conversion, and a wide
                                                        range of failure modes for malformed LLM responses and
                                                        corrupted input files.

`src/analyze_llm_performance.py`        `78%`           COMPLETE. Comprehensive unit tests validate the main
                                                        orchestrator's control flow and early-exit conditions, all
                                                        core statistical calculations (including `IndexError` and
                                                        `ValueError` handling), meta-analysis functions for combining
                                                        p-values, and the robust parsing of all input file formats.

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

`src/compile_study_results.py`          `70%`           COMPLETE. Unit tests cover the recursive aggregation
                                                        workflow and robustly handle edge cases like empty or missing
                                                        experiment files.

`src/analyze_study_results.py`          `62%`           COMPLETE. The unit test suite fully validates the script's
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

**`src/config_loader.py`**                  `86%`           COMPLETE. Comprehensive unit tests validate all aspects of
                                                        value retrieval, including type conversions (int, float, bool,
                                                        str), fallbacks, `fallback_key` handling, inline comment
                                                        stripping, list parsing, section-to-dict conversion, and
                                                        sandbox path resolution. Error logging for invalid types is
                                                        also covered.

**PowerShell Wrappers (Experiments)**

`new_experiment.ps1`                    `N/A`           COMPLETE. Validated via end-to-end integration testing.

`audit_experiment.ps1`                  `N/A`           COMPLETE. Validated via end-to-end integration testing.

`fix_experiment.ps1`                    `N/A`           COMPLETE. Validated via end-to-end integration testing.

`migrate_experiment.ps1`                `N/A`           COMPLETE. Validated via the scripted end-to-end integration
                                                        test (Layer 5), which confirms the script correctly handles a
                                                        severely corrupted experiment and produces a valid, repaired output.

`compile_study.ps1`                     `N/A`           PENDING. Manual validation is pending.

**PowerShell Wrappers (Studies)**

`new_study.ps1`                         `N/A`           PENDING. Manual validation is pending.

`audit_study.ps1`                       `N/A`           PENDING. Manual validation is pending.

`fix_study.ps1`                         `N/A`           PENDING. Manual validation is pending.

`migrate_study.ps1`                     `N/A`           PENDING. Manual validation is pending.
-----------------------------------------------------------------------------------------------------------------------------------------