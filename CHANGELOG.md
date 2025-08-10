# Changelog

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