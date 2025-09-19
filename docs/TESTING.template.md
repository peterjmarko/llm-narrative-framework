# Testing Strategy for the LLM Personality Matching Project

This document outlines the testing philosophy, procedures, and coverage strategy for the framework. It serves as a guide for developers and a record of the project's quality assurance standards.

{{toc}}

## Testing Philosophy

The project's testing strategy is organized into a clear, three-part hierarchy designed to ensure both scientific validity and software robustness. This approach allows for rigorous, independent verification at every level of the framework.

1.  **Unit Testing:** Focuses on the internal logic of individual Python scripts, validating each component in isolation.
2.  **Core Algorithm Validation:** A set of standalone, high-precision tests that provide scientific proof for the framework's core methodological claims (e.g., bit-for-bit accuracy of data generation, statistical integrity of analysis).
3.  **Pipeline & Workflow Integration Testing:** A suite of end-to-end tests that validate the complete, live execution flows for the project's two main functional domains: the data preparation pipeline and the experiment/study lifecycle.

This structure ensures that we can verify that our individual components are correct (Unit Testing), our scientific method is sound (Algorithm Validation), and our implementation of that method is robust when all parts are working together (Integration Testing).

{{diagram:docs/diagrams/test_strategy_overview.mmd | scale=2.5 | width=100% | caption=The Three Pillars of the Testing Strategy: A hierarchical approach to validating the framework.}}

### Core Algorithm Validation

This category includes standalone, high-precision tests designed to verify the scientific and logical integrity of the framework's most critical components. These tests are not part of the sequential 7-layer workflow but are essential for proving the validity of the experimental design.

#### Personality Assembly Algorithm

This is the project's most rigorous validation. It is a two-part process that combines a semi-automated workflow for generating a ground-truth dataset with a fully automated test that verifies our algorithm against it.

##### Part 1: The Ground Truth Generation Workflow

This is a developer-run, five-step workflow that uses the source expert system (Solar Fire) to generate a "ground truth" version of the personality database. This process is essential for creating the validation asset that the automated test relies on. The scripts for this workflow are located in `scripts/workflows/assembly_logic/` and must be run in the numbered order.

1.  **`1_generate_coverage_map.py`**: Pre-computes which delineation keys are triggered by each subject.
2.  **`2_select_assembly_logic_subjects.py`**: Uses a greedy algorithm to select the smallest set of subjects that provides maximum coverage of all delineation keys.
3.  **`3_prepare_assembly_logic_import.py`**: Formats the selected subjects for manual import into the Solar Fire software.
4.  **Manual Step**: The developer imports the file into Solar Fire, runs the "Interpretation Reports" for all subjects, and saves the raw text output.
5.  **`4_extract_assembly_logic_text.py`**: Parses the raw reports from Solar Fire and assembles the final `personalities_db.assembly_logic.txt` ground-truth file.
6.  **`5_validate_assembly_logic_subjects.py`** (Optional): An integrity check to confirm the manual import/export process was lossless.

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

#### Query Generation & Randomization Integrity Test

This standalone test provides mathematical proof of the mapping and randomization logic in `query_generator.py`. The test is composed of two scripts that work in tandem:

1.  **`validate_query_generation.ps1` (The Harness):** The user-facing entry point. It prepares a sandbox and calls `query_generator.py` in a loop to generate a statistically significant sample of manifest files.
2.  **`analyzers/analyze_query_generation_results.py` (The Analyzer):** A worker script called by the harness. It inspects the generated files to validate two core properties:
    *   **Determinism:** That the `correct` strategy produces bit-for-bit identical outputs when given the same random seed.
    *   **Non-Determinism:** That the `random` strategy produces different outputs across multiple runs.

**Statistical Rigor:** The test is parameterized by statistical power. The user specifies the acceptable Type II error rate (`-Beta`), and the harness automatically calculates the required number of iterations `N` to achieve the corresponding statistical power (1 - `Beta`). This ensures that the non-determinism check is statistically sound.

-   **To run the test:**
    ```powershell
    # Run with default 99.9999% power (Beta = 0.000001), which requires 9 iterations for k=3.
    pdm run test-query-gen

    # Run with a custom 99.9% power (Beta = 0.001), which requires 5 iterations.
    pdm run test-query-gen -Beta 0.001
    ```
-   **Prerequisites:**
    This test depends on asset files that are **automatically generated** by the Layer 3 integration test. On a fresh clone, you must run `pdm run test-l3-default` once to bootstrap these assets. If the assets are not present, the test will be skipped.

#### Statistical Analysis & Reporting Validation

This is a standalone test (`validate_statistical_reporting.ps1`) that provides bit-for-bit verification of the entire data analysis and aggregation pipeline. The test uses a static, pre-generated set of mock LLM response files as input, runs the full sequence of analysis and compilation scripts, and compares the final `STUDY_results.csv` and report JSON against a pre-computed, known-good ground truth.

-   **To run the test:**
    ```powershell
    pdm run test-stats-reporting
    ```
-   **Prerequisites:**
    This test is optional and requires a one-time manual setup. You must place the required mock experiment assets in the `tests/assets/mock_study/` directory. If these files are not present, the test will be skipped automatically.

### Unit Testing

This foundational layer focuses on validating the internal logic of individual Python scripts. The project uses `pytest` for all unit tests, which are managed via PDM.

#### Running Automated Tests
The project includes a suite of PDM scripts for running tests, defined in `pyproject.toml`. The most common commands are summarized below for quick reference.

| Command | Description |
| :--- | :--- |
| **`pdm run test`** | **Primary Entry Point:** Runs all Python and PowerShell tests. |
| `pdm run cov` | Runs all tests with a console coverage report. |
| `pdm run test-cov-report` | Runs a specific test file and generates a focused coverage report for its source file. |
| `pdm run test-l3-default` | Runs the **Layer 3** Integration test for the data pipeline (default profile). |
| `pdm run test-l3-bypass` | Runs the Layer 3 test with `bypass_candidate_selection` enabled. |
| `pdm run test-l3-interactive` | Runs the Layer 3 test in interactive "guided tour" mode. |
| `pdm run test-l3-selection` | Runs the **Large-Scale Algorithm Validation** for the selection logic. |
| `pdm run test-query-gen` | Runs the **Query Generation Algorithm Validation**. |
| `pdm run test-stats-reporting` | Runs the **Statistical Reporting Algorithm Validation**. |
| `pdm run test-l4` | Runs the **Layer 4** Integration test for the experiment lifecycle. |
| `pdm run test-l5` | Runs the **Layer 5** Integration test for the migration workflow. |

### Pipeline & Workflow Integration Testing

This category includes end-to-end tests that validate the complete, live execution flows for the project's two main functional domains. All integration tests create a temporary `temp_test_environment` directory at the project root to run in a safe, isolated sandbox. These tests are non-destructive and will not modify your main project files.

{{diagram:docs/diagrams/test_sandbox_architecture.mmd | scale=2.5 | width=100% | caption=The Integration Test Sandbox Architecture: All integration tests run in a temporary, isolated environment.}}

#### Data Preparation Pipeline

This procedure validates the real data preparation pipeline using a robust, profile-driven test harness. The harness uses a controlled seed dataset from `tests/assets/` to ensure complete test isolation. The main `prepare_data.ps1` orchestrator is the System Under Test.

The test validates the orchestrator's state machine logic in two ways: first with fast, lightweight mock scripts to test halt/resume logic (`pdm run test-l2`), and then with the full, live pipeline to test all four stages from Data Sourcing to Profile Generation.

All workflow tests are run via PDM scripts from the project root:

*   **Default Profile (`default`):**
    This is the standard test case. It runs the full pipeline with LLM-based candidate selection active.
    ```powershell
    pdm run test-l3-default
    ```

*   **Bypass Profile (`bypass`):**
    This profile tests the pipeline with the `bypass_candidate_selection` flag enabled.
    ```powershell
    pdm run test-l3-bypass
    ```

*   **Interactive Mode (Guided Tour):**
    This profile provides a step-by-step guided tour of the data pipeline.
    ```powershell
    pdm run test-l3-interactive
    ```

**Prerequisites:** A configured `.env` file is required for the `default` and `interactive` profiles.

#### Experiment & Study Lifecycle

This category validates the end-to-end workflows for creating experiments and compiling them into a final study.

##### Experiment Creation (`new -> audit -> fix`)

This procedure validates the core `new -> audit -> break -> fix` experiment lifecycle for a single experiment in an isolated sandbox. It follows a clean `Setup -> Test -> Cleanup` pattern.

*   **Step 1: Automated Setup**
    ```powershell
    .\tests\testing_harness\layer4_step1_setup.ps1
    ```
*   **Step 2: Execute the Test Workflow**
    ```powershell
    .\tests\testing_harness\layer4_step2_test_workflow.ps1
    ```
*   **Step 3: Automated Cleanup**
    ```powershell
    .\tests\testing_harness\layer4_step3_cleanup.ps1
    ```

##### Study Compilation (Planned)

> **Note:** This is a planned test harness.

This procedure will validate the `compile_study.ps1` workflow. The test will create a mock study directory, populate it with pre-generated valid experiment artifacts, run the compilation script, and verify that the final analysis outputs are created correctly.

## Testing Status

This section provides a summary of the project's validation status.

### High-Level Validation Status

| Test Category | Workflow | Status & Justification |
| :--- | :--- | :--- |
| **Integration** | Data Preparation Pipeline | **COMPLETE.** Validated by a robust, profile-driven test harness that runs the full, live pipeline in an isolated sandbox with a controlled seed dataset. |
| | Experiment Lifecycle | **COMPLETE.** Validated by Layer 4 integration tests that execute the full `new -> audit -> break -> fix` lifecycle in an isolated sandbox environment. Tests creation, validation, deliberate corruption, automated repair, and final verification of experiment integrity. |
| | Study Compilation | **PLANNED.** The test harness will validate the `compile_study.ps1` workflow using a set of pre-generated, valid experiments. |

### Code Coverage Targets

To ensure the framework's reliability, we have established tiered code coverage targets based on the criticality of each module. These targets guide our testing efforts and provide a clear quality standard.

| Module Tier         | Description                                                                                                                            | Coverage Target     |
| :------------------ | :------------------------------------------------------------------------------------------------------------------------------------- | :------------------ |
| **Critical**  | Core orchestrators, state-detection logic, and data validation/parsing modules whose failure could lead to data corruption or invalid scientific results. | **90%+**        |
| **Standard**  | Individual scripts within a pipeline that perform a discrete, well-defined task.                                                       | **80%+**        |
| **Utility**   | Shared helper modules, such as configuration loaders, that are foundational to many other scripts.                                       | **85%+**        |

PowerShell wrapper scripts are not measured by Python code coverage; their correctness is validated through the end-to-end integration tests.

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

**`Query Generation Algorithm`**        `N/A`           COMPLETE. Standalone test provides mathematical proof of the
                                                    mapping and randomization logic. It validates that the 'random'
                                                    strategy is non-deterministic and that the 'correct' strategy is
                                                    deterministic when provided with a fixed seed.

**`Statistical Reporting Algorithm`**   `N/A`           PLANNED. Standalone test to provide bit-for-bit verification
                                                    of the entire data analysis and aggregation pipeline against a
                                                    known-good ground truth dataset.

**Stage 1: Data Sourcing**

`src/fetch_adb_data.py`             `84%`           COMPLETE. Unit tests cover all critical offline logic (data
                                                    parsing, timezone conversion) and use mocks to validate the main
                                                    workflow, including login, scraping, and pagination.

**Stage 2: Candidate Qualification**

`src/find_wikipedia_links.py`       `80%`           COMPLETE. Target met. Unit test suite expanded to validate
                                                    the main workflow, all helper functions, and robustly handle
                                                    edge cases for file I/O, API failures, timeouts, and malformed
                                                    input data.

`src/validate_wikipedia_pages.py`   `82%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    all helper functions, and critical error handling for input
                                                    validation, network resiliency, and report generation.

`src/select_eligible_candidates.py` `84%`           COMPLETE. Comprehensive unit tests validate all core filtering,
                                                    deduplication, and resumability logic, including error
                                                    handling for stale and missing input files.

**Stage 3: LLM-based Selection**

`src/generate_eminence_scores.py`   `87%`           COMPLETE. Target met. Unit test suite expanded to validate
                                                    the main workflow, all helper functions, and robustly handle
                                                    edge cases for file I/O, API failures, user-driven workflow
                                                    paths (force, stale, bypass), and summary report generation.

`src/generate_ocean_scores.py`      `82%           COMPLETE. Target met. Unit test suite expanded to validate
                                                    the main workflow, all helper functions, and robustly handle
                                                    edge cases for file I/O, API failures, user-driven workflow
                                                    paths (force, stale, bypass), and summary report generation.

`src/select_final_candidates.py`    `80%`           COMPLETE. Unit tests cover the entire data transformation
                                                    workflow for both default and bypass modes, including the
                                                    variance-based cutoff analysis.

**Stage 4: Profile Generation**

`src/prepare_sf_import.py`          `86%`           COMPLETE. Comprehensive unit tests validate the main workflow,
                                                    core data transformation, and error handling for stale data,
                                                    missing inputs, and invalid records.

`src/create_subject_db.py`          `92%`           COMPLETE. Target met. Unit test suite expanded to validate
                                                    all major data integration logic, including Base58 ID decoding,
                                                    robust error handling for malformed chart data and candidate
                                                    files, and all user-driven workflow paths (force, stale, cancel).

`src/neutralize_delineations.py`    `91%`           COMPLETE. Target met. Unit test suite expanded to validate
                                                    core orchestration, all helper functions (parsing, grouping,
                                                    sorting), and robustly handle edge cases for file I/O, API
                                                    failures, and user-driven workflow paths.

**`src/generate_personalities_db.py`**  `90%`           COMPLETE. Target met. Comprehensive unit tests validate the
                                                    main workflow, core data assembly algorithm, and error handling
                                                    for stale data, missing inputs, and single-record debug runs.

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

**`src/experiment_manager.py`**             `95%`           COMPLETE. Comprehensive unit tests validate the core state
                                                        machine, all helper functions, argument parsing, and critical
                                                        failure paths. The end-to-end `new`/`audit`/`fix` workflows are
                                                        validated by the Layer 4 integration test.

**`src/experiment_auditor.py`**             `95%`           COMPLETE. Target met. The comprehensive unit test suite
                                                        validates the auditor's ability to correctly identify all
                                                        major experiment states (e.g., Complete, Repair Needed,
                                                        Migration Needed) by using a mocked file system to
                                                        simulate various data completeness scenarios.

**Finalization Scripts**

`src/manage_experiment_log.py`          `87%`           COMPLETE. Target met. The unit test suite was expanded to
                                                        validate all core commands (`rebuild`, `finalize`, `start`)
                                                        and robustly handle edge cases, including malformed report
                                                        files, missing data, and invalid log file states.

`src/compile_experiment_results.py`     `89%`           COMPLETE. Target met. Unit test suite expanded to cover
                                                        all major error handling paths (e.g., non-existent dirs,
                                                        malformed CSVs, missing config) and edge cases for data
                                                        aggregation.

**SINGLE REPLICATION PIPELINE**
**Primary Orchestrator**

**`src/replication_manager.py`**            `95%`           COMPLETE. The script was refactored for testability by
                                                        extracting the `session_worker` to the module level. This
                                                        enabled a simple, reliable testing strategy using direct
                                                        patching, replacing complex and brittle `ThreadPoolExecutor`
                                                        mocks. The test suite now robustly covers the core control
                                                        flow, all failure modes, and edge cases.

**Pipeline Stages**

`src/build_llm_queries.py`              `84%`           COMPLETE. Target met. The test suite was expanded to validate
                                                        argument parsing, error handling for invalid states (e.g.,
                                                        k > n), and the correct cleanup of temporary directories
                                                        and files for both new and continued runs.

`src/query_generator.py`                `80%`           COMPLETE. Target met. Unit tests cover both 'correct' and
                                                        'random' mapping strategies, argument parsing, all major
                                                        error handling paths (e.g., invalid k, file I/O errors),
                                                        and edge cases for file content.

`src/llm_prompter.py`                   `81%`           COMPLETE. Comprehensive unit tests validate the core API call
                                                        logic, all major failure modes (HTTP errors, timeouts,
                                                        malformed JSON, `KeyboardInterrupt`), file I/O contracts,
                                                        standalone interactive mode, and the internal testing hooks.
**`src/process_llm_responses.py`**          `95%`           COMPLETE. Comprehensive unit tests validate all core parsing
                                                        and validation logic, including markdown, fallback, flexible
                                                        spacing, reordered columns, rank conversion, and a wide
                                                        range of failure modes for malformed LLM responses and
                                                        corrupted input files.

**`src/analyze_llm_performance.py`**        `83%`           COMPLETE. Target met. The unit test suite provides comprehensive
                                                        validation of the core statistical logic, file I/O contracts,
                                                        and data parsing. It covers all major failure modes and
                                                        validation edge cases, meeting the 80%+ standard target.

`src/run_bias_analysis.py`              `86%`           COMPLETE. Unit tests cover the main orchestrator workflow,
                                                        core bias calculations, and robust handling of empty or
                                                        malformed data files.

`src/generate_replication_report.py`    `90%`           COMPLETE. Target met. Unit tests cover the main workflow,
                                                        including robust error handling for missing/corrupted files
                                                        and correct fallback for optional data sources.

`src/compile_replication_results.py`    `91%`           COMPLETE. Target met. Unit test suite expanded to cover
                                                        all major error handling paths, including malformed JSON,
                                                        incomplete/legacy config files, and invalid run directory
                                                        structures.

**Study-Level & Analysis**

`src/compile_study_results.py`          `87%`           COMPLETE. Target met. The test suite was expanded to validate
                                                        all helper functions and orchestration logic, including data
                                                        aggregation, file I/O, and robust error handling for empty,
                                                        missing, or corrupted files.

`src/analyze_study_results.py`          `82%`           COMPLETE. Target met. The test suite was significantly
                                                        overhauled to fix bugs in the script's logging and post-hoc
                                                        logic. It now robustly covers data filtering, error handling,
                                                        and all major analysis code paths, meeting the 80%+ target.

**Utility & Other Scripts**

**`src/config_loader.py`**                  `86%`           COMPLETE. Comprehensive unit tests validate all aspects of
                                                        value retrieval, including type conversions (int, float, bool,
                                                        str), fallbacks, `fallback_key` handling, inline comment
                                                        stripping, list parsing, section-to-dict conversion, and
                                                        sandbox path resolution. Error logging for invalid types is
                                                        also covered.

**`src/id_encoder.py`**                     `100%`          COMPLETE. Target met. The test suite validates both encoding and decoding functions with known values, invalid inputs, and a round-trip conversion check to ensure perfect symmetry.

**`src/utils/file_utils.py`**               `100%`          COMPLETE. Target met. The test suite validates the `backup_and_remove` function for files, directories, and non-existent paths, ensuring it correctly logs output and handles exceptions gracefully.

**PowerShell Wrappers**

`new_experiment.ps1`                    `N/A`           PENDING. Will be validated by the planned integration test harness
                                                        for the experiment lifecycle.

`audit_experiment.ps1`                  `N/A`           PENDING. Will be validated by the planned integration test harness
                                                        for the experiment lifecycle.

`fix_experiment.ps1`                    `N/A`           PENDING. Will be validated by the planned integration test harness
                                                        for the experiment lifecycle.

`compile_study.ps1`                     `N/A`           PENDING. Will be validated by the planned integration test harness
                                                        for study compilation.
-----------------------------------------------------------------------------------------------------------------------------------------

### Module-Level Test Coverage: Developer & Utility Scripts

The following scripts are developer utilities used for maintenance, one-off analysis, or test asset generation. They are not part of the core, automated data pipeline. As per the project roadmap, creating unit test suites for these scripts is planned for after the initial publication.

-----------------------------------------------------------------------------------------------------------------------------------------
Module                                          Cov. (%)        Status & Justification
----------------------------------------------- --------------- ----------------------------------------------------------------------------------
**Test Asset Generation**
`scripts/workflows/assembly_logic/*.py`         `N/A`           PLANNED. These scripts are developer tools used to generate
                                                                a ground-truth test asset. Their functional correctness is
                                                                validated end-to-end by the Core Algorithm Validation test, but
                                                                unit tests for their internal logic are postponed.
**Utilities**
`src/utils/analyze_research_patterns.py`        `N/A`           PLANNED. Postponed until after publication.
`src/utils/patch_eminence_scores.py`            `N/A`           PLANNED. Postponed until after publication.
`src/utils/validate_country_codes.py`           `N/A`           PLANNED. Postponed until after publication.

**Analysis Scripts**
`scripts/analysis/analyze_cutoff_parameters.py` `N/A`           PLANNED. Postponed until after publication.
`scripts/analysis/get_docstring_summary.py`     `N/A`           PLANNED. Postponed until after publication.
`scripts/analysis/inspect_adb_categories.py`    `N/A`           PLANNED. Postponed until after publication.
`scripts/analysis/validate_import_file.py`      `N/A`           PLANNED. Postponed until after publication.

**Linting & Maintenance Scripts**
`scripts/lint/*.py`                             `N/A`           PLANNED. Postponed until after publication.
`scripts/maintenance/*.py`                      `N/A`           PLANNED. Postponed until after publication.
-----------------------------------------------------------------------------------------------------------------------------------------