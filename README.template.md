# A Framework for Testing Complex Narrative Systems
 
This project provides a framework for the resilient and reproducible testing of large-scale LLM experiments with complex narrative systems. It offers a fully automated, end-to-end pipeline that manages the entire experimental workflow, from data preparation to final statistical analysis.

This README provides a high-level overview of the framework and guides new users to the detailed documentation that best suits their needs.

## 🚀 Quick Start

```
# PowerShell Commands:
# 1. Configure and run each experimental condition
# (e.g., run once with mapping_strategy = correct, then again with = random)
./new_experiment.ps1

# 2. Organize the completed experiment folders into a single study directory
# (e.g., move them to output/new_studies/My_First_Study/)

# 3. Compile and analyze the entire study
./compile_study.ps1 -StudyDirectory output/new_studies/My_First_Study

# 4. View the final, publication-ready analysis
Get-Content output/new_studies/My_First_Study/anova/STUDY_analysis_log.txt
```

## ✨ Key Features

{{grouped_figure:docs/diagrams/arch_project_overview.mmd | scale=2.5 | width=75% | caption=Project Architecture: A high-level overview of the main functional components.}}

*   **Automated Batch Execution**: Run hundreds of replications with intelligent self-healing to resume interrupted experiments.
*   **Parallel LLM Sessions**: Maximizes throughput by running multiple LLM API calls concurrently, significantly speeding up data collection.
*   **Guaranteed Reproducibility**: Automatically archives the `config.ini` file with every run, permanently linking results to the exact parameters that generated them.
*   **Hierarchical Analysis & Aggregation**: Performs a bottom-up aggregation of all data, generating level-aware summary files for a fully auditable research archive.
*   **Powerful Reprocessing Engine**: Re-run data processing and analysis on existing results without repeating expensive LLM calls, making it easy to apply analysis updates or bug fixes.

## Experimental Hierarchy

The framework organizes research into a clear hierarchy. Understanding this structure is key to using the workflow scripts correctly.

```
Study
└── Experiment (Condition A)
    ├── Replication 1
    │   ├── Trial 1
    │   ├── Trial 2
    │   └── ...
    └── Replication 2
        └── ...
└── Experiment (Condition B)
    ├── Replication 1
    │   └── ...
    └── Replication 2
        └── ...
```

-   **Study:** The highest-level grouping, representing a complete research question (e.g., comparing "correct" vs. "random" mappings).
-   **Experiment:** A complete set of runs for a single experimental condition (e.g., all runs for the "correct" mapping condition).
-   **Replication:** A single, complete run of an experiment, repeated multiple times for statistical power.
-   **Trial:** An individual matching task performed within a replication.

## The Research Workflow

The end-to-end process is designed around a clear, two-stage workflow: first, you create an **Experiment** for each condition; second, you group them into a **Study** for final analysis.

{{grouped_figure:docs/diagrams/flow_research_workflow.mmd | scale=2.5 | width=100% | caption=The End-to-End Research Workflow.}}

### Stage 1: Create Experiments for Each Condition

This stage focuses on generating the raw data. For each condition, you will configure `config.ini` and use the following scripts:

-   **`new_experiment.ps1` (Create)**: The primary script for data generation. It runs a full set of replications for one condition.
-   **`audit_experiment.ps1` (Check)**: A read-only diagnostic tool to check the status and health of an experiment.
-   **`fix_experiment.ps1` (Fix)**: If an experiment is interrupted, this script intelligently resumes it.

**Learning the Workflow**: For users new to the framework, a comprehensive interactive guided tour is available that demonstrates the complete experiment workflow with detailed explanations at each step. This Layer 4 integration test walks users through:

- Creating a 2×2 factorial experiment design (4 experiments)
- Auditing experiment health and completeness
- Simulating 4 distinct real-world failure scenarios:
  - Missing LLM responses (API interruption)
  - Corrupted analysis files (I/O errors)
  - Corrupted configuration data (metadata damage)
  - Corrupted report files (storage corruption)
- Automated detection and repair of each corruption type
- Final verification of experiment integrity

This can be accessed via `pdm run test-l4-interactive` (see the Testing Guide for details).

### Stage 2: Compile and Analyze the Study

Once you have a separate experiment directory for each of your conditions, you can analyze them together as a single study.

1.  **Organize Experiments**: Manually move all completed experiment directories into a single parent folder (e.g., `output/studies/My_First_Study/`).

2.  **Audit the Study (`audit_study.ps1`)**: Run this read-only script on your study directory to perform a consolidated health check on all experiments.

3.  **Compile the Study (`compile_study.ps1`)**: This is the final step. It aggregates all data, runs the statistical analysis, and generates the publication-ready reports and plots.

## Workflow Validation & Reliability

The experiment workflow has been comprehensively validated through integration testing that demonstrates the framework's self-healing capabilities:

### Automated Corruption Detection
The audit system can detect and classify multiple types of experiment corruption:

- **REPAIR_NEEDED**: Single-category failures (missing files, simple corruption)
- **REPROCESS_NEEDED**: Analysis corruption requiring regeneration
- **AGGREGATION_NEEDED**: Experiment-level file corruption
- **MIGRATION_NEEDED**: Complex multi-category corruption (archived functionality)

### Intelligent Repair Strategies
The repair system automatically determines the appropriate recovery strategy:

- **Session Repair**: Re-runs only failed API calls, preserving existing data
- **Analysis Regeneration**: Rebuilds analysis from raw response data
- **Configuration Restoration**: Restores corrupted config files from source parameters
- **Summary Regeneration**: Rebuilds experiment-level aggregation files

### Validation Coverage
The framework's reliability is validated through comprehensive testing that covers:
- End-to-end experiment creation and compilation workflows
- Deliberate corruption scenarios with automated recovery
- State detection accuracy across all failure modes
- Data integrity verification throughout the repair process

This ensures that researchers can trust the framework to maintain data integrity even when facing common real-world failures like network interruptions, storage errors, or process crashes.

## Project Philosophy

This framework was designed with three core principles in mind:

1.  **Promote Open Science:** In response to the replication crisis, this project provides a fully transparent, open-source, and computationally reproducible pipeline. All data, code, and documentation are publicly available to encourage verification and new research.
2.  **Provide a Method, Not an Endorsement:** This study uses astrology as a challenging "hard problem" to validate the framework's ability to detect weak signals in complex, narrative-based systems. **The goal is not to validate astrology**, but to demonstrate a robust scientific methodology.
3.  **Focus on Empirical Questions:** The framework is designed to answer a single, empirical question: is there a detectable, non-random signal in the data? The deeper philosophical implications of the findings are explicitly deferred to a separate, companion article.

## 🔧 Requirements

-   Python 3.11+
-   PDM package manager
-   PowerShell (Core) for Windows, Linux, or macOS

## 📚 Documentation Architecture

This project uses a **coordinated documentation strategy** with each document serving a specific purpose:

| Document | Primary Focus | When to Use |
|----------|---------------|-------------|
| **[📖 Framework Manual](docs/FRAMEWORK_MANUAL.md)** | Complete system architecture | Deep technical reference |
| **[📁 Data Preparation](data/DATA_PREPARATION_DATA_DICTIONARY.md)** | Input data pipeline | Understanding data sources |
| **[📊 Experiment Workflow](output/EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md)** | Output & results structure | Understanding experimental results |
| **[🔬 Replication Guide](docs/REPLICATION_GUIDE.md)** | Step-by-step reproduction | Reproducing study findings |

## 📚 Where to Go Next

This project is extensively documented to support different use cases. The resources are listed in the recommended reading order for new users.

-   **For Researchers (Replication):** The best place to start is the **[🔬 Replication Guide (docs/REPLICATION_GUIDE.md)](docs/REPLICATION_GUIDE.md)**. It provides a step-by-step walkthrough for reproducing the original study's findings.

-   **For a Deep Dive (Full Details):** To understand the system's architecture, run new experiments, or explore the complete methodology, see the **[📖 Framework Manual (docs/FRAMEWORK_MANUAL.md)](docs/FRAMEWORK_MANUAL.md)**.

-   **To Understand the Data:** For detailed explanations of all data files:
    - **[📁 Data Preparation Pipeline (docs/DATA_PREPARATION_DATA_DICTIONARY.md)](docs/DATA_PREPARATION_DATA_DICTIONARY.md)** - Input data and preparation workflow
    - **[📊 Experiment Workflow (output/EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md)](output/EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md)** - Output structure and experimental results

-   **For Developers (Contributing):** To contribute to the project, please see the **[🤝 Developer's Guide (DEVELOPERS_GUIDE.md)](DEVELOPERS_GUIDE.md)** for development setup and contribution workflows.

-   **To Understand the Validation Strategy:** For a detailed overview of the project's testing strategy, see the **[🧪 Testing Guide (docs/TESTING_GUIDE.md)](docs/TESTING_GUIDE.md)**.

-   **To see what's planned and track known issues**, view the **[🗺️ Project Roadmap (docs/ROADMAP.md)](docs/ROADMAP.md)**.

## 📦 Out of Scope for Publication

To streamline the framework for its initial publication, several advanced features for managing the study workflow have been deferred to a future release. The source code for these features has been preserved in the `_archive/` directory of the repository for future development.

Archived features include:

*   **Automated Multi-Experiment Studies (`new_study.ps1`)**: A top-level orchestrator for running a matrix of experiments automatically.
*   **Automated Study Repair (`fix_study.ps1`)**: A wrapper to diagnose and fix all experiments within a study.
*   **Factorial Study Generation (`generate_factorial_commands.ps1`)**: A generator tool for creating factorial study specifications.
*   **Development Synchronization (`sync_project_assets.py`)**: Efficient project asset synchronization for Claude development workflows.
*   **Data Migration Tools (`migrate_*.ps1`)**: Workflows for upgrading legacy or severely corrupted experimental data.

## ⚖️ Licensing

This project uses a dual-licensing model to promote open science:

-   All **source code** is licensed under the **[GNU General Public License v3.0](LICENSE.md)**.
-   All **data, documentation, and other written content** are licensed under the **[Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/)**.

This ensures that the framework and its derivatives will always remain open-source, while also allowing the data and research to be freely shared and adapted under terms that are standard for scientific and creative works.