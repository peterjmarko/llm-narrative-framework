# A Resilient Framework for Large-Scale LLM Experimentation

A comprehensive research framework for conducting Large Language Model (LLM) experiments with statistical analysis, hierarchical data aggregation, and resilient, self-healing workflow management.

## 🚀 Quick Start

\\\powershell
# Run a complete experiment (outputs to a new timestamped directory)
.\run_experiment.ps1

# Analyze the results of all experiments in the default output folder
.\analyze_study.ps1 -StudyDirectory output/new_experiments

# View the final analysis log
Get-Content output/new_experiments/anova/STUDY_analysis_log.txt
\\\

## 📊 What This Framework Does

- **LLM Personality Matching**: Generate and process personality-based queries
- **Statistical Analysis**: ANOVA, bias detection, significance testing
- **Batch Processing**: Handle multiple experiments and replications
- **Automated Reports**: Generate comprehensive analysis reports

## 🔧 Requirements

- Python 3.11+
- PDM package manager
- PowerShell (Windows/Linux/macOS)

## 📚 Documentation

**[📖 Complete Documentation](docs/DOCUMENTATION.md)** - Detailed setup, usage, and architecture

**[🏗️ Architecture Diagrams](docs/images/)** - Visual workflow and system design

**[🤝 Contributing Guide](docs/CONTRIBUTING.md)** - Development and contribution guidelines

## 📄 Additional Resources

- **[📋 Changelog](docs/CHANGELOG.md)** - Version history and updates
- **[⚖️ License](docs/LICENSE.md)** - GPL v3.0 license terms

## 🎯 Core Workflow

1. **Generate LLM Queries** → 2. **Process Responses** → 3. **Statistical Analysis** → 4. **Reports**

Built for reproducible psychological research with LLMs.

---

**For detailed setup instructions and comprehensive documentation, see [docs/DOCUMENTATION.md](docs/DOCUMENTATION.md)**

