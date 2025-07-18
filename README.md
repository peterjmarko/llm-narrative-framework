# Overwrite 'README.md' with the following content:

# A Resilient Framework for Large-Scale LLM Experimentation

A comprehensive research framework for conducting Large Language Model (LLM) experiments with statistical analysis, hierarchical data aggregation, and resilient, self-healing workflow management.

## 🚀 Quick Start

```powershell
# 1. Configure your experiment in config.ini

# 2. Run a complete experimental batch
# Results are saved to a new timestamped directory in output/new_experiments/
./run_experiment.ps1

# 3. Organize completed experiments into a study folder
# (e.g., move them to output/studies/My_First_Study/)

# 4. Analyze the entire study
./analyze_study.ps1 -StudyDirectory output/studies/My_First_Study

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

## 📚 Documentation & Resources

**[📖 Complete Documentation](docs/DOCUMENTATION.md)** - Detailed setup, usage, and architecture.

**[🤝 Contributing Guide](CONTRIBUTING.md)** - How to set up a development environment and contribute.

**[📋 Changelog](CHANGELOG.md)** - Version history and updates.

**[⚖️ License](LICENSE.md)** - GPL v3.0 license terms.

---

**For detailed setup instructions and comprehensive documentation, see [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)**