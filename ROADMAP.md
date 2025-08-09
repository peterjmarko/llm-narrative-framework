# Project Roadmap

This document outlines planned development tasks and tracks known issues for the project. The framework is designed to support two key research activities: the **direct replication** of the original study's findings by using the static data files included in the repository, and the **conceptual replication** of the methodology by generating new data from live sources. All development tasks are categorized by work stream below.

## Tasks Prior to Release

### Code Development

- [ ] **Automate Foundational Assets**
  - [ ] Develop `generate_eminence_scores.py` script to create the eminence file via LLM.
    - [ ] The script must read `adb_raw_export.txt` as its source.
    - [ ] The output file (`eminence_scores.csv`) must contain the headers: `idADB`, `Name`, `EminenceScore`.
  - [ ] Update `filter_adb_candidates.py` to use the new `eminence_scores.csv`.
    - [ ] This will replace the temporary name-based matching with the permanent, robust `idADB`-based lookup.
    - [ ] The script should include a secondary name-matching check to ensure data integrity between the source files.
  - [ ] Develop `generate_ocean_scores.py` script to create the OCEAN file via LLM.
    - [ ] The script will proceed in the order of eminence scores established in `eminence_scores.csv`.
    - [ ] It will continually evaluate the variance in OCEAN scores and stop at a pre-determined cutoff (when it falls below a certain threshold).
    - [ ] The total number of entries at this cutoff point will be rounded down to the nearest 100 and will be used for filtering the ADB database.
- [ ] **Automate Delineation Neutralization**
  - [ ] Create `src/neutralize_delineations.py` to process the raw library via LLM.

### Resolution of Known Issues

-   **Inconsistent Logging**:
    -   The log file for `repair_experiment.ps1` is not as detailed as those from other scripts.
    -   The `process_study.ps1` workflow does not currently generate a dedicated log file.
    -   Log files from migration scripts contain unnecessary PowerShell transcript headers and footers.
-   **Redundant API Calls**: Forcing a migration on an already `VALIDATED` experiment unnecessarily re-runs all LLM API calls.
-   **Outdated Test Suite**: The test suite for the PowerShell wrapper scripts is out of date and does not reflect the current command-line arguments or script behaviors.

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

## Tasks After Release

### Code Development

- [ ] **Improve Experiment Execution and Reproducibility**
  - [ ] Implement CLI-driven experiments where parameters are passed as arguments to `new_experiment.ps1` instead of being read from a global `config.ini`.
  - [ ] Generate an experiment manifest file with results to permanently record all parameters used (this will replace config.ini as the source of parameters).
  - [ ] Update `audit`, `repair`, and `migrate` workflows to use the manifest as the ground truth.
- [ ] **Automate Study Generation (`new_study.ps1`)**
  - [ ] Develop the `new_study.ps1` workflow to orchestrate multiple `new_experiment.ps1` calls based on a factor matrix, creating entire studies automatically.
- [ ] **Update and Restore Test Coverage**
  - [ ] Update all PowerShell and Python tests to reflect the current codebase.
  - [ ] Ensure the test suite is robust and provides thorough coverage.
