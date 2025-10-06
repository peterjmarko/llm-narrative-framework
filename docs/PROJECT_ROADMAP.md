# Project Roadmap

This document outlines planned development tasks and tracks known issues for the project. The framework is designed to support two key research activities: the **direct replication** of the original study's findings by using the static data files included in the repository, and the **conceptual replication** of the methodology by generating new data from live sources. All development tasks are categorized by work stream below.

## Tasks Prior to Publication

### 1. Final Data Generation and Study Execution

- [ ] **Execute Final Data Preparation**
  - [ ] Run the complete `prepare_data.ps1` pipeline to generate a fresh, final dataset from live sources.
- [ ] **Execute Final Study Runs**
  - [ ] Design final study.
  - [ ] Run `new_experiment.ps1` for each experimental condition defined in the paper, using fixed randomization seeds in `config.ini`.
- [ ] **Organize and Compile Final Study**
  - [ ] Manually create a final study directory (e.g., `output/studies/publication_run/`).
  - [ ] Move all generated experiment folders into the study directory.
  - [ ] Run `compile_study.ps1` to produce the definitive analysis and plots for the manuscript.
- [ ] **Perform and Report Correction for Multiple Comparisons**
  - [ ] Add a footnote or supplementary note to the article reporting the Benjamini-Hochberg FDR-corrected p-values to demonstrate statistical rigor.
- [ ] **Tag Publication Commit**
  - [ ] Create a permanent Git tag (e.g., `v1.0-publication`) to mark the exact version of the code used to generate the paper's results.

### 2. Final Documentation Polish

- [ ] **Update All Documents with Final Results**
  - [ ] Consolidate documentation: justify each document and sharply define scope and relationships.
    - [ ] Merge Lifecycle Guide into main README.
  - [ ] Replace placeholder LLM names in `article_main_text.md` with the specific, versioned models used in the final study.
  - [ ] Update all dates, tables, figures, counts, and statistical results in the article and documentation to reflect the final generated data.
  - [ ] Replace the text placeholder in `article_main_text.md` with the final, generated interaction plot (`interaction_plot_mean_rank.png`).
  - [ ] Address Research Article inconsistencies identified in documentation alignment:
    - [ ] Clarify statistical analysis - either report Three-Way ANOVA results consistent with 2×3×3 design or explain why Two-Way was used
    - [ ] Update model descriptions - specify all three evaluation LLMs or clarify scope of reported results
    - [ ] Correct statistical reporting - ensure degrees of freedom match experimental design
    - [ ] Add access dates - include October 2025 access dates for all LLMs
    - [ ] Add specific references - reference Framework Manual and Replication Guide in Supplementary Materials
    - [ ] Expand replication path descriptions - briefly describe each path with references to detailed guides
    - [ ] Verify figure references - ensure all figures have proper descriptions and clear references
- [ ] **Perform a final review of all documents** to ensure they are clean, consistent, and easy for an external researcher to understand.
  - [ ] Check all tables and diagrams.
  - [ ] Check counts and dates.

## Final Review and Preprint Publication

- [ ] **Establish Public Repository**
  - [ ] Create a public GitHub repository for the project.
  - [ ] Push all final code, data, and documentation to the repository.
- [ ] **Final Co-Author Review**
  - [ ] Provide the co-author with the final manuscript, the live repository link, and a summary of the final results.
  - [ ] Incorporate any final revisions from the co-author and push updates to the repository.
- [ ] **Update Author Profiles**
  - [ ] Update ORCID profile with the new publication/project.
- [ ] **Preprint Publication**
  - [ ] Post the final manuscript to a preprint server like PsyArXiv.

## Journal Submission and Peer Review

- [ ] **Solicit Pre-Submission Expert Feedback**
  - [ ] Identify and contact key field experts (e.g., Currey, Godbout) for friendly pre-submission reviews.
  - [ ] Incorporate feedback into the final manuscript draft.
- [ ] **Final Co-Author Approval**
  - [ ] Secure final approval from the co-author on the revised manuscript before submission.
- [ ] **Manuscript Finalization**
  - [ ] Prepare the final version of the manuscript with numbered lines.
- [ ] **Compliance & Disclosure**
  - [ ] Complete the TOP (Transparency and Openness Promotion) disclosure table and add it as an appendix.
  - [ ] Complete the "Self-Assessment Questionnaire" from the PCI Psychology guide to ensure the project meets all standards.
- [ ] **Submission Preparation**
  - [ ] Identify suitable Recommenders whose research interests align with the paper.
  - [ ] Prepare the PCI Psychology submission form.
- [ ] **Submission**
  - [ ] Submit the completed package to PCI Psychology.
  - [ ] IF RECOMMENDED (PATH A): Submit the manuscript to Meta-Psychology.
    - [ ] If needed, submit to Collabra: Psychology
    - [ ] If needed, submit to Royal Society Open Science
  - [ ] IF REJECTED (PATH B): Revise Manuscript using the PCI feedback. Submit the improved manuscript for a fresh review at AMPPS
    - [ ] If needed, submit to Behavior Research Methods
    - [ ] If needed, submit to PLOS One

## Future Work: Potential Enhancements After Publication

### Code Development

- [ ] **Create Unit Tests for Developer Utility Scripts**
  - [ ] `src/utils/analyze_research_patterns.py`
  - [ ] `src/utils/patch_eminence_scores.py`
  - [ ] `src/utils/validate_country_codes.py`
  - [ ] `scripts/analysis/analyze_cutoff_parameters.py`
  - [ ] `scripts/analysis/get_docstring_summary.py`
  - [ ] `scripts/analysis/inspect_adb_categories.py`
  - [ ] `scripts/analysis/validate_import_file.py`
  - [ ] `scripts/lint/lint_docstrings.py`
  - [ ] `scripts/lint/lint_file_headers.py`
  - [ ] `scripts/maintenance/clean_project.py`
  - [ ] `scripts/maintenance/convert_py_to_txt.py`
  - [ ] `scripts/maintenance/generate_scope_report.py`
  - [ ] `scripts/maintenance/list_project_files.py`
  - [ ] `scripts/workflows/assembly_logic/1_generate_coverage_map.py`
  - [ ] `scripts/workflows/assembly_logic/2_select_assembly_logic_subjects.py`
  - [ ] `scripts/workflows/assembly_logic/3_prepare_assembly_logic_import.py`
  - [ ] `scripts/workflows/assembly_logic/4_extract_assembly_logic_text.py`
  - [ ] `scripts/workflows/assembly_logic/5_validate_assembly_logic_subjects.py`

- [ ] **Architectural Refactoring for Modularity**
  - [ ] Apply the "Refactor for Testability" pattern (extracting complex functions to the module level for direct patching) to other orchestrators like `experiment_manager.py`.
  - [ ] Reorganize the `src/` directory into logical subdirectories (`data_preparation/`, `experimentation/`) to improve separation of concerns and navigability.

- [ ] **Refactor Core Scripts for Consistent Logging**
  - [ ] Systematically replace all user-facing `print()` statements with appropriate `logging` calls to ensure that `--quiet` flags are respected framework-wide. This task is parked for post-publication as it requires a significant refactoring of the unit test suites that currently mock `print()`.
  - [ ] Mirror the new `src/` structure in the `tests/` directory to create a parallel test suite.
  - [ ] Move tests for developer utility scripts from `tests/` to a self-contained `scripts/tests/` directory.
  - [ ] Systematically update all import statements and script paths across the entire project to reflect the new structure.

- [ ] **Implement Shared Progress Bar Utility**
  - [ ] Create a new utility in `src/utils/` to provide a standardized, shared `tqdm` progress bar.
  - [ ] Refactor `generate_eminence_scores.py` and `generate_ocean_scores.py` to use this shared utility for a consistent user experience during long-running LLM calls.
- [ ] **Implement Automated Study Lifecycle Management**
  - [ ] Restructure `config.ini` to accommodate [Study] parameters (like for Layer 4). Sync with Layer 4 approach.
  - [ ] Implement a `new_study.ps1` orchestrator to automate the creation of multi-experiment studies based on a factor matrix in `config.ini`.
  - [ ] Develop a corresponding Layer 7 test harness to validate the full `new -> audit -> break -> fix` study workflow.
  - [ ] Implement `fix_study.ps1` to provide an automated repair workflow for entire studies.
- [ ] **Implement Provenance Capture**
  - [ ] Modify `new_experiment.ps1` to generate a `provenance.json` file in each new experiment directory.
  - [ ] The provenance file will capture Git state (commit SHA, tag) and key environment details (Python version, OS).
  - [ ] Implement a smoke test that runs `new_experiment.ps1` with a minimal configuration and asserts that the `provenance.json` file is correctly generated.

**Note**: This task is distinct from the "Generate an experiment parameters manifest (`parameters.json`) to permanently record all parameters used" task under "Improve Experiment Execution and Reproducibility" below. The current provenance capture focuses on environmental metadata only (via `provenance.json`), while the future parameters manifest (via `parameters.json`) will be part of CLI-driven experiments and replace config.ini as the parameter source.

- [ ] **Implement Comprehensive Test Results Preservation System**
  - [ ] Create centralized test results repository structure in `tests/results/` with archives, latest symlinks, and summaries
  - [ ] Develop test results manager module (`src/utils/test_results_manager.py`) for consistent preservation across all test types
  - [ ] Update all test harness scripts (Layer 2-5) to use the new preservation system
  - [ ] Create test summary generator (`scripts/testing/generate_test_summary.py`) for aggregating and comparing results
  - [ ] Implement test results viewer tool (`scripts/testing/view_test_results.py`) for browsing historical results
  - [ ] Add PDM commands for accessing test results: `test-results-view` and `test-results-summary`
  - [ ] Update testing guide to document the new preservation approach and usage

- [ ] **Improve Experiment Execution and Reproducibility**
  - [ ] Refactor inter-script communication for robustness. Modify core Python scripts (`experiment_manager.py`, etc.) to send all human-readable logs to `stderr` and use `stdout` exclusively for machine-readable output (e.g., the final experiment path). Update PowerShell wrappers to correctly handle these separate streams.
  - [ ] Implement CLI-driven experiments where parameters are passed as arguments to `new_experiment.ps1` instead of being read from a global `config.ini`.
  - [ ] Generate an experiment parameters manifest (`parameters.json`) to permanently record all parameters used (this will replace config.ini as the source of parameters).
  - [ ] Update `audit`, `repair`, and `migrate` workflows to use the manifest as the ground truth.
- [ ] **Concurrent LLM Averaging for Eminence and OCEAN Scores**
  - [ ] Use a "wisdom of the crowd" approach by querying multiple different LLMs for the same batch and averaging their scores to get more stable, less biased results for both eminence and personality scoring.
- [ ] **Pre-Run Estimate of Cost and Time**
  - [ ] Before processing the first batch, the script would calculate and display:
    - [ ] The total number of new subjects to be processed.
    - [ ] The total number of API calls (batches) that will be made.
    - [ ] An estimated total cost for the entire run, based on the chosen model's pricing.
    - [ ] A very rough estimated time to completion.
- [ ] **Improve Migration Workflow**
  - [ ] Re-introduce the `migrate_experiment.ps1` workflow for upgrading legacy or corrupted single experiments.
  - [ ] Optimize the `migrate` command to skip re-running API calls for replications that are already valid.
  - [ ] Clean up `migrate_experiment.ps1` log files by removing PowerShell transcript headers and footers.
  - [ ] Implement `migrate_study.ps1` to provide a batch-migration workflow for entire studies.

- [ ] **Refactor Data Pipeline Test Harness for Simplicity**
  - [ ] Modify the main `prepare_data.ps1` orchestrator to include a `-TestMode` flag. This will consolidate the complex test setup logic (e.g., the targeted fetching for Step 1) directly into the production script, eliminating code duplication.
  - [ ] Simplify the Layer 3 test harness scripts (`layer3_phase*.ps1`) to become simple wrappers that call `prepare_data.ps1` with the appropriate test-mode flags. This change will make the testing UI easier to maintain and ensure a consistent user experience between live runs and test runs.

- [ ] **Enhance Interactive Test Harness with Step-Back Functionality**
  - [ ] Allow developers to step backward and forward through the guided tour for easier debugging and learning.
  - [ ] Refactor the test harness to manage pipeline steps as a stateful list.
  - [ ] Implement a command parser in the interactive prompt to handle 'back' and 'repeat' commands.
  - [ ] Develop logic to automatically delete the output artifacts of any steps being re-run to ensure a clean state.