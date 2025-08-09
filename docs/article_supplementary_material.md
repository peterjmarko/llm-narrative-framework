---
title: "Supplementary Material: A Replication Guide"
author: "Peter J. Marko"
date: "[Date]"
---

This document is the **Replication Guide** that provides supplementary material to the main article, "A Framework for the Computationally Reproducible Testing of Complex Narrative Systems: A Case Study in Astrology." Its purpose is to serve as a detailed, step-by-step guide for researchers seeking to perform a **direct replication of the original study's findings**. The sections are arranged in workflow order as follows:

*   **Obtaining Birth Data from Astro-Databank:** Describes the filtering of the ADB research database and the manual extraction process for obtaining birth data.
*   **Data Preparation:** Describes the process of transforming the raw birth data in preparation for importing to the astrology software.
*   **Importing to and Exporting from Solar Fire:** Describes the process of importing of birth data to and exporting of astrological information from the Solar Fire astrology program.
*   **Creating the Personalities Database:** Describes the process of compiling the personalities database using the information obtained in the previous three steps.

## Obtaining Birth Data from Astro-Databank

This guide supports two distinct research paths.

**Path 1: Direct Replication (Validating Original Findings)**
The Astro-Databank (ADB) is a live research database. To directly replicate and validate the original study's results, it is essential to use the static data files included in this repository. This approach ensures that you are working with the identical dataset used for the original analysis, providing the most stable baseline for comparison.

**Path 2: Conceptual Replication (Creating a New Dataset)**
For researchers wishing to perform a conceptual replication or conduct new research, the framework provides a fully automated pipeline to generate a fresh dataset. The instructions below describe how to use the provided scripts to create a new, up-to-date export from the live ADB. Note that this will yield a different dataset than the one used in the original study.

The original manual data extraction steps are retained at the end of this section for methodological transparency.

### Automated Data Fetching (Recommended)

The project includes a Python script, `src/fetch_adb_data.py`, to fully automate scraping the Astro-Databank website.

**Prerequisites:**
1.  You must have a registered account at `astro.com`.
2.  Add your credentials to the `.env` file in the project's root directory:
    ```
    ADB_USERNAME=your-username-here
    ADB_PASSWORD=your-password-here
    ```

**Execution:**
Run the script from your terminal. It will log in, perform the search with the required filters (Top 5% Famous, has a Death record, AA/A Rating, etc.), scrape all results, and save them to a new file. The script is resilient, saving data incrementally, and includes an interactive prompt to prevent accidental overwrites, automatically creating a timestamped backup of any existing file.

```bash
# Run the script to fetch data
pdm run python src/fetch_adb_data.py

# To bypass the interactive prompt and force an overwrite
pdm run python src/fetch_adb_data.py --force
```
The script produces a rich, tab-separated output file (`data/sources/adb_raw_export.txt`) with a file-specific `Index` and the stable `idADB`, and includes fully processed timezone information. The columns are: `Index`, `idADB`, `LastName`, `FirstName`, `Gender`, `Day`, `Month`, `Year`, `Time`, `ZoneAbbr`, `ZoneTimeOffset`, `City`, `CountryState`, `Longitude`, `Latitude`, `Rating`, `Bio`, `Categories`, and `Link`.

**A Note on Downstream Compatibility:** This new, detailed format is superior for new research but is **not** directly compatible with the downstream processing scripts in this project (`filter_adb_candidates.py`, etc.), which were designed to parse the original, manually-exported `adb_raw_export.txt`. To use a newly fetched file with the existing pipeline, those scripts would need to be adapted.

### Manual Data Extraction (Obsolete)

The following procedure describes the original manual process for obtaining the initial database, which resulted in the static `data/sources/adb_raw_export.txt` file. This method produced a different, less detailed format and is no longer recommended.

1.  Navigate to `https://www.astro.com/adb-search/adb-search/`.
2.  Manually select the search criteria (Categories: Death, Top 5% of Profession; Options: AA/A Ratings, 500 results per page).
3.  Execute the search and use a browser extension like 'Table Capture' to copy the results from all pages.

The data obtained through this manual process required significant cleaning and resulted in a file with the columns: `ARN`, `Name`, `Born`, and `At`. The automated script is now the standard method.

## Data Preparation

The raw export of over 10,000 candidates must be validated, filtered, and formatted. This is an automated, three-step process driven by Python scripts.

### Step 1: Data Validation (`validate_adb_data.py`)

**A Note on Reproducibility and Dynamic Data:** The raw export (`adb_raw_export.txt`) is audited by `src/validate_adb_data.py`. This script cross-references each entry against Wikipedia to verify it is a person with a recorded death date. Because Wikipedia is a dynamic source, this validation is not perfectly reproducible. The study's pipeline therefore relies on the static report that resulted from this one-time audit, which is included as `data/reports/adb_validation_report.csv`. A status of `OK` is assigned only to validated `Person` entries. This static report ensures the subsequent filtering is fully deterministic.

**A Note on Validation Logic:** The script uses a multi-step validation process. A "name mismatch" is flagged if the similarity score between the ADB name and the Wikipedia page title falls below 90% after normalization. A death date is confirmed by searching for multiple positive signals (e.g., a "Died" field in an infobox) while checking for negative signals (e.g., the "Living people" category). The validation also requires a valid English Wikipedia page; this is a methodological control to ensure a consistent and high-quality baseline for the LLM's biographical knowledge, as its training data is predominantly English.

### Step 2: Filtering and Selection (`filter_adb_candidates.py`)

**A Note on Eminence Scores and Reproducibility:** The eminence scores used for filtering are stored in the static file `data/foundational_assets/eminence_scores.csv`. By treating the scores as a static input, the filtering process remains fully deterministic.

This step is automated by `src/filter_adb_candidates.py`. It takes the raw data, the validation report, and the eminence scores as input. It filters candidates based on a validation status of `OK`, a valid birth time, and a birth year between 1900-1999. It then ranks the remaining candidates by eminence score and selects the top 5,000. The output is `data/intermediate/adb_filtered_5000.txt`, a clean, sorted file ready for final formatting.

### Step 3: Formatting for Import (`prepare_sf_import.py`)

This final automated step, handled by `src/prepare_sf_import.py`, formats the 5,000 selected subjects for import into the Solar Fire astrology software. It reads the clean data from `adb_filtered_5000.txt`, transforms names and dates into the required format, and assembles a Comma Quote Delimited (CQD) record for each subject. The output is `data/intermediate/sf_data_import.txt`.

## Importing to and Exporting from Solar Fire

Once the data is prepared, we can start making the Solar Fire astrology software ready for the import. This commercial program is available at https://alabe.com/solarfireV9.html. Many good alternatives exist, but the data preparation, import, and export procedures will be different in each case. The main advantages of Solar Fire are as follows:

*   It is the industry standard astrology software for astrologers around the world.
*   It has a long history of development and is considered accurate and reliable.
*   Data import / chart export functionality is straightforward and seamless.
*   Its delineations library is fully exportable.
*   It is relatively inexpensive ($360 USD currently).

### Recommended Settings

Prior to importing the birth data, we need to prepare the grounds within Solar Fire so that the data can be processed accurately. There are two separate screens to deal with: Chart Options and Preferences.

#### Chart Options

*   **Menu access:** *Chart Options > Displayed Points...*

Define chart points:

*   **Displayed Points:** 

    *   Create a new *.pts file and save it with your preferred filename (e.g., `10_planets_2_angles.pts`).
    *   Edit this file to have the following chart points: 10 Planets from Moon to Pluto, plus Ascendant and Midheaven (12 points).
    *   Save and Select. The Current Settings table on top will display your filename with '(12 Points)' appended for 'Displayed Points'.

#### Preferences

*Menu access: Preferences > Edit Settings...*

Make sure these settings are in place:

*   **Atlas ('Places' tab):** 'ACS (Built-in)' (default).
*   **Astrologer's Assistant ('AutoRun' tab):** Click the 'Clear' button to remove the auto-running of any tasks. The 'Astrologer's Assistant task file to run on startup' field will be empty.
*   **MC in Polar Regions ('Calculations' tab):** 'Always above horizon' (default).
*   **Default Zodiac ('Zodiac' tab):** 'Tropical' (default).

### Importing Birth Data

*   **Menu access:** *Utilities > Chart Import/Export...*

Once chart options and preferences are adjusted, everything is set for a successful operation. Import the birth data as follows:

*   **'Import From' tab**: Select 'ASCII files' for 'Chart Type to Import From'. Navigate to and select your previously saved TXT file (e.g., `sf_data_import.txt`).
*   **'Save To' tab:**: Select 'Solar Charts' for 'Chart Type to Save Into'. Navigate to and select the folder Documents > Solar Fire > Charts. Type a filename for 'File Name to Save Into' (e.g., `famous_5000.cht`).
*   **'Options' tab:** 

    *   **New Solar fire Chart Files:** Select the 'Create current format chart files (v6 or higher)' default.
    *   **Default House System:** Select the 'Placidus' default (this setting is not used).
    *   **Default Zodiac:** Select the 'Tropical' default.
    *   **Default Coordinates:** Select the 'Geocentric' default.
    *   **ASCII Format to Use:** Click the 'Edit ASCII Formats...' button to open the 'ASCII Formet Definitions' dialog. Click the 'Create New Definition' button and change the name of the newly created definition to your preference (e.g., `CQD Import`). For 'Fields in each record', use the 'Up', 'Dn, '>', and '<' buttons and items under 'Available fields' to make sure the following 9 fields are showing:

        *   Name/Description
        *   Date (String)
        *   Time (String)
        *   Zone Abbreviation
        *   Zone Time (String)
        *   Place Name
        *   Country/State Name
        *   Latitude (String)
        *   Longitude (String)

        Select 'Comma Quote Delimited' for 'Record Format' and leave the defaults under Conversion Options and Flags' (boxes unchecked and 'W', 'N', and 'PM' for the flags). Click the 'Save' button to get back to the previous dialog. Make sure your new CQD format is selected for 'ASCII Format to Use'.

        Click the 'Convert' button once everything above is done. Solar Fire will import your data file into the specified charts file (e.g., `famous_5000.cht`).

### Opening Charts

*   **Menu access:** *Chart > Open...*

Now we need to open all the charts so they can be exported. In the Chart Database dialog, click the arrow next to the 'File' button and select your charts file. If now shown on the list, select 'Other files...' and pick the file from the File Management dialog and click 'Select'. The total number of charts (5000) in the charts file and number of currently selected charts (1) within the file are shown on top. Do not change the sorting of the chart list.

Click the 'All' button: all charts will be highlighted (selected) and '5000' will be shown in the 'Selected' field on top. Click the 'Open...' button: all 5000 charts will be calculated and opened one by one and shown on the list of Calculated Charts (note: this could take 20 minutes or more).

### Exporting Astrological Data

*   **Menu access:** *Chart > Export Charts as Text...*

Once all 5000 charts are calculated and added to the list of Calculated Charts, press the Home key to select the first chart. Shift-press the End key to scroll down to select all charts on the list.

Open the 'Export Chart Data' dialog by invoking the 'Chart > Export Charts as Text...' menu item. Check the 'Chart Details' and 'Column Types' boxes, then click the 'Edit ASCII...' button to open the 'ASCII Formet Definitions' dialog. This window is identical to the one encountered during the import process with one important difference: the list of Definitions is specific to the export workflow. Just as for the import, go through the creation of a CQD format and ensure the exact same 9 fields are specified. Name the newly created definition to your preference (e.g., `CQD Export`) and click the 'Save' button to get back to the previous dialog. 

Select 'Chart Points' (first item) under 'Select types of points:-' if not already selected. Make sure your new CQD format is selected under the 'Edit ASCII...' button. Select 'Comma Quote (CQD)' for 'Field Delimiters' and 'Export to File' for 'Destination'. Click the 'Browse' button, navigate to the `data/foundational_assets` folder, name the export file `sf_chart_export.csv`, and click the 'Save' button to get back to the main dialog. Click the 'Export' button to export the chart data to the file. Wait until the program exports all files, then dismiss the 'Export completed successfully' message and click the 'Quit' button in the main dialog.

The format of the exported file is as follows:

```
"<First_name Last_name>","<D MMMM YYYY>","<H:MM>","<Zone_Abbreviation>","<±H:MM>","<Place>","<State>","<DDvMM>","<DDDhMM>"
"Body Name","Body Abbr","Longitude"
"Moon","Mon",<Moon_Longitude>
"Sun","Sun",<Sun_Longitude>
"Mercury","Mer",<Mercury_Longitude>
"Venus","Ven",<Venus_Longitude>
"Mars","Mar",<Mars_Longitude>
"Jupiter","Jup",<Jupiter_Longitude>
"Saturn","Sat",<Saturn_Longitude>
"Uranus","Ura",<Uranus_Longitude>
"Neptune","Nep",<Neptune_Longitude>
"Pluto","Plu",<Pluto_Longitude>
"Ascendant","Asc",<Ascendant_Longitude>
"Midheaven","MC",<Midheaven_Longitude>
<14_lines_above_repeating_for_each_person>
```

Each 14-line block contains the following for one person:

*   **Line 1:** Name, date of birth, time of birth, time zone abbreviation, time zone UTC offset, place, state, latitude with vertical (N/S) direction, longitude with horizontal (E/W) direction.
*   **Line 2:** Header for the remaining lines.
*   **Lines 3-14:** Chart point's name, point's abbreviation, point's zodiacal longitude (0.00-359.99 degrees)

The entire file consists of 5000 * 14 = 7000 lines.

### Exporting the Delineations Library

*   **Menu access:** *Interps > Interpretation Files > Natal*

Note: In Solar Fire, the cookbook-style delineation components are called "decompiled interpretations". Since the term 'interpretation' is typically considered a broader term that includes the synthesis of individual delineation components (such as the ones in this library) to arrive at a holistic view, we prefer the term "delineation" for the components we are dealing with here.

In addition to astrological data for the database of 5000 famous people, we also need to export the delineations library so that these two pieces can be connected to form a complete personality description for every individual. To export the standard natal delineations library from Solar Fire, follow these steps:

*   Open the File Management dialog for interpretations files by selecting the Interps > Interpretation Files > Natal menu item.
*   Select 'Standard.int' on the list of natal interpretation files.
*   Click the 'Edit' button.
*   In the 'Interpretations Editor' dialog, select the File > Decompile... menu item, then click the 'Save' button. The file will be saved as `standard.def` in Documents > Solar Fire User Files > Interpretations.
*   Close the 'Interpretations Editor' window to return to the main dialog.
*   Click the 'Cancel' button to close the File Management dialog.
*   Navigate to the definition file in File Explorer open it in a text editor.
*   Save the file as a TXT file in the `data/foundational_assets` folder as `sf_delineations_library.txt`.

The full library contains a header block followed by delineation components by category. The categories are listed at the start of the header block:

```
;
; Decompiled Interpretations
; <directory_path>\standard.int
; Time: <YYYY-MM-DD HH:MM:SS>
; SUMMARY OF ITEMS INCLUDED

; Title Interpretations - Included below
; Copyright Interpretations - Included below
; Introduction Interpretations - Included below
; Degree Interpretations - Included below
; Decanate Interpretations - NOT INCLUDED IN THIS SET
; Quadrant Interpretations - Included below
; Hemisphere Interpretations - Included below
; Element Interpretations - Included below
; Mode Interpretations - Included below
; Ray Interpretations - Included below
; Aspect Interpretations - Included below
; Lunar Phase Interpretations - Included below
; House Interpretations - Included below
; Sign Interpretations - Included below
; Point Interpretations - Included below
; Point in House Interpretations - Included below
; Point in Sign Interpretations - Included below
; Sign on House Cusp Interpretations - Included below
; Point in Aspect to Point Interpretations - Included below
; Midpoint Interpretations - NOT INCLUDED IN THIS SET
; Point on Midpoint Interpretations - NOT INCLUDED IN THIS SET
; Midpoint on Point Interpretations - NOT INCLUDED IN THIS SET

*Title
Standard Natal Interpretations

```

This is followed by a copyright block and an introductory block, after which the various delination blocks follow in the order above. For our purposes, only the following categories hold interest:

*   **Sign Interpretations:** An example of a 'strong' sign is given below.
    ```
    *Aries Strong
    Initiating, pioneering energy. Independent, bold, courageous, assertive, fiery, inspirational, direct, decisive. Can be egotistical, impulsive, impatient, aggressive, lacking subtlety.
    ```
*   **Element Interpretations:** An example of a 'weak' and 'strong' element is given below.
    ```
    *Element Fire Weak
    You have difficulty getting yourself motivated to achieve your own goals. In fact at times you may lack the self-confidence to even set personal goals. You may experience a general lack of enthusiasm, feeling overwhelmed by change.

    *Element Fire Strong
    You are a highly-motivated person with many goals and aspirations for the future. You are vital and spontaneous, often enjoying the challenge of travelling down new and adventurous roads in your life. Your enthusiasm is irrepressible. Your weakness lies in your tendency to exaggerate and your inability to cope with the more mundane activities in life.
    ```
*   **Mode Interpretations:** An example of a 'weak' and 'strong' mode (quality) is given below.
    ```
    *Mode Cardinal Weak
    You prefer to follow in other people's footsteps rather than initiate actions. You can be relied on to come up with the goods as long as someone else has the initial ideas. Your survival mechanisms are weak.

    *Mode Cardinal Strong
    You enjoy challenge and action, and become frustrated when you have no recourse for change. You expect others to also rise to a challenge.
    ```
*   **Quadrant Interpretations:** An example of a 'strong' quadrant is given below.
    ```
    *Quadrant 1 Strong
    You see yourself as an independent individual, capable of organising your own life. You could be self-centred. The planets in this quadrant will highlight the areas of life in which you want to express yourself.
    ```
*   **Hemisphere Interpretations:** An example of a 'strong' hemisphere is given below.
    ```
    *Hemisphere Eastern Strong
    You are a self-motivated and self-oriented individual. You like to map out your own life and follow your own path, experiencing difficulties only if anyone stands in your way. You value your independence and enjoy your own company. You enjoy the company of other people, but only if they give you plenty of freedom for your own pursuits. You need to watch out for egocentric and selfish behaviour.
    ```
*   **Point in Sign Interpretations:** An example of a 'chart point in sign' is given below.
    ```
    *Moon in Aries
    You have an emotional need for action and independence. Under stress you will seek a challenge and time on your own, away from other people. You may have experienced your mother as independent and possibly impatient. As an adult you are a go-getter.
    ```

Note: Solar Fire uses the term "mode" for what is typically referred to as the "quality" of signs (i.e., cardinal, fixed, or mutable signs).

## Creating the Personalities Database

The final stage of the pipeline assembles the `personalities_db.txt` file. The process involves three conceptual tasks, all of which are automated by the `generate_personalities_db.py` script using the clean `data/processed/subject_db.csv` as its main input.

The following subsections describe the methodology that the script automates.

### Creating Divisional Classifications

#### Zodiac Categories and Divisions
The zodiac categories and their constituent divisions are defined by longitude ranges as follows:

*   **Signs** are 30-degree segments starting at 0 degrees tropical longitude: Aries, Taurus, Gemini, etc.
*   **Elements** are sets of three 30-degree segments (tropical signs) distributed evenly along the zodiac. Starting at 0 degrees longitude, they follow in this order, repeating after each 120-degree segment: Fire, Earth, Air, Water.
*   **Modes** are sets of four 30-degree segments (tropical signs) distributed evenly along the zodiac. Starting at 0 degrees longitude, they follow in this order, repeating after each 90-degree segment: Cardinal, Fixed, Mutable.
*   **Quadrants** are 90-degree segments starting at 0 degrees tropical longitude and numbered from 1 to 4.
*   **Hemispheres** are 180-degree segments starting at 0 degrees tropical longitude for vertical (North/South) divisions and at 90 degrees tropical longitude for horizontal (East/Wwest) divisions.
*   **Points in Signs** are the 144 combinations of 12 chart points and 12 tropical signs.

The process of classifying divisions in the first five categories above follows Solar Fire's algorithm for assembling the "Balances Report". 

#### The Solar Fire "Balances Report"

*   **Menu access for weights:** *Utilities > Edit Rulers/Weightings > Weighting Scores*
*   **Menu access for weak and strong ratios:** *Interps > Interpretation Files > Natal... [select nterpretation file] > Edit > Edit > Scoring of Balances... [select Balance Type]*

Note: All functionality and procedures described in this document, including the calculation of chart point balances (planetary dominance), form part of the Testing Framework. Modifying settings for the Balances Report in Solar Fire is optional but highly recommended since it may well serve as an external validation tool.

We utilize the default weighting system for the calculation of Solar Fire's balances (planetary dominance) with one key modification. Based on exploratory trials, the weights for the generational planets (Uranus, Neptune, and Pluto) are set to zero to isolate more individualized factors. The specific "weight-points" assigned under 'Weighting Scores' are as follows:

*   **3 points:** Sun, Moon, Ascendant, Midheaven
*   **2 points:** Mercury, Venus, Mars
*   **1 point:** Jupiter, Saturn
*   **0 points:** Uranus, Neptune, Pluto

Dominance within each astrological division (i.e., signs, elements, modes, quadrants, and hemispheres) is automatically determined by the program through a multi-step calculation:

1.  A "total score" (`TS`) is calculated for each division (e.g., the element 'fire', the mode 'cardinal') by summing the "weight-points" of all chart points located within it.
2.  An "average score" (`AS`) is then determined for the category by averaging the `TS` values across all its constituent divisions.
3.  Two thresholds are established using this AS and predefined ratios: a "weak threshold" (`WT`) calculated with a "weak ratio" (`WR`), and a "strong threshold" (`ST`) calculated with a "strong ratio" (``SR`):
    *   `WT = AS * WR`
    *   `ST = AS * SR`
4.  The default `WR` values are as follows: Quadrants 0, Hemispheres 0, Elements 0.5, Modes 0.5, Signs 0. The default `SR` values are as follows: Quadrants 1.5, Hemispheres 1.4, Elements 1.5, Modes 1.5, Signs 2.
5.  A division is classified as 'weak' if its `TS` was below the `WT`, or 'strong' if its `TS` was greater than or equal to the `ST`. If `TS` is in-between the two thresholds, it is considered 'neutral' and the corresponding division is not mentioned in delineations.
6. Other than being 'neutral', elements and modes can be classified either 'weak' or 'strong'. Signs, quadrants, and hemispheres on the other hand can only ever be 'strong' (i.e., they are 'neutral' when not 'strong'). This is because the default `WR`values are 0 (zero) for these latter categories, resulting in the same for `WT` values.

Using the above settings, the resulting WT and ST values (rounded up to the nearest integer) are as follows:

*   **Quadrants:** WT 0, ST 6.
*   **Hemispheres:** WT 0, ST 10.
*   **Elements:** WT 3, ST 8.
*   **Modes:** WT 4, ST 10.
*   **Signs:** WT 0, ST 4.

The interpretive output of this process is the resulting list of 'strong' and 'weak' classifications for each division, which is then used by Solar Fire for report assembly. The `generate_personalities_db.py` script reimplements this entire classification logic.

#### Divisional Classification Procedure

The method for determining the divisional classifications is as follows:

*   Determine which tropical sign each chart point falls into.
*   Add up all the points for each sign.
*   Classify each sign according to the criteria given for the "balances report" above.
*   Add up all the points for each division in each category based on the fixed mapping between signs and categories.
*   Classify each division in each category according to the criteria given for the "balances report" above.

For example, John F. Kennedy had the following chart placements:

*   Moon in Virgo, Sun in Gemini, Mercury in Taurus, Venus in Gemini, Mars in Taurus, Jupiter in Taurus, Saturn in Cancer, Uranus in Aquarius, Neptune in Leo, Pluto in Cancer, Ascendant in Libra, Midheaven in Cancer.
*   This translates into the following points in the regular order of **signs** (Aries to Pisces): 0, 5, 5, 4, 0, 3, 3, 0, 0, 0, 0, 0 (Total 20).
*   Distribution of **elements**: Fire 0, Earth 8, Air 8, Water 4 (Total 20).
*   Distribution of **modes**: Cardinal 7, Fixed 5, Mutable 8 (Total 20).
*   Distribution of **quadrants**: Ascendant and Midheaven are not counted, making Cancer 1 and Libra 0. Points: 0, 0, 10, 4 (Total 14).
*   Distribution of **hemispheres**: Ascendant and Midheaven are not counted, making Cancer 1 and Libra 0. Points: Eastern 4, Western 10, Northern 0, Southern 14 (Total 28 due to overlap of hemispheres).

The point disctributions result in the following classifications:

*   **Signs:** 
    *   Strong: Taurus, Gemini, Cancer.
*   **Elements:** 
    *   Weak: Fire.
    *   Strong: Earth, Air.
*   **Modes:** Balanced (no mode can be identified as 'weak' or 'strong').
*   **Quadrants:** 
    *   Strong: Quadrant 3.
*   **Hemispheres:** 
    *   Strong: Western, Southern.

### Neutralizing the Library

Use an LLM to remove all astrological, gender, and chronological references from the raw Solar Fire delineations library ("decompiled interpretations"). For example, one could use the following prompt:

"Revise the attached text as follows: remove references to astrology and astronomy; shift from second-person langauge to an impersonal, objective, neutral style without referring to specific people, generations or time periods; and correct for grammar and spelling (US English). Preserve original meaning as much as possible while making these revisions."

If this is done for several components at the same time, you will need to have the LLM preserve division identifiers that will facilitate the lookup functionality described in the next section. For example, if you are using the original Solar Fire format, you might lead with this wording:

"Revise the attached text *with the exception of lines marked with an asterisk, which need to remain intact:*"

Save the LLM's output in six separate files as follows:

*   Sign Interpretations: `balances_signs.csv`
*   Element Interpretations: `balances_elements.csv`
*   Mode Interpretations: `balances_modes.csv`
*   Quadrant Interpretations: `balances_quadrants.csv`
*   Hemisphere Interpretations: `balances_hemispheres.csv`
*   Point in Sign Interpretations: `points_in_signs.csv`

### Compiling the Database

Once the above information is available, compiling the final personalities database becomes a simple lookup and assembly procedure. For example, given the following delineation components for John F. Kennedy:

*   **Taurus Strong:** "Stable and enduring, strong values, unyielding, earthy, acquisitive, strong desires. Can be stuck, stubborn, overly possessive, self-indulgent."
*   **Gemini Strong:** "Agile, versatile, inquisitive, flowing, conversational, airy, many ideas. Can be volatile, superficial, changeable, restless and inconsistent."

The beginning of the personality description becomes: "Stable and enduring, strong values, unyielding, earthy, acquisitive, strong desires. Can be stuck, stubborn, overly possessive, self-indulgent. Agile, versatile, inquisitive, flowing, conversational, airy, many ideas. Can be volatile, superficial, changeable, restless and inconsistent."

This continues with the rest of the delineation components corresponding to weak and strong divisions for the person in question. This entire lookup and assembly process is performed automatically by the `generate_personalities_db.py` script.

The final `personalities_db.txt` is a tab-delimited file containig the following fields: Index, Name, BirthYear, and DescriptionText. For example:

```
1	John F. Kennedy	1917	Stable and enduring, defined by strong values and an unyielding, earthy nature with acquisitive tendencies and powerful desires. At times, may be perceived as rigid, stubborn, overly possessive, or self-indulgent. Agile, versatile, and inquisitive, characterized by a fluid and conversational style with many ideas. Can exhibit volatility, superficiality, inconsistency, and restlessness. Nurturing, protective, and tenacious, with pronounced emotional sensitivity and deeply rooted foundations. At times, may be overly protective, reluctant to let go, timid, or reclusive. Experiences difficulty becoming motivated to achieve personal goals. At times, self-confidence is insufficient even to set these goals, and a general lack of enthusiasm coupled with feeling overwhelmed by change is common. Exhibits a practical and efficient, hands-on approach with a dependable common-sense method applied to most matters. A down-to-earth demeanor proves advantageous for daily tasks, though a stubborn reluctance to embrace change can sometimes stifle both personal and others’ enthusiasm. Displays objectivity and philosophical insight, favoring an intellectual perspective in approaching life. The rational mind consistently outweighs emotional considerations, which are viewed as less reliable. Possesses a strong sense of fairness and logical thought, though there is a tendency to consider emotions in a disparaging light. Seeks relationships from an objective standpoint rather than a personal one and values public engagement alongside contributing to society. Interactions with others assume a paramount role, with significant value placed on both personal relationships and broader social connections. Possesses a natural aptitude for mediation, informed by an understanding of the nuances inherent in relationships. The greatest insights into personal identity are often gained through these relational contexts. Care should be taken to avoid becoming entangled in stifling relationships. Public life is regarded as the pinnacle of achievement, with personal satisfaction derived from notable accomplishments and ongoing contributions in the public arena. A high public profile may be attained through career success and social status, though it is essential that such accomplishments do not come at the expense of personal relationships. Reveals a strong connection between emotion and physical well-being coupled with a desire for perfection and order. Under stress, occasional health challenges may emerge. Exhibits curiosity, adaptability, and a versatile nature, maintaining high levels of engagement through lively communication and multiple interests. Often infuses situations with dynamic energy—even if this occasionally leads to disorganization. Values traditional knowledge and adopts a methodical, hands-on approach to learning. Prefers established ideas, approaching new information with caution. Values intellectual stimulation and engaging, flirtatious exchanges in relationships. Communication is essential, though a restless nature may drive frequent shifts in interest. Pursues personal desires with determination and methodical persistence. Follows a reliable course of action and can exhibit stubbornness when challenged. Pursues truth persistently while demonstrating loyalty and wisdom. Exhibits a robust desire for both material and experiential abundance. May tend toward emotional inhibition and shyness while still committing seriously to personal and familial responsibilities. Encourages brilliant, inventive breakthroughs that contribute unique insights to collective progress. Infuses creativity with spirituality, manifesting dramatic artistic expression and an appreciation for aesthetics. Represents the upheaval and reformation of familiar systems, prompting new social concepts and security structures. A courteous and thoughtful approach to life is combined with a strong focus on interpersonal relationships. Fairness, justice, and the cultivation of harmonious connections—whether personal or professional—play a central role in defining purpose. A career providing emotional security and opportunities to care for others is central, with strong feelings about public stature and a need for a nurturing work environment.
```

The rest of the Testing Framework is fully automated in Python, as documented herein.

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