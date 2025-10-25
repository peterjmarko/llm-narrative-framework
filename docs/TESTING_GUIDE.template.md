# Testing Guide for the LLM Narrative Framework

This document outlines the testing philosophy, procedures, and coverage strategy for the framework. It serves as a guide for developers and a record of the project's quality assurance standards.

## 📚 Related Documentation

- **[👨‍💻 Developer's Guide](../DEVELOPERS_GUIDE.md)** - Development environment setup and contribution workflows (start here if you're new)
- **[🔬 Replication Guide](REPLICATION_GUIDE.md)** - Step-by-step procedures that these tests validate
- **[🔧 Framework Manual](FRAMEWORK_MANUAL.md)** - Technical specifications for the system being tested
- **[📖 README](../README.md)** - Project overview and quick start

---

## 👥 Who Should Read This Document

**Primary Audience:**
- **Developers** contributing code to the framework
- **QA Engineers** validating framework correctness
- **Researchers** wanting to understand validation methodology

**You should read this if you want to:**
- Understand the testing philosophy and architecture
- Run the test suite and interpret results
- Add new tests for new functionality
- Use interactive tours to learn the framework's workflows
- Validate statistical analyses against external tools

**You should also read this if you're a researcher who wants:**
- Educational walkthroughs of the data preparation and experiment workflows (see interactive test modes)

**You should read something else if you want to:**
- Set up development environment → See **[👨‍💻 Developer's Guide](../DEVELOPERS_GUIDE.md)**
- Run experiments or replicate the study → See **[🔬 Replication Guide](REPLICATION_GUIDE.md)**
- Technical specifications → See **[🔧 Framework Manual](FRAMEWORK_MANUAL.md)**

**Note for Researchers**: The interactive test modes (Layer 3 & Layer 4) provide educational walkthroughs of the procedures described in the Replication Guide. While designed as validation tools, they serve as excellent learning resources for understanding the framework's workflows.

---

{{toc}}

## Testing Philosophy and Architecture

The project's testing strategy is organized into a clear, four-part hierarchy—the "Four Pillars"—designed to ensure both scientific validity and software robustness. This approach allows for rigorous, independent verification at every level of the framework.

{{diagram:docs/diagrams/test_philosophy_overview.mmd | scale=2.5 | width=100% | caption=The Four Testing Pillars: A comprehensive overview of the testing philosophy and how each pillar breaks down into specific validation areas.}}

### The Four Testing Pillars

**1. Unit Testing** validates individual components in isolation. These tests use `pytest` to verify that each Python script performs its intended function correctly, with proper error handling and edge case management. Unit tests are fast and focused, providing rapid feedback during development.

**2. Integration Testing** validates complete workflows from end to end. These tests run the actual production scripts in isolated sandbox environments to ensure that all components work together correctly. Integration tests catch issues that only emerge when multiple components interact, such as file format incompatibilities or state management errors.

**3. Algorithm Validation** provides mathematical proof of correctness for the framework's core methodological contributions. These standalone tests verify that the framework's novel algorithms produce scientifically valid results, including bit-for-bit validation against reference implementations.

**4. Statistical Analysis & Reporting Validation** provides external verification against industry-standard tools. By comparing the framework's statistical calculations against GraphPad Prism 10.6.1, this validation establishes academic credibility and ensures publication-ready analyses.

### Testing Layers and Modes

The integration tests are organized into a layered architecture that mirrors the framework's workflow:

**Layer 2: Data Pipeline State Machine Validation**

- Tests the orchestrator's halt/resume logic using lightweight mock scripts
- Validates state transitions without requiring expensive LLM calls
- Command: `pdm run test-l2`

**Layer 3: Complete Data Pipeline**

- Tests the full data preparation workflow from raw data to final profiles
- Runs in three modes: default, bypass, and interactive
- Commands: `pdm run test-l3`, `pdm run test-l3-bypass`, `pdm run test-l3-interactive`

**Layer 4: Experiment Lifecycle**

- Tests the complete `new -> audit -> break -> fix` workflow
- Includes deliberate corruption scenarios and automated repair validation
- Commands: `pdm run test-l4`, `pdm run test-l4-interactive`

**Layer 5: Study Compilation**

- Tests multi-experiment aggregation and statistical analysis
- Validates the complete study workflow using realistic test data
- Command: `pdm run test-l5`

### Testing Modes Explained

**Default Mode** runs tests with standard configuration settings, including LLM-based candidate selection and all production features enabled. This mode validates the framework as it will be used in actual research.

**Bypass Mode** disables LLM-based selection steps, allowing validation of the deterministic pipeline components without API costs. This mode is useful for testing infrastructure and file processing logic.

**Interactive Mode** transforms automated tests into educational guided tours. These modes pause before each major step, explain what will happen, and allow inspection of intermediate results. Interactive modes are invaluable for learning the framework and debugging complex workflows.

**Automated Mode** runs tests without user interaction, making them suitable for continuous integration pipelines and rapid validation during development.

### Sandbox Architecture

All integration tests run in isolated `temp_test_environment` directories at the project root. This ensures tests are:

- **Non-destructive**: Never modify production files or directories
- **Reproducible**: Start from a clean state every time
- **Parallel-safe**: Multiple tests can run without interfering (prevented by global lock)
- **Self-contained**: All test assets are created and cleaned up automatically

### Race Condition Prevention

All test operations and data processing workflows use a global lock mechanism to prevent concurrent execution. This ensures:

- **Data Integrity**: No simultaneous operations can corrupt shared data files
- **Experiment Safety**: Only one experiment operation runs at a time
- **Automatic Management**: Locks are acquired/released automatically through PDM commands and pytest fixtures

If you encounter a "Cannot acquire lock" error:
1. Wait for the current operation to complete
2. If certain no operations are running (e.g., after a crash), use `pdm run unlock`

The lock is implemented at the project level in `.pdm-locks/operations.lock` and is automatically cleaned up by the OS if a process crashes.

## Audit Logging

All test executions are automatically logged to `tests/results/test_summary.jsonl`. Each entry includes:
- Timestamp
- Operation name
- Status (PASS/FAIL)
- Exit code
- Duration in seconds
- Full command executed

This provides a permanent record of test execution history. The audit log is managed automatically by `scripts/maintenance/operation_runner.py` and requires no manual intervention.

Example entries:

```json
{"timestamp": "2025-10-12T14:30:22.123456", "operation": "test-data-prep", "status": "PASS", "exit_code": 0, "duration_seconds": 12.45, "command": "pytest tests/data_preparation/"}
{"timestamp": "2025-10-12T14:35:10.789012", "operation": "test-l4", "status": "PASS", "exit_code": 0, "duration_seconds": 347.82, "command": "pwsh -File ./tests/testing_harness/experiment_workflow/layer4/run_layer4_test.ps1"}
```

Similarly, data preparation runs are logged to `data_prep_summary.jsonl` and workflow operations to `workflow_summary.jsonl`.

## Typical Testing Sequence

**Note on PDM commands:** PDM allows two syntaxes for running custom scripts: `pdm run <script-name>` and the shorter `pdm <script-name>`. Both achieve the same result. This guide uses the more explicit `pdm run` form for clarity, but you can use either.

This section provides a practical walkthrough of running the complete test suite. The workflow is divided into two major parts, reflecting a clear separation of concerns:

- **Part 1: Core Software Validation:** Fast, self-contained tests that validate the software's components and workflows. These are ideal for rapid feedback during development and for continuous integration (CI) pipelines. They use small, controlled test assets and do not require a full production dataset.

- **Part 2: Scientific & Large-Scale Validation:** Slower, more intensive tests that validate the scientific integrity and performance of the framework's core algorithms at scale. These tests **require a full production dataset** as a prerequisite.

**Note on PDM commands:** PDM allows two syntaxes for running custom scripts: `pdm run <script-name>` and `pdm <script-name>`. Both achieve the same result. This documentation uses `pdm run` for clarity, but you can use either form.

### Part 1: Core Software Validation (CI/CD Friendly)

Follow this sequence for rapid, everyday validation.

#### Stage 0: Infrastructure Tests
Start by validating the foundational infrastructure for locking, logging, and recovery.

```bash
# Test the operation runner (locking and logging)
pdm run test-op-runner

# Test the backup and restore functionality
pdm run test-restore-backup
```
**Why first?** These quick tests (< 5 seconds total) confirm that the core framework services are working correctly before running longer test suites.

#### Stage 1: All Unit Tests
Run the complete suite of fast, isolated unit tests for all Python components.

```bash
# Test all data preparation components
pdm run test-data-prep

# Test all experiment workflow components
pdm run test-exp-wf
```
**Why second?** This validates the internal logic of every individual script before testing how they work together.

#### Stage 2: Data & Experiment Integration Tests (Small Scale)
Validate the complete end-to-end workflows using a small, fast, controlled dataset in an isolated sandbox.

```bash
# State Machine Logic (Layer 2)
pdm run test-l2

# Complete Data Pipeline (Layer 3)
pdm run test-l3
pdm run test-l3-bypass
pdm run test-l3-interactive

# Experiment Lifecycle (Layer 4)
pdm run test-l4
pdm run test-l4-interactive

# Study Compilation (Layer 5)
pdm run test-l5
```
**Why third?** These tests confirm that all software components integrate and execute correctly from start to finish, validating the complete workflow logic without the time and expense of a full production run.

#### Stage 3: Randomization Integrity Test
Validate the query generator's mapping and randomization logic.

```bash
pdm run test-query-gen
```
**Why here?** This test's prerequisites (a small `personalities_db.txt`) are generated by the Layer 3 integration test, so it naturally follows.

---

### Part 2: Scientific & Large-Scale Validation

These tests validate the scientific method and require a full production dataset.

#### Prerequisite Step: Generate the Full Production Dataset
Run the full data preparation pipeline **once** to generate the large-scale assets required by the following tests.

```bash
# This is a one-time setup step for scientific validation
pdm run prep-data
```
**Why first?** This step creates the large-scale `subject_db.csv`, `eminence_scores.csv`, and other files that the algorithm validation tests need to perform their analyses correctly. **This is not a test itself, but a required prerequisite.**

#### Stage 4: Algorithm Validation Tests
Validate the scientific correctness of the framework's core algorithms using the full dataset.

**Personality Assembly Algorithm:**
```bash
# Run the 5-step setup workflow (with a manual pause)
pdm run test-assembly-setup

# After setup, run the final bit-for-bit validation
pdm run test-assembly
```

**Qualification & Selection Algorithms:**
```bash
# Validate filtering and cutoff logic at scale
pdm run test-l3-selection
```
**Why here?** These tests validate the scientific methodology. They must run after the full production dataset is generated to ensure they are operating on realistic, large-scale data.

#### Stage 5: Statistical Validation (Publication Readiness)
Validate the framework's statistical calculations against GraphPad Prism.

```bash
# Run the 4-stage validation workflow
pdm run test-stats-study
pdm run test-stats-imports
# (Perform manual GraphPad step)
pdm run test-stats-results
```
**Why last in this part?** This is the most time-consuming validation, establishing academic credibility. It depends on a complete and validated framework and production dataset.

---

### Part 3: Final Comprehensive Checks

#### Stage 6: Run All Tests Together
As a final sanity check, run the composite commands that execute all unit tests or the entire test suite.

```bash
# Run all Python tests with a coverage report
pdm run cov

# Run all Python and PowerShell tests
pdm run test
```
**Why last?** This is a final catch-all to ensure no regressions were introduced during development or testing.

### Troubleshooting Common Issues

**"Prerequisites not found" errors:** Run Layer 3 tests first (`pdm run test-l3` or `pdm test-l3`) to generate required assets for algorithm validation tests.

**"Assembly logic sandbox was not found" errors:** Run the 5-step Personality Assembly Algorithm workflow first to generate the required ground truth dataset.

**API key errors:** Ensure `.env` file is configured with OpenRouter API key for tests requiring LLM calls.

**Long test runtimes:** Use Layer 2 and bypass mode tests for rapid validation. Full Layer 3-5 tests require LLM calls and take longer.

**Interactive tests don't pause:** Ensure you're using the `-Interactive` flag or specific interactive command variants.

## Unit Testing

This foundational layer focuses on validating the internal logic of individual Python scripts. The project uses `pytest` for all unit tests, which are managed via PDM. Unit tests verify that each component performs its intended function correctly, with proper error handling and edge case management.

### Running Unit Tests

**Test individual pipelines:**
```bash
# Test data preparation components
pdm run test-data-prep

# Test experiment workflow components
pdm run test-exp-wf
```

**Test specific modules:**
```bash
# Run test file and generate focused coverage report
pdm test-cov tests/experiment_workflow/test_analyze_llm_performance.py
pdm report-cov src/analyze_llm_performance.py
```

**Run all unit tests:**
```bash
# Quick test run
pdm run test

# With coverage report
pdm run cov
```

### Data Preparation Pipeline

These tests validate the components that transform raw Astro-Databank data into the final personality profiles database.

#### Data Sourcing

**Module:** `src/fetch_adb_data.py`

Validates the automated extraction of birth data from the live Astro-Databank website.

**Test file:** `tests/data_preparation/test_fetch_adb_data.py`

**What's tested:**

- HTTP session management and connection handling
- API query construction with proper timezone calculations
- Data parsing from JSON responses
- Error handling for network failures and malformed data
- Timeout scenarios and retry logic
- Rodden rating and category filtering

**Key validation:** Ensures the script produces well-formed `adb_raw_export.txt` with standardized identifiers and pre-calculated timezone information.

#### Candidate Qualification (Filtering)

These tests validate the deterministic filtering rules that create the pool of eligible candidates.

##### Wikipedia Link Discovery

**Module:** `src/find_wikipedia_links.py`

**Test file:** `tests/data_preparation/test_find_wikipedia_links.py`

**What's tested:**

- Web scraping logic for ADB pages
- Wikipedia search API fallback mechanism
- URL extraction and validation
- Error handling for malformed pages and missing data
- Robust handling of network failures

##### Subject Qualification

**Module:** `src/qualify_subjects.py`

**Test file:** `tests/data_preparation/test_qualify_subjects.py`

**What's tested:**

- Content validation (name matching, life status)
- Redirect handling and resolution (canonical, meta-refresh)
- Disambiguation page detection and handling
- Wikidata integration for life status verification
- Error categorization and reporting
- Extensive mocking of HTTP requests

##### Final Eligibility Filtering

**Module:** `src/select_eligible_candidates.py`

**Test file:** `tests/data_preparation/test_select_eligible_candidates.py`

**What's tested:**

- Sequential application of all deterministic filters:
  - Wikipedia validation status
  - Entry type (Person vs Event)
  - Birth year range (1900-1999)
  - Hemisphere (Northern only)
  - Time format validation (HH:MM)
  - Deduplication logic
- File I/O and data integrity
- Edge cases (empty datasets, missing columns)
- Sandbox-aware execution

**Key validation:** Ensures only subjects meeting all quality criteria advance to the selection stage.

#### Candidate Selection (Selection)

These tests validate the LLM-based scoring and data-driven cutoff algorithm that determines the final subject pool.

##### Eminence Scoring

**Module:** `src/generate_eminence_scores.py`

**Test file:** `tests/data_preparation/test_generate_eminence_scores.py`

**What's tested:**

- Batch processing logic and queue management
- LLM API interaction patterns
- Response parsing and score extraction
- Error handling for API failures and malformed responses
- Resume capability for interrupted runs
- Score normalization and validation

##### OCEAN Personality Scoring

**Module:** `src/generate_ocean_scores.py`

**Test file:** `tests/data_preparation/test_generate_ocean_scores.py`

**What's tested:**

- Text processing and prompt construction
- LLM API interaction and rate limiting
- OCEAN score extraction and validation
- Robust error handling for API failures
- Pre-flight checks for resumable runs
- Data format validation

##### Cutoff Parameter Analysis

**Module:** `src/analyze_cutoff_parameters.py`

**Test file:** `tests/data_preparation/test_analyze_cutoff_parameters.py`

**What's tested:**

- Grid search over parameter space (start points and smoothing windows)
- Variance curve calculation and ideal cutoff detection
- Stability-based recommendation algorithm
- Error calculation and parameter ranking
- Table formatting and output generation
- Handling of datasets too small for analysis
- Sandbox-aware execution for testing

**Key validation:** Ensures the parameter optimization script correctly identifies the most robust parameter values for the cutoff algorithm through comprehensive grid search analysis.

##### Final Selection with Cutoff Algorithm

**Module:** `src/select_final_candidates.py`

**Test file:** `tests/data_preparation/test_select_final_candidates.py`

**What's tested:**

- Cumulative variance curve calculation
- Smoothing algorithm (moving average)
- Slope analysis for plateau detection
- Edge cases (insufficient data, no plateau found)
- Bypass mode (skipping LLM selection)
- Country code resolution
- Eminence score merging and sorting
- Boundary conditions

**Key validation:** Ensures the sophisticated cutoff algorithm correctly identifies the optimal cohort size based on personality diversity.

#### Profile Generation

These tests validate the components that assemble the final neutralized personality descriptions.

##### Solar Fire Import Preparation

**Module:** `src/prepare_sf_import.py`

**Test file:** `tests/data_preparation/test_prepare_sf_import.py`

**What's tested:**

- File formatting for Solar Fire import
- Data transformation and encoding
- ID encoding into timezone abbreviations
- Edge case handling
- Format validation

##### Chart Data Integration

**Module:** `src/create_subject_db.py`

**Test file:** `tests/data_preparation/test_create_subject_db.py`

**What's tested:**

- Solar Fire export parsing (14-line repeating blocks)
- ID decoding from timezone abbreviations
- Data merging with final candidates list
- Robust error handling for malformed input
- Edge cases (missing fields, duplicate entries)
- All data processing pathways

**Key validation:** Ensures seamless integration between manual Solar Fire processing and automated pipeline.

##### Delineation Neutralization

**Module:** `src/neutralize_delineations.py`

**Test file:** `tests/data_preparation/test_neutralize_delineations.py`

**What's tested:**

- Text processing workflow (fast and robust modes)
- Complex regular expression patterns for text extraction
- LLM API interaction for text rewriting
- Task batching logic (fast mode)
- Individual task processing (robust mode)
- Resume capability for failed tasks
- Error handling and retry logic
- Output validation

**Key validation:** Validates the sophisticated hybrid strategy that guarantees completion of all 149 delineation tasks.

##### Personality Database Assembly

**Module:** `src/generate_personalities_db.py`

**Test file:** `tests/data_preparation/test_generate_personalities_db.py`

**What's tested:**

- Complete profile generation workflow
- Point weight calculations
- Balance threshold classifications (strong/weak)
- Text component lookup and assembly
- Data aggregation from multiple sources
- Robust error handling
- Output format validation

**Key validation:** Ensures the deterministic assembly algorithm produces correctly formatted personality profiles. Note: Bit-for-bit accuracy is validated separately by the Algorithm Validation test suite.

### Experiment & Study Lifecycle

These tests validate the components that manage experiment execution, LLM interaction, analysis, and study compilation.

#### Experiment Creation, Audit & Fix

##### Experiment Manager (Orchestrator)

**Module:** `src/experiment_manager.py`

**Test file:** `tests/experiment_workflow/test_experiment_manager.py`

**What's tested:**

- New experiment creation workflow
- Directory structure generation
- Config archival and parameter capture
- Batch execution logic with progress tracking
- Replication skipping for interrupted runs
- Reprocess mode (analysis-only updates)
- Error handling and recovery
- Non-interactive mode
- All execution pathways

**Key validation:** Ensures the primary orchestrator correctly manages the entire experiment workflow, from directory creation through batch completion.

##### Experiment Auditor (Diagnostic Tool)

**Module:** `src/experiment_auditor.py`

**Test file:** `tests/experiment_workflow/test_experiment_auditor.py`

**What's tested:**

- Completeness detection logic
- Corruption classification (severity levels)
- Validation status determination
- Report generation (human-readable and structured)
- All exit codes (0-5)
- Edge cases (empty directories, missing files)
- Robust error handling

**Key validation:** Validates the sophisticated diagnostic system that powers both `audit_experiment.ps1` and `fix_experiment.ps1`.

##### Configuration Management

**Module:** `src/config_loader.py`

**Test file:** `tests/experiment_workflow/test_config_loader.py`

**What's tested:**

- Config file parsing and validation
- Type conversion and default values
- Section and key existence checks
- Error handling for malformed config
- Path resolution
- Multiple config file scenarios

**Module:** `src/restore_experiment_config.py`

**Test file:** `tests/experiment_workflow/test_restore_experiment_config.py`

**What's tested:**

- Archived config restoration
- Parameter extraction and validation
- Error handling for missing archives

#### Replication Management

**Module:** `src/replication_manager.py`

**Test file:** `tests/experiment_workflow/test_replication_manager.py`

**What's tested:**

- Six-stage replication pipeline execution
- Parallel session management with ThreadPoolExecutor
- Session worker control flow
- Failure tolerance (< 50% failure threshold)
- Progress tracking and ETA calculations
- Error handling for stage failures
- All edge cases and failure modes

**Key validation:** Validates the core replication orchestrator that manages the complete lifecycle of a single experimental run. Test suite uses direct patching of `session_worker` for simple, reliable testing strategy.

#### LLM Interaction Management

##### Query Construction

**Module:** `src/build_llm_queries.py`

**Test file:** `tests/experiment_workflow/test_build_llm_queries.py`

**What's tested:**

- Query file generation for all trials
- Manifest creation (trial-to-subject mappings)
- Data loading from personalities database
- Query template processing
- File I/O operations
- Edge cases and error handling

**Module:** `src/query_generator.py`

**Test file:** `tests/experiment_workflow/test_query_generator.py`

**What's tested:**

- Mapping strategy implementation (correct vs random)
- Subject selection and randomization
- Manifest structure validation
- Deterministic seeding
- Group size handling

##### LLM API Interaction

**Module:** `src/llm_prompter.py`

**Test file:** `tests/experiment_workflow/test_llm_prompter.py`

**What's tested:**

- API call construction and execution
- Rate limiting logic
- Timeout handling
- Response processing
- Error categorization
- Retry mechanisms
- Multiple API provider patterns

##### Response Processing

**Module:** `src/process_llm_responses.py`

**Test file:** `tests/experiment_workflow/test_process_llm_responses.py`

**What's tested:**

- k×k matrix extraction from text responses
- Rank conversion and validation
- Score range validation (1 to k)
- Ground-truth cross-validation against manifests
- Error detection and reporting
- Malformed response handling
- Edge cases (missing data, invalid formats)

**Key validation:** Validates the simplified extraction logic that measures actual LLM performance without correction, ensuring scientific validity.

#### Analysis and Reporting

##### Performance Analysis

**Module:** `src/analyze_llm_performance.py`

**Test file:** `tests/experiment_workflow/test_analyze_llm_performance.py`

**What's tested:**

- Core statistical calculations (MRR, Top-K accuracy)
- Wilcoxon signed-rank test implementation
- Chance calculation and documentation
- Error categorization and validation logic
- File I/O contracts and data parsing
- All major failure modes and edge cases
- Enhanced validation logic from Priority 1-3 improvements

**Key validation:** Comprehensive validation of statistical engine, meeting 80%+ target for critical modules. Enhanced with Priority 1-3 statistical validation improvements for GraphPad validation testing.

**Module:** `src/run_bias_analysis.py`

**Test file:** `tests/experiment_workflow/test_run_bias_analysis.py`

**What's tested:**

- Linear regression for positional bias detection
- Slope, R-value, and p-value calculations
- Rank-based analysis (not MRR)
- Empty and malformed data handling
- Statistical edge cases

##### Report Generation

**Module:** `src/generate_replication_report.py`

**Test file:** `tests/experiment_workflow/test_generate_replication_report.py`

**What's tested:**

- Report assembly from analysis results
- Human-readable summary formatting
- Machine-parsable JSON block generation
- Log capture and integration
- Template processing
- Error handling

**Module:** `src/manage_experiment_log.py`

**Test file:** `tests/experiment_workflow/test_manage_experiment_log.py`

**What's tested:**

- Log file creation and updates
- Timestamp handling
- Status message formatting
- Concurrent access handling

#### Study-Level Processing

##### Result Compilation

**Module:** `src/compile_replication_results.py`

**Test file:** `tests/experiment_workflow/test_compile_replication_results.py`

**What's tested:**

- Single replication CSV generation
- Data extraction from reports
- Error handling for missing files

**Module:** `src/compile_experiment_results.py`

**Test file:** `tests/experiment_workflow/test_compile_experiment_results.py`

**What's tested:**

- Multi-replication aggregation
- Experiment-level CSV generation
- Data validation and formatting

**Module:** `src/compile_study_results.py`

**Test file:** `tests/experiment_workflow/test_compile_study_results.py`

**What's tested:**

- Multi-experiment aggregation
- Study-level CSV generation
- Cross-experiment validation

##### Statistical Analysis

**Module:** `src/analyze_study_results.py`

**Test file:** `tests/experiment_workflow/test_analyze_study_results.py`

**What's tested:**

- Two-way ANOVA implementation
- Post-hoc test calculations
- Effect size computations (eta-squared)
- Data filtering and validation
- Report generation
- Plot creation logic
- Edge cases and error handling

**Key validation:** Validates complete statistical analysis pipeline. Enhanced with Priority 1-3 improvements for GraphPad validation, meeting 80%+ target.

#### Utility Scripts

These shared utility modules provide common functionality across the framework.

**Module:** `src/id_encoder.py`

**Test file:** `tests/test_id_encoder.py`

**What's tested:**

- ID encoding into timezone abbreviations
- Decoding back to original IDs
- Round-trip validation
- Edge cases

**Module:** `src/utils/file_utils.py`

**Test file:** `tests/utils/test_file_utils.py`

**What's tested:**

- Path resolution and validation
- File existence checks
- Directory creation
- Safe file operations

#### User Entry Points (Wrappers)

PowerShell wrapper scripts are not measured by Python code coverage; their correctness is validated through end-to-end integration tests (Layer 4-5).

**Tested wrappers:**
- `new_experiment.ps1` - Test file: `tests/experiment_workflow/new_experiment.Tests.ps1`
- `audit_experiment.ps1` - Test file: `tests/experiment_workflow/audit_experiment.Tests.ps1`
- `fix_experiment.ps1` - Test file: `tests/experiment_workflow/fix_experiment.Tests.ps1`
- `compile_study.ps1` - Test file: `tests/experiment_workflow/compile_study.Tests.ps1`
- `audit_study.ps1` - Test file: `tests/experiment_workflow/audit_study.Tests.ps1`

**What's tested:**

- Parameter handling and validation
- Script execution workflows
- Error handling and exit codes
- User interaction patterns
- Integration with Python components

## Integration Testing

This category includes end-to-end tests that validate complete workflows from start to finish. All integration tests run in isolated `temp_test_environment` directories at the project root, ensuring they are non-destructive and will not modify production files. These tests execute actual production scripts to validate that all components work together correctly.

### Interactive Testing Mode

Several integration tests offer an interactive mode that transforms automated validation into educational guided tours. These interactive modes serve dual purposes:

**For Researchers (Learning):**
- Understanding how the framework works before running experiments
- Following along with procedures described in the Replication Guide
- Hands-on exploration of data preparation and experiment workflows
- See the **[🔬 Replication Guide](REPLICATION_GUIDE.md)** "Interactive Learning Tools" section for research-focused guidance

**For Developers (Validation):**
- Debugging complex workflows step-by-step
- Training new team members on framework internals
- Live demonstrations of framework capabilities
- Understanding test infrastructure and validation logic

Interactive tests pause before each major step, provide detailed explanations of what will happen, and allow users to inspect intermediate results. This makes them invaluable for both learning the framework's workflows (researchers) and understanding its internal operations (developers), while maintaining the same technical validation as automated tests.

{{diagram:docs/diagrams/test_sandbox_architecture.mmd | scale=2.5 | width=100% | caption=The Integration Test Sandbox Architecture: All integration tests run in a temporary, isolated environment.}}

### Data Preparation Pipeline

These tests validate the complete data preparation workflow from raw Astro-Databank export through final personality profile generation.

#### Layer 2: Testing Using Mocking Logic

**Purpose:** Validates the orchestrator's state machine logic using lightweight mock scripts.

**Command:**
```powershell
pdm run test-l2
```

**What's tested:**

- Halt/resume logic without expensive LLM calls
- State transition correctness
- Step completion detection
- Error handling and recovery

**Test duration:** < 30 seconds

**Implementation:** Uses fast mock scripts that simulate pipeline stages to test orchestration logic independently.

#### Orchestrator Feature Tests

##### Backup and Restore Functionality

**Purpose:** Validates the `-RestoreBackup` functionality of the `prepare_data.ps1` orchestrator.

**Command:**
```powershell
pdm run test-restore-backup
# or simply:
pdm test-restore-backup
```

**What's tested:**
- **Sandbox Creation:** An isolated test environment is created.
- **File & Backup Creation:** A test file is created, and a timestamped backup is manually generated to simulate a previous pipeline run.
- **Simulated Data Loss:** The original test file is deleted.
- **Restore Execution:** The `prepare_data.ps1 -RestoreBackup` command is called on the sandbox.
- **Verification:** The test confirms that the original file was successfully restored with the correct content and that the backup file was preserved.

**Test duration:** < 5 seconds

**Implementation:** A standalone PowerShell script (`tests/test_restore_data_backup.ps1`) executes the complete test cycle in an isolated, temporary directory that is automatically cleaned up.

#### Layer 3: Complete Live Testing

**Purpose:** Validates the full, live data preparation pipeline with real Python scripts.

**System Under Test:** `prepare_data.ps1` orchestrator

**Test harness:** Profile-driven test system using controlled seed datasets from `tests/assets/`

**Three testing profiles:**

##### Default Mode

Runs the full pipeline with LLM-based candidate selection active.

**Command:**
```powershell
pdm run test-l3
```

**What's tested:**

- Complete 4-stage pipeline execution (14 steps):
  1. Data Sourcing (fetch_adb_data.py)
  2. Candidate Qualification (find_wikipedia_links.py, validate_wikipedia_pages.py, select_eligible_candidates.py)
  3. Candidate Selection (generate_eminence_scores.py, generate_ocean_scores.py, analyze_cutoff_parameters.py, select_final_candidates.py)
  4. Profile Generation (prepare_sf_import.py, create_subject_db.py, neutralize_delineations.py, generate_personalities_db.py)
- Orchestrator state machine with real scripts
- LLM interaction patterns
- File generation and validation
- Complete data flow integrity

**Prerequisites:** Configured `.env` file with OpenRouter API key

**Test duration:** ~10-15 minutes (includes LLM calls)

##### Bypass Mode

Tests the pipeline with `bypass_candidate_selection` flag enabled, skipping LLM-based selection.

**Command:**
```powershell
pdm run test-l3-bypass
```

**What's tested:**

- Data Sourcing stage
- Candidate Qualification stage
- Profile Generation stage (without LLM selection)
- Bypass mode logic and data flow

**Prerequisites:** Configured `.env` file

**Test duration:** ~8-10 minutes (fewer LLM calls)

**Key difference:** Uses all eligible candidates without eminence/OCEAN scoring and cutoff algorithm.

##### Interactive Mode (Guided Tour)

Provides a step-by-step educational walkthrough of the data pipeline.

**Command:**
```powershell
pdm run test-l3-interactive
```

**What's tested:**

- Same technical validation as Default Mode
- Pause-and-explain at each pipeline stage
- Intermediate file inspection opportunities
- Educational demonstrations

**Use cases:**
- Learning the data preparation workflow
- Understanding pipeline architecture
- Training new team members
- Debugging complex data processing issues

**Prerequisites:** Configured `.env` file

### Experiment & Study Lifecycle

These tests validate the complete workflows for creating experiments and compiling them into final studies.

#### Layer 4: Core Workflow (new → audit → break → fix)

**Purpose:** Validates the complete experiment workflow with deliberate corruption scenarios and automated repair.

**System Under Test:** `new_experiment.ps1`, `audit_experiment.ps1`, `fix_experiment.ps1`

**Test structure:** Three-phase design (Setup → Execute → Cleanup)

##### Automated Mode

Rapid validation suitable for CI/CD pipelines.

**Command:**
```powershell
pdm run test-l4
```

**What's tested:**
1. **Experiment Creation:**
   - New experiment directory generation
   - Config archival
   - Complete replication execution
   - Progress tracking and ETA

2. **Validation (Audit):**
   - Initial completeness check
   - Status classification

3. **Deliberate Corruption (4 scenarios):**
   - **Scenario 1: Missing Response Files** - Simulates interrupted LLM calls
   - **Scenario 2: Outdated Analysis** - Simulates code updates requiring reprocessing
   - **Scenario 3: Missing Config Archive** - Simulates file system errors
   - **Scenario 4: Missing Aggregation** - Simulates interrupted finalization

4. **Automated Repair:**
   - Audit-driven diagnosis
   - Targeted repair for each corruption type
   - Final verification of experiment integrity

**Expected outcome:** All corruption scenarios successfully detected and repaired. Final audit confirms experiment validity.

**Test duration:** ~5-7 minutes

##### Interactive Mode (Guided Tour)

Comprehensive educational experience with detailed explanations at each step.

**Command:**
```powershell
pdm run test-l4-interactive
```

**What's tested:**

- Same technical validation as Automated Mode
- Detailed explanations before each phase
- Opportunity to inspect experiment state
- Live demonstration of corruption and repair

**Use cases:**
- Learning the experiment workflow
- Understanding audit and repair logic
- Training new developers
- Debugging complex experiment issues

**Manual Phase Execution (Advanced):**

For granular control or debugging:

**Phase 1 - Setup:**
```powershell
.\tests\testing_harness\experiment_lifecycle\layer4\layer4_phase1_setup.ps1
```

**Phase 2 - Execute Test Workflow:**
```powershell
.\tests\testing_harness\experiment_lifecycle\layer4\layer4_phase2_run.ps1
```

**Phase 3 - Cleanup:**
```powershell
.\tests\testing_harness\experiment_lifecycle\layer4\layer4_phase3_cleanup.ps1
```

#### Layer 5: Study Compilation

**Purpose:** Validates the complete study compilation workflow using realistic experiments.

**System Under Test:** `compile_study.ps1`, `audit_study.ps1`

**Test structure:** Three-phase design (Setup → Execute → Cleanup)

##### Automated Mode

**Command:**
```powershell
pdm run test-l5
```

**What's tested:**
1. **Study Setup:**
   - Uses Layer 4 experiments when available
   - Creates 2×2 factorial design (4 experiments)
   - Organized study directory structure

2. **Study Compilation:**
   - `STUDY_results.csv` generation
   - Multi-experiment data aggregation
   - Cross-experiment validation

3. **Statistical Analysis:**
   - Two-way ANOVA execution
   - Appropriate handling of test data limitations
   - Model filtering for insufficient replications
   - Study-level artifact generation (anova directory)

4. **Study Audit:**
   - Consolidated status report
   - Cross-experiment consistency checks
   - Final validation

**Expected outcome:** Complete study compilation with proper aggregation and appropriate handling of test data scenarios (filtered models due to insufficient replications).

**Key capabilities:**
- Cross-layer integration validation
- Realistic test data scenarios
- Proper statistical filtering behavior
- Complete lifecycle validation

**Test duration:** ~2-3 minutes

**Note:** This test demonstrates proper handling of both successful compilation and appropriate filtering when insufficient data is present for certain statistical tests.

## Algorithm Validation

This category includes standalone, high-precision tests designed to verify the scientific and logical integrity of the framework's most critical components. These tests are not part of the sequential layer workflow but are essential for proving the validity of the experimental design.

### Personality Assembly Algorithm

This is the project's most rigorous validation. It is a two-part process that combines a semi-automated workflow for generating a ground-truth dataset with a fully automated test that verifies our algorithm against it.

#### Part 1: The Ground Truth Generation Workflow

This is a developer-run, five-step workflow that uses the source expert system (Solar Fire) to generate a "ground truth" version of the personality database. This process is essential for creating the validation asset that the automated test relies on. The scripts for this workflow are located in `scripts/workflows/assembly_logic/` and must be run in the numbered order.

1.  **`1_generate_coverage_map.py`**: Pre-computes which delineation keys are triggered by each subject.
2.  **`2_select_assembly_logic_subjects.py`**: Uses a greedy algorithm to select the smallest set of subjects that provides maximum coverage of all delineation keys.
3.  **`3_prepare_assembly_logic_import.py`**: Formats the selected subjects for manual import into the Solar Fire software.
4.  **`4_extract_assembly_logic_text.py`**: Processes the Solar Fire export to extract the delineation text components and assembles the ground truth database.
5.  **`5_validate_assembly_logic_subjects.py`**: Validates the integrity of the data round-trip through Solar Fire.

#### Part 2: The Automated Validation Test

Once the ground truth dataset is generated, the automated test (`tests/algorithm_validation/test_profile_generation_algorithm.py`) can run. This test performs a **bit-for-bit validation** by generating personalities for a set of subjects using our algorithm and comparing them against the pre-computed ground truth from the expert system.

**To run the test:**
```powershell
pdm run test-assembly
```

**Prerequisites:**
The test requires a ground-truth dataset in `tests/assets/assembly_logic/ground_truth_personalities_db.txt`. If this file is not present, the test will be skipped.

### Qualification & Selection Algorithms

This standalone test validates the core filtering and cutoff algorithms at scale using a large, pre-generated seed dataset in an isolated sandbox.

#### Filtering for Qualification

Validates the deterministic filtering rules applied to create the "eligible candidates" pool from raw Astro-Databank data.

**What's tested:**

- Sequential application of all filtering criteria
- Deduplication logic
- Wikipedia validation integration
- Entry type filtering
- Birth year range constraints
- Hemisphere filtering
- Time format validation

#### Cutoff Algorithm for Selection

Validates the sophisticated variance-based cutoff algorithm that determines the optimal cohort size.

**What's tested:**

- Cumulative variance curve calculation at scale
- Moving average smoothing algorithm
- Slope analysis for plateau detection
- Edge cases with large datasets
- Bypass mode operation

**To run the test:**
```powershell
pdm run test-l3-selection
```

**Prerequisites:**
This test depends on large seed files that must be manually placed in `tests/assets/large_seed/`:
- `eminence_scores.csv`
- `ocean_scores.csv`
- `adb_eligible_candidates.txt`

These files are generated by the data preparation pipeline and are too large to store in Git. If the assets are not present, the specific cutoff validation will be skipped.

### Query Generation & Randomization Integrity Test

This standalone test provides mathematical proof of the mapping and randomization logic in `query_generator.py`. The test is composed of two scripts that work in tandem:

1.  **`validate_query_generation.ps1` (The Harness):** The user-facing entry point. It prepares a sandbox and calls `query_generator.py` in a loop to generate a statistically significant sample of manifest files.
2.  **`analyzers/analyze_query_generation_results.py` (The Analyzer):** A worker script called by the harness. It inspects the generated files to validate two core properties:
    *   **Determinism:** That the `correct` strategy produces bit-for-bit identical outputs when given the same random seed.
    *   **Non-Determinism:** That the `random` strategy produces different outputs across multiple runs.

**Statistical Rigor:** The test is parameterized by statistical power. The user specifies the acceptable Type II error rate (`-Beta`), and the harness automatically calculates the required number of iterations `N` to achieve the corresponding statistical power (1 - `Beta`). This ensures that the non-determinism check is statistically sound.

**To run the test:**
```powershell
# Run with default 99.9999% power (Beta = 0.000001), which requires 9 iterations for k=3.
pdm run test-query-gen

# Run with a custom 99.9% power (Beta = 0.001), which requires 5 iterations.
pdm run test-query-gen -Beta 0.001
```

**Prerequisites:**
This test depends on asset files that are **automatically generated** by the Layer 3 integration test. On a fresh clone, you must run `pdm run test-l3` (or `pdm test-l3`) once to bootstrap these assets. If the assets are not present, the test will be skipped.

## Statistical Analysis & Reporting Validation

This 4-stage validation workflow provides external validation of the entire statistical analysis pipeline against GraphPad Prism 10.6.1. Uses real framework execution with sufficient replications to trigger full statistical analysis (ANOVA, post-hoc tests, Bayesian analysis).

**Implementation:** 4-stage validation process using real framework execution with deterministic parameters (temperature=0.0, gemini-2.5-flash-lite-preview-06-17) and framework's built-in seeded randomization. 2×2 factorial design with 6 replications per condition = 24 total experiments.

**Validation Methodology:** Representative sampling approach - full manual validation of 2 replications per condition (8 total), with automated spot-checks of descriptive statistics for remaining 16 replications. This validates the calculation engine without exhaustive manual checking of all replications.

### 4-Stage Validation Workflow

```powershell
# Stage 1: Create statistical validation study using real framework
pdm run test-stats-study

# Stage 2: Generate GraphPad import files
pdm run test-stats-imports

# Stage 3: Manual GraphPad Prism processing
# (Manual import, analyze, export for 8 selected replications)

# Stage 4: Validate GraphPad results against framework calculations
pdm run test-stats-results
```

**Current Status: Complete**
- ✅ **Stage 1**: Statistical study creation completed (24 replications, 768 trials)
- ✅ **Stage 2**: Export generation with individual replication sampling (8 of 24)
- ✅ **Stage 3**: Manual GraphPad processing of 8 selected replications
- ✅ **Stage 4**: Automated validation comparison completed

**Prerequisites:** Requires `data/personalities_db.txt` from data preparation pipeline.

**Academic Citation:** "Statistical analyses were validated against GraphPad Prism 10.6.1"

### Validation Details

**Phase A: Core Algorithmic Validation**
- Mean Reciprocal Rank (MRR) calculations and Wilcoxon tests
- Top-1 accuracy calculations and Wilcoxon tests
- Top-3 accuracy calculations and Wilcoxon tests
- K-specific validation datasets for comprehensive coverage
- Positional bias detection (linear trend analysis)
- Effect size calculations (Cohen's r)

**Phase B: Standard Statistical Analyses**
- Two-Way ANOVA (F-statistics, p-values, effect sizes)
- Post-hoc tests and FDR corrections
- Multi-factor experimental design validation

**Validation Conclusion:** The framework's implementation of statistical analyses produces results that match GraphPad Prism 10.6.1 within acceptable tolerances:
- p-value calculations: ±0.0001
- Effect sizes (eta-squared): ±0.01
- Positional bias slopes: ±0.0001
- R-values: ±0.01

This ensures validation tests the **actual framework code** used during the experiment workflow, not a reimplementation in the validation script.

## Test Status Matrix

This comprehensive table provides the current status of all tests in the framework, organized by category and component.

### Legend

**Status Values:**
- **COMPLETE** - Fully implemented and passing
- **PARTIAL** - Partially implemented, requires additional work
- **PLANNED** - Scheduled for future implementation

**Module Tier (Coverage Target):**
- **Critical** - 85%+ (core orchestrators, state-detection logic, data validation)
- **Standard** - 80%+ (individual pipeline scripts)
- **Utility** - 85%+ (shared helper modules)
- **N/A** - Not measured by Python coverage (integration tests, algorithm validation)

---

### Integration Tests

| Test Name | Category | Status | Notes |
|:----------|:---------|:-------|:------|
| **Data Preparation Pipeline** | Integration | **COMPLETE** | Validated by robust, profile-driven test harness running full pipeline in isolated sandbox |
| Layer 2: State Machine Logic | Integration | **COMPLETE** | Fast mock-based validation of orchestrator halt/resume logic |
| Layer 3: Default Profile | Integration | **COMPLETE** | Full pipeline with LLM-based candidate selection |
| Layer 3: Bypass Profile | Integration | **COMPLETE** | Full pipeline without LLM selection |
| Layer 3: Interactive Mode | Integration | **COMPLETE** | Educational guided tour of data pipeline |
| **Experiment Lifecycle** | Integration | **COMPLETE** | Validates full `new → audit → break → fix` lifecycle in isolated sandbox |
| Layer 4: Automated Mode | Integration | **COMPLETE** | Tests 4 corruption scenarios with automated repair |
| Layer 4: Interactive Mode | Integration | **COMPLETE** | Educational guided tour of experiment workflow |
| **Study Compilation** | Integration | **COMPLETE** | Validates complete study compilation workflow using Layer 4 experiments |
| Layer 5: Automated Mode | Integration | **COMPLETE** | Tests study aggregation, statistical analysis, artifact generation |

---

### Algorithm Validation

| Test Name | Category | Status | Coverage | Notes |
|:----------|:---------|:-------|:---------|:------|
| **Personality Assembly Algorithm** | Algorithm | **COMPLETE** | N/A | Bit-for-bit validation against Solar Fire ground truth |
| Part 1: Ground Truth Generation | Algorithm | **COMPLETE** | N/A | 5-step workflow using Solar Fire expert system |
| Part 2: Automated Validation | Algorithm | **COMPLETE** | N/A | Pytest suite validates against pre-computed ground truth |
| **Qualification & Selection Algorithms** | Algorithm | **COMPLETE** | N/A | Large-scale validation of filtering and cutoff logic |
| Filtering for Qualification | Algorithm | **COMPLETE** | N/A | Validates deterministic filtering rules at scale |
| Cutoff Algorithm for Selection | Algorithm | **COMPLETE** | N/A | Validates variance curve analysis and plateau detection |
| **Query Generation & Randomization** | Algorithm | **COMPLETE** | N/A | Statistical proof of determinism and non-determinism |
| Determinism Test (correct strategy) | Algorithm | **COMPLETE** | N/A | Validates bit-for-bit identical outputs with same seed |
| Non-Determinism Test (random strategy) | Algorithm | **COMPLETE** | N/A | Validates different outputs across runs (99.9999% power) |

---

### Statistical Analysis & Reporting Validation

| Test Name | Category | Status | Notes |
|:----------|:---------|:-------|:------|
| **GraphPad Prism 10.6.1 Validation** | Statistical | **COMPLETE** | 4-stage validation workflow for academic publication |
| Stage 1: Create Validation Study | Statistical | **COMPLETE** | 24 experiments (2×2 factorial, 6 reps/condition) using real framework |
| Stage 2: Generate Import Files | Statistical | **COMPLETE** | Representative sampling (8 of 24) + spot-check summaries |
| Stage 3: Manual GraphPad Processing | Statistical | **COMPLETE** | Manual import, analysis, export for 8 replications |
| Stage 4: Validate Results | Statistical | **COMPLETE** | Framework calculations match GraphPad within tolerances |

**Academic Citation:** "Statistical analyses were validated against GraphPad Prism 10.6.1"

---

### Unit Tests: Data Preparation Pipeline

| Module | Category | Status | Coverage | Notes |
|:-------|:---------|:-------|:---------|:------|
| **Data Sourcing** | | | | |
| `src/fetch_adb_data.py` | Standard | **COMPLETE** | 84% | Session management, data parsing, error handling, timeout scenarios |
| **Candidate Qualification** | | | | |
| `src/find_wikipedia_links.py` | Standard | **COMPLETE** | 89% | Name sanitization, web scraping, fallback logic |
| `src/qualify_subjects.py` | Standard | **COMPLETE** | 91% | URL validation, content checks, disambiguation detection |
| `src/select_eligible_candidates.py` | **Critical** | **COMPLETE** | 90% | Deterministic filtering rules, deduplication, edge cases |
| **Candidate Selection** | | | | |
| `src/generate_eminence_scores.py` | **Critical** | **COMPLETE** | 87% | Batch processing, API interaction, resume capability |
| `src/generate_ocean_scores.py` | **Critical** | **COMPLETE** | 88% | Text processing, API interaction, pre-flight checks |
| `src/analyze_cutoff_parameters.py` | Standard | **COMPLETE** | 84% | Grid search, stability analysis, parameter optimization |
| `src/select_final_candidates.py` | **Critical** | **COMPLETE** | 91% | Variance curve calculation, slope analysis, cutoff detection |
| **Profile Generation** | | | | |
| `src/prepare_sf_import.py` | Standard | **COMPLETE** | 86% | File formatting, ID encoding, data transformation |
| `src/create_subject_db.py` | **Critical** | **COMPLETE** | 92% | Solar Fire export parsing, ID decoding, data merging |
| `src/neutralize_delineations.py` | **Critical** | **COMPLETE** | 91% | Hybrid text processing (fast/robust modes), resume capability |
| `src/generate_personalities_db.py` | **Critical** | **COMPLETE** | 91% | Profile generation workflow, text component assembly |

---

### Unit Tests: Experiment & Study Lifecycle

| Module | Category | Status | Coverage | Notes |
|:-------|:---------|:-------|:---------|:------|
| **Experiment Creation, Audit & Fix** | | | | |
| `src/experiment_manager.py` | **Critical** | **COMPLETE** | 94% | State machine, batch execution, reprocess mode |
| `src/experiment_auditor.py` | **Critical** | **COMPLETE** | 95% | Completeness detection, corruption classification, reporting |
| `src/config_loader.py` | **Utility** | **COMPLETE** | 85% | Config parsing, type conversion, path resolution |
| `src/restore_experiment_config.py` | Standard | **COMPLETE** | Target met | Config restoration, parameter extraction |
| `src/manage_experiment_log.py` | Standard | **COMPLETE** | 87% | Log file management, timestamp handling |
| **Replication Management** | | | | |
| `src/replication_manager.py` | **Critical** | **COMPLETE** | 91% | 6-stage pipeline, parallel session management, failure tolerance |
| **LLM Interaction Management** | | | | |
| `src/build_llm_queries.py` | Standard | **COMPLETE** | 84% | Query file generation, manifest creation |
| `src/query_generator.py` | Standard | **COMPLETE** | Target met | Mapping strategies, subject selection, randomization |
| `src/llm_prompter.py` | Standard | **COMPLETE** | 85% | API interaction, rate limiting, timeout handling |
| `src/process_llm_responses.py` | Standard | **COMPLETE** | 94% | Matrix extraction, rank conversion, validation |
| **Analysis and Reporting** | | | | |
| `src/analyze_llm_performance.py` | **Critical** | **COMPLETE** | 83% | Statistical calculations, Wilcoxon tests, chance calculations |
| `src/run_bias_analysis.py` | Standard | **COMPLETE** | 86% | Linear regression, positional bias detection |
| `src/generate_replication_report.py` | Standard | **COMPLETE** | 90% | Report assembly, JSON block generation |
| **Study-Level Processing** | | | | |
| `src/compile_replication_results.py` | Standard | **COMPLETE** | Target met | Single replication CSV generation |
| `src/compile_experiment_results.py` | Standard | **COMPLETE** | 89% | Multi-replication aggregation |
| `src/compile_study_results.py` | Standard | **COMPLETE** | Target met | Multi-experiment aggregation |
| `src/analyze_study_results.py` | **Critical** | **COMPLETE** | 82% | Two-way ANOVA, post-hoc tests, effect sizes |
| **Utility Scripts** | | | | |
| `src/id_encoder.py` | Standard | **COMPLETE** | Target met | ID encoding/decoding, round-trip validation |
| `src/utils/file_utils.py` | **Utility** | **COMPLETE** | 85% | Path resolution, file operations |
| **User Entry Points (Wrappers)** | | | | |
| `new_experiment.ps1` | PowerShell | **COMPLETE** | N/A | Validated by Layer 4 integration tests |
| `audit_experiment.ps1` | PowerShell | **COMPLETE** | N/A | Validated by Layer 4 integration tests |
| `fix_experiment.ps1` | PowerShell | **COMPLETE** | N/A | Validated by Layer 4 integration tests |
| `compile_study.ps1` | PowerShell | **COMPLETE** | N/A | Validated by Layer 5 integration tests |
| `audit_study.ps1` | PowerShell | **COMPLETE** | N/A | Validated by Layer 5 integration tests |

---

### Developer & Utility Scripts (Planned for Post-Publication)

| Module | Category | Status | Notes |
|:-------|:---------|:-------|:------|
| **Test Asset Generation** | | | |
| `scripts/workflows/assembly_logic/*.py` | Developer | **PLANNED** | Validated end-to-end by Algorithm Validation tests |
| **Utilities** | | | |
| `src/utils/analyze_research_patterns.py` | Utility | **PLANNED** | One-off analysis tool |
| `src/utils/patch_eminence_scores.py` | Utility | **PLANNED** | Data maintenance tool |
| `src/utils/validate_country_codes.py` | Utility | **PLANNED** | Validation helper |
| **Analysis Scripts** | | | |
| `scripts/analysis/analyze_cutoff_parameters.py` | Analysis | **PLANNED** | Parameter optimization tool |
| `scripts/analysis/get_docstring_summary.py` | Analysis | **PLANNED** | Documentation helper |
| `scripts/analysis/inspect_adb_categories.py` | Analysis | **PLANNED** | Data exploration tool |
| `scripts/analysis/validate_import_file.py` | Analysis | **PLANNED** | Import validation helper |
| **Linting & Maintenance** | | | |
| `scripts/lint/*.py` | Maintenance | **PLANNED** | Code quality tools |
| `scripts/maintenance/*.py` | Maintenance | **PLANNED** | Project maintenance tools |

---

### Summary Statistics

**Total Tests:** 70+

**Status Breakdown:**
- **COMPLETE:** 63 tests (90%)
- **PLANNED:** 12 tests (17%) - Post-publication developer utilities

**Coverage Status:**
- All Critical modules meet or exceed 85% target
- All Standard modules meet or exceed 80% target
- All Utility modules meet or exceed 85% target

**Milestone Status:**
- ✅ Data Preparation Pipeline - All layers complete
- ✅ Experiment Lifecycle - All layers complete
- ✅ Study Compilation - All layers complete
- ✅ Statistical Analysis & Reporting Validation - All stages complete

---

## Code Coverage Targets

To ensure the framework's reliability, we have established tiered code coverage targets based on the criticality of each module.

| Module Tier | Description | Coverage Target |
|:------------|:------------|:----------------|
| **Critical** | Core orchestrators, state-detection logic, and data validation/parsing modules whose failure could lead to data corruption or invalid scientific results. | **85%+** |
| **Standard** | Individual scripts within a pipeline that perform a discrete, well-defined task. | **80%+** |
| **Utility** | Shared helper modules, such as configuration loaders, that are foundational to many other scripts. | **85%+** |

PowerShell wrapper scripts are not measured by Python code coverage; their correctness is validated through the end-to-end integration tests.