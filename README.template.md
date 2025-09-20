# A Framework for Testing Complex Narrative Systems

This project provides a framework for the resilient and reproducible testing of large-scale LLM experiments with complex narrative systems. It offers a fully automated, end-to-end pipeline that manages the entire experimental lifecycle, from data preparation to final statistical analysis.

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

## Project Philosophy

This framework was designed with three core principles in mind:

1.  **Promote Open Science:** In response to the replication crisis, this project provides a fully transparent, open-source, and computationally reproducible pipeline. All data, code, and documentation are publicly available to encourage verification and new research.
2.  **Provide a Method, Not an Endorsement:** This study uses astrology as a challenging "hard problem" to validate the framework's ability to detect weak signals in complex, narrative-based systems. **The goal is not to validate astrology**, but to demonstrate a robust scientific methodology.
3.  **Focus on Empirical Questions:** The framework is designed to answer a single, empirical question: is there a detectable, non-random signal in the data? The deeper philosophical implications of the findings are explicitly deferred to a separate, companion article.

## 🔧 Requirements

-   Python 3.11+
-   PDM package manager
-   PowerShell (Core) for Windows, Linux, or macOS

## 📚 Where to Go Next

This project is extensively documented to support different use cases. The resources are listed in the recommended reading order for new users.

-   **For Researchers (Replication):** The best place to start is the **[🔬 Replication Guide (docs/article_supplementary_material.md)](docs/article_supplementary_material.md)**. It provides a step-by-step walkthrough for reproducing the original study's findings.

-   **To Understand the Workflow:** For a high-level guide to the `Create -> Check -> Fix -> Compile` workflow, see the **[🚀 Lifecycle Guide (docs/LIFECYCLE_GUIDE.md)](docs/LIFECYCLE_GUIDE.md)**.

-   **For a Deep Dive (Full Details):** To understand the system's architecture, run new experiments, or explore the complete methodology, see the **[📖 Framework Manual (docs/DOCUMENTATION.md)](docs/DOCUMENTATION.md)**.

-   **To Understand the Data:** For a detailed explanation of all data files and their roles in the pipeline, see the **[🗂️ Data Dictionary (data/DATA_DICTIONARY.md)](data/DATA_DICTIONARY.md)**.

-   **For Developers (Contributing):** To contribute to the project, please see the **[🤝 Developer's Guide (CONTRIBUTING.md)](CONTRIBUTING.md)** for development setup and contribution workflows.

-   **To Understand the Validation Strategy:** For a detailed overview of the project's testing strategy, see the **[🧪 Testing Guide (docs/TESTING.md)](docs/TESTING.md)**.

-   **To see what's planned and track known issues**, view the **[🗺️ Project Roadmap (docs/ROADMAP.md)](docs/ROADMAP.md)**.

## 📦 Out of Scope for Publication

To streamline the framework for its initial publication, several advanced features for managing the study lifecycle have been deferred to a future release. The source code for these features has been preserved in the `_archive/` directory of the repository for future development.

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