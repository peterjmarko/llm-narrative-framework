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
This script performs a two-stage filtering of the raw data export from
Astro-Databank (ADB) to produce a final, curated list of 5,000 subjects.

It serves as the first step in the data preparation pipeline, before the
data is converted for Solar Fire import.

Stage 1: Initial Filtering
  - Reads the raw ADB export (~10,000 entries).
  - Filters out entries based on several criteria:
    1. Must have a valid (non-empty) birth time.
    2. Must be born between 1900-1999, inclusive.
    3. Must have a status of 'OK' in the validation report
       (via `data/reports/adb_validation_report.csv`).
    4. A final on-the-fly check removes duplicates based on a normalized
       name and birth date.
  - This reduces the list to a pool of viable candidates.

Stage 2: Eminence-Based Selection
  - Sorts the viable candidates by their eminence score in descending order
    (using `eminence_scores.csv`), with a secondary sort by ARN for tie-breaking.
  - Selects the top 5,000 subjects.

Output:
  - A new file (`adb_filtered_5000.txt`) containing the final 5,000 subjects.
  - The original ADB Raw Number (ARN) is replaced with a new, clean sequence
    number from 1 to 5,000.
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

def normalize_name_for_deduplication(raw_name: str) -> str:
    """
    Normalizes a name for robust duplicate detection.
    It strips URL slugs and other parenthetical content before normalizing.
    e.g., "Desroches Noblecourt, Christiane" -> ('christiane', 'desroches', 'noblecourt')
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

def load_valid_arns(filepath: str) -> set:
    """
    Loads the validation report and returns a set of ARNs with 'OK' status.
    """
    valid_arns = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('Status') == 'OK' and row.get('ARN'):
                    valid_arns.add(row['ARN'])
        logging.info(f"Loaded {len(valid_arns):,} valid ARNs from the validation report.")
        return valid_arns
    except FileNotFoundError:
        logging.error(f"Validation report file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading validation report file {filepath}: {e}")
        sys.exit(1)

def load_eminence_scores(filepath: str) -> dict:
    """Loads the eminence_scores.csv file into a dictionary keyed by ARN."""
    eminence_data = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                arn = row.get('ARN')
                score_str = row.get('EminenceScore')
                if not arn or not score_str:
                    continue
                try:
                    eminence_data[arn] = float(score_str)
                except ValueError:
                    logging.warning(f"Invalid eminence score for ARN {arn}: '{score_str}'. Skipping.")
        logging.info(f"Loaded {len(eminence_data):,} eminence scores.")
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

    valid_arns = load_valid_arns(args.validation_report_file)
    eminence_scores = load_eminence_scores(args.eminence_file)

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
        # New fetched format has 13 columns
        if len(parts) < 13 or not parts[0].strip().isdigit():
            continue

        # Extract data fields from the new format
        arn, last_name, first_name, year, birth_time = parts[0], parts[2], parts[3], parts[7], parts[8]

        # Reconstruct name and date for deduplication and filtering
        raw_name_for_dedup = f"{last_name}, {first_name}"
        date_str = f"{parts[7]}-{parts[6]}-{parts[5]}" # YYYY-MM-DD
        unique_identifier = (normalize_name_for_deduplication(raw_name_for_dedup), date_str)

        if unique_identifier in processed_identifiers:
            name_for_log = re.sub(r'\(.*\)', '', raw_name_for_dedup).strip()
            removed_duplicates_info.append(f"  - ARN {arn}: {name_for_log}")
            continue
        
        if arn not in valid_arns:
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
    missing_score_arns = []
    for candidate_parts in stage1_candidates:
        arn = candidate_parts[0].strip()
        score = eminence_scores.get(arn)
        if score is not None:
            candidates_with_scores.append((score, candidate_parts))
        else:
            missing_score_arns.append(arn)

    if missing_score_arns:
        log_path = Path(args.missing_eminence_log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(log_path, 'w', encoding='utf-8') as f:
                for arn in sorted(missing_score_arns, key=int):
                    f.write(f"{arn}\n")
            
            logging.warning(f"{len(missing_score_arns):,} candidates were excluded for lacking an eminence score.")
            logging.warning(f"A list of their ARNs has been saved to: {log_path}")
        except IOError as e:
            logging.error(f"Failed to write missing eminence scores log to {log_path}: {e}")

    candidates_with_scores.sort(key=lambda x: (-x[0], int(x[1][0])))
    
    final_candidates = candidates_with_scores[:5000]
    logging.info(f"Stage 2 complete. Selected top {len(final_candidates):,} candidates from the remaining list of {len(candidates_with_scores):,} subjects.")

    # --- Final Output Generation ---
    print("")
    print(f"{BColors.YELLOW}--- Finishing... ---{BColors.ENDC}")
    logging.info(f"Writing final output to {args.output_file}...")
    try:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as outfile:
            for i, (score, parts) in enumerate(final_candidates, start=1):
                # parts: [ARN, ADBNo, LName, FName, G, D, M, Y, T, City, Country, Lon, Lat]
                name = f"{parts[2]}, {parts[3]}".replace("’", "'")
                # Reconstruct a line with a clean, structured set of fields for
                # downstream processing.
                output_content = [
                    name,
                    parts[4],  # Gender
                    f"{parts[7]}-{int(parts[6]):02d}-{int(parts[5]):02d}", # YYYY-MM-DD
                    parts[8],  # Time
                    "0",       # Placeholder for Timezone, not present in fetched data
                    parts[9],  # City
                    parts[10], # Country/State
                    parts[12], # Latitude
                    parts[11], # Longitude
                ]
                outfile.write(f"{i}\t" + "\t".join(output_content) + "\n")
    except IOError as e:
        logging.error(f"Failed to write to output file {args.output_file}: {e}")
        sys.exit(1)
        
    print("")
    print(f"{BColors.GREEN}Filtering process complete. ✨\n{BColors.ENDC}")

if __name__ == "__main__":
    main()

# === End of src/filter_adb_candidates.py ===
