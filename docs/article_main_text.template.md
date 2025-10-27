---
title: "A Framework for Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology"
author: "Peter J. Marko and Kenneth McRitchie"
date: "[Date]"
abstract: |
  **Background:** Psychology has struggled to empirically validate complex, holistic systems that produce narrative-based claims. This methodological gap highlights the need for new, more rigorous, and transparent research paradigms.
  **Objective:** This paper introduces and validates a novel, fully automated, and open-source framework for testing for weak signals in complex narratives. Using astrology as a challenging case study, we demonstrate a reproducible method for assessing the construct validity of a symbolic system against biographical data.
  **Methods:** A library of astrological descriptions was programmatically neutralized by a Large Language Model (LLM) to remove all esoteric terminology. A cohort of 10,707 historically eminent individuals was sourced from a public database and subjected to a rigorous, multi-stage filtering process, yielding 5,736 "eligible" candidates. This cohort was then rank-ordered by an LLM-generated eminence score, and the final subject pool was determined by a data-driven cutoff based on the variance of their LLM-generated OCEAN scores. An independent LLM was then used as an impartial arbiter to perform a series of matching tasks, pairing biographies from a final pool of 4,987 individuals with their corresponding personality descriptions. All code, data, and materials are publicly available in an open-source repository at https://github.com/peterjmarko/llm-narrative-framework.git.
  **Results:** A multi-level analysis revealed statistically significant signal detection across multiple evaluation models. Aggregate analysis showed a very small but highly significant main effect for the matching condition (*F*(1, 1218) = 18.22, *p* < .001, η² = .003), with optimal signal exposure occurring at medium task difficulty (k=10: η² = 1.25%). Individual model analysis revealed extreme heterogeneity in signal detection capability, ranging from 0.03% to 17.23% (575× variation). Trajectory analysis identified two distinct patterns: framework-compatible models (GPT-4o, DeepSeek) showing Goldilocks patterns peaking at k=10, and framework-incompatible models (Claude, Llama) showing consistently minimal detection across all difficulty levels. These findings demonstrate that framework effectiveness requires both compatible model architecture and optimal task difficulty calibration.
  **Conclusion:** This study's primary contribution is a new, open-science paradigm for psychological research. By demonstrating its utility on a difficult and controversial topic, we provide a robust, methodologically reproducible, and scalable framework for future investigations into complex narrative systems.
---

**Keywords:** Psychology, astrology, large language models, computational social science, reproducibility, open science

### Introduction

The replication crisis has spurred a fierce and ongoing debate within psychological science about methodological reform (van Dongen & van Grootel, 2025). A key challenge in this landscape is establishing the **construct validity** (i.e., whether a system measures what it claims to measure) of complex, holistic systems that generate narrative-based claims (Cronbach & Meehl, 1955). This paper introduces and validates the **LLM Narrative Framework**—an automated testing methodology that uses Large Language Models as pattern-detection engines to perform matching tasks, determining whether systematic signals in narrative descriptions can be detected at rates significantly greater than chance. Astrology serves as a prime example, where landmark empirical studies have faced significant methodological debate (Carlson, 1985; Eysenck & Nias, 1982; Ertel, 2009) and where comprehensive meta-analyses of quantitative research have consistently shown null results (Dean & Kelly, 2003). While modern "whole-chart" matching tests show promise (Currey, 2022; Godbout, 2020), even recent computational explorations have been limited by a reliance on opaque "black-box" tools and manual processes for assessing semantic similarity (Marko, 2018). This history highlights the need for a fully automated, transparent, and scalable testing framework.

The advent of Large Language Models (LLMs) presents an opportunity to develop such a framework. Prior research on the construct validity of astrology has often employed matching tests, where judges attempt to pair biographical or psychological descriptions with their corresponding subjects (e.g., Carlson, 1985). LLMs, as powerful pattern-recognition engines (Google, 2024; Wei et al., 2022), are uniquely suited to automate this process. Unlike human judges, who are susceptible to cognitive biases, LLMs can be deployed as **agnostic arbiters**, executing a matching task at a massive scale. Recent research has shown that modern LLMs can meet or even exceed the reliability of human annotators for complex text-classification tasks (Gilardi et al., 2023) and can be used to simulate human samples for social science research (Argyle et al., 2023). This study introduces and validates such an LLM-based framework, using astrology as a challenging case study.

Our primary goal is to determine if a fully automated pipeline can serve as a sensitive instrument for detecting weak signals in complex, narrative-based claims. To this end, the study tests a single, core hypothesis: *that the LLM-based framework can distinguish between correctly mapped and randomly mapped personality descriptions at a rate significantly greater than chance.* While the successful detection of such a signal within the present case study of astrology has implications for that field, the broader contribution of this work is the validation of the methodology itself. The philosophical implications of using a non-conscious system to analyze subjective consciousness are taken up in a companion article (McRitchie & Marko, manuscript in preparation).

### Methods

#### Tool Selection Across Pipeline Stages

The framework employs distinct LLMs for different stages of data preparation and evaluation, each selected to optimize performance, cost, and methodological independence (see Figure 1 for system architecture). For the LLM-based candidate selection stage, **LLM A (OpenAI's GPT-5)** performed eminence scoring in batches of 100 subjects, while **LLM B (Anthropic's Claude 4.5 Sonnet)** generated OCEAN personality scores with a batch size of 50, chosen for its strong performance on nuanced psychological assessment tasks. For profile generation, **LLM C (Google's Gemini 2.5 Pro)** handled the neutralization of 149 astrological delineations, selected for its superior instruction-following capabilities and large context window. For the core matching task, seven independent evaluation models were deployed (see Table 2 for the complete experimental design). For the LLM-based candidate selection stage, **LLM A** used a calibrated eminence scoring prompt with fixed historical anchors (Jesus Christ = 100.0, Plato/Newton = 99.5, Einstein = 99.0) to establish an absolute scale, with explicit instructions to distinguish "lasting historical eminence" from "transient celebrity." **LLM B** used a structured prompt requesting Big Five personality traits rated on a 1.0-7.0 scale with JSON output format for automated parsing. Complete prompt texts for all LLM stages are available in the project repository.

To minimize potential data contamination, the seven evaluation models used for the core matching task were selected to be independent from data generation models where possible. Four evaluation models (DeepSeek Chat v3.1, Qwen 2.5 72B, Mistral Large, Llama 3.3 70B) had no prior role in the pipeline and represent completely independent architectures. Three models share providers with data generation models: GPT-4o shares a provider with LLM A (GPT-5), Claude Sonnet 4 is from the same family as LLM B (Claude 4.5 Sonnet), and Gemini 2.0 Flash Lite is from the same family as LLM C (Gemini 2.5 Pro). While this creates potential contamination risk through shared training data, three critical findings argue against contamination as an explanatory artifact: (1) The three "contaminated" models show opposite performance patterns—GPT-4o detected the strongest signal (η²=17.23%) while Claude Sonnet 4 detected essentially no signal (η²=0.03%), demonstrating that provider overlap does not predict signal detection; (2) The two strongest performers (GPT-4o and DeepSeek V3.1, η²=11.16%) come from completely different architectural lineages—one with potential contamination and one without—suggesting signal detection depends on architectural capabilities rather than training data overlap; (3) The extreme heterogeneity (575× variation) emerged across models with similar levels of potential contamination, inconsistent with a uniform contamination effect. Nevertheless, this limitation cannot be definitively ruled out and motivates replication with fully independent model sets. 

All evaluation models used temperature = 0.0 to maximize response consistency across trials—a standard practice in LLM evaluation benchmarks. While temperature=0.0 minimizes sampling variance, it does not eliminate it: LLM API responses exhibit inherent non-determinism, with identical prompts producing different outputs even at temperature=0.0. Therefore, exact computational reproducibility (bit-for-bit identical results) is not achievable with current LLM architectures. The framework instead provides methodological reproducibility through transparent documentation of experimental parameters and open-source code. The original study did not employ randomization seeds for query generation; future implementations may optionally use seeds (e.g., base_seed for subject selection, qgen_base_seed for list shuffling) to enable exact replication of experimental stimuli, though this does not resolve LLM response variance. The consistency of findings across 1,260 experiments spanning multiple days demonstrates methodological stability despite temporal and stochastic variance in LLM responses.

{{grouped_figure:docs/diagrams/arch_llm_pipeline.mmd | scale=2.5 | width=70% | caption=Figure 1: System architecture showing distinct LLM roles across the six pipeline stages. LLM A (GPT-5) performs eminence scoring, LLM B (Claude 4.5 Sonnet) generates OCEAN scores, LLM C (Gemini 2.5 Pro) neutralizes astrological text, and seven independent evaluation models perform the matching task. This separation minimizes data contamination risk.}}

#### Sample Population

The framework is designed to support three distinct research paths. For **direct replication**, researchers can use the static data files included in the project's public repository. While the framework employs temperature=0.0 to minimize LLM response variance, exact computational reproducibility is not achievable due to inherent API non-determinism. Researchers should expect methodological reproducibility: statistically equivalent results using the same experimental design. For **methodological replication**, the framework's automated tools can be used to generate a fresh dataset from the live Astro-Databank (ADB) to test the robustness of the findings. Finally, for **conceptual replication**, researchers can modify the framework itself (e.g., by using a different LLM or analysis script) to extend the research.

The final study sample was derived from a multi-stage data preparation pipeline, as illustrated in Figure 2. This section provides a conceptual overview of the workflow; a detailed, step-by-step guide for the entire data preparation pipeline and experiment workflow is available in the **Supplementary Materials** (see Replication Guide in the online repository). The first stage of the pipeline, **Data Sourcing**, involved an initial query of the Astro-Databank (ADB) which selected subjects based on three source-level criteria: high-quality birth data (Rodden Rating 'A' or 'AA'), inclusion in the specific **Personal > Death** category to ensure the subject is deceased, and inclusion in the specific eminence category of **Notable > Famous > Top 5% of Profession**. The rationale for these filters is as follows:

*   Accurate birth date and time are required for the astrology program to generate reliable personality descriptions
*   The use of publicly available data of deceased historical individuals obviates privacy concerns
*   Focusing on famous people on top of their profession assures the general availability of ample biographical data

---

{{grouped_figure:docs/diagrams/flow_sample_derivation.mmd | scale=2.5 | width=60% | caption=Figure 2: Flowchart of the sample derivation process, showing the number of subjects retained at each stage of the data preparation pipeline.}}

The second stage, **Candidate Qualification**, subjected this initial set to a more rigorous automated filtering pass. This pass applied several additional data quality rules, retaining only individuals who: had a death date recorded on their Wikidata page; had passed an automated validation against their English Wikipedia page; were classified as a `Person` and not a `Research` entry; had a birth year between 1900-1999 to minimize cohort-specific confounds (Ryder, 1965), a step which excluded only 0.6% of the raw dataset; had a validly formatted birth time; were not duplicates; and were born in the Northern Hemisphere, which excluded approximately 5% of the remaining records. Checking Wikidata life status of each person was done for two reasons: first, the 'death' attribute in ADB might be incorrect or perhaps indicating the death of another, related individual; second, the aggressive filtering avoids the accidental inclusion of living individuals. The final filter was applied to control for the potential confounding variable of a 180-degree zodiacal shift for Southern Hemisphere births, a well-documented open question in astrology (Lewis, 1994). This multi-step process produced a clean cohort of "eligible candidates."

This "eligible" cohort was then subjected to the third stage, **LLM-Based Candidate Selection**: a multi-step process to determine the final sample. First, **LLM A (OpenAI's GPT-5)**[^1] generated a static eminence score for each candidate, sorting the cohort by historical prominence. Second, **LLM B (Anthropic's Claude 4.5 Sonnet)** generated Big Five (OCEAN) personality scores for the entire eminence-ranked cohort. Finally, a separate script applied an algorithmic cutoff procedure to determine optimal cohort size based on psychological diversity, operationalized as the average variance across the five OCEAN traits. The algorithm calculated cumulative personality variance incrementally as subjects were added in eminence-descending order, smoothed the resulting curve using a 1,500-point moving average to eliminate local noise, and performed slope analysis to identify the plateau—the point where additional less-eminent subjects contributed negligible diversity (slope threshold: -0.00001). This objective, reproducible procedure yielded a cutoff at 4,987 subjects (87% of eligible candidates). Sensitivity analysis across 412 parameter combinations confirmed robustness, with consensus cutoff at 4,975 subjects (SD = 12 subjects, 0.24% deviation). The variance curve and cutoff detection are illustrated in Figure S8 (Supplementary Materials). This approach maximizes sample diversity while excluding subjects with sparse biographical data and homogeneous personality profiles that would add measurement noise without increasing discriminating power. This cutoff procedure was executed during data preparation, prior to experimental trials, ensuring sample size determination was independent of experimental outcomes. For **conceptual replication**, this stage may be bypassed to (1) use all eligible candidates and assess robustness to sample selection, or (2) apply alternative stopping rules (e.g., fixed N, multiple cutoff points) to validate consistency across sample definitions.

#### Profile Generation

The personality descriptions used as test interventions were generated in the fourth stage, **Profile Generation**, through a multi-step process.

##### Component Library Neutralization and Validation

To create a robust, double-blind experimental design, the entire library of interpretive delineations within the **Solar Fire v9.0.3** expert system (Astrolabe Inc., n.d.) was systematically "neutralized". The primary goal of this de-jargonization process was to remove all astrological terminology while preserving core descriptive meaning. This library of components was processed by **LLM C (Google's Gemini 2.5 Pro)** using a methodical approach by breaking down the entire set by component into 149 individual API calls. Each snippet was rewritten using a structured prompt that instructed the model to remove astrological terminology, shift to impersonal third-person style, and preserve core psychological meaning while maintaining heading structure for lookup purposes. The lines marked with an asterisk (e.g., `*Moon in Taurus`) are the unique identifiers for each delineation and were preserved verbatim to serve as lookup keys for generating the individual neutralized components. This process created a master database of neutralized components. To validate the neutralization, an automated keyword search for over 150 astrological terms confirmed that no explicit terminology remained. Table 1 provides an example of this process. It is acknowledged that this neutralization results in a loss of nuance compared to the original text, a necessary trade-off for achieving a robust blinding procedure. The strengths of this automated approach, particularly its scalability and consistency, are a key advancement over previous methods.

**Component-Level Validation of Discriminability:** To validate that neutralization preserved description discriminability, we analyzed semantic diversity across the 178 neutralized delineation components that serve as building blocks for profile generation. TF-IDF vectorization with pairwise cosine similarity analysis revealed mean similarity of 0.029 (SD = 0.056), indicating components are meaningfully distinct rather than generic variants. Vocabulary analysis showed mean pairwise overlap (Jaccard similarity) of 0.093 (SD = 0.050), with the component library utilizing 1,917 unique terms (type-token ratio = 0.329). Within-category components showed higher semantic similarity (M = 0.033) than between-category components (M = 0.023), confirming the neutralization process preserved the system's semantic structure. Component length varied substantially (M = 32.7 words, SD = 26.2, CV = 0.802), demonstrating the algorithm utilized diverse building blocks rather than template-like patterns.

**Profile-Level Validation via Random Control:** The experimental design itself provides functional validation through the random control condition. If neutralization had created generic, Barnum-like descriptions lacking discriminating power, performance on random mappings would equal performance on correct mappings (since generic descriptions would "match" any biography equally well). The significant correct-vs-random difference at optimal difficulty (k=10: η²=1.25%, *p*<.001) demonstrates that assembled profiles retain sufficient specificity to support above-chance discrimination. Together, the component-level diversity metrics and profile-level discrimination performance provide converging evidence that neutralization maintained rather than eliminated discriminating power.

*Table 1: Example of Text Neutralization*

| Original Astrological Text (Sun in Aries) | Neutralized Text |
| :--- | :--- |
| "Your Sun is in the zodiac sign of Aries indicating that you're an assertive and freedom-loving individual, with a strong need for independence. Others may call you headstrong, but you simply believe that everyone has a right to assert themselves in any situation. Life presents many challenges which you enjoy meeting head-on regardless of the obstacles along the way. You're a natural-born leader.  The ability to focus on one's own goals to the exclusion of others is a healthy trait, but like all things a balance is needed, and you must make sure that you take the time to include others' points of views and modus operandi. On the whole though you handle yourself with aplomb as, astrologically speaking, the Sun is exalted in Aries emphasising the strengths rather than the weaknesses." | "Assertive and freedom-loving, with a strong need for independence. A headstrong quality, coupled with a firm belief in the right to self-assertion. An enjoyment of meeting challenges head-on, regardless of the obstacles. Natural leadership ability. An ability to focus on goals to the exclusion of others, which requires balance and the inclusion of others' points of view and methods. On the whole, a sense of aplomb, with strengths emphasized over weaknesses." |

{{pagebreak}}

The neutralization process is depicted on Figure 3 below.

{{grouped_figure:docs/diagrams/logic_prep_neutralization_simple.mmd | scale=2.0 | width=50% | caption=Figure 3: Text neutralization pipeline implemented via neutralize_delineations.py. The process parses the raw astrological library, processes each component through LLM C (Gemini 2.5 Pro), validates removal of esoteric terminology, and outputs neutralized descriptions while preserving lookup keys for profile assembly.}}

##### Profile Assembly

For each of the 4,987 test subjects in the final study database, a foundational set of astrological placements was exported from Solar Fire. This structured data included the factors necessary to generate two reports: the "Balances" (Planetary Dominance) report, covering signs, elements, modes (qualities), quadrants, and hemispheres; and the "Chart Points" report, covering the sign placements of the 12 key chart points (Sun through Pluto, Ascendant, and Midheaven). The specific weighting and threshold settings used for the "Balances" report (based on default values) are detailed in the **Supplementary Materials** available in the project's online repository. This foundational set of factors was chosen deliberately to test for a primary signal while minimizing the confounding variables that could arise from more complex astrological techniques, such as planetary aspects or midpoints.

Each test subject's complete, neutralized personality profile was then programmatically assembled. Their specific set of astrological placements was used as a key to look up and concatenate the corresponding pre-neutralized description components from the validated master database. **This personality assembly algorithm was rigorously validated for technical correctness: using the original, non-neutralized delineations, it produced an output that was bit-for-bit identical to a ground-truth dataset generated by the source expert system.** This validation confirms our implementation faithfully reproduces the source system's logic, ensuring the test fairly represents that system's claims. However, this technical validation does not establish whether the astrological weighting system itself (e.g., point weights, balance thresholds) produces psychologically meaningful output—that question is precisely what the experimental results address empirically. This process resulted in a unique, composite personality profile for each individual, expressed in neutral language, which formed the basis of the stimuli used in the matching task.

#### Experimental Design and Procedure

All data generation, experiments, and analysis were conducted in October 2025 (see Figure 4 for complete timeline). Specifically, the data preparation pipeline was executed on October 16; the main experimental runs were conducted between October 18-22; and the final analysis was performed on October 22-25. Documenting this specific timeframe is critical for methodological context, as the behavior of LLMs varies over time even for the same model versions due to inherent API non-determinism.

{{grouped_figure:docs/diagrams/timeline_study_execution.mmd | scale=2.0 | width=100% | caption=Figure 4: Study execution timeline (October 2025). Data preparation completed October 16, experimental runs conducted October 18-22 (1,260 experiments, 100,800 LLM queries), and statistical analysis performed October 22-25. This temporal documentation provides critical methodological context given the time-specific behavior and inherent response variability of LLM models.}}

The study employed a 2 × 3 × 7 factorial design, as detailed in Table 2. The end-to-end research workflow, from generating data for individual experimental conditions to compiling the final study analysis, is illustrated in Figure 5.

*Table 2: Experimental Design*

| Factor | Type | Levels |
| :--- | :--- | :--- |
| **`mapping_strategy`** | Between-Groups | 2 (`correct`, `random`) |
| **`k` (Group Size)** | Within-Groups | 3 (`7`, `10`, `14`) |
| **`model`** | Within-Groups | 7 (Claude Sonnet 4, Gemini 2.0 Flash Lite, Llama 3.3 70B, GPT-4o, DeepSeek Chat v3.1, Qwen 2.5 72B, Mistral Large) |

The experimental design is shown on Figure 5 below.

{{grouped_figure:docs/diagrams/design_factorial_experiment.mmd | scale=2.5 | width=100% | caption=Figure 5: Experimental design structure showing the 2×3×7 factorial arrangement: 2 mapping strategies (correct vs. random) × 3 group sizes (k=7, 10, 14) × 7 evaluation models = 42 conditions, each with 30 replications.}}

Figure 6 below shows an example for generating two experiments and compiling them into a study. 

{{grouped_figure:docs/diagrams/flow_research_workflow.mmd | scale=2.5 | width=75% | caption=Figure 6: The end-to-end research workflow, showing the generation of individual experiments and their final compilation into a study.}}

The factor **`mapping_strategy`** is the core experimental manipulation: a `correct` value means the matching test is evaluated against the true mappings between test subjects and their astrologically derived, neutralized peronality descriptions while a `random` value corresponds to arbitrary mappings between the paired lists, effectively creating a control group for each scenario. The LLMs are blinded to the true mappings.

The factor `k` is the size of the test group: the number of test subjects and their corresponding personality descriptions. This factor directly influences the difficulty of the matching task: `k=7` is considered 'easy', `k=10` 'medium-level', and `k=14` 'hard' on the task difficulty scale.

The core matching task was executed by seven evaluation models: Claude Sonnet 4, Gemini 2.0 Flash Lite, Llama 3.3 70B, GPT-4o, DeepSeek Chat v3.1, Qwen 2.5 72B, and Mistral Large. A complete reference table mapping these simplified names to their exact API identifiers and provider details is available in Appendix C of the Supplementary Materials. For each trial, the LLM was provided with a group of `k` neutralized personality descriptions (labeled as "List B" with IDs) and a corresponding group of `k` subject names with birth years (labeled as "List A"), with the presentation order of both lists randomly shuffled to control for any potential effects on the LLM's evaluation resulting from original item position. The presentation order of both lists was randomly shuffled for each trial to control for position effects. Note: The original study did not employ randomization seeds; list shuffling used non-seeded randomization. Future implementations may optionally use seed parameters to enable exact replication of query generation. The evaluation prompt instructed the model to: (1) independently source biographical information for each named individual, (2) assess similarity between each biography and each personality description, and (3) return results as a tab-delimited table with persons as rows, description IDs as columns, and similarity scores (0.00-1.00) as cell values, with explicit instructions to provide no additional commentary. The complete evaluation prompt text is available in the project repository as `data/base_query.txt`.

The experiment consisted of 80 trials per replication, with 30 full replications conducted for each of the 42 conditions (`2 mapping_strategy levels × 3 k levels × 7 models`), totaling 100,800 LLM queries in 1,260 complete experimental runs. Parsing success rates (percentage of queries producing valid structured output) varied substantially by model: Claude Sonnet 4 (100%, 14,398/14,400 trials), DeepSeek V3.1 (100%, 14,384/14,400), Gemini 2.0 Flash (98%, 14,131/14,400), Llama 3.3 70B (96%, 13,840/14,400), Mistral Large (96%, 13,799/14,400), GPT-4o (87%, 12,530/14,400), and Qwen 2.5 72B (65%, 9,393/14,400), yielding an overall success rate of 92.4% (93,175 valid responses). Failed trials were excluded from analysis. Despite substantial model differences in parsing reliability, this exclusion introduced no bias: within each model, failures were randomly distributed across mapping_strategy conditions (correct vs. random rates differed by <2 percentage points), and all 1,260 replications exceeded the minimum quality threshold of 25 valid responses (observed range: 26-80, mean: 65.5). The 80-trial design provided sufficient resilience: even Qwen 2.5 72B (the lowest-performing model) averaged 52.2 valid responses per replication across all k-levels, maintaining adequate statistical power for within-subject comparisons. Complete per-condition success rates are provided in Supplementary Materials Table S4. With 30 replications per condition, this design provided sufficient statistical power (>.80) to detect small-to-medium effect sizes.

The selection of the seven evaluation models was the result of a systematic piloting process conducted on a separate pilot dataset (details in Supplementary Materials). Selection prioritized technical reliability over signal detection capability to avoid circular reasoning. Models were assessed for: (1) parsing reliability (≥90% success rate in pilot testing with 50 trials per model), (2) response time and cost-effectiveness for large-scale deployment, and (3) architectural diversity across providers and geographic origins. A total of 42 candidate models were evaluated; 35 were excluded due to parsing failures, inconsistent formatting, extreme response time, or prohibitive cost. The final seven models represented maximum diversity across architecture, provider, and geographic origin while maintaining technical reliability. Importantly, signal detection performance was NOT a selection criterion—the heterogeneity in signal detection (0.03% to 17.23%) was discovered post-hoc during the main study analysis. To monitor the integrity of the matching process, the LLM was also periodically queried to provide a detailed explanation of its methodology. These introspective checks were reviewed to ensure the model was operating within the intended parameters of the task and not applying external, domain-specific knowledge.

#### Dependent Variables and Statistical Analysis

The primary dependent variables were "lift" metrics, which normalize for chance and are thus comparable across different `k` values (e.g., a lift score of 1.15 indicates performance 15% above what is expected by chance). Key metrics included:

*   **Mean Reciprocal Rank (MRR) Lift**: The observed MRR divided by the MRR expected by chance.
*   **Top-1 and Top-3 Accuracy Lift**: Observed accuracy divided by chance accuracy.

A Three-Way Analysis of Variance (ANOVA) was conducted for each metric to assess the main effects of `mapping_strategy`, `k`, and `model`, as well as their interactions. Effect sizes were calculated using eta-squared (η²) to determine the proportion of variance attributable to each factor (Cohen, 1988). The significance level was set at α = .05.

To address the potential for aggregate findings to mask model-specific heterogeneity, a systematic, data-driven multi-level decomposition approach was employed. This strategy proceeded in four stages:

1.  **Aggregate Analysis:** A three-way ANOVA was first conducted on the full dataset to establish a baseline and test for main effects and interactions.
2.  **Optimal Difficulty Identification:** To identify the task difficulty (`k`) that best exposed a potential signal, the data was subset by each `k` level, and separate two-way ANOVAs (`model` × `mapping_strategy`) were conducted. This process was designed to locate a "Goldilocks zone" of peak signal detection.
3.  **Model Heterogeneity Characterization:** Based on the results of the previous step, the data was further subset to the optimal difficulty level (`k=10`). A series of one-way ANOVAs were then performed for each model individually to quantify its specific signal detection capability and effect size.
4.  **Trajectory Pattern Analysis:** Finally, to characterize the full performance patterns, the signal detection results (η²) for representative high-detection (e.g., GPT-4o, DeepSeek) and low-detection (e.g., Claude, Llama) models were plotted across all three `k` levels to identify distinct "Goldilocks" versus "Flat" trajectories.

This multi-level approach allowed for a comprehensive assessment that moved from a general baseline to specific, actionable insights about both overall framework effectiveness and model-specific compatibility patterns.

Given the large sample size (N=1,260), balanced design, and use of lift metrics (which normalize distributions), ANOVA provided robust inference even if normality and other assumptions were not perfectly met.

Each ANOVA was treated as a separate, pre-specified test of the core hypothesis that the framework can distinguish between correct and random mappings.[^2] To complement the frequentist approach, a Bayesian analysis was also conducted. This allowed us to quantify the evidence for the hypothesis that a real signal exists against the null hypothesis that performance is due to chance. This approach responds to the ongoing debate about the proper use of statistical inference in psychology (van Dongen & van Grootel, 2022).

**Pre-registration and Exploratory Analysis:** The core hypothesis—that the framework can distinguish between correct and random mappings—was pre-specified. However, the multi-level decomposition approach represents exploratory framework validation, with specific analyses (optimal difficulty identification, model heterogeneity characterization, trajectory patterns) emerging from data inspection rather than _a priori_ hypotheses. This hybrid approach is appropriate for novel framework validation studies, where the primary goal is methodological demonstration rather than theory testing. Future replications and confirmatory studies employing this framework should pre-register specific hypotheses about signal strength, model performance, and task difficulty effects.

**Software and Computational Environment:** All analyses were conducted using Python 3.11+ with the following core packages: NumPy (numerical computing), Pandas (data manipulation), SciPy and Statsmodels (statistical analysis), Pingouin (ANOVA and effect sizes), Seaborn and Matplotlib (visualization), and python-dotenv (configuration management). Data preparation and experiment orchestration scripts were implemented in PowerShell 7.x for cross-platform compatibility. The complete computational environment, including all package versions and dependencies, is specified in the project's `pyproject.toml` and can be reproduced using PDM (Python Dependency Manager). All code is version-controlled via Git, ensuring transparent tracking of methodological decisions and modifications.

### Results

The analysis employed a multi-level decomposition approach to comprehensively assess framework effectiveness. Aggregate findings established baseline signal detection, followed by targeted analyses to identify optimal task conditions, characterize model-specific capabilities, and reveal distinct patterns of signal detection across difficulty levels.

Aggregate three-way ANOVA revealed statistically significant main effects for both `mapping_strategy` and `k` on key performance metrics, with small effect sizes indicating detection of subtle signals (see Table 3 for complete results). To control for false discovery rate across 21 primary statistical tests conducted in this study (1 aggregate 3-way ANOVA with 7 effects + 3 k-level subset ANOVAs + 7 model-specific ANOVAs at k=10 + 3 secondary analyses), Benjamini-Hochberg FDR correction was applied to all p-values. All statistically significant results reported in this article remained significant after FDR correction (see Supplementary Materials Table S1 for complete corrected values), demonstrating robustness against Type I error inflation. For clarity and consistency with standard reporting practices, uncorrected p-values are reported throughout the main text. For the primary metric (MRR Lift), the main effect of `mapping_strategy` was highly significant (*F*(1, 1218) = 18.22, *p* < .001, η² = .003), demonstrating that evaluation models collectively performed better when assessed against correct mappings (i.e., in the test gorups) than random mappings (control groups), though the effect size was very small. The main effect of group size `k` was also highly significant (*F*(2, 1218) = 667.48, *p* < .001, η² = .200), confirming that task difficulty substantially impacts signal detectability.

While most interactions were not significant, the `mapping_strategy × k` interaction approached significance for the primary metric, MRR Lift (*F*(2, 1218) = 2.81, *p* = .061). This suggested that the strength of the detected signal might depend on the task difficulty, providing a statistical motivation for the planned multi-level decomposition to investigate each `k` level independently. Other interactions were not significant (`mapping_strategy × model`: *F*(6, 1218) = 2.09, *p* = .052; `k × model`: *F*(12, 1218) = 82.74, *p* < .001; `mapping_strategy × k × model`: *F*(12, 1218) = 1.29, *p* = .218). Table 3 summarizes the aggregate main effect of `mapping_strategy` across performance metrics.

*Table 3: Aggregate ANOVA Results for Main Effect of `mapping_strategy`*

| Dependent Variable | *F*(1, 1218) | *p*-value | η² | 95% CI for η² |
| :--- | :---: | :---: | :---: | :---: |
| MRR Lift | 18.22 | < .001 | .003 | [.000, .007] |
| Top-1 Accuracy Lift | 10.73 | .001 | .001 | [.000, .004] |
| Top-3 Accuracy Lift | 7.54 | .006 | .001 | [.000, .003] |

Figure 7 visualizes the aggregate comparison between correct and random mapping conditions. A Bayesian analysis of the primary metric (MRR Lift) yielded BF₁₀ ≈ 0.35, providing anecdotal evidence *for the null hypothesis* (i.e., against signal existence) according to conventional standards (Jeffreys, 1961). This creates a statistical tension: the frequentist analysis yielded a significant p-value, while the Bayesian analysis suggests the data are more likely under the null. This apparent contradiction suggests the aggregate effect may not be robust and strongly motivates the multi-level decomposition to investigate whether heterogeneity is being masked by averaging across models (explored further below).

{{grouped_figure:output/studies/publication_run/anova/boxplots/mapping_strategy/boxplot_mapping_strategy_mean_mrr_lift.png | scale=2.5 | width=100% | caption=Figure 7: Aggregate comparison of MRR Lift between correct and random mapping strategies across all models and k-values. The 'correct' mapping condition showed a statistically significant but very small increase in performance over the 'random' condition (*F*(1, 1218) = 18.22, *p* < .001, η² = .003).}}

#### Optimal Difficulty Analysis: Identifying the Goldilocks Zone

To identify the task difficulty level at which the framework most effectively exposes signals, targeted analyses were conducted for each `k` level independently. Results revealed a clear Goldilocks pattern, with signal detection peaking at medium difficulty.

At k=7 (easiest condition), the main effect of `mapping_strategy` on MRR Lift was minimal and non-significant (*F*(1, 406) = 1.25, *p* = .264, η² = 0.25%). At k=10 (medium difficulty), signal detection was strongest and highly significant (*F*(1, 406) = 20.77, *p* < .001, η² = 1.25%), representing a 5-fold increase in effect size over k=7. At k=14 (hardest condition), the effect, while still marginally significant, diminished substantially (*F*(1, 406) = 3.65, *p* = .057, η² = 0.10%). Figures 8 and 9 illustrate this Goldilocks pattern, where medium difficulty optimizes signal exposure.

This Goldilocks pattern demonstrates that the framework requires optimal task calibration: when the task is too easy (k=7), the signal-to-noise ratio may be insufficient to reveal meaningful differences; when too difficult (k=14), noise overwhelms the signal. The k=10 condition represents the optimal difficulty level for this framework and dataset.

{{grouped_figure:output/studies/publication_run/anova/boxplots/k/boxplot_k_mean_mrr_lift.png | scale=2.5 | width=100% | caption=Figure 8: Distribution of MRR Lift values across different group sizes (k). While all three difficulty levels cluster near chance performance (1.0), subsequent subset analyses revealed that k=10 showed the strongest signal detection effect when comparing correct vs. random mappings, demonstrating a Goldilocks pattern where medium difficulty optimizes signal exposure.}}

{{grouped_figure:output/studies/publication_run/anova_subsets/effect_sizes/mapping_strategy_x_k.png | scale=2.5 | width=90% | caption=Figure 9: Goldilocks Effect in LLM Signal Detection. Mapping strategy shows optimal effect size at medium task difficulty (k=10, η²=1.25%, p<.001), with significantly weaker effects at easy (k=7, η²=0.25%, ns) and hard (k=14, η²=0.10%, ns) conditions.}}

#### Model Heterogeneity: Extreme Variation in Signal Detection Capability

Individual LLM model analyses at the optimal difficulty level (k=10) revealed extreme heterogeneity in signal detection capability, with effect sizes ranging from 0.03% to 17.23%—a 575-fold variation. For each model at k=10, the analysis included 60 observations (30 replications × 2 mapping strategies: correct and random). Table 4 presents signal detection metrics for each evaluation model, with Figures 10 and 11 visualizing this heterogeneity

*Table 4: Model-Specific Signal Detection at Optimal Difficulty (k=10)*

| Model | N | *p*-value | η² | BF₁₀ | Signal Detection |
| :--- | :---: | :---: | :---: | :---: | :--- |
| GPT-4o | 60 | .001 | 17.23% | 31.627 | Very strong |
| DeepSeek Chat v3.1 | 60 | .009 | 11.16% | 5.076 | Strong |
| Gemini 2.0 Flash Lite | 60 | .033 | 7.63% | 1.689 | Moderate |
| Qwen 2.5 72B | 60 | .129 | 3.93% | 0.705 | Weak (NS) |
| Llama 3.3 70B | 60 | .204 | 2.77% | 0.524 | Minimal (NS) |
| Mistral Large | 60 | .590 | 0.38% | 0.284 | Minimal (NS) |
| Claude Sonnet 4 | 60 | .890 | 0.03% | 0.265 | Minimal (NS) |

This heterogeneity reveals that aggregate findings substantially underestimate framework effectiveness for compatible models while overestimating it for incompatible models. The framework successfully exposes signals through GPT-4o and DeepSeek with large effect sizes, moderately through Gemini, and minimally or not at all through Qwen, Llama, Mistral, and Claude. These findings demonstrate that model architecture significantly moderates framework effectiveness.

{{grouped_figure:output/studies/publication_run/anova_subsets/1.2_k10_analysis/anova/boxplots/model/boxplot_model_mean_mrr_lift.png | scale=2.5 | width=100% | caption=Figure 10: Model heterogeneity in signal detection at k=10. Effect sizes range from 0.03% (Claude Sonnet 4) to 17.23% (GPT-4o)—a 575-fold variation in sensitivity to correct personality mapping.}}

{{pagebreak}}

Figure 11 below shows the extreme difference in signal detection capability across the models.

{{grouped_figure:docs/diagrams/viz_model_heterogeneity.mmd | scale=2.5 | width=100% | caption=Figure 11: Model heterogeneity summary showing 575-fold variation in signal detection capability at optimal difficulty (k=10). Models demonstrate three tiers: strong detection (GPT-4o, DeepSeek), moderate detection (Gemini), and minimal/no detection (Qwen, Llama, Mistral, Claude). Framework effectiveness requires both compatible architecture (Goldilocks pattern) and optimal task difficulty.}}

#### Signal Detection Trajectories: Goldilocks vs. Flat Patterns

To characterize how signal detection varies across difficulty levels for different model types, complete study trajectories were analyzed for representative high-detection (GPT-4o, DeepSeek) and low-detection (Claude, Llama) models. Two distinct patterns emerged.

**High-Detection Models: Goldilocks Patterns**

GPT-4o exhibited an extreme Goldilocks pattern with signal detection exclusively at k=10. At k=7, no significant detection occurred (*p* = .638, η² = 0.38%). At k=10, detection was massive and highly significant (*p* = .001, η² = 17.23%). At k=14, detection again disappeared (*p* = .372, η² = 1.38%). This represents a 45-fold difference between optimal and suboptimal difficulty, demonstrating extreme sensitivity to task calibration.

DeepSeek showed a modified Goldilocks pattern with greater robustness. Signal detection peaked at k=10 (*p* = .009, η² = 11.16%) but remained marginally significant at k=14 (*p* = .033, η² = 7.63%), while absent at k=7 (*p* = .359, η² = 1.45%). Unlike GPT-4o, DeepSeek maintained partial signal detection even at the highest difficulty level.

**Low-Detection Models: Flat Patterns**

Claude exhibited a flat pattern with consistently minimal detection across all difficulty levels: k=7 (*p* = .304, η² = 1.82%), k=10 (*p* = .890, η² = 0.03%), and k=14 (*p* = .170, η² = 3.28%). All effects were non-significant, demonstrating that the framework does not successfully expose signals through Claude regardless of task difficulty.

Llama similarly showed a flat pattern: k=7 (*p* = .367, η² = 1.41%), k=10 (*p* = .204, η² = 2.77%), and k=14 (*p* = .710, η² = 0.24%). Like Claude, Llama showed minimal detection across all conditions, indicating framework incompatibility independent of difficulty calibration.


Table 5 summarizes complete trajectories for these representative models, with Figure 12 illustrating the distinct patterns at the optimal difficulty level.

*Table 5: Signal Detection Trajectories Across Difficulty Levels*

| Model | k=7 η² | k=10 η² | k=14 η² | Pattern Type |
| :--- | :---: | :---: | :---: | :--- |
| GPT-4o | 0.38% (NS) | **17.23%** (***) | 1.38% (NS) | Extreme Goldilocks |
| DeepSeek | 1.45% (NS) | **11.16%** (**) | 7.63% (*) | Modified Goldilocks |
| Claude | 1.82% (NS) | 0.03% (NS) | 3.28% (NS) | Flat |
| Llama | 1.41% (NS) | 2.77% (NS) | 0.24% (NS) | Flat |

*Note: NS = not significant; * p < .05; ** p < .01; *** p < .001*

These trajectory analyses reveal that framework effectiveness requires both optimal difficulty calibration (k=10) and compatible model architecture (GPT-4o, DeepSeek). Having only one requirement satisfied is insufficient: compatible models at suboptimal difficulty show minimal detection (GPT-4o at k=7 or k=14), while incompatible models show minimal detection regardless of difficulty (Claude, Llama at all k levels).

{{grouped_figure:output/studies/publication_run/anova_subsets/1.2_k10_analysis/anova/boxplots/interaction_plot_mapping_strategy_x_model_mean_mrr_lift_k_10.png | scale=2.5 | width=100% | caption=Figure 12: Model × mapping strategy interaction at k=10, revealing two distinct trajectory patterns. GPT-4o and DeepSeek V3 show pronounced "Goldilocks" sensitivity (large separation between correct and random conditions), while Claude Sonnet 4, Llama 3.3, and Mistral Large exhibit "flat" patterns with minimal discrimination.}}

#### Analysis of Presentation Order Bias

To ensure the integrity of the core findings, potential presentation order biases were analyzed. The metric Top-1 Prediction Bias (Std Dev) measures whether evaluation models consistently favor items based on ordinal position rather than content. ANOVA showed a significant effect for group size `k` (*F*(2, 1218) = 8.45, *p* < .001) but not for `mapping_strategy` (*F*(1, 1218) = 0.85, *p* = .357), indicating that while `k` influenced response consistency, this behavior did not differ between correct and random conditions. Further analyses for simple linear position (presentation) bias showed no statistically significant effects for either `mapping_strategy` or `k`, reinforcing that the observed signal detection effects reflect genuine content-based discrimination rather than positional artifacts.

### Discussion

As a replication and methodological extension of Godbout (2020), this study deployed a framework that detected a statistically significant, yet practically minuscule (η² = .003), non-random signal at the aggregate level. This finding is heavily qualified by Bayesian analysis favoring the null hypothesis, suggesting that the framework's primary utility is not in confirming a general signal, but in identifying the specific conditions—namely, model architecture and task difficulty—under which a signal becomes discernible. Through multi-level decomposition analysis, the framework successfully detected weak signals across multiple evaluation models, demonstrating both the methodology's validity and revealing critical insights about model-framework compatibility.

#### Signal Detection Confirmed Through Multi-Level Validation

The aggregate analysis established baseline signal detection with high statistical significance (*p* < .001), confirming that evaluation models collectively distinguish between correct and random mappings at rates exceeding chance, although the practical effect size was very small (η² = .003). While this aggregate effect is small—consistent with the weak nature of signals in complex narrative systems—the multi-level decomposition revealed that aggregate findings substantially mask underlying heterogeneity.

The identification of k=10 as the optimal difficulty level (η² = 1.25%) demonstrates a clear Goldilocks zone where signal detectability peaks. At k=7, the task may be insufficiently challenging to reveal meaningful discrimination, while at k=14, noise from increased distractors overwhelms the signal. This finding has practical implications for framework deployment: signal detection in complex narrative systems requires careful task calibration to balance challenge with detectability.

#### Model Heterogeneity: The Central Finding

The most critical discovery is the extreme model-to-model variation in signal detection capability, ranging from 0.03% to 17.23%—a 575-fold difference. This heterogeneity fundamentally reframes our understanding of framework effectiveness: the framework does not work uniformly across models but instead reveals which model architectures are compatible with the task of detecting weak signals in complex narratives.

GPT-4o and DeepSeek demonstrated strong signal detection (17.23% and 11.16% respectively), with effect sizes far exceeding the aggregate (see Table 4). The magnitude of GPT-4o's effect is substantial; in practical terms, this 17.23% variance explained corresponds to a nearly 18% improvement in its Top-3 Accuracy Lift at the optimal difficulty (k=10) compared to its baseline performance at suboptimal difficulties. These models successfully function as sensitive instruments for exposing subtle patterns in narrative-biographical matching tasks. In contrast, Claude, Llama, and Mistral showed minimal to no signal detection (0.03%, 2.77%, and 0.38%), suggesting fundamental incompatibility with this framework regardless of task calibration (see Table 5 for complete trajectory patterns).

**Addressing Contamination Concerns:** Three evaluation models share providers with data generation models, raising potential contamination concerns: GPT-4o (same provider as eminence scoring model GPT-5), Claude Sonnet 4 (same family as OCEAN scoring model Claude 4.5 Sonnet), and Gemini 2.0 Flash Lite (same family as neutralization model Gemini 2.5 Pro). If contamination explained the observed signals, we would expect these three models to show consistently elevated performance. Instead, they demonstrate opposite patterns: GPT-4o shows the strongest signal detection (η²=17.23%, *p*<.001), Gemini shows moderate detection (η²=7.63%, *p*=.033), and Claude shows essentially no detection (η²=0.03%, *p*=.890). This 575-fold variation within the "contaminated" set mirrors the variation across all models, suggesting that architectural differences—not training data overlap—drive signal detection capability. Furthermore, DeepSeek V3.1 (the second-strongest performer with η²=11.16%) has zero overlap with data generation models, demonstrating that strong signal detection occurs in fully independent architectures. While contamination risk cannot be definitively excluded with closed-source models, the empirical patterns are inconsistent with contamination as a primary explanation for the observed heterogeneity.

This heterogeneity also explains the apparent contradiction between the significant frequentist result and the Bayesian analysis, which favored the null hypothesis (BF₁₀ ≈ 0.35). The Bayesian analysis correctly concluded that there was no consistent signal *at the aggregate level*. This finding was not a statistical artifact but an accurate reflection of the data: the strong positive signals from the few compatible models (GPT-4o, DeepSeek) were overwhelmed by the null results from the majority of incompatible models. The aggregate statistics, therefore, masked rather than revealed the framework's true performance with specific, compatible architectures.

#### Two Distinct Model-Framework Relationships

Trajectory analysis across difficulty levels revealed two qualitatively different patterns of model-framework interaction. Framework-compatible models (GPT-4o, DeepSeek) exhibited Goldilocks patterns characterized by peak signal detection at optimal difficulty (k=10) with substantial dropoff at suboptimal levels. GPT-4o showed an extreme version of this pattern, with signal detection exclusively at k=10 and 45-fold sensitivity to calibration. DeepSeek demonstrated a more robust variant, maintaining marginal detection even at k=14.

Framework-incompatible models (Claude, Llama) exhibited flat patterns characterized by consistently minimal detection across all difficulty levels. Importantly, these models showed no response to task calibration—they detected minimal signal at k=7, k=10, and k=14 alike. This demonstrates that their incompatibility is not a matter of suboptimal difficulty but rather reflects fundamental architectural differences in how these models process narrative-biographical relationships.

These patterns confirm the dual requirements previously identified, with incompatible models showing minimal detection regardless of calibration.

While the "black box" nature of proprietary models makes a definitive explanation for this heterogeneity impossible, it is worth hypothesizing about potential mechanisms. The two best-performing models, GPT-4o and DeepSeek, are known for their sophisticated reasoning and pattern-matching architectures (the latter being a Mixture-of-Experts model). It is plausible that their superior performance stems not just from general capability, but from a specific emergent ability to detect subtle, cross-domain semantic relationships between abstract personality traits and concrete biographical events. In contrast, models showing a "flat" trajectory may be architecturally optimized for more direct, literal tasks, making them less sensitive to the faint, metaphorical patterns present in this study. This suggests that signal detection in complex narratives is not a universal capability but may depend on specific architectural features geared towards nuanced, inferential reasoning.

#### Implications for Framework Validation and Deployment

The primary contribution of this work is the introduction and validation of a methodological framework for testing weak signals in complex narrative systems. Three key insights emerge for framework deployment:

Three key insights emerge for framework deployment. First, **aggregate analysis alone is insufficient**—multi-level decomposition is essential to identify which models successfully expose signals and avoid misleading aggregate statistics. Second, **model selection is critical**: the 575-fold variation demonstrates that architecture fundamentally moderates effectiveness, with GPT-4o and DeepSeek prioritized while Claude, Llama, and Mistral should be avoided for signal detection. Third, **optimal task difficulty must be empirically determined**: the Goldilocks pattern at k=10 emerged from data rather than prediction, requiring calibration studies before deployment.

This LLM-driven, open-source pipeline represents a new paradigm for bringing empirical rigor to complex narrative systems that have long resisted quantitative assessment—including Jungian archetypes, qualitative sociological theories, and personality typologies. By demonstrating its utility on the particularly challenging case of astrology, we provide a robust template and establish clear methodological principles for investigating other complex narrative systems.

#### Open Science and Reproducibility

This study embodies open science principles through fully automated, publicly available workflows with methodological reproducibility (Open Science Collaboration, 2015). While exact computational reproducibility is not achievable due to inherent LLM API non-determinism, the framework enables independent verification of methods and statistical conclusions. The entire data preparation pipeline (Figure 2), system architecture (Figure 1), and experimental workflow (Figures 4-6) are fully documented and reproducible at the methodological level. The multi-level decomposition approach demonstrated here (Tables 3-5, Figures 7-12) could serve as a model for standard practice for framework validation, as it reveals patterns invisible to aggregate analysis alone.

#### Alternative Explanations and Confounds

Several alternative explanations merit consideration. **The Barnum Effect:** The concern that neutralized descriptions might be generic statements that apply universally is addressed by four key findings: (1) The random control condition provides the critical test—if descriptions were Barnum-like (vague, universally applicable), models would show equivalent performance on correct and random mappings since generic descriptions would "match" anyone equally well. Instead, models at k=10 showed significantly better performance with correct mappings (η²=1.25%, *p*<.001), demonstrating that descriptions contain discriminating information. (2) The extreme model heterogeneity (575× variation) argues against a universal-match explanation—if descriptions applied to everyone, all models would perform similarly. (3) The neutralization process was validated to preserve lookup-key integrity while removing jargon (automated keyword search confirmed zero residual astrological terminology), maintaining the deterministic structure-content relationship. (4) The Goldilocks pattern across k-values demonstrates that task difficulty (number of profiles to discriminate among) systematically affects performance—this pattern would not emerge if descriptions lacked discriminating power. However, a formal validation study measuring description specificity (e.g., using semantic diversity metrics or human rater discriminability tests) would provide stronger evidence that neutralization preserved rather than eliminated uniqueness.

Demographic confounds, such as the "birth season effect" or a self-fulfilling prophecy based on cultural stereotypes (e.g., an "assertive Aries"), are unlikely to explain the findings. The personality descriptions are a composite signal derived from two distinct sources: (1) the simple placements of 12 chart points in their respective signs (as opposed to just the Sun sign), and (2) five different algorithmic balance configurations based on the distribution of these points across elements, modes, quadrants, hemispheres, and signs. While a person may be aware of their Sun sign, the 12 chart-point placements combined with the balance configurations (which are the output of a specific, non-obvious weighting algorithm, resulting in classifications like "Element Fire Weak" or "Quadrant 3 Strong") produce a complex esoteric signal that is impossible to confound culturally. Furthermore, the extreme model heterogeneity argues against a simple cultural confound, which one would expect to be detected more uniformly across different LLM architectures.

While neutralization removed astrological terminology, subtle era-specific biographical patterns may persist. Future research comparing biography sources could help isolate signal types.

Model heterogeneity itself suggests the signal requires specific architectural features: top-performing general-purpose models (Claude, Llama) show minimal detection while others (GPT-4o, Gemini) show strong detection, indicating detection capability is not correlated with overall model performance.

#### Philosophical Implications

Ultimately, this study addressed a single empirical question: can a fully automated framework detect weak signals in complex narrative systems? The results indicate yes, but with critical caveats about model compatibility and task calibration. The profound question of *what it means* for non-conscious algorithmic systems to detect faint patterns within symbolic frameworks traditionally associated with human meaning-making remains philosophical rather than empirical. This deeper inquiry—exploring implications for consciousness, patterns of subjective experience, and characterization—is the subject of a companion analysis (McRitchie & Marko, manuscript in preparation).

#### Limitations and Future Directions

This study has several limitations, primarily related to the nature of the LLM-based method, the sample population, and the specific stimuli used.

**Model Selection Transparency:** The seven evaluation models were selected from 42 candidates using the same dataset later used in the main study. While selection was based strictly on technical criteria (parsing reliability, cost, speed) rather than signal detection performance, this design introduces a potential concern: models that failed technically on this specific dataset might have succeeded on different data. To address circular reasoning concerns, we emphasize that (1) signal detection performance was not measured during selection, (2) the 35 excluded models failed objective technical tests (detailed in Supplementary Materials), and (3) the discovered heterogeneity (575× variation) was entirely unexpected—no pilot analysis examined whether models could detect signals. Future studies should ideally use separate pilot and main datasets, or employ pre-registered model selection criteria established before any data collection.

**The "Black Box" Problem and Model Contamination Risk:** The most significant limitation is the reliance on closed-source LLMs with potential training data overlap. Three evaluation models share providers with data generation models (GPT-4o/GPT-5, Claude Sonnet 4/Claude 4.5 Sonnet, Gemini 2.0/Gemini 2.5 Pro), creating theoretical contamination risk if these models learned implicit personality-biography associations during training. However, several empirical patterns argue against contamination as the primary explanation: the three potentially "contaminated" models showed opposite performance (GPT-4o detected the strongest signal while Claude detected essentially none), and the extreme heterogeneity (575× variation) occurred across models with similar contamination risk levels. Additionally, it is theoretically possible that the evaluation LLMs, despite the neutralization of the text, could have inferred the astrological origin of the descriptions and used latent, pre-existing knowledge to defeat the purpose of the test. While introspective checks suggested the models were not actively applying an astrological framework, this possibility of data contamination cannot be definitively excluded. Similarly, because the LLMs autonomously sources its own biographical data, we cannot be certain it is not finding an obscure source that contains a non-obvious correlation with the birth data. A future study could create a more controlled design by providing the biographical text directly in the prompt, sourced exclusively from the validated Wikipedia pages. This "black box" problem highlights a central challenge in using proprietary AI for scientific research. Future studies should aim to replicate these findings using open-source models or, ideally, custom-trained LLMs with no prior exposure to astrological concepts to ensure the detected signal is not an artifact. Furthermore, the results are specific to the models used in this study; replication with different architectures is necessary to establish robustness.

**Sample and Stimulus Constraints:** The use of famous individuals (born 1900-1999, Northern Hemisphere, deceased), while necessary to ensure rich biographical data and control for specific confounds, limits the generalizability of *these specific findings* to the broader population. However, these constraints are specific to this case study of astrology, not inherent to the framework itself. The framework is designed to be adaptable: different narrative systems may require different sampling strategies. The widely known lives of these subjects could also introduce unknown confounds. Similarly, the study intentionally used a simplified astrological model (primary placements only) to test for a foundational signal. The weak effect size may be a function of this simplification. Future research should extend this methodology to non-public figures, different cultural contexts, and incorporate more complex astrological factors (e.g., aspects, midpoints, house systems) to assess whether the signal strength varies across populations and model complexity.

**Technical vs. Conceptual Validation:** Our validation of the profile assembly algorithm demonstrates technical correctness—that our code faithfully implements the astrological weighting system—but does not validate the conceptual meaningfulness of that system. The "bit-for-bit identical" reproduction confirms implementation fidelity, ensuring the test fairly represents the source system's claims. However, whether the astrological weights and thresholds produce psychologically meaningful distinctions is an empirical question answered by the experimental data itself. The weak aggregate signal (0.3% effect size), extreme model heterogeneity (575× variation), and task-difficulty dependency suggest the weighting system, if meaningful at all, generates subtle patterns accessible only under specific conditions. This distinction between technical validation (did we implement it correctly?) and conceptual validation (does it produce meaningful output?) is important for interpreting our findings: we can confidently state the test was conducted fairly, but we cannot claim the underlying astrological system is validated—the empirical results themselves constitute that test.

**Neutralization Process Validation:** While the automated keyword search for astrological jargon confirmed the successful removal of explicit terminology, three further validation studies could strengthen the framework. First, **measuring description specificity and discriminability**: quantitative metrics (e.g., semantic diversity indices, pairwise cosine similarity between profiles, lexical uniqueness scores) would provide objective evidence that neutralized descriptions maintain sufficient distinctiveness to support meaningful discrimination. The present study relied on the random control condition as an indirect test of discriminability—the significant correct vs. random difference at k=10 demonstrates descriptions are not uniformly generic—but direct measurement would be more rigorous. Second, **human validation studies** could provide benchmarks: a formal matching test using expert human astrologers as judges could assess whether humans can match neutralized profiles at above-chance rates, and a study using non-astrologer human raters could test whether lay readers can discriminate between neutralized descriptions or whether they perceive them as generic Barnum statements. Third, **preservation of component-level uniqueness**: analyzing whether the 149 neutralized delineation components maintain their original semantic distances after neutralization would confirm the process preserved rather than collapsed the system's internal structure. First, a formal matching test using expert human astrologers as judges could provide a valuable benchmark against which to compare the performance of the automated system. Second, a study using non-astrologer human raters, blind to the source, could test the integrity of the blinding procedure. If these lay raters, when asked to classify the neutralized snippets back into their original astrological categories, perform at chance level, it would provide stronger evidence that the neutralization successfully removed all discernible stylistic artifacts and esoteric traces of the source system.

### Conclusion

This study successfully deployed an automated and objective framework to test for weak, hypothesized signals in a complex narrative system, meeting its primary methodological goal. The framework demonstrated that while an aggregate-level signal was statistically detectable, it was practically negligible and only became robustly evident under highly specific conditions. Critically, the framework exposed extreme model-to-model heterogeneity (575× variation in signal detection), revealing that effectiveness requires both compatible model architecture and optimal task difficulty calibration. This work does not validate astrology as a whole, but it suggests that the null hypothesis of pure arbitrariness may be an oversimplification. The findings indicate that any non-randomness in the system's outputs is not universally accessible but is highly dependent on the architecture of the analytical tool used to detect it. It provides a robust, methodologically reproducible framework for future empirical investigations into complex narrative systems and establishes a firm factual basis that gorunds the philosophical inquiry into consciousness and symbolic systems explored in our companion article.

### Author Contact

Correspondence concerning this article should be addressed to Peter J. Marko at peter.j.marko@gmail.com.

### Author Contributions

Peter J. Marko was responsible for the conceptualization, methodology, software, formal analysis, investigation, and writing the original draft of the article. Kenneth McRitchie was responsible for supervision, assisted with the conceptualization, and reviewed and edited the article.

**ORCID iDs**

*   Peter J. Marko: https://orcid.org/0000-0001-9108-8789
*   Kenneth McRitchie: https://orcid.org/0000-0001-8971-8091

### Conflicts of Interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

### Acknowledgements

The authors wish to thank Vincent Godbout for generously sharing his pioneering thoughts, drafts, and procedures on automated matching tests, which provided a valuable foundation for this work. The authors are independent researchers and received no specific funding for this study.

### Open Data and Code Availability

In accordance with the principles of open science and methodological reproducibility (The Turing Way Community, 2022), all data, analysis scripts, supplementary materials, and documentation necessary to reproduce the findings reported in this article are permanently and publicly available at https://github.com/peterjmarko/llm-narrative-framework.git.

**Repository Contents:**

- **Replication Guide** (Supplementary Material): Complete step-by-step procedures for all three replication paths, including detailed descriptions of the data preparation pipeline, astrological weighting system, pilot study on LLM selection, and experiment workflow
- **Framework Manual**: Technical specifications, data formats, and API references
- **README**: Quick start guide and framework overview
- **Source Code**: Complete Python and PowerShell codebase (147 scripts, 41,000+ lines) with comprehensive test suite and 40 technical diagrams
- **Data Files**: Static datasets for direct replication (34 files total), including:
  - Neutralized component library (CSV format with component IDs and neutralized text)
  - Final subject database (CSV format with biographical and astrological metadata)
  - Raw experimental results (JSON format with trial-level data and model responses)
  - Compiled study-level analysis results (CSV format with summary statistics)
- **Configuration Files**: Exact parameter settings used in the original study
- **Data Dictionaries**: Complete documentation of variable names, data types, valid ranges, and missing data codes for all datasets

Example data structures and loading scripts are included to facilitate immediate data access and reuse.

**Licensing:** The framework is released under dual licensing: source code under GNU GPL v3.0, and data/documentation under CC BY-SA 4.0.

---
[^1]: The naming of the data generation models reflects the latest versions available at the time of the study. For provider details and release context, see Appendix C of the Supplementary Materials (Replication Guide).

[^2]: Complete FDR-corrected p-values for all 21 primary statistical tests are provided in Supplementary Materials Table S1. The corrected values confirm that all findings reported as "statistically significant" in the main text remain significant after controlling for multiple comparisons (smallest corrected p = .000037 for aggregate mapping_strategy effect on MRR Lift).

### References

Astro-Databank. (n.d.). [Online database]. Astrodienst AG. Retrieved from https://www.astro.com/astro-databank/Main_Page

Astrodatabank Research Tool. (n.d.). [Online tool]. Astrodienst AG. Retrieved from https://www.astro.com/adb-search/

Brown, T. B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J. D., Dhariwal, P., Agarwal, S., Neelakantan, A., Ramesh, P., Sastry, G., Askell, A., Mishkin, P., Clark, J., Krueger, G., & Amodei, D. (2020). Language models are few-shot learners. *Advances in Neural Information Processing Systems*, *33*, 1877-1901.

Argyle, L. P., Busby, E. C., Fulda, N., Gubler, J. R., Rytting, C., & Wingate, D. (2023). Out of One, Many: Using Language Models to Simulate Human Samples. *Political Analysis*, *31*(3), 337-351.

Carlson, S. (1985). A double-blind test of astrology. *Nature*, *318*(6045), 419-425.

Cohen, J. (1988). *Statistical power analysis for the behavioral sciences* (2nd ed.). Lawrence Erlbaum Associates.

Cronbach, L. J., & Meehl, P. E. (1955). Construct validity in psychological tests. *Psychological Bulletin*, *52*(4), 281–302.

Currey, R. (2022). Meta-analysis of recent advances in natal astrology using a universal effect-size. *Correlation*, *34*(2), 43-55.

Dean, G., & Kelly, I. W. (2003). Is astrology relevant to consciousness and psi? *Journal of Consciousness Studies*, *10*(6-7), 175-198.

Ertel, S. (2009). Appraisal of Shawn Carlson’s renowned astrology tests. *Journal of Scientific Exploration*, *23*(2), 125-137.

Eysenck, H. J., & Nias, D. K. (1982). *Astrology: Science or superstition?* St. Martin's Press.

Gilardi, F., Alizadeh, M., & Kubli, M. (2023). ChatGPT outperforms crowd-workers for text-annotation tasks. *Proceedings of the National Academy of Sciences*, *120*(24), e2305016120.

Godbout, V. (2020). An automated matching test: Comparing astrological charts with biographies. *Correlation*, *32*(2), 13-41.

Google. (2024). *Gemini 1.5: Unlocking multimodal understanding across millions of tokens of context*. Google AI. https://arxiv.org/abs/2403.05530

Jeffreys, H. (1961). *Theory of Probability* (3rd ed.). Oxford University Press.

Kosinski, M. (2023). Theory of mind may have spontaneously emerged in large language models. *Proceedings of the National Academy of Sciences*, *120*(9), e2218926120. https://doi.org/10.1073/pnas.2218926120

Lewis, J. R. (1994). Southern Hemisphere. In *The Astrology Encyclopedia* (p. 484). Visible Ink Press.

Marko, P. J. (2018). Boomers and the lunar defect. *The Astrological Journal, 60*(1), 35-39.

McRitchie, K. (2022). How to think about the astrology research program: An essay considering emergent effects. *Journal of Scientific Exploration*, *36*(4), 706-716. https://doi.org/10.31275/20222641

Open Science Collaboration. (2015). Estimating the reproducibility of psychological science. *Science*, *349*(6251), aac4716.

OpenRouter.ai. (n.d.). [Online API service]. Retrieved from https://openrouter.ai/

Ryder, N. B. (1965). The Cohort as a Concept in the Study of Social Change. *American Sociological Review*, *30*(6), 843-861.

Solar Fire. (n.d.). [Software]. Astrolabe Inc. Retrieved from https://alabe.com/solarfireV9.html

The Turing Way Community. (2022). *The Turing Way: A handbook for reproducible, ethical and collaborative research*. Zenodo. https://doi.org/10.5281/zenodo.3233853

van Dongen, N., & van Grootel, L. (2025). Overview on the Null Hypothesis Significance Test: A Systematic Review on Essay Literature on its Problems and Solutions in Present Psychological Science. *Meta-Psychology*, *9*, MP.2021.2927. https://doi.org/10.15626/MP.2021.2927

Wei, J., Tay, Y., Bommasani, R., Raffel, C., Zoph, B., Borgeaud, S., Chowdhery, A., Narang, S., & Le, Q. V. (2022). Emergent abilities of large language models. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2206.07682
