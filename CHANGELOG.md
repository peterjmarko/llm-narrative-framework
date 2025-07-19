# Changelog

All notable changes to the Personality Matching Experiment Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v2.7.0 (2025-07-19)

### Feat

- **audit-study**: introduce study-level audit and enhance output

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