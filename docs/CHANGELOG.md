# Changelog

All notable changes to the Personality Matching Experiment Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (Your next feature here)

## [1.1.0] - 2025-07-14

### Added
- New `update_experiment.ps1` script for reprocessing experiments.
- New `audit_experiment.ps1` script for validating experiment completeness.
- `commitizen` integration for standardized commits and automated changelogs.
- Shared test harness for PowerShell scripts.

### Changed
- **BREAKING**: Refactored project architecture into five distinct, documented workflows.
- **BREAKING**: Renamed `process_study.ps1` to `analyze_study.ps1`.
- Updated all documentation (`README.md`, `DOCUMENTATION.md`, `CONTRIBUTING.md`) to align with the consolidated architecture.

### Fixed
- Corrected logic in the statistical analysis module.
- Repaired diagram rendering and optimized the documentation build script.
- Excluded archive directories from test collection.
- Added missing `pytest-cov` development dependency.

### Build
- Automated test coverage cleanup and updated script paths.
- Made DOCX conversion resilient to locked files.

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