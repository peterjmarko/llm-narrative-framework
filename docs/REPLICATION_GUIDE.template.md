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

The **User-Facing Interface** comprises PowerShell orchestration scripts that provide a simple, consistent way to execute complex workflows. These scripts handle parameter validation, error recovery, and progress tracking, allowing researchers to focus on the research questions rather than implementation details.

The **Core Logic** contains the production Python scripts in the `src/` directory that implement the actual data processing, experiment execution, and analysis algorithms. These modules are designed to be modular, testable, and reusable across different research contexts.

The **Project Governance** component includes documentation, diagrams, the validation test suite, and developer utilities that ensure the framework maintains high standards of quality, reproducibility, and transparency.

The **Data & Artifacts** component manages all inputs and outputs, including source data, generated experiments, analysis reports, and project-level documentation that provides provenance for all research artifacts.

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

## Prerequisites

The framework was developed and validated on a specific stack of technologies. Variations are possible but not currently supported. Before proceeding, please ensure you have the following:

*   **Software:**
    *   **Operating System:** Windows (the primary development and testing platform).
    *   **PowerShell:** Version 7.0 or higher.
    *   **Git:** For cloning the repository.
    *   **Solar Fire:** A licensed copy of version 9.
    *   **GraphPad Prism:** Version 10.6.1 for validating statistical analysis and reporting functionalities.

*   **Accounts & Services:**
    *   **OpenRouter:** An account with a valid API key and sufficient funds to cover the cost of LLM queries.
    *   **Astro-Databank:** A registered account at `astro.com` (this is only required if you intend to generate a new dataset via **Path 2: Methodological Replication**).

## Setup and Installation

This project uses **PDM** for dependency and environment management. Please see the **[🤝 Developer's Guide (DEVELOPERS_GUIDE.md)](DEVELOPERS_GUIDE.md)** for detailed information on the project environment and its maintenance.

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

*   **`[Experiment]`**:
    *   `num_replications = 30`: Selected to have 80% statistical power for small effects (Cohen's d < 0.20).
    *   `num_trials = 80`: Provides 1.80:1 signal-to-noise ratio for d > 0.20 effects.
    *   `group_size`: Should be set to `7`, `10`, or `14` depending on the experiment you wish to replicate.
    *   `mapping_strategy`: Should be set to `correct` or `random` depending on the experiment you wish to replicate.
*   **`[LLM]`**:
    *   `model_name`: The API identifier for the LLM to be tested (e.g., `google/gemini-2.0-flash-lite-001`).
    *   `temperature`: `0.0` was used in the original study for deterministic output.

The framework automatically archives this file with the results for guaranteed reproducibility.

## The Data Preparation Pipeline

The data preparation pipeline is a fully automated, multi-stage workflow that transforms the raw data from the Astro-Databank into the final `personalities_db.txt` file used in the experiments. The overall flow of data artifacts is shown below.

{{grouped_figure:docs/diagrams/flow_prep_1_qualification.mmd | scale=2.5 | width=85% | caption=Figure S4: Data Prep Flow 1 - Data Sourcing and Candidate Qualification.}}

{{grouped_figure:docs/diagrams/flow_prep_2_selection.mmd | scale=2.5 | width=100% | caption=Figure S5: Data Prep Flow 2 - LLM-based Candidate Selection.}}

{{grouped_figure:docs/diagrams/flow_prep_3_generation.mmd | scale=2.5 | width=100% | caption=Figure S6: Data Prep Flow 3 - Profile Generation.}}

This guide supports three distinct research paths.

**Path 1: Direct Replication (Computational Reproducibility)**
To ensure computational reproducibility of the original findings, researchers should use the static data files and randomization seeds included in this repository. This path validates that the framework produces the same statistical results.

**Path 2: Methodological Replication (Testing Robustness)**
To test the robustness of the findings, researchers can use the framework's automated tools to generate a fresh dataset from the live Astro-Databank (ADB). The instructions below detail this workflow, which is organized into four main stages.

**Path 3: Conceptual Replication (Extending the Research)**
To extend the research, researchers can modify the framework itself, for example, by using a different LLM for the matching task or altering the analysis scripts.

### Models Used in the Original Study

For a direct or methodological replication, it is crucial to use the exact models and versions from the original study. All models were accessed via the **OpenRouter API**.

| Purpose | Model Name | API Identifier |
| :--- | :--- | :--- |
| Eminence Scoring (LLM A) | OpenAI GPT-5 | `openai/gpt-5-chat` |
| OCEAN Scoring (LLM B) | Anthropic Claude 4 Sonnet | `anthropic/claude-4-sonnet` |
| Neutralization (LLM C) | Google Gemini 2.5 Pro | `google/gemini-2.5-pro` |
| Evaluation (LLM D) | Google Gemini 1.5 Flash | `google/gemini-1.5-flash-001` |

*Access Dates for Evaluation LLM: September 2025*

### Stage 1: Data Sourcing, Link Finding & Validation (Automated)

The entire data preparation workflow is managed by a single, intelligent orchestrator: `prepare_data.ps1`. This script is fully resumable and is the recommended method for generating a new dataset.

**Prerequisites:** An account at `astro.com` and credentials in the `.env` file.
```powershell
# Run the entire data preparation pipeline
.\prepare_data.ps1
```
This single command will execute all the necessary steps, from fetching the raw data to generating the final `personalities_db.txt` file. The individual `pdm run` scripts (e.g., `pdm run find-links`) are also available for advanced development and debugging but are not part of the standard replication workflow.

#### a. Fetching Raw Data (fetch_adb_data.py)

This script automates the scraping of the Astro-Databank website.

**Prerequisites:**
1. A registered account at astro.com.
2. Credentials in the .env file: ADB_USERNAME and ADB_PASSWORD.

**Execution:**
```bash
# Fetch a new dataset from the live ADB
pdm run fetch-adb
```
This produces `data/sources/adb_raw_export.txt`.

#### b. Finding Wikipedia Links (find_wikipedia_links.py)

This script takes the raw export and finds the best-guess Wikipedia URL for each subject, creating the intermediate `data/processed/adb_wiki_links.csv` file.

```bash
# Find Wikipedia links for all raw records
pdm run find-links
```

#### c. Validating Wikipedia Pages (validate_wikipedia_pages.py)

This script takes the list of found links, validates the content of each page, and produces the final `data/reports/adb_validation_report.csv` and a human-readable summary.

**A Note on Reproducibility:** Because Wikipedia is a dynamic source, this validation is not perfectly reproducible. For direct replication, the study's pipeline relies on the static report (`adb_validation_report.csv`) included in the repository.

```bash
# Validate the content of each found Wikipedia page
pdm run validate-pages
```

#### d. A Note on Determining the Optimal Cutoff Parameters
To ensure the parameters for the final candidate selection algorithm were chosen objectively and were optimally tuned to the specific shape of the dataset's variance curve, a **systematic sensitivity analysis** was performed using the dedicated `scripts/analyze_cutoff_parameters.py` utility. The search space for the parameters was iteratively expanded to ensure a true global optimum was found.

The script performed a grid search over a wide range of values for `cutoff_search_start_point` and `smoothing_window_size`. To avoid overfitting to a single "best" result, a sophisticated **stability-based recommendation algorithm** was used. This algorithm first identifies a cluster of high-performing parameter sets (those with a low error between the predicted and ideal cutoffs) and then calculates a "stability score" for each based on the average error of its neighbors in the parameter grid. The final recommendation is the parameter set with the best stability score, representing the center of the most stable, high-performing region.

The final, expanded analysis revealed several key insights:

*   **The Variance Curve Shape:** The cumulative variance curve has a distinct shape: a long, steep decline followed by a wide, shallow plateau containing long-wavelength, low-amplitude noise.
*   **Justification for the Final Parameters:** A high `cutoff_search_start_point` (3500) was essential to force the analysis to begin *on the plateau*, isolating the region of interest. A large `smoothing_window_size` (800) was necessary to average out the long, shallow waves on the plateau, allowing the slope-based algorithm to detect the true global trend.

Based on this comprehensive, data-driven analysis, the following optimal parameters were chosen and set in `config.ini`:

*   `cutoff_search_start_point = 3500`
*   `smoothing_window_size = 800`

The plot of this analysis (see Figure S1) provides a clear visual justification for these choices. It shows how the algorithm, using these parameters, correctly identifies the start of the curve's final plateau, resulting in a final cutoff of 4,954 subjects.

{{grouped_figure:data/reports/variance_curve_analysis.png | caption=Figure S7: Variance Curve Analysis for Optimal Cohort Selection. The plot shows the raw cumulative variance, the smoothed curve (800-pt moving average), the search start point (3500), and the final data-driven cutoff (4954).}}

### Stage 2: Pre-filtering & Scoring (Automated)

#### a. Selecting Eligible Candidates (select_eligible_candidates.py)

This script performs all initial data quality checks (valid birth year, 'OK' status, uniqueness), ensuring that expensive LLM scoring is only performed on high-quality candidates.

```bash
# Create the list of eligible candidates
pdm run select-eligible
```

#### b. Eminence Scoring (generate_eminence_scores.py)

This script processes the eligible candidates list and uses an LLM to assign a calibrated eminence score to each, creating the rank-ordered eminence_scores.csv.

```bash
# Generate eminence scores for all eligible candidates
pdm run gen-eminence
```

#### c. OCEAN Scoring & Dynamic Cutoff (generate_ocean_scores.py)

This script is a fully automated, resilient process that determines the final subject pool size. It processes subjects by eminence and stops when diversity (variance) shows a sustained drop. Its robust pre-flight check re-analyzes all existing data on startup, ensuring that interrupted runs can be safely resumed or correctly finalized without user intervention.

```bash
# Generate OCEAN scores to determine the final cutoff
pdm run gen-ocean
```

### Stage 3: Final Subject Selection (Automated)

#### a. Selecting Final Candidates (select_final_candidates.py)

This script performs the final transformation. It filters the eligible list by the OCEAN set, resolves country codes, and sorts the result by eminence.

```bash
# Create the final, transformed list of subjects
pdm run select-final
```

#### b. Formatting for Import (prepare_sf_import.py)

This script formats the final candidates list for import into Solar Fire, encoding the unique idADB of each subject into the ZoneAbbr field for data integrity.

```bash
# Prepare the final list for the manual import step
pdm run prep-sf-import
```
This produces `data/intermediate/sf_data_import.txt`, the input for the next stage. Note: to facilitate the Solar Fire import process, this file is copied to the Solar Fire import folder once it's created in its original location (see the 'File Locations' section in 'Importing to and Exporting from Solar Fire' below).

### Stage 4: Profile Generation

This is the final stage, which assembles the personality profiles for the selected candidates. It involves both automated scripts and a one-time manual process using the Solar Fire software.

The process consists of three main parts:

1.  **Preparing the Solar Fire Import File:** The `prepare_sf_import.py` script formats the final candidates list for import into Solar Fire.

2.  **Solar Fire Import/Calculate/Export Process:** This is a manual process that involves importing the data into Solar Fire, calculating all charts, and exporting the chart data. This process is detailed in the next section.

3.  **Final Database Generation:** Once the `sf_chart_export.csv` charts file is exported from Solar Fire, the `create_subject_db.py` and `generate_personalities_db.py` scripts assemble the final personalities database. This process is detailed in the "Final Database Generation" section. Note: to facilitate the Solar Fire export process, the exported charts file is copied from the Solar Fire export folder to its permanent location at `data/foundational_assets/` (see the 'File Locations' section in 'Importing to and Exporting from Solar Fire' chapter below).

## Importing to and Exporting from Solar Fire

Once the data is prepared, we can start making the Solar Fire astrology software ready for the import. This commercial program is available at https://alabe.com/solarfireV9.html. Many good alternatives exist, but the data preparation, import, and export procedures will be different in each case. The main advantages of Solar Fire are as follows:

*   It is the industry standard astrology software for astrologers around the world.
*   It has a long history of development and is considered accurate and reliable.
*   Data import / chart export functionality is straightforward and seamless.
*   Its delineations library is fully exportable.
*   It is relatively inexpensive ($360 USD currently).

### File Locations

Solar Fire stores its user files in the standard Windows Documents folder. Understanding these locations is helpful for managing the import/export process:

*   **Solar Fire User Files:** `Documents\Solar Fire User Files`
*   **Subdirectories:**
    *   **Charts:** Chart ('*.sfcht') files accessible within Solar Fire
    *   **Import:** Imported birth data files (various formats)
    *   **Export:** Exported astrological data (various formats)
    *   **Points & Colors:** Settings ('*.pts') file for Displayed Points
    *   **Interpretations:** Delineations library ('*.def') files

### One-Time Software Setup

The following configuration steps only need to be performed once. After the initial setup, you can proceed directly to the **Import/Export Workflow**.

#### 1. Configure Chart Points

You must define which astrological points are included in the calculations.

*   **Menu:** `Chart Options > Displayed Points...`
*   **Action:**
    1.  Create a new `.pts` file (e.g., `llm_narrative_dp12.pts`).
    2.  Edit this file to include exactly these 12 points: Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, Pluto, Ascendant, and Midheaven.
    3.  Save the file and ensure it is selected as the active set.

{{grouped_figure:docs/images/replication_guide/sf_setup_1_displayed_points.png | width=60% | caption=Figure S8: The Solar Fire "Displayed Points" dialog configured with the 12 required chart points.}}

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

{{grouped_figure:docs/images/replication_guide/sf_setup_2_import_format.png | width=80% | caption=Figure S9: The Solar Fire "Edit ASCII Formats" dialog configured for the CQD Import format.}}

**b. Define Export Format**

*   **Menu:** `Chart > Export Charts as Text...`
*   **Action:**
    1.  Click the **'Edit ASCII...'** button to open the format definitions dialog.
    2.  **This list is separate from the import list.** You must create another **new format definition**.
    3.  Repeat the exact same configuration as the import format, set it to `Comma Quote Delimited`, and add the same 9 fields in the same order.
    4.  Save the format as `CQD Export`. This ensures both workflows use an identical data structure.

{{grouped_figure:docs/images/replication_guide/sf_setup_3_export_format.png | width=80% | caption=Figure S10: The Solar Fire "Export Chart Data" format dialog configured for the CQD Export format.}}

### Import/Export Workflow

After completing the one-time setup, follow this workflow to process the data.

#### Pre-flight Check: Clearing Existing Chart Data (For Re-runs)
If you are re-running the import process, you must first clear the existing charts from your Solar Fire charts file to avoid duplicates.

*   **Menu:** `Chart > Open...`
*   **Action:**
    1.  In the **'Chart Database'** dialog, select your charts file (e.g., `adb_candidates.sfcht`).
    2.  Click the **'All'** button to highlight every chart in the file.
    3.  Click the **'Delete...'** button, then select **'Selected Charts...'**.
    4.  A dialog will ask: "Do you wish to confirm the deletion of each chart individually?". Click **'No'** to delete all charts at once.
    5.  Click **'Cancel'** to close the 'Chart Database' dialog. The file is now empty and ready for a fresh import.

{{grouped_figure:docs/images/replication_guide/sf_workflow_1_clear_charts.png | width=95% | caption=Figure S11: The Solar Fire "Chart Database" dialog with all charts selected for deletion.}}

#### Step 1: Import Birth Data
The procedure below is for the production workflow. When validating the Personality Assembly Algorithm, choose `sf_data_import.assembly_logic.txt` in the Solar Fire import folder for #2 and save to `adb_candidates.assembly_logic` for #3.

*   **Menu:** `Utilities > Chart Import/Export...`
*   **Action:**
    1.  If a **"Confirm"** dialog appears immediately, click **'OK'**.
    2.  On the **'Import From' tab**, select `ASCII files` and choose `sf_data_import.txt` in the import folder.
    3.  On the **'Save To' tab**, ensure your `adb_candidates.sfcht` file is selected.
    4.  On the **'Options' tab**, select your `CQD Import` format.
    5.  Click the **'Convert'** button.
    6.  Once the import completes, click the **'Quit'** button to close the dialog.

{{grouped_figure:docs/images/replication_guide/sf_workflow_2_import_dialog.png | width=95% | caption=Figure S12: The Solar Fire "Chart Import/Export" dialog configured to import the prepared data.}}

#### Step 2: Calculate All Charts
The procedure below is for the production workflow. When validating the Personality Assembly Algorithm, select `adb_candidates.assembly_logic` for #1.

*   **Menu:** `Chart > Open...`
*   **Action:**
    1.  Select the charts file you just created (e.g., `adb_candidates.sfcht`).
    2.  Click the **'All'** button to select all charts in the file.
    3.  Click the **'Open...'** button. This will calculate all charts and add them to the "Calculated Charts" list. The processing time will vary depending on the number of subjects (typically a few minutes for each set of 1,000 charts).

> **A Note on Character Encoding:** In the "Calculated Charts" list, you may notice that some names with international characters appear corrupted (e.g., `PelÃ©` instead of `Pelé`). This is an expected display issue within Solar Fire. **Do not attempt to fix these names manually.** The automated scripts are designed to detect and repair these encoding errors in the next stage, ensuring the final database is clean.

#### Step 3: Export Chart Data
The procedure below is for the production workflow. When validating the Personality Assembly Algorithm, browse to the Solar Fire export folder and set the filename to `sf_data_import.assembly_logic.txt` for #6.

*   **Menu:** `Chart > Export Charts as Text...`
*   **Action:**
    1.  In the "Calculated Charts" window, select all calculated charts.
    2.  In the menu item's **"Export Chart Data" dialog**, check the **'Chart Details'** and **'Column Types'** boxes.
    3.  Under **'Select types of points'**, ensure **'Chart Points'** is selected.
    4.  For the ASCII format, select your custom `CQD Export` format.
    5.  Set **'Field Delimiters'** to `Comma Quote (CQD)` and 'Destination' to `Export to File`.
    6.  Browse to the export directory, set the filename to `sf_chart_export.csv`, and click **Save**. Note: 'Save as type' cannot be set in this dialog.
    7.  **Warning:** Solar Fire will overwrite this file without confirmation. Click **'Export'**.
    8.  Once the export completes successfully, click the **'Quit'** button to close the dialog.

{{grouped_figure:docs/images/replication_guide/sf_workflow_3_export_dialog.png | width=75% | caption=Figure S13: The Solar Fire "Export Chart Data" dialog configured for the final chart data export.}}

The exported file consists of a repeating 14-line block for each subject. The structure of this block is detailed below:

| Line(s) | Content/Fields | Description |
| :--- | :--- | :--- |
| 1 | `Name`, `Date`, `Time`, `ZoneAbbr`, `ZoneOffset`, `Place`, `State`, `Lat`, `Lon` | The subject's core birth data. The `idADB` is critically encoded into the `ZoneAbbr` field. |
| 2 | `"Body Name","Body Abbr","Longitude"` | The literal header line for the planetary data that follows. |
| 3-14 | `Point Name`, `Point Abbr`, `Zodiacal Longitude` | The data for each of the 12 chart points (Sun, Moon, ..., Midheaven). |

The entire file consists of `N * 14` lines, where `N` is the final number of subjects.

#### Special Step: Generate Interpretation Reports

This procedure is not part of the production workflow and only applies to the last manual item ('Generate and save interpretation reports...') of validating the Personality Assembly Algorithm ('test-assembly-setup'). The first 3 stages of the 5-stage validation process should be completed at this point.

*   **Menu:** `Interps > Full Report...`
*   **Action:**
    1.  In the "Calculated Charts" window, select the first calculated chart.
    2.  In the menu item's "Select Text for Report" dialog, select only 'Balances' and 'Chart Points' for the 'Text Categories' section.
    3.  Click View. The report is generated and opened in your default word processor.
    4.  Save As a 'Plain Text' file in the 'Documents/Solar Fire User Files/Export' directory with the following filename: 'sf_raw_report.assembly_logic_[SN]', where "[SN]" is a sequence number from 1 to 17. For example: 'sf_raw_report.assembly_logic_1'. If a 'File Conversion' dialog is shown, accept the default 'Windows' text encoding (leave boxes unchecked). Close the file and do not save if asked.
    5.  Click Cancel in the "Select Text for Report" dialog and select the next chart.
    6.  Go through steps 2 to 5 for all charts in sequence (#2 to #17) using the sequence number as the suffix in the filename. Save last report as 'sf_raw_report.assembly_logic_17'.
    7.  Once all reports have been exported, click Cancel in the "Select Text for Report" dialog and continue with executing stage 4 and 5 of the validation (i.e., resume 'test-assembly-setup').

## Final Database Generation

The final stage of the pipeline assembles the personalities_db.txt file. This is a fully automated, three-step process.

### Step 1: Exporting the Delineations Library (One-Time Task)

The personality descriptions are assembled from a library of pre-written text components. This library must first be exported from Solar Fire.

*   **Menu:** `Interps > Interpretation Files > Natal`
*   **Action:**
    1.  Select `Standard.int` and click **'Edit'**.
    2.  In the 'Interpretations Editor', go to `File > Decompile...` and save the file. This creates `Standard.def` in the `Documents/Solar Fire User Files/Interpretations` directory.
    3.  Copy this file to the `data/foundational_assets/` folder and rename it to `sf_delineations_library.txt`. Note: Filename extensions must be displayed for this rename.

### Step 2: Automated Delineation Neutralization (neutralize_delineations.py)

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

### Step 3: Automated Database Generation (create_subject_db.py, generate_personalities_db.py)

Once all foundational assets are in place, the final assembly is handled by two scripts.

#### a. Integrating Chart Data (create_subject_db.py)
This script bridges the manual software step. It reads the `sf_chart_export.csv` file, decodes the `idADB` from the `ZoneAbbr` field, and merges the chart data with the final subject list to produce the clean `data/processed/subject_db.csv`.
```bash
# Integrate the manual chart data export
pdm run create-subject-db
```

#### b. Assembling the Final Database (generate_personalities_db.py)
This script performs the final assembly. It loads the clean `subject_db.csv`, the configuration files (`point_weights.csv`, `balance_thresholds.csv`), and the entire neutralized delineation library. For each person, it calculates their divisional classifications according to a deterministic algorithm and assembles the final description by looking up the corresponding text components. **The entire personality assembly algorithm has been rigorously validated against a ground-truth dataset generated by the source Solar Fire software to ensure its output is bit-for-bit identical.**
```bash
# Generate the final personalities database
pdm run gen-db
```
The output is `personalities_db.txt`, a tab-delimited file with the fields: `Index`, `Name`, `BirthYear`, and `DescriptionText`.

With the `personalities_db.txt` file generated, the data preparation phase is complete. The following sections describe how to run the experiment lifecycle and analysis.

## Experiment and Study Workflow

The research process is divided into two main stages: first, generating the data for each experimental condition, and second, compiling those conditions into a final study for analysis.

### Stage 1: Generate Data for Each Experimental Condition

The first stage is to generate a complete set of results for each of the 12 conditions in the study's factorial design (2 `mapping_strategy` levels x 6 `group_size` levels).

For a factorial study, you can use the `generate_factorial_commands.ps1` script to automatically generate all the necessary commands:

```powershell
# Generate commands for all experimental conditions
./generate_factorial_commands.ps1 -OutputScript "run_factorial_study.ps1"
```

This will create a script with all the necessary `new_experiment.ps1` commands for each condition. You can then execute this script to run all experiments.

For each condition, you will:

1.  **Configure `config.ini`**: Set the `mapping_strategy` and `group_size` parameters for the specific condition you are running.
2.  **Run the Experiment**: Execute the `new_experiment.ps1` script. This will create a new, self-contained experiment directory in `output/new_experiments/`.

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