---
title: "Detecting a Non-Random Signal in Astrological Descriptions Using a Large Language Model as an Impartial Arbiter"
author: "[Author Name(s)]"
date: "[Date]"
abstract: |
  **Background:** Empirical validation of complex, holistic systems like astrology has historically been challenging due to methodological limitations, including experimenter bias and the difficulty of quantitatively analyzing narrative data.
  **Objective:** This study introduces a novel, fully automated methodology to test the hypothesis that astrological descriptions contain a non-random, discernible signal that correlates with an individual's biographical data. We utilize a Large Language Model (LLM) as an unbiased pattern-recognition tool to circumvent traditional testing challenges.
  **Methods:** Personality descriptions for a curated database of famous individuals with verified birth data were deterministically generated using the Solar Fire v9.0.3 astrology program. These descriptions were programmatically neutralized by an LLM (Anthropic Claude 3.5 Sonnet) to remove all explicit astrological terminology, blinding the evaluation model to the data's origin. A second, independent LLM (Google Gemini 1.5 Flash) was then tasked with matching these neutralized descriptions to the correct biographical profiles, where the group size (`k`) varied from 4 to 30. This task was performed for both "correct" (astrologically generated) and "random" (shuffled) mappings across 30 full replications per condition. Performance was measured using lift metrics, which normalize for chance.
  **Results:** A Two-Way ANOVA revealed a statistically significant main effect for the mapping strategy. The LLM consistently performed better on "correct" mappings compared to "random" mappings across multiple lift metrics (e.g., MRR Lift: *F*(1, 353) = 6.26, *p* = .013; Top-1 Accuracy Lift: *F*(1, 353) = 5.17, *p* = .024). The effect size was small but consistent, indicating a subtle signal. As expected, group size (`k`) also had a significant effect, with performance lift decreasing as the number of choices increased.
  **Conclusion:** The study provides quantitative, reproducible evidence that the astrological descriptions, even when neutralized, contain a faint but statistically significant signal that an impartial AI tool can detect. This methodology represents a promising new frontier for the empirical investigation of complex narrative systems.
---

### 1. Introduction

For centuries, astrology has postulated a meaningful correlation between celestial configurations at the time of birth and human personality. However, empirical validation of this claim has proven notoriously difficult. Previous studies have often been criticized for methodological flaws, including small sample sizes, susceptibility to experimenter bias, and the challenge of quantitatively analyzing the nuanced, narrative-based output of astrological systems (Eysenck & Nias, 1982; Carlson, 1985). More recent efforts have begun to leverage computational techniques to address these issues (Godbout, 2020; Godbout & Coron, 2023), yet the core difficulty remains in designing a test that is both ecologically valid—respecting the complexity of the system—and rigorously objective.

The advent of Large Language Models (LLMs) presents a transformative opportunity to address these historical challenges. LLMs are powerful, general-purpose pattern-recognition engines trained on vast swathes of human text and data. They can process and compare complex narratives with a degree of sophistication that was previously unattainable in automated systems. Crucially, they can be deployed as impartial arbiters, executing a well-defined task without prior knowledge of the experimental hypothesis or the theoretical basis of the stimuli.

As a conceptual replication and methodological advancement of prior computational research (Godbout, 2020), this study leverages this novel capability to test a foundational astrological hypothesis: **Do personality descriptions derived from a deterministic astrological algorithm contain a non-random, discernible signal that correlates with the biographical data of the individuals they purport to describe?**

To test this, we employ a two-step LLM pipeline. First, we use an LLM to programmatically "neutralize" professionally generated astrological descriptions, removing all explicit terminology to blind the evaluation system. Second, we use an independent LLM to perform a complex "who's who" matching task. By comparing the LLM's success rate on correctly mapped profiles versus randomly mapped profiles, we can isolate and quantify the presence of any underlying systematic signal. Our primary hypothesis is that the LLM's performance in the "correct" mapping condition will be significantly higher than in the "random" mapping condition, as measured by performance lift over chance.

### 2. Methods

#### 2.1. Sample Population

The study utilized a curated database of test subjects drawn from the Astro-Databank (ADB) public database. An initial query using the Astrodatabank Research Tool yielded 10,378 candidates based on the following primary filters:

*   **Biographical Availability**: Subjects were selected from the "Famous: Top 5% of Profession" category to increase the likelihood of comprehensive biographical information being available to the LLM.
*   **Data Reliability**: Only subjects with a Rodden Rating of 'AA' (from birth certificate) or 'A' (from memory or a reliable source) were included. Subjects with birth times given only in hours were excluded to avoid rounded data.
*   **Ethical Considerations**: The sample was filtered for "Personal: Death" to avoid the need for consent to use personal information.

This list was then subjected to a final programmatic filter to verify a sufficient knowledge base for the LLM. This required that each subject (1) had a corresponding Wikipedia page, and (2) that this page contained an identifiable death date, which served to correct for occasional inaccuracies in the ADB's "Personal: Death" filter. This final step reduced the sample to 6,193 pre-selected candidates.

To ensure the final sample consisted of well-known and clearly distinguishable figures, the 6,193 candidates were subjected to a final ranking procedure. Four distinct LLMs (o3 mini high, Claude 3.7 Sonnet, ChatGPT 4o, and Gemini 2.0 Flash) evaluated each candidate for both public eminence and OCEAN (Openness, Conscientiousness, Extraversion, Agreeableness, Neuroticism) traits. The candidates were then ranked using the average eminence score as the primary criterion. This analysis revealed that meaningful distinctions in eminence scores diminished beyond the top 5,000 individuals. To optimize the sample's suitability for the matching task, the final study database was therefore composed of these top 5,000 persons.

#### 2.2. Stimulus Generation and Neutralization

The textual stimuli were generated through a multi-step process designed to ensure that final descriptions were constructed from a consistent, pre-neutralized set of interpretive components.

1.  **Component Library Neutralization:** First, the entire library of interpretive delineations within **Solar Fire v9.0.3** was systematically neutralized. This "cookbook" of text components, which contains descriptions for every possible astrological combination (e.g., planet in a sign, elemental dominances), was processed by **OpenAI's o3 mini**. Each individual snippet was rewritten using the prompt: *"Revise the attached text with the exception of lines marked with an asterisk, which need to remain intact: remove references to astrology and astronomy: shift from second-person perspective to an impersonal, objective, neutral style without referring to specific people; and correct for grammar and spelling. Preserve original text as much as possible while making these revisions."* The lines marked with an asterisk, which were preserved verbatim, served as the unique key lookup text for each component in the neutralized library. This one-time process created a master database of neutralized personality description components.

2.  **Placement Extraction:** Second, for each of the 5,000 individuals in the study database, their unique set of astrological placements was exported from Solar Fire. This structured data included the factors necessary to generate the "Balances" (Planetary Dominance) and "Chart Points" reports, covering elements, modes, and the sign placements of the 12 key chart points (Sun through Pluto, Ascendant, and Midheaven).

3.  **Profile Assembly:** Finally, each individual's complete personality profile was programmatically assembled. Their specific set of astrological placements, exported in the previous step, was used as a key to look up and concatenate the corresponding pre-neutralized description components from the master database. This assembly process resulted in a unique, composite personality profile for each individual, expressed in neutral language, which formed the basis of the stimuli used in the matching task.

#### 2.3. Experimental Design and Procedure

The study employed a 2 x 6 factorial design. The independent variables were:

*   **`mapping_strategy`**: A between-groups factor with two levels: `correct` (descriptions were correctly paired with biographical profiles) and `random` (descriptions were randomly shuffled and paired).
*   **`k` (Group Size)**: A within-groups factor representing the number of subjects to be matched in a given trial, with six levels: 4, 7, 10, 15, 20, and 30.

The core matching task was executed by **Google's Gemini 1.5 Flash** LLM. For each trial, the LLM was provided with a randomly shuffled list of `k` neutralized personality descriptions and a list of corresponding but independently shuffled `k` names. It was then tasked with independently sourcing the biographical information for each individual before performing the matching. It was prompted with a highly structured request to produce a similarity score matrix. A portion of the prompt is excerpted here: *"You are expected to source the biographies of and any other relevant information about the {k} named people... Please provide your answer *only* in the format of a table... Each cell... should contain a numerical score from 0.00 to 1.00... Do not include any other text, explanations, or introductions..."*

The experiment consisted of 100 trials per replication, with 30 full replications conducted for each of the 12 conditions (`2 mapping_strategy levels x 6 k levels`), totaling 360 complete experimental runs.

#### 2.4. Dependent Variables and Statistical Analysis

The primary dependent variables were "lift" metrics, which normalize for chance and are thus comparable across different `k` values. Key metrics included:

*   **Mean Reciprocal Rank (MRR) Lift**: The observed MRR divided by the MRR expected by chance.
*   **Top-1 and Top-3 Accuracy Lift**: Observed accuracy divided by chance accuracy.
*   **Effect Size (r) and Stouffer's Z-score**: Combined metrics of statistical effect size.

A Two-Way Analysis of Variance (ANOVA) was conducted for each metric to assess the main effects of `mapping_strategy` and `k`, as well as their interaction. Post-hoc comparisons were performed using Tukey's HSD test. The significance level was set at α = .05.

### 3. Results

The analysis revealed statistically significant main effects for both `mapping_strategy` and `k` on the most critical performance metrics. The interaction effect (`mapping_strategy * k`) was found to be not statistically significant for the primary lift metrics (e.g., for MRR Lift, *F*(5, 348) = 1.13, *p* = .345). However, a significant interaction was observed for the raw performance metric `Mean Rank of Correct ID` (*F*(5, 348) = 2.72, *p* = .020), indicating that the magnitude of the difference in raw rank between mapping strategies varies with group size. Given our focus on chance-corrected lift metrics, the main effects are of primary interest.

#### 3.1. Main Effect of `mapping_strategy`

A statistically significant main effect of `mapping_strategy` was found for multiple lift and effect size metrics, consistently showing that the LLM performed better in the `correct` condition than in the `random` condition.

*   **MRR Lift**: *F*(1, 353) = 6.26, *p* = .013, η² = .015.
*   **Top-1 Accuracy Lift**: *F*(1, 353) = 5.17, *p* = .024, η² = .009.
*   **Top-3 Accuracy Lift**: *F*(1, 353) = 4.44, *p* = .036, η² = .007.
*   **Effect Size (r)**: *F*(1, 353) = 4.95, *p* = .027, η² = .012.

*Figure 1* illustrates the difference in performance lift between the two mapping strategies, showing a small but consistent advantage for the `correct` condition.

{{grouped_figure:docs/images/boxplot_mapping_strategy_mean_mrr_lift.png | caption=Figure 1: Comparison of MRR Lift (vs. Chance) between Correct and Random mapping strategies.}}

#### 3.2. Main Effect of Group Size (`k`)

As hypothesized, `k` had a strong, statistically significant main effect on all lift metrics (*p* < .001 for all). Post-hoc tests confirmed that performance lift systematically decreased as `k` increased. This confirms that the astrological signal, while detectable, is more easily leveraged in less complex choice environments.

{{grouped_figure:docs/images/boxplot_k_mean_mrr_lift.png | caption=Figure 2: Comparison of MRR Lift (vs. Chance) across different group sizes (k).}}

#### 3.3. Analysis of Positional Bias

The study also analyzed potential positional biases in the LLM's responses. The ANOVA for `Top-1 Prediction Bias (Std Dev)`—a measure of how consistently the LLM preferred certain ranked positions—showed a significant effect for group size `k` (*p* < .001) but not for `mapping_strategy` (*p* = .357). This indicates that while task complexity influenced the consistency of the LLM's choices, this behavior did not differ between the correct and random conditions. Importantly, the analyses for `Bias Slope` and `Bias P-value` showed no statistically significant effects for either `mapping_strategy` or `k`, suggesting the absence of a simple linear positional bias in the rankings.

### 4. Discussion

As a successful conceptual replication and methodological extension of Godbout (2020), the results of this study provide quantitative evidence supporting the hypothesis that neutralized descriptions generated by an astrological algorithm contain a non-random, discernible signal. The LLM, acting as an impartial pattern-recognition tool, was able to distinguish between correctly mapped and randomly mapped profiles at a statistically significant level. This finding is notable as it overcomes many of the historical methodological hurdles in empirical astrological research. Furthermore, the analysis of positional bias showed no evidence of a systematic linear bias in the LLM's rankings. While the *consistency* of its top choices was affected by group size (`k`), the model did not appear to favor certain positions in its ranked output, reinforcing the integrity of the core performance metrics.

The subtlety of the detected signal, indicated by the small effect sizes, is an important aspect of this finding. It suggests that the predictive information, while present, is weak and likely insufficient for high-accuracy predictions in practical, high-noise environments. This may be due to several factors: the inherent nature of the phenomenon, the loss of information during the necessary neutralization process, or the constraints placed on the astrological factors used for generation. The significant effect of `k` reinforces this interpretation; the faint signal is more easily obscured as the number of potential distractors (noise) increases.

Furthermore, the lack of a significant interaction effect between `mapping_strategy` and `k` for the primary lift metrics is an important finding in itself. It suggests that the magnitude of the astrological signal's effect, while subtle, remains relatively consistent regardless of the task's complexity. The signal does not appear to become disproportionately stronger or weaker as more distractors are introduced.

#### 4.1. Limitations and Future Directions

This study has several limitations. First, it relies on specific LLMs for neutralization and evaluation; results may differ with other models. Second, the sample was restricted to famous individuals, whose widely known biographies may introduce confounding variables. Future research should replicate this methodology with different astrological techniques (e.g., aspects, midpoints, different house systems, inclusion of more complex factors), different LLMs, and non-public-figure populations to assess the generalizability of these findings. Exploring the impact of the neutralization process itself would also be a valuable avenue of investigation. Finally, the astrology expert system itself is specific to this study, providing a further avenue to explore.

### 5. Conclusion

This study successfully deployed a novel, automated, and objective methodology for testing a core hypothesis of astrology. The findings indicate the presence of a faint but statistically significant signal within neutralized astrological descriptions, detectable by a sophisticated, impartial AI arbiter. This work does not validate astrology as a whole, but it challenges the commonly accepted null hypothesis that its outputs are purely arbitrary and provides a robust, reproducible framework for future empirical investigations into complex narrative and symbolic systems.

### Appendix: Settings for "Balances Report"

The calculation of Solar Fire's "balances report" (planetary dominances) utilized the default weighting system, with one key modification. Based on exploratory trials, the weights for the generational planets (Uranus, Neptune, and Pluto) were set to zero to isolate more individualized factors. The specific "weight-points" assigned were as follows:

*   **3 points:** Sun, Moon, Ascendant (Asc), Midheaven (MC)
*   **2 points:** Mercury, Venus, Mars
*   **1 point:** Jupiter, Saturn
*   **0 points:** Uranus, Neptune, Pluto

Dominance within each astrological category (e.g., elements, modes) is automatically determined by the program through a multi-step calculation:

1.  A "total score" (TS) is calculated for each division (e.g., the element 'fire', the mode 'cardinal') by summing the "weight-points" of all chart points located within it.
2.  An "average score" (AS) is then determined for the category by averaging the TS values across all its constituent divisions.
3.  Two thresholds are established using this AS and predefined ratios: a "weak threshold" (WT) calculated with a "weak ratio" (WR), and a "strong threshold" (ST) calculated with a "strong ratio" (SR):
    *   `WT = AS * WR`
    *   `ST = AS * SR`
4.  Finally, a division is classified as 'weak' if its TS was below the WT, or 'strong' if its TS was greater than or equal to the ST.

The interpretive output of the report is a the resulting list of 'strong' and 'weak' placements for each division.

---
### References

*   Carlson, S. (1985). A double-blind test of astrology. *Nature*, *318*(6045), 419-425.
*   Eysenck, H. J., & Nias, D. K. (1982). *Astrology: Science or superstition?* St. Martin's Press.
*   Godbout, V. (2020). An automated matching test: Comparing astrological charts with biographies. *Correlation*, *32*(2), 13-41.
*   Godbout, V., & Coron, V. (2023). A model of planetary dominance. *Correlation*, *35*(2), 11-29.
