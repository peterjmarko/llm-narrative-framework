# Project Roadmap

This document outlines planned development tasks and tracks known issues for the project. The framework is designed to support two key research activities: the **direct replication** of the original study's findings by using the static data files included in the repository, and the **conceptual replication** of the methodology by generating new data from live sources. All development tasks are categorized by work stream below.

## Tasks Prior to Publication

### Code Development and Testing

This phase focuses on achieving a fully validated and stable codebase before the final data generation run.

- [ ] **Complete Test Coverage for Existing Framework**
  - [ ] Update and complete the test suites for all existing Python scripts and PowerShell wrappers.
- [ ] **Develop `new_study.ps1` Orchestrator**
  - [ ] Implement the `new_study.ps1` workflow to automate multi-experiment studies based on a factor matrix in `config.ini`.
- [ ] **Test the New Study Orchestrator**
  - [ ] Create and execute a scripted integration test for the `new_study.ps1` script to ensure it correctly manages the study lifecycle.

### Resolution of Known Issues

The following issues will be addressed concurrently during the "Code Development and Testing" phase.

-   **Inconsistent Logging**:
    -   Log files from migration scripts contain unnecessary PowerShell transcript headers and footers.
-   **Redundant API Calls**: Forcing a migration on an already `VALIDATED` experiment unnecessarily re-runs all LLM API calls.

### Final Validation and Data Generation

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

- [ ] **Improve Experiment Execution and Reproducibility**
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