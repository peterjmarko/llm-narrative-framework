# Changelog

All notable changes to the Personality Matching Experiment Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive documentation suite with architecture diagrams
- Mermaid diagrams for workflow visualization
- PowerShell entry points for cross-platform compatibility
- Automated documentation building with uild_docs.py
- Professional README with complete setup instructions

### Changed
- Renamed scripts for clarity and specificity:
  - eplication_manager.py → xperiment_manager.py
  - uild_queries.py → uild_llm_queries.py
  - nalyze_performance.py → nalyze_llm_performance.py
  - etry_failed_sessions.py → etry_llm_sessions.py
  - compile_results.py → compile_study_results.py
  - un_anova.py → nalyze_study_results.py
  - erify_pipeline_completeness.py → erify_experiment_completeness.py
  - log_manager.py → eplication_log_manager.py
  - patch_old_runs.py → patch_old_experiment.py

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
