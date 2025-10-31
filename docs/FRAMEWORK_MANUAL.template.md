# A Framework for Testing Complex Narrative Systems

**What Is This Framework?** The LLM Narrative Framework is an automated testing methodology that uses Large Language Models as pattern-detection engines to perform matching tasks between narrative personality descriptions and biographical profiles, determining whether systematic signals can be detected at rates significantly greater than chance.

This document is the **Framework Manual** for the project. It serves as the **technical reference** for the framework's architecture, providing specifications for data formats, API interfaces, configuration parameters, and system components. The manual is intended for developers, contributors, and researchers who need to understand the technical implementation details. **For step-by-step procedural guidance on running experiments or replicating the study, please refer to the [🔬 Replication Guide](docs/REPLICATION_GUIDE.md).**

## 📑 Document Navigation

- **📄 Research Article** (`docs/article_main_text.md`) - Scientific findings and validation
- **📖 README** (`README.md`) - Quick start guide and feature overview  
- **🔬 Replication Guide** (`docs/REPLICATION_GUIDE.md`) - Step-by-step procedures for reproducing or extending the study
- **🔧 Framework Manual** (this document) - Technical specifications and API references
- **📊 Data Preparation Data Dictionary** (`docs/DATA_PREPARATION_DATA_DICTIONARY.md`) - Detailed file specifications for `data/` directory
- **📈 Experiment and Study Workflow Data Dictionary** (`docs/EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md`) - Detailed file specifications for `output/` directory

{{toc}}

---

## Quick Reference Card

### Essential Commands

*Table 1: Essential Commands*

| Task | Command | Purpose |
|:-----|:--------|:--------|
| **Create experiment** | `./new_experiment.ps1` | Generate new experiment for a single condition |
| **Check status** | `./audit_experiment.ps1 -ExperimentDirectory <path>` | Diagnostic report on experiment completeness |
| **Resume/fix** | `./fix_experiment.ps1 -ExperimentDirectory <path>` | Repair interrupted or incomplete experiment |
| **Compile study** | `./compile_study.ps1 -StudyDirectory <path>` | Aggregate experiments and run statistical analysis |
| **Run all tests** | `pdm run test` or `pdm test` | Execute complete test suite |

### Key Configuration Parameters

*Table 2: Key Configuration Parameters*

| Parameter | Location | Purpose | Example |
|:----------|:---------|:--------|:--------|
| `mapping_strategy` | `[Study]` or `[Experiment]` | Correct vs random pairing | `correct, random` |
| `group_size` | `[Study]` or `[Experiment]` | Number of subjects per trial (k) | `7, 10, 14` |
| `model_name` | `[Study]` or `[LLM]` | LLM to evaluate | `google/gemini-2.0-flash-001` |
| `num_replications` | `[Experiment]` | Repetitions per condition | `30` |
| `num_trials` | `[Experiment]` | Trials per replication | `80` |
| `temperature` | `[LLM]` | Output randomness (0.0-2.0) | `0.0` |

### Critical File Paths

*Table 3: Critical File Paths*

| File | Purpose |
|:-----|:--------|
| `config.ini` | Main configuration file |
| `.env` | API key storage (OPENROUTER_API_KEY) |
| `data/personalities_db.txt` | Final personality database (input to experiments) |
| `output/new_experiments/` | Individual experiment results |
| `output/studies/` | Compiled study analyses |

### Quick Troubleshooting

*Table 4: Quick Troubleshooting Guide*

| Issue | Solution |
|:------|:---------|
| Experiment incomplete | Run `audit_experiment.ps1` to diagnose, then `fix_experiment.ps1` to repair |
| API errors | Check `.env` file for valid OPENROUTER_API_KEY |
| Cannot acquire lock | Wait for current operation or use `pdm run unlock` if certain no operations running |
| Missing dependencies | Run `pdm install -G dev` from project root |

### Getting Help

- **Framework details:** See sections below
- **Step-by-step procedures:** [📋 Replication Guide](docs/REPLICATION_GUIDE.md)
- **Development:** [👨‍💻 Developer's Guide](DEVELOPERS_GUIDE.md)
- **Testing:** [🧪 Testing Guide](docs/TESTING_GUIDE.md)

---

## Reader Navigation Guide

This manual serves multiple audiences. Use this matrix to identify which sections are most relevant to your needs:

*Table 5: Reader Navigation Guide*

| Section | Researcher | Developer | Data Analyst | Page |
|:--------|:----------:|:---------:|:------------:|:----:|
| **Technical Overview** | ✓✓ | ✓✓✓ | ✓✓ | [Link](#technical-overview) |
| **Data Preparation Pipeline** | ✓✓ | ✓✓ | ✓✓✓ | [Link](#data-preparation-pipeline) |
| **Architecture Overview** | ✓ | ✓✓✓ | ✓✓ | [Link](#architecture-overview) |
| **Visual Architecture** | ✓✓ | ✓✓✓ | ✓✓ | [Link](#visual-architecture) |
| **Experimental Hierarchy** | ✓✓✓ | ✓✓ | ✓✓✓ | [Link](#experimental-hierarchy) |
| **Study Design** | ✓✓✓ | ✓✓ | ✓✓ | [Link](#study-design) |
| **Directory Structure** | ✓ | ✓✓✓ | ✓✓ | [Link](#directory-structure) |
| **Setup and Installation** | ✓✓✓ | ✓✓✓ | ✓✓ | [Link](#setup-and-installation) |
| **Configuration** | ✓✓✓ | ✓✓ | ✓✓ | [Link](#configuration-configini) |
| **Choosing the Right Workflow** | ✓✓✓ | ✓✓ | ✓ | [Link](#choosing-the-right-workflow-separation-of-concerns) |
| **Core Workflows** | ✓✓✓ | ✓✓ | ✓✓ | [Link](#core-workflows) |
| **Data Preparation Pipeline** | ✓✓ | ✓✓ | ✓✓✓ | [Link](#data-preparation-pipeline) |
| **Report Formats** | ✓✓ | ✓✓ | ✓✓✓ | [Link](#report-formats) |
| **Key Data Formats** | ✓ | ✓✓ | ✓✓✓ | [Link](#key-data-formats) |
| **Testing** | ✓ | ✓✓✓ | ✓ | [Link](#testing) |
| **Extending the Framework** | ✓✓ | ✓✓✓ | ✓ | [Link](#extending-the-framework) |

**Legend:** ✓✓✓ = Essential | ✓✓ = Highly Relevant | ✓ = Useful Context

**Quick Start Paths:**
- **Researchers:** Start with Quick Reference → Research Question → Core Workflows → Configuration
- **Developers:** Start with Quick Reference → Architecture → Directory Structure → Testing
- **Data Analysts:** Start with Quick Reference → Experimental Hierarchy → Data Formats → Data Preparation Pipeline

---

## Getting Started

### Setup and Installation

This project uses **PDM** for dependency and environment management.

1.  **Install PDM (One-Time Setup)**:
    If you don't have PDM, install it once with pip. It's best to run this from a terminal *outside* of any virtual environment.
    ```bash
    pip install --user pdm
    ```
    > **Note:** If `pdm` is not found in a new terminal, use `python -m pdm` instead.

2.  **Install Project Environment & Dependencies**:
    From the project's root directory, run the main PDM installation command. The `-G dev` flag installs all packages, including the development tools needed to run the test suite.
    ```bash
    pdm install -G dev
    ```
    This command creates a local `.venv` folder and installs all necessary packages into it.

3.  **Configure API Key**:
    *   Create a file named `.env` in the project root.
    *   Add your API key from OpenRouter. The key will start with `sk-or-`.
        `OPENROUTER_API_KEY=your-actual-api-key`

To run any project command, such as the test suite, prefix it with `pdm run`:
```bash
pdm run test
```

> **For Developers:** If you intend to contribute to the project or encounter issues with the simple setup, please see the **[Developer Setup Guide](../DEVELOPERS_GUIDE.md#getting-started-development-environment-setup)** for more detailed instructions and troubleshooting.

### Configuration (`config.ini`)

The `config.ini` file is the central hub for defining all parameters for your experiments. The pipeline automatically archives this file with the results to document experimental parameters.

### Configuration Reference

*Table 6: Configuration (`config.ini`) Reference*

| Section | Parameter | Description | Example Value |
| :--- | :--- | :--- | :--- |
| **`[Study]`** | `mapping_strategy` | Comma-separated list of mapping strategies for factorial design. Enables interactive selection. | `correct, random` |
| | `group_size` | Comma-separated list of group sizes (`k`) for factorial design. | `7, 10, 14` |
| | `model_name` | Comma-separated list of LLM models for factorial design. | `google/gemini-2.0-flash-001, meta-llama/llama-3.3-70b-instruct` |
| **`[Experiment]`** | `num_replications` | The number of times the experiment will be repeated (`r`). | `30` |
| | `num_trials` | The number of trials for each replication (`m`). | `80` |
| | `group_size` | The number of subjects in each group (`k`). Used when `[Study]` section is empty. | `10` |
| | `mapping_strategy` | Mapping strategy: `correct` or `random`. Used when `[Study]` section is empty. | `correct` |
| **`[LLM]`** | `model_name` | The API identifier for the LLM. Used when `[Study]` section is empty. | `google/gemini-2.0-flash-001` |
| | `temperature` | Controls the randomness of the model's output (0.0-2.0). | `0.0` |
| | `max_tokens` | Maximum tokens in the model's response. | `8192` |
| | `max_parallel_sessions` | The number of concurrent API calls to make. | `10` |
| **`[Analysis]`** | `min_valid_response_threshold` | Minimum average valid responses for an experiment to be included in the final analysis. Set to `0` to disable. | `25` |
| **`[DataGeneration]`** | `bypass_candidate_selection` | If `true`, skips LLM-based scoring and uses all eligible candidates. | `false` |
| | `cutoff_search_start_point` | The cohort size at which to start searching for the variance curve plateau. | `3500` |
| | `smoothing_window_size` | The window size for the moving average used to smooth the variance curve. | `800` |

**Note:** Parameters defined in `[Study]` take precedence. When you run `new_experiment.ps1` with a populated `[Study]` section, you'll select specific values interactively, which are then written to `[Experiment]` and `[LLM]` sections before the experiment executes. If `[Study]` is empty or absent, values are read directly from `[Experiment]` and `[LLM]` sections.

### Study-Level vs. Experiment-Level Configuration

The framework supports two configuration modes:

#### Interactive Study Design (`[Study]` Section)

For factorial experiments comparing multiple conditions, define experimental 
factors in the `[Study]` section with comma-separated values:
```ini
  [Study]
  mapping_strategy = correct, random
  group_size = 7, 10, 14
  model_name = anthropic/claude-sonnet-4, google/gemini-2.0-flash-lite-001, meta-llama/llama-3.3-70b-instruct, openai/gpt-4o, deepseek/deepseek-chat-v3.1, qwen/qwen-2.5-72b-instruct, mistralai/mistral-large-2411
  num_replications = 30
  num_trials = 80
  temperature = 0.0
  max_tokens = 2048
```

When you run `new_experiment.ps1`, the script presents an interactive menu 
for selecting specific values. Your selections are automatically written to 
the `[Experiment]` section before the experiment executes.

**Use this mode when:** You're creating multiple experiments for a factorial study.

#### Direct Configuration (`[Experiment]` Section Only)

For single-condition experiments, specify parameters directly:
```ini
  [Experiment]
  num_replications = 2
  num_trials = 3
  group_size = 5
  mapping_strategy = random
```

**Use this mode when:** You're running a single experiment with fixed parameters (type 'e' at the first prompt).

#### How They Work Together

1. **If `[Study]` section exists with parameters** → Interactive mode activated
2. **User selections** → Written to `[Experiment]` section
3. **Experiment executes** → Uses values from `[Experiment]` section
4. **Configuration archived** → `config.ini.archived` captures exact parameters used

This two-tier system enables efficient factorial study creation while maintaining complete methodological documentation for each individual experiment.

#### Analysis Settings (`[Analysis]`)

-   **`min_valid_response_threshold`**: Minimum average number of valid responses (`n_valid_responses`) for an experiment to be included in the final analysis. Set to `0` to disable.

### Choosing the Right Workflow: Separation of Concerns

The framework is designed around a clear "Create -> Check -> Fix -> Compile" model. This separation of concerns ensures that each workflow is simple, predictable, and safe.

-   **`new_experiment.ps1` (Create)**: Use this to create a new experiment from scratch for a single experimental condition.

-   **`audit_experiment.ps1` (Check - Experiment)**: Use this read-only tool to get a detailed status report on any existing experiment. It is your primary diagnostic tool.

-   **`fix_experiment.ps1` (Fix & Update)**: Use this for any experiment with a fixable error, such as an interrupted run. This is the main "fix-it" tool for common issues.

-   **`audit_study.ps1` (Check - Study)**: Use this read-only tool to get a consolidated status report on all experiments in a study directory before final analysis.

-   **`compile_study.ps1` (Compile)**: After creating and validating all experiments, use this script to aggregate the results and run the final statistical analysis.

{{grouped_figure:docs/diagrams/logic_workflow_chooser.mmd | scale=2.5 | width=50% | caption=Figure 1: Choosing the Right Workflow: A guide for experiment and study tasks.}}

### Core Workflows

The project is orchestrated by several PowerShell wrapper scripts that handle distinct user workflows.

### Creating a New Experiment (`new_experiment.ps1`)

This is the entry point for creating a new experiment from scratch. It reads `config.ini`, generates a timestamped directory, and runs the full batch.

```powershell
# Create and run a new experiment
.\new_experiment.ps1 -Verbose
```

#### Interactive Study Parameter Selection

If your `config.ini` includes a `[Study]` section with multiple values for experimental design parameters, `new_experiment.ps1` will present an interactive menu for selecting specific conditions:
```ini
[Study]
# Study-level experimental design parameters
mapping_strategy = correct, random
group_size = 7, 10, 14
model_name = meta-llama/llama-3.3-70b-instruct, google/gemini-2.5-flash-lite, openai/gpt-4.1-nano

[Experiment]
num_replications = 30
num_trials = 80
```

When you run the script, it displays available options:
```powershell
.\new_experiment.ps1
```
```
  ################################################################################
  ###                           NEW EXPERIMENT SETUP                           ###
  ################################################################################

                                                                                                                          
  Study Experimental Design
  ================================================================================

  Mapping Strategies:
    [1] correct
    [2] random

  Group Sizes:
    [1] 7
    [2] 10
    [3] 14

  Models:
    [1] anthropic/claude-sonnet-4
    [2] google/gemini-2.0-flash-lite-001
    [3] meta-llama/llama-3.3-70b-instruct
    [4] openai/gpt-4o
    [5] deepseek/deepseek-chat-v3.1
    [6] qwen/qwen-2.5-72b-instruct
    [7] mistralai/mistral-large-2411

  Select Mapping Strategy [1-2] or 'e' to use [Experiment] defaults: 1
  Select Group Size [1-3]: 2
  Select Model [1-7]: 3
```

  After making the selections:
```
  Selected Configuration:
    Mapping Strategy: correct
    Group Size: 10
    Model: meta-llama/llama-3.3-70b-instruct
    Number of Replications: 30
    Number of Trials: 80
    Temperature: 0.0
    Max Tokens: 2048

  Proceed with this configuration? (Y/N, Ctrl+C to exit):
```

After selection, your choices are automatically written to the `[Experiment]` and `[LLM]` sections before experiment creation. Each experiment's parameters are logged to `output/studies/study_creation_log.txt` for tracking your complete study design.

**Fallback Behavior:** If the `[Study]` section is empty or absent, the script uses values directly from `[Experiment]` and `[LLM]` sections (standard behavior).

### Auditing an Experiment (`audit_experiment.ps1`)

This is the primary diagnostic tool for an experiment. It performs a read-only check and provides a detailed status report.

```powershell
# Get a status report for an existing experiment
.\audit_experiment.ps1 -ExperimentDirectory "output/new_experiments/experiment_20250910_062305"
```

### Fixing or Updating an Experiment (`fix_experiment.ps1`)

This is the main "fix-it" tool for an existing experiment. It automatically diagnoses and fixes issues.

**To automatically fix a broken or incomplete experiment:**
The script will run an audit, identify the problem (e.g., missing responses, outdated analysis), and automatically apply the correct fix.
```powershell
# Automatically fix a broken experiment
.\fix_experiment.ps1 -ExperimentDirectory "output/new_experiments/experiment_20250910_062305"
```

**To interactively force an action on a valid experiment:**
If you run the script on a complete and valid experiment, it will present an interactive menu allowing you to force a full repair, an analysis update, or a re-aggregation of results.

```powershell
# Run on a valid experiment to bring up the interactive force menu
.\fix_experiment.ps1 -ExperimentDirectory "output/new_experiments/experiment_20250910_062305"
```

### Auditing a Study (`audit_study.ps1`)

This is the main diagnostic tool for a study. It performs a comprehensive, read-only audit of all experiments in a study directory and provides a consolidated summary report with a final recommendation.

```powershell
# Get a status report for an entire study
.\audit_study.ps1 -StudyDirectory "output/studies/My_First_Study"
```

### Compiling a Study (`compile_study.ps1`)

This script orchestrates the entire compilation and analysis workflow for a study. It audits, compiles, and performs the final statistical analysis on all experiments.

**Important:** This script begins with a robust pre-flight check by calling `audit_study.ps1`. If the audit reveals that any experiment is not `VALIDATED`, or that the study is already `COMPLETE`, the process will halt with a detailed report and a clear recommendation. This guarantees that analysis is only performed on a complete and ready set of data.

For organizational purposes, one would typically move all experiment folders belonging to a single study into a common directory (e.g., `output/studies/My_First_Study/`).

**To run the compilation and analysis:**
Point the script at the top-level directory containing all relevant experiment folders. It will provide a clean, high-level summary of its progress.

```powershell
# Example: Compile and analyze all experiments in the "My_First_Study" directory
.\compile_study.ps1 -StudyDirectory "output/studies/My_First_Study"
```
For detailed, real-time logs, add the `-Verbose` switch.

**Final Artifacts:**
The script generates two key outputs:

1.  A master `STUDY_results.csv` file in your study directory, containing the aggregated data from all experiments.
2.  A new `anova/` subdirectory containing the final analysis:
    *   `STUDY_analysis_log.txt`: A comprehensive text report of the statistical findings.
    *   `boxplots/`: Publication-quality plots visualizing the results.
    *   `diagnostics/`: Q-Q plots for checking statistical assumptions.

---

## Architecture & Design

As depicted below, the framework consists of the following main components:

*   Documentation (root and `docs/`)
*   Diagrams (`docs/diagrams/`)
*   Validation Suite (`tests/`)
*   Developer Utilities (`scripts/`)
*   Orchestration Scripts (`*.ps1` in root)
*   Production Scripts (`src/`)
*   Input & Output Data (`data/`)
*   Generated Experiments & Analysis Reports (`output/`)
*   Generated Project Reports (`output/project_reports`)

{{grouped_figure:docs/diagrams/arch_project_overview.mmd | scale=2.5 | width=100% | caption=Figure 2: Project Architecture: A high-level overview of the project's main functional components and their relationships.}}

### Directory Structure

This logical hierarchy is reflected in the physical layout of the repository:

*Figure 3: Directory Structure of the Project Repository*
{{diagram:docs/diagrams/view_directory_structure.txt | scale=2.5 | width=100%}}

## Data Dictionaries

For comprehensive file-by-file documentation of all data structures, see the data dictionaries:

- **[📊 Data Preparation Data Dictionary](DATA_PREPARATION_DATA_DICTIONARY.md)** - Complete specifications for the `data/` directory:
  - Source files (`adb_raw_export.txt`)
  - Intermediate processing files (`adb_eligible_candidates.txt`, `adb_final_candidates.txt`)
  - Foundational assets (`point_weights.csv`, `balance_thresholds.csv`, neutralized delineations)
  - Reports and validation files

- **[📈 Experiment and Study Workflow Data Dictionary](EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md)** - Complete specifications for the `output/` directory:
  - Experiment hierarchy (Study → Experiment → Replication → Trial)
  - Result files at each level (`REPLICATION_results.csv`, `EXPERIMENT_results.csv`, `STUDY_results.csv`)
  - Statistical analysis outputs (`anova/` directory contents)
  - Log files and metadata

These dictionaries provide the detailed file format specifications that complement the architectural overview presented in this manual.

## Technical Overview

This framework provides an automated pipeline for testing complex narrative systems using Large Language Models (LLMs) as pattern-recognition engines. The system executes matching tasks where an LLM attempts to pair narrative personality descriptions with biographical profiles at rates significantly greater than chance.

The framework's architecture supports three distinct research paths (direct replication, methodological replication, and conceptual replication) through modular components and well-defined data interfaces. For conceptual background and research rationale, see the research article and Replication Guide.

## Data Preparation Pipeline

The data preparation pipeline transforms raw data from external sources into the curated dataset used in experiments. For detailed procedural guidance on running this pipeline, see the **[🔬 Replication Guide](docs/REPLICATION_GUIDE.md)**.

### Pipeline Script Reference

*Table 7: Data Preparation Pipeline Script Reference*

| Script | Purpose | Key Outputs |
|--------|---------|-------------|
| `fetch_adb_data.py` | Query Astro-Databank API | `adb_raw_export.txt` |
| `find_wikipedia_links.py` | Locate Wikipedia URLs | `adb_wiki_links.csv` |
| `validate_wikipedia_pages.py` | Validate Wikipedia content | `adb_validation_report.csv` |
| `select_eligible_candidates.py` | Apply qualification filters | `adb_eligible_candidates.txt` |
| `generate_eminence_scores.py` | LLM-based eminence scoring | `eminence_scores.csv` |
| `generate_ocean_scores.py` | LLM-based personality scoring | `ocean_scores.csv` |
| `select_final_candidates.py` | Data-driven cohort selection | `adb_final_candidates.txt` |
| `prepare_sf_import.py` | Format for Solar Fire import | `sf_data_import.txt` |
| `generate_personalities_db.py` | Assemble personality profiles | `personalities_db.txt` |

### Orchestration

The `prepare_data.ps1` PowerShell script orchestrates the entire pipeline with automatic resumption from failures. For usage details, see the Replication Guide.

## The Experiment & Study Workflow

### Experimental Hierarchy

The project's experiments are organized in a logical hierarchy:

-   **Study**: The highest-level grouping, representing a major research question (e.g., "Performance on Random vs. Correct Mappings").
-   **Experiment**: A complete set of runs for a single condition within a study (e.g., "Gemini 2.0 Flash with k=10 Subjects").
-   **Replication**: A single, complete run of an experiment, typically repeated 30 times for statistical power.
-   **Trial**: An individual matching task performed within a replication, typically repeated 100 times.

### Key Features

-   **Automated Batch Execution**: The `experiment_manager.py` script, driven by a simple PowerShell wrapper, manages entire experimental batches. It can run hundreds of replications, intelligently skipping completed ones to resume interrupted runs, and provides real-time progress updates, including a detailed spinner showing individual trial timers and overall replication batch ETA.
-   **Powerful Reprocessing Engine**: The manager's `--reprocess` mode allows for re-running the data processing and analysis stages on existing results without repeating expensive LLM calls. This makes it easy to apply analysis updates or bug fixes across an entire experiment.
-   **Guaranteed Reproducibility**: On every new run, the `config.ini` file is automatically archived in the run's output directory, permanently linking the results to the exact parameters that generated them.
-   **Standardized, Comprehensive Reporting**: Each replication produces a `replication_report.txt` file containing run parameters, status, a human-readable statistical summary, and a machine-parsable JSON block with all key metrics. This format is identical for new runs and reprocessed runs.
-   **Hierarchical Analysis & Aggregation**: The pipeline uses a set of dedicated compiler scripts for a fully auditable, bottom-up aggregation of results. `compile_replication_results.py` creates a summary for each run, `compile_experiment_results.py` combines those into an experiment-level summary, and finally `compile_study_results.py` creates a master `STUDY_results.csv` for the entire study.
-   **Comprehensive Self-Healing Capabilities**: The framework automatically detects and repairs multiple types of experiment corruption, including missing response files, corrupted analysis data, damaged configuration files, and malformed reports. The audit system classifies corruption severity and applies appropriate repair strategies, ensuring data integrity even after network interruptions, storage errors, or process crashes.
-   **Session Failure Tolerance**: Experiments continue when individual LLM API calls fail, requiring only that failure rates remain below 50% to maintain data quality while accommodating intermittent service disruptions.
-   **Graceful Repair Handling**: When repair operations fail, the pipeline continues to final audit and aggregation stages, providing complete experiment status reports rather than halting execution.
-   **Response Parsing Diagnostics**: Generates detailed parsing summaries showing success/failure status for each response, included in replication reports for troubleshooting diverse LLM output formats.
-   **Flexible Response Processing**: Extracts k×k numerical score matrices from diverse LLM response formats by identifying exactly k consecutive lines containing exactly k numeric values at the end of each line, regardless of headers, explanations, or column formatting variations.
-   **Standardized Console Banners**: All audit results, whether for success, failure, or a required update, are presented in a consistent, easy-to-read, 4-line colored banner, providing clear and unambiguous status reports.
-   **Streamlined ANOVA Workflow**: The final statistical analysis is a simple two-step process. `compile_study_results.py` prepares a master dataset, which `analyze_study_results.py` then automatically analyzes to generate tables and publication-quality plots using user-friendly display names defined in `config.ini`.

### Visual Architecture

The main pipeline's architecture can be understood through four different views: the code architecture, the workflows, the data flow, and the experimental logic.

#### Code Architecture Diagram
The codebase for the experiment workflow and analysis is organized into a clear hierarchy:

1.  **Main User Entry Points**: User-facing PowerShell scripts (`.ps1`) that orchestrate high-level workflows like creating, auditing, or fixing experiments and studies.
2.  **Experiment Lifecycle Management**: The core Python backend for managing a single experiment. This includes primary orchestrators (`experiment_manager.py`, `experiment_auditor.py`) and dedicated finalization scripts (`manage_experiment_log.py`, `compile_experiment_results.py`).
3.  **Single Replication Pipeline**: A set of scripts, managed by `replication_manager.py`, that execute the end-to-end process for a single run, from query generation to final reporting.
4.  **Study-Level Analysis**: Python scripts that operate on the outputs of multiple experiments to perform study-wide aggregation and statistical analysis.
5.  **Utility & Other Scripts**: Shared modules and standalone utility scripts that provide common functionality (e.g., `config_loader.py`) or perform auxiliary tasks.

<br>

{{grouped_figure:docs/diagrams/arch_main_codebase.mmd | scale=2.5 | width=100% | caption=Figure 4: Codebase Architecture: A comprehensive map of the entire Python codebase. PowerShell scripts (blue) are user-facing entry points that execute core Python logic. Solid lines indicate execution, while dotted lines show module imports.}}

#### Workflow Diagrams
The framework's functionality is organized into a clear hierarchy of workflows, initiated by dedicated PowerShell scripts.

**Experiment-Level Workflows:**
-   **Create a New Experiment (`new_experiment.ps1`):** The primary workflow for generating new experimental data for a single condition.
-   **Audit an Experiment (`audit_experiment.ps1`):** A read-only diagnostic tool that provides a detailed completeness report for an experiment.
-   **Fix or Update an Experiment (`fix_experiment.ps1`):** The main "fix-it" tool for resuming interrupted runs or reapplying analysis updates to existing data.

**Study-Level Workflows:**
-   **Audit a Study (`audit_study.ps1`):** A read-only diagnostic tool that provides a consolidated audit of all experiments in a study directory.
-   **Compile a Study (`compile_study.ps1`):** The final step in the research process. This script aggregates data from all experiments in a study, runs the statistical analysis, and generates the final reports and plots.

#### Workflow 1: Create a New Experiment

This is the primary workflow for generating new experimental data. The PowerShell entry point (`new_experiment.ps1`) calls the Python batch controller (`experiment_manager.py`). The manager creates a new, timestamped directory and runs the full set of replications from scratch.

The `replication_manager.py` script executes the full pipeline for a single run, which is broken into six distinct stages:

1.  **Build Queries**: Generates all necessary query files and trial manifests.
2.  **Run LLM Sessions**: Interacts with the LLM API in parallel to get responses.
3.  **Process LLM Responses**: Parses the raw text responses from the LLM into structured score files.
4.  **Analyze LLM Performance**: A unified two-part process that first calculates core performance metrics and then injects diagnostic bias metrics.
5.  **Generate Final Report**: Assembles the final `replication_report.txt` from the analysis results and captured logs.
6.  **Create Replication Summary**: Creates the final `REPLICATION_results.csv`, marking the run as valid.

{{grouped_figure:docs/diagrams/flow_main_1_new_experiment.mmd | scale=2.5 | width=60% | caption=Figure 5: Workflow 1: Create a New Experiment, showing the main control loop and the internal replication pipeline.}}

#### Workflow 2: Audit an Experiment

This workflow provides a read-only, detailed completeness report for an experiment without performing any modifications. The `audit_experiment.ps1` wrapper calls the dedicated `experiment_auditor.py` script. The full audit report, including subprocess outputs, is also saved to `experiment_audit_log.txt` within the audited directory.

{{grouped_figure:docs/diagrams/flow_main_2_audit_experiment.mmd | scale=2.5 | width=85% | caption=Figure 6: Workflow 2: Audit an Experiment. Provides a read-only, detailed completeness report for an experiment.}}

##### Interpreting the Audit Report
The audit script is the primary diagnostic tool for identifying issues in a failed or incomplete experiment. It uses a simple but robust rule to classify problems: the number of distinct errors found in a single replication run.

**Repairable Issues (Single Error)**
If a replication run has **exactly one** identifiable problem, it is considered safe to repair in-place. The `Status` column will show a specific, targeted error code:

*Table 8: Audit Report Status Codes for Repairable Issues*

| Status Code | Description | Recommended Action |
| :--- | :--- | :--- |
| **`INVALID_NAME`** | The run directory name is malformed. | Run `fix_experiment.ps1` to repair. |
| **`CONFIG_ISSUE`** | The `config.ini.archived` is missing or inconsistent. | Run `fix_experiment.ps1` to repair. |
| **`QUERY_ISSUE`** | Core query files or manifests are missing. | Run `fix_experiment.ps1` to repair. |
| **`RESPONSE_ISSUE`** | One or more LLM response files are missing. | Run `fix_experiment.ps1` to repair. |
| **`ANALYSIS_ISSUE`** | Core data is present, but analysis files are missing/outdated. | Run `fix_experiment.ps1` to repair. |

Any of these single-error states will result in an overall audit recommendation to run **`fix_experiment.ps1`**.

**Corrupted Runs (Multiple Errors)**
If a replication run has **two or more** distinct problems (e.g., a missing config file *and* missing responses), it is flagged with the status `RUN_CORRUPTED`. A corrupted run indicates a systemic issue that cannot be safely repaired automatically. The audit will recommend investigating the issue manually. Corrupted experiments should generally be deleted and re-run.

The `Details` string provides a semicolon-separated list of all detected issues (e.g., `CONFIG_MISSING; RESPONSE_FILES_INCOMPLETE`).

A key part of this validation is a strict schema check on the `replication_report.txt` file. The audit verifies that the JSON block of metrics contains *exactly* the set of required keys—no more, and no less. A report with missing (`REPORT_INCOMPLETE_METRICS`) or extra, obsolete metrics (`REPORT_UNEXPECTED_METRICS`) will be flagged with an `ANALYSIS_ISSUE`. This ensures that analysis is only ever performed on data with a correct and up-to-date schema.

In addition to the per-replication table, the audit provides an `Overall Summary` that includes the `Experiment Aggregation Status`. This checks for the presence and completeness of top-level summary files (`EXPERIMENT_results.csv`, `experiment_log.csv`), confirming whether the last aggregation step for the experiment was successfully completed.

#### Workflow 3: Fixing or Updating an Experiment

This workflow is the main "fix-it" tool for any existing experiment. The `fix_experiment.ps1` script is an intelligent wrapper. It first performs a full audit by calling `experiment_auditor.py` to diagnose the experiment's state. Based on the audit result, it then calls `experiment_manager.py` to apply the correct repairs.

-   If the audit finds missing data or outdated analysis files, the script proceeds to automatically apply the correct repair.
-   If the audit finds the experiment is already complete and valid, it becomes interactive, presenting a menu that allows the user to force a full data repair, an analysis update, or a simple re-aggregation of results.

<br>

{{grouped_figure:docs/diagrams/flow_main_3_fix_experiment.mmd | scale=2.5 | width=100% | caption=Figure 7: Workflow 3: Fixing or Updating an Experiment, showing both automatic and interactive repair paths.}}

#### Workflow 4: Compile a Study

This workflow is used after all experiments are validated to audit, compile, and analyze the entire study. It performs a robust pre-flight check by calling `audit_study.ps1`. If the study is not ready for processing (or is already complete), it will halt with a clear recommendation. Otherwise, it proceeds to compile all results and run the final statistical analysis.

<br>

{{grouped_figure:docs/diagrams/flow_main_4_compile_study.mmd | scale=2.5 | width=90% | caption=Figure 8: Workflow 4: Compile a Study. Audits, compiles, and analyzes all experiments in a study.}}

#### Workflow 5: Audit a Study

This script is the primary diagnostic tool for assessing the overall state of a study. It performs a two-part, read-only audit:

1.  **Readiness Audit**: It iterates through every experiment folder and runs a quiet, individual audit on each to determine its status (e.g., `VALIDATED`, `NEEDS REPAIR`).
2.  **Completeness Audit**: It verifies the existence of top-level study artifacts, such as `STUDY_results.csv` and the `anova/` analysis directory.

Based on the combined results from both audits, it presents a consolidated summary table and provides a final, context-aware recommendation for the correct next step.

<br>

{{grouped_figure:docs/diagrams/flow_main_5_audit_study.mmd | scale=2.5 | width=55% | caption=Figure 9: Workflow 5: Audit a Study. Consolidated completeness report for all experiments in a study.}}

#### Workflow 6: Analyzing Study Subsets

The `analyze_study_subsets.ps1` script enables flexible subset analysis by filtering the master `STUDY_results.csv` and running statistical analysis on specific data subsets. This is useful for examining results within specific conditions (e.g., analyzing only one model, one k-value, or one mapping strategy).

**Key Features:**
- **Interactive Mode**: Default guided filter builder when no filter is provided
- **Direct Filter Mode**: Supports pandas query syntax for custom filtering
- **Reuses Existing Infrastructure**: Uses the standard `analyze_study_results.py` without requiring new Python code
- **Organized Output**: Creates separate subdirectories in `anova_subsets/` for each analysis

**Usage Examples:**
````powershell
# Interactive mode (default) - guided filter builder
.\analyze_study_subsets.ps1

# Analyze only k=10 experiments
.\analyze_study_subsets.ps1 -Filter "k == 10"

# Analyze specific model at specific k-value
.\analyze_study_subsets.ps1 -Filter "model == 'anthropic/claude-sonnet-4' and k == 14"

# Custom output name for easy identification
.\analyze_study_subsets.ps1 -Filter "k == 10" -OutputName "k10_analysis"
````

**Filter Syntax:**
The script accepts pandas query expressions:
- **Equality**: `k == 10`, `model == 'anthropic/claude-sonnet-4'`
- **Comparison**: `k >= 10`, `k < 14`
- **Multiple conditions**: `k == 10 and mapping_strategy == 'correct'`
- **Advanced queries**: `model.isin(['anthropic/claude-sonnet-4', 'meta-llama/llama-3.3-70b-instruct'])`

**Output Structure** (`<StudyDirectory>/anova_subsets/<OutputName>/`):
- `STUDY_results.csv`: Filtered data subset
- `subset_metadata.txt`: Filter parameters and timestamp
- `anova/STUDY_analysis_log.txt`: Statistical analysis report
- `anova/boxplots/`: Visualization plots
- `anova/diagnostics/`: Q-Q plots

#### Workflow 7: Rerunning All Subset Analyses

The `rerun_all_study_subsets.ps1` script automatically reruns all existing subset analyses found in `anova_subsets/`. This is particularly useful after updating analysis code or display names in `config.ini`.

**Key Features:**
- **Automatic Discovery**: Scans `anova_subsets/` to identify all existing analyses
- **Filter Parsing**: Reconstructs filters from directory naming conventions
- **Consolidated Reporting**: Generates summary logs and concatenated detailed logs
- **Archive Management**: Archives previous results with timestamps
- **Dry-Run Mode**: Preview execution without making changes

**Usage Examples:**
````powershell
# Rerun all subset analyses
.\rerun_all_study_subsets.ps1 -StudyDirectory "output/studies/publication_run"

# Preview what would be run (no execution)
.\rerun_all_study_subsets.ps1 -StudyDirectory "output/studies/publication_run" -DryRun

# Only compile existing logs (no reanalysis)
.\rerun_all_study_subsets.ps1 -StudyDirectory "output/studies/publication_run" -CompileOnly
````

**Naming Convention Recognition:**

| Directory Name | Reconstructed Filter |
|----------------|---------------------|
| `1.1_k7_analysis` | `k == 7` |
| `2.1_claude_k10` | `model contains 'claude' and k == 10` |
| `3.1_traj_gpt4o_k7` | `mapping_strategy == 'correct' and model contains 'gpt4o' and k == 7` |

**Output Artifacts:**
- `anova_subsets/ANOVA_SUBSETS_SUMMARY.txt`: High-level summary
- `anova_subsets/CONSOLIDATED_ANALYSIS_LOG.txt`: All detailed logs concatenated
- `anova/archive/`: Previous summary logs with timestamps

**Use Cases:**
- Regenerate plots after display name changes in `config.ini`
- Apply updated analysis methodology to all existing subsets
- Refresh results after statistical code improvements
- Create consolidated documentation of all subset findings

#### Workflow 8: Effect Size Chart Generation

The framework generates effect size visualizations at two levels: study-level (main effects from the primary ANOVA) and consolidated subset charts (for visualizing patterns across multiple subset analyses, such as the Goldilocks effect).

**Configuration** (`config.ini`):
The generation of all effect size charts is controlled by the `[EffectSizeCharts]` section.
```ini
[EffectSizeCharts]
# Generate a main effect chart for the 'model' factor from the main study ANOVA
study_level_main_effects = model

# Define rules for creating consolidated charts from subset analyses.
# Format is primary_factor:stratifying_factor
subset_consolidated_charts = mapping_strategy:k, mapping_strategy:model

# Specify the metric to use for the y-axis on consolidated charts
subset_chart_metric = mean_mrr_lift
```

**Study-Level Charts:**
- **Purpose**: Visualize the main effects calculated from the full study's primary ANOVA.
- **Location**: `output/studies/<StudyName>/anova/effect_sizes/`
- **Generation**: These charts are generated automatically by `analyze_study_results.py` during the `compile_study.ps1` workflow. They can be regenerated independently by running `analyze_study_results.py` with the `--charts-only` flag.
- **Output**: One chart per factor configured in `study_level_main_effects` (e.g., `model.png`).

**Consolidated Subset Charts:**
- **Purpose**: Visualize patterns that emerge across a series of subset analyses. For example, plotting the effect size of `mapping_strategy` at each level of `k` to visualize the Goldilocks effect.
- **Location**: `output/studies/<StudyName>/anova_subsets/effect_sizes/`
- **Generation**: These charts are generated on-demand by running `src/generate_consolidated_effect_charts.py` and pointing it at a directory containing the `CONSOLIDATED_ANALYSIS_LOG.txt` produced by the `rerun_all_study_subsets.ps1` workflow.
- **Input**: The script parses the consolidated analysis log file.
- **Output**: One chart per rule defined in `subset_consolidated_charts` (e.g., `mapping_strategy_x_k.png`, `mapping_strategy_x_model.png`).

**Chart Properties**: All charts are generated as 300 DPI, publication-ready PNG files. They include the effect size (η²), p-value, and standard significance indicators (*** p<.001, ** p<.01, * p<.05).

**Scripts Reference:**

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `analyze_study_results.py` | Runs main study analysis and genera

#### Workflow 8: Effect Size Chart Generation

The framework generates effect size visualizations at two levels: study-level (main effects) and consolidated subset charts (cross-subset patterns like the Goldilocks effect).

**Configuration** (`config.ini`):
````ini
[EffectSizeCharts]
study_level_main_effects = model
subset_consolidated_charts = mapping_strategy:k
subset_chart_metric = mean_mrr_lift
````

**Study-Level Charts:**
- **Purpose**: Main effects from full study ANOVA
- **Location**: `anova/effect_sizes/`
- **Generation**: Automatic during `compile_study.ps1` or via `--charts-only` flag
- **Output**: One chart per configured factor (e.g., `model.png`)

**Consolidated Subset Charts:**
- **Purpose**: Visualize patterns across subsets (e.g., Goldilocks effect showing inverted-U pattern)
- **Location**: `anova_subsets/effect_sizes/`
- **Generation**: `pdm run python src/generate_consolidated_effect_charts.py <subsets_dir>`
- **Input**: Parses `CONSOLIDATED_ANALYSIS_LOG.txt`
- **Output**: `mapping_strategy_x_k.png` (Goldilocks chart), `mapping_strategy_x_model.png` (model heterogeneity)

**Chart Properties**: Effect size (η²), significance indicators (*** p<.001, ** p<.01, * p<.05), 300 DPI publication-ready

**Scripts Reference:**

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `analyze_study_results.py` | Study analysis + charts | STUDY_results.csv | anova/effect_sizes/*.png |
| `generate_consolidated_effect_charts.py` | Consolidated subset charts | CONSOLIDATED_ANALYSIS_LOG.txt | anova_subsets/effect_sizes/*.png |

{{pagebreak}}
#### Data Flow Diagram

This diagram shows how data artifacts (files) are created and transformed by the experiment workflow and analysis scripts. It traces the flow from initial inputs like `config.ini` and the personalities database, through intermediate query and response files, to the final aggregated results and analysis plots.

{{grouped_figure:docs/diagrams/data_main_flow.mmd | scale=2.5 | width=80% | caption=Figure 10: Data Flow Diagram: Creation and transformation of data artifacts (files) by the experiment workflow and analysis scripts.}}

#### Logic Flowcharts

These diagrams illustrate the scientific and procedural methodology at each level of the experimental hierarchy.

{{grouped_figure:docs/diagrams/logic_main_replication.mmd | scale=2.5 | width=62% | caption=Figure 11: Replication Logic: The scientific methodology for a single replication run.}}

{{grouped_figure:docs/diagrams/logic_main_experiment.mmd | scale=2.5 | width=80% | caption=Figure 12: Experiment Logic: The aggregation of multiple replication results to produce final experiment-level summaries.}}

{{grouped_figure:docs/diagrams/logic_main_study.mmd | scale=2.5 | width=100% | caption=Figure 13: The complete workflow for processing a study, from auditing and aggregation to final statistical analysis.}}

### Testing

The project includes a comprehensive test suite managed by PDM scripts, which provides shortcuts for running tests with and without code coverage. Several integration tests offer interactive modes that provide guided tours of the framework's capabilities.

#### Automated CI Checks

The project uses a GitHub Actions workflow for Continuous Integration (CI). On every push or pull request, it automatically runs a series of checks on Windows, Linux, and macOS to ensure code quality and consistency. This includes:

-   Linting all source files for correct formatting and headers.
-   Verifying that the documentation is up-to-date.

This ensures that the main branch is always stable and that all contributions adhere to the project's standards.

#### Running the Test Suite

-   **To run all tests (Python and PowerShell) at once:**
```bash
    pdm run test
```
-   **To run only the PowerShell script tests:**
```bash
    pdm run test-ps-all
```
    You can also test individual PowerShell scripts (e.g., `pdm run test-ps-exp`, `pdm run test-ps-stu`).

For detailed code coverage analysis, see the [👨‍💻 Developer's Guide - Code Coverage](../DEVELOPERS_GUIDE.md#code-coverage).

#### Statistical Validation

The framework provides external validation against GraphPad Prism 10.6.1 for academic publication.

For complete validation procedures, see the **[Statistical Analysis & Reporting Validation section in the Testing Guide](TESTING_GUIDE.md#statistical-analysis--reporting-validation)**.

**Academic Citation:** "Statistical analyses were validated against GraphPad Prism 10.6.1"

#### Methodological Validation Scripts

The framework includes standalone scripts for performing targeted validation of key methodological claims.

##### Neutralized Library Diversity Analysis

This script provides a quantitative rebuttal to the "Barnum Effect" concern by analyzing the semantic and lexical diversity of the neutralized component library. It calculates metrics for vocabulary overlap, semantic similarity, and structural coherence to validate that the building blocks of the personality profiles are distinct and not generic.

-   **Command:** `pdm run validate-diversity`
-   **Input:** Reads all neutralized component files from `data/foundational_assets/neutralized_delineations/`.
-   **Output:** Generates a detailed report at `output/validation_reports/neutralized_library_diversity_analysis.txt`, which includes key metrics and a pre-formatted text block suitable for inclusion in a research article.

### Troubleshooting Common Issues

This section provides solutions to the most common issues researchers may encounter when setting up the framework or running experiments.

| Issue | Solution |
| :--- | :--- |
| **`pdm` command not found** | This usually means the Python scripts directory is not in your system's PATH. You can either add it, or use `python -m pdm` as a reliable alternative (e.g., `python -m pdm install -G dev`). |
| **API Errors during an experiment run** | Network issues or API rate limits can cause individual LLM calls to fail. The framework is designed for this. Simply run the `fix_experiment.ps1` script on the experiment directory. It will automatically find and re-run only the failed API calls. |
| **"Permission Denied" error when building DOCX files** | This error occurs if a `.docx` file is open in Microsoft Word while the `pdm run build-docs` script is running. Close the file in Word, and the script will automatically retry and continue. |
| **`git` command not found** | The framework requires Git for versioning and reproducibility checks. Please install it from [git-scm.com](https://git-scm.com/downloads) and ensure it is available in your system's PATH. |
| **All LLM sessions fail (100% failure rate)** | This indicates a model configuration problem. Verify the model name in `config.ini` matches available models and check your API credentials and permissions. |
| **Repair process loops indefinitely** | The repair system automatically limits retry attempts to 3 cycles maximum. After 3 cycles, it proceeds with available data to prevent endless loops when external factors cause persistent failures. |
| **Enhanced status messages** | The framework now provides colored error output and detailed progress tracking (elapsed time, remaining time, ETA) for better visibility during long-running operations. |
| **Data preparation fails at fetch stage** | Verify your Astro-Databank credentials in the `.env` file. Check that your account has active access and that you can log in through the web interface. |
| **Wikipedia validation fails** | This can occur due to Wikipedia rate limiting or page structure changes. The script includes automatic retry logic, but persistent failures may require manual intervention. |
| **Solar Fire import issues** | Verify the file format matches the expected CQD format. Check that all required fields are present and correctly formatted. |
| **Neutralization script fails** | Check your OpenRouter API key and ensure you have sufficient funds. The `--fast` mode may fail on large tasks; use the default mode for reliable completion. |
| **LLM scoring steps report missing subjects** | The eminence and OCEAN scoring steps use a tiered approach for handling missing subjects. If ≥99% of subjects are scored, the pipeline continues with a notification. If 95-98% are scored, it continues with a warning. If <95% are scored, it stops with an error. Check the data completeness report at the end of the pipeline for details on missing subjects and instructions on how to retry specific steps. |

### Known Issues and Future Work

This framework is under active development. For a detailed and up-to-date list of planned improvements, known issues, and future development tasks, please see the [📋 Project Roadmap](docs/PROJECT_ROADMAP.md).

### Study Design

The original study for which this framework was developed employed a **2 × 3 × 7 factorial design**, resulting in 42 distinct experimental conditions.

-   **Factor 1: Mapping Strategy (Between-Subjects):**
    -   `correct`: Personality descriptions were correctly matched to their corresponding biographical profiles.
    -   `random`: Personality descriptions were randomly shuffled, serving as a null condition.

-   **Factor 2: Group Size / Difficulty (Within-Subjects):**
    -   `k = 7`: An easier condition with 49 comparisons per trial.
    -   `k = 10`: A moderate difficulty condition with 100 comparisons per trial.
    -   `k = 14`: A harder condition with 196 comparisons per trial.

-   **Factor 3: LLM Model (Within-Subjects):**
    -   Seven different large language models were evaluated to test for generalizability across architectures, providers, and training data. See the **[Replication Guide](docs/REPLICATION_GUIDE.md)** for the complete list of models used.

**Sample Size:**
For each of the 42 conditions, the following sample sizes were used:
-   **30 Replications per condition:** To ensure sufficient statistical power for detecting small effect sizes (Cohen's d < 0.20) with over 80% power.
-   **80 Trials per replication:** To provide a stable estimate of performance within each run and offer a robust buffer against occasional API or parsing failures.

This design resulted in a total of **1,260 replications** and **100,800 trials**.

> **Note for Researchers:** This section documents the design of the *original* study. For comprehensive guidance on how to design and execute new multi-factor experiments (including methodological and conceptual replications), please refer to **Appendix C** in the **[📋 Replication Guide](docs/REPLICATION_GUIDE.md)**.

## Error Recovery and Resilience

The framework implements comprehensive error recovery mechanisms to ensure data integrity and experimental continuity even when facing real-world failures.

### Categorized Error Handling

The pipeline categorizes errors by type and severity to apply appropriate recovery strategies:

**Statistical Issues:**
- Problems with data variance, sample sizes, or statistical test assumptions
- **Recovery**: Fallback strategies (e.g., Games-Howell when Tukey HSD fails)
- **Impact**: Analysis continues with reduced functionality but preserved scientific validity

**Data Structure Issues:**
- Missing columns, malformed files, or schema mismatches  
- **Recovery**: Validation with repair recommendations and graceful degradation
- **Impact**: Quality warnings generated while preserving completed analysis

**File I/O Issues:**
- Permission errors, missing manifests, or corrupted data files
- **Recovery**: Specific error logging with targeted recovery paths
- **Impact**: Affected components isolated while other analysis continues

**Validation Errors:**
- Manifest mismatches or experimental consistency failures
- **Recovery**: Analysis completion with quality status marking
- **Impact**: Results flagged for review but data preserved

### Intelligent Recovery Strategies

**Graceful Degradation:** When non-critical components fail, the analysis continues with reduced functionality rather than aborting entirely. For example, if Bayesian analysis fails due to data structure issues, the frequentist analysis proceeds normally.

**Intelligent Fallbacks:** The system automatically selects alternative methods when primary approaches fail. Post-hoc testing falls back from Tukey HSD to Games-Howell when equal variance assumptions are violated.

**Quality Preservation:** Results are marked with validation status (COMPLETE, PARTIAL, INVALID) while preserving all successfully completed analysis, ensuring maximum data recovery from partial failures.

**Enhanced Logging:** Error categorization enables targeted troubleshooting by distinguishing between statistical issues, data problems, and system failures, accelerating diagnosis and repair.

This multi-layered approach ensures that researchers can trust the framework to maintain scientific rigor and data integrity even when facing common real-world failures like network interruptions, storage errors, or process crashes.

### Enhanced Error Reporting and Recovery

The framework provides intelligent error detection and user-friendly guidance:

- **Model Configuration Errors**: When all LLM sessions fail (100% failure rate), the system automatically detects likely model configuration issues and provides specific guidance to check model names and API credentials.

- **Colored Error Output**: Error messages use color coding for improved visibility and categorization of different failure types.

- **Repair Cycle Limits**: The repair system implements a 3-cycle maximum to prevent infinite loops when queries consistently fail due to external issues (e.g., API problems, invalid models).

- **Progress Feedback**: All operations provide consistent timing information (Time Elapsed, Time Remaining, ETA) to keep users informed during long-running processes.

## Appendices

### Standardized Output

The pipeline generates a consistent, standardized `replication_report.txt` for every run, whether it's a new, an updated (reprocessed), or migrated experiment. This ensures that all output is easily comparable and machine-parsable.

#### Replication Report Format

Each report contains a clear header, the base query used, a human-readable analysis summary, and a machine-readable JSON block with all calculated metrics.

*Figure 14: Format for `replication_report.txt`*
{{diagram:docs/diagrams/format_replication_report.txt}}

**Date Handling by Mode:**

-   **Normal Mode**: The report title is `REPLICATION RUN REPORT` and the `Date` field shows the time of the original run.
-   **`--reprocess` Mode**: The report title is `REPLICATION RUN REPORT (YYYY-MM-DD HH:MM:SS)` with the reprocessing timestamp. The `Date` field continues to show the time of the **original** run for clear traceability.

#### Study Analysis Log Format

The final analysis script (`analyze_study_results.py`) produces a comprehensive log file detailing the full statistical analysis of the entire study. The report is structured by metric, with each section providing descriptive statistics, the ANOVA summary, post-hoc results (if applicable), and performance groupings.

*Figure 15: Format for `STUDY_analysis_log.txt`*
{{diagram:docs/diagrams/format_analysis_log.txt}}

### Key Data Formats

This section provides a summary reference for the most important data files. For complete format specifications and detailed field descriptions, see the **[📁 Data Preparation Data Dictionary](DATA_PREPARATION_DATA_DICTIONARY.md)** and **[📊 Experiment Workflow Data Dictionary](../output/EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md)**.

#### Format Summary Table

*Table 9: Summary of Key Data Formats*

| Category | File | Purpose | Key Fields |
|:---------|:-----|:--------|:-----------|
| **Input Sources** | `adb_raw_export.txt` | Raw Astro-Databank export | idADB, Name, DateTime, Place, Rodden Rating |
| | `sf_chart_export.csv` | Solar Fire chart calculations | Subject_ID, Sun, Moon, Ascendant, etc. |
| **Core Databases** | `subject_db.csv` | Cleaned & validated master database | idADB, Subject_Name, Wikipedia_URL, Birth data |
| | `personalities_db.txt` | Final experiment input database | Subject_ID, Description (5000+ chars), Metadata |
| **Configuration** | `point_weights.csv` | Astrological element weights | Point, Weight (Sun=3, Moon=3, etc.) |
| | `balance_thresholds.csv` | Classification thresholds | Category, WeakRatio, StrongRatio |
| **Intermediate** | `adb_wiki_links.csv` | Wikipedia URL mappings | idADB, Subject_Name, Wikipedia_URL |
| | `eminence_scores.csv` | LLM-generated eminence rankings | Subject_ID, Eminence_Score, Rank |
| | `ocean_scores.csv` | LLM-generated personality scores | Subject_ID, O, C, E, A, N scores |
| | `adb_eligible_candidates.txt` | Filtered subject pool | idADB, Name, Birth data (validated) |
| | `adb_final_candidates.txt` | Study-selected subjects | idADB, Name (diversity-optimized) |
| **Text Libraries** | `sf_delineations_library.txt` | Raw interpretive text from Solar Fire | Structured astrological descriptions |
| | `neutralized_delineations/*.csv` | Sanitized description components | De-jargonized text fragments |

#### Critical Formats (Detailed)

For most use cases, the summary table above is sufficient. However, three formats warrant detailed explanation due to their centrality to the framework:

##### Final Personality Database Format

{{diagram:docs/diagrams/format_data_personalities_db.txt | caption=Figure 16: Format for `personalities_db.txt` - The definitive input to all experiments}}

##### Configuration Files

{{diagram:docs/diagrams/format_data_point_weights.txt | caption=Figure 17: Format for `point_weights.csv` - Defines algorithmic weights}}

{{diagram:docs/diagrams/format_data_balance_thresholds.txt | caption=Figure 18: Format for `balance_thresholds.csv` - Sets classification rules}}

**For complete format specifications:** See the data dictionaries linked above.

---

### Related Files Reference

This section provides reference information for key data files used by the framework.

#### base_query.txt

This file contains the final prompt template used for the LLM matching task. It is the product of a systematic, multi-stage piloting process. Various prompt structures and phrasing were tested to find the version that yielded the most reliable and consistently parsable structured output from the target LLM.

#### country_codes.csv

This file provides a mapping from the country/state abbreviations used in the Astro-Databank to their full, standardized names. A sample is shown below. The complete file can be found at `data/foundational_assets/country_codes.csv`.

*Table 10: Sample from `country_codes.csv`*

| Abbreviation | Country |
| :--- | :--- |
| `AB (CAN)` | Canada |
| `AK (US)` | United States |
| `ENG (UK)` | United Kingdom |
| `FR` | France |
| `GER` | Germany |

#### Configuration Files

##### point_weights.csv

Defines the weights assigned to each astrological point when calculating balances. These weights determine the relative importance of each point in the overall personality profile.

##### balance_thresholds.csv

Defines the thresholds used to classify astrological factors as 'strong' or 'weak' based on their calculated values. These thresholds are used in the personality assembly algorithm.