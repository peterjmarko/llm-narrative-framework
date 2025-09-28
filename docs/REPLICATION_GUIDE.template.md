---
title: "Replication Guide"
subtitle: "Supplementary Material for 'A Framework for the Computationally Reproducible Testing of Complex Narrative Systems'"
author: "Peter J. Marko"
date: "[Date]"
---

This document is the **Replication Guide** that provides supplementary material to the main article, "A Framework for the Computationally Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology." Its purpose is to serve as a detailed, step-by-step guide for researchers who wish to replicate or extend the original study's findings.

This guide defines the three primary replication paths (Direct, Methodological, and Conceptual) and provides a complete walkthrough of the end-to-end workflow, from initial setup and data preparation to running the main experiments and producing the final statistical analysis.

{{toc}}

### Models Used in the Original Study

For a direct or methodological replication, it is crucial to use the exact models and versions from the original study. All models were accessed via the **OpenRouter API**.

| Purpose | Model Name | API Identifier |
| :--- | :--- | :--- |
| Eminence Scoring (LLM A) | OpenAI's GPT-5 | `openai/gpt-5-chat` |
| OCEAN Scoring (LLM B) | Anthropic's Claude 4 Sonnet | `anthropic/claude-4-sonnet` |
| Neutralization (LLM C) | Google's Gemini 2.5 Pro | `google/gemini-2.5-pro` |
| Evaluation (LLM D) | Google's Gemini 1.5 Flash | `google/gemini-1.5-flash-001` |

*Access Dates for Evaluation LLM: September 2025*

## The Data Preparation Pipeline

The data preparation pipeline is a fully automated, multi-stage workflow that transforms the raw data from the Astro-Databank into the final `personalities_db.txt` file used in the experiments. The overall flow of data artifacts is shown below.

{{grouped_figure:docs/diagrams/flow_prep_1_qualification.mmd | scale=2.5 | width=85% | caption=Figure S1: Data Prep Flow 1 - Data Sourcing and Candidate Qualification.}}

{{grouped_figure:docs/diagrams/flow_prep_2_selection.mmd | scale=2.5 | width=100% | caption=Figure S2: Data Prep Flow 2 - LLM-based Candidate Selection.}}

{{grouped_figure:docs/diagrams/flow_prep_3_generation.mmd | scale=2.5 | width=100% | caption=Figure S3: Data Prep Flow 3 - Profile Generation.}}

This guide supports three distinct research paths.

**Path 1: Direct Replication (Computational Reproducibility)**
To ensure computational reproducibility of the original findings, researchers should use the static data files and randomization seeds included in this repository. This path validates that the framework produces the same statistical results.

**Path 2: Methodological Replication (Testing Robustness)**
To test the robustness of the findings, researchers can use the framework's automated tools to generate a fresh dataset from the live Astro-Databank (ADB). The instructions below detail this workflow, which is organized into four main stages.

**Path 3: Conceptual Replication (Extending the Research)**
To extend the research, researchers can modify the framework itself, for example, by using a different LLM for the matching task or altering the analysis scripts.

> **Note on Learning the Pipeline:** For researchers who wish to understand the automated pipeline in detail, an interactive **Guided Tour** is available. This step-by-step walkthrough is an excellent way to learn how the data processing scripts work together. Full instructions for running the tour can be found in the project's **[🧪 Testing Guide (TESTING.md)](TESTING.md)**.

### Stage 1: Data Sourcing

The entire data preparation workflow is managed by a single, intelligent orchestrator: `prepare_data.ps1`. This script is fully resumable and is the recommended method for generating a new dataset.

**Prerequisites:** An account at `astro.com` and credentials in the `.env` file.
```powershell
# Run the entire data preparation pipeline
.\prepare_data.ps1
```
This single command will execute all the necessary steps, from fetching the raw data to generating the final `personalities_db.txt` file. The individual `pdm run` scripts (e.g., `pdm run find-links`) are also available for advanced development and debugging but are not part of the standard replication workflow.

##### d. A Note on Determining the Optimal Cutoff Parameters
To ensure the parameters for the final candidate selection algorithm were chosen objectively and were optimally tuned to the specific shape of the dataset's variance curve, a **systematic sensitivity analysis** was performed using the dedicated `scripts/analyze_cutoff_parameters.py` utility. The search space for the parameters was iteratively expanded to ensure a true global optimum was found.

The script performed a grid search over a wide range of values for `cutoff_search_start_point` and `smoothing_window_size`. To avoid overfitting to a single "best" result, a sophisticated **stability-based recommendation algorithm** was used. This algorithm first identifies a cluster of high-performing parameter sets (those with a low error between the predicted and ideal cutoffs) and then calculates a "stability score" for each based on the average error of its neighbors in the parameter grid. The final recommendation is the parameter set with the best stability score, representing the center of the most stable, high-performing region.

The final, expanded analysis revealed several key insights:
*   **The Variance Curve Shape:** The cumulative variance curve has a distinct shape: a long, steep decline followed by a wide, shallow plateau containing long-wavelength, low-amplitude noise.
*   **Justification for the Final Parameters:** A high `cutoff_search_start_point` (3500) was essential to force the analysis to begin *on the plateau*, isolating the region of interest. A large `smoothing_window_size` (800) was necessary to average out the long, shallow waves on the plateau, allowing the slope-based algorithm to detect the true global trend.

Based on this comprehensive, data-driven analysis, the following optimal parameters were chosen and set in `config.ini`:
*   `cutoff_search_start_point = 3500`
*   `smoothing_window_size = 800`

The plot of this analysis (see Figure S1) provides a clear visual justification for these choices. It shows how the algorithm, using these parameters, correctly identifies the start of the curve's final plateau, resulting in a final cutoff of 4,954 subjects.

{{grouped_figure:data/reports/variance_curve_analysis.png | caption=Figure S1: Variance Curve Analysis for Optimal Cohort Selection. The plot shows the raw cumulative variance, the smoothed curve (800-pt moving average), the search start point (3500), and the final data-driven cutoff (4954).}}

### Stage 4: Profile Generation

This is the final stage, which assembles the personality profiles for the selected candidates.

#### a. Formatting for Import (`prepare_sf_import.py`)
This script formats the final candidates list for import into Solar Fire.
```bash
# Prepare the final list for the manual import step
pdm run prep-sf-import
```
This produces `data/intermediate/sf_data_import.txt`, the input for the next stage.

## Importing to and Exporting from Solar Fire

Once the data is prepared, we can start making the Solar Fire astrology software ready for the import. This commercial program is available at https://alabe.com/solarfireV9.html. Many good alternatives exist, but the data preparation, import, and export procedures will be different in each case. The main advantages of Solar Fire are as follows:

*   It is the industry standard astrology software for astrologers around the world.
*   It has a long history of development and is considered accurate and reliable.
*   Data import / chart export functionality is straightforward and seamless.
*   Its delineations library is fully exportable.
*   It is relatively inexpensive ($360 USD currently).

### One-Time Software Setup

The following configuration steps only need to be performed once. After the initial setup, you can proceed directly to the **Import/Export Workflow**.

#### 1. Configure Chart Points

You must define which astrological points are included in the calculations.

*   **Menu:** `Chart Options > Displayed Points...`
*   **Action:**
    1.  Create a new `.pts` file (e.g., `10_planets_2_angles.pts`).
    2.  Edit this file to include exactly these 12 points: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Ascendant, and Midheaven.
    3.  Save the file and ensure it is selected as the active set.

{{grouped_figure:docs/images/replication_guide/sf_setup_1_displayed_points.png | width=60% | caption=Figure SX: The Solar Fire "Displayed Points" dialog configured with the 12 required chart points.}}

#### 2. Configure Preferences

Ensure the core calculation settings match the study's methodology.

*   **Menu:** `Preferences > Edit Settings...`
*   **Action:** Verify the following default settings are active:
    *   **'Places' tab -> Atlas:** `ACS (Built-in)`
    *   **'Calculations' tab -> MC in Polar Regions:** `Always above horizon`
    *   **'Zodiac' tab -> Default Zodiac:** `Tropical`
    *   **'AutoRun' tab -> Astrologer's Assistant:** Ensure this is cleared and no tasks run on startup.

#### 3. Define Data Formats

You must define the data structure for both importing and exporting. Solar Fire maintains **separate** format lists for each, so this process must be done twice.

**a. Define Import Format**
*   **Menu:** `Utilities > Chart Import/Export...`
*   **Action:**
    1.  Go to the **'Options' tab** and click **'Edit ASCII Formats...'**.
    2.  Create a **new format definition**.
    3.  Set **'Record Format'** to `Comma Quote Delimited`.
    4.  Configure **'Fields in each record'** to contain exactly these 9 fields in this specific order: Name/Description, Date (String), Time (String), Zone Abbreviation, Zone Time (String), Place Name, Country/State Name, Latitude (String), Longitude (String).
    5.  Save the format as `CQD Import`.

{{grouped_figure:docs/images/replication_guide/sf_setup_2_import_format.png | width=80% | caption=Figure SX: The Solar Fire "Edit ASCII Formats" dialog configured for the CQD Import format.}}

**b. Define Export Format**
*   **Menu:** `Chart > Export Charts as Text...`
*   **Action:**
    1.  Click the **'Edit ASCII...'** button to open the format definitions dialog.
    2.  **This list is separate from the import list.** You must create another **new format definition**.
    3.  Repeat the exact same configuration as the import format, set it to `Comma Quote Delimited`, and add the same 9 fields in the same order.
    4.  Save the format as `CQD Export`. This ensures both workflows use an identical data structure.

{{grouped_figure:docs/images/replication_guide/sf_setup_3_export_format.png | width=80% | caption=Figure SX: The Solar Fire "Export Chart Data" format dialog configured for the CQD Export format.}}

### Import/Export Workflow

After completing the one-time setup, follow this workflow to process the data.

#### Pre-flight Check: Clearing Existing Chart Data (For Re-runs)
If you are re-running the import process, you must first clear the existing charts from your Solar Fire charts file to avoid duplicates.

*   **Menu:** `Chart > Open...`
*   **Action:**
    1.  In the 'Chart Database' dialog, select your charts file (e.g., `adb_candidates.sfcht`).
    2.  Click the **'All'** button to highlight every chart in the file.
    3.  Click the **'Delete...'** button, then select **'Selected Charts...'**.
    4.  A dialog will ask: "Do you wish to confirm the deletion of each chart individually?". Click **'No'** to delete all charts at once.
    5.  Click **'Cancel'** to close the 'Chart Database' dialog. The file is now empty and ready for a fresh import.

{{grouped_figure:docs/images/replication_guide/sf_workflow_1_clear_charts.png | width=95% | caption=Figure SX: The Solar Fire "Chart Database" dialog with all charts selected for deletion.}}

#### Step 1: Import Birth Data

*   **Menu:** `Utilities > Chart Import/Export...`
*   **Action:**
    1.  If a "Confirm" dialog appears immediately, click **'OK'**.
    2.  On the **'Import From' tab**, select `ASCII files` and choose `data/intermediate/sf_data_import.txt`.
    3.  On the **'Save To' tab**, ensure your `adb_candidates.sfcht` file is selected.
    4.  On the **'Options' tab**, select your `CQD Import` format.
    5.  Click the **'Convert'** button.
    6.  Once the import completes, click the **'Quit'** button to close the dialog.

{{grouped_figure:docs/images/replication_guide/sf_workflow_2_import_dialog.png | width=95% | caption=Figure SX: The Solar Fire "Chart Import/Export" dialog configured to import the prepared data.}}

#### Step 2: Calculate All Charts

*   **Menu:** `Chart > Open...`
*   **Action:**
    1.  Select the charts file you just created (e.g., `adb_candidates.sfcht`).
    2.  Click the **'All'** button to select all charts in the file.
    3.  Click the **'Open...'** button. This will calculate all charts and add them to the "Calculated Charts" list. The processing time will vary depending on the number of subjects (typically a few minutes for each set of 1,000 charts).

> **A Note on Character Encoding:** In the "Calculated Charts" list, you may notice that some names with international characters appear corrupted (e.g., `PelÃ©` instead of `Pelé`). This is an expected display issue within Solar Fire. **Do not attempt to fix these names manually.** The automated scripts are designed to detect and repair these encoding errors in the next stage, ensuring the final database is clean.

#### Step 3: Export Chart Data

*   **Menu:** `Chart > Export Charts as Text...`
*   **Action:**
    1.  In the "Calculated Charts" window, select all calculated charts.
    2.  In the "Export Chart Data" dialog, check the **'Chart Details'** and **'Column Types'** boxes.
    3.  Under 'Select types of points', ensure **'Chart Points'** is selected.
    4.  For the ASCII format, select your custom `CQD Export` format.
    5.  Set 'Field Delimiters' to `Comma Quote (CQD)` and 'Destination' to `Export to File`.
    6.  Browse to the `data/foundational_assets/` directory, set the filename to `sf_chart_export.csv`, and click **Save**. Note: 'Save as type' cannot be set in this dialog.
    7.  **Warning:** Solar Fire will overwrite this file without confirmation. Click **'Export'**.
    8.  Once the export completes successfully, click the **'Quit'** button to close the dialog.

{{grouped_figure:docs/images/replication_guide/sf_workflow_3_export_dialog.png | width=75% | caption=Figure SX: The Solar Fire "Export Chart Data" dialog configured for the final chart data export.}}

The exported file consists of a repeating 14-line block for each subject. The structure of this block is detailed below:

| Line(s) | Content/Fields | Description |
| :--- | :--- | :--- |
| 1 | `Name`, `Date`, `Time`, `ZoneAbbr`, `ZoneOffset`, `Place`, `State`, `Lat`, `Lon` | The subject's core birth data. The `idADB` is critically encoded into the `ZoneAbbr` field. |
| 2 | `"Body Name","Body Abbr","Longitude"` | The literal header line for the planetary data that follows. |
| 3-14 | `Point Name`, `Point Abbr`, `Zodiacal Longitude` | The data for each of the 12 chart points (Sun, Moon, ..., Midheaven). |

The entire file consists of `N * 14` lines, where `N` is the final number of subjects.

### Stage 4: Profile Generation

This is the final stage, which assembles the personality profiles for the selected candidates. It involves both automated scripts and a one-time manual process using the Solar Fire software.

#### a. Manual Solar Fire Processing

The personality descriptions are assembled from a library of pre-written text components. This library must first be exported from Solar Fire.

*   **Menu:** `Interps > Interpretation Files > Natal`
*   **Action:**
    1.  Select `Standard.int` and click **'Edit'**.
    2.  In the 'Interpretations Editor', go to `File > Decompile...` and save the file. This creates `Standard.def` in the `Documents/Solar Fire User Files/Interpretations` directory.
    3.  Copy this file to the `data/foundational_assets/` folder and rename it to `sf_delineations_library.txt`. Note: Filename extensions must be displayed for this rename.

#### b. Automated Profile Assembly

This script uses a powerful hybrid strategy to rewrite the esoteric library into neutral, psychological text. The recommended workflow is a two-step process:

1.  **Initial Fast Pass:** Run the script with the `--fast` flag. This mode bundles tasks into large, high-speed API calls (e.g., all 12 "Sun in Signs" delineations at once). This is highly efficient but may fail on some large tasks.
    ```bash
    # Perform the initial, high-speed neutralization
    pdm run neutralize --fast
    ```

2.  **Robust Resume/Fix:** After the fast run, re-run the script without any flags. In its default mode, the script processes each of the 149 delineations as a separate, atomic task. It will automatically detect any tasks that failed during the fast pass and re-run only those, guaranteeing completion.
    ```bash
    # Automatically fix any failed tasks from the fast run
    pdm run neutralize
    ```
The script's output is the collection of `.csv` files in the `data/foundational_assets/neutralized_delineations/` directory.

#### c. Integrating Chart Data (`create_subject_db.py`)
This script bridges the manual software step. It reads the `sf_chart_export.csv` file, decodes the `idADB` from the `ZoneAbbr` field, and merges the chart data with the final subject list to produce the clean `data/processed/subject_db.csv`.
```bash
# Integrate the manual chart data export
pdm run create-subject-db
```

#### d. Assembling the Final Database (`generate_personalities_db.py`)
This script performs the final assembly. It loads the clean `subject_db.csv`, the configuration files (`point_weights.csv`, `balance_thresholds.csv`), and the entire neutralized delineation library. For each person, it calculates their divisional classifications according to a deterministic algorithm and assembles the final description by looking up the corresponding text components. **The entire personality assembly algorithm has been rigorously validated against a ground-truth dataset generated by the source Solar Fire software to ensure its output is bit-for-bit identical.**
```bash
# Generate the final personalities database
pdm run gen-db
```
The output is `personalities_db.txt`, a tab-delimited file with the fields: `Index`, `Name`, `BirthYear`, and `DescriptionText`.

With the `personalities_db.txt` file generated, the data preparation phase is complete. The following sections describe how to run the experiment lifecycle and analysis.

## Prerequisites

The framework was developed and validated on a specific stack of technologies. Variations are possible but not currently supported. Before proceeding, please ensure you have the following:

*   **Software:**
    *   **Operating System:** Windows (the primary development and testing platform).
    *   **PowerShell:** Version 7.0 or higher.
    *   **Git:** For cloning the repository.
    *   **Solar Fire:** A licensed copy of version 9.

*   **Accounts & Services:**
    *   **OpenRouter:** An account with a valid API key and sufficient funds to cover the cost of LLM queries.
    *   **Astro-Databank:** A registered account at `astro.com` (this is only required if you intend to generate a new dataset via **Path 2: Conceptual Replication**).

## Setup and Installation

This project uses **PDM** for dependency and environment management.

1.  **Install PDM (One-Time Setup)**:
    If you don't have PDM, install it once with pip.
    ```bash
    pip install --user pdm
    ```

2.  **Install Project Environment & Dependencies**:
    From the project's root directory, run the main PDM installation command.
    ```bash
    pdm install -G dev
    ```

3.  **Configure API Key**:
    *   Create a file named `.env` in the project root.
    *   Add your API key from your chosen provider (e.g., OpenRouter):
        `OPENROUTER_API_KEY=your-actual-api-key`

To run any project command, prefix it with `pdm run`.

## Configuration (`config.ini`)

All experimental parameters are defined in the `config.ini` file. For a direct replication, the key settings to verify are:

*   **`[Study]`**:
    *   `num_replications = 30`
    *   `mapping_strategy`: Should be set to `correct` or `random` depending on the experiment you wish to replicate.
*   **`[LLM]`**:
    *   `model_name`: The API identifier for the LLM to be tested (e.g., `google/gemini-flash-1.5`).
    *   `temperature`: `0.2` was used in the original study for deterministic output.

The framework automatically archives this file with the results for guaranteed reproducibility.

## Experiment and Study Workflow

The research process is divided into two main stages: first, generating the data for each experimental condition, and second, compiling those conditions into a final study for analysis.

### Stage 1: Generate Data for Each Experimental Condition

The first stage is to generate a complete set of results for each of the 12 conditions in the study's factorial design (2 `mapping_strategy` levels x 6 `group_size` levels).

For each condition, you will:
1.  **Configure `config.ini`**: Set the `mapping_strategy` and `group_size` parameters for the specific condition you are running.
2.  **Run the Experiment**: Execute the `new_experiment.ps1` script. This will create a new, self-contained experiment directory in `output/new_experiments/`.

This process must be repeated until you have 12 separate experiment directories.

**Execution:**
```powershell
# Example: After setting parameters in config.ini
./new_experiment.ps1
```

> **Tip for Long Runs:** Generating all 12 experiments can take a significant amount of time and may be interrupted. The framework is designed for this.
> -   Use `audit_experiment.ps1` to get a detailed, read-only status report on any experiment.
> -   Use `fix_experiment.ps1` to intelligently resume any interrupted run. The script will automatically pick up where it left off, ensuring no work is lost.

### Stage 2: Compile and Analyze the Study

Once you have generated and validated all 12 experiment directories, you can proceed to the final analysis.

**Step 1: Organize Your Experiments**
Manually create a new study directory (e.g., `output/studies/My_Replication_Study/`) and move all 12 of your completed experiment folders into it.

**Step 2: Perform a Pre-Flight Check (`audit_study.ps1`)**
Before running the final compilation, it is best practice to run a consolidated audit on the entire study directory. This script checks every experiment and confirms that the study is complete and ready for analysis.

**Execution:**
```powershell
./audit_study.ps1 -StudyDirectory "output/studies/My_Replication_Study"
```

**Step 3: Run the Final Analysis (`compile_study.ps1`)**
This is the final step. The `compile_study.ps1` script orchestrates the entire analysis pipeline. It aggregates the data from all experiments, runs the Two-Way ANOVA, and generates the final, publication-ready reports and plots.

**Execution:**
```powershell
./compile_study.ps1 -StudyDirectory "output/studies/My_Replication_Study"
```

**Final Artifacts:**
The script generates two key outputs in your study directory:
1.  A master `STUDY_results.csv` file containing the aggregated data from all 12 experiments.
2.  A new `anova/` subdirectory containing:
    *   `STUDY_analysis_log.txt`: A comprehensive text report of the statistical findings.
    *   `boxplots/`: Publication-quality plots visualizing the results.
    *   `diagnostics/`: Q-Q plots used for checking statistical assumptions.

## Troubleshooting Common Issues

This section provides solutions to the most common issues researchers may encounter when setting up the framework or running experiments.

| Issue | Solution |
| :--- | :--- |
| **`pdm` command not found** | This usually means the Python scripts directory is not in your system's PATH. You can either add it, or use `python -m pdm` as a reliable alternative (e.g., `python -m pdm install -G dev`). |
| **API Errors during an experiment run** | Network issues or API rate limits can cause individual LLM calls to fail. The framework is designed for this. Simply run the `fix_experiment.ps1` script on the experiment directory. It will automatically find and re-run only the failed API calls. |
| **"Permission Denied" error when building DOCX files** | This error occurs if a `.docx` file is open in Microsoft Word while the `pdm run build-docs` script is running. Close the file in Word, and the script will automatically retry and continue. |
| **`git` command not found** | The framework requires Git for versioning and reproducibility checks. Please install it from [git-scm.com](https://git-scm.com/downloads) and ensure it is available in your system's PATH. |
| **All LLM sessions fail (100% failure rate)** | This indicates a model configuration problem. Verify the model name in `config.ini` matches available models and check your API credentials and permissions. |
| **Repair process loops indefinitely** | The repair system automatically limits retry attempts to 3 cycles maximum. After 3 cycles, it proceeds with available data to prevent endless loops when external factors cause persistent failures. |
| **Enhanced status messages** | The framework now provides colored error output and detailed progress tracking (elapsed time, remaining time, ETA) for better visibility during long-running operations. |

## Related Files

*   `base_query.txt`

    This file contains the final prompt template used for the LLM matching task. It is the product of a systematic, multi-stage piloting process. Various prompt structures and phrasing were tested to find the version that yielded the most reliable and consistently parsable structured output from the target LLM.

*   `country_codes.csv`

    This file provides a mapping from the country/state abbreviations used in the Astro-Databank to their full, standardized names. A sample is shown below. The complete file can be found at `data/foundational_assets/country_codes.csv`.

| Abbreviation | Country |
| :--- | :--- |
| `AB (CAN)` | Canada |
| `AK (US)` | United States |
| `ENG (UK)` | United Kingdom |
| `FR` | France |
| `GER` | Germany |