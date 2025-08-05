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
# Filename: src/create_subject_database.py

"""
Creates a master subject database by flattening and enriching chart data.

This script acts as a crucial data integration and validation step. It reads
the multi-line chart data from Solar Fire (`sf_chart_export.csv`), flattens
it into one row per subject, and enriches it by cross-referencing multiple
source files to add Rank, ARN, and Eminence Score. The final output is a
clean, sorted `subject_db.csv` file, which serves as the primary input for
the final database generation script.
"""

import argparse
import csv
import logging
import re
import sys
from pathlib import Path

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Helper Functions ---

def normalize_name(name: str) -> str:
    """Normalizes a name for robust cross-referencing."""
    # Convert "Last, First" to "First Last"
    if ',' in name:
        parts = name.split(',', 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"
    # Standardize whitespace and case
    return ' '.join(name.lower().split())

def load_lookup_data(filepath: Path, key_col: str, val_col: str, key_norm_fn=None) -> dict:
    """Generic function to load a lookup dictionary from a CSV."""
    lookup = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = row[key_col]
                if key_norm_fn:
                    key = key_norm_fn(key)
                lookup[key] = row[val_col]
        return lookup
    except FileNotFoundError:
        logging.error(f"Lookup file not found: {filepath}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing expected column '{e}' in {filepath}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create a master subject database.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--chart-export", default="data/sources/sf_chart_export.csv")
    parser.add_argument("--filtered-5000", default="data/adb_filtered_5000.txt")
    parser.add_argument("--eminence-scores", default="data/eminence_scores.csv")
    parser.add_argument("--raw-export", default="data/sources/adb_raw_export.txt")
    parser.add_argument("--output-file", default="data/subject_db.csv")
    args = parser.parse_args()

    # --- Load all necessary lookup tables ---
    logging.info("Loading lookup data...")
    ranks = {normalize_name(line.split('\t')[1]): line.split('\t')[0] for line in Path(args.filtered_5000).read_text(encoding='utf-8').splitlines()}
    eminence_scores = load_lookup_data(Path(args.eminence_scores), 'ARN', 'EminenceScore')
    
    # Create ARN lookup from raw export
    arn_map = {}
    for line in Path(args.raw_export).read_text(encoding='utf-8').splitlines():
        parts = line.split('\t')
        if len(parts) > 1 and parts[0].isdigit():
            # Name in raw export has slug, e.g., "Doe, John (http...)"
            name_no_slug = re.sub(r'\(.*\)', '', parts[1]).strip()
            arn_map[normalize_name(name_no_slug)] = parts[0]

    # --- Process the main chart export file ---
    logging.info(f"Processing chart data from {args.chart_export}...")
    all_subjects = []
    header = ["Rank", "ARN", "Name", "Date", "Time", "ZoneAbbrev", "ZoneTime", "Place", "Country", "Latitude", "Longitude", 
              "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven", "EminenceScore"]
    
    chart_points_order = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"]

    try:
        with open(args.chart_export, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f]
    except FileNotFoundError:
        logging.error(f"Chart export file not found: {args.chart_export}")
        sys.exit(1)

    for i in range(0, len(lines), 14):
        block = lines[i:i+14]
        if len(block) < 14: continue

        person_info = next(csv.reader([block[0]]))
        
        placements_raw = {next(csv.reader([line]))[0]: next(csv.reader([line]))[2] for line in block[2:]}
        # Reorder Sun and Moon to match header
        placements = {p: placements_raw.get(p, '') for p in chart_points_order}

        name = person_info[0]
        norm_name = normalize_name(name)
        
        arn = arn_map.get(norm_name)
        if not arn:
            logging.warning(f"Could not find ARN for '{name}'. Skipping.")
            continue

        subject_data = {
            "Rank": int(ranks.get(norm_name, -1)),
            "ARN": int(arn),
            "Name": name,
            "Date": person_info[1], "Time": person_info[2], "ZoneAbbrev": person_info[3],
            "ZoneTime": person_info[4], "Place": person_info[5], "Country": person_info[6],
            "Latitude": person_info[7], "Longitude": person_info[8],
            "EminenceScore": float(eminence_scores.get(arn, 0.0)),
            **placements
        }
        all_subjects.append(subject_data)

    # --- Sort and Validate ---
    logging.info("Sorting subjects and validating rank...")
    # Sort by EminenceScore (desc) then ARN (asc)
    sorted_subjects = sorted(all_subjects, key=lambda x: (-x['EminenceScore'], x['ARN']))

    # Validate that the Rank field is now sequential
    validation_passed = True
    for i, subject in enumerate(sorted_subjects, 1):
        if subject['Rank'] != i:
            logging.error(f"Rank validation failed! Expected rank {i} for {subject['Name']} (ARN {subject['ARN']}), but found {subject['Rank']}.")
            validation_passed = False
    
    if not validation_passed:
        logging.error("Sorting by eminence did not produce the expected rank order. Aborting.")
        sys.exit(1)
    logging.info("Rank validation successful.")

    # --- Write final output ---
    logging.info(f"Writing {len(sorted_subjects)} records to {args.output_file}...")
    try:
        with open(args.output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(sorted_subjects)
        logging.info("Master subject database created successfully. ✨")
    except IOError as e:
        logging.error(f"Failed to write to output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()