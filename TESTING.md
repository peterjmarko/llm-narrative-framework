# Testing Strategy for the LLM Personality Matching Project

This document outlines the testing philosophy, procedures, and coverage strategy for the framework. It serves as a guide for developers and a record of the project's quality assurance standards.

## How to Run Tests

The project uses `pytest` for Python unit tests and PowerShell scripts for integration testing. All tests are managed via PDM.

-   **Run all tests (Python & PowerShell):**
    ```bash
    pdm run test
    ```
-   **Run Python tests with a console coverage report:**
    ```bash
    pdm run cov
    ```
-   **Run coverage for a specific file by its base name:**
    ```bash
    pdm run cov-file validate_wikipedia_pages
    ```

## Testing Strategy

The framework is validated using a multi-layered testing strategy to ensure correctness at all levels, from individual functions to the full end-to-end pipeline.

1.  **Unit Testing (Python / `pytest`):** Each Python script has a corresponding `pytest` file that tests its critical, offline logic in isolation. This includes testing data transformations, calculations, and response parsing logic. These tests are fast and run automatically as part of the main test suite.

2.  **Orchestration Logic Testing (PowerShell + Mocks):** The PowerShell orchestrator scripts (e.g., `prepare_data.ps1`) are tested in isolation to validate their state machine logic. This is done by replacing the real Python scripts with simple "mock" scripts that instantly create empty output files. This allows for rapid and predictable testing of the orchestrator's core responsibilities: resumability, error handling, and correct sequencing of steps.

3.  **End-to-End Integration Testing (Full Pipeline):** This is the final validation phase. The full pipeline is run using the **real** Python scripts on a small, controlled, and representative seed dataset. The goal is to verify that the data handoffs between each live script are correct and that the final output is as expected.

## Testing Process

Each production script in the project is validated using the following three-step process:

1.  **Manual Test Cases:** Execute a few simple, representative test cases manually to confirm the script's core functionality and expected output.
2.  **Automated Unit Testing:** Write a `pytest` script to cover critical, complex, or error-prone offline logic. The script is tested and debugged until all tests pass and coverage is deemed sufficient.
3.  **Manual Validation (If Changed):** If the production script's code was modified during the automated testing phase, it must be manually validated again to ensure the changes did not introduce unintended side effects.

## Data Preparation Pipeline: Testing Status

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

## Future Work

Once the data preparation pipeline is fully validated, the testing process will be applied to the scripts that manage the main experimental workflows:

-   Experiment Management (`experiment_manager.py`, `experiment_auditor.py`, etc.)
-   Study-Level Aggregation & Analysis (`compile_study_results.py`, `study_analyzer.py`, etc.)
-   PowerShell Wrapper Scripts (`new_experiment.ps1`, `fix_study.ps1`, etc.)