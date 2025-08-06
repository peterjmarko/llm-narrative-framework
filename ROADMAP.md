# Project Roadmap

This document outlines the planned development tasks for the project, categorized by work stream.

## Code Development

- [ ] **Automate Foundational Assets**
  - [ ] Develop script to generate `eminence_scores.csv`.
- [ ] **Integrate Automated Data Fetching**
  - [ ] Update `validate_adb_data.py` to parse the new fetched format.
  - [ ] Update `filter_adb_candidates.py` to parse the new fetched format.
- [ ] **Automate Delineation Neutralization**
  - [ ] Create `src/neutralize_delineations.py` to process the raw library via LLM.
- [ ] **Create `new_study.ps1` Workflow**
  - [ ] Develop a new top-level script to automate the creation of an entire study by running a matrix of experiments.
- [ ] **Update Test Suite**
  - [ ] Update all PowerShell and Python tests to reflect the current codebase.
  - [ ] Ensure the test suite is robust and provides thorough coverage.

## Documentation

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
  
## Completed

- [x] All tasksk to v3.16.0 (2025-08-05)
- [x] Establish a complete and robust documentation suite.
- [x] Implement a CI workflow with GitHub Actions.
- [x] Correct and align all architectural diagrams across all project domains.
- [x] Create a `ROADMAP.md` to track remaining work.
- [x] Develop script to validate `country_codes.csv`.
