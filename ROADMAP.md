# Project Roadmap

This document outlines planned development tasks and tracks known issues for the project. The framework is designed to support two key research activities: the **direct replication** of the original study's findings by using the static data files included in the repository, and the **conceptual replication** of the methodology by generating new data from live sources. All development tasks are categorized by work stream below.

## Completed Milestones

- [x] **Redesigned Final Candidate Selection Algorithm:**
  - The original heuristic-based algorithm was replaced with a robust, multi-stage, data-driven approach involving smoothed slope analysis of the cumulative personality variance curve to find a scientifically optimal cohort size.
  - A new standalone analysis script (`scripts/analyze_cutoff_parameters.py`) was created to perform a systematic sensitivity analysis, providing a data-driven recommendation for the optimal algorithm parameters.
  - A `--plot` flag was added to `select_final_candidates.py` to generate a diagnostic plot of the variance curve analysis, making the algorithm's decision-making process fully transparent.

- [x] **Hardened Data Preparation Pipeline:**
  - The `prepare_data.ps1` orchestrator was made significantly more intelligent. It now parses summary file content to robustly resume partially completed steps (e.g., Eminence and OCEAN scoring).
  - Both scoring scripts (`generate_eminence_scores.py`, `generate_ocean_scores.py`) now automatically regenerate their summary reports if run when data is complete, replacing confusing interactive prompts.
  - Added duplicate prevention logic to both scoring scripts to filter out redundant records returned by the LLM, ensuring data integrity.
  - The pipeline status report now has a more granular `[INCOMPLETE]` state for partially finished scoring runs.

- [x] **Improved User Experience and Reporting:**
  - Implemented `tqdm` progress bars in all long-running data preparation scripts for clean, real-time feedback.
  - The "PIPELINE HALTED" banner now uses a more readable dark orange color for non-error halts.
  - Standardized all summary report locations to `data/reports/`.
  - The `generate_eminence_scores.py` script now creates a `missing_eminence_scores.txt` report to easily identify data gaps.

- [x] **Standardized File Backup/Removal Logic**
  - A new shared utility module (`src/utils/file_utils.py`) was created to centralize file operations.
  - All data preparation scripts were refactored to use a single `backup_and_remove` function, ensuring consistent behavior.

- [x] **Data Preparation Pipeline Fully Tested**
  - All layers of testing for the data preparation pipeline are complete and passing, including a fully automated Layer 2 (Orchestration) test harness, ensuring a robust and reliable data foundation for the main experiments.

## Tasks Prior to Publication

### Code Development and Testing

This phase focuses on achieving a fully validated and stable codebase before the final data generation run.

- [ ] **Update Test Suites for New Candidate Selection Logic**
  The logic for determining the final subject pool was moved from `generate_ocean_scores.py` to `select_final_candidates.py`. The following test updates are required to reflect this change:
  - [ ] **Layer 1:** Simplify the `test_generate_ocean_scores.py` unit test, as the script is now much simpler.
  - [ ] **Layer 1:** Expand the `test_select_final_candidates.py` unit test to cover the new, critical variance-based cutoff logic.
  - [ ] **Layer 3:** Update the integration test with a larger, pre-generated seed file for `ocean_scores.csv` that is sufficient to trigger the cutoff logic and validate the new behavior.
  - [ ] **Layers 4-7:** Review and update all higher-level integration tests to remove any hard-coded assumptions about the final subject count, as it is now data-driven.
- [ ] **Standardize Layer 4 & 5 Integration Tests**
  - [ ] Create a new directory structure: `tests/testing_harness/experiment_pipeline/layer4/` and `layer5/`.
  - [ ] Create a master `run_layer4_test.ps1` script that orchestrates the setup, execution, and cleanup steps.
  - [ ] Create a master `run_layer5_test.ps1` script that does the same for the migration workflow.
  - [ ] Update `pyproject.toml` with new, simplified PDM commands (`test-l4`, `test-l5`) that use these master scripts.
- [ ] **Re-validate Integration Tests After Filter Changes**
  - [ ] Perform a full run of the Layer 4 and Layer 5 integration tests to ensure that the changes to the data filtering logic (Northern Hemisphere and eminence/OCEAN scoring) have not introduced any downstream regressions.
- [ ] **Develop `new_study.ps1` Orchestrator**
  - [ ] Implement the `new_study.ps1` workflow to automate multi-experiment studies based on a factor matrix in `config.ini`.
- [ ] **Test the New Study Orchestrator**
  - [ ] Create and execute a scripted integration test for the `new_study.ps1` script to ensure it correctly manages the study lifecycle.
- [ ] **Enhance Layer 4 Test Harness with a Guided Tour**
  - [ ] Add an `-Interactive` flag to the Layer 4 test workflow to provide a guided, step-by-step tour of the `new -> audit -> break -> fix` experiment lifecycle, similar to the existing tour for the data pipeline.
- [ ] **Complete Test Coverage for Existing Framework**
  - [ ] Implement Layer 6 Test Harness (Post-Hoc Study Evaluation) to validate the `compile_study.ps1` workflow.
  - [ ] Implement Layer 7 Test Harness (New Study Lifecycle) to validate the `new_study.ps1`, `audit_study.ps1`, and `fix_study.ps1` workflows.
  - [ ] Update and complete unit test suites for any remaining Python scripts with low coverage.

### Final Validation and Data Generation

- [x] **Perform and Report Correction for Multiple Comparisons**
  - [x] Apply a Bonferroni or FDR (False Discovery Rate) correction to the final ANOVA results.
  - [x] Add a footnote or supplementary note to the article reporting the corrected p-values to demonstrate statistical rigor.
- [ ] **Execute Full End-to-End Study**
  - [ ] Run the complete data preparation pipeline (`prepare_data.ps1`) to generate a fresh, final dataset from live sources.
  - [ ] Conduct the full experimental study, varying all three core factors (model name, group size, mapping strategy) to produce the final results.
  - [ ] This will serve as the final end-to-end validation of the entire framework and will generate the definitive data used in the manuscript.

### Final Documentation Polish

- [ ] **Update All Documents with Final Results**
  - [ ] Replace placeholder LLM names in `article_main_text.md` with the specific, versioned models used in the final study.
  - [ ] Update all tables, figures, counts, and statistical results in the article and documentation to reflect the final generated data.
  - [ ] Replace the text placeholder in `article_main_text.md` with the final, generated interaction plot (`interaction_plot_mean_rank.png`).
- [x] **Add Supporting Figures to Replication Guide**
  - [x] Embed existing data flow diagrams at the start of the data preparation section.
  - [x] Create and embed screenshots for the Solar Fire one-time setup process:
    - [x] `sf_setup_1_displayed_points.png` (Displayed Points dialog)
    - [x] `sf_setup_2_import_format.png` (Import Format dialog)
    - [x] `sf_setup_3_export_format.png` (Export Format dialog)
  - [x] Create and embed screenshots for the Solar Fire import/export workflow:
    - [x] `sf_workflow_1_clear_charts.png` (Clear Charts dialog)
    - [x] `sf_workflow_2_import_dialog.png` (Import dialog)
    - [x] `sf_workflow_3_export_dialog.png` (Export dialog)
- [ ] **Perform a final review of all documents** to ensure they are clean, consistent, and easy for an external researcher to understand.

## Online Presence & Final Review

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

## Paper Submission (PCI Psychology & Meta-Psychology)

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

- [ ] **Architectural Refactoring for Modularity**
  - [ ] Reorganize the `src/` directory into logical subdirectories (`data_preparation/`, `experimentation/`) to improve separation of concerns and navigability.
  - [ ] Mirror the new `src/` structure in the `tests/` directory to create a parallel test suite.
  - [ ] Move tests for developer utility scripts from `tests/` to a self-contained `scripts/tests/` directory.
  - [ ] Systematically update all import statements and script paths across the entire project to reflect the new structure.

- [ ] **Implement Shared Progress Bar Utility**
  - [ ] Create a new utility in `src/utils/` to provide a standardized, shared `tqdm` progress bar.
  - [ ] Refactor `generate_eminence_scores.py` and `generate_ocean_scores.py` to use this shared utility for a consistent user experience during long-running LLM calls.
- [ ] **Improve Experiment Execution and Reproducibility**
  - [ ] Refactor inter-script communication for robustness. Modify core Python scripts (`experiment_manager.py`, etc.) to send all human-readable logs to `stderr` and use `stdout` exclusively for machine-readable output (e.g., the final experiment path). Update PowerShell wrappers to correctly handle these separate streams.
  - [ ] Implement CLI-driven experiments where parameters are passed as arguments to `new_experiment.ps1` instead of being read from a global `config.ini`.
  - [ ] Generate an experiment manifest file with results to permanently record all parameters used (this will replace config.ini as the source of parameters).
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
  - [ ] Optimize the `migrate` command to skip re-running API calls for replications that are already valid.
  - [ ] Clean up `migrate_experiment.ps1` log files by removing PowerShell transcript headers and footers.

- [ ] **Refactor Data Pipeline Test Harness for Simplicity**
  - [ ] Modify the main `prepare_data.ps1` orchestrator to include a `-TestMode` flag. This will consolidate the complex test setup logic (e.g., the targeted fetching for Step 1) directly into the production script, eliminating code duplication.
  - [ ] Simplify the Layer 3 test harness scripts (`layer3_phase*.ps1`) to become simple wrappers that call `prepare_data.ps1` with the appropriate test-mode flags. This change will make the testing UI easier to maintain and ensure a consistent user experience between live runs and test runs.

- [ ] **Enhance Interactive Test Harness with Step-Back Functionality**
  - [ ] Allow developers to step backward and forward through the guided tour for easier debugging and learning.
  - [ ] Refactor the test harness to manage pipeline steps as a stateful list.
  - [ ] Implement a command parser in the interactive prompt to handle 'back' and 'repeat' commands.
  - [ ] Develop logic to automatically delete the output artifacts of any steps being re-run to ensure a clean state.