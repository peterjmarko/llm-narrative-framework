# Project Roadmap

This document outlines planned development tasks and tracks known issues for the project. The framework is designed to support two key research activities: the **direct replication** of the original study's findings by using the static data files included in the repository, and the **conceptual replication** of the methodology by generating new data from live sources. All development tasks are categorized by work stream below.

## Tasks Prior to Publication

### Code Development and Testing

This phase focuses on achieving a fully validated and stable codebase before the final data generation run.

- [ ] **Add the Option to Bypass Eminence/OCEAN Scoring**
  - [ ] Implement a configuration flag to allow 'final candidates' to be the same as 'eligible candidates'. This makes the LLM-based sample selection optional, allowing for validation studies that are more robust to the criticism of using an opaque selection method.
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

- [ ] **Perform and Report Correction for Multiple Comparisons**
  - [ ] Apply a Bonferroni or FDR (False Discovery Rate) correction to the final ANOVA results.
  - [ ] Add a footnote or supplementary note to the article reporting the corrected p-values to demonstrate statistical rigor.
- [ ] **Execute Full End-to-End Study**
  - [ ] Run the complete data preparation pipeline (`prepare_data.ps1`) to generate a fresh, final dataset from live sources.
  - [ ] Conduct the full experimental study, varying all three core factors (model name, group size, mapping strategy) to produce the final results.
  - [ ] This will serve as the final end-to-end validation of the entire framework and will generate the definitive data used in the manuscript.

### Final Documentation Polish

- [ ] **Update All Documents with Final Results**
  - [ ] Replace placeholder LLM names in `article_main_text.md` with the specific, versioned models used in the final study.
  - [ ] Update all tables, figures, counts, and statistical results in the article and documentation to reflect the final generated data.
  - [ ] Perform a final review of all documents to ensure they are clean, consistent, and easy for an external researcher to understand.

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

- [ ] **Enhance Interactive Test Harness with Step-Back Functionality**
  - [ ] Allow developers to step backward and forward through the guided tour for easier debugging and learning.
  - [ ] Refactor the test harness to manage pipeline steps as a stateful list.
  - [ ] Implement a command parser in the interactive prompt to handle 'back' and 'repeat' commands.
  - [ ] Develop logic to automatically delete the output artifacts of any steps being re-run to ensure a clean state.