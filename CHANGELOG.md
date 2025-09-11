# Changelog

## 9.2.0 (2025-09-10)

### Bump

- **version 9.1.3 → 9.2.0**

### Features

- **Improve candidate filtering and stabilize L3 interactive test**
  Improves the core data filtering logic and completely overhauls the Layer 3 test harness to enhance validation depth, stability, and user experience.
  
  -   Enhances the core candidate selection logic in `select_eligible_candidates.py` for more robust and accurate filtering. The corresponding logic diagram has been updated.
  
  -   Upgrades the `large_seed` validation in the Layer 3 test to run the improved selection script directly against raw data, providing a more comprehensive end-to-end test of the filtering algorithm.
  
  -   Implements a file-based communication system between the test harness and the `prepare_data.ps1` subprocess. This permanently resolves the persistent PowerShell output buffering issue that caused interactive prompts to render out of order, making the "Guided Tour" stable and responsive.
  
  -   Adds new introductory pauses and standardized color-coding to the interactive test for better user guidance.
  
  -   Ensures Python progress bars are always visible and suppresses stray cleanup progress bars for a cleaner console output.

## 9.1.3 (2025-09-10)

### Bump

- **version 9.1.2 → 9.1.3**

### Documentation

- **align all documentation with refactored test suite**
  Performs a comprehensive update to all project documentation to align with the final, refactored state of the test suite and data pipeline.
  
  - **Testing Guide (`TESTING.md`):**
    - Updates the developer workflow to use the new `-StopAfterStep` parameter, replacing the obsolete `exit 0` method.
    - Simplifies the Layer 4 and 5 test instructions to use the single `pdm run` commands.
  
  - **Replication Guide (`article_supplementary_material.template.md`):**
    - Recommends the `prepare_data.ps1` orchestrator as the primary replication method.
    - Corrects the name of the final analysis script to `compile_study.ps1`.
  
  - **Core Documentation (`DOCUMENTATION.template.md`):**
    - Updates all data counts to reflect the final, correct numbers (10619 -> 7234 -> 4954).
    - Enhances the explanation of the `ZoneAbbr` data integrity technique.
  
  - **Diagrams:**
    - Corrects four Mermaid diagrams (`arch_prep_codebase`, `flow_prep_3_generation`, `flow_prep_pipeline`, `logic_prep_eligible_candidates`) to reflect the final data flows and script logic.
  
  - **Other Documents:**
    - Updates `CONTRIBUTING.md` to include `ROADMAP.md` in the contribution workflow.
    - Updates `article_main_text.md` to direct readers to the supplementary guide for replication instructions.
    - Standardizes all dates to "September 2025".

### Fixes

- **bump version for test suite and documentation updates**

## 9.1.2 (2025-09-09)

### Bump

- **version 9.1.1 → 9.1.2**

### Refactor

- **Overhaul test suite for controlled execution and accuracy**
  Performs a comprehensive overhaul of the data preparation pipeline's test suite. This fixes critical bugs in the Layer 2 orchestration test, completely refactors the Layer 3 integration test for deterministic, controlled execution, and improves code and user documentation.
  
  ### Layer 2 Orchestration Fixes
  - **Corrected False Positives:** Modified `run_layer2_test.ps1` to correctly check for `[INCOMPLETE]` statuses and use proper success message matching, ensuring the test fails when steps are not fully complete.
  - **Enhanced Mock Generation:** Upgraded the mock script generator to create the necessary summary files and directory structures, resolving the root cause of the `[INCOMPLETE]` statuses and subsequent test looping.
  
  ### Layer 3 Integration Refactor
  - **Controlled Execution:** Introduced a `-StopAfterStep` parameter to `prepare_data.ps1`, allowing the test harness to run the pipeline in precise, controlled segments. The Layer 3 workflow is now broken into four distinct runs to manage its complex logic.
  - **Corrected Test Sequence:** The isolated validation for the cutoff logic now runs in its correct sequence (as Step 7.a) after the pipeline completes Step 6.
  - **Resolved Logging Bugs:** Fixed a persistent race condition that caused duplicate and out-of-sequence entries in the summary table.
  - **Fixed Test Environment:** The setup script no longer copies pipeline-generated files into the sandbox, ensuring a clean state for each test run.
  - **Standardized Asset Structure:** Reorganized the `tests/assets` directory to mirror the project's `data/` structure for consistency.
  
  ### Documentation & Code Clarity
  - **Docstring Enhancements:** Updated docstrings in key scripts (`generate_ocean_scores.py`, `select_final_candidates.py`, `prepare_sf_import.py`) to reflect current logic and explain critical techniques.
  - **Testing Guide:** Updated `TESTING.md` with details on the new asset structure and clarified the scope of Layer 2 and 3 tests.

## 9.1.1 (2025-09-08)

### Bump

- **version 9.1.0 → 9.1.1**

### Fixes

- **overhaul test suite and fix latent bugs**
  We have completed a comprehensive overhaul and expansion of the unit test suites for the entire data preparation pipeline. This initiative successfully identified and fixed numerous latent bugs, resolved persistent test failures caused by issues like test pollution and incorrect mocks, and dramatically increased code coverage across all modules.
  
  The result is a more robust, reliable, and maintainable data preparation workflow.

## 9.1.0 (2025-09-08)

### Bump

- **version 9.0.0 → 9.1.0**

### Features

- **Finalize documentation build system and enhance analysis scripts**
  This release represents a major push to finalize the project's documentation and build system, enhancing clarity, reproducibility, and professional presentation.
  
  The core of this effort was a complete architectural refactoring of the documentation build process. The system now uses a robust template-based architecture, where `.template.md` files are compiled into final `.md` and `.docx` documents. This new system supports automatically generated Tables of Contents and correctly handles the embedding of both Mermaid diagrams and static images. As part of this, the replication guide was renamed to `article_supplementary_material.template.md` to integrate it into this new workflow.
  
  In parallel, all key project documentsthe Framework Manual, Replication Guide, Testing Guide, and main articlewere systematically reviewed and improved with new tables and figures. The parameter analysis utility was also finalized, and the statistical rigor of the main analysis pipeline was improved with the addition of multiple comparison correction and automated generation of interaction plots.

## 9.0.0 (2025-09-07)

### Bump

- **version 8.0.0 → 9.0.0**
- **version 7.0.1 → 8.0.0**
  This major release introduces a significant methodological refactoring of the LLM-based candidate selection process. The responsibility for determining the final subject pool size has been moved from the data generation script (`generate_ocean_scores.py`) to a new post-hoc analysis step in the selection script (`select_final_candidates.py`).
  
  This change decouples expensive data generation from flexible data selection, making the framework more robust, reproducible, and easier to adapt for future research.
  
  Key changes in this release include:
  - **Methodological Shift:** The variance-based cutoff logic now resides in `select_final_candidates.py`.
  - **Test Harness Overhaul:** The Layer 2 and 3 integration tests for the data preparation pipeline have been completely rewritten to be fully automated and non-interactive.
  - **Improved Pipeline Resumption:** The pipeline orchestrator now correctly identifies and resumes from `[INCOMPLETE]` steps by parsing summary files.
  - **Enhanced UX:** Implemented `tqdm` progress bars for a clean user experience during long-running LLM scoring scripts.
  
  BREAKING CHANGE: The core logic for determining the final subject pool has been moved from `generate_ocean_scores.py` to `select_final_candidates.py`. As a result, the `ocean_scores_discarded.csv` artifact is no longer generated by the pipeline. All related documentation, diagrams, and tests have been updated to reflect this new workflow.

### Features

- **Redesign candidate selection and harden data pipeline**
  This release marks a comprehensive overhaul of the data preparation pipeline, focusing on two key areas: the implementation of a robust, data-driven algorithm for final candidate selection, and a major upgrade to the pipeline's intelligence, error handling, and user experience.
  
  The candidate selection process was completely redesigned, moving from a simple heuristic to a sophisticated, multi-stage analysis involving curve smoothing and slope detection to find a scientifically optimal cohort size. This was validated by a new, one-off parameter analysis utility.
  
  Simultaneously, the pipeline orchestrator was made significantly more intelligent, with the ability to detect partially completed steps, prevent data corruption from duplicate or invalid records, and provide a vastly improved user experience through real-time progress indicators and clearer reporting.
- **decouple candidate selection and overhaul data prep tests**
  This release completes a major refactoring of the LLM-based candidate selection logic and a significant overhaul of the data preparation pipeline's test harnesses. The final subject pool is now determined by a more flexible, post-hoc analysis in `select_final_candidates.py` instead of during the data generation step.
  
  - **METHODOLOGICAL SHIFT: Decoupled Candidate Selection:**
    - The complex, stateful variance-based cutoff logic was removed from `generate_ocean_scores.py`. Its sole responsibility is now to generate OCEAN scores for all eligible candidates.
    - This cutoff logic was moved into `select_final_candidates.py`, which now performs a post-hoc analysis to determine the final cohort size. This makes the selection process more flexible and transparent.
  
  - **Test Harness Overhaul:**
    - Completed a full overhaul of the Layer 2 and 3 data preparation integration tests, making them non-interactive, stateless, and reliable, with clean, context-aware logging.
    - The test suite commands in `pyproject.toml` were reorganized for clarity.
  
  - **Robustness & UX Fixes:**
    - Fixed a critical bug where `prepare_data.ps1` would use the wrong working directory, causing errors in test runs.
    - The pipeline now correctly detects and resumes from `[INCOMPLETE]` steps by parsing summary files, not just checking for file existence.
    - Implemented `tqdm` progress bars for LLM scoring scripts for a clean, user-friendly experience.
    - Fixed `UnboundLocalError` crashes in scoring scripts by correcting the module import order.
    - The eminence scoring script now correctly halts the pipeline if it fails to retrieve all scores, preventing data corruption.
  
  BREAKING CHANGE:

## 8.0.0 (2025-09-07)

### Bump

- **version 7.0.1 → 8.0.0**

### Features

- **decouple candidate selection and overhaul data prep tests**
  This release completes a major refactoring of the LLM-based candidate selection logic and a significant overhaul of the data preparation pipeline's test harnesses. The final subject pool is now determined by a more flexible, post-hoc analysis in `select_final_candidates.py` instead of during the data generation step.
  
  - **METHODOLOGICAL SHIFT: Decoupled Candidate Selection:**
    - The complex, stateful variance-based cutoff logic was removed from `generate_ocean_scores.py`. Its sole responsibility is now to generate OCEAN scores for all eligible candidates.
    - This cutoff logic was moved into `select_final_candidates.py`, which now performs a post-hoc analysis to determine the final cohort size. This makes the selection process more flexible and transparent.
  
  - **Test Harness Overhaul:**
    - Completed a full overhaul of the Layer 2 and 3 data preparation integration tests, making them non-interactive, stateless, and reliable, with clean, context-aware logging.
    - The test suite commands in `pyproject.toml` were reorganized for clarity.
  
  - **Robustness & UX Fixes:**
    - Fixed a critical bug where `prepare_data.ps1` would use the wrong working directory, causing errors in test runs.
    - The pipeline now correctly detects and resumes from `[INCOMPLETE]` steps by parsing summary files, not just checking for file existence.
    - Implemented `tqdm` progress bars for LLM scoring scripts for a clean, user-friendly experience.
    - Fixed `UnboundLocalError` crashes in scoring scripts by correcting the module import order.
    - The eminence scoring script now correctly halts the pipeline if it fails to retrieve all scores, preventing data corruption.
  
  BREAKING CHANGE: The responsibility for the data-driven cutoff has moved from `generate_ocean_scores.py` to `select_final_candidates.py`. The `ocean_scores_discarded.csv` file is no longer generated by the pipeline.

## 7.0.1 (2025-09-07)

### Bump

- **version 7.0.0 → 7.0.1**

### Refactor

- **standardize file backup utility and fix orchestration tests**
  This major refactoring introduces a standardized file backup-and-remove utility, significantly improving code maintainability and consistency across the data preparation pipeline.
  
  The Layer 2 orchestration test harness has been completely overhauled to be fully automated, non-interactive, and provide clean, context-aware logging.
  
  - **Standardized Backup/Overwrite Logic:**
    - A new shared module, `src/utils/file_utils.py`, was created to centralize file operations.
    - All data preparation scripts were refactored to use a single `backup_and_remove` function, ensuring consistent behavior for the `--force` flag.
  
  - **Layer 2 Test Overhaul:**
    - Resolved an infinite loop caused by a conflict between the `-Force` and resume logic.
    - Cleaned up test logs by suppressing unnecessary banners, completion messages, and user-facing warnings.
    - Introduced a `-TestMode` switch in `prepare_data.ps1` to ensure non-interactive execution during tests.
  
  - **Other Fixes & Improvements:**
    - Updated PDM shortcuts to use `pwsh` to fix ANSI color rendering.
    - Enabled unbuffered output (`python -u`) for real-time progress display.
    - Removed a duplicated function definition in `prepare_data.ps1`.

## 7.0.0 (2025-09-06)

### Bump

- **version 6.15.1 → 7.0.0**

### Features

- **complete data preparation pipeline testing**
  This marks a major milestone in the project's maturity by completing the multi-layered testing strategy for the entire data preparation pipeline. All four layers are now fully validated and passing:
  
  - Core Algorithm Validation (`test-assembly`)
  - Layer 1: Unit Testing (`test-data-prep`)
  - Layer 2: Orchestration Testing (`test-l2`)
  - Layer 3: Integration Testing (default, bypass, and interactive modes)
  
  BREAKING CHANGE: The completion and validation of the full data preparation testing suite represents a major step in the project's stability and reliability. This milestone justifies a major version bump to v7.0.0.

## 6.15.1 (2025-09-06)

### Bump

- **version 6.15.0 → 6.15.1**

### Fixes

- **resolve unit test failure and enhance interactive UI**
  This series of changes addressed several test failures and significantly enhanced the usability and clarity of the interactive testing mode (`test-l3-interactive`).
  
  **1. Core Bug Fixes (Test Failures):**
  *   **`generate_personalities_db.py` Output Path:** The script was updated to save its output to the `data/` directory instead of `data/processed/`.
  *   **Test Corrections:** The corresponding unit and integration tests (`test_generate_personalities_db.py`, `test_assembly_algorithm.py`, and the Layer 3 test harness) were all updated to look for the `personalities_db.txt` file in the correct `data/` directory, resolving the initial failures.
  
  **2. Developer Experience Improvements:**
  *   **PDM Shortcut:** A PDM shortcut, `test-assembly`, was created in `pyproject.toml` to simplify running the core algorithm integration test.
  *   **Documentation:** `TESTING.md` was updated to use this new, simpler shortcut.
  
  **3. Interactive Mode Enhancements:**
  *   **Consistent Pausing:** The Layer 3 test harness was fixed to correctly pause for user input at Step 1, making the "guided tour" experience consistent from the start.
  *   **Contextual Summaries:** A new utility script (`scripts/get_docstring_summary.py`) was created to extract richer, multi-paragraph summaries from Python scripts. This was integrated into the pipeline orchestrator and the test harness to provide a more detailed explanation for each step in interactive mode.
  *   **Forced Color Output:** Enabled forced color code generation in all Python scripts (`colorama.init(strip=False)`). This resolves an issue where colors were stripped when the test harness captured script output, ensuring a consistently colored UI throughout the interactive pipeline tour.
  *   **Improved Readability and UI:**
      *   **Color-Coding:** Log messages and final status reports were consistently color-coded (magenta, yellow, green, red, cyan) across all Python scripts and the PowerShell test harness for better clarity.
      *   **Robust Prompts:** The `Read-Host` prompts were modified to include leading and trailing newlines, ensuring a clean exit with `Ctrl+C`.
      *   **Concise Logging:** Redundant words like "Successfully" were trimmed from certain log messages in `fetch_adb_data.py` for better readability.
  
  **4. Enhanced Reporting:**
  *   **Expanded Scope Reporting:** The `generate_scope_report.py` script was updated to include test harn

## 6.15.0 (2025-09-06)

### Bump

- **version 6.14.0 → 6.15.0**

### Features

- **overhaul Layer 2 and refactor Layer 3 test harness**
  This commit hardens the entire data preparation test suite by overhauling the Layer 2 test and refactoring the Layer 3 harness for improved robustness, clarity, and organization.
  
  **Layer 2 Overhaul:**
  - The three outdated `layer2_step*.ps1` scripts are deleted and replaced with a single, modern `run_layer2_test.ps1` orchestrator.
  - The new test is "self-healing": it programmatically parses the real `prepare_data.ps1` to dynamically build its mock environment, ensuring it remains in sync with the production script.
  - The entire test is now automated via `pdm run test-l2`.
  
  **Layer 3 Refactoring & Fixes:**
  - All Layer 3 scripts are moved into a dedicated `layer3/` subdirectory for better organization.
  - A robust `Get-ProjectRoot` function is implemented across all harness scripts, making the test suite immune to file relocations.
  - The `bypass` test profile is corrected to use the same full subject list as the `default` profile, ensuring a true A/B comparison.
  - `run_layer3_test.ps1` is refactored to use a common subject list (`$commonSubjects`), eliminating code duplication.
  - `prepare_data.ps1` now silently skips steps during automated test runs, providing a clean log that is identical in both `default` and `bypass` modes.
  
  **Documentation:**
  - `TESTING.md` is updated to reflect the new PDM-based commands and simplified workflows for running the overhauled Layer 2 and Layer 3 tests.

## 6.14.0 (2025-09-06)

### Bump

- **version 6.13.2 → 6.14.0**

### Features

- **add profile-driven architecture and automated workflows**
  Refactors the Layer 3 data pipeline test from a monolithic set of scripts into a robust, profile-driven architecture orchestrated by a new master runner. This fixes a critical testing anti-pattern and resolves numerous bugs related to test isolation, configuration, and execution flow.
  
  - **Introduces Master Runner & Profiles**: A new `run_layer3_pipeline_test.ps1` script is now the single entry point, using "Test Profiles" to define scenarios, centralize test-specific data, configuration overrides, and fault-injection logic.
  
  - **Enforces Complete Test Isolation**: All static and foundational assets are now sourced exclusively from a new `tests/assets/` directory, fully decoupling the test suite from the main project's generated files.
  
  - **Adds Automated Archiving & Diagnostics**: The cleanup phase now automatically creates a timestamped ZIP archive of the sandbox for post-mortem analysis. The setup phase integrates diagnostics to identify file-locking processes on failure.
  
  - **Implements Strict Asset Validation**: The setup script now uses a manifest to validate all test assets against precise rules (e.g., line counts), preventing tests from running with corrupted data.

## 6.13.2 (2025-09-03)

### Bump

- **version 6.13.1 → 6.13.2**

### Refactor

- **standardize terminology and refactor bypass flag**
  Standardizes the terminology for the data preparation pipeline into a clear, four-stage model: Data Sourcing, Candidate Qualification, LLM-based Candidate Selection, and Profile Generation.
  
  Refactors the ambiguous `bypass_llm_scoring` flag to the more precise `bypass_candidate_selection`. Updates all relevant scripts, unit tests, diagrams, and high-level documentation to use the new terminology and flag. Improves the layout of key diagrams to a "waterfall" structure for better readability. Also restructures and updates the .gitignore file.

## 6.13.1 (2025-09-02)

### Bump

- **version 6.13.0 → 6.13.1**

### Refactor

- **standardize data preparation terminology and refactor bypass flag**
  - Renames the `bypass_llm_scoring` flag to the more precise `bypass_candidate_selection` to avoid ambiguity with the main experiment's similarity scoring.
  - Updates all relevant scripts (`config.ini`, `prepare_data.ps1`, `generate_eminence_scores.py`, `generate_ocean_scores.py`, `select_final_candidates.py`) and their docstrings to use the new flag and terminology.
  - Restructures all high-level documentation (`DOCUMENTATION.md`, `TESTING.md`, `article_main_text.md`, etc.) to use a clear, four-stage model for the data preparation pipeline: `Data Sourcing`, `Candidate Qualification`, `LLM-based Candidate Selection`, and `Profile Generation`.

## 6.13.0 (2025-09-02)

### Bump

- **version 6.12.0 → 6.13.0**

### Features

- **add option to bypass LLM-based scoring**
  - Adds a `bypass_llm_scoring` flag to `config.ini` to serve as a methodological control for the data preparation pipeline.
  - Modifies the scoring scripts (`generate_eminence_scores.py`, `generate_ocean_scores.py`) to be bypass-aware, warning the user if they are run while the bypass is active.
  - Updates `select_final_candidates.py` with a conditional logic path to use the full eligible candidate list when the bypass is active.
  - Makes the main `prepare_data.ps1` orchestrator bypass-aware, allowing it to skip the two scoring scripts for a more efficient workflow.
  - Adds a `config.ini` creation step to the Layer 3 integration test setup to support this new functionality.
  - Adds new unit tests for all three affected Python scripts to validate the bypass feature.

## 6.12.0 (2025-09-02)

### Bump

- **version 6.11.1 → 6.12.0**

### Features

- **add Northern Hemisphere filter and update documentation**
  - Adds a new filter to `select_eligible_candidates.py` to include only subjects with a Northern Hemisphere latitude ('N'), controlling for a potential zodiacal shift confound.
  - Updates the corresponding unit test to validate this new logic.
  - Corrects relative paths in the Layer 3 integration test scripts to function from their new, refactored locations.
  - Makes the Layer 3 cleanup script interactive, adding a confirmation prompt before deletion and a `-Force` override for automation.
  - Adds a new `cov-prep` PDM script to run a consolidated coverage report on the data preparation test suite.
  - Standardizes the console output for `generate_scope_report.py` and `list_project_files.py`.
  - Consolidates all data filtering criteria into `DOCUMENTATION.md` to create a single source of truth.
  - Adds methodological citations for filtering choices to the main article.
  - Updates the project `ROADMAP.md` with new tasks and priorities.

## 6.11.1 (2025-09-01)

### Bump

- **version 6.11.0 → 6.11.1**

### Refactor

- **reorganize test suite for modularity and add PDM shortcut**
  - Created new subdirectories (`tests/data_preparation/` and `tests/testing_harness/data_preparation/`) to group all tests related to the data preparation pipeline.
  - Moved all relevant Python unit tests and PowerShell-based integration tests (Layer 3) into these new directories.
  - Corrected all relative paths in the moved scripts (`test_assembly_algorithm.py`, `layer3_stage2_test_workflow.ps1`) to ensure they function correctly from their new locations.
  - Added a new `test-prep` PDM script to `pyproject.toml` to allow for running all data preparation unit tests with a single command.
  - Updated documentation (`TESTING.md`, etc.) to reflect the new test structure and PDM command.

## 6.11.0 (2025-09-01)

### Bump

- **version 6.10.0 → 6.11.0**

### Features

- **add assembly logic verification workflow and fix algorithm bugs**
  - Introduces a full suite of utility scripts (`select_*`, `prepare_*`, `extract_*`, etc.) to generate all artifacts for validating the personality assembly algorithm.
  - Adds a new, flexible `pytest` script (`test_assembly_algorithm.py`) that provides push-button validation of the core assembly logic against a Solar Fire-generated ground truth. The test can be run on the full subject set or a single record via the `--test-record-number` flag.
  - The verification process revealed and fixed several critical bugs in `generate_personalities_db.py`, including the logic for Quadrant/Hemisphere calculations, key formatting, and assembly order.
  - The ground truth extraction script (`extract_assembly_logic_text.py`) was also made more robust to correctly handle various report formats.

## 6.10.0 (2025-08-31)

### Bump

- **version 6.9.0 → 6.10.0**

### Features

- **add utility scripts for assembly logic verification**
  This commit introduces the full suite of utility scripts to generate and
  validate the data for the assembly logic verification test.
  
  - Adds four new scripts to:
    1. Algorithmically select an optimal subject set.
    2. Prepare a Solar Fire import file for the selected subjects.
    3. Validate the round-trip data integrity after manual SF processing.
    4. Extract the final ground-truth text from raw Solar Fire reports.
  
  - Refactors this entire workflow to operate within a temporary,
    git-ignored sandbox (`temp_assembly_logic_validation/`).
  - Renames all "gold standard" scripts and artifacts to the more precise
    "assembly logic" convention.
  - Decouples core logic from the CLI in `prepare_sf_import.py` to enable
    reuse (DRY).
  - Fixes a bug in `create_subject_db.py` to ensure it always creates
    the `reports` directory for consistency.

## 6.9.0 (2025-08-31)

### Bump

- **version 6.8.10 → 6.9.0**

### Features

- **add gold standard selection tools and fix assembly bugs**
  This commit introduces a new workflow for gold standard verification and
  fixes several critical bugs discovered during its development.
  
  - Adds two new utility scripts (`generate_coverage_map.py` and
    `select_gold_standard_subjects.py`) that algorithmically select a
    minimal set of subjects for 100% coverage of all achievable
    delineation keys.
  - Adds a `--bypass-llm` flag to `neutralize_delineations.py` and a
    corresponding unit test to support the new verification process.
  
  - Fixes a critical bug in `generate_personalities_db.py` where Uranus,
    Neptune, and Pluto were incorrectly excluded from "Point in Sign"
    calculations.
  - Fixes a long-standing bug that generated incorrect keys for "Sign
    Strong" classifications.
  
  - Updates `article_main_text.md` to clarify limitations around
    blinding and data sourcing.
  - Updates `ROADMAP.md` with new tasks for statistical correction and
    making sample selection optional.

## 6.8.10 (2025-08-30)

### Bump

- **version 6.8.9 → 6.8.10**

### Refactor

- **complete sandbox refactoring and fix assembly logic**
  This commit completes the full sandbox refactoring of the data
  preparation pipeline and fixes a critical bug in the final assembly
  script.
  
  - Refactored the final script, `generate_personalities_db.py`, to be
    fully sandbox-aware.
  - Fixed a critical bug in the assembly algorithm where incorrect key
    formatting resulted in empty personality descriptions.
  - Updated the unit test for `generate_personalities_db.py` to align
    with the corrected key generation logic.
  - Finalized the Layer 3 integration test harness, which now performs a
    complete, error-free, end-to-end run of the entire pipeline.
  - Added the remaining static assets to the test harness to ensure a
    self-contained test environment.

## 6.8.9 (2025-08-30)

### Bump

- **version 6.8.8 → 6.8.9**

### Refactor

- **improve test harness interactivity and resolve sandboxing bugs**
  This commit significantly overhauls the Layer 3 integration test harness
  to improve usability, interactivity, and correctness.
  
  - Introduces an interactive "guided tour" mode via an `-Interactive`
    switch to help new users learn the data pipeline step-by-step.
  - Renames test harness scripts from `step` to `stage` and updates all
    documentation to use a consistent "Layer > Stage > Step" terminology.
  
  - Resolves several critical sandboxing bugs where the harness would
    incorrectly read from or write to the main project's data
    directory.
  - Simplifies and hardens the startup logic in
    `validate_wikipedia_pages.py` to prevent it from reading the wrong
    input file.
  - Adds `adb_category_map.csv` to the list of static assets copied
    into the sandbox.
  
  - Adds "step back" functionality to the project roadmap as a future
    enhancement.
  - Removes sparkle emojis from console output to prevent
    `UnicodeEncodeError`.

## 6.8.8 (2025-08-30)

### Bump

- **version 6.8.7 → 6.8.8**

### Refactor

- **refactor data integration pipeline and improve documentation**
  This commit refactors the final data integration scripts and improves
  the resilience of the test pipeline, while also clarifying core project
  documentation.
  
  - Refactored `create_subject_db.py` to be fully sandbox-aware.
  - Standardized all console output paths to be project-relative and fixed
    Unicode errors in success messages.
  - Enhanced `neutralize_delineations.py` with pipe-aware logging and a
    more robust startup sequence.
  - Improved the Layer 3 integration test harness with an automated debug
    workflow to diagnose neutralization failures.
  - Updated the abstract in `article_main_text.md` to more accurately
    describe the LLM matching task.
  - Added a "Prerequisites" section to `article_supplementary_material.md`.

## 6.8.7 (2025-08-30)

### Bump

- **version 6.8.6 → 6.8.7**

### Refactor

- **refactor selection and import scripts for sandbox awareness**
  This commit continues the sandbox refactoring for the data preparation
  pipeline, updating `select_final_candidates.py` and
  `prepare_sf_import.py`.
  
  - Refactored `select_final_candidates.py` and `prepare_sf_import.py` to be
    fully sandbox-aware, using the `--sandbox-path` argument for all file
    I/O.
  - Updated the console output for both scripts to match the new
    standardized format.
  - Updated the unit tests for both scripts to reflect the new
    sandbox-aware interface.
  - Enhanced the Layer 3 integration test harness by copying required
    static assets into the sandbox and streamlining test log output.

## 6.8.6 (2025-08-30)

### Bump

- **version 6.8.5 → 6.8.6**

### Refactor

- **refactor scoring scripts and standardize console logs**
  This commit refactors the LLM-based scoring scripts for sandbox awareness and standardizes console output across the data preparation pipeline.
  
  - Refactored `generate_eminence_scores.py` and `generate_ocean_scores.py` to be fully sandbox-aware, replacing file path arguments with `--sandbox-path`.
  - Standardized the final console output block for all six refactored data-prep scripts to a consistent, more readable format.
  - Updated the Layer 3 integration test to call the refactored scripts and use the final 7-subject test cohort.
  - Updated unit tests for the scoring scripts to align with their new interfaces.

## 6.8.5 (2025-08-29)

### Bump

- **version 6.8.4 → 6.8.5**

### Fixes

- **fix research entry filter and harden integration test**
  This commit introduces a critical bug fix to the data preparation pipeline's filtering logic, hardens the link-finding script, and overhauls the integration test suite to be more robust and deterministic.
  
  - **`select_eligible_candidates.py` (Bug Fix):** Corrected the core filtering logic to properly exclude non-person "Research" entries.
  - **`find_wikipedia_links.py` (Enhancement):** Added a title-match validation step for any URL scraped from an ADB page to prevent incorrect links from being passed downstream.
  - **Integration Test Overhaul:** Redesigned the Layer 3 test to fetch a new 7-subject cohort and use a "Fetch, then Corrupt" strategy to deterministically test all key failure paths.
  - **Unit Tests:** Updated unit tests for both scripts to align with the code changes.
  - **Documentation:** Updated `DOCUMENTATION.md` to clarify the types of scientific replication and updated the `logic_prep_eligible_candidates.mmd` flowchart to reflect the new logic.

## 6.8.4 (2025-08-29)

### Bump

- **version 6.8.3 → 6.8.4**

### Documentation

- **restructure and enhance data prep diagrams**
  This commit overhauls the documentation for the Data Preparation Pipeline to improve clarity and logical flow.
  
  *   Reorganizes the diagram sections into a more intuitive Architecture -> Workflow -> Data Flow -> Logic structure.
  *   Adds four new diagrams: a high-level logic flowchart and three detailed stage-by-stage data flow diagrams.
  *   Corrects the layout for two existing diagrams (`arch_prep_codebase.mmd` and `logic_prep_final_candidates.mmd`) to improve readability and fix rendering errors.

### Fixes

- **trigger release for documentation updates**

## 6.8.3 (2025-08-24)

### Bump

- **version 6.8.2 → 6.8.3**

### Refactor

- **refactor candidate selection for sandboxing**
  Refactors the select_eligible_candidates.py script to be fully sandbox-aware, replacing explicit file I/O arguments with --sandbox-path.
  Updates the corresponding unit test suite to use a mock sandbox environment, aligning it with the script's new interface. Also advances the Layer 3 integration test checkpoint to verify the script's output within the pipeline.

## 6.8.2 (2025-08-24)

### Bump

- **version 6.8.1 → 6.8.2**

### Refactor

- **refactor validation script and improve log cosmetics**
  This commit continues the sandbox-aware refactoring of the data preparation pipeline and improves console output readability.
  
   - Refactored `validate_wikipedia_pages.py` to be fully sandbox-aware, replacing explicit file path arguments with `--sandbox-path`.
   - Advanced the Layer 3 integration test checkpoint to run after the validation script.
   - Improved log cosmetics by removing color from report files and standardizing console colors for notes (yellow) and file paths (cyan).

## 6.8.1 (2025-08-24)

### Bump

- **version 6.8.0 → 6.8.1**

### Fixes

- **standardize relative paths in test logs**
  Resolves inconsistent and ambiguous file path logging during the Layer 3 integration test.
  
  Previously, some scripts and the test harness logged paths relative to the sandbox directory, which was confusing. All logged paths are now consistently relative to the project root for clarity.

## 6.8.0 (2025-08-24)

### Bump

- **version 6.7.0 → 6.8.0**

### Features

- **implement live, chdir-based Layer 3 integration test**
  This commit implements a robust, live, limited-scope integration test for the data preparation pipeline (Layer 3).
  
  A new `--work-dir` architecture is introduced, where Python scripts explicitly change their working directory via `os.chdir()` to a provided sandbox. This correctly isolates all file operations and works reliably with PDM's execution environment.
  
  - Refactored `fetch_adb_data.py` and `find_wikipedia_links.py` to use the `--work-dir` standard.
  - Fixed unit tests for `find_wikipedia_links.py` to correctly mock dependencies.
  - The Layer 3 test harness now successfully orchestrates a live fetch, filters data, and validates the first two pipeline stages.
  
  A known cosmetic issue with inconsistent path logging remains.

## 6.7.0 (2025-08-23)

### Bump

- **version 6.6.1 → 6.7.0**

### Features

- **establish sandbox-aware architecture for data pipeline tests**
  This commit lays the foundation for a new, high-fidelity testing architecture for the data preparation pipeline. It introduces a sandbox-aware pathing system to enable robust, isolated integration tests.
  
  - Adds a new `get_path()` utility to `config_loader.py` that intelligently resolves file paths relative to a sandbox directory when the `PROJECT_SANDBOX_PATH` environment variable is set.
  - Refactors `fetch_adb_data.py` as the first script to be fully compliant with this new architecture.
  - Updates the Layer 3 test harness to orchestrate the targeted live fetch and verification for `fetch_adb_data.py`.
  - Formalizes the "Refactor -> Unit Test -> Integration Test" workflow in TESTING.md.

## 6.6.1 (2025-08-23)

### Bump

- **version 6.6.0 → 6.6.1**

### Refactor

- **standardize all PowerShell wrapper interfaces and calls**
  This commit completes a comprehensive refactoring to standardize the entire suite of user-facing PowerShell scripts and their interactions with Python backends, enhancing robustness and consistency.
  
  Guiding Principles Implemented:
  - PowerShell-to-Python calls now uniformly use the robust array-building method.
  - PowerShell-to-PowerShell calls now uniformly use the robust hashtable splatting method.
  - Directory parameters are standardized to `$ExperimentDirectory` for single experiments and `$StudyDirectory` for studies.
  - Python backends now have consistent argument interfaces.
  
  This resolves multiple subtle argument-passing bugs and aligns all scripts with the architectural guidelines now documented in CONTRIBUTING.md.

## 6.6.0 (2025-08-22)

### Bump

- **version 6.5.0 → 6.6.0**

### Features

- **implement live, limited-scope data pipeline integration test**
  This commit refactors the Layer 3 integration test into a high-fidelity, live, limited-scope validation of the entire data preparation pipeline. The previous test was offline and did not accurately validate API interactions.
  
  - `fetch_adb_data.py` is now testable, accepting `--start-date` and `--end-date` flags to fetch a small, predictable number of live records from Astro-Databank.
  - `neutralize_delineations.py` now accepts a `--force` flag for non-interactive execution in automated workflows.
  - The Layer 3 test harness is rewritten to orchestrate a live end-to-end run using a more diverse and representative set of test subjects (Busch, McCartney, Cainer).
  - The harness now correctly bypasses only the manual steps, allowing all automated scripts, including those with network/LLM calls, to run against the limited live data.
  - Fixes bugs in `prepare_data.ps1` related to the `-Force` flag logic and improves its console output.
  - Adds temporary test directories to `.gitignore`.

## 6.5.0 (2025-08-22)

### Bump

- **version 6.4.0 → 6.5.0**

### Features

- **automate and optimize Layer 3 data pipeline test**
  The Layer 3 data pipeline integration test was previously slow, costly, and required manual user interaction. This commit completely refactors the harness to be fully automated and significantly more efficient.
  
  - The test now bypasses the expensive `neutralize_delineations.py` LLM step by providing a minimal, pre-generated set of its output files as seed data.
  - The workflow is now a single, non-interactive script call, making it suitable for CI environments.
  - The now-obsolete `layer3_simulate_manual_step.ps1` has been deleted.
  - `TESTING.md` has been updated to describe the new, streamlined procedure.
  - `CONTRIBUTING.md` now includes a "Pre-Commit Checklist" to clarify the developer workflow.

## 6.4.0 (2025-08-22)

### Bump

- **version 6.3.0 → 6.4.0**

### Features

- **complete sandboxing refactor for all test layers**
  This commit completes the system-wide refactoring to a fully isolated, sandboxed testing framework, eliminating the intrusive backup-and-restore method.
  
  The new architecture uses a `PROJECT_CONFIG_OVERRIDE` environment variable, set via a standard `-ConfigPath` parameter, to run tests in a non-destructive environment.
  
  - All user-facing PowerShell wrappers (experiment and study level) now accept the `-ConfigPath` parameter.
  - The test harnesses for Layer 4 (Main Workflow) and Layer 5 (Migration Workflow) have been completely rewritten to use the new sandboxed model.
  - `TESTING.md` is now updated to reflect the simpler, safer procedures.
  - Fixed a key bug where `replication_manager.py` archived the wrong config file during tests.

## 6.3.0 (2025-08-22)

### Bump

- **version 6.2.0 → 6.3.0**

### Features

- **Implement sandboxed testing framework & rename study script**
  This commit introduces a new, partially implemented sandboxed testing architecture and renames the primary study evaluation script for clarity.
  
  The previous integration testing model was intrusive, requiring manual backups of core project files. The new architecture uses a `PROJECT_CONFIG_OVERRIDE` environment variable, set via a standard `-ConfigPath` parameter on user-facing scripts, to run tests in a completely isolated environment without modifying the main workspace.
  
  Key Changes:
  
  **Sandboxed Testing Framework (Partial Implementation)**
  -   `config_loader.py` now checks for the override environment variable.
  -   `new_experiment.ps1` and `audit_experiment.ps1` are the first scripts to be fully refactored with the `-ConfigPath` parameter.
  -   The backends (`experiment_manager.py`, `experiment_auditor.py`) now support this sandboxing mechanism.
  -   The `replication_manager.py` now correctly archives the specified test config, not the default one.
  
  **Script Renaming and Documentation Update**
  -   Renamed `evaluate_study.ps1` to `compile_study.ps1` for better consistency with the overall pipeline terminology.
  -   Updated all related documentation and diagrams (`DOCUMENTATION.md`, `arch_main_codebase.mmd`, etc.) to reflect this name change.
  
  **Bug Fixes & UX Improvements**
  -   Restored visibility of the `tqdm` progress bar for LLM sessions, which was previously being suppressed.
  -   Changed the ETA timer color in the console output to magenta for better visibility.
  -   Improved the formatting of final log messages for `experiment_manager` and `audit_experiment`.

## 6.2.0 (2025-08-21)

### Bump

- **version 6.1.5 → 6.2.0**

### Features

- **add scripted test harnesses and standardize testing framework**
  Implements a full suite of scripted, end-to-end integration tests by adding new harnesses for Layer 2 (Orchestration), Layer 3 (Data Pipeline), and Layer 5 (Migration).
  
  This commit also refactors the entire testing framework for consistency and clarity:
  - Relocates the `testing_harness` directory from `scripts/` to `tests/` to align with project standards.
  - Standardizes all test harness scripts with consistent console headers and parameter names.
  - Updates `TESTING.md` and `ROADMAP.md` to reflect the new, streamlined procedures and project status.

## 6.1.5 (2025-08-21)

### Bump

- **version 6.1.4 → 6.1.5**

### Fixes

- **resolve query generator bugs and complete unit tests**
  Resolves bugs in `query_generator.py` related to standalone execution and incorrect manifest reporting for the 'random' mapping strategy.
  
  These issues were discovered during the implementation of comprehensive unit test suites for `query_generator.py` and `config_loader.py`, which are included in this commit. This completes the test coverage for all Python scripts in the main experiment pipeline.
  
  `TESTING.md` is also updated to reflect the new 'COMPLETE' status and final code coverage for these scripts.

## 6.1.4 (2025-08-21)

### Bump

- **version 6.1.3 → 6.1.4**

### Refactor

- **streamline utility scripts and associated tests**
  Refactors the test suite for utility scripts by creating new, dedicated test files for `restore_experiment_config.py` and `upgrade_legacy_experiment.py`.
  
  Renames `restore_experiment_configuration.py` to `restore_experiment_config.py` for brevity.
  
  Removes obsolete test files for `replication_log_manager` and `run_llm_sessions`.
  
  All related documentation, diagrams, and calling scripts have been updated to reflect these changes.

## 6.1.3 (2025-08-21)

### Bump

- **version 6.1.2 → 6.1.3**

### Refactor

- **align utility naming with repair and migration workflows**
  - Renamed `restore_config.py` to `restore_experiment_configuration.py` and `patch_old_experiment.py` to `upgrade_legacy_experiment.py` to better align their names with the 'repair' and 'migrate' user workflows.
  - Fixed a `Resolve-Path` error in `migrate_experiment.ps1` by ensuring the destination directory is created before its path is used.
  - Updated all calling scripts, diagrams, and documentation to use the new, more descriptive script names.

## 6.1.2 (2025-08-21)

### Bump

- **version 6.1.1 → 6.1.2**

### Refactor

- **align architecture, add tests for core utilities**
  - feat(testing): Added a comprehensive unit test suite for experiment_auditor.py (71% coverage), validating all major state detection logic.
  - feat(testing): Added a comprehensive unit test suite for manage_experiment_log.py (79% coverage), validating all core commands.
  - fix(core): Fixed a critical bug in fix_experiment.ps1 where it was calling a renamed script, causing aggregation to fail.
  - fix(ux): Improved console output formatting for fix_experiment.ps1 and several Python compilers for better readability.
  - docs(diagrams): Updated all architecture and workflow diagrams to reflect recent script/artifact renames and to improve logical groupings.
  - docs(framework): Updated TESTING.md and other documentation to reflect the completed test suites and architectural changes.
  - chore: Removed several obsolete test files.

## 6.1.1 (2025-08-21)

### Bump

- **version 6.1.0 → 6.1.1**

### Refactor

- **align script and artifact naming for consistency**
  - Renamed orchestrate_replication.py to replication_manager.py and replication_log_manager.py to manage_experiment_log.py to clarify their roles and improve naming consistency.
  - Renamed the output log file from batch_run_log.csv to experiment_log.csv to align with other experiment-level artifacts.
  - Updated all diagrams, documentation, and script calls throughout the codebase to reflect these changes.
  - Added a comprehensive unit test suite for the experiment auditor.

## 6.1.0 (2025-08-21)

### Bump

- **version 6.0.0 → 6.1.0**

### Features

- **add full test suite and fixes for study analyzer**
  - feat(testing): Added a comprehensive unit test suite for analyze_study_results.py, achieving 66% coverage and validating all core logic and edge cases.
  - fix(analyzer): Fixed a critical shutdown bug where early exits would prevent the finally block from running, which caused PermissionErrors during testing by leaving log files locked.
  - fix(analyzer): Corrected logging logic to ensure all relevant messages are written before the script exits when all data is filtered out.
  - fix(analyzer): Resolved a PendingDeprecationWarning from seaborn by updating the boxplot generation call.
  - fix(runner): Fixed a bug in new_experiment.ps1 where the final verification audit failed due to using an outdated parameter name.
  - ci(gitignore): Added generated boxplot images to .gitignore and untracked existing files.
  - docs(testing): Updated TESTING.md to reflect the completed status of the study analyzer test suite.

## 6.0.0 (2025-08-20)

### Bump

- **version 5.9.1 → 6.0.0**

### Refactor

- **standardize parameter naming and fix reporter**
  The primary path parameter for all experiment-level wrappers (`audit_experiment.ps1`, `fix_experiment.ps1`, `migrate_experiment.ps1`) has been renamed from -TargetDirectory to -ExperimentDirectory.
  
  BREAKING CHANGE:

## 5.9.1 (2025-08-20)

### Bump

- **version 5.9.0 → 5.9.1**

### Refactor

- **refactor entire study evaluation workflow**
  The main user-facing script for study analysis has been renamed from `process_study.ps1` to `evaluate_study.ps1`. The underlying Python analyzer has been renamed from `study_analyzer.py` to `analyze_study_results.py`. All study-level wrappers now consistently use the `-StudyDirectory` parameter.

## 5.9.0 (2025-08-20)

### Bump

- **version 5.8.0 → 5.9.0**

### Features

- **add test suites for experiment and study compilers**
  - feat(testing): Added comprehensive unit test suites for `compile_experiment_results.py` (74% coverage) and `compile_study_results.py` (76% coverage), completing the validation of the entire aggregation pipeline.
  - fix(compiler): Fixed critical `ValueError` crashes in the experiment and study compilers by adding `return` statements after `sys.exit` calls, ensuring they handle empty/missing data gracefully.
  - fix(testing): Corrected several flawed assertions and mocking strategies in the test suites for `compile_replication_results.py` and `generate_replication_report.py` that were identified during this testing phase.
  - docs(testing): Updated `TESTING.md` to reflect the `COMPLETE` status of the entire aggregation pipeline.

## 5.8.0 (2025-08-20)

### Bump

- **version 5.7.0 → 5.8.0**

### Features

- **add test suites for bias, reporter, and compiler**
  - feat(testing): Added comprehensive unit test suites for `run_bias_analysis.py` (86%), `generate_replication_report.py` (90%), and `compile_replication_results.py` (78%).
  - fix(core): Fixed critical `UnboundLocalError` bugs in the reporter and compiler by adding `return` statements after `sys.exit` calls, ensuring scripts terminate correctly after fatal errors.
  - fix(testing): Corrected flawed assertions and mocking strategies across the test suites for the bias analyzer, report generator, and replication compiler to ensure they pass reliably.
  - docs(testing): Updated `TESTING.md` to reflect the `COMPLETE` status for multiple modules and reorganized the table to prioritize aggregation scripts.
  - docs(framework): Clarified the definition of reproducibility in the Framework Manual introduction for improved technical accuracy.

## 5.7.0 (2025-08-19)

### Bump

- **version 5.6.4 → 5.7.0**

### Features

- **add full test suite and fixes for performance analyzer**
  - feat(analyzer): Added a comprehensive unit test suite for `analyze_llm_performance.py`. The suite validates the main orchestrator, all core statistical functions with edge cases, and the robust parsing of complex file formats, achieving 63% coverage.
  - fix(analyzer): Fixed a critical bug where the script would continue execution after a fatal error or a clean "zero response" exit when `sys.exit` was mocked during testing.
  - fix(testing): Corrected failing tests for the analyzer that were improperly using `assertRaises(SystemExit)`. The tests now correctly assert that the mock was called with the appropriate exit code.
  - fix(release): The `finalize_release.py` script now automatically adds a blank line after each new entry in CHANGELOG.md for improved formatting.
  - docs(testing): Updated `TESTING.md` to reflect the `COMPLETE` status of the `analyze_llm_performance.py` test suite.
  - docs(contributing): Clarified in `CONTRIBUTING.md` that the release script is solely responsible for changelog formatting.

## 5.6.4 (2025-08-19)

### Bump

- **version 5.6.3 → 5.6.4**

### Fixes

- **fix parser column reordering and add full test suite**
  - fix(parser): Refactored the LLM response parser to correctly reorder score columns based on the header, fixing a critical data integrity bug. The parser now uses the `(YYYY)` birth year as a reliable anchor for splitting data rows.
  - test(parser): Added a comprehensive unit test suite for `process_llm_responses.py`. Achieved 67% coverage by validating various response formats and failure modes.
  - docs(parser): Updated the docstring for the main parsing function to reflect its new, more robust logic.
  - docs(testing): Updated `TESTING.md` to reflect the completion of the `process_llm_responses.py` tests.
  
## 5.6.3 (2025-08-19)

### Bump

- **version 5.6.2 → 5.6.3**

### Fixes

- **add full unit test suite and refactor for testability**
  - test(build_queries): Added a comprehensive unit test suite for `build_llm_queries.py`. Achieved 68% coverage, validating the orchestration logic for new runs, continued runs, and critical failure modes like insufficient data and worker script errors.
  
  - refactor(build_queries): Refactored `build_llm_queries.py` to load configuration defaults inside the `main()` function instead of at the module level. This change was critical for making the script testable in isolation without affecting its production behavior.
  
  - docs(testing): Updated `TESTING.md` to reflect the completion of the `build_llm_queries.py` tests.

## 5.6.2 (2025-08-19)

### Bump

- **version 5.6.1 → 5.6.2**

### Fixes

- **add orchestrator tests and standardize logging**
  - test(orchestrator): Added a comprehensive unit test suite for `orchestrate_replication.py` (77% coverage), validating all core control flows.
  - test(build_queries): Created the initial test file and plan for `build_llm_queries.py`.
  - fix(orchestrator): Corrected a bug to ensure a "FAILED" report is always generated when the pipeline fails.
  - fix(logging): Implemented standardized transcript logging for `process_study.ps1`.
  - style(changelog): Manually added a blank line between release entries in `CHANGELOG.md` for improved readability.
  - docs(testing): Updated `TESTING.md` with the latest test plan status and fixed table formatting.
  - chore: Updated `ROADMAP.md` to reflect the completion of the `process_study.ps1` logging fix.

## 5.6.1 (2025-08-19)

### Bump

- **version 5.6.0 → 5.6.1**

### Fixes

- **standardize logging and improve test harness**
  - fix(logging): Standardized logging across experiment wrappers and their Python backends to ensure real-time, sequential, and clear output with standardized relative paths.
  
  - refactor(testing): Replaced the manual copy-paste workflow for Layer 4 integration testing with a robust, script-based harness that uses a state file to reliably manage and clean up multiple test runs.
  
  - docs(testing): Overhauled TESTING.md to document the new script-based harness with clearer, safer instructions.
  
  - chore(linting): Updated linters to exclude the new testing harness scripts.
  
  - chore: Updated ROADMAP.md to reflect the completion of the logging fix.

## 5.6.0 (2025-08-18)

### Bump

- **version 5.5.0 → 5.6.0**

### Features

- **Overhaul and validate core experiment workflow**
  This is a major stabilization and validation release that hardens the entire experiment workflow. A full end-to-end test of the `new -> audit -> fix` lifecycle was conducted, revealing and leading to fixes for several deep, subtle bugs.
  
  **Features:**
  - Overhauled all user-facing PowerShell wrappers (`new_experiment.ps1`, `audit_experiment.ps1`, etc.) with a robust `Get-ProjectRoot` function. This makes them context-independent and guarantees they function correctly.
  - Completely refactored `TESTING.md` into a comprehensive guide with safe, scripted procedures for all manual and integration tests, including a new timestamped backup-and-restore mechanism.
  
  **Bug Fixes:**
  - Fixed a critical, silent bug in `config_loader.py` where `.ini` files created by PowerShell were not being parsed correctly due to a file encoding (BOM) issue. The loader now correctly uses `encoding='utf-8-sig'`.
  - Fixed a major control-flow bug in the `experiment_manager.py` main loop that could cause an infinite loop on step failure.
  - Fixed a bug in the `TESTING.md` harness where the test configuration and data did not match the production code's expectations.
  
  **Documentation:**
  - Added a new high-level project overview diagram to `DOCUMENTATION.md`.
  - Updated the `TESTING.md` status tables to reflect the successful completion of the core workflow testing.
  - Made several strategic updates to the `ROADMAP.md` to improve the pre-publication workflow.

## 5.5.0 (2025-08-17)

### Bump

- **version 5.4.5 → 5.5.0**

### Features

- **Enhance and validate data preparation orchestrator**
  This commit finalizes the data preparation pipeline by significantly enhancing the `prepare_data.ps1` orchestrator and ensuring all project documentation is consistent and accurate.
  
  The orchestrator has been successfully validated through a multi-stage testing process using mock scripts to confirm its state machine logic.
  
  Key changes include:
  
  **`prepare_data.ps1` Orchestrator:**
  - Refactored to be a stateful, resumable script that is aware of the entire pipeline.
  - Now intelligently pauses with clear user instructions when a manual step (e.g., Solar Fire processing) is required.
  - Corrected several PowerShell syntax and variable parsing errors identified during interactive testing.
  - Improved readability by refactoring complex strings to use PowerShell "here-strings".
  - Polished final console output by suppressing the return value of the status function.
  
  **Documentation & Consistency:**
  - Harmonized the study's sample size to 6,000 subjects across `DOCUMENTATION.template.md` and `article_main_text.md`.
  - Corrected outdated script names and file paths in `DOCUMENTATION.template.md` and `data/README.md` to align with the current codebase.
  - Added a "Project Philosophy" section to the main `README.md` to centralize core principles.
  - Added a "Licensing" section to `README.md` to clarify the dual-license model (GPL-3.0 for code, CC BY-SA 4.0 for data/docs).
  - Updated `ROADMAP.md` to remove a redundant documentation task and add new, specific pre-publication action items.
  
  **Testing Framework:**
  - Updated `TESTING.md` to formally describe the multi-layered testing strategy (Unit, Orchestration, Integration).
  - Updated the status of `prepare_data.ps1` to "IN PROGRESS" to reflect the successful completion of the orchestration logic tests, pending the final end-to-end integration test.

## 5.4.5 (2025-08-17)

### Bump

- **version 5.4.4 → 5.4.5**

### Refactor

- **test suites and align UX for remaining data prep scripts**
  - Creates new pytest suites for prepare_sf_import, create_subject_db, neutralize_delineations, and generate_personalities_db.
  - Completes the refactoring of all data preparation scripts to align their startup logic (stale check, interactive prompt) and UX with the modern project standard.
  - Updates TESTING.md with the completed status of all data preparation scripts.

## 5.4.4 (2025-08-16)

### Bump

- **version 5.4.3 → 5.4.4**

### Fixes

- **Add test suite for final candidate selection and fix linter**
  - Creates a new pytest suite for select_final_candidates.py, covering its full data transformation workflow.
  - Refactors select_final_candidates.py to align its startup logic (stale check, interactive prompt) with the modern project standard.
  - Fixes an AttributeError in the lint_file_headers.py script.
  - Updates TESTING.md with the status of the newly tested script.

## 5.4.3 (2025-08-16)

### Test

- **Add test suite for OCEAN scoring and align UX**
  - Creates a new pytest suite for generate_ocean_scores.py, covering response parsing, variance calculation, and the pre-flight check.
  - Refactors generate_ocean_scores.py to align its startup logic (stale check, interactive prompt) and UX with the modern project standard.
  - Polishes the UX of the lint_file_headers.py script for consistency.
  - Updates TESTING.md with the status of the newly tested script.

## 5.4.2 (2025-08-16)

### Test

- **Add test suite for eminence scoring and update docs**
  - Creates a new pytest suite for generate_eminence_scores.py, covering response parsing, resumability, and the main orchestrator loop.
  - Refactors generate_eminence_scores.py to add a stale-check and align its UX with the modern project standard.
  - Updates CONTRIBUTING.md to formally document the architectural standard for resilient pipeline scripts.
  - Updates TESTING.md with the status of the newly tested script.

## 5.4.1 (2025-08-16)

### Bump

- **version 5.4.0 → 5.4.1**

### Refactor

- **Establish test suite and refactor core scripts**
  - Establishes a formal test suite with pytest and coverage.
  - Creates a TESTING.md document to track strategy and status.
  - Refactors select_eligible_candidates.py to a modern, resumable, Pandas-based architecture.
  - Adds unit tests for fetch_adb_data, find_wikipedia_links, validate_wikipedia_pages, and select_eligible_candidates.
  - Hardens pyproject.toml and build_docs.py for robustness.

## 5.4.0 (2025-08-16)

### Bump

- **version 5.3.0 → 5.4.0**

### Features

- **Refactor validation pipeline and add master orchestrator**
  Introduces `prepare_data.ps1`, a master orchestrator script that runs the entire data preparation pipeline with a single command.
  
  - Replaces the monolithic `validate_adb_data.py` with a more robust, two-step pipeline (`find_wikipedia_links.py`, `validate_wikipedia_pages.py`).
  - Hardens all data scripts with intelligent retries for timeouts, stale-data detection, safe overwrite logic, and robust interrupt handling.
  - Fixes critical regressions in death date validation and Wikipedia search logic, restoring original accuracy.
  - Updates all relevant documentation and diagrams to reflect the new workflow.
## 5.3.0 (2025-08-15)

### Bump

- **version 5.2.3 → 5.3.0**

### Features

- **Refactor validation pipeline into modular scripts**
  Replaces the monolithic `validate_adb_data.py` with a more robust, modular, and user-friendly two-step pipeline (`find_wikipedia_links.py` and `validate_wikipedia_pages.py`).
  
  - Implements intelligent retries for timed-out records and adds stale-data detection to ensure data integrity.
  - Adds safe overwrite logic with interactive prompts and automatic backups to all data generation scripts.
  - Fixes critical bugs related to script hanging, inconsistent logging, and incorrect summary reporting.
  - Updates all relevant documentation, diagrams, and developer guides to reflect the new, more modular workflow.
  
## 5.2.3 (2025-08-14)

### Bump

- **version 5.2.2 → 5.2.3**

### Fixes

- **Refine study-level workflow UX and logging**
  Refactors the study-level workflow scripts (audit, fix, migrate) based on manual testing feedback.
  
  - Improves logging by adding prominent banners for sub-processes and centralizing PDM detection messages to reduce noise.
  - Enhances user experience by replacing harsh red "FAILED" banners for controlled halts with clearer, yellow "HALTED" banners that provide specific, actionable advice.
  - Updates documentation and diagrams to reflect the script rename from `repair_study.ps1` to `fix_study.ps1`, ensuring consistency.

## 5.2.2 (2025-08-14)

### Bump

- **version 5.2.1 → 5.2.2**

### Fixes

- **improve robustness of repair, migration, and build workflows**
  - Make the experiment repair workflow resilient to transient API failures by cleaning up old error files and handling session failures gracefully.
  - Fix multiple bugs in the migration workflow, including an incorrect file path for patch scripts and an infinite loop after reprocessing.
  - Add intelligent up-to-date checks to the build script to skip unnecessary `.docx` and `.md` file regeneration, improving efficiency.
  - Improve the console output and user prompts for the `fix_experiment` and `migrate_experiment` scripts to be clearer and more informative.

## 5.2.1 (2025-08-14)

### Bump

- **version 5.2.0 → 5.2.1**

### Refactor

- **centralize audit logic into single source of truth**
  Enforce separation of concerns by making `experiment_auditor.py` the single source of truth for all audit-related logic.
  
  - Remove duplicated audit logic from `experiment_manager.py` and replace it with an import from the auditor.
  - Create a new `src/utils/` directory for standalone maintenance and analysis scripts, moving five files to clean up the main source directory.
  - Delete the obsolete `filter_adb_candidates.py` script.
  - Fix a bug in `generate_replication_report.py` that incorrectly duplicated Top-1 accuracy metrics.
  - Perform a comprehensive update of all documentation (docstrings, architecture diagrams, data format diagrams, and main text) to reflect the new, cleaner architecture.

## 5.2.0 (2025-08-13)

### Bump

- **version 5.1.4 → 5.2.0**

### Features

- **Improve study processing and audit UX**
  This commit introduces a series of significant improvements to the study-level workflow scripts (`process_study.ps1`, `audit_study.ps1`) based on manual testing, focusing on bug fixes, clarity, and user experience.
  
  ### Key Changes:
  
  1.  **Improved `process_study.ps1` Logic:**
      *   The script now correctly handles studies that are already complete, prompting the user for confirmation before re-running and exiting gracefully if the user aborts.
      *   When the pre-flight audit fails, it now prints a clear summary of which steps were skipped, providing better context than a generic error.
      *   Standardized the initial startup banner to be consistent with other scripts.
  
  2.  **Enhanced `audit_study.ps1`:**
      *   Added a `-NoHeader` switch to suppress the PDM detection message, allowing it to be called cleanly from other scripts.
      *   The real-time progress table is now more informative, using a yellow `[ WARN ]` for non-critical issues (like needing an update) instead of a red `[ FAIL ]`.
      *   The completeness check now uses a yellow `[ MISSING ]` status for un-generated artifacts, which is more accurate than `[ FAIL ]`.
  
  3.  **Bug Fixes:**
      *   Fixed a critical bug in `audit_study.ps1` where it would incorrectly validate an experiment that had zero replication runs. It now correctly checks against the `num_replications` value from `config.ini`.
  
  4.  **Standardized PDM Detection:**
      *   Standardized the "PDM detected" message snippet across all PowerShell scripts (`fix_experiment.ps1`, `fix_study.ps1`, `new_experiment.ps1`, etc.) for a consistent startup experience.
## 5.1.4 (2025-08-13)

### Bump

- **version 5.1.3 → 5.1.4**

### Refactor

- **Rename 'repair' scripts to 'fix' for clarity**
  This commit renames the main "fix-it" scripts from `repair_*` to `fix_*` to better reflect their dual functionality of performing both critical data repairs and simple analysis updates.
  
  Key changes:
  - Renamed `repair_experiment.ps1` to `fix_experiment.ps1`.
  - Renamed `repair_study.ps1` to `fix_study.ps1`.
  
  Consequential updates:
  - Updated the output of `fix_experiment.ps1` to explicitly state whether it is performing a "repair" or an "update".
  - Updated all documentation (`DOCUMENTATION.template.md`, `article_supplementary_material.md`), diagrams, and calling scripts (`audit_study.ps1`) to use the new `fix_*` naming convention.
  
  Note: The modification to `project_scope_report.md` is not covered by this summary and should be reviewed separately.
  
## 5.1.3 (2025-08-13)

### Bump

- **version 5.1.2 → 5.1.3**

### Fixes

- **Fix and harden experiment migration workflow**
  Resolves several critical bugs that caused the `migrate_experiment.ps1`
  workflow to fail during testing. The migration process is now robust
  and handles corrupted, valid, and repairable experiments correctly.
  
  Key fixes include:
  - Making the `--migrate` mode in `experiment_manager.py` smarter by
    conditionally running the legacy patcher, preventing crashes on
    modern-but-broken experiments.
  - Correcting logic in `orchestrate_replication.py` to ensure both .txt
    and .json response files are checked for during repairs.
  - Implementing robust, real-time output streaming in the PowerShell
    wrapper to fix buffering and file-locking issues.
  
  Additionally, enhances the console UI by improving the clarity, color,
  and formatting of user prompts and status messages.
## 5.1.2 (2025-08-13)

### Bump

- **version 5.1.1 → 5.1.2**

### Fixes

- **Fix repair workflow and improve console UI**
  Fixes several critical bugs that caused the `repair_experiment.ps1`
  workflow to fail during testing. The script now correctly handles
  all three core scenarios: automatic repair, graceful halting for
  non-repairable experiments, and interactive updates for valid ones.
  
  Key fixes include:
  - Resolving a `NameError` in `orchestrate_replication.py`.
  - Correcting an `unrecognized argument` error in `experiment_manager.py`.
  - Fixing a PowerShell `ParserError` in `repair_experiment.ps1`.
  
  Improves the console UI by standardizing all step and result banners
  for a more consistent and professional user experience.
  
## 5.1.1 (2025-08-13)

### Bump

- **version 5.1.0 → 5.1.1**

### Fixes

- **Fix repair workflow and enhance console logging**
  Corrects several critical bugs that caused the `repair_experiment.ps1`
  workflow to fail during testing.
  
  - Fixes an `unrecognized argument: --quiet` error by removing an invalid
    flag pass from `experiment_manager.py` to `orchestrate_replication.py`.
  - Resolves a `NameError` in `orchestrate_replication.py` by ensuring
    the `all_stage_outputs` list is always initialized.
  - Corrects a PowerShell `ParserError` in `repair_experiment.ps1`.
  
  Additionally, improves the user experience by standardizing and colorizing
  console log banners across `repair_experiment.ps1`, `experiment_manager.py`,
  and `orchestrate_replication.py` for better clarity and consistency.

## 5.1.0 (2025-08-13)

### Bump

- **version 5.0.4 → 5.1.0**

### Features

- **Enhance experiment audit workflow and UI**
  Isolates experiment auditing logic into a new, dedicated script,
  `src/experiment_auditor.py`, improving separation of concerns.
  
  The `audit_experiment.ps1` script now automatically saves a clean,
  uncolored copy of its full report to `experiment_audit_log.txt` inside
  the audited directory.
  
  Improves audit accuracy and user experience by:
  - Refining failure classification logic.
  - Standardizing UI banners for color, terminology, and error handling.

## 5.0.4 (2025-08-12)

### Bump

- **version 5.0.3 → 5.0.4**

### Refactor

- **separate audit logic into dedicated script**
  The experiment_manager.py script was refactored to improve maintainability and separation of concerns. Its dual role of read-only auditing and state management made it complex and difficult to test effectively.
  
  This change introduces experiment_auditor.py, a new script dedicated solely to performing comprehensive, read-only verification of an experiment's state. The experiment_manager.py script is now a streamlined state-machine controller that orchestrates actions based on the auditor's findings.
  
  All relevant PowerShell wrappers, documentation, and diagrams have been updated to reflect this new, more robust architecture.

## 5.0.3 (2025-08-12)

### Bump

- **version 5.0.2 → 5.0.3**

### Refactor

- **harden error handling and standardize user experience**
  Refactors the entire data preparation and main experiment pipelines to improve robustness, consistency, and the developer/user experience.
  
  Data Preparation Pipeline:
  - Standardizes all ten scripts to a consistent UX model.
  - Implements a universal `--force` flag for non-interactive overwriting.
  - Ensures automatic, timestamped backups are created for all overwritten files.
  - Replaces custom color codes with the `colorama` library for cross-platform consistency.
  
  Main Experiment Pipeline:
  - Fixes a chain of silent failures in the `new_experiment.ps1` workflow by hardening error handling in all child scripts (`build_llm_queries`, `orchestrate_replication`, etc.).
  - Corrects the verbosity logic to align with the design principle: high-level logs are now shown by default, and `--verbose` enables debug-level output.
  - Restores real-time, non-buffered logging for stage progress.
  
  Documentation:
  - Adds a "Design Principles" section to CONTRIBUTING.md.
  - Updates the project ROADMAP.md.
  - Corrects a workflow diagram to reflect the current codebase.

## 5.0.2 (2025-08-12)

### Bump

- **version 5.0.1 → 5.0.2**

### Fixes

- **Finalize pipeline scripts and documentation**
  Script Fixes:
  - `select_final_candidates.py`: Corrected a bug preventing the script from re-indexing its output and properly replacing the `CountryState` column with the resolved `Country` name.
  - `create_subject_db.py`: Fixed a crash caused by referencing an obsolete input file and a non-existent `EminenceScore` column.
  - `generate_personalities_db.py`: Standardized console logging for consistency.
  
  Documentation Overhaul:
  - The monolithic data prep flow diagram has been split into three clearer, stage-specific diagrams (Sourcing, Scoring, Generation).
  - All data preparation diagrams now use a consistent color scheme and have been updated to reflect the latest script logic, including labels for LLM-assisted steps.
  - Logic flowcharts for several scripts have been rearranged into a more compact, horizontal layout to improve readability in the final documents.
  - Console logging for all final pipeline scripts has been cleaned up and standardized for a better user experience.

## 5.0.1 (2025-08-11)

### Bump

- **version 5.0.0 → 5.0.1**

### Refactor

- **Overhaul and harden data generation scripts**
  This commit introduces a major refactoring of the data preparation pipeline to improve performance, resilience, and user experience.
  
  Key Improvements:
  - Introduces a hybrid `--fast` mode to `neutralize_delineations.py` for rapid initial runs, followed by a robust, granular default mode for resuming and fixing any failed tasks.
  - Refactors `neutralize_delineations.py` to use atomic, single-item tasks in its default mode, permanently solving LLM response truncation issues.
  - Hardens `generate_ocean_scores.py` with a robust pre-flight check that re-analyzes all existing data on startup, ensuring correct finalization of interrupted runs.
  - Overhauls console logging in `neutralize_delineations.py` for clarity, providing clean, task-by-task status updates.
  - Updates all related documentation, docstrings, and diagrams to reflect the new, more sophisticated workflows.

## 5.0.0 (2025-08-11)

### Bump

- **version 4.4.0 → 5.0.0**

### Features

- **Overhaul data prep pipeline for efficiency and automation**
  This major overhaul re-engineers the entire data preparation pipeline to be more efficient, robust, and automated. All data quality checks are now performed *before* any expensive LLM scoring, and the previously manual delineation neutralization process is now a fully automated, resumable script.
  
  - **Efficiency Overhaul:**
    - Introduces `select_eligible_candidates.py` to perform all data quality checks upfront.
    - Updates `generate_eminence_scores.py` and `generate_ocean_scores.py` to use this pre-filtered list, significantly reducing API costs and runtime.
    - Replaces `filter_adb_candidates.py` with `select_final_candidates.py` for a more logical final selection and transformation step.
  
  - **Automation:**
    - Introduces `neutralize_delineations.py` to fully automate the rewriting of the esoteric delineation library using an LLM.
  
  - **Data Integrity:**
    - Adds a `BirthYear` column to `eminence_scores.csv` and `ocean_scores.csv` for better disambiguation.
    - Includes `patch_eminence_scores.py` to safely upgrade existing data.
    - Updates `fetch_adb_data.py` to sanitize tab characters at the source.
  
  - **Documentation:**
    - Updates all documentation (Framework Manual, Supplementary Material, Data Dictionary) and all associated diagrams to reflect the new, final pipeline.
  
  BREAKING CHANGE: The data preparation pipeline scripts have been renamed and their sequence altered. `filter_adb_candidates.py` has been removed and replaced by `select_eligible_candidates.py` and `select_final_candidates.py`. The schemas for `eminence_scores.csv` and `ocean_scores.csv` have been updated to include a `BirthYear` column. Any workflows or scripts relying on the old pipeline structure or data formats will need to be updated.
## 4.4.0 (2025-08-10)

### Bump

- **version 4.3.0 → 4.4.0**

### Features

- **OCEAN scoring and dynamic cutoff to data pipeline**
  Finalizes the data preparation pipeline by introducing a robust, data-driven method for determining the final subject pool size.
  
  - Introduces the `generate_ocean_scores.py` script, which uses a sophisticated "M of N" variance-based cutoff rule to automatically stop when personality diversity declines.
  - The script is fully resumable, archives discarded data, includes a smart pre-flight check, and generates comprehensive summary and audit reports.
  - Updates `filter_adb_candidates.py` to use the output of the OCEAN script as the definitive source for the final subject set, removing the previous hardcoded limit.
  - All corresponding documentation, including the Framework Manual, supplementary materials, and all diagrams, has been updated to reflect the new, completed pipeline.
  This completes the development of the data preparation work stream.
  
## 4.3.0 (2025-08-10)

### Bump

- **version 4.2.0 → 4.3.0**

### Features

- **complete eminence score generation script**
  This commit finalizes the development of `generate_eminence_scores.py`, a robust, resumable orchestrator for creating the eminence scores foundational asset.
  
  - Implemented the new script with key features including calibrated LLM prompting, safety checks (backup, force flag), and automated summary reporting.
  - Added a new `[DataGeneration]` section to `config.ini` to manage settings for data asset creation scripts.
  - Iteratively refined the LLM prompt with historical anchors and explicit instructions to solve calibration issues and improve score quality.
  - Updated all project documentation (ROADMAP, main manual, data dictionary, and diagrams) to reflect the new automated data preparation workflow.
  - Fixed a critical bug in the save function that was overwriting previous results, ensuring correct data persistence.
  - Added a custom `changelog_template.md` and updated `pyproject.toml` to fix an issue where `commitizen` would not add a blank line between release notes.

## 4.2.0 (2025-08-09)

### Bump

- **version 4.1.0 → 4.2.0**

### Features

- **replace name-matching with robust idADB pass-through**
  Replaces the fragile name-matching process with a deterministic Base58 encoding strategy to guarantee data integrity across the manual Solar Fire step.
  - Adds id_encoder.py utility for Base58 encoding/decoding.
  - prepare_sf_import.py now encodes the idADB and injects it into the ZoneAbbr field.
  - create_subject_db.py now decodes the idADB for a perfect 1-to-1 merge, eliminating the need for fuzzy matching.
  - Hardens create_subject_db.py with strict "perfect or nothing" validation, aborting and creating a diagnostic report on any failure.
  - Overhauls the Solar Fire instructions in the supplementary material for clarity, accuracy, and ease of use.

## 4.1.0 (2025-08-09)

### Bump

- **version 4.0.0 → 4.1.0**

### Features

- **finalize data preparation pipeline**
  Updates all data preparation scripts and related documentation to handle the new standardized data format using Index and idADB.
  - Simplifies create_subject_db.py by removing external lookups.
  - Updates prepare_sf_import.py, generate_personalities_db.py, and build_llm_queries.py for the new format.
  - Aligns user-facing messages, backup logic, and error handling across all scripts.
  - Corrects .gitignore to exclude generated data files and removes them from tracking.
  - Updates all relevant documentation (DOCUMENTATION.template.md, data/README.md, CONTRIBUTING.md) and diagrams.

## 4.0.0 (2025-08-09)

### Bump

- **version 3.18.0 → 4.0.0**

### Features

- **Overhaul and stabilize the data preparation pipeline**
  - Standardized on stable identifiers (Index, idADB) across all data preparation scripts, fixing the critical eminence score sorting bug.
  - Fixed multiple critical bugs in `validate_adb_data.py` including crashes (NameError, UnboundLocalError), incorrect URL construction for Research entries, and SSL/timeout errors.
  - Improved diagnostics and UX with colored logging, a cyan progress bar, and Index-prefixed messages for better readability during long validation runs.
  - Enhanced the validation summary report with a detailed breakdown of failure types and improved column alignment.
  - Refactored the `analyze_research_patterns.py` diagnostic script for accuracy and clarity.
  - Updated all relevant documentation (READMEs, articles, framework manual) to reflect the new, robust pipeline and clarify key methodological details.
  
  BREAKING CHANGE: The file formats for `adb_raw_export.txt`, `adb_validation_report.csv`, and `adb_filtered_5000.txt` have changed. They now use `Index` and `idADB` as the primary key columns, and column order has been updated.

## 3.18.0 (2025-08-07)

### Bump

- **version 3.17.1 → 3.18.0**

### Features

- **automate data fetching and enhance validation pipeline**
  This overhauls the entire data preparation pipeline, transitioning it to a fully automated, resilient, and intelligent workflow.
  
  -   **Automated Data Sourcing:** `fetch_adb_data.py` is now the primary entry point, generating an enriched 17-column raw data file with bios, categories, and correct ADB page links. It also automatically creates the `adb_category_map.csv` asset.
  -   **Intelligent Validation:** `validate_adb_data.py` now distinguishes between 'Person' and 'Research' entries using a new config file. For Person entries, it uses a Wikipedia search API as a robust fallback for missing links.
  -   **Enhanced Resilience:** The validation script is now protected against hanging with per-record timeouts and a throttling mechanism for Wikipedia searches to prevent rate-limiting.
  -   **Improved Usability:** Adds `--retry-failed` and `--report-only` modes, a detailed real-time progress bar, and a comprehensive, well-formatted summary report.
  -   **Documentation Sync:** All documentation and diagrams (`arch_prep_codebase`, `data_prep_flow`, `flow_prep_pipeline`) have been updated to reflect the new workflow.
  -   **Preserved Legacy Flow:** The original scripts and data file are preserved as `_legacy` versions for historical reference and reproducibility.

## 3.17.1 (2025-08-06)

### Bump

- **version 3.17.0 → 3.17.1**

### Fixes

- **Correct pagination logic to fetch unique pages**
  Fixes a critical pagination bug in `fetch_adb_data.py` that caused it to repeatedly fetch the first page of results.
  
  The original script incorrectly used the complex "initial search" POST request for all pages. This caused the server to re-run the search each time instead of paginating, leading to a corrupt data file with duplicated records.
  
  The `fetch_all_data` function is now rewritten to implement the server's correct two-stage API logic:
  - A complex `POST` request with a full JSON payload is sent once for Page 1.
  - Simple `GET` requests with query parameters (`uid`, `pageNumber`) are sent for all subsequent pages.
  
  This change resolves the data corruption symptoms (the "27 unique codes" issue and the final page "overfetch"). It also includes new diagnostic scripts and documentation updates related to this debugging effort.

## 3.17.0 (2025-08-06)

### Bump

- **version 3.16.0 → 3.17.0**

### Features

- **Establish comprehensive documentation and CI workflow**
  This major update establishes a complete, professional documentation suite and a robust CI workflow.
  
  - Rewrites and aligns all architectural diagrams (main and prep pipelines) with a unified, consistent visual style.
  - Corrects inaccuracies in architectural diagrams to match the actual codebase execution flow.
  - Implements a new GitHub Actions CI workflow for automated linting and documentation validation.
  - Creates a `ROADMAP.md` file to track all remaining development work.
  - Overhauls the main `README.md` and creates a detailed `data/README_DATA.md`.
  - Documents the new CI workflow in `CONTRIBUTING.md` and `docs/DOCUMENTATION.md`.
  - Refactors data preparation scripts for clarity (e.g., `generate_database.py` -> `generate_personalities_db.py`) and updates all documentation to match.

## 3.16.0 (2025-08-05)

### Bump

- **version 3.15.0 → 3.16.0**

### Features

- **add automated adb data fetching script**
  Introduces `src/fetch_adb_data.py` to fully automate the data extraction process from the Astro-Databank website, replacing the previous manual method.
  
  The new script handles the entire workflow:
  - Authenticates with the site using credentials from the .env file.
  - Scrapes the search page for all required dynamic security tokens.
  - Constructs and sends a complete JSON payload to the site's internal API.
  - Parses the paginated JSON responses and saves the detailed data incrementally.
  
  Key features include an interactive user prompt with an automatic backup system to prevent accidental data loss.
  
  This change also updates all relevant documentation and diagrams (workflow, data flow, and code architecture) to reflect the new, recommended data acquisition pipeline. The .gitignore has been updated to exclude the script's output file and any debugging artifacts.

## 3.15.0 (2025-08-05)

### Bump

- **version 3.14.0 → 3.15.0**

### Features

- **add data integration script and fix encoding**
  Introduces create_subject_database.py to the data preparation pipeline.
  
  This new script integrates the raw Solar Fire chart export with other data sources and fixes critical character encoding errors before generating the master subject_db.csv.
  
  - Moves subject_db.csv to a new data/processed/ directory.
  - Updates all documentation and diagrams to reflect the new 4-step data pipeline.

## 3.14.0 (2025-08-05)

### Bump

- **version 3.13.0 → 3.14.0**

### Features

- **Refactors `generate_database.py` to be more robust and user-friendly**
  - The script now dynamically loads point weights and balance thresholds from their respective CSV files in `data/foundational_assets/` instead of using hardcoded values.
  - Adds a confirmation prompt and a timestamped backup feature to prevent accidental overwrites of `personalities_db.txt`.
  - Fixes a critical bug where incorrect classification keys were being generated, resulting in empty descriptions in the output database.
  - Updates documentation and diagrams to reflect the new logic and data flow.

## 3.13.0 (2025-08-05)

### Bump

- **version 3.12.0 → 3.13.0**

### Features

- **architect data prep pipeline with master subject database**
  Introduces a master `subject_db.csv` to serve as a single, auditable source of truth for the data generation pipeline. This decouples complex data parsing and integration from the final personality description assembly.
  
  - Creates `create_subject_database.py` to flatten and enrich chart data by cross-referencing all source files.
  - Implements a robust name normalization function that handles encoding errors (mojibake), all quote types, diacritics, and name order.
  - Replaces manual name corrections for truncation errors with an automated string slicing method.
  - Refactors `generate_database.py` to use the new, simpler `subject_db.csv` as its input.
  - Adds user confirmation prompts and automated backups to all data preparation scripts for improved safety.
  - Consolidates the data directory structure for better organization, moving assets to `foundational_assets` and intermediate files to `intermediate`.
  
## 3.12.0 (2025-08-04)

### Bump

- **version 3.11.0 → 3.12.0**

### Documentation

- **Update diagrams to reflect removal of run_llm_sessions.py**
  This commit updates three key architecture and workflow diagrams to align with the current system architecture after a recent refactoring.
  
  The `run_llm_sessions.py` script was removed, and the `orchestrate_replication.py` script now directly manages parallel calls to the `llm_prompter.py` worker.
  
  The following diagrams were modified to reflect this change:
  - `arch_main_codebase.mmd`
  - `data_main_flow.mmd`
  - `flow_main_1_new_experiment.mmd`

### Features

- **Enhance data preparation scripts and documentation**
  Improves the data preparation pipeline with enhanced script robustness, user safety features, and updated documentation.
  
  Key changes include:
  - Adds interactive confirmation prompts and automated backups to `validate_adb_data.py` and `filter_adb_candidates.py` to prevent accidental file overwrites.
  - Improves user messaging with clearer instructions and color-coded warnings.
  - Enhances web scraping logic in the validation script.
  - Redirects long console logs in the filtering script to a dedicated report file.
  - Updates all relevant documentation and diagrams to reflect the new script behaviors and data flows.
  - Adds rules to .gitignore to exclude generated data and backups.

## 3.11.0 (2025-08-04)

### Bump

- **version 3.10.0 → 3.11.0**

### Features

- **Add validation script and overhaul candidate filtering**
  This commit introduces a major overhaul of the data preparation pipeline to make it more robust, automated, and reproducible.
  
  The core of this change is the new `validate_adb_data.py` script, which programmatically audits the raw data against Wikipedia to produce a static validation report.
  
  The `filter_adb_candidates.py` script has been completely rewritten to use this new report for its primary filtering. This change includes:
  - A corrected, robust, on-the-fly duplicate check.
  - Significantly improved logging with clear, formatted, and colored stage transitions for better readability.
  - More accurate reporting of record counts, with thousand-separators for clarity.
  
  Finally, all project documentation (`article_main_text.md`, `article_supplementary_material.md`, and `DOCUMENTATION.template.md`) has been updated to reflect this new, more rigorous data preparation workflow.

## 3.10.0 (2025-08-04)

### Bump

- **version 3.9.0 → 3.10.0**

### Features

- **Harden and automate data preparation pipeline**
  This release focuses on hardening and automating the data preparation pipeline, introducing a new validation script, fixing critical bugs, and updating all relevant documentation to ensure full reproducibility.
  FEATURES:
  New Wikipedia Validation Script (src/validate_adb_data.py): Created a powerful, parallelized script to audit the raw ADB data against live Wikipedia pages, with robust interrupt/resume capabilities and a user-friendly console interface.
  Automated Duplicate Detection (filter_adb_candidates.py): Implemented automated logic to detect and remove complex duplicate entries from the raw data.
  New Comparison Utility (scripts/validate_import_file.py): Added a new developer script for comparing formatted name/year lists.
  BUG FIXES:
  Deterministic Filtering (filter_adb_candidates.py): Fixed a critical reproducibility bug by implementing a stable, two-level sort (eminence, ARN) to resolve ties. Also fixed a bug where URL-encoded characters in names were not decoded.
  Data Formatting (prepare_sf_import.py): Fixed critical bugs that produced invalid CQD files with missing commas and corrupted latitude/longitude data.
  Thread Safety (validate_adb_data.py): Fixed a critical race condition caused by the use of a global variable.
  DOCUMENTATION & HOUSEKEEPING:
  Documentation Updates: Updated the main article, supplement, and DOCUMENTATION.template.md to reflect the new automated validation process and clarify the project's reproducibility scope regarding static data sources (ADB export, eminence scores).
  Diagrams: Updated all four data preparation diagrams to include the new validation script and reflect the enhanced filtering logic.
  CONTRIBUTING.md: Added a new section documenting the purpose of developer utility scripts.
  Version Control: Removed the intermediate, generated file data/sources/sf_chart_import.csv from Git and updated .gitignore to exclude the new data/reports/ and data/temp/ directories.
  Dependencies: Added new project dependencies (thefuzz, requests, beautifulsoup4, tqdm).

## 3.9.0 (2025-08-03)

### Bump

- **version 3.8.0 → 3.9.0**

### Features

- **add docstring linter and enhance header linter**
  This release introduces two new linter scripts to enforce code quality and documentation standards, along with significant enhancements to the project's documentation and data organization.
  
  Features:
  - Enhanced Header Linter (`lint_file_headers.py`): Significantly refactored the header linter to be interactive. It now features a safe, two-stage validation check (core content integrity and post-fix compliance) and a timestamped backup system.
  - New Docstring Linter (`lint_docstrings.py`): Created a new, read-only script using Python's `ast` module to validate docstring presence and length. It supports both high-level and deep scan modes.
  - New Project Scope Report (`generate_scope_report.py`): Created a new script to generate a quantitative report (`project_scope_report.md`) on the scope of all project assets.
  
  Documentation:
  - Updated `CONTRIBUTING.md`: The commit workflow has been updated to include the new header and docstring linting steps.
  
  Refactoring & Bug Fixes:
  - Refactored `list_project_files.py` to remove redundant script-tallying.
  - Refactored `generate_scope_report.py` to use `os.walk` for efficient file discovery.
  - Updated `.gitignore` to correctly exclude generated PDFs and the `docs/images` directory.

## 3.8.0 (2025-08-03)

### Bump

- **version 3.7.1 → 3.8.0**

### Features

- **add data preparation and documentation pipeline**
  Implements the complete data preparation pipeline to automate the
  creation of the final personalities database from the raw Astro-Databank
  export.
  
  Key additions include:
  - `filter_adb_candidates.py`: A new script to perform a multi-stage
    filtering of the raw data down to the final 5,000 subjects.
  - `prepare_sf_import.py`: A new script to format the filtered data
    for import into the Solar Fire software.
  - New data files (`country_codes.csv`, `filter_adb_raw.csv`, etc.) to
    support the new filtering and preparation scripts.
  
  The project documentation has been significantly updated to reflect these
  new processes, including the addition of 7 new diagrams for the data
  preparation phase and a complete refactoring of the diagram naming
  convention for improved clarity and consistency.
  
## 3.7.1 (2025-07-31)

### Bump

- **version 3.7.0 → 3.7.1**

### Fixes

- **Revert release process to original stable state**
  Recent attempts to fix a minor formatting issue in CHANGELOG.md (missing blank line) introduced critical bugs that broke the entire release process.
  
  This commit reverts `scripts/finalize_release.py` and `pyproject.toml` to their original, functional state from v3.7.0.
  
  This restores the reliable release functionality. The minor formatting issue in the changelog will be addressed separately in a future update.
- **Ensure correct changelog formatting via release script**
  The `commitizen` tool was creating poorly formatted changelog entries. Previous attempts to fix this were unsuccessful.
  
#### Previous attempts
  This commit implements a definitive fix by giving the `scripts/finalize_release.py` script exclusive control over writing to the changelog.
  
  1. `pyproject.toml` is updated to remove the `changelog_file` key, preventing `cz bump` from writing to the file directly.
  2. `finalize_release.py` is refactored to:
     - Capture the complete, formatted changelog entry from `cz bump --changelog`.
     - Delete the broken manual changelog generation logic.
     - Prepend the captured entry to CHANGELOG.md with the correct trailing blank line.
- **Ensure correct changelog formatting via release script**
  The `commitizen` tool was creating poorly formatted and sometimes duplicated entries in CHANGELOG.md. Previous attempts to fix this with templates or hooks were unsuccessful.
  
  This commit implements a definitive fix by giving the `scripts/finalize_release.py` script exclusive control over writing to the changelog.
  
  1. `pyproject.toml` is updated to remove the `changelog_file` key, preventing `cz bump` from writing to the file.
  2. `finalize_release.py` is updated to capture the simple changelog output from `cz bump` and combine it with a detailed commit log, creating a single, perfectly formatted entry that it writes to CHANGELOG.md.
- **Add blank line between release entries via changelog hook**
  The default `keep_a_changelog` format in commitizen does not include a blank line between release entries. The previous attempt to fix this with a custom template failed because the `template` key is ignored by this format.
  
  This commit implements a robust fix using a `changelog_hook`.
  1. A new script, `scripts/changelog_hook.py`, is introduced to programmatically prepend the new entry to the changelog with correct spacing.
  2. `pyproject.toml` is updated to use this hook.
  3. The obsolete `cz_templates/` directory has been removed.
- **Add blank line between release entries**
  The default `keep_a_changelog` format in commitizen does not include a blank line between release entries, making the changelog difficult to read.
  
  This fix overrides the default by:
  1. Creating a custom Jinja2 template (`cz_templates/keep_a_changelog_template.j2`) that adds the required trailing newline.
  2. Updating `pyproject.toml` to use this custom template.
  
## 3.7.0 (2025-07-31)

### Bump

- **version 3.6.2 → 3.7.0**

### Features

- **Enhance study-level workflows and align all documentation**
  This commit introduces a major enhancement to the study-level workflows and brings all project documentation into alignment with the current codebase.
  
  Workflow Enhancements:
  - `audit_study.ps1` now performs a robust two-part audit for both readiness and completeness, with a more transparent report.
  - Logging across all PowerShell scripts is now standardized and produces clean, reliable log files that correctly capture Python output.
  - The output parser in `process_study.ps1` has been fixed.
  
  Documentation Overhaul:
  - Updated all workflow and script descriptions in `DOCUMENTATION.template.md` for accuracy and clarity.
  - Improved document structure and removed redundant sections.
  - Updated all relevant workflow and architecture diagrams.
  - Added a "Known Issues and Future Work" section to track the project's roadmap.

## 3.6.2 (2025-07-30)

### Bump

- **version 3.6.1 → 3.6.2**

### Fixes

- **Prevent double confirmation prompt in migrate_study.ps1**
  The `migrate_study.ps1` script correctly prompted for user consent but failed to pass this consent to the `migrate_experiment.ps1` script it called in a loop. This resulted in a redundant confirmation prompt for each experiment in the study.
  
  This fix adds the `-NonInteractive = $true` flag to the call, ensuring that once study-level migration is approved, the individual experiment migrations proceed automatically without further user interaction.

## 3.6.1 (2025-07-30)

### Bump

- **version 3.6.0 → 3.6.1**

### Fixes

- **Correct file copy logic in migrate_experiment.ps1**
  The migrate_experiment.ps1 script was incorrectly copying the entire source directory into the destination, rather than just its contents. This caused a nested directory structure that made experiment_manager.py fail to find the run_* folders, leading it to incorrectly re-run LLM sessions from scratch.
  
  This fix modifies the `Copy-Item` command to use a wildcard path (Join-Path $TargetPath "*"), ensuring only the contents are copied. This resolves the nesting issue and allows the migration workflow to correctly reprocess existing data without unnecessary LLM calls.
  
  This change was validated for both migrate_experiment.ps1 and the batch-wrapper migrate_study.ps1.

## 3.6.0 (2025-07-30)

### Bump

- **version 3.5.0 → 3.6.0**

### Features

- **Implement and standardize study-level management scripts**
  This feature introduces a suite of robust, user-friendly, study-level management scripts and standardizes the UI across the entire framework.
  
  New Functionality:
  - Implemented `repair_study.ps1` to safely audit and automatically fix, update, or finalize all experiments in a study. Includes an interactive "force action" menu for valid studies.
  - Implemented `migrate_study.ps1` to provide a batch workflow for safely upgrading all legacy or corrupted experiments in a study.
  
  UI and Workflow Standardization:
  - The `-TargetDirectory` parameter is now used consistently across all experiment-level and study-level scripts.
  - All user-facing PowerShell scripts now use `Tee-Object` to generate useful, complete log files (e.g., `study_repair_log.txt`), replacing the non-functional `Start-Transcript` method.
  - Standardized all UI messages for colors, wording, relative paths, and banner formatting.
  
  Bug Fixes and Refinements:
  - Added non-interactive and force flags to experiment-level scripts to support the new automated study-level workflows.
  - Fixed numerous bugs caught during testing, including file locking on exit, incorrect prompts, and faulty audit-parsing logic.
  
  Known Issues:
  - The `migrate_study.ps1` and `migrate_experiment.ps1` scripts incorrectly re-run LLM API calls when forcing a migration on an already valid experiment. This is a non-destructive but unintended behavior that will be addressed in a future release.

## 3.5.0 (2025-07-29)

### Bump

- **version 3.4.0 → 3.5.0**

### Features

- **introduce study-level scripts and refactor LLM concurrency**
  - Refactors LLM session execution for true concurrency by deleting the redundant run_llm_sessions.py and moving its logic into a ThreadPoolExecutor in orchestrate_replication.py.
  
  - Introduces new study-level PowerShell scripts (repair_study.ps1, migrate_study.ps1) for robust batch operations (yet untested) and deprecates the old update_study.ps1.
  
  - Overhauls audit_study.ps1 to provide a clearer, more reliable summary report by correctly calling the experiment-level audit for each sub-directory.
  
  - Fixes critical classification bugs in the experiment_manager.py audit logic to correctly distinguish between states requiring repair, update, or migration.
  
  - Updates all documentation, diagrams, and workflow descriptions to reflect the new scripts and simplified 5-stage pipeline.

## 3.4.0 (2025-07-29)

### Bump

- **version 3.3.2 → 3.4.0**

### Features

- **overhaul migration workflow and standardize audit engine**
  This major update started as a refinement of the `migrate_experiment.ps1` script and evolved into a comprehensive overhaul of the project's core diagnostic engine and the user experience across all experiment-level workflows.
  
  ### 1. `migrate_experiment.ps1` Overhaul:
  The script's user interaction, error handling, and diagnostic integration have been completely revamped.
  - **Improved Clarity:** All user prompts and messages were rewritten to be more intuitive, providing clear recommendations and explaining the non-destructive copy-then-upgrade process.
  - **Robustness:** Added handling for previously uncaught audit statuses (e.g., `AUDIT_NEEDS_AGGREGATION`), preventing crashes.
  - **UI Polish:** Fixed numerous UI bugs related to prompt formatting, message coloring, and header consistency.
  - **Internal Consistency:** Standardized the `-TargetDirectory` parameter across the script and all documentation, and clarified internal terminology (e.g., "Transforming" -> "Upgrading").
  
  ### 2. New Diagnostic Engine:
  The deep dive into migration failures led to a new, simpler, and more robust system-wide audit rule:
  - A run with a **single error** is considered repairable.
  - A run with **two or more errors** is flagged as `RUN_CORRUPTED`, correctly triggering a migration recommendation for safety.
  
  ### 3. Workflow Standardization & Enhancements:
  - All action-oriented scripts (`new`, `repair`, `migrate`) now conclude with a consistent, final verification audit.
  - Standardized UI elements (PDM detection, headers) across all scripts.
  - The "Total Valid LLM Responses" audit statistic is now color-coded based on performance thresholds (Green >= 80%, Yellow >= 50%, Red < 50%).
  
  ### 4. Documentation Overhaul:
  - All relevant documentation (`DOCUMENTATION.md`, script docstrings, diagrams) has been updated to reflect the new diagnostic logic and improved workflows.

## 3.3.2 (2025-07-28)

### Bump

- **version 3.3.1 → 3.3.2**

### Fixes

- **refine migration workflow and audit report UI**
  This commit resolves several UI inconsistencies and improves the user experience for the migration and audit workflows.
  
  Key changes include:
  - Standardized `migrate_experiment.ps1` to consistently use the `-TargetDirectory` parameter, aligning the code with its documentation.
  - Reworded user prompts in `migrate_experiment.ps1` to provide clearer recommendations when an experiment needs repair or reprocessing.
  - Corrected message coloring for prompts and the "aborted by user" notice to improve readability.
  - Added color-coding to the "Overall Summary" statistics in audit reports for immediate visual feedback on experiment completeness.

## 3.3.1 (2025-07-28)

### Bump

- **version 3.3.0 → 3.3.1**

### Documentation

- **update contribution and release guidelines**
  Aligns CONTRIBUTING.md with the automated pdm run release script and clarifies dependency installation instructions.

### Fixes

- **harden powershell wrappers and improve messaging**
  - Hardens PowerShell wrappers (audit, migrate) by trimming and validating the -TargetDirectory path to prevent crashes from whitespace or invalid paths.
  - Fixes argument passing to the Python backend in migrate_experiment.ps1.
  - Resolves an unhandled state bug in experiment_manager.py that caused migration to fail during finalization.
  - Refines user-facing prompts and removes redundant banners for a cleaner UX.
  - Corrects a Mermaid diagram parsing error.

## 3.3.0 (2025-07-28)

### Bump

- **version 3.2.0 → 3.3.0**

### Features

- **standardize audit banners and streamline repair workflow**
  Introduces a more intelligent and user-friendly repair workflow with consistent, clear console output.
  
  Key changes:
  - Adds a new AUDIT_NEEDS_AGGREGATION state to experiment_manager.py. This allows repair_experiment.ps1 to perform a fast re-aggregation for experiment-level corruption instead of unnecessarily reprocessing all replications.
  - Standardizes all audit results (success, failure, and update) into a consistent 4-line banner format for improved readability.
  - The audit banner's "Recommendation" line is now automatically suppressed during non-interactive repair flows, providing cleaner output.
  - The final success message for all repair actions is now the standardized "PASSED" banner, ensuring a consistent user experience.

## 3.2.0 (2025-07-28)

### Bump

- **version 3.1.0 → 3.2.0**

### Features

- **Introduce new Create/Check/Fix user interface**
  This commit overhauls the user workflow to be more intuitive and robust by adopting a "Create -> Check -> Fix" model. It deprecates the confusing `run_experiment.ps1` and `update_experiment.ps1` scripts in favor of a single, intelligent `repair_experiment.ps1` tool.
  
  Key Changes:
  - New `repair_experiment.ps1`: A unified "fix-it" script for all existing experiments. It automatically detects and fixes issues (e.g., missing data, outdated analysis) and provides an interactive prompt to force actions on already valid experiments.
  - Deprecations: `run_experiment.ps1` and `update_experiment.ps1` are now removed.
  - Smarter Backend (`experiment_manager.py`):
    - Implemented non-destructive config file repair.
    - Streamlined the main state-machine loop to eliminate redundant audit reports for a cleaner UI.
  - Bug Fixes:
    - Corrected an issue in `restore_config.py` that wrote numbers with incorrect zero-padding.
    - Removed the creation of unnecessary `.bak` files from `replication_log_manager.py`.
  - Documentation Overhaul:
    - Updated `DOCUMENTATION.template.md`, `CONTRIBUTING.md`, and all relevant diagrams to reflect the new workflow.
    - Updated script docstrings.
    - Added `cover_letter.md` to the DOCX build process in `build_docs.py`.
    - Renamed `study_supplement.md` to `study_supplements.md` for clarity.

## 3.1.0 (2025-07-27)

### Bump

- **version 3.0.3 → 3.1.0**

### Features

- **introduce new_experiment.ps1 and refactor manager**
  This commit introduces a clearer, user-intent-driven workflow for experiment creation and significantly refactors the main controller for improved clarity and maintainability.
  
  New Feature:
  - Adds `new_experiment.ps1`, a dedicated script for creating new experiments from the global `config.ini`. This separates the "create" action from the "repair/resume" action, which remains with `run_experiment.ps1`.
  
  Refactoring:
  - The monolithic `main()` function in `experiment_manager.py` has been broken down into three logical, private helper functions:
    - `_setup_environment_and_paths()`
    - `_handle_experiment_state()`
    - `_run_finalization()`
  - This refactoring makes the main execution flow a clean three-step process (setup, loop, finalize).
  - All global color variables have been eliminated. Color information is now passed explicitly via a `colors` dictionary, making dependencies clear.
  
  Improvements:
  - Console output for new experiments is cleaner, with consistent banners, colors, and spacing for a more readable user experience.
  - All documentation, diagrams, and help text have been updated to reflect the new workflow.
  
  Fixed:
  - Corrected a bug in the timestamp formatting (`%Ym%d` -> `%Y%m%d`) that caused incorrect directory naming for new experiments.

## 3.0.3 (2025-07-26)

### Bump

- **version 3.0.2 → 3.0.3**

### Fixes

- **resolve critical audit bug and standardize UI**
  This commit resolves a critical bug in the audit logic and standardizes the user interface across all PowerShell scripts for a consistent user experience.
  
  -   **Audit Logic:** Fixed a major bug in `experiment_manager.py` that caused it to incorrectly validate experiments with missing report files, especially within a study context. The audit now correctly identifies all file-level issues.
  
  -   **UI Standardization:**
      -   Standardized all user-facing banners in `audit_study.ps1`, `update_study.ps1`, and `process_study.ps1` to a consistent 80-column format.
      -   Centralized banner printing for single-experiment audits into `experiment_manager.py`, simplifying `audit_experiment.ps1` into a pure launcher.
      -   Improved layout and color-coding in `process_study.ps1` for clearer step-by-step progress.
  
  -   **Parameter Consistency:** Standardized the main directory parameter to `-TargetDirectory` across all study-level scripts and their documentation.

## 3.0.2 (2025-07-26)

### Bump

- **version 3.0.1 → 3.0.2**

### Refactor

- **organize utility scripts into a dedicated scripts/ directory**
  This commit improves the project structure by separating core application logic from developer utility scripts.
  
  -   Creates a new top-level `scripts/` directory.
  -   Moves project maintenance scripts (e.g., `build_docs`, `lint_file_headers`, `finalize_release`) from `src/` to `scripts/`.
  -   Deletes obsolete scripts (`rebuild_reports.py`, `verify_experiment_completeness.py`) and their corresponding tests to reduce clutter.
  -   Updates `pyproject.toml` to reflect the new script paths for PDM commands.
  
  This change enhances clarity by enforcing a clean separation of concerns, making the codebase easier to navigate.

## 3.0.1 (2025-07-26)

### Bump

- **version 3.0.0 → 3.0.1**

### Fixes

- **resolve bugs in migration and repair workflows**
  This series of fixes addresses several critical bugs discovered during the validation of the experiment management workflows.
  
  -   **Migration:** The config restoration script (`restore_config.py`) now correctly parses `k` (group_size) and `m` (num_trials) from the run directory name itself, making it robust against report formatting changes and fixing a critical `CONFIG_MISMATCH` failure.
  
  -   **Repair/Update:** Corrected argument passing in `experiment_manager.py` for repair and reprocess modes, resolving `NameError` exceptions.
  
  -   **Diagnostics:** The audit recommendation messages are now context-aware, providing clearer instructions when run as a standalone tool.
  
  -   **Logging:** Redirected `tqdm` progress bars in `orchestrate_replication.py` to stdout to prevent them from being logged as errors during repair operations.

### Style

- **enforce standard script header and footer format**
## 3.0.0 (2025-07-26)

### Bump

- **version 2.14.0 → 3.0.0**

### Features

- **add header linter and refactor compilation workflow**
  - Refactored the results pipeline into dedicated compiler scripts (compile_replication_results.py, compile_experiment_results.py, compile_study_results.py) for improved modularity.
  - Created a new linter script (lint_file_headers.py) to programmatically enforce a standard header/footer format across all project scripts.
  - Renamed the study workflow entry point to process_study.ps1 to more accurately reflect its audit-compile-analyze function.
  - Fixed critical bugs, including the missing base query in reports and several Mermaid diagram rendering errors.
  - Updated all documentation, diagrams, and docstrings to align with the new architecture.
  
  BREAKING CHANGE: The user entry point 'analyze_study.ps1' has been renamed to 'process_study.ps1'. Any scripts or user workflows that called the old script by name will need to be updated.

## 2.14.0 (2025-07-26)

### Bump

- **version 2.13.0 → 2.14.0**

### Features

- **overhaul pipeline, clean data, and expand documentation**
  - Refactored the results pipeline to use dedicated compiler scripts for each stage (replication, experiment), improving modularity.
  - Cleaned up the data/ directory, removing numerous obsolete database and sample files to rely on a single source.
  - Fixed a critical bug preventing the base LLM query from appearing in the final replication report.
  - Improved formatting and terminology in the replication report for better readability and consistency.
  - Added new documentation, including a data README, study supplement, and cover letter.
  - Expanded testing with a new Bayesian analysis test.
  - Reorganized historical data into a new pilot_studies/ directory.

## 2.13.0 (2025-07-24)

### Bump

- **version 2.12.0 → 2.13.0**

### Features

- **automate release process and simplify commit workflow**
  This commit introduces a fully automated release process and simplifies the
  commit workflow, significantly improving developer experience and reducing
  the potential for manual error.
  
  Key Changes:
  -   **Automated Release (`pdm run release`)**:
      -   Introduced `src/finalize_release.py`, a new script that
          orchestrates the entire release process.
      -   The script programmatically determines the next version, runs `cz bump`,
          generates a detailed changelog with full commit bodies, amends the
          release commit, and correctly moves the Git tag.
      -   This replaces a multi-step, error-prone manual process with a single,
          non-interactive command.
  
  -   **Simplified Commits (`pdm run commit`)**:
      -   Introduced a new `pdm run commit` shortcut that uses `cz commit` for an
          interactive, guided commit experience.
      -   This makes the manual creation of `commit.txt` obsolete.
  
  -   **Updated Documentation**:
      -   Overhauled the "Commit Your Changes" and "Releasing a New Version"
          sections in `CONTRIBUTING.md` to reflect the new, simpler two-step
          (`commit` -> `release`) process.
  
  -   **Cleanup**:
      -   Removed temporary refactoring scripts (`rename_diagrams.ps1`,
        `update_doc_references.ps1`) that are no longer needed.This commit introduces a fully automated release process and simplifies the
  commit workflow, significantly improving developer experience and reducing
  the potential for manual error.
  
  Key Changes:
  -   **Automated Release (`pdm run release`)**:
      -   Introduced `src/finalize_release.py`, a new script that
          orchestrates the entire release process.
      -   The script programmatically determines the next version, runs `cz bump`,
          generates a detailed changelog with full commit bodies, amends the
          release commit, and correctly moves the Git tag.
      -   This replaces a multi-step, error-prone manual process with a single,
          non-interactive command.
  
  -   **Simplified Commits (`pdm run commit`)**:
      -   Introduced a new `pdm run commit` shortcut that uses `cz commit` for an
          interactive, guided commit experience.
      -   This makes the manual creation of `commit.txt` obsolete.
  
  -   **Updated Documentation**:
      -   Overhauled the "Commit Your Changes" and "Releasing a New Version"
          sections in `CONTRIBUTING.md` to reflect the new, simpler two-step
          (`commit` -> `release`) process.
  
  -   **Cleanup**:
      -   Removed temporary refactoring scripts (`rename_diagrams.ps1`,
        `update_doc_references.ps1`) that are no longer needed.
All notable changes to the Personality Matching Experiment Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v2.12.0 (2025-07-24)

### Feat

- **analysis, core**: enhance analysis workflow and standardize filenames

This commit introduces a major enhancement to the statistical analysis
pipeline and standardizes core script and documentation filenames for
improved consistency and maintainability.

Analysis Enhancements (`study_analyzer.py`):
- Upgraded the statistical model from a Two-Way ANOVA to a full Factorial
  ANOVA, enabling the analysis of interaction effects between experimental
  factors.
- Enhanced the plotting workflow to automatically copy generated boxplots
  to the central `docs/images/` directory, making them immediately
  available for inclusion in project documentation via `build_docs.py`.

Filename Standardization & Refactoring:
- **Core Scripts:** Renamed `src/experiment_aggregator.py` to
  `src/aggregate_experiments.py` and `src/study_analysis.py` to
  `src/study_analyzer.py` for clarity. All call-sites and test files
  have been updated accordingly.
- **Documentation Diagrams:** Renamed all diagram source files in `docs/diagrams`
  to a consistent `view_*`, `flow_*`, `logic_*`, `format_*` convention.
  All references within `DOCUMENTATION.template.md` have been updated.
- **Utility Script:** Updated `convert_py_to_txt.py` to place its
  output in `output/project_code_as_text`, aligning with the project's
  standard of keeping generated artifacts in the `output/` directory.

Documentation & Repository Maintenance:
- Added `docs/study_article.md` as a source for the main research paper.
- Updated `.gitignore` to correctly handle new generated files and build
  artifacts.

## v2.10.0 (2025-07-21)

### Feat

- **analysis-pipeline**: consolidate analysis stage for clarity

This refactoring addresses user feedback that the analysis pipeline felt fragmented by unifying the core performance analysis and diagnostic bias analysis into a single, user-facing stage named "Analyze LLM Performance".

Key changes include:
- `orchestrate_replication.py` now manages a 6-stage pipeline, calling both `analyze_llm_performance.py` and `run_bias_analysis.py` under a single header.
- `experiment_manager.py` has been updated to delegate all analysis responsibilities to the orchestrator, ensuring consistent behavior across all modes (new, reprocess, repair).
- All relevant documentation, including script descriptions, docstrings, and architectural diagrams (`codebase_architecture`, `workflow_1_run_experiment`, `data_flow`), has been updated to reflect the new, streamlined structure.

This approach preserves the modularity and single-responsibility principle of the underlying scripts while providing a more intuitive and coherent user experience.

## v2.9.1 (2025-07-21)

### Fix

- **workflows**: Resolve critical bugs and refine contribution process

This commit addresses a series of cascading bugs in the PowerShell audit and update workflows and refines the contribution guidelines for clarity and correctness.

- The `audit_study.ps1` script no longer truncates long experiment names in its summary table. This was the root cause of the `TargetDirectory` validation error in `update_study.ps1`.
- The `update_study.ps1` script now uses a more robust method to parse the audit report, making it resilient to formatting variations.
- The audit summary in `experiment_manager.py` now uses contextual coloring and messaging to provide a clearer user experience during intermediate states like "pending finalization".
- Fixed an `UnboundLocalError` that would crash post-update audits by reordering the logic in the `_run_verify_only_mode` function.
- The `CONTRIBUTING.md` document was significantly updated to clarify and correct the standard commit and release workflows, including the use of `commit.txt` and the proper sequence for staging changes.

## v2.9.0 (2025-07-20)

### Feat

- Implement lift metrics and comprehensive audit workflows

This commit introduces new "lift" metrics to analyze LLM performance relative to chance.
It also significantly refactors and enhances the audit and update PowerShell workflows
to ensure data integrity and consistency across the entire study.

Key changes include:
- New `mean_mrr_lift`, `mean_top_1_acc_lift`, `mean_top_3_acc_lift` calculated in `analyze_llm_performance.py`.
- `experiment_aggregator.py` updated to correctly handle new metrics and flatten bias data.
- `experiment_manager.py` audit logic refined to enforce all required metrics and exit with true status codes.
- New `update_study.ps1` script for batch updates across studies.
- `audit_study.ps1` and `analyze_study.ps1` adjusted for robust inter-script communication.
- Documentation and diagrams (`DOCUMENTATION.template.md`, `.mmd` files) updated to reflect all changes.

## v2.8.1 (2025-07-20)

### Fix

- **audit**: ensure robust pre-analysis validation

This commit resolves several critical bugs in the audit and analysis
workflows to ensure data integrity before statistical analysis.

- `analyze_study.ps1` now performs a mandatory pre-analysis audit
  and will halt if the study is not fully validated.
- `audit_study.ps1` now correctly returns a non-zero exit code on
  failure and uses a more robust parsing logic to provide a
  consistent and accurate summary report.
- `experiment_manager.py` was fixed to return the correct, non-zero
  exit codes for all non-validated states (e.g., MIGRATION), ensuring
  programmatic checks are reliable.
- Log file timestamps in both audit scripts are now consistently
  formatted to be human-readable.
- All relevant documentation, docstrings, and diagrams have been
  updated to reflect the new pre-analysis audit workflow.

## v2.8.0 (2025-07-20)

### Feat

- **audit-study**: introduce study-level audit and enhance output

This commit introduces a new `audit_study.ps1` script, providing a
comprehensive, consolidated audit report across multiple experiments
within a study directory.

Key improvements include:
- New `audit_study.ps1` entry point for study-level verification.
- All console banners are now consistently capitalized and centered.
- Real-time audit progress is displayed in a clear, tabular format.
- The final summary report table has improved spacing and uses "Details"
  as the third column header.
- All console output is now captured and saved to a `study_audit_log.txt`
  file.
- Updated `pyproject.toml` to include `pdm run aud-stu` shortcut.
- Added new `architecture_workflow_6_audit_study.mmd` diagram.
- Updated `DOCUMENTATION.template.md` to describe the new workflow and its
  diagram.
- Updated codebase architecture diagram to include the new entry point.

### Fix

- **docs**: add robust page break support for DOCX
  Added `python-docx` dependency for DOCX post-processing.
  Created `docx_postprocessor.py` to reliably insert page breaks.
  Updated `build_docs.py` to call the post-processor, solving
  Pandoc rendering issues.

- **workflow**: remove unnecessary user prompt in new experiments
  Modified `experiment_manager.py` to remove the user prompt that was
  halting the process before the final aggregation for new experiments.
  This allows for a fully non-interactive completion of new runs.

- **reports**: restore correct replication report format
  Corrected an issue where the `replication_report.txt` format was
  corrupted during a previous script update.

### Refactor

- clean up project files
  Deleted the obsolete `RESTORE_PRODUCTION.ps1` script.

## v2.7.0 (2025-07-19)

### Feat

- **audit-study**: introduce study-level audit and enhance output

    This commit introduces a new `audit_study.ps1` script, providing a
    comprehensive, consolidated audit report across multiple experiments
    within a study directory.

    Key improvements include:
    - New `audit_study.ps1` entry point for study-level verification.
    - All console banners are now consistently capitalized and centered.
    - Real-time audit progress is displayed in a clear, tabular format (Progress, Experiment, Result).
    - The final summary report table has improved spacing and uses "Details" as the third column header.
    - All console output is now captured and saved to a `study_audit_log.txt` file.
    - Log file timestamps are formatted for human readability post-processing.
    - Standardized, two-line messages are used when the transcript stops.
    - Fixed critical runtime errors related to table formatting and transcript handling.
    - Updated `pyproject.toml` to include `pdm run aud-stu` shortcut.
    - Added new `architecture_workflow_6_audit_study.mmd` diagram.
    - Updated `DOCUMENTATION.template.md` to describe the new workflow and its diagram.
    - Updated `codebase_architecture.mmd` to include the new entry point.

## v2.6.0 (2025-07-19)

### Feat

- **framework**: overhaul workflows and improve UX

This commit refactors the core migration workflow to be fully robust and operational. It also introduces significant user experience improvements across all interactive scripts and documentation.

Key changes include:
- Corrected silent failures in the patching process by improving error propagation from worker scripts.
- Fixed parsing logic in `restore_config.py` to handle various legacy report formats and correctly select the latest report file.
- Resolved an infinite loop in the state machine by ensuring the reprocess mode performs a full finalization.
- Standardized all console headers and prompts for clarity and consistency.
- Made user prompts robust by looping until valid input is received.
- Improved and clarified all workflow diagrams (Run, Audit, Update, Migrate) to be more accurate and compact.
- Added a new decision-tree diagram to the documentation to help users choose the correct workflow.
- Ensured `run_experiment.ps1` always displays an audit report for existing experiments, improving consistency.
- Streamlined output by removing redundant final audit steps from the migration script.
- Updated all relevant script docstrings to reflect the new logic.

## v2.5.0 (2025-07-18)

### Feat

- **docs**: Finalize diagram grouping and reference doc inclusion

    This commit introduces the completed solution for grouping diagrams
    with their captions in the generated DOCX, ensuring they stay on a single page.

    Key changes include:
    - Implemented grouped_figure placeholder processing in build_docs.py.
    - Updated documentation template to use grouped_figure.
    - Added custom_reference.docx to Git for consistent styling and pagination.
    - Ensured render_all_diagrams processes embedded diagrams.

## v2.4.3 (2025-07-18)

### Perf

- **pipeline**: parallelize LLM sessions for new runs

This commit introduces parallel execution for the LLM session stage (Stage 2) for all new replication runs, significantly speeding up data collection.

- The parallel worker logic, previously only used for repairs in the experiment manager, has been centralized within `orchestrate_replication.py`.
- This new parallel execution is controlled by the `max_parallel_sessions` parameter in `config.ini`.
- The obsolete `--max-workers` command-line argument has been removed from `experiment_manager.py`.
- All relevant documentation, including README.md, workflow diagrams, and configuration details, has been updated to reflect these changes.

## v2.4.2 (2025-07-18)

### Fix

- **pipeline**: restore correct replication pipeline sequence

    This fix corrects a regression introduced during a previous refactoring. The `orchestrate_replication.py` script was calling `experiment_aggregator.py` before the necessary `replication_report.txt` was generated, causing the aggregation to fail silently.

    This resulted in incomplete replication runs that required an immediate and unnecessary `UPDATE` cycle to fix.

    The correct sequence is now restored within the orchestrator:
    1.  Core analysis stages (1-5) are run to produce `replication_metrics.json`.
    2.  A new Stage 6 generates the `replication_report.txt` from the finalized metrics.
    3.  A new Stage 7 calls `experiment_aggregator.py`, which can now successfully parse the report to create `REPLICATION_results.csv`.

    This ensures each replication is atomically complete and valid upon creation.

## v2.4.1 (2025-07-18)

### Fix

- **resilience**: implement atomic replications and parallel new runs

This commit resolves all known bugs related to experiment resilience,
state handling, and race conditions, resulting in a significantly more
robust and correct pipeline.

- **Atomic Replications**: `orchestrate_replication.py` is now fully atomic.
  It manages a 6-stage pipeline, including a "Finalize Replication"
  stage that generates the `REPLICATION_results.csv` file. This ensures
  that any replication completing the orchestrator is 100% `VALIDATED`,
  eliminating the need for a final reprocessing step after new runs.

- **Corrected State Priority**: Fixed the state-detection logic in
  `experiment_manager.py` to prioritize `REPAIR` over `NEW`. This
  ensures that existing, interrupted runs are always fixed before new
  ones are created, correcting a critical flaw in the resume logic.

- **Resolved Parallel Repair Race Conditions**:
  - Fixed a race condition where parallel repair workers conflicted
    over a shared temp directory by creating unique, process-ID-based
    temp directories in `run_llm_sessions.py`.
  - Fixed a race condition where parallel workers for the same replication
    attempted to delete the same report file. The `REPAIR` mode now
    decouples parallel session fetching from serial reprocessing.

- **Fixed Full Repair Deadlock**: Resolved a file-locking issue on Windows
  that caused the `FULL REPLICATION REPAIR` mode to hang, by ensuring
  file handles are properly closed during the audit phase.

- **Enhanced Progress Spinner**: The live spinner in `llm_prompter.py` now
  displays comprehensive progress for the entire replication, including the
  current trial number, total trials, elapsed time, and ETR.

- **Documentation Overhaul**: Updated all relevant docstrings, `DOCUMENTATION.md`,
  and architecture diagrams (`workflow_1`, `codebase_architecture`) to
  accurately reflect the new 6-stage atomic replication pipeline.

## v2.4.0 (2025-07-17)

### Feat

- **resilience**: enhance repair logic and progress feedback

This commit introduces significant improvements to the framework's
resilience, error handling, and user feedback during long-running
experiments.

- **Enhanced Spinner**: The live spinner in `llm_prompter.py` now displays
  comprehensive progress for the entire replication, including the
  current trial number, total trials, elapsed time, and estimated time
  remaining, in addition to the timer for the individual API call.

- **Fixed State-Detection Priority**: Corrected the state-detection logic
  in `experiment_manager.py` to prioritize `REPAIR` over `NEW`. This
  ensures that any existing, interrupted replication runs are fully
  repaired before the manager attempts to create new ones, fixing a
  critical flaw in the resume logic.

- **Resolved Parallel Repair Race Conditions**:
  - Fixed a race condition where parallel repair workers would conflict
    over a shared temporary directory. `run_llm_sessions.py` now creates
    a unique, process-ID-based temporary directory for each instance.
  - Fixed a second race condition where parallel workers for the same
    replication run would attempt to delete the same report file. The
    repair logic in `experiment_manager.py` now correctly decouples the
    parallel LLM session fetching from a subsequent, serial reprocessing
    step for each uniquely affected replication.

## v2.3.2 (2025-07-17)

### Refactor

- **output**: improve console readability and state handling

This commit introduces several user experience improvements and refines
the experiment manager's state handling:

- **Enhanced `NEW_NEEDED` state handling**: The `experiment_manager.py` now
  prioritizes the `NEW_NEEDED` state, allowing it to directly initiate
  new experiment runs without an initial, potentially misleading, audit
  report when the target directory is empty. This prevents premature abortion
  of new experiments.

- **Improved progress reporting**: The `experiment_manager.py` now provides
  a "Time Remaining" metric alongside "Time Elapsed" and "ETA" during new
  replication runs, offering more granular progress insight.

- **Standardized stage names**: Updated the stage names printed by
  `orchestrate_replication.py` to "Build LLM Queries" and "Analyze LLM Performance"
  for consistency with script names and improved clarity.

- **Refined console output formatting**: Implemented consistent newline
  and indentation formatting for file and directory paths across
  `migrate_experiment.ps1`, `analyze_study.ps1`, `src/experiment_manager.py`,
  `src/experiment_aggregator.py`, `src/replication_log_manager.py`,
  `src/patch_old_experiment.py`, and `src/restore_config.py`. This significantly
  enhances the readability of console logs.

- **Documentation updates**: Reflected all new features and output
  enhancements in `CONTRIBUTING.md` and `docs/DOCUMENTATION.template.md`.

## v2.3.1 (2025-07-17)

### Fix

- **migration**: enhance robustness and user feedback

This commit addresses several issues to improve the reliability and clarity
of the experiment migration workflow:

- **Fix `rebuild_reports.py` argument parsing**: `rebuild_reports.py` now correctly
  accepts `--reprocess`, `--run_output_dir`, and `--quiet` arguments,
  resolving the `unrecognized arguments` error during migration's re-processing step.
  This allows `experiment_manager.py` to use `rebuild_reports.py` as a single-run
  worker for individual replication report regeneration.

- **Fix `experiment_manager.py` full replication repair**: Corrected a `NameError`
  in `_run_full_replication_repair` where the `run_dir` variable was not
  re-defined after deleting and recreating a run directory. The fix ensures
  the newly created directory's path is correctly identified for subsequent
  bias analysis and logging.

- **Improve `tqdm` progress bar width**: Adjusted `tqdm` calls in `experiment_manager.py`
  to set a fixed column width (80 characters) for progress bars, ensuring consistent
  and readable output in various terminal environments.

- **Add post-migration audit in `migrate_experiment.ps1`**: Introduced a final
  `--verify-only` audit step at the end of the `migrate_experiment.ps1` script.
  This provides explicit, automated confirmation to the user that the entire
  migration and self-healing process has completed successfully, showing the
  "VALIDATED" status for all runs and the "COMPLETE" experiment aggregation status.

## v2.3.0 (2025-07-17)

### Feat

- **parser**: Enhance response parsing for verbose LLMs

    This commit introduces a more robust LLM response parser and improves the experiment update workflow.

    - The response parser in `process_llm_responses.py` now includes a fallback mechanism. If a markdown code block is not found, it attempts to parse the last k+1 lines of the response. This significantly improves the valid response rate for verbose, "thinking" LLMs.

    - The update workflow (`update_experiment.ps1` and `experiment_manager.py`) is now more intelligent. It prompts for confirmation before reprocessing an already `VALIDATED` experiment and automatically runs a post-update audit to verify success.

    - Refactored the project structure by moving `CONTRIBUTING.md`, `CHANGELOG.md`, and `LICENSE.md` to the root directory to align with open-source conventions.

    - Updated all relevant documentation, diagrams, and build scripts to reflect these enhancements.

## v2.2.1 (2025-07-17)

### Fix

- **migration**: handle experiments with zero valid responses

    The migration process would enter an infinite loop when run on experiments where all LLM responses were refusals. This was caused by downstream analysis scripts crashing when they encountered empty data files.

    This commit resolves the issue by making the pipeline resilient to a total data failure:
    - `process_llm_responses.py` now always creates empty `all_scores.txt` and `all_mappings.txt` files if no valid responses are found.
    - `analyze_llm_performance.py` and `run_bias_analysis.py` now handle these empty files gracefully by writing "null" metrics to the report instead of crashing.

    This allows the audit to pass and the migration to complete successfully. The documentation and docstrings for the migration workflow have also been updated to reflect the new, more robust process.

## v2.2.0 (2025-07-17)

### Feat

- **framework**: enhance experiment management and self-healing workflows

    This commit introduces significant improvements to the experiment management
    and data handling processes, enhancing robustness and user experience.

    - **`src/experiment_manager.py`:**
      - **Robust State Machine:** Refined primary loop to ensure correct
        state re-evaluation after actions (repair, update) to break infinite loops.
        Now uses `_get_experiment_state` to accurately determine next action.
      - **Intelligent Repair Handling:** Distinguishes between session-level
        (`RESPONSE_ISSUE`) and full replication (`QUERY_ISSUE`, `CONFIG_ISSUE`) repairs.
      - **Full Replication Regeneration:** `_run_full_replication_repair` now
        deletes severely corrupted runs and regenerates them from scratch.
      - **Interactive Prompts:** Presents clear findings and prompts user
        confirmation for `REPAIR` and `UPDATE` actions.
      - **Automated Update during Migration:** Automatically proceeds with `UPDATE`
        (reprocessing) during the `MIGRATE` workflow after initial confirmation.
      - **Improved Logging:** Ensures subprocess output is streamed directly or captured
        based on `quiet` mode, fixing spinner display issues and providing better logs.

    - **`src/rebuild_reports.py`:**
      - **Diagnostic Mode:** Temporarily simplified to focus on raw subprocess
        output and basic logging, aiding in diagnosing underlying analysis failures.
      - **Explicit `k` value passing:** Ensures analysis scripts receive the correct `k`
        from `config.ini.archived`, addressing "Could not deduce k > 0" errors.

    - **`migrate_experiment.ps1`:**
      - **Clearer Audit Phase:** Removed misleading "Step 0/2" and provides a clean
        summary from `experiment_manager.py`'s audit.
      - **Consistent Terminology:** Renamed "Migrating New Experiment Copy" to
        "Transforming New Experiment Copy" (Step 2/2) for clarity and consistency
        with documentation.
      - **Streamlined User Interaction:** Consolidates audit output and action prompt,
        removing unnecessary intermediate prompts.

    - **`audit_experiment.ps1`:**
      - **Robust Exit Code Handling:** Correctly interprets `experiment_manager.py`'s
        exit codes to provide accurate final audit summaries (VALIDATED, NEEDS UPDATE, etc.).
      - **Standardized Banners:** Ensures consistent visual formatting.

    - **General:**
      - Standardized terminology across scripts for 'audit', 'update', and 'transform'.
      - Enhanced error propagation to halt on specific internal subprocess failures
        (e.g., "--- FAILED ---", "Missing scores/mappings").

    This set of changes addresses previous infinite loop issues and significantly
    improves the framework's overall resilience and user guidance.

## v2.1.0 (2025-07-16)

### Feat

- **workflow,manager**: enhance update workflow with pre-check audit and robust error handling

    This commit introduces a significant overhaul to the 'update experiment' workflow and the underlying experiment manager's audit and state detection capabilities.

    Key changes include:
    -   **Pre-update Audit**: The `update_experiment.ps1` wrapper now performs an initial `--verify-only` audit using `experiment_manager.py`. It explicitly checks the experiment's readiness before proceeding with reprocessing, preventing attempts to update malformed, legacy, or incomplete experiments.
    -   **Granular Audit Exit Codes**: `experiment_manager.py`'s audit mode now returns specific exit codes:
        -   `AUDIT_ALL_VALID (0)`: Experiment is complete and up-to-date.
        -   `AUDIT_NEEDS_REPROCESS (1)`: Experiment has minor analysis issues and is ready for reprocessing.
        -   `AUDIT_NEEDS_REPAIR (2)`: Critical data (queries/responses) is missing, requiring repair via `run_experiment.ps1`.
        -   `AUDIT_NEEDS_MIGRATION (3)`: Experiment is malformed or legacy, requiring `migrate_experiment.ps1`.
    -   **Improved State Detection**: The internal `_get_experiment_state` logic in `experiment_manager.py` is refined to correctly identify various states (NEW, REPAIR, REPR

## v2.0.6 (2025-07-16)

### Fix

- **audit**: complete audit logic and improve report readability

    This commit finalizes the experiment audit functionality, making it
    fully comprehensive and visually readable.

    Key changes include:
    - Added new checks to verify the presence and completeness of
      experiment-level (`EXPERIMENT_results.csv`) and replication-level
      (`REPLICATION_results.csv`) summary files.
    - Corrected the audit summary to use the definitive `n_valid_responses`
      from replication reports, ensuring an accurate total.
    - Improved the visual layout of the console audit report by truncating
      long directory names for better alignment.

## v2.0.5 (2025-07-16)

### Fix

- **audit**: finalize audit logic for all file types and outputs

    This commit resolves all remaining issues with the experiment audit
    function, making it fully robust for both new and migrated data.

    Key changes include:
    - The `FILE_MANIFEST` was updated with the correct file patterns for
      `mappings.txt` and the trial-level `llm_query_*_manifest.txt` files,
      resolving incorrect failure reports.
    - The audit logic for optional trial manifests is now conditional,
      ensuring legacy runs without these files are correctly validated.
    - The `audit_experiment.ps1` wrapper script has been enhanced to
      simultaneously display colored output in the console while saving a

## v2.0.4 (2025-07-16)

### Fix

- **audit**: resolve all verification failures for legacy and new data

    This commit addresses a series of cascading bugs in the experiment
    auditor (`--verify-only` mode) that caused incorrect failure reports.

    Key fixes include:
    - Corrected the file search logic to use full sub-directory paths,
      resolving `SESSION_QUERIES_MISSING` errors.
    - Enforced the use of precise regular expressions for counting trial
      files, preventing `SESSION_QUERIES_TOO_MANY` errors from extra
      non-trial files in the directory.
    - Refactored the analysis file validation to use the definitive
      `n_valid_responses` metric from the `replication_report.txt` JSON as

## v2.0.3 (2025-07-16)

### Refactor

- **audit**: harden and isolate config validation logic

    This commit refactors the configuration verification logic within the
    experiment_manager.py audit/verify mode.

    The validation logic now uses a self-contained, hardcoded compatibility
    map within the script's FILE_MANIFEST. This intentional design choice
    insulates the audit function from any changes to the live, project-level
    config.ini, ensuring that historical experiments can be reliably and
    reproducibly validated over time without external dependencies.

    This change resolves issues where the audit was failing incorrectly by
    making the verifier a stable, self-contained tool.

## v2.0.2 (2025-07-15)

### Fix

- **migration-and-update**: resolve infinite-migration loop and drop STUDY_results.csv
    - Eliminate STUDY_results.csv entirely; aggregator now outputs only REPLICATION / EXPERIMENT CSVs  
    - Prevent infinite loop in legacy-migration workflow by ensuring state transitions NEW_NEEDED → COMPLETE  
    - update_experiment.ps1 enforces step-wise VERIFY → REPAIR/REPROCESS logic, never loops more than once  
    - Mermaid diagram and docstrings updated to reflect final artifact list

## v2.0.1 (2025-07-15)

### Fix

- **workflow**: improve script usability and test reliability
    - Adds graceful Ctrl+C handling to `experiment_manager.py` to prevent stack traces on user interruption.
    - Implements a progress bar in the migration workflow's report rebuilding step for better user feedback on long-running operations.
    - Corrects the mock argument order in `test_rebuild_reports.py` to fix failing tests and ensure test suite stability.
    - Updates `CONTRIBUTING.md` to document the more robust, two-step commit and release process.

## v2.0.0 (2025-07-14)

### BREAKING CHANGE

    - The `migrate_experiment.ps1` script's signature has changed. It no longer accepts a `-TargetDirectory` for in-place modification. Instead, it requires a `-SourceDirectory` and automatically handles the destination.

### Feat

- **workflow**: implement non-destructive migration and --reprocess flag

## v1.1.0 (2025-07-14)

### Feat

    - Add update_experiment script for reprocessing
    - **testing**: Add audit script and finalize test runner
    - **tests**: Introduce shared harness for PowerShell tests
    - **build**: Make docx conversion resilient to locked files
    - **testing**: Overhaul coverage and refactor compile_results test
    - **testing**: Implement test suite for migrate_old_experiment.ps1
    - **testing**: Implement full test suite for process_study.ps1
    - Integrate ArgBuilder logic into run_experiment.ps1 and finalize bare-bones, non-Pester testing setup
    - Establish working PowerShell test suite (without Pester) and retain ArgBuilder as production dependency
    - **build**: Automate documentation and diagram generation
    - Enhance final analysis workflow and reporting
    - Enhance analysis and untrack generated code files
    - Implement docs-as-code and finalize utilities

### Fix

    - **analysis**: Correct test logic and align scripts with docs
    - **builder**: Properly handle doc status check by build_docs.py during commit.
    - **docs**: Repair diagram rendering and optimize build script
    - **scripts**: Sync tests and improve build utility
    - **tests**: Exclude archive directories from test collection
    - **deps**: Add missing pytest-cov to dev dependencies

### Refactor

    - **project**: Consolidate architecture and testing
    - **analysis**: Rename study processing scripts for clarity
    - All tests passing with overall 60% coverage; test suite not necessarily complete.
    - Enhance test suite and update documentation
    - Centralize batch logic in Python and update config

## [1.0.0] - 2025-07-11

### Added
    - Initial personality matching experiment framework
    - LLM query generation and processing pipeline
    - Statistical analysis with ANOVA and bias detection
    - Experiment replication management system
    - Data migration tools for legacy experiments
    - Comprehensive logging and error handling
    - Study-level result compilation and analysis

### Framework Components
    - **Entry Points:** PowerShell scripts for user-friendly execution
    - **Core Pipeline:** Python scripts for LLM interaction and analysis
    - **Data Management:** Automated organization and validation
    - **Analysis Tools:** Statistical testing and bias detection
    - **Documentation:** Auto-generated reports and visualizations

### Supported Features
    - Multiple LLM model integration
    - Batch experiment processing
    - Automatic retry mechanisms
    - Result compilation across experiments
    - Statistical significance testing
    - Bias analysis and reporting
    - Legacy data migration