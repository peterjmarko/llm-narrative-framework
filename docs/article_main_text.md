---
title: "A Framework for the Computationally Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology"
author: "Peter J. Marko, Kenneth McRitchie"
date: "[Date]"
abstract: |
  **Background:** Psychology has struggled to empirically validate complex, holistic systems that produce narrative-based claims. This methodological gap highlights the need for new, more rigorous, and transparent research paradigms.
  **Objective:** This paper introduces and validates a novel, fully automated, and open-source framework for testing for weak signals in complex narratives. Using astrology as a challenging case study, we demonstrate a reproducible method for assessing the construct validity of a symbolic system against biographical data.
  **Methods:** A library of astrological descriptions was programmatically neutralized by a Large Language Model (LLM) to remove all esoteric terminology. A pre-filtered cohort of historically eminent individuals was rank-ordered by an LLM-generated score, and the final subject pool was determined by a data-driven cutoff, stopping when the personality diversity of new subjects (measured by the variance of their LLM-generated OCEAN scores) showed a sustained decline. An independent LLM was then used as an impartial arbiter to perform a series of matching tasks. In each trial, the LLM was tasked with correctly pairing a small group of biographies, drawn from a final pool of 6,000 eminent individuals, with their corresponding personality descriptions. All code, data, and materials are publicly available.
  **Results:** A two-way ANOVA revealed a statistically significant main effect for the matching condition, with the LLM's performance being higher for "correct" pairings than for "random" pairings (*F*(1, 348) = 6.27, *p* = .013, η² = .015), indicating the detection of a weak but non-random signal. A complementary Bayesian analysis provided anecdotal evidence for the same conclusion (BF₁₀ ≈ 1.61).
  **Conclusion:** This study's primary contribution is a new, open-science paradigm for psychological research. By demonstrating its utility on a difficult and controversial topic, we provide a robust, computationally reproducible, and scalable framework for future investigations into complex narrative systems.
---

**Keywords:** Psychology, astrology, large language models, computational social science, reproducibility, open science

### Introduction

The replication crisis has spurred a fierce and ongoing debate within psychological science about methodological reform (van Dongen & van Grootel, 2025). A key challenge in this landscape is establishing the **construct validity** (i.e., whether a system measures what it claims to measure) of complex, holistic systems that generate narrative-based claims. Astrology serves as a prime example, where landmark empirical studies have faced significant methodological debate over their design and analysis (Carlson, 1985; Eysenck & Nias, 1982; Ertel, 2009). While modern "whole-chart" matching tests show promise (Currey, 2022; Godbout, 2020), even recent computational explorations have been limited by a reliance on opaque "black-box" tools and manual processes (Marko, 2018). This history highlights the need for a fully automated, transparent, and scalable testing framework.

The advent of Large Language Models (LLMs) presents an opportunity to develop such a framework. Prior research on construct validity has often employed matching tests, where judges attempt to pair descriptions with their corresponding subjects (e.g., Carlson, 1985; Godbout, 2020). LLMs, as powerful pattern-recognition engines (Google, 2024; Wei et al., 2022), are uniquely suited to automate this process. Unlike human judges, who are susceptible to cognitive biases, LLMs can be deployed as **agnostic arbiters**, executing a matching task at a massive scale. This study introduces and validates such an LLM-based framework, using astrology as a challenging case study.

The primary goal is to determine if a fully automated pipeline can serve as a sensitive instrument for detecting weak signals in complex, narrative-based claims. To this end, the study tests a single, core hypothesis: *that the LLM-based framework can distinguish between correctly mapped and randomly mapped personality descriptions at a rate significantly greater than chance.* While the successful detection of such a signal within the case study has implications for that field, the broader contribution of this work is the validation of the methodology itself. The philosophical implications of using a non-conscious system to analyze a framework of human meaning are taken up in a companion article (McRitchie & Marko, manuscript in preparation).

### Methods

#### Sample Population

The framework supports two research paths. For **direct replication**, this study used a static dataset from the Astro-Databank (ADB), which is included in the project's public repository. For **conceptual replication**, the framework includes an automated tool to acquire current data from the live ADB.

The final study sample was derived from an initial query of over 10,000 famous individuals with high-quality birth data (Rodden Rating 'AA' or 'A') and a recorded death date. This raw data was processed through a fully automated, multi-stage pipeline designed for efficiency and reproducibility.

First, a validation script audited each candidate against their English Wikipedia page, a methodological control for ensuring a consistent biographical source for the LLM. To guarantee reproducibility, the results of this one-time audit were archived and used as a static master filter in the next step. A second script then performed a rigorous pre-filtering, retaining only candidates who had passed validation, had a validly formatted birth time, a birth year within 1900-1999, and were not duplicates. This produced a clean cohort of "eligible candidates."

This eligible cohort was then subjected to a two-stage scoring process to determine the final sample. First, **OpenAI's GPT-5** generated a static eminence score—defined as lasting historical impact—for each candidate, creating a rank-ordered list of all viable subjects. Second, a separate script processed these subjects in descending order of eminence, querying **Anthropic's Claude 4 Sonnet** for Big Five (OCEAN) personality scores. This script's primary function was to establish a data-driven cutoff for the final sample size. It employed a robust "M of N" stopping rule, halting automatically when the average variance of personality scores in new windows of subjects showed a sustained decline relative to a fixed benchmark derived from the top 500 most eminent individuals. The script is designed for resilience; its pre-flight check re-analyzes all existing data on startup, ensuring that interrupted runs can be safely resumed or correctly finalized without user intervention. This process yielded the final sample of 6,000 subjects used in the study, ensuring the population was both eminent and psychologically diverse. The use of publicly available data of deceased historical individuals obviated privacy concerns.

#### Preparation of Personality Descriptions

The personality descriptions used as test interventions were generated through a multi-step process.

##### Component Library Neutralization and Validation

To create a robust, double-blind experimental design, the entire library of interpretive delineations within the **Solar Fire v9.0.3** expert system (Astrolabe Inc., n.d.) was systematically de-jargonized. The primary goal of this "neutralization" process was to remove all astrological terminology while preserving core descriptive meaning. This library of components was processed by **Google' Gemini 2.5 Pro** using a hybrid, two-stage strategy. First, a high-speed pass bundled related texts into large API calls for efficiency. Second, a robust resume pass automatically re-processed any failed tasks individually, guaranteeing completion by breaking down large requests that could be truncated by the LLM. Each snippet was rewritten using the following prompt:
> *"Revise the attached text. You MUST follow these rules: 1. Lines starting with an asterisk (*) are headings. Do NOT revise them; they must remain intact. 2. Remove all references to astrology, astronomy, time periods, and generations. 3. Shift the perspective to an impersonal, objective, neutral third-person style. 4. Do NOT use phrases like "You are," "One sees oneself," "Individuals with this configuration," or any phrasing that refers to "a person." Describe the trait directly. 5. Correct for grammar and spelling. 6. Preserve the core psychological meaning of the original text. 7. Your entire response must be ONLY the revised text block in the same format as the original. Do not add any commentary."*

The lines marked with an asterisk (e.g., `*Moon in Aries`) are the unique identifiers for each delineation and were preserved verbatim to serve as lookup keys in the neutralized library. This process created a master database of neutralized components. To validate the neutralization, an automated keyword search for over 150 astrological terms confirmed that no explicit terminology remained. Table 1 provides an example of this process. It is acknowledged that this neutralization results in a loss of nuance compared to the original text, a necessary trade-off for achieving a robust blinding procedure. The strengths of this automated approach, particularly its scalability and consistency, are a key advancement over previous methods.

*Table 1: Example of Text Neutralization*

| Original Astrological Text (Sun in Aries) | Neutralized Text |
| :--- | :--- |
| "Your Sun is in the zodiac sign of Aries indicating that you're an assertive and freedom-loving individual, with a strong need for independence. Others may call you headstrong, but you simply believe that everyone has a right to assert themselves in any situation. Life presents many challenges which you enjoy meeting head-on regardless of the obstacles along the way..." | "Is assertive and freedom-loving, with a strong need for independence. May be perceived as headstrong, but believes that everyone has a right to assert themselves. Enjoys meeting life's challenges head-on regardless of obstacles. Possesses natural leadership qualities. The ability to focus on personal goals is a healthy trait, though a balance is needed to include others' points of view..." |

##### Profile Assembly from Astrological Placements

For each of the 6,000 individuals in the study database, a foundational set of astrological placements was exported from Solar Fire. This structured data included the factors necessary to generate two reports: the "Balances" (Planetary Dominance) report, covering signs, elements, modes (qualities), quadrants, and hemispheres; and the "Chart Points" report, covering the sign placements of the 12 key chart points (Sun through Pluto, Ascendant, and Midheaven). The specific weighting and threshold settings used for the "Balances" report are detailed in the **Supplementary Materials** available in the project's online repository. This foundational set of factors was chosen deliberately to test for a primary, non-interactive signal while minimizing the confounding variables that could arise from more complex astrological techniques, such as planetary aspects or midpoints.

Each individual's complete personality profile was then programmatically assembled. Their specific set of astrological placements was used as a key to look up and concatenate the corresponding pre-neutralized description components from the validated master database. This assembly process resulted in a unique, composite personality profile for each individual, expressed in neutral language, which formed the basis of the stimuli used in the matching task.

#### Experimental Design and Procedure

The study employed a 2 x 6 factorial design. The independent variables were:

*   **`mapping_strategy`**: A between-groups factor with two levels: `correct` (descriptions were correctly paired with biographical profiles) and `random` (descriptions were randomly shuffled and paired).
*   **`k` (Group Size)**: A within-groups factor representing the number of subjects to be matched in a given trial, with six levels: 4, 7, 10, 15, 20, and 30.

The core matching task was executed by **Google's Gemini 1.5 Flash** LLM (Google, 2024). For each trial, the LLM was provided with a group of `k` neutralized personality descriptions and a corresponding group of `k` names, with the presentation order of both lists randomly shuffled to control for any potential effects of item position on the LLM's evaluation. It was then tasked with independently sourcing the biographical information for each individual before performing the matching and producing a similarity score matrix based on a structured prompt.

The experiment consisted of 100 trials per replication, with 30 full replications conducted for each of the 12 conditions (`2 mapping_strategy levels x 6 k levels`), totaling 360 complete experimental runs. With 30 replications per condition, this design provided sufficient statistical power (>.80) to detect small-to-medium effect sizes.

The selection of Google's `Gemini 1.5 Flash` (model `gemini-1.5-flash-001`, accessed via the OpenRouter API between June 10 and July 21, 2025) as the evaluation LLM was the result of a systematic piloting process. A range of models were tested for their performance on the matching task, response time, cost-effectiveness, and reliability in adhering to the structured output format. While several high-performing models were considered, `Gemini 1.5 Flash` provided the optimal balance of these criteria for the large-scale querying required by this study. To monitor the integrity of the matching process, the LLM was also periodically queried to provide a detailed explanation of its methodology. These introspective checks were reviewed to ensure the model was operating within the intended parameters of the task and not applying external, domain-specific knowledge.

#### Dependent Variables and Statistical Analysis

The primary dependent variables were "lift" metrics, which normalize for chance and are thus comparable across different `k` values. Key metrics included:

*   **Mean Reciprocal Rank (MRR) Lift**: The observed MRR divided by the MRR expected by chance.
*   **Top-1 and Top-3 Accuracy Lift**: Observed accuracy divided by chance accuracy.
*   **Effect Size (r) and Stouffer's Z-score**: Combined metrics of statistical effect size.

A Two-Way Analysis of Variance (ANOVA) was conducted for each metric to assess the main effects of `mapping_strategy` and `k`, as well as their interaction. Effect sizes were calculated using eta-squared (η²) to determine the proportion of variance attributable to each factor (Cohen, 1988). Post-hoc comparisons for significant main effects were performed using Tukey's HSD test. The significance level was set at α = .05. Our single core hypothesis was tested across several related but distinct performance metrics. Each ANOVA was therefore treated as a separate, pre-specified test of this hypothesis, and no correction for multiple comparisons was applied. To complement the frequentist analysis, a Bayesian analysis was also conducted. This allowed us to quantify the evidence for the astrological hypothesis (that a real signal exists) against the null hypothesis (that there is no signal and performance is due to chance). This approach responds to the ongoing debate about the proper use of statistical inference in psychology (van Dongen & van Grootel, 2022).

#### Open Data and Code Availability

In accordance with the principles of open science and computational reproducibility (The Turing Way Community, 2022), all data, analysis scripts, and supplementary materials necessary to reproduce the findings reported in this article are permanently and publicly available. The complete project repository can be accessed on GitHub at https://github.com/[user]/[repository-name-placeholder]. This includes the neutralized component library, the final subject database, the raw experimental results, and the scripts used for statistical analysis and figure generation.

### Results

The analysis revealed statistically significant main effects for both `mapping_strategy` and `k` on the most critical performance metrics. The interaction effect (`mapping_strategy * k`) was found to be not statistically significant for the primary lift metrics (e.g., for MRR Lift, *F*(5, 348) = 1.13, *p* = .345). However, a significant interaction was observed for the raw performance metric `Mean Rank of Correct ID` (*F*(5, 348) = 2.72, *p* = .020), indicating that the magnitude of the difference in raw rank between the correct and random conditions varies with group size. Given our focus on chance-corrected lift metrics, the main effects are of primary interest.

#### Main Effect of `mapping_strategy`

A statistically significant main effect of `mapping_strategy` was found for all key performance metrics, consistently showing that the LLM performed better in the `correct` condition than in the `random` condition. As detailed in Table 2, the effect sizes (η²) were small, confirming the subtle nature of the signal. The confidence intervals for η², while wide, do not include zero for the primary MRR Lift metric, reinforcing the statistical significance of the finding.

*Table 2: ANOVA Results for the Main Effect of `mapping_strategy`*

| Dependent Variable | *F*(1, 348) | *p*-value | η² | 95% CI for η² |
| :--- | :---: | :---: | :---: | :---: |
| MRR Lift | 6.27 | .013 | .015 | [.001, .040] |
| Top-1 Accuracy Lift | 5.13 | .024 | .009 | [.000, .031] |
| Top-3 Accuracy Lift | 4.47 | .035 | .007 | [.000, .028] |
| Effect Size (r) | 4.95 | .027 | .012 | [.000, .035] |

To provide a different perspective on this small effect, a Bayesian analysis was also conducted on the primary metric, MRR Lift. The resulting Bayes Factor (BF₁₀ ≈ 1.61) indicates that the experimental results are approximately 1.6 times more likely under the astrological hypothesis (that a signal exists) than under the null hypothesis. In line with conventional standards (Jeffreys, 1961), this provides "anecdotal" evidence for the astrological hypothesis, a nuance that complements the significant but borderline p-value from the frequentist analysis.

*Figure 1* illustrates the difference in performance lift between the two mapping strategies, showing a small but consistent advantage for the `correct` condition.

{{grouped_figure:docs/images/boxplots/boxplot_mapping_strategy_mean_mrr_lift.png | caption=Figure 1: Comparison of MRR Lift (vs. Chance) between Correct and Random mapping strategies.}}

#### Main Effect of Group Size (`k`)

As hypothesized, `k` had a strong, statistically significant main effect on all lift metrics (*p* < .001 for all). Post-hoc tests confirmed that performance lift systematically decreased as `k` increased. This result is an expected property of matching tests; as the number of choices increases, the signal-to-noise ratio decreases, making the correct match harder to detect.

{{grouped_figure:docs/images/boxplots/boxplot_k_mean_mrr_lift.png | caption=Figure 2: Comparison of MRR Lift (vs. Chance) across different group sizes (k).}}

#### Analysis of Presentation Order Bias

The study also analyzed for potential presentation order bias. A key metric, Top-1 Prediction Bias (Std Dev), measures whether the LLM consistently gives its top rating to items based on their ordinal position in the presented list (e.g., always preferring the first item). The ANOVA for this metric showed a significant effect for group size `k` (*p* < .001) but not for `mapping_strategy` (*p* = .357). This indicates that while group size influenced the consistency of the LLM's choices, this behavior did not differ between the correct and random conditions. Importantly, further analyses for a simple linear bias (e.g., a consistent preference for items appearing earlier in a list) showed no statistically significant effects for either factor.

### Discussion

As a replication and methodological extension of Godbout (2020), the results of this study provide quantitative evidence supporting the hypothesis that neutralized descriptions generated by an astrological expert system contain a non-random, discernible signal. The LLM, acting as an autonomous agent that could independently source biographical information and perform a complex matching analysis, was able to distinguish between correctly mapped and randomly mapped profiles at a statistically significant level. This finding is notable as it overcomes historical methodological hurdles by removing the human judge from the loop; however, this automated approach introduces its own set of technical complexities. The analysis for presentation order effects showed no evidence of a simple linear bias, reinforcing the integrity of the core performance metrics.

The subtlety of the detected signal, indicated by the small effect sizes, is an important aspect of this finding. It suggests that the predictive information, while present, is weak and likely insufficient for high-accuracy predictions in practical, high-noise environments. This may be due to several factors: the inherent nature of the phenomenon, the loss of information during the necessary neutralization process, or the constraints placed on the astrological factors used for generation. The significant effect of `k` reinforces this interpretation; the faint signal is more easily obscured as the number of potential distractors (noise) increases.

Furthermore, the lack of a significant interaction effect between `mapping_strategy` and `k` for the primary lift metrics is an important finding in itself. It suggests that the magnitude of the astrological signal's effect, while subtle, remains relatively consistent regardless of the task's complexity. The signal does not appear to become disproportionately stronger or weaker as more distractors are introduced.

The primary contribution of this work is the introduction and validation of its methodological framework. Key features of this framework include its fully autonomous execution, computational reproducibility, scalability, and robust blinding procedures. This LLM-driven, open-source pipeline represents a new paradigm for bringing empirical rigor to complex narrative systems (e.g., Jungian archetypes, qualitative sociological theories), which have long been challenging to assess quantitatively. The use of an LLM is supported by research suggesting they can engage with complex psychological constructs (cf. Kosinski, 2023, on Theory of Mind). By demonstrating its utility on a particularly challenging "hard problem," we offer a template for investigating other complex narrative systems, such as Jungian archetypes or theories from qualitative sociology.

This study was designed from the ground up to embody the principles of open science, transparency, and computational reproducibility. In an era defined by the "reproducibility crisis" (Open Science Collaboration, 2015), our autonomous and open framework provides a practical template for verifiable research. The framework includes a robust diagnostic and repair engine, ensuring data pipeline integrity and simplifying replication. The empirical finding is not an end in itself but serves to validate the methodology. It demonstrates that questions about the validity of complex narrative systems can now be approached with greater rigor and transparency.

It is important to proactively address alternative explanations for these findings. One is the "Barnum effect," where generalized statements appear personally relevant. The forced-choice design of this study inherently controls for this, as the LLM must differentiate between multiple distinct profiles rather than simply validate one. A more complex confound is the possibility that the LLM is matching based on demographic or stylistic regularities correlated with birth data rather than the intended signal. For example, the well-documented "birth season" effect correlates birth month with certain life outcomes. However, the signal tested here is derived from a complex, multi-factorial system based on the precise date, time, and location of birth—not just the month—making it far more specific than a simple seasonal variable. While it is unlikely that a broad seasonal effect could account for this nuanced signal, future research could control for it by comparing results against a simplified model using only the sun sign (which correlates with birth month). Similarly, the LLM could be matching on subtle linguistic patterns in the source biographies that correlate with era-specific data, but the neutralization process was designed to mitigate such stylistic artifacts by standardizing the language.

Ultimately, this study was designed to answer a single, empirical question: is there a detectable signal? The results indicate that the answer is yes. The profound question of *what it means* for a non-conscious, algorithmic system to detect a faint but significant pattern within a symbolic framework traditionally associated with human meaning-making is a philosophical one. This deeper inquiry, which explores the implications for our understanding of consciousness and pattern recognition, is the subject of a companion analysis (McRitchie & Marko, manuscript in preparation).

#### Limitations and Future Directions

This study has several limitations, primarily related to the nature of the LLM-based method, the sample population, and the specific stimuli used.

**The "Black Box" Problem and Model Specificity:** The most significant limitation is the reliance on closed-source LLMs. It is theoretically possible that the evaluation LLM, despite the neutralization of the text, could have inferred the astrological origin of the descriptions and used latent, pre-existing knowledge to "cheat" the test. While introspective checks suggested the model was not actively applying an astrological framework, this possibility of data contamination cannot be definitively excluded. Similarly, because the LLM sources its own biographical data, we cannot be certain it is not finding an obscure source that contains a non-obvious correlation with the birth data. A future study could create a more controlled design by providing the biographical text directly in the prompt, sourced exclusively from the validated Wikipedia pages. This "black box" problem highlights a central challenge in using proprietary AI for scientific research. Future studies should aim to replicate these findings using open-source models or, ideally, custom-trained LLMs with no prior exposure to astrological concepts to ensure the detected signal is not an artifact. Furthermore, the results are specific to the models used (`o3 mini` and `Gemini 1.5 Flash`); replication with different architectures is necessary to establish robustness.

**Sample and Stimulus Constraints:** The use of famous individuals, while necessary to ensure rich biographical data, limits the generalizability of the findings to the broader population. The widely known lives of these subjects could also introduce unknown confounds. Similarly, the study intentionally used a simplified astrological model (primary placements only) to test for a foundational signal. The weak effect size may be a function of this simplification. Future research should extend this methodology to non-public figures and incorporate more complex astrological factors (e.g., aspects, midpoints, house systems) to assess whether the signal strength varies.

**Neutralization Process Validation:** While the automated keyword search confirmed the successful removal of explicit terminology, a formal matching test using human astrologers as judges was not conducted. Such a study could provide a valuable benchmark, comparing the performance of the automated system against human expertise. Future research could also include a study where human raters, blind to the source, attempt to classify the neutralized snippets back into their original astrological categories. If they perform at chance, it would provide stronger evidence that the neutralization successfully removed all discernible traces of the source system.

### Conclusion

This study successfully deployed an automated and objective framework to test for a weak signal in a complex narrative system, meeting its primary methodological goal. The findings indicate the presence of a faint but statistically significant signal within neutralized astrological descriptions, detectable by a sophisticated, impartial AI arbiter. This work does not validate astrology as a whole, but it challenges the null hypothesis that its outputs are purely arbitrary. It provides a robust, reproducible framework for future empirical investigations and establishes a firm factual basis for the subsequent philosophical inquiry into consciousness and symbolic systems explored in its companion article.

### Author Contact

Correspondence concerning this article should be addressed to Peter Marko at peter.j.marko@gmail.com.

### Author Contributions

Peter Marko was responsible for the conceptualization, methodology, software, formal analysis, investigation, and writing the original draft of the article. Kenneth McRitchie was responsible for supervision, assisted with the conceptualization, and reviewed and edited the article.

**ORCID iDs**

*   Peter Marko: https://orcid.org/0000-0001-9108-8789
*   Kenneth McRitchie: https://orcid.org/0000-0001-8971-8091

### Conflicts of Interest

The authors declare that they have no known competing financial interests or personal relationships that could have appeared to influence the work reported in this paper.

### Acknowledgements

The authors wish to thank Vincent Godbout for generously sharing his pioneering thoughts, drafts, and procedures on automated matching tests, which provided a valuable foundation for this work. The authors are independent researchers and received no specific funding for this study.

### Supplementary Materials

Supplementary materials for this article, including a detailed description of the astrological weighting system ("Settings for Balances Report") and a pilot study on LLM selection, are available in the project's public repository at [Insert GitHub Repository URL Here].

---
### References

Astro-Databank. (n.d.). [Online database]. Astrodienst AG. Retrieved from https://www.astro.com/astro-databank/Main_Page

Astrodatabank Research Tool. (n.d.). [Online tool]. Astrodienst AG. Retrieved from https://www.astro.com/adb-search/

Brown, T. B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J. D., Dhariwal, P., Agarwal, S., Neelakantan, A., Ramesh, P., Sastry, G., Askell, A., Mishkin, P., Clark, J., Krueger, G., & Amodei, D. (2020). Language models are few-shot learners. *Advances in Neural Information Processing Systems*, *33*, 1877-1901.

Carlson, S. (1985). A double-blind test of astrology. *Nature*, *318*(6045), 419-425.

Cohen, J. (1988). *Statistical power analysis for the behavioral sciences* (2nd ed.). Lawrence Erlbaum Associates.

Currey, R. (2022). Meta-analysis of recent advances in natal astrology using a universal effect-size. *Correlation*, *34*(2), 43-55.

Ertel, S. (2009). Appraisal of Shawn Carlson’s renowned astrology tests. *Journal of Scientific Exploration*, *23*(2), 125-137.

Eysenck, H. J., & Nias, D. K. (1982). *Astrology: Science or superstition?* St. Martin's Press.

Godbout, V. (2020). An automated matching test: Comparing astrological charts with biographies. *Correlation*, *32*(2), 13-41.

Google. (2024). *Gemini 1.5: Unlocking multimodal understanding across millions of tokens of context*. Google AI. https://arxiv.org/abs/2403.05530

Jeffreys, H. (1961). *Theory of Probability* (3rd ed.). Oxford University Press.

Kosinski, M. (2023). Theory of mind may have spontaneously emerged in large language models. *Proceedings of the National Academy of Sciences*, *120*(9), e2218926120. https://doi.org/10.1073/pnas.2218926120

Marko, P. J. (2018). Boomers and the lunar defect. *The Astrological Journal, 60*(1), 35-39.

McRitchie, K. (2022). How to think about the astrology research program: An essay considering emergent effects. *Journal of Scientific Exploration*, *36*(4), 706-716. https://doi.org/10.31275/20222641

Open Science Collaboration. (2015). Estimating the reproducibility of psychological science. *Science*, *349*(6251), aac4716.

OpenRouter.ai. (n.d.). [Online API service]. Retrieved from https://openrouter.ai/

Solar Fire. (n.d.). [Software]. Astrolabe Inc. Retrieved from https://alabe.com/solarfireV9.html

The Turing Way Community. (2022). *The Turing Way: A handbook for reproducible, ethical and collaborative research*. Zenodo. https://doi.org/10.5281/zenodo.3233853

van Dongen, N., & van Grootel, L. (2025). Overview on the Null Hypothesis Significance Test: A Systematic Review on Essay Literature on its Problems and Solutions in Present Psychological Science. *Meta-Psychology*, *9*, MP.2021.2927. https://doi.org/10.15626/MP.2021.2927

Wei, J., Tay, Y., Bommasani, R., Raffel, C., Zoph, B., Borgeaud, S., Chowdhery, A., Narang, S., & Le, Q. V. (2022). Emergent abilities of large language models. *Transactions on Machine Learning Research*. https://arxiv.org/abs/2206.07682
