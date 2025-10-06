---
title: "Replication Guide"
subtitle: "Supplementary Material for 'A Framework for the Computationally Reproducible Testing of Complex Narrative Systems'"
author: "Peter J. Marko"
date: "[Date]"
---

This document is the **Replication Guide** that provides supplementary material to the main article, "A Framework for the Computationally Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology." Its purpose is to serve as a detailed, step-by-step guide for researchers who wish to replicate or extend the original study's findings. For detailed information on the components of the framework, please refer to the **[📖 Framework Manual (docs/FRAMEWORK_MANUAL.md)](docs/FRAMEWORK_MANUAL.md)**.

This guide defines the three primary replication paths (Direct, Methodological, and Conceptual) and provides a complete walkthrough of the end-to-end workflow, from initial setup and data preparation to running the main experiments and producing the final statistical analysis.

{{toc}}

## Project Overview

The framework is organized into four primary components that work together to enable reproducible research on complex narrative systems. The production codebase is structured around a clear separation of concerns, with user-facing orchestration scripts executing core logic modules that operate on well-defined data artifacts.

{{grouped_figure:docs/diagrams/arch_project_overview.mmd | scale=2.0 | width=100% | caption=Figure S1: Project Architecture Overview. The framework consists of four main components: User-Facing Interface, Core Logic, Project Governance, and Data & Artifacts.}}

The **User-Facing Interface** comprises PowerShell orchestration scripts that provide a simple, consistent way to execute complex workflows. These scripts handle parameter validation, error recovery, and progress tracking, allowing researchers to focus on research questions rather than implementation details.

The **Core Logic** contains the production Python scripts in the `src/` directory that implement the actual data processing, experiment execution, and analysis algorithms. These modules are designed to be modular, testable, and reusable across different research contexts.

The **Project Governance** component includes documentation, diagrams, the validation test suite, and developer utilities that ensure the framework maintains high standards of quality, reproducibility, and transparency.

The **Data & Artifacts** component manages all inputs and outputs, including source data, generated experiments, analysis reports, and project-level documentation that provides provenance for all research artifacts.

## Research Paths

The framework supports three distinct research paths: direct, methodological, and conceptual replication.

**Path 1: Direct Replication (Computational Reproducibility)**
To ensure computational reproducibility of the original findings, researchers should use the static data files and randomization seeds included in this repository. This path validates that the framework produces the same statistical results.

**Path 2: Methodological Replication (Testing Robustness)**
To test the robustness of the findings, researchers can use the framework's automated tools to generate a fresh dataset from the live Astro-Databank (ADB). The instructions below detail this workflow, which is organized into four main stages.

**Path 3: Conceptual Replication (Extending the Research)**
To extend the research, researchers can modify the framework itself, for example, by using different LLMs for the matching task or altering the analysis scripts.

For a direct or methodological replication, it is crucial to use the exact models and versions from the original study. All models were accessed via the **OpenRouter API**. See Appendix C for the complete list of models used.

## Production Codebase

The production codebase implements two principal workflows that form the backbone of the research process: the Data Preparation Pipeline and the Experiment & Study Workflow. These workflows are sequentially dependent but architecturally distinct, with the data preparation pipeline creating the foundational datasets that the experiment workflow consumes.

> **Note on the Principal Workflows:** Researchers wishing to experience the workflows in detail are advised to refer to the interactive Guided Tours. These step-by-step walkthroughs are an excellent way to learn how the various scripts work together. Full instructions for running the tours can be found in the project's **[🧪 Testing Guide (docs/TESTING_GUIDE.md)](docs/TESTING_GUIDE.md)**.

### Data Preparation Pipeline

The **Data Preparation Pipeline** is a fully automated, multi-stage workflow that transforms raw data from external sources (Astro-Databank, Wikipedia) into the curated `personalities_db.txt` file used in experiments. This pipeline implements sophisticated filtering, scoring, and selection algorithms to create a high-quality, diverse dataset of personality profiles.

{{grouped_figure:docs/diagrams/flow_data_preparation_pipeline.mmd | scale=2.0 | width=35% | caption=Figure S2: Data Preparation Pipeline. The pipeline processes raw astrological data from ADB through multiple stages to create personalities_db.txt.}}

### Experiment & Study Workflow

The **Experiment & Study Workflow** consumes the prepared data to generate experimental results across multiple conditions, then compiles these results into comprehensive statistical analyses. This workflow supports factorial experimental designs, automated result aggregation, and publication-ready statistical reporting.

The two workflows are connected through well-defined data interfaces, with the output of the data preparation pipeline serving as the input to the experiment workflow. This modular design allows researchers to update or extend either workflow independently while maintaining reproducibility.

{{grouped_figure:docs/diagrams/flow_experiment_study_workflow.mmd | scale=2.0 | width=35% | caption=Figure S3: Experiment & Study Workflow. The workflow uses personalities_db.txt to run experiments and compile study results.}}

## Replication Procedures

### Direct Replication Procedure

This procedure validates computational reproducibility by using the static data files and randomization seeds included in this repository to verify that the framework produces the same statistical results as the original study.

1. **Set Up Environment**: Follow the setup instructions in Appendix A.1.

2. **Verify Configuration**: Ensure `config.ini` matches the original study parameters (see Appendix A.1).

3. **Run Experiments**: Execute the experiments using the provided static data:
   ```powershell
   # For each experimental condition
   ./new_experiment.ps1
   ```

4. **Compile Results**: Once all experiments are complete:
   ```powershell
   ./compile_study.ps1 -StudyDirectory "output/studies/Original_Study"
   ```

5. **Compare Results**: Verify your results match the reported findings.

### Methodological Replication Procedure

This procedure tests the robustness of the findings by using the framework's automated tools to generate a fresh dataset from the live Astro-Databank, allowing researchers to verify that the results are not an artifact of a specific dataset.

1. **Set Up Environment**: Follow the setup instructions in Appendix A.2.

2. **Generate Fresh Dataset**: Create a new dataset from the live Astro-Databank:
   ```powershell
   ./prepare_data.ps1
   ```

3. **Configure Experiments**: Update `config.ini` for your experimental design.

4. **Run Experiments**: Execute the experiments with your new dataset:
   ```powershell
   # For each experimental condition
   ./new_experiment.ps1
   ```

5. **Compile Results**: Once all experiments are complete:
   ```powershell
   ./compile_study.ps1 -StudyDirectory "output/studies/Methodological_Replication"
   ```

6. **Compare Results**: Compare your results with the original study to assess robustness.

### Conceptual Replication Procedure

This procedure extends the research by modifying the framework itself, enabling researchers to test new hypotheses, explore alternative methodologies, or apply the framework to entirely different research questions.

1. **Set Up Environment**: Follow the setup instructions in Appendix A.3.

2. **Modify Framework**: Implement your conceptual extensions (see Section 6).

3. **Generate Dataset**: Create a dataset appropriate for your modified framework:
   ```powershell
   # May use prepare_data.ps1 or custom scripts
   ```

4. **Configure Experiments**: Update `config.ini` for your experimental design.

5. **Run Experiments**: Execute the experiments with your modified framework:
   ```powershell
   # For each experimental condition
   ./new_experiment.ps1
   ```

6. **Compile Results**: Once all experiments are complete:
   ```powershell
   ./compile_study.ps1 -StudyDirectory "output/studies/Conceptual_Replication"
   ```

7. **Analyze Results**: Interpret your findings in the context of your conceptual extensions.

## Suggestions for Future Research

Conceptual replication offers numerous opportunities to extend the research framework. These innovations can be categorized into three main types:

- **Methodological Parameter Innovations**: Modifications to the core algorithms, models, and analytical approaches used in the framework
- **Operational Parameter Innovations**: Changes to the data sources, software tools, and infrastructure that support the research process
- **Narrative Parameter Innovations**: Applications to entirely different signal systems, cultural contexts, or temporal domains

### Methodological Parameter Innovations

**LLM Substitutions:**
- Use different LLMs for: eminence scoring, OCEAN scoring, neutralization, and evaluation
- Incorporate thinking models (e.g., OpenAI o1, o3 series) with appropriate prompt adjustments
- Compare performance across model architectures (open-source vs. proprietary)

**Candidate Selection Modifications:**
- Implement alternative qualification criteria (e.g., different eminence thresholds)
- Use different selection algorithms (e.g., clustering-based instead of variance-based)
- Apply different personality diversity metrics

**Astrological Parameter Variations:**
- Include additional chart points (e.g., lunar nodes, Chiron, asteroids)
- Use different house systems (e.g., Placidus, Koch, Equal)
- Incorporate aspects and midpoints in the personality generation
- Experiment with different weighting schemes for planetary influences

### Operational Parameter Innovations

**Alternative Data Sources:**
- Use different biographical databases (e.g., Wikipedia directly, Library of Congress)
- Incorporate non-Western astrological traditions
- Apply to different populations (e.g., contemporary figures, non-famous individuals)

**Alternative Software Tools:**
- Use different astrological software (e.g., Sirius, Solar Fire Gold, Astro Gold)
- Implement custom calculation engines for astrological factors
- Explore open-source astrological calculation libraries

**Alternative Infrastructure:**
- Use different LLM providers (e.g., Anthropic Claude, OpenAI directly, Hugging Face)
- Implement custom model routing logic
- Use different API aggregation services

### Narrative Parameter Innovations

**Alternative Signal Systems:**
- Replace astrology with other symbolic systems (e.g., numerology, tarot, enneagram)
- Apply to different personality theories (e.g., MBTI, Socionics, Big Five)
- Test non-personality narrative systems (e.g., historical patterns, literary analysis)

**Cross-Cultural Applications:**
- Apply the framework to non-Western personality systems
- Test cultural variations in narrative expression
- Explore universal vs. culture-specific patterns

**Temporal Extensions:**
- Test whether patterns change across historical periods
- Apply to longitudinal data tracking
- Explore generational shifts in narrative expression

These innovations can be combined in various ways to create novel research questions while maintaining the rigorous methodological framework established in the original study.

## Appendices

### Appendix A: Setup and Configuration by Replication Path

#### A.1 Direct Replication Setup

**Software Requirements:**
- Windows operating system
- PowerShell 7.0 or higher
- Git
- PDM (Python Dependency Manager)

**Accounts and Services:**
- OpenRouter account with sufficient funds (approximately $140 for full study)
- No Astro-Databank account required (using static data)

**Installation Steps:**
1. Install PDM (one-time setup):
   ```bash
   pip install --user pdm
   ```

2. Clone repository and install dependencies:
   ```bash
   git clone [repository-url]
   cd llm-narrative-framework
   pdm install -G dev
   ```

3. Configure API key:
   ```bash
   # Create .env file with OpenRouter API key
   echo "OPENROUTER_API_KEY=your-actual-api-key" > .env
   ```

4. Verify configuration:
   ```bash
   # Check that config.ini matches original study parameters
   cat config.ini
   ```

#### A.2 Methodological Replication Setup

**All requirements from A.1 plus:**

**Additional Accounts and Services:**
- Astro-Databank account at astro.com
- Sufficient OpenRouter funds for data generation (additional $50-100)

**Additional Configuration:**
1. Configure Astro-Databank credentials in `.env`:
   ```
   ADB_USERNAME=your-astro-username
   ADB_PASSWORD=your-astro-password
   ```

2. Verify data generation settings in `config.ini`:
   ```ini
   [DataGeneration]
   bypass_candidate_selection = false
   cutoff_search_start_point = 3500
   smoothing_window_size = 800
   ```

#### A.3 Conceptual Replication Setup

**All requirements from A.1 and A.2 as needed, plus:**

**Additional Software (depending on innovation):**
- Alternative astrological software (if changing from Solar Fire)
- Custom development tools (if implementing new algorithms)
- Additional Python packages (add to pyproject.toml)

**Additional Configuration:**
- Custom configuration parameters as needed for your conceptual extensions
- Potential modifications to data structures and file formats
- Additional API keys or services as required by your innovations

### Appendix B: Troubleshooting Quick Reference

| Issue | Solution |
| :--- | :--- |
| **`pdm` command not found** | Use `python -m pdm` as an alternative |
| **API Errors during experiment** | Run `fix_experiment.ps1` to resume from failures |
| **Permission Denied with .docx** | Close files in Microsoft Word before rebuilding |
| **`git` command not found** | Install Git from git-scm.com |
| **All LLM sessions fail** | Verify model names and API credentials |
| **Repair process loops** | System limits retries to 3 cycles automatically |

For detailed troubleshooting, see the **[📖 Framework Manual (docs/FRAMEWORK_MANUAL.md)](docs/FRAMEWORK_MANUAL.md)**.

### Appendix C: Models and Experimental Design

#### Models Used in the Original Study

| Purpose | Model Name | API Identifier |
| :--- | :--- | :--- |
| Eminence Scoring (LLM A) | OpenAI GPT-5 | `openai/gpt-5-chat` |
| OCEAN Scoring (LLM B) | Anthropic Claude 4 Sonnet | `anthropic/claude-4-sonnet` |
| Neutralization (LLM C) | Google Gemini 2.5 Pro | `google/gemini-2.5-pro` |
| Evaluation (LLM D1) | Meta Llama 3.3 70B | `meta-llama/llama-3.3-70b-instruct` |
| Evaluation (LLM D2) | Google Gemini 2.5 Flash Lite | `google/gemini-2.5-flash-lite` |
| Evaluation (LLM D3) | OpenAI GPT-4.1 Nano | `openai/gpt-4.1-nano` |

*Access Dates for LLMs: October 2025*

#### Experimental Design Reference

**Original Study Design:**
- 2×3×3 factorial design (18 conditions)
- 30 replications per condition
- 80 trials per replication
- Total: 43,200 trials

**Factors:**
- Mapping Strategy: correct, random
- Group Size (k): 7, 10, 14
- Model: 3 low-cost, high-reliability models

**Statistical Analysis:**
- Three-Way Repeated Measures ANOVA
- Effect size measures (η², Cohen's d)
- Post-hoc tests (Tukey HSD)
- Bayesian analysis (Bayes Factor)