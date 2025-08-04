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
    2. Must be confirmed on Wikipedia (via `filter_adb_raw.csv`).
    3. Must have a confirmed death date (via `filter_adb_raw.csv`).
    4. Must not be a known duplicate (via `filter_adb_raw.csv`).
  - This reduces the list to ~6,200 candidates.

Stage 2: Eminence-Based Selection
  - Sorts the ~6,200 candidates by their eminence score in descending order
    (using `eminence_scores.csv`).
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
from urllib.parse import unquote

def normalize_name_for_deduplication(raw_name: str) -> str:
    """
    Normalizes a name for robust duplicate detection.
    
    Converts "Last, First Middle" into a sorted tuple of lowercase name parts.
    e.g., "Desroches Noblecourt, Christiane" -> ('christiane', 'desroches', 'noblecourt')
    """
    # Remove anything in parentheses
    name = re.sub(r'\(.*\)', '', raw_name).strip()
    
    # Split into parts, handling both comma and space delimiters
    parts = re.split(r'[,\s-]+', name)
    
    # Filter out empty strings, convert to lowercase, and sort
    normalized_parts = sorted([part.lower() for part in parts if part])
    
    return tuple(normalized_parts)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def load_master_filter(filepath: str) -> dict:
    """Loads the filter_adb_raw.csv file into a dictionary keyed by ARN."""
    filter_data = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                arn = row.get('ARN')
                if not arn:
                    continue
                filter_data[arn] = {
                    'WikiConfirmed': (row.get('WikiConfirmed') or 'FALSE').upper() == 'TRUE',
                    'DeathDateConfirmed': (row.get('DeathDateConfirmed') or 'FALSE').upper() == 'TRUE',
                    'IsDuplicate': (row.get('IsDuplicate') or 'FALSE').upper() == 'TRUE',
                }
        logging.info(f"Loaded {len(filter_data)} records from master filter file.")
        return filter_data
    except FileNotFoundError:
        logging.error(f"Master filter file not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading master filter file {filepath}: {e}")
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
        logging.info(f"Loaded {len(eminence_data)} records from eminence scores file.")
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
    parser.add_argument("-o", "--output-file", default="data/adb_filtered_5000.txt", help="Path for the final 5,000-entry output file.")
    parser.add_argument("--filter-file", default="data/filter_adb_raw.csv", help="Path to the master filter CSV file.")
    parser.add_argument("--eminence-file", default="data/eminence_scores.csv", help="Path to the eminence scores CSV file.")
    args = parser.parse_args()

    # Load lookup files
    master_filter = load_master_filter(args.filter_file)
    eminence_scores = load_eminence_scores(args.eminence_file)

    # --- Stage 1: Initial Filtering ---
    stage1_candidates = []
    processed_identifiers = set() # Set to track processed individuals for deduplication
    logging.info(f"Starting Stage 1: Reading and filtering raw data from {args.input_file}...")
    try:
        with open(args.input_file, 'r', encoding='utf-8') as infile:
            next(infile)  # Skip the header row
            for line in infile:
                # Decode URL-encoded characters (e.g., %22 for ") from the raw line
                decoded_line = unquote(line)
                parts = decoded_line.strip().split('\t')
                if len(parts) < 5:
                    continue

                arn = parts[0].strip()
                raw_name = parts[1].strip()
                date_str = parts[3].strip()
                birth_time = parts[4].strip()

                # --- New Duplicate Check ---
                # Create a unique identifier based on normalized name and birth date
                normalized_name = normalize_name_for_deduplication(raw_name)
                unique_identifier = (normalized_name, date_str)
                
                if unique_identifier in processed_identifiers:
                    logging.info(f"Found and skipped duplicate entry for: {raw_name} on {date_str}")
                    continue
                processed_identifiers.add(unique_identifier)
                # --- End of Duplicate Check ---

                # Criterion 1: Birth Time must be a valid HH:MM format
                if not re.match(r"^\d{1,2}:\d{2}$", birth_time):
                    continue

                # Criterion 2: Birth Year must be 1999 or earlier
                try:
                    birth_year = int(date_str.split('-')[0])
                    if birth_year > 1999:
                        continue
                except (ValueError, IndexError):
                    logging.warning(f"Could not parse birth year for ARN {arn}: '{date_str}'. Skipping.")
                    continue

                # Criterion 3: Must pass master filter checks
                filter_conditions = master_filter.get(arn)
                if not filter_conditions:
                    continue # Skip if ARN not in our filter file

                if (filter_conditions['WikiConfirmed'] and
                    filter_conditions['DeathDateConfirmed'] and
                    not filter_conditions['IsDuplicate']):
                    stage1_candidates.append(parts)

    except FileNotFoundError:
        import os
        abs_path = os.path.abspath(args.input_file)
        logging.error(f"Raw input file not found. The script looked for it at: {abs_path}")
        sys.exit(1)

    logging.info(f"Stage 1 complete. Found {len(stage1_candidates)} candidates.")
    if len(stage1_candidates) < 5000:
        logging.error("Fewer than 5000 candidates passed Stage 1 filtering. Cannot proceed.")
        sys.exit(1)

    # --- Stage 2: Eminence-Based Selection ---
    logging.info("Starting Stage 2: Sorting candidates by eminence score...")
    
    # Pair candidates with their scores for sorting
    candidates_with_scores = []
    for candidate_parts in stage1_candidates:
        arn = candidate_parts[0].strip()
        score = eminence_scores.get(arn)
        if score is not None:
            candidates_with_scores.append((score, candidate_parts))
        else:
            logging.warning(f"ARN {arn} passed Stage 1 but has no eminence score. It will be excluded.")
            
    # Sort by score (descending), then by ARN (ascending) for a stable tie-break.
    # We sort on the negative of the score to achieve descending order for the primary key.
    # The ARN (parts[0]) is converted to an integer for correct numerical sorting.
    candidates_with_scores.sort(key=lambda x: (-x[0], int(x[1][0])))
    
    top_5000 = candidates_with_scores[:5000]
    logging.info(f"Stage 2 complete. Selected top {len(top_5000)} candidates.")

    # --- Final Output Generation ---
    logging.info(f"Writing final output to {args.output_file}...")
    try:
        with open(args.output_file, 'w', encoding='utf-8') as outfile:
            for i, (score, parts) in enumerate(top_5000, start=1):
                # --- Clean ONLY the cosmetic Name and Links fields ---
                
                # Clean Name field (column at index 1)
                if len(parts) > 1:
                    # Clean name, normalize whitespace, and fix smart quotes.
                    cleaned_name = parts[1].split('(')[0].strip()
                    normalized_name = ' '.join(cleaned_name.split())
                    parts[1] = normalized_name.replace("’", "'")

                # Clean Links field (the last column)
                if len(parts) > 6: # Ensure the Links field exists
                    parts[-1] = parts[-1].split('(')[0].strip()

                # Join the original line parts (now with cleaned Name/Links) from the Name field onwards
                original_content_cleaned = "\t".join(parts[1:])
                # Write new sequence number, a tab, and then the content
                outfile.write(f"{i}\t{original_content_cleaned}\n")
    except IOError as e:
        logging.error(f"Failed to write to output file {args.output_file}: {e}")
        sys.exit(1)
        
    logging.info("Filtering process complete. ✨")

if __name__ == "__main__":
    main()

# === End of src/filter_adb_candidates.py ===
