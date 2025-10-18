---
title: "Replication Guide"
subtitle: "Supplementary Material for 'A Framework for the Computationally Reproducible Testing of Complex Narrative Systems'"
author: "Peter J. Marko"
date: "[Date]"
---

This document is the **Replication Guide** that provides supplementary material to the main article, "A Framework for the Computationally Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology." Its purpose is to serve as a detailed, step-by-step guide for researchers who wish to replicate or extend the original study's findings. For detailed information on the components of the framework, please refer to the **[📖 Framework Manual](docs/FRAMEWORK_MANUAL.md)**.

This guide defines the three primary replication paths (direct, methodological, and conceptual) and provides a complete walkthrough of the end-to-end workflow, from initial setup and data preparation to running the main experiments and producing the final statistical analysis.

{{toc}}

> **📘 Note on Terminology:** This guide uses "replication" in two distinct contexts:
> 
> 1. **Research Replication** (this document's focus): The scientific practice of reproducing a study to verify findings—addressing the widely-discussed "replication crisis" in research
> 2. **Experimental Replication** (framework terminology): A single complete run of an experiment, repeated multiple times (typically 30×) for statistical power
> 
> Context makes the distinction clear: "Direct Replication Procedure" refers to reproducing the study, while "30 replications per condition" refers to repeated experimental runs.

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

### Choosing Your Research Path

The following table summarizes key differences to help you select the appropriate replication path:

| Aspect | Direct Replication | Methodological Replication | Conceptual Replication |
|--------|-------------------|---------------------------|------------------------|
| **Data Source** | Static files (`data/`) | Fresh from live ADB | Custom/Modified |
| **Randomization Seeds** | Fixed (from config) | Fresh | Custom |
| **Framework Code** | Unchanged | Unchanged | Modified |
| **Primary Purpose** | Verify computational reproducibility | Test statistical robustness | Extend research questions |
| **Time Required** | Hours | Days | Weeks to months |
| **Estimated Cost** | ~$150 | ~$200-240 | Variable |
| **Prerequisites** | Basic setup (A.1) | Basic + ADB + Solar Fire (A.2) | Full dev environment (A.3) |
| **Output** | Bit-for-bit match validation | Robustness assessment | New findings |

**Quick Decision Guide:**
- **Choose Direct** if you want to verify the framework produces identical results
- **Choose Methodological** if you want to test whether findings hold with fresh data
- **Choose Conceptual** if you want to test new hypotheses or apply the framework to new domains

## Production Codebase

The production codebase implements two principal workflows that form the backbone of the research process: the Data Preparation Pipeline and the Experiment & Study Workflow. These workflows are sequentially dependent but architecturally distinct, with the data preparation pipeline creating the foundational datasets that the experiment workflow consumes.

> **Note on the Principal Workflows:** Researchers wishing to experience the workflows in detail are advised to refer to the interactive Guided Tours. These step-by-step walkthroughs are an excellent way to learn how the various scripts work together. Full instructions for running the tours can be found in the project's **[🧪 Testing Guide](docs/TESTING_GUIDE.md)**.

### Data Preparation Pipeline

The **Data Preparation Pipeline** is a fully automated, multi-stage workflow that transforms raw data from external sources (Astro-Databank, Wikipedia) into the curated `personalities_db.txt` file used in experiments. This pipeline implements sophisticated filtering, scoring, and selection algorithms to create a high-quality, diverse dataset of personality profiles.

{{grouped_figure:docs/diagrams/flow_prep_pipeline.mmd | scale=2.0 | width=35% | caption=Figure S2: Data Preparation Pipeline. The pipeline processes raw astrological data from ADB through multiple stages to create personalities_db.txt.}}

### Experiment & Study Workflow

The **Experiment & Study Workflow** consumes the prepared data to generate experimental results across multiple conditions, then compiles these results into comprehensive statistical analyses. This workflow supports factorial experimental designs, automated result aggregation, and publication-ready statistical reporting.

The two workflows are connected through well-defined data interfaces, with the output of the data preparation pipeline serving as the input to the experiment workflow. This modular design allows researchers to update or extend either workflow independently while maintaining reproducibility.

{{grouped_figure:docs/diagrams/flow_experiment_study_workflow.mmd | scale=2.0 | width=35% | caption=Figure S3: Experiment & Study Workflow. The workflow uses personalities_db.txt to run experiments and compile study results.}}

## Replication Procedures

### Direct Replication Procedure

This procedure validates computational reproducibility by using the static data files (located in the `data/` subdirectory) and randomization seeds included in this repository to verify that the framework produces the same statistical results as the original study.

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

2. **Generate Fresh Dataset**: Create a new dataset from the live Astro-Databank database:
```powershell
   # Run the entire data preparation workflow
    pdm run prep-data
    # or simply:
    pdm prep-data
```
This executes `prepare_data.ps1`, which is a PowerShell wrapper that orchestrates the **14 distinct steps** of the data preparation pipeline (including automated Python scripts and manual processes). This script automatically checks the state of the pipeline and resumes from the first incomplete step, and it will pause with clear instructions when a manual user action is required.

It is highly recommended that you first run this module in read-only mode to produce a report on current data files (use the '-ReportOnly' parameter). Subsequently, it is advisable to step through execution in interactive mode to understand what can be expected on a normal run (use the '-Interactive' paramater). Once the script's operation is clear, use the '-Force' parameter to overwrite existing data.

3. **Verify Configuration**: Ensure `config.ini` matches the original study parameters (see Appendix A.1).

4. **Run Experiments**: Execute the experiments with interactive parameter selection:
```powershell
   # For each experimental condition (repeat 42 times for 2×3×7 design)
   ./new_experiment.ps1
```
   
   The script will display an interactive menu for selecting experimental conditions. Alternatively, manually configure `config.ini` before each run (see Appendix A.2 for details).

5. **Compile Results**: Once all experiments are complete:
```powershell
   ./compile_study.ps1 -StudyDirectory "output/studies/Methodological_Replication"
```

6. **Compare Results**: Compare your results with the original study to assess robustness.

### Conceptual Replication Procedure

This procedure extends the research by modifying the framework itself, enabling researchers to test new hypotheses, explore alternative methodologies, or apply the framework to entirely different research questions.

1. **Set Up Environment**: Follow the setup instructions in Appendix A.3.

2. **Modify Framework**: Implement your conceptual extensions (see "Suggestions for Future Research" section).

3. **Generate Dataset**: Create a dataset appropriate for your modified framework:
```powershell
   # May use prepare_data.ps1 or custom scripts
```

4. **Configure Study Design**: Update `config.ini` for your experimental design (example):
```ini
   [Study]
   mapping_strategy = your, custom, values
   group_size = your, custom, values
   model_name = your, custom, models
   temperature = your, custom, values
   ...
   
   [Experiment]
   num_replications = your custom value
   num_trials = your custom value

   [LLM]
   max_tokens = your custom value
   max_parallel_sessions = your custom value
```

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

## Expected Results for Validation

This section provides baseline performance metrics from the framework's validation testing to help researchers verify their replication results.

### Performance Benchmarks

The framework has been validated using controlled test conditions with known ground truth. Researchers should expect performance metrics within these ranges when using similar experimental parameters:

**For Correct Mappings (signal present):**
- Mean MRR: 0.15-0.25 (vs chance ~0.10-0.25 depending on k)
- Top-1 Accuracy: 8-15% (vs chance ~7-14% depending on k)
- Top-3 Accuracy: 20-35% (vs chance ~20-43% depending on k)

**For Random Mappings (null condition):**
- Performance should approximate chance levels
- Statistical tests should show p > 0.05 for most metrics

### Chance Level Calculations

The framework calculates theoretical chance levels based on group size (k):

- **MRR Chance**: `(1/k) × Σ(1/j)` for j=1 to k (harmonic mean formula)
- **Top-1 Accuracy Chance**: `1/k`
- **Top-3 Accuracy Chance**: `min(3, k)/k`
- **Mean Rank Chance**: `(k + 1)/2`

### Quality Control Thresholds

Experiments must meet these minimum standards for inclusion in analysis:

- **Minimum valid responses**: 25 per replication (configurable in `config.ini`)
- **Parsing success rate**: >92% for k=14, >95% for k≤10
- **Expected valid responses** (with 80 trials):
  - k=7: ~77 valid responses (96% success rate)
  - k=10: ~76 valid responses (95% success rate)
  - k=14: ~74 valid responses (93% success rate)

### Validation Checklist

✓ Performance metrics fall within expected ranges
✓ Chance level calculations match theoretical values
✓ Random mapping conditions approximate chance performance
✓ Statistical significance patterns align with experimental design
✓ Parsing success rates meet minimum thresholds

Significant deviations from these benchmarks may indicate configuration issues, API problems, or changes in model behavior. See the **[📖 Framework Manual](docs/FRAMEWORK_MANUAL.md)** for troubleshooting guidance.

## Suggestions for Future Research

Conceptual replication offers numerous opportunities to extend the research framework. These innovations can be categorized into three main types:

- **Methodological Parameter Innovations**: Modifications to the core algorithms, models, and analytical approaches (e.g., using different LLMs for scoring/evaluation, alternative candidate selection algorithms, different astrological parameters)
- **Operational Parameter Innovations**: Changes to the data sources, software tools, and infrastructure (e.g., different biographical databases, alternative astrological software, different LLM providers)
- **Narrative Parameter Innovations**: Applications to entirely different signal systems, cultural contexts, or temporal domains (e.g., numerology, MBTI, cross-cultural applications, longitudinal studies)

For detailed examples and guidance on each innovation type, see the **[📖 Framework Manual](docs/FRAMEWORK_MANUAL.md)** "Extending the Framework" section.

## Appendices

### Appendix A: Setup and Configuration by Replication Path

#### A.1 Direct Replication Setup

**Software Requirements:**
- Python 3.11 or higher
- PowerShell 7.0 or higher (cross-platform)
- Git
- PDM (Python Dependency Manager)

**Accounts and Services:**
- OpenRouter account with sufficient funds (approximately $150 for full study)
- No Astro-Databank account required (using static data)

**Installation Steps:**
1. Install PDM (one-time setup):
```powershell
   pip install --user pdm
```

2. Clone repository and install dependencies:
```powershell
   git clone [repository-url]
   cd llm-narrative-framework
   pdm install -G dev
```

3. Configure API key:
```powershell
   # Create .env file with OpenRouter API key
   "OPENROUTER_API_KEY=your-actual-api-key" | Out-File -FilePath .env -Encoding UTF8
```

4. Verify configuration:
```powershell
   # Check that config.ini matches original study parameters
   Get-Content config.ini
```

```ini
   [Study]
   mapping_strategy = correct, random
   group_size = 7, 10, 14
   model_name = anthropic/claude-sonnet-4, google/gemini-2.0-flash-lite-001, meta-llama/llama-3.3-70b-instruct, openai/gpt-4o, deepseek/deepseek-chat-v3.1, qwen/qwen-2.5-72b-instruct, mistralai/mistral-large-2411
   
   [Experiment]
   num_replications = 30
   num_trials = 80

   [LLM]
   temperature = 0.0
   max_tokens = 8,192
   max_parallel_sessions = 10
```

#### A.2 Methodological Replication Setup

**All requirements from A.1 plus:**

**Additional Accounts and Services:**
- Astro-Databank account at astro.com
- Sufficient OpenRouter funds for data generation (additional $50-90)

**Additional Software:**
- Solar Fire software (required for manual data preparation steps)

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

For detailed troubleshooting, see the **[📖 Framework Manual](docs/FRAMEWORK_MANUAL.md)**.

### Appendix C: Models and Experimental Design

#### Models Used in the Original Study

**Data Generation Models:**

| Purpose | Model Name | API Identifier |
| :--- | :--- | :--- |
| Eminence Scoring (LLM A) | OpenAI GPT-5 Chat | `openai/gpt-5-chat` |
| OCEAN Scoring (LLM B) | Anthropic Claude 4.5 Sonnet | `anthropic/claude-sonnet-4.5` |
| Neutralization (LLM C) | Google Gemini 2.5 Pro | `google/gemini-2.5-pro` |

**Evaluation Models (All Independent from Data Generation):**

**United States (4 models):**

| Purpose | Model Name | API Identifier | Provider | Parsing |
| :--- | :--- | :--- | :--- | :--- |
| Evaluation 1 (LLM D1) | Claude Sonnet 4 | `anthropic/claude-sonnet-4` | Anthropic | High |
| Evaluation 2 (LLM D2) | Gemini 2.0 Flash Lite | `google/gemini-2.0-flash-lite-001` | Google | 98% |
| Evaluation 3 (LLM D3) | Llama 3.3 70B Instruct | `meta-llama/llama-3.3-70b-instruct` | Meta | High |
| Evaluation 4 (LLM D4) | GPT-4o | `openai/gpt-4o` | OpenAI | High |

**China (2 models):**

| Purpose | Model Name | API Identifier | Provider | Parsing |
| :--- | :--- | :--- | :--- | :--- |
| Evaluation 5 (LLM D5) | DeepSeek Chat V3.1 | `deepseek/deepseek-chat-v3.1` | DeepSeek | 100% |
| Evaluation 6 (LLM D6) | Qwen 2.5 72B Instruct | `qwen/qwen-2.5-72b-instruct` | Alibaba | 92% |

**Europe (1 model):**

| Purpose | Model Name | API Identifier | Provider | Parsing |
| :--- | :--- | :--- | :--- | :--- |
| Evaluation 7 (LLM D7) | Mistral Large 2 2411 | `mistralai/mistral-large-2411` | Mistral AI | 98% |

*Access Dates for LLMs: October 16-19, 2025*

**Model Selection Rationale:**

All evaluation models were selected to ensure complete independence from data generation models, eliminating potential contamination from model reuse. The evaluation set represents maximum diversity across key dimensions:

- **Geographic Distribution:** 57% US, 29% Chinese, 14% European - enabling cross-cultural bias assessment
- **Open-Source Representation:** 57% open-weights (Llama, DeepSeek, Qwen2.5, Mistral) for long-term reproducibility
- **Architectural Diversity:** Standard transformers (Claude, GPT, Llama), Gemini architecture, and Mixture-of-Experts (DeepSeek, Qwen2.5)
- **Parsing Reliability:** All models achieved ≥92% structured output success in pilot testing (n=50 trials each)

**Pilot Testing Exclusions:**

Several models were tested but excluded due to reliability failures:
- Qwen3 235B: 24% parsing success (below 92% threshold)
- Qwen3-Next 80B: Entered infinite reprocessing loops (0% effective)
- Qwen3 30B: 96% parsing but only 3.3B active parameters (10× smaller than comparable models, would confound interpretation)

#### Experimental Design Reference

**Original Study Design:**
- 2×3×7 factorial design (42 conditions)
- 30 replications per condition (experiment)
- 80 trials per replication
- Total: 100,800 trials

**Factors:**
- Mapping Strategy (between-subjects): correct, random
- Group Size (within-subjects): k ∈ {7, 10, 14}
- Model (within-subjects): 7 diverse evaluation models

**Sample Size Justification:**

With 30 replications per condition and 80 trials per replication, the design provides >80% statistical power to detect small effect sizes (Cohen's d < 0.20) for main effects. The 80-trial count provides robust redundancy against parsing failures:
- Expected valid responses: 74-77 per replication (93-96% success rate)
- Minimum threshold: 25 valid responses per replication
- Buffer: 194-208% above minimum threshold

**Statistical Analysis:**
- Three-Way Mixed ANOVA (1 between-subjects, 2 within-subjects factors)
- Effect size measures (η², Cohen's d)
- Post-hoc tests (Tukey HSD with Benjamini-Hochberg FDR correction)
- Bayesian analysis (Bayes Factor)