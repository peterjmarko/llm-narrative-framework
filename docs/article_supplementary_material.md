---
title: "Supplementary Material: A Replication Guide"
author: "Peter J. Marko"
date: "[Date]"
---

This document is the **Replication Guide** that provides supplementary material to the main article, "A Framework for the Computationally Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology." Its purpose is to serve as a detailed, step-by-step guide for researchers seeking to perform a **direct replication of the original study's findings**. The sections are arranged in workflow order as follows:

*   **The Data Preparation Pipeline:** Describes the fully automated scripts that transform raw data into the final subject list.
*   **The Manual Chart Calculation Step:** Details the one-time setup and repeatable workflow for using the Solar Fire astrology program.
*   **Final Database Generation:** Describes the automated scripts that neutralize the esoteric texts and assemble the final `personalities_db.txt`.

## The Data Preparation Pipeline

This guide supports two distinct research paths.

**Path 1: Direct Replication (Validating Original Findings)**
The Astro-Databank (ADB) is a live research database. To directly replicate the original study, it is essential to use the static data files included in this repository (e.g., `adb_raw_export.txt`, `adb_validation_report.csv`). This ensures the pipeline starts with the identical data used for the original analysis, providing a stable baseline for comparison.

**Path 2: Conceptual Replication (Creating a New Dataset)**
For new research, the framework provides a fully automated pipeline to generate a fresh dataset from live sources. The instructions below describe how to use the provided scripts to create new data assets.

### Stage 1: Data Sourcing & Validation (Automated)

#### a. Fetching Raw Data (`fetch_adb_data.py`)
This script automates the scraping of the Astro-Databank website.

**Prerequisites:**
1.  A registered account at `astro.com`.
2.  Credentials in the `.env` file: `ADB_USERNAME` and `ADB_PASSWORD`.

**Execution:**
```bash
# Fetch a new dataset from the live ADB
pdm run fetch-adb
```
The script logs in, applies the required search filters, and saves the complete results to `data/sources/adb_raw_export.txt`.

#### b. Validating Data (`validate_adb_data.py`)
This script audits the raw export against Wikipedia to verify each entry is a person with a recorded death date.

**A Note on Reproducibility:** Because Wikipedia is a dynamic source, this validation is not perfectly reproducible. The study's pipeline therefore relies on the static report that resulted from this one-time audit, which is included as `data/reports/adb_validation_report.csv`. This static report ensures all subsequent filtering is fully deterministic.

**Execution:**
```bash
# Run the validation script on the raw export
pdm run validate-adb
```

### Stage 2: Pre-filtering & Scoring (Automated)

#### a. Selecting Eligible Candidates (`select_eligible_candidates.py`)
This script performs all initial data quality checks (valid birth year, 'OK' status, uniqueness), ensuring that expensive LLM scoring is only performed on high-quality candidates.
```bash
# Create the list of eligible candidates
pdm run select-eligible
```

#### b. Eminence Scoring (`generate_eminence_scores.py`)
This script processes the eligible candidates list and uses an LLM to assign a calibrated eminence score to each, creating the rank-ordered `eminence_scores.csv`.
```bash
# Generate eminence scores for all eligible candidates
pdm run gen-eminence
```

#### c. OCEAN Scoring & Dynamic Cutoff (`generate_ocean_scores.py`)
This script is a fully automated, resilient process that determines the final subject pool size. It processes subjects by eminence and stops when diversity (variance) shows a sustained drop. Its robust pre-flight check re-analyzes all existing data on startup, ensuring that interrupted runs can be safely resumed or correctly finalized without user intervention.
```bash
# Generate OCEAN scores to determine the final cutoff
pdm run gen-ocean
```

### Stage 3: Final Subject Selection (Automated)

#### a. Selecting Final Candidates (`select_final_candidates.py`)
This script performs the final transformation. It filters the eligible list by the OCEAN set, resolves country codes, and sorts the result by eminence.
```bash
# Create the final, transformed list of subjects
pdm run select-final
```

#### b. Formatting for Import (`prepare_sf_import.py`)
This script formats the final candidates list for import into Solar Fire, encoding the unique `idADB` of each subject into the `ZoneAbbr` field for data integrity.
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

**b. Define Export Format**
*   **Menu:** `Chart > Export Charts as Text...`
*   **Action:**
    1.  Click the **'Edit ASCII...'** button to open the format definitions dialog.
    2.  **This list is separate from the import list.** You must create another **new format definition**.
    3.  Repeat the exact same configuration as the import format, set it to `Comma Quote Delimited`, and add the same 9 fields in the same order.
    4.  Save the format as `CQD Export`. This ensures both workflows use an identical data structure.

### Import/Export Workflow

After completing the one-time setup, follow this workflow to process the data.

#### Pre-flight Check: Clearing Existing Chart Data (For Re-runs)
If you are re-running the import process, you must first clear the existing charts from your Solar Fire charts file to avoid duplicates.

*   **Menu:** `Chart > Open...`
*   **Action:**
    1.  In the 'Chart Database' dialog, select your charts file (e.g., `adb_famous.sfcht`).
    2.  Click the **'All'** button to highlight every chart in the file.
    3.  Click the **'Delete...'** button, then select **'Selected Charts...'**.
    4.  A dialog will ask: "Do you wish to confirm the deletion of each chart individually?". Click **'No'** to delete all charts at once.
    5.  Click **'Cancel'** to close the 'Chart Database' dialog. The file is now empty and ready for a fresh import.

#### Step 1: Import Birth Data

*   **Menu:** `Utilities > Chart Import/Export...`
*   **Action:**
    1.  If a "Confirm" dialog appears immediately, click **'OK'**.
    2.  On the **'Import From' tab**, select `ASCII files` and choose `data/intermediate/sf_data_import.txt`.
    3.  On the **'Save To' tab**, ensure your `adb_famous.sfcht` file is selected.
    4.  On the **'Options' tab**, select your `CQD Import` format.
    5.  Click the **'Convert'** button.
    6.  Once the import completes, click the **'Quit'** button to close the dialog.

#### Step 2: Calculate All Charts

*   **Menu:** `Chart > Open...`
*   **Action:**
    1.  Select the charts file you just created (e.g., `adb_famous.sfcht`).
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
    6.  Browse to the `data/foundational_assets/` directory and set the filename to `sf_chart_export.csv`.
    7.  **Warning:** Solar Fire will overwrite this file without confirmation. Click **'Export'**.
    8.  Once the export completes successfully, click the **'Quit'** button to close the dialog.

The format of the exported file is as follows:

```
"<First_name Last_name>","<D MMMM YYYY>","<H:MM>","<Encoded_idADB>","<±H:MM>","<Place>","<State>","<DDvMM>","<DDDhMM>"
"Body Name","Body Abbr","Longitude"
...
```

Each 14-line block contains the following for one person:

*   **Line 1:** Name, date of birth, time of birth, the **Base58-encoded `idADB`** in the time zone field, time zone UTC offset, place, state, latitude with vertical (N/S) direction, longitude with horizontal (E/W) direction.
*   **Line 2:** Header for the remaining lines.
*   **Lines 3-14:** Chart point's name, point's abbreviation, point's zodiacal longitude (0.00-359.99 degrees)

The entire file consists of `N * 14` lines, where `N` is the final number of subjects.

## Final Database Generation

The final stage of the pipeline assembles the `personalities_db.txt` file. This is a fully automated, three-step process.

### Step 1: Exporting the Delineations Library (One-Time Task)

The personality descriptions are assembled from a library of pre-written text components. This library must first be exported from Solar Fire.

*   **Menu:** `Interps > Interpretation Files > Natal`
*   **Action:**
    1.  Select `Standard.int` and click **'Edit'**.
    2.  In the 'Interpretations Editor', go to `File > Decompile...` and save the file. This creates `standard.def` in the `Documents/Solar Fire User Files/Interpretations` directory.
    3.  Copy this file to `data/foundational_assets/sf_delineations_library.txt`.

### Step 2: Automated Delineation Neutralization (`neutralize_delineations.py`)

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
```
The script's output is the collection of `.csv` files in the `data/foundational_assets/neutralized_delineations/` directory.

### Step 3: Automated Database Generation (`create_subject_db.py`, `generate_personalities_db.py`)

Once all foundational assets are in place, the final assembly is handled by two scripts.

#### a. Integrating Chart Data (`create_subject_db.py`)
This script bridges the manual software step. It reads the `sf_chart_export.csv` file, decodes the `idADB` from the `ZoneAbbr` field, and merges the chart data with the final subject list to produce the clean `data/processed/subject_db.csv`.
```bash
# Integrate the manual chart data export
pdm run create-subject-db
```

#### b. Assembling the Final Database (`generate_personalities_db.py`)
This script performs the final assembly. It loads the clean `subject_db.csv`, the configuration files (`point_weights.csv`, `balance_thresholds.csv`), and the entire neutralized delineation library. For each person, it calculates their divisional classifications according to the deterministic algorithm and assembles the final description by looking up the corresponding text components.
```bash
# Generate the final personalities database
pdm run gen-db
```
The output is `personalities_db.txt`, a tab-delimited file with the fields: `Index`, `Name`, `BirthYear`, and `DescriptionText`.

The rest of the Testing Framework is fully automated in Python, as documented in the main Framework Manual.

## Related Files

*   `base_query.txt`

    This file contains the final prompt template used for the LLM matching task. It is the product of a systematic, multi-stage piloting process. Various prompt structures and phrasing were tested to find the version that yielded the most reliable and consistently parsable structured output from the target LLM.

*   `country_codes.csv`
    ```
    "Abbreviation","Country"
    "AB (CAN)","Canada"
    "AK (US)","United States"
    "AL (US)","United States"
    "ALB","Albania"
    "ALG","Algeria"
    "AM","Armenia"
    "AR (US)","United States"
    "ARG","Argentina"
    "ATG","Antigua and Barbuda"
    "AUS","Austria"
    "AUSTL","Australia"
    "AZ (US)","United States"
    "AZE","Azerbaijan"
    "BC (CAN)","Canada"
    "BEL","Belgium"
    "BIH","Bosnia and Herzegovina"
    "BLZ","Belize"
    "BRAS","Brazil"
    "BRU","Brunei"
    "BULG","Bulgaria"
    "BURMA","Myanmar"
    "BY","Belarus"
    "CA (US)","United States"
    "CHILE","Chile"
    "CHINA","China"
    "CO (US)","United States"
    "COL","Colombia"
    "CR","Costa Rica"
    "CT (US)","United States"
    "CUBA","Cuba"
    "CZ","Czech Republic"
    "DC (US)","United States"
    "DE (US)","United States"
    "DEN","Denmark"
    "DR","Dominican Republic"
    "EGYPT","Egypt"
    "ENG (UK)","United Kingdom"
    "ETH","Ethiopia"
    "FIN","Finland"
    "FL (US)","United States"
    "FR","France"
    "FRGU","French Guiana (France)"
    "FRPO","French Polynesia (France)"
    "GA (US)","United States"
    "GER","Germany"
    "GHANA","Ghana"
    "GRC","Greece"
    "GUAD","Guadeloupe (France)"
    "GUAT","Guatemala"
    "GUY","Guyana"
    "HI (US)","United States"
    "HK","Hong Kong (China)"
    "HRV","Croatia"
    "HUN","Hungary"
    "IA (US)","United States"
    "ID (US)","United States"
    "IL (US)","United States"
    "IMAN (UK)","Isle of Man (Crown Dependency)"
    "IN (US)","United States"
    "INDIA","India"
    "IRAN","Iran"
    "IRE","Ireland"
    "ISRL","Israel"
    "ITALY","Italy"
    "JAPAN","Japan"
    "KOREA","South Korea"
    "KS (US)","United States"
    "KY (US)","United States"
    "LA (US)","United States"
    "LEB","Lebanon"
    "LT","Lithuania"
    "LUX","Luxembourg"
    "MA (US)","United States"
    "MADA","Madagascar"
    "MART","Martinique (France)"
    "MB (CAN)","Canada"
    "MD (US)","United States"
    "ME (US)","United States"
    "MEX","Mexico"
    "MI (US)","United States"
    "MLYS","Malaysia"
    "MN (US)","United States"
    "MNE","Montenegro"
    "MO (US)","United States"
    "MONACO","Monaco"
    "MOR","Morocco"
    "MS (US)","United States"
    "MT (US)","United States"
    "NB (CAN)","Canada"
    "NC (US)","United States"
    "ND (US)","United States"
    "NE (US)","United States"
    "NETH","Netherlands"
    "NF (CAN)","Canada"
    "NH (US)","United States"
    "NIC","Nicaragua"
    "NIRE (UK)","United Kingdom"
    "NJ (US)","United States"
    "NM (US)","United States"
    "NOR","Norway"
    "NS (CAN)","Canada"
    "NV (US)","United States"
    "NY (US)","United States"
    "NZ","New Zealand"
    "OH (US)","United States"
    "OK (US)","United States"
    "ON (CAN)","Canada"
    "OR (US)","United States"
    "PA (US)","United States"
    "PAK","Pakistan"
    "PAN","Panama"
    "PAPUA","Papua New Guinea"
    "PAR","Paraguay"
    "PERU","Peru"
    "PHIL","Philippines"
    "POL","Poland"
    "PORT","Portugal"
    "PR (US)","Puerto Rico (U.S. territory)"
    "QU (CAN)","Canada"
    "REU","Réunion (France)"
    "RI (US)","United States"
    "ROM","Romania"
    "RU","Russia"
    "S LEONE","Sierra Leone"
    "SAFR","South Africa"
    "SAUDI","Saudi Arabia"
    "SC (US)","United States"
    "SCOT (UK)","United Kingdom"
    "SD (US)","United States"
    "SEN","Senegal"
    "SI","Slovenia"
    "SK (CAN)","Canada"
    "SPAIN","Spain"
    "STVI","Saint Vincent and the Grenadines"
    "SVK","Slovakia"
    "SWED","Sweden"
    "SWTZ","Switzerland"
    "SYRIA","Syria"
    "THAI","Thailand"
    "TN (US)","United States"
    "TONGA","Tonga"
    "TUN","Tunisia"
    "TUR","Turkiye"
    "TX (US)","United States"
    "UA","Ukraine"
    "UR","Uruguay"
    "UT (US)","United States"
    "VA (US)","United States"
    "VEN","Venezuela"
    "VIET","Vietnam"
    "VT (US)","United States"
    "WA (US)","United States"
    "WALES (UK)","United Kingdom"
    "WI (US)","United States"
    "WV (US)","United States"
    "WY (US)","United States"
    "YEMEN","Yemen"
    "ZAIRE","Democratic Republic of the Congo"
    "ZIM","Zimbabwe"
    ```