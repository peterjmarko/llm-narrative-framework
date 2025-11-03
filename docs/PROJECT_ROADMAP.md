# Project Roadmap

This document outlines planned tasks categorized by work stream and tracks known issues for the project.

## Journal Submission and Peer Review

- [ ] **Submission Preparation**
  - [ ] Identify suitable Recommenders whose research interests align with the paper.
  - [ ] Prepare the PCI Psychology submission form.
- [ ] **Submission**
  - [ ] Submit the completed package to PCI Psychology. Tag the latest release as 'pci-submission'.
  - [ ] IF RECOMMENDED (PATH A): Submit with PCI recommendation. Tag the latest release as 'publication'.
    - [ ] Meta-Psychology (first choice: free, methodological focus)
    - [ ] Collabra: Psychology (second choice: free, PCI-friendly)
    - [ ] Behavior Research Methods (third choice: methodology focus)
    - [ ] PLOS ONE (fourth choice: broad scope)
  - [ ] IF REJECTED (PATH B): Revise using PCI feedback, submit directly to journals
    - [ ] Behavior Research Methods (first choice: methodology papers)
    - [ ] AMPPS (second choice: methods/practices focus)
    - [ ] PLOS ONE (third choice: broad acceptance)

## Future Work: Potential Enhancements After Publication

### Pipeline Robustness and Reporting
- [ ] **Correct the reporting logic in `analyze_cutoff_parameters.py`** to align with its stability-focused selection algorithm.
  - [ ] Sort the `cutoff_parameter_stability_report.txt` by `Deviation from Consensus` instead of by `Error`.
  - [ ] Add the `Deviation` column to the final `cutoff_parameter_analysis_results.csv` to provide context for the recommendation.
- [ ] **Implement consistent artifact backup mechanism** for key data preparation scripts.
  - [ ] `select_final_candidates.py`: Add backup for the `variance_curve_analysis.png` file before it is overwritten.
  - [ ] `analyze_cutoff_parameters.py`: Add backup for its three output files (`.csv`, `.txt`) before they are overwritten.

### Code Development

- [ ] **Create Unit Tests for Developer Utility Scripts**
  - [ ] `src/utils/analyze_research_patterns.py`
  - [ ] `src/utils/patch_eminence_scores.py`
  - [ ] `src/utils/validate_country_codes.py`
  - [ ] `src/generate_consolidated_effect_charts.py`
  - [ ] `scripts/analysis/analyze_cutoff_parameters.py`
  - [ ] `scripts/analysis/analyze_neutralized_library_diversity.py`
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
  - [ ] **Known Issue:** `analyze_study_results.py` outputs verbose logging to console even without console handler, likely due to Python's `lastResort` handler. Multiple suppression attempts (NullHandler, CRITICAL+1 level, clearing handlers) have failed. Low priority as analysis completes correctly and logs save properly. May require stderr redirection or fundamental logging redesign.

- [ ] **Implement Shared Progress Bar Utility**
  - [ ] Create a new utility in `src/utils/` to provide a standardized, shared `tqdm` progress bar.
  - [ ] Refactor `generate_eminence_scores.py` and `generate_ocean_scores.py` to use this shared utility for a consistent user experience during long-running LLM calls.
- [ ] **Implement Interactive Study Parameter Selection**
  - [x] Restructure `config.ini` to accommodate [Study] parameters
  - [x] Enhance `new_experiment.ps1` to present interactive selection from study design matrix
  - [x] Implement study creation logging for tracking experimental conditions
  - [ ] Update Layer 4 test suite for compatibility

- [ ] **Implement Automated Study Lifecycle Management**
  - [ ] Implement a `new_study.ps1` orchestrator to automate batch creation of all experimental conditions from study design matrix
  - [ ] Develop a corresponding Layer 7 test harness to validate the full `new -> audit -> break -> fix` study workflow
  - [ ] Implement `fix_study.ps1` to provide an automated repair workflow for entire studies

- [ ] **Implement CLI-Driven Experiment Creation**
  - [ ] Add command-line parameter support to `new_experiment.ps1` for non-interactive use
  - [ ] Support syntax: `.\new_experiment.ps1 -MappingStrategy "correct" -GroupSize 7 -Model "meta-llama/llama-3.3-70b-instruct"`
  - [ ] Maintain backward compatibility with interactive and config-only modes
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

### Data Pipeline Reporting Enhancements

- [ ] **Enhance Data Preparation Pipeline Summary Report**
  - [ ] **Performance Metrics**: Add timing information for each pipeline stage, estimated API costs, and processing speed metrics
  - [ ] **Historical Comparisons**: Track changes over time and compare pipeline runs with different parameters
  - [ ] **Visual Elements**: Implement ASCII charts for better visualization and color-coding for status indicators
  - [ ] **Automated Recommendations**: Develop more sophisticated analysis of issues and suggested parameter adjustments
  - [ ] **Integration with Pipeline Management**: Add direct links to retry failed steps and automatic issue detection and resolution