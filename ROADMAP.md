# Project Roadmap

This document outlines planned development tasks and tracks known issues for the project. The framework is designed to support two key research activities: the **direct replication** of the original study's findings by using the static data files included in the repository, and the **conceptual replication** of the methodology by generating new data from live sources. All development tasks are categorized by work stream below.

## Tasks Prior to Publication

### Code Development

- [ ] **Re-engineer Data Prep Pipeline for Efficiency**
  - [ ] Create `select_eligible_candidates.py` to perform all data quality checks *before* LLM scoring, producing a list of all candidates eligible for the study.
  - [ ] Rename `filter_adb_candidates.py` to `select_final_candidates.py` and simplify its logic to be the final filter that matches the eligible list against the OCEAN set.
  - [ ] Update `generate_eminence_scores.py` to use the output of `select_eligible_candidates.py` as its input, ensuring no resources are wasted on scoring invalid subjects.
- [ ] **Automate Delineation Neutralization**
  - [ ] Create `src/neutralize_delineations.py` to process the raw library via LLM.
- [ ] **Update and Restore Test Coverage**
  - [ ] Update all PowerShell and Python tests to reflect the current codebase.
  - [ ] Ensure the test suite is robust and provides thorough coverage.

### Resolution of Known Issues

-   **Inconsistent Logging**:
    -   The log file for `repair_experiment.ps1` is not as detailed as those from other scripts.
    -   The `process_study.ps1` workflow does not currently generate a dedicated log file.
    -   Log files from migration scripts contain unnecessary PowerShell transcript headers and footers.
-   **Redundant API Calls**: Forcing a migration on an already `VALIDATED` experiment unnecessarily re-runs all LLM API calls.

### Documentation

- [ ] **Create "How to Reproduce" Guide**
  - [ ] Add a top-level section to `DOCUMENTATION.md` that provides a clear, step-by-step guide for reproducing the study's findings from start to finish.
- [ ] **Final Documentation Polish**
  - [ ] Ensure all data files, scripts, and supplementary materials are clean, well-documented, and easy for an external researcher to understand.

## Online Presence & Open Science

- [ ] **Establish Public Repository**
  - [ ] Create a public GitHub repository for the project.
  - [ ] Push all final code, data, and documentation to the repository.
- [ ] **Update Author Profiles**
  - [ ] Update ORCID profile with the new publication/project.
- [ ] **Preprint Publication**
  - [ ] Post the final manuscript to a preprint server like PsyArXiv.

## Paper Submission (PCI Psychology & Meta-Psychology)

- [ ] **Solicit Pre-Submission Expert Feedback**
  - [ ] Identify and contact key field experts (e.g., Currey, Godbout, Kosinski) for friendly pre-submission reviews.
  - [ ] Incorporate feedback into the final manuscript draft.
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

- [ ] **Improve Experiment Execution and Reproducibility**
  - [ ] Implement CLI-driven experiments where parameters are passed as arguments to `new_experiment.ps1` instead of being read from a global `config.ini`.
  - [ ] Generate an experiment manifest file with results to permanently record all parameters used (this will replace config.ini as the source of parameters).
  - [ ] Update `audit`, `repair`, and `migrate` workflows to use the manifest as the ground truth.
- [ ] **Automate Study Generation (`new_study.ps1`)**
  - [ ] Develop the `new_study.ps1` workflow to orchestrate multiple `new_experiment.ps1` calls based on a factor matrix, creating entire studies automatically.
- [ ] **Concurrent LLM Averaging for Eminence Scores**
  - [ ] Use a "wisdom of the crowd" approach by querying 4 different LLMs for the same batch and averaging their scores to get a more stable, less biased result.
- [ ] **Pre-Run Estimate of Cost and Time**
  - [ ] Before processing the first batch, the script would calculate and display:
    - [ ] The total number of new subjects to be processed.
    - [ ] The total number of API calls (batches) that will be made.
    - [ ] An estimated total cost for the entire run, based on the chosen model's pricing.
    - [ ] A very rough estimated time to completion.