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
./process_study.ps1 -StudyDirectory output/studies/My_First_Study

# 5. View the final, publication-ready analysis
Get-Content output/studies/My_First_Study/anova/STUDY_analysis_log.txt
```

## ✨ Key Features

-   **Automated Batch Execution**: Run hundreds of replications with intelligent self-healing to resume interrupted experiments.
-   **Parallel LLM Sessions**: Maximizes throughput by running multiple LLM API calls concurrently, significantly speeding up data collection.
-   **Guaranteed Reproducibility**: Automatically archives the `config.ini` file with every run, permanently linking results to the exact parameters that generated them.
-   **Hierarchical Analysis & Aggregation**: Performs a bottom-up aggregation of all data, generating level-aware summary files for a fully auditable research archive.
-   **Powerful Reprocessing Engine**: Re-run data processing and analysis on existing results without repeating expensive LLM calls, making it easy to apply analysis updates or bug fixes.

## 🔧 Requirements

-   Python 3.8+
-   PDM package manager
-   PowerShell (Core) for Windows, Linux, or macOS

## 📚 Where to Go Next

This project is extensively documented to support different use cases. The resources are listed in the recommended reading order for new users.

-   **For Researchers (Replication):** The best place to start is the **[🔬 Replication Guide (article_supplementary_material.md)](article_supplementary_material.md)**. It provides a step-by-step walkthrough for reproducing the original study's findings.

-   **For a Deep Dive (Full Details):** To understand the system's architecture, run new experiments, or explore the complete methodology, see the **[📖 Framework Manual (DOCUMENTATION.md)](docs/DOCUMENTATION.md)**.

-   **To Understand the Data:** For a detailed explanation of all data files and their roles in the pipeline, see the **[🗂️ Data Dictionary (data/README.md)](data/README.md)**.

-   **For Developers (Contributing):** To contribute to the project, please see the **[🤝 Developer's Guide (CONTRIBUTING.md)](CONTRIBUTING.md)** for development setup and contribution workflows.

-   **To see what's planned and track known issues**, view the **[🗺️ Project Roadmap (ROADMAP.md)](ROADMAP.md)**.