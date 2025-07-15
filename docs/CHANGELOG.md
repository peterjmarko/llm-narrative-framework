# Changelog

All notable changes to the Personality Matching Experiment Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v2.0.1 (2025-07-15)

### Fix

- **workflow**: improve script usability and test reliability
- **workflow**: improve migration progress display and Ctrl-C handling

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