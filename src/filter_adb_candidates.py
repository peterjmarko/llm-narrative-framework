#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: src/filter_adb_candidates.py

"""
Filter raw ADB data and select the top 5,000 candidates.

This script performs a two-stage filtering of the raw data export from
Astro-Databank (ADB) to produce a final, curated list of 5,000 subjects.
It serves as the primary data reduction step before the data is formatted
for Solar Fire import by the next script in the pipeline.

Stage 1: Initial Filtering
  - Reads the raw ADB export (~10,000 entries), validation report, and
    eminence scores.
  - Filters entries based on:
    1. Validation status of 'OK'.
    2. Birth year between 1900-1999, inclusive.
    3. Presence of a validly formatted birth time.
    4. Uniqueness (deduplicated by name and birth date).

Stage 2: Eminence-Based Selection
  - Sorts the viable candidates by their eminence score (descending), with
    ARN as a tie-breaker.
  - Selects the top 5,000 subjects.

Output:
  - Creates `data/intermediate/adb_filtered_5000.txt`, a clean,
    tab-delimited file with a header. This file contains all the necessary,
    un-transformed data fields for the next pipeline step.
"""

import argparse
import csv
import logging
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

class BColors:
    """A helper class for terminal colors."""
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    ENDC = '\033[0m'

def normalize_name_for_matching(name_str: str) -> str:
    """
    Normalizes a name string into a consistent key for matching.
    It handles 'Last, First' format, lowercases, and removes non-alphanumerics.
    e.g., "Kennedy, John F." -> "johnfkennedy"
    """
    # Reorder if "Last, First"
    if ',' in name_str:
        parts = name_str.split(',', 1)
        name_str = f"{parts[1].strip()} {parts[0].strip()}"
    # Lowercase and remove all non-alphanumeric characters
    return re.sub(r'[^a-z0-9]', '', name_str.lower())

def normalize_name_for_deduplication(raw_name: str) -> tuple:
    """
    Normalizes a name for robust duplicate detection.
    It strips parenthetical content and sorts name parts alphabetically.
    """
    # Remove anything in parentheses (including the URL)
    name = re.sub(r'\(.*\)', '', raw_name).strip()
    
    # Split into parts, handling both comma and space delimiters
    parts = re.split(r'[,\s-]+', name)
    
    # Filter out empty strings, convert to lowercase, and sort
    normalized_parts = sorted([part.lower() for part in parts if part])
    
    return tuple(normalized_parts)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(levelname)s: %(message)s')

def load_valid_ids(filepath: str) -> set:
    """
    Loads the validation report and returns a set of idADBs for entries that
    are validated with a status of 'OK'.
    """
    valid_ids = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if (row.get('Status') == 'OK' and row.get('idADB')):
                    valid_ids.add(row['idADB'])
        logging.info(f"Loaded {len(valid_ids):,} valid idADBs (Status='OK') from the validation report.")
        return valid_ids
    except FileNotFoundError:
        logging.error(f"Validation report file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading validation report file {filepath}: {e}")
        sys.exit(1)

def load_country_codes(filepath: str) -> dict:
    """Loads country code mappings from a CSV file."""
    country_map = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                country_map[row['Abbreviation']] = row['Country']
        logging.info(f"Loaded {len(country_map)} country code mappings.")
        return country_map
    except FileNotFoundError:
        logging.error(f"Country codes file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading country codes file {filepath}: {e}")
        sys.exit(1)

def load_eminence_scores(filepath: str) -> dict:
    """
    (Temporary) Loads eminence_scores.csv into a dictionary keyed by a
    normalized version of the person's name.
    """
    eminence_data = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Use a normalized name as the key for matching
                name = row.get('Name')
                score_str = row.get('EminenceScore')
                if not name or not score_str:
                    continue
                try:
                    normalized_name = normalize_name_for_matching(name)
                    eminence_data[normalized_name] = float(score_str)
                except ValueError:
                    logging.warning(f"Invalid eminence score for {name}: '{score_str}'. Skipping.")
        logging.info(f"Loaded {len(eminence_data):,} eminence scores, keyed by normalized name.")
        return eminence_data
    except FileNotFoundError:
        logging.error(f"Eminence scores file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading eminence scores file {filepath}: {e}")
        sys.exit(1)

def main():
    """Main function to orchestrate the filtering process."""
    parser = argparse.ArgumentParser(
        description="Filter raw ADB export to 5,000 candidates based on multiple criteria.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-i", "--input-file", default="data/sources/adb_raw_export.txt", help="Path to the raw, tab-delimited file exported from ADB.")
    parser.add_argument("-o", "--output-file", default="data/intermediate/adb_filtered_5000.txt", help="Path for the final 5,000-entry output file.")
    parser.add_argument("--validation-report-file", default="data/reports/adb_validation_report.csv", help="Path to the ADB validation report CSV file.")
    parser.add_argument("--eminence-file", default="data/foundational_assets/eminence_scores.csv", help="Path to the eminence scores CSV file.")
    parser.add_argument("--country-codes-file", default="data/foundational_assets/country_codes.csv", help="Path to the country code mapping CSV file.")
    parser.add_argument("--missing-eminence-log", default="data/reports/missing_eminence_scores.txt", help="Path to log ARNs of candidates missing an eminence score.")
    args = parser.parse_args()

    output_path = Path(args.output_file)
    if output_path.exists():
        print("")
        print(f"{BColors.YELLOW}WARNING: The output file '{output_path}' already exists and will be overwritten.{BColors.ENDC}")
        confirm = input("Are you sure you want to continue? (Y/N): ").lower()
        if confirm != 'y':
            print("\nOperation cancelled by user.\n")
            sys.exit(0)
        
        # Create a timestamped backup before proceeding
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
            shutil.copy2(output_path, backup_path)
            logging.info(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup file: {e}")
            sys.exit(1)

    print("")
    print(f"{BColors.YELLOW}--- Starting Candidate Filtering ---{BColors.ENDC}")

    try:
        with open(args.input_file, 'r', encoding='utf-8') as infile:
            lines = infile.readlines()
            # Count unique candidates based on ARN in the first column
            candidate_arns = set()
            for line in lines:
                if '\t' in line:
                    parts = line.strip().split('\t')
                    if parts and parts[0].strip().isdigit():
                        candidate_arns.add(parts[0].strip())
            logging.info(f"Loaded {len(candidate_arns):,} records from raw ADB export file.")
    except FileNotFoundError:
        import os
        abs_path = os.path.abspath(args.input_file)
        logging.error(f"Raw input file not found. The script looked for it at: {abs_path}")
        sys.exit(1)

    valid_ids = load_valid_ids(args.validation_report_file)
    eminence_scores = load_eminence_scores(args.eminence_file)
    country_map = load_country_codes(args.country_codes_file)

    # --- Stage 1: Initial Filtering ---
    print("")
    print(f"{BColors.YELLOW}--- Stage 1: Initial Filtering ---{BColors.ENDC}")
    
    stage1_candidates = []
    processed_identifiers = set()
    removed_duplicates_info = []
    
    for line in lines:
        if '\t' not in line:
            continue
        
        parts = line.strip().split('\t')
        # The new fetched format has 19 columns. Skip header or malformed lines.
        if len(parts) < 19 or not parts[0].strip().isdigit():
            continue

        # Extract data fields from the new format (0-indexed):
        # 1:idADB, 2:LName, 3:FName, 7:Year, 8:Time
        id_adb, last_name, first_name, year, birth_time = parts[1], parts[2], parts[3], parts[7], parts[8]

        # Reconstruct name and date for deduplication and filtering
        raw_name_for_dedup = f"{last_name}, {first_name}"
        date_str = f"{parts[7]}-{parts[6]}-{parts[5]}" # YYYY-MM-DD
        unique_identifier = (normalize_name_for_deduplication(raw_name_for_dedup), date_str)

        if unique_identifier in processed_identifiers:
            name_for_log = re.sub(r'\(.*\)', '', raw_name_for_dedup).strip()
            removed_duplicates_info.append(f"  - idADB {id_adb}: {name_for_log}")
            continue
        
        if id_adb not in valid_ids:
            continue
        
        if not re.match(r"^\d{1,2}:\d{2}$", birth_time):
            continue

        try:
            birth_year = int(year)
            if not (1900 <= birth_year <= 1999):
                continue
        except (ValueError, IndexError):
            continue
        
        # Store the original parts from the new format
        stage1_candidates.append(parts)
        processed_identifiers.add(unique_identifier)

    if removed_duplicates_info:
        logging.info(f"Dropped {len(removed_duplicates_info):,} duplicate entries:")
        for info in removed_duplicates_info:
            logging.info(info)

    logging.info(f"Stage 1 complete. Found {len(stage1_candidates):,} unique candidates.")

    # --- Stage 2: Eminence-Based Selection ---
    print("")
    print(f"{BColors.YELLOW}--- Stage 2: Eminence-Based Selection ---{BColors.ENDC}")
    logging.info("Sorting candidates by eminence score...")
    
    candidates_with_scores = []
    missing_score_names = []
    for candidate_parts in stage1_candidates:
        # Construct and normalize the name for the lookup
        first_name = candidate_parts[3]
        last_name = candidate_parts[2]
        full_name = f"{first_name} {last_name}"
        normalized_name = normalize_name_for_matching(full_name)
        
        score = eminence_scores.get(normalized_name)
        if score is not None:
            candidates_with_scores.append((score, candidate_parts))
        else:
            missing_score_names.append(full_name.strip())

    if missing_score_names:
        log_path = Path(args.missing_eminence_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                for name in sorted(missing_score_names):
                    f.write(f"{name}\n")
            
            logging.warning(f"{len(missing_score_names):,} candidates were excluded for lacking an eminence score.")
            logging.warning(f"A list of their names has been saved to: {log_path}")
        except IOError as e:
            logging.error(f"Failed to write missing eminence scores log to {log_path}: {e}")

    # Sort by Eminence (desc), then by LastName (asc), then FirstName (asc) for a stable tie-breaker.
    candidates_with_scores.sort(key=lambda x: (-x[0], x[1][2], x[1][3]))
    
    final_candidates = candidates_with_scores[:5000]
    logging.info(f"Stage 2 complete. Selected top {len(final_candidates):,} candidates from the remaining list of {len(candidates_with_scores):,} subjects.")

    # --- Final Output Generation ---
    print("")
    print(f"{BColors.YELLOW}--- Finishing... ---{BColors.ENDC}")
    logging.info(f"Writing final output to {args.output_file}...")
    try:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            writer = csv.writer(outfile, delimiter='\t')
            # Write a clear header for the structured output file
            header = [
                "Index", "idADB", "LastName", "FirstName", "Gender", "Day", "Month",
                "Year", "Time", "ZoneAbbr", "ZoneTimeOffset", "City",
                "Country", "Longitude", "Latitude", "EminenceScore"
            ]
            writer.writerow(header)

            for i, (score, parts) in enumerate(final_candidates, start=1):
                # parts is a list of 19 strings from the raw export file.
                # Standardize the country name using the lookup map.
                raw_country_state = parts[12]
                country = country_map.get(raw_country_state, raw_country_state)

                # Select the raw data fields needed for the next pipeline step.
                output_row = [
                    i,          # Index (1-5000)
                    parts[1],   # idADB
                    parts[2],   # LastName
                    parts[3],   # FirstName
                    parts[4],   # Gender
                    parts[5],   # Day
                    parts[6],   # Month
                    parts[7],   # Year
                    parts[8],   # Time
                    parts[9],   # ZoneAbbr
                    parts[10],  # ZoneTimeOffset
                    parts[11],  # City
                    country,    # Standardized country name
                    parts[13],  # Longitude
                    parts[14],   # Latitude
                    f"{score:.2f}" # EminenceScore
                ]
                writer.writerow(output_row)
    except IOError as e:
        logging.error(f"Failed to write to output file {args.output_file}: {e}")
        sys.exit(1)
        
    print("")
    print(f"{BColors.GREEN}Filtering process complete. ✨\n{BColors.ENDC}")

if __name__ == "__main__":
    main()

# === End of src/filter_adb_candidates.py ===
