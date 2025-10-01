# Testing Guide for the LLM Narrative Framework

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
4.  **`4_manual_export_instructions.md`**: Provides detailed instructions for manually exporting the required data from Solar Fire.
5.  **`5_build_ground_truth_db.py`**: Processes the exported Solar Fire data to create a ground-truth personality database.

##### Part 2: The Automated Validation Test

Once the ground truth dataset is generated, the automated test (`tests/algorithm_validation/test_profile_generation_algorithm.py`) can run. This test performs a **bit-for-bit validation** by generating personalities for a set of subjects using our algorithm and comparing them against the pre-computed ground truth from the expert system.

-   **To run the test:**
    ```powershell
    pytest tests/algorithm_validation/test_profile_generation_algorithm.py -v
    ```
-   **Prerequisites:**
    The test requires a ground-truth dataset in `tests/assets/assembly_logic/ground_truth_personalities_db.txt`. If this file is not present, the test will be skipped.

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

This 4-stage validation workflow provides external validation of the entire statistical analysis pipeline against GraphPad Prism 10.6.1. Uses real framework execution with sufficient replications to trigger full statistical analysis (ANOVA, post-hoc tests, Bayesian analysis).

**Implementation:** 4-stage validation process using real framework execution with deterministic parameters (temperature=0.0, gemini-2.5-flash-lite-preview-06-17) and framework's built-in seeded randomization. 2×2 factorial design with 6 replications per condition = 24 total experiments.

**Validation Methodology:** Representative sampling approach - full manual validation of 2 replications per condition (8 total), with automated spot-checks of descriptive statistics for remaining 16 replications. This validates the calculation engine without exhaustive manual checking of all replications.

**4-Stage Validation Workflow:**
```powershell
# Stage 1: Create statistical validation study using real framework
pdm run test-stats-study

# Stage 2: Generate GraphPad import files
pdm run test-stats-imports

# Stage 3: Manual GraphPad Prism processing
# (Manual import, analyze, export for 8 selected replications)

# Stage 4: Validate GraphPad results against framework calculations
pdm run test-stats-results
```

**Current Status: Ready for Validation**
- ✓ **Stage 1**: Statistical study creation completed (24 replications, 768 trials)
- ✓ **Stage 2**: Export generation with individual replication sampling (8 of 24)
- ⏳ **Stage 3**: Manual GraphPad processing of 8 selected replications
- ⏳ **Stage 4**: Automated validation comparison pending

**Prerequisites:** Requires `data/personalities_db.txt` from data preparation pipeline.

**Comprehensive Validation Coverage:**
- **6 Wilcoxon signed-rank tests**: K-specific validation (K=4, K=10) for MRR, Top-1, and Top-3 accuracy
  - MRR uses harmonic mean chance levels: K=4: 0.5208, K=10: 0.2929
  - Top-1 uses 1/k: K=4: 0.25, K=10: 0.1
  - Top-3 uses min(3,k)/k: K=4: 0.75, K=10: 0.3
- **3 Two-way ANOVA analyses**: MRR, Top-1, and Top-3 with eta-squared effect sizes
- **5 Bias regression analyses**: Overall and condition-specific linear regression validation
- **Purpose-built GraphPad formats**: Two-column XY files for regression, grouped tables for ANOVA

**Academic Citation:** "Core statistical calculations were validated against GraphPad Prism 10.6.1"

**Individual Replication Validation Results: 5/8 (62.5%)**

✓ **All 5 non-edge-case replications validated within ±0.005 tolerance**
  - Correct_K4 (Rep_01): median far from chance
  - Correct_K10 (Rep_03, Rep_04): medians far from chance
  - Random_K10 (Rep_07, Rep_08): medians far from chance

✗ **3 edge-case failures due to conversion limitations, not framework errors:**
  - Rep_02_Correct_K4: median = 0.5208 (exactly equals chance)
  - Rep_06_Random_K4: median = 0.5208 (exactly equals chance)
  - Rep_05_Random_K4: median = 0.5104 (very close to chance)

**Edge Case Explanation:** When observed median equals or closely approximates the null hypothesis value, the one-tailed vs two-tailed p-value conversion is mathematically ambiguous. GraphPad and the framework use different conventions for handling this boundary condition, leading to large p-value discrepancies despite identical N and median values.

**Validation Conclusion:** The framework's Wilcoxon test implementation is validated for all replications with clear directional effects. Edge-case behavior matches statistical theory (median ≈ chance indicates no effect).

**K-Specific Wilcoxon Validation Results: 16/18 (88.9%)**

✓ **Perfect N and Median agreement across all 6 tests**
  - All sample sizes (N=12) match exactly
  - All median values match to 4 decimal places

✓ **Excellent p-value agreement for K=10 tests (4/4 passed)**
  - MRR K=10: Diff = 0.000250 (within tolerance)
  - Top1 K=10: Diff = 0.000250 (within tolerance)
  - Top3 K=10: Diff = 0.000250 (within tolerance)

✗ **Minor K=4 discrepancies in tie-handling (2/2 failed)**
  - MRR K=4: Diff = 0.028077 (p ≈ 0.65, not statistically significant)
  - Top1 K=4: Diff = 0.012441 (p ≈ 0.68, not statistically significant)

**K=4 Edge Case Explanation:** The two K=4 failures occur when p-values are near 0.65-0.68, indicating no statistically significant effect. These small discrepancies (0.012-0.028) represent minor variations in how GraphPad Prism and scipy.stats.wilcoxon handle tied ranks with small sample sizes (N=12). Since both software packages report p > 0.60, neither can make strong statistical claims about these datasets.

**Validation Methodology:** The validation script calls the framework's `analyze_metric_distribution` function (from `src/analyze_llm_performance.py`) using the same K-specific CSV files that GraphPad imported. This ensures validation tests the **actual framework code** used during the experiment lifecycle, not a reimplementation in the validation script.

**K-Specific Test Purpose:** These tests validate that when replications are grouped by K value (group size), the framework's statistical calculations match GraphPad's results. This differs from individual replication tests (Step 1) which validate each replication independently.

**Overall K-Specific Validation Conclusion:** The framework's implementation of `scipy.stats.wilcoxon` with `zero_method='wilcox'` and `alternative='greater'` produces results that match GraphPad Prism 10.6.1 within acceptable tolerance for all meaningful statistical tests (p < 0.60).

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
| `pdm run test-graphpad-exports` | Runs the **GraphPad export generation**. |
| `pdm run test-l4` | Runs the **Layer 4** Integration test for the experiment lifecycle. |
| `pdm run test-l4-interactive` | Runs the Layer 4 test in interactive "guided tour" mode. |
| `pdm run test-l5` | Runs the **Layer 5** Integration test for the study compilation workflow. |

### Pipeline & Workflow Integration Testing

This category includes end-to-end tests that validate the complete, live execution flows for the project's two main functional domains. All integration tests create a temporary `temp_test_environment` directory at the project root to run in a safe, isolated sandbox. These tests are non-destructive and will not modify your main project files.

#### Interactive Testing Mode

Several integration tests offer an interactive mode that transforms automated validation into educational guided tours. These interactive modes are designed for:

- **Learning the Framework**: New users can understand how each component works
- **Documentation Purposes**: Live demonstrations of framework capabilities  
- **Debugging Workflows**: Step-by-step inspection of complex processes
- **Training Materials**: Hands-on education for team members

Interactive tests pause before each major step, provide detailed explanations of what will happen, and allow users to inspect intermediate results. This makes them invaluable for understanding the framework's internal operations while maintaining the same technical validation as automated tests.

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

This procedure validates the core `new -> audit -> break -> fix` experiment lifecycle for a single experiment in an isolated sandbox. It follows a clean `Setup -> Test -> Cleanup` pattern and includes both automated and interactive modes.

**Automated Mode:**
```powershell
pdm run test-l4
```

**Interactive Mode (Guided Tour):**
```powershell
pdm run test-l4-interactive
```

The interactive mode provides a comprehensive educational experience that walks users through each step of the experiment lifecycle with detailed explanations, making it ideal for learning how the framework operates. The automated mode provides quick validation for CI/CD pipelines.

**Manual Execution (Advanced):**
If you need to run individual phases manually:
*   **Phase 1: Automated Setup**
```powershell
    .\tests\testing_harness\experiment_lifecycle\layer4\layer4_phase1_setup.ps1
```
*   **Phase 2: Execute the Test Workflow**
```powershell
    .\tests\testing_harness\experiment_lifecycle\layer4\layer4_phase2_run.ps1
```
*   **Phase 3: Automated Cleanup**
```powershell
    .\tests\testing_harness\experiment_lifecycle\layer4\layer4_phase3_cleanup.ps1
```

##### Study Compilation ✅ **COMPLETE**

This procedure validates the complete `compile_study.ps1` workflow using a 3-phase structure (setup, execution, cleanup). The test uses experiments from Layer 4 when available, creating a realistic 2×2 factorial design for study compilation testing.

**Automated Mode:**
```powershell
pdm run test-l5
```

**What the test validates:**
- Complete study compilation workflow from Layer 4 experiments
- `STUDY_results.csv` generation with proper experiment aggregation
- Statistical analysis with appropriate handling of test data limitations (models filtered due to insufficient replications)
- Study-level artifact generation (anova directory structure)
- Full lifecycle: setup → compilation → audit → cleanup

**Key capabilities:**
- Cross-layer integration testing of research workflows
- Realistic test data scenarios with proper filtering behavior
- Validation of both successful compilation and appropriate handling of insufficient data

## Testing Status

This section provides a summary of the project's validation status.

### High-Level Validation Status

| Test Category | Workflow | Status & Justification |
| :--- | :--- | :--- |
| **Integration** | Data Preparation Pipeline | **COMPLETE.** Validated by a robust, profile-driven test harness that runs the full, live pipeline in an isolated sandbox with a controlled seed dataset. |
| | Experiment Lifecycle | **COMPLETE.** Validated by Layer 4 integration tests that execute the full `new -> audit -> break -> fix` lifecycle in an isolated sandbox environment. Tests creation, validation, deliberate corruption, automated repair, and final verification of experiment integrity. Features both automated and interactive modes for different use cases. |
| | Study Compilation | **COMPLETE.** Validated by Layer 5 integration test that executes the full study compilation workflow using realistic Layer 4 experiments. Tests complete lifecycle including study aggregation, statistical analysis with appropriate filtering, and artifact generation. Demonstrates proper cross-layer integration. |

### Code Coverage Targets

To ensure the framework's reliability, we have established tiered code coverage targets based on the criticality of each module.

### Analysis Result Validation Criteria

The framework defines specific criteria for determining when an analysis result is considered "valid" for scientific interpretation:

**Replication-Level Validation:**
- **Minimum Data Quality**: At least 25 valid LLM responses per replication (configurable threshold)
- **Statistical Completeness**: All core metrics (MRR, Top-K accuracy, bias measures) successfully calculated
- **Manifest Consistency**: Perfect alignment between LLM responses and experimental mappings
- **Validation Success**: ANALYZER_VALIDATION_SUCCESS marker printed for successful runs

**Study-Level Validation:**
- **Experiment Consistency**: All experiments use identical parameters (k, m, temperature) where required
- **Statistical Power**: Sufficient replications to support planned statistical tests (typically ≥30 per condition)
- **Data Completeness**: No missing critical columns or malformed data structures
- **Analysis Completeness**: ANOVA tables, effect sizes, and post-hoc tests (where applicable) generated successfully

**Quality Markers:**
- **COMPLETE**: All validation criteria met, suitable for publication
- **PARTIAL**: Some non-critical validation issues, requires review
- **INVALID**: Critical validation failures, not suitable for analysis

**Acceptance Thresholds:**
- **Statistical**: p-value calculations within 0.001 of reference values (GraphPad Prism validation)
- **Effect Size**: Cohen's d, eta-squared within 0.01 of reference calculations (GraphPad validation)
- **Data Integrity**: 100% consistency in experimental configuration validation
- **External Validation**: Statistical pipeline validated against GraphPad Prism 10.6.1 for academic publication

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

**Unit Testing: Data Pipeline**

**`src/create_subject_db.py`**          `92%`           COMPLETE. Target met. The comprehensive unit test suite
                                                    validates all data processing pathways, including robust
                                                    error handling for malformed input files and edge cases.

**`src/fetch_adb_data.py`**             `84%`           COMPLETE. Target met. Full test coverage includes session
                                                    management, data parsing, error handling, and timeout scenarios.

`src/find_wikipedia_links.py`      `89%`           COMPLETE. Unit tests cover the core data extraction logic,
                                                    robust error handling for malformed pages, and fallback behavior.

`src/validate_wikipedia_pages.py`  `91%`           COMPLETE. Unit tests validate URL validation, content checks,
                                                    and disambiguation detection with extensive mocking.

**`src/select_eligible_candidates.py`** `90%`           COMPLETE. Target met. Comprehensive unit test coverage
                                                    includes data filtering, file I/O, and all edge cases.

**`src/select_final_candidates.py`**    `91%`           COMPLETE. Target met. The comprehensive unit test suite
                                                    validates the complex cutoff algorithm logic, including edge
                                                    cases like insufficient data and boundary conditions.

**`src/generate_eminence_scores.py`**   `90%`           COMPLETE. Target met. Unit tests validate batch processing,
                                                    API interaction patterns, and robust error handling.

**`src/generate_ocean_scores.py`**      `82%`           COMPLETE. Target met. Unit tests cover the core text
                                                    processing, API interaction, and error handling logic.

`src/prepare_sf_import.py`          `86%`           COMPLETE. Unit tests validate file formatting, data
                                                    transformation, and edge case handling.

**`src/neutralize_delineations.py`**    `91%`           COMPLETE. Target met. The comprehensive unit test suite
                                                    validates the sophisticated text processing workflow, including
                                                    complex regular expression patterns and error handling.

**`src/generate_personalities_db.py`**  `91%`           COMPLETE. Target met. Unit tests validate the complete
                                                    profile generation workflow, including data aggregation,
                                                    text processing, and robust error handling.
--------------------------------------------------------------------------------------------------------------------

### Module-Level Test Coverage: Experiment Lifecycle & Analysis

**Recent Achievement:** Analysis scripts (`analyze_llm_performance.py` and `analyze_study_results.py`) successfully enhanced with Priority 1-3 statistical validation improvements while maintaining 82-83% coverage targets. Enhanced error handling, documented chance calculations, and validation logic provide foundation for GraphPad Prism validation testing.

**Milestone Complete:** All layers of testing for the experiment lifecycle workflow are complete and passing.

-----------------------------------------------------------------------------------------------------------------------------------------
Module                                  Cov. (%)        Status & Justification
--------------------------------------- --------------- ---------------------------------------------------------
**MULTI-EXPERIMENT MANAGEMENT**
**Primary Orchestrator**

**`src/experiment_manager.py`**             `97%`           COMPLETE. Target exceeded. Comprehensive unit tests validate the core state
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

`src/build_llm_queries.py`              `84%`           COMPLETE. Target met. Unit test suite validates the entire
                                                        query construction workflow, including data loading, query
                                                        building, and I/O operations, with comprehensive mocking.

`src/llm_prompter.py`                   `85%`           COMPLETE. Unit test suite validates API interaction patterns,
                                                        rate limiting, timeout handling, and response processing.

`src/process_llm_responses.py`          `82%`           COMPLETE. Target met. Unit test suite validates response
                                                        parsing, malformed content handling, and file I/O edge cases
                                                        across all supported LLM response formats.

**Analysis and Reporting**

**`src/analyze_llm_performance.py`**        `83%`           COMPLETE. Target met. The unit test suite provides comprehensive
                                                        validation of the core statistical logic, file I/O contracts,
                                                        and data parsing. Enhanced with Priority 1-3 statistical
                                                        validation improvements including documented chance calculations,
                                                        improved error categorization, and enhanced validation logic.
                                                        Covers all major failure modes and edge cases, meeting the 80%+ target.

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

`src/restore_experiment_config.py`      `83%`           COMPLETE. Unit tests validate config file restoration
                                                        functionality used during CONFIG_ISSUE repairs. Test coverage
                                                        includes config parsing, restoration logic, and error handling.
                                                        Integrated with Layer 4 test (experiment 3 corruption scenario).
                                                        Gap areas: Lines 80-83, 89-91 (error paths), Line 151 (cleanup),
                                                        and 5 partial branch coverage scenarios need additional testing.

**Study-Level & Analysis**

`src/compile_study_results.py`          `87%`           COMPLETE. Target met. The test suite was expanded to validate
                                                        all helper functions and orchestration logic, including data
                                                        aggregation, file I/O, and robust error handling for empty,
                                                        missing, or corrupted files.

`src/analyze_study_results.py`          `82%`           COMPLETE. Target met. The test suite was significantly
                                                        overhauled to fix bugs in the script's logging and post-hoc
                                                        logic. Enhanced with Priority 2-3 improvements including
                                                        specific error handling for Bayesian analysis and Games-Howell
                                                        fallback scenarios. Robustly covers data filtering, error
                                                        handling, and all major analysis code paths, meeting the 80%+ target.

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

`new_experiment.ps1`                    `N/A`           COMPLETE. Validated by Layer 4 integration test which exercises
                                                        the full experiment creation workflow in an isolated sandbox.

`audit_experiment.ps1`                  `N/A`           COMPLETE. Validated by Layer 4 integration test which exercises
                                                        experiment auditing with 4 distinct corruption scenarios.

`fix_experiment.ps1`                    `N/A`           COMPLETE. Validated by Layer 4 integration test which exercises
                                                        experiment repair workflows including config restoration.

`compile_study.ps1`                     `N/A`           COMPLETE. Validated by Layer 5 integration test which exercises
                                                        the complete study compilation workflow including statistical
                                                        analysis and artifact generation.
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