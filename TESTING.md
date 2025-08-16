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

`src/select_eligible_candidates.py` `Pending`       **PENDING AUTOMATED TESTS.** The script has been fully refactored
                                                    to the modern, resilient standard and has passed manual
                                                    validation. Awaiting creation of the final `pytest` script.

`src/generate_eminence_scores.py`   `N/A`           **PENDING.** Primary function is live LLM interaction. To be
                                                    validated by successful pipeline execution.

`src/generate_ocean_scores.py`      `N/A`           **PENDING.** Primary function is live LLM interaction. To be
                                                    validated by successful pipeline execution.

`src/select_final_candidates.py`    `N/A`           **PENDING.** Simple data filter. Validated by the pipeline's
                                                    output artifacts.

`src/prepare_sf_import.py`          `N/A`           **PENDING.** Simple data formatter. Validated by successful import
                                                    of its output into Solar Fire.

`src/create_subject_db.py`          `N/A`           **PENDING.** Deterministic data integration script. Validated by
                                                    the final `subject_db.csv`.

`src/neutralize_delineations.py`    `N/A`           **PENDING.** Primary function is live LLM interaction. To be
                                                    validated by successful execution.

`src/generate_personalities_db.py`  `N/A`           **PENDING.** Core deterministic algorithm. Validated by the final
                                                    `personalities_db.txt`.

`prepare_data.ps1`                  `N/A`           **PENDING.** This is the integration test itself. It is validated
                                                    by the successful run of the entire pipeline.
--------------------------------------------------------------------------------------------------------------------

## Future Work

Once the data preparation pipeline is fully validated, the testing process will be applied to the scripts that manage the main experimental workflows:

-   Experiment Management (`experiment_manager.py`, `experiment_auditor.py`, etc.)
-   Study-Level Aggregation & Analysis (`compile_study_results.py`, `study_analyzer.py`, etc.)
-   PowerShell Wrapper Scripts (`new_experiment.ps1`, `fix_study.ps1`, etc.)