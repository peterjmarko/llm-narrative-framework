# A Framework for Testing Complex Narrative Systems
 
This project provides a framework for the resilient and reproducible testing of large-scale LLM experiments with complex narrative systems. It offers a fully automated, end-to-end pipeline that manages the entire experimental workflow, from data preparation to final statistical analysis.

This README provides a high-level overview of the framework and guides new users to the detailed documentation that best suits their needs.

## 📚 Documentation Map

{{grouped_figure:docs/diagrams/documentation_map.mmd | scale=2.0 | width=80% | caption=Navigate to the documentation that best matches your needs.}}

## 🚀 Quick Start

**Prerequisites:** Python 3.11+, PDM, PowerShell (Core)
```powershell
# 1. Install PDM (one-time setup)
pip install --user pdm

# 2. Install project dependencies
pdm install -G dev

# 3. Configure API key
#    Create a .env file in the project root with:
#    OPENROUTER_API_KEY=sk-or-your-key-here

# 4. Configure your experiment in config.ini [Study] section
#    See the "Configuring Your First Experiment" section below for details.

# 5. Run the interactive experiment wizard
./new_experiment.ps1

# 6. Organize completed experiments into a study folder
#    Move all experiment_YYYYMMDD_HHMMSS folders into one directory:
#    output/studies/My_First_Study/

# 7. Compile and analyze the entire study
./compile_study.ps1 -StudyDirectory output/studies/My_First_Study

# 8. View the final, publication-ready analysis
Get-Content output/studies/My_First_Study/anova/STUDY_analysis_log.txt
```

> **Note:** PowerShell scripts (`.ps1`) run directly. Use `pdm run <command>` for Python maintenance scripts. For detailed setup, see the [Framework Manual](docs/FRAMEWORK_MANUAL.md).

## 🎯 Project Philosophy

This framework embodies a **"trust but verify"** approach to computational research:

- **Resilient by Design**: Automatically resumes from failures, maintaining data integrity through multi-level validation
- **Reproducibility First**: Every experimental run archives its complete configuration, ensuring results can always be traced back to exact parameters
- **Human-Readable Throughout**: All intermediate outputs are in accessible formats (CSV, TXT, JSON) for inspection and verification
- **Hierarchical Validation**: Each level (trial, replication, experiment, study) performs independent validation before aggregation

The framework prioritizes **transparency and auditability** over black-box automation, ensuring researchers maintain full visibility into and control over the experimental process.

**Bottom line:** If you can read the CSV files and understand the log files, you can trust the results.

{{grouped_figure:docs/diagrams/arch_project_overview.mmd | scale=2.5 | width=75% | caption=Project Architecture: A high-level overview of the main functional components.}}

## ✨ Key Features

*   **Automated Batch Execution**: Run hundreds of replications with intelligent self-healing to resume interrupted experiments.
*   **Parallel LLM Sessions**: Maximizes throughput by running multiple LLM API calls concurrently, significantly speeding up data collection.
*   **Guaranteed Reproducibility**: Automatically archives the `config.ini` file with every run, permanently linking results to the exact parameters that generated them.
*   **Hierarchical Analysis & Aggregation**: Performs a bottom-up aggregation of all data, generating level-aware summary files for a fully auditable research archive.
*   **Powerful Reprocessing Engine**: Re-run data processing and analysis on existing results without repeating expensive LLM calls, making it easy to apply analysis updates or bug fixes.
*   **Cost-Effective**: Intelligent caching and repair mechanisms minimize redundant API calls, reducing experimental costs

## ⚙️ Configuring Your First Experiment

The framework uses an **interactive wizard** that guides you through selecting experimental conditions. This ensures consistent parameter tracking across your entire study.

1. **Define Study Parameters** in `config.ini`:
```ini
   [Study]
   # Study-level experimental design parameters
   mapping_strategy = correct, random
   group_size = 7, 10, 14
   model_name = meta-llama/llama-3.3-70b-instruct, google/gemini-2.5-flash-lite
   
   [Experiment]
   num_replications = 30
   num_trials = 80
```

2. **Run the Interactive Wizard**:
```powershell
   ./new_experiment.ps1
```
   
   The script displays available options and prompts for selection:
```
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
     [1] meta-llama/llama-3.3-70b-instruct
     [2] google/gemini-2.5-flash-lite
   
   Select Mapping Strategy [1-2]: 1
   Select Group Size [1-3]: 2
   Select Model [1-2]: 1
   
   Selected Configuration:
     Mapping Strategy: correct
     Group Size: 10
     Model: meta-llama/llama-3.3-70b-instruct
```

3. **Automatic Configuration**: Your selections are automatically written to `[Experiment]` and `[LLM]` sections before experiment creation. Each experiment's parameters are logged to `output/studies/study_creation_log.txt` for tracking your complete study design.

4. **Repeat for Each Condition**: Run `new_experiment.ps1` again to create additional experiments with different parameter combinations.

> **Note:** If the `[Study]` section is empty, the script uses values directly from `[Experiment]` and `[LLM]` sections (non-interactive mode).

For complete configuration options, see the [Framework Manual](docs/FRAMEWORK_MANUAL.md).

## 🔄 Understanding the Workflow

The framework's structure and workflow are designed to be logical and hierarchical.

### Experimental Hierarchy

Understanding the organizational structure is essential for navigating your results:
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

-   **Study:** The highest-level grouping, representing a complete research question.
-   **Experiment:** Runs for a single experimental condition.
-   **Replication:** A single, complete run of an experiment.
-   **Trial:** An individual matching task within a replication.

### The Research Workflow

{{grouped_figure:docs/diagrams/flow_research_workflow.mmd | scale=2.5 | width=70% | caption=The End-to-End Research Workflow.}}

The framework follows a two-stage process:

**Stage 1: Create Experiments**
- Configure conditions in `config.ini` and run `new_experiment.ps1` for each experimental condition
- Use `audit_experiment.ps1` to verify completion
- Use `fix_experiment.ps1` to resume interrupted experiments

**Stage 2: Compile Study**
- Organize all experiment directories into a study folder (e.g., `output/studies/My_First_Study/`)
- Run `compile_study.ps1` to aggregate data and perform statistical analysis

For a comprehensive interactive tutorial demonstrating the complete workflow with real failure scenarios and automated repair, see the [Testing Guide](docs/TESTING_GUIDE.md) (`pdm run test-l4-interactive`).

## 🎯 What's Next?

**For Researchers:** Start with the [Replication Guide](docs/REPLICATION_GUIDE.md) to reproduce the original study, or dive into the [Framework Manual](docs/FRAMEWORK_MANUAL.md) to design your own experiments.

**For Developers:** See the [Developer's Guide](DEVELOPERS_GUIDE.md) for setup, testing, and contribution workflows.

**For Data Analysis:** Explore the data dictionaries to understand the complete pipeline from raw input to final statistical analysis.

## 📚 Documentation Guide

### Quick Navigation by Role

**🔬 Researchers (Replication)**
- Start here: **[Replication Guide](docs/REPLICATION_GUIDE.md)** - Step-by-step walkthrough for reproducing the original study

**🔧 Researchers (New Experiments)**
- Start here: **[Framework Manual](docs/FRAMEWORK_MANUAL.md)** - Complete system architecture and methodology for running new experiments

**💾 Data Analysis**
- **[Data Preparation Data Dictionary](docs/DATA_PREPARATION_DATA_DICTIONARY.md)** - Input data and preparation pipeline
- **[Experiment Workflow Data Dictionary](docs/EXPERIMENT_WORKFLOW_DATA_DICTIONARY.md)** - Output structure and experimental results

**👨‍💻 Developers**
- **[Developer's Guide](DEVELOPERS_GUIDE.md)** - Development setup, contribution workflows, and project conventions
- **[Testing Guide](docs/TESTING_GUIDE.md)** - Validation strategy and test suite details

**📋 Project Planning**
- **[Project Roadmap](docs/PROJECT_ROADMAP.md)** - Planned features and known issues

> **💡 Tip:** All documentation is available in both Markdown (.md) and Word (.docx) formats. Word documents can be found in `docs/word_docs/`.

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