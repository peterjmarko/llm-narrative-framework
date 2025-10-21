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
| **Estimated Cost** | ~$1,500 | ~$2,000-2,400 | Variable |
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
- OpenRouter account with sufficient funds (approximately $1,500 for full study)
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
   model_name = anthropic/claude-sonnet-4, google/gemini-2.0-flash-001, meta-llama/llama-3.3-70b-instruct, openai/gpt-4o, deepseek/deepseek-chat-v3.1, qwen/qwen-2.5-72b-instruct, mistralai/mistral-large-2411
   
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
- Sufficient OpenRouter funds for data generation (additional $500-900)

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

This appendix provides a comprehensive reference for both understanding the original study and designing new ones. It is organized into two parts: a specific reference for the original study's design and a general guide for researchers planning new experiments.

#### Original Study Reference

This section details the specific models, parameters, and design choices used in the original study.

##### Models Used in the Original Study

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
| Evaluation 2 (D2) | Gemini 2.5 Flash Lite | `google/gemini-2.5-flash-lite` | Google | ⚠️ Partial* |
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

Several relatively recent models (i.e., those published within the past 12 months) were evaluated during pilot testing but were excluded from the final study for failing to meet the required reliability and performance criteria. Exclusions fell into three main categories:

-   **Low Parsing Success Rate (<90%):** These models failed to consistently produce structured, parsable output.
    -   `Qwen: Qwen3 235B A22B Instruct` (24% success)
    -   `Google: Gemma 3` (12B and 27B variants, 23% and 80% success)
    -   `Z.AI: GLM 4.5` (83% success)
    -   `OpenAI: gpt-oss-20b` (63% success)

-   **Technical Instability:** This model caused critical failures in the automated workflow.
    -   `Qwen: Qwen3 Next 80B A3B Instruct` (Caused infinite reprocessing loops, resulting in 0% effective completion).

-   **Atypical Architecture or Output Format:** These models, while functional, were excluded to avoid confounding the analysis or because their output was fundamentally incompatible with the parsing engine.
    -   `Qwen: Qwen3 30B A3B Instruct` (Although parsing was high, it used only 3.3B active parameters, making it a significant architectural outlier that would complicate interpretation).
    -   `Google: Gemini 2.5 Pro` and `Gemini 2.5 Flash` (Generated conversational, explanatory text rather than the required structured data table, making them incompatible with the automated parser).

Note: Free or rate-limited models available via OpenRouter were not included in pilot testing due to a lack of the reliable, high-throughput access required for large-scale automated experiments.

###### Experimental Design Reference

**Original Study Design:**
- 2×3×7 factorial design (42 conditions)
- 30 replications per condition (experiment)
- 80 trials per replication
- Total: 100,800 trials

###### Factor Justification

-   **Mapping Strategy (Between-Subjects):** This is the core experimental manipulation.
    -   `correct`: The experimental condition, testing the LLM's ability to detect the faint, systematic signal when it is present.
    -   `random`: The null/control condition, where profiles are shuffled. This establishes a chance-level baseline and tests whether the model is merely guessing or hallucinating patterns.
    -   This was treated as a between-subjects factor to ensure a clean design where a model is not "tipped off" to the existence of random trials within a single experiment.

-   **Group Size (`k`) (Within-Subjects):** This factor systematically varies the difficulty of the matching task.
    -   `k ∈ {7, 10, 14}`: This range was chosen to create a clear difficulty gradient. The step from 7 to 10, and 10 to 14, each represents an approximate 20% increase in difficulty (as measured by the decrease in chance-level MRR).
    -   `k=7` serves as an easier baseline, while `k=14` pushes the model's context-processing capabilities to test for performance degradation under high cognitive load.

-   **Model (Within-Subjects):** This factor tests for the generalizability of the findings across different LLMs.
    -   The seven evaluation models were chosen for maximum diversity in architecture, provider, and training data. A detailed justification for their selection is provided in the "Model Selection Rationale" section above.

###### Sample Size Justification

The choice of **30 replications** per condition and **80 trials** per replication was made to strike an optimal balance between statistical power, metric precision, and the practical constraints of cost and time.

**Why 30 Replications? (Statistical Power)**

-   **Purpose:** The number of replications is the sample size (`n`) for the statistical tests that compare conditions (e.g., Model A vs. Model B). A larger `n` increases the power to detect real differences.
-   **Justification:** A sample size of 30 is a well-established standard in experimental research for conducting robust ANOVA and t-tests. It provides sufficient statistical power (>80%) to reliably detect small-to-medium main effects and interactions (Cohen's d > 0.20).
-   **Trade-offs:**
    -   *Fewer Replications (<20)* would significantly reduce statistical power, increasing the risk of failing to detect a true effect (Type II error).
    -   *More Replications (>50)* would offer diminishing returns in power gain while linearly increasing the total cost and runtime of the study.

**Why 80 Trials? (Metric Precision and Resilience)**

-   **Purpose:** The number of trials determines the precision of the performance metrics (like MRR) *within a single replication*. Each replication's performance score is an average across all its trials; more trials lead to a more stable and less noisy estimate.
-   **Justification:** An 80-trial count provides a strong balance:
    1.  **Reduces Noise:** It smooths out the randomness of LLM performance on any single query, yielding a more reliable data point for each replication.
    2.  **Provides Resilience:** It creates a crucial buffer against real-world API and parsing failures. With a minimum threshold of 25 valid responses required for a replication to be included in the final analysis, 80 trials offer a substantial safety margin. Even with a parsing success rate as low as 90%, we can expect 72 valid responses—nearly 3 times the required minimum.
-   **Trade-offs:**
    -   *Fewer Trials (<50)* would make each replication's metrics more volatile and highly susceptible to a few outlier results. It would also reduce the buffer against parsing failures, risking data loss.
    -   *More Trials (>100)* would offer slightly more precision but at a direct, linear increase in cost per replication, representing a point of diminishing returns.

In summary, the 30x80 design was chosen as a robust and cost-effective standard that ensures the study is both statistically powerful and resilient to the practical challenges of large-scale LLM experimentation.

###### Statistical Analysis Plan

- **Primary Analysis:** Three-Way Mixed ANOVA (1 between-subjects, 2 within-subjects factors).
- **Effect Size Measures:** Eta-squared (η²) and Cohen's d.
- **Post-Hoc Tests:** Tukey HSD with Benjamini-Hochberg FDR correction for multiple comparisons.
- **Complementary Analysis:** Bayesian analysis (Bayes Factor) to quantify evidence for or against the null hypothesis.

---

#### Guidance for Designing New Studies

This section provides general principles for designing new multi-factor experiments for methodological or conceptual replication. Note: All cost estimates are in USD and based on OpenRouter.ai rates as of October 2025.

##### 1. Define Your Factors

The framework is built for factorial designs. Start by defining the independent variables (factors) you want to investigate. Common factors include:

-   **`mapping_strategy` (Between-Subjects):** The core experimental manipulation (e.g., `correct` vs. `random`).
-   **`group_size` (`k`) (Within-Subjects):** The difficulty of the matching task. Choose values that create a systematic difficulty gradient (e.g., an easy, medium, and hard condition like 7, 10, 14).
-   **`model_name` (Within-Subjects):** The LLMs you want to compare.

##### 2. Select Your Parameters

-   **Models:** When selecting models, consider a balance of:
    -   **Cost-Effectiveness:** Choose models that fit your budget.
    -   **Architectural Diversity:** Include models from different providers (e.g., OpenAI, Google, Anthropic, Meta) and with different architectures to test generalizability.
    -   **Parsing Reliability:** Models must consistently return structured, parsable data. Test this in a pilot run.
    -   **Independence:** For conceptual replications, ensure evaluation models are different from any models used in your data generation pipeline.

-   **Group Sizes (`k`):** Select a range of `k` values that meaningfully vary the task difficulty. The original study used {7, 10, 14} because they create a roughly 20% increase in difficulty (measured by chance-level MRR) between steps. Avoid very small `k` (e.g., k < 5) where chance performance is too high.

##### 3. Determine Your Sample Size

Your sample size is a function of replications and trials, and it represents a trade-off between statistical power and resources (time and cost).

-   **Replications (`num_replications`):** This determines the statistical power for comparing conditions (e.g., model A vs. model B). The original study used **30 replications**, which provides over 80% power to detect small-to-medium sized effects. This is a robust baseline for academic research.
-   **Trials (`num_trials`):** This determines the stability and reliability of the performance metrics *within* a single replication. More trials reduce noise. The original study used **80 trials**, which provides a strong buffer against occasional API errors or parsing failures while keeping costs manageable.

A **30x80 design** is a well-justified starting point, but you may adjust these values based on your research goals and budget.

##### 4. Plan Your Execution Strategy

Never run a large-scale study in one go. Follow a phased approach:

1.  **Estimate:** Calculate the total number of trials (conditions × replications × trials) to estimate the total API cost and runtime.
2.  **Pilot:** Always run a small pilot study first (e.g., one condition, 5-10 replications). This is critical for validating your entire pipeline, confirming your chosen models have a high parsing success rate (>95%), and catching any configuration errors before committing to a large budget.
3.  **Execute in Batches:** Run the full study in manageable chunks (e.g., by model or by k-value). Perform quality checks after each batch using the `audit_experiment.ps1` script to ensure data integrity.

##### 5. Organize Your Study

-   **Directory Structure:** Create a dedicated study directory in `output/studies/` to hold all related experiment folders.
-   **Naming Convention:** Use a consistent, descriptive naming convention for your experiment folders (e.g., `exp_{mapping}_{k}_{model}`) to keep your work organized and easily sortable.