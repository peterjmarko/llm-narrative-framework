# A Resilient Framework for Large-Scale LLM Experimentation

This document provides a high-level overview of the project. Its purpose is to introduce the framework's key features and guide users to the detailed documentation that best suits their needs.

## 🚀 Quick Start

```powershell
# 1. Configure your experiment in config.ini

# 2. Create and run a new experiment from scratch
# Results are saved to a new timestamped directory in output/new_experiments/
./new_experiment.ps1

# 3. Organize completed experiments into a study folder
# (e.g., move them to output/studies/My_First_Study/)

# 4. Process and analyze the entire study
./compile_study.ps1 -StudyDirectory output/studies/My_First_Study

# 5. View the final, publication-ready analysis
Get-Content output/studies/My_First_Study/anova/STUDY_analysis_log.txt
```

## ✨ Key Features

-   **Automated Batch Execution**: Run hundreds of replications with intelligent self-healing to resume interrupted experiments.
-   **Parallel LLM Sessions**: Maximizes throughput by running multiple LLM API calls concurrently, significantly speeding up data collection.
-   **Guaranteed Reproducibility**: Automatically archives the `config.ini` file with every run, permanently linking results to the exact parameters that generated them.
-   **Hierarchical Analysis & Aggregation**: Performs a bottom-up aggregation of all data, generating level-aware summary files for a fully auditable research archive.
-   **Powerful Reprocessing Engine**: Re-run data processing and analysis on existing results without repeating expensive LLM calls, making it easy to apply analysis updates or bug fixes.

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

-   **For Researchers (Replication):** The best place to start is the **[🔬 Replication Guide (article_supplementary_material.md)](article_supplementary_material.md)**. It provides a step-by-step walkthrough for reproducing the original study's findings.

-   **For a Deep Dive (Full Details):** To understand the system's architecture, run new experiments, or explore the complete methodology, see the **[📖 Framework Manual (DOCUMENTATION.md)](docs/DOCUMENTATION.md)**.

-   **To Understand the Data:** For a detailed explanation of all data files and their roles in the pipeline, see the **[🗂️ Data Dictionary (data/README_DATA.md)](data/README_DATA.md)**.

-   **For Developers (Contributing):** To contribute to the project, please see the **[🤝 Developer's Guide (CONTRIBUTING.md)](CONTRIBUTING.md)** for development setup and contribution workflows.

-   **To Understand the Validation Strategy:** For a detailed overview of the project's multi-layered testing strategy and validation procedures, see the **[🧪 Testing Guide (TESTING.md)](TESTING.md)**.

-   **To see what's planned and track known issues**, view the **[🗺️ Project Roadmap (ROADMAP.md)](ROADMAP.md)**.

## ⚖️ Licensing

This project uses a dual-licensing model to promote open science:

-   All **source code** is licensed under the **[GNU General Public License v3.0](LICENSE.md)**.
-   All **data, documentation, and other written content** are licensed under the **[Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/)**.

This ensures that the framework and its derivatives will always remain open-source, while also allowing the data and research to be freely shared and adapted under terms that are standard for scientific and creative works.