# Changelog

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