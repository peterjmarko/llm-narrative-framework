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
# Filename: src/create_subject_db.py

"""
Creates a master subject database by flattening and enriching chart data.

This script acts as a crucial data integration step. It reads the multi-line
chart data exported from Solar Fire (`sf_chart_export.csv`), flattens it into
one row per subject, and merges it with the primary subject list from
`adb_filtered_5000.txt`. It uses the name for matching and adds key identifiers
(`Index`, `idADB`) and `EminenceScore` from the filtered list. The final output
is a clean `subject_db.csv` file, which serves as the primary input for the
final database generation script. The records in the output file are
guaranteed to be in the same order as in the `adb_filtered_5000.txt` input
file.
"""

import argparse
import csv
import logging
import re
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

class BColors:
    """A helper class for terminal colors."""
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- Helper Functions ---

def normalize_name(name: str) -> str:
    """
    Normalizes a name for robust cross-referencing by repairing encoding
    errors, handling all quote types, diacritics, punctuation, and name order.
    """
    try:
        name = name.encode('latin-1').decode('utf-8')
    except (UnicodeDecodeError, UnicodeEncodeError):
        pass  # Keep original if repair fails

    # Handle "Last, First" format before other cleaning
    if ',' in name:
        parts = name.split(',', 1)
        name = f"{parts[1].strip()} {parts[0].strip()}"

    # Aggressively remove all types of quotation marks (standard, smart, etc.)
    name = re.sub(r'["“”‘’`\']', '', name)

    # Transliterate diacritics (e.g., 'é' -> 'e')
    nfkd_form = unicodedata.normalize('NFD', name)
    ascii_name = "".join([c for c in nfkd_form if not unicodedata.combining(c)])

    # Remove any remaining non-alphanumeric characters (except spaces) and lowercase
    ascii_name = re.sub(r'[^\w\s]', '', ascii_name).lower()
    
    # Standardize whitespace
    return ' '.join(ascii_name.split())

def load_lookup_data(filepath: Path, key_col: str, val_col: str) -> dict:
    """Generic function to load a lookup dictionary from a CSV."""
    lookup = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lookup[row[key_col]] = row[val_col]
        return lookup
    except FileNotFoundError:
        logging.error(f"Lookup file not found: {filepath}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing expected column '{e}' in {filepath}")
        sys.exit(1)

def load_chart_data_map(filepath: Path) -> dict:
    """
    Parses sf_chart_export.csv and returns a dictionary keyed by normalized name.
    Uses regex to robustly handle malformed/truncated CSV lines from the export.
    """
    chart_map = {}
    try:
        # Read with 'latin-1' which never fails, then we will repair the text.
        with open(filepath, 'r', encoding='latin-1') as f:
            lines = [line.strip() for line in f]
    except FileNotFoundError:
        logging.error(f"Chart export file not found: {filepath}")
        sys.exit(1)

    chart_points_order = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"]

    for i in range(0, len(lines), 14):
        block = lines[i:i+14]
        if len(block) < 14: continue

        # Use regex to robustly find all quoted fields, ignoring line-end corruption.
        person_info_parts = re.findall(r'"([^"]*)"', block[0])
        if len(person_info_parts) < 9:
            logging.warning(f"Skipping malformed person info line: {block[0]}")
            continue
        
        raw_name = person_info_parts[0]
        
        # Attempt to repair mojibake by reversing the incorrect latin-1 decode
        try:
            repaired_name = raw_name.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            repaired_name = raw_name # Keep original if repair fails

        # Key the map with a truncated normalized name to handle export inconsistencies.
        norm_name_truncated = normalize_name(repaired_name)[:25]

        placements_raw = {next(csv.reader([line]))[0]: next(csv.reader([line]))[2] for line in block[2:]}
        placements = {p: placements_raw.get(p, '') for p in chart_points_order}

        chart_map[norm_name_truncated] = {
            "Name": repaired_name, # Use the fixed name for output
            "Date": person_info_parts[1], "Time": person_info_parts[2], "ZoneAbbrev": person_info_parts[3],
            "ZoneTime": person_info_parts[4], "Place": person_info_parts[5], "Country": person_info_parts[6],
            "Latitude": person_info_parts[7], "Longitude": person_info_parts[8],
            **placements
        }
    return chart_map

def main():
    parser = argparse.ArgumentParser(description="Create a master subject database.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--chart-export", default="data/foundational_assets/sf_chart_export.csv")
    parser.add_argument("--filtered-5000", default="data/intermediate/adb_filtered_5000.txt")
    parser.add_argument("--output-file", default="data/processed/subject_db.csv")
    args = parser.parse_args()

    print("")
    output_path = Path(args.output_file)
    if output_path.exists():
        print(f"{BColors.YELLOW}WARNING: The output file '{output_path}' already exists and will be overwritten.{BColors.ENDC}")
        confirm = input("Are you sure you want to continue? (Y/N): ").lower()
        if confirm != 'y':
            print("\nOperation cancelled by user.\n")
            sys.exit(0)
        
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
            shutil.copy2(output_path, backup_path)
            print("")
            logging.info(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup file: {e}")
            sys.exit(1)

    # No external lookups are needed; all required data is in the primary files.

    # --- Pre-process the chart export into a searchable map ---
    logging.info(f"Loading and parsing chart data from {args.chart_export}...")
    chart_data_map = load_chart_data_map(Path(args.chart_export))

    # --- Assemble final list using the filtered list as the source of truth ---
    logging.info(f"Assembling master database from primary list: {args.filtered_5000}")
    all_subjects = []
    header = ["Index", "idADB", "Name", "Date", "Time", "ZoneAbbrev", "ZoneTime", "Place", "Country", "Latitude", "Longitude", 
              "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven", "EminenceScore"]
    
    subjects_not_in_chart_export = 0
    try:
        with open(args.filtered_5000, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                # Construct full name from parts, handling single-name cases like 'Pelé'
                full_name = " ".join(filter(None, [row['FirstName'], row['LastName']]))
                norm_name_from_filter = normalize_name(full_name)
                
                # Find chart data using a truncated normalized name.
                norm_name_truncated = norm_name_from_filter[:25]
                chart_data = chart_data_map.get(norm_name_truncated)
                
                if not chart_data:
                    subjects_not_in_chart_export += 1
                    logging.warning(f"Index {row['Index']}: '{full_name}' could not be matched in the chart export file. Skipping.")
                    continue

                subject_data = {
                    "Index": int(row['Index']),
                    "idADB": int(row['idADB']),
                    "EminenceScore": float(row['EminenceScore']),
                    **chart_data
                }
                all_subjects.append(subject_data)

    except FileNotFoundError:
        logging.error(f"Filtered list not found: {args.filtered_5000}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing expected column {e} in {args.filtered_5000}. Please ensure it is correctly formatted.")
        sys.exit(1)

    if subjects_not_in_chart_export > 0:
        logging.warning(f"A total of {subjects_not_in_chart_export} subjects from the filtered list were missing from the chart export.")
    
    # --- Write final output ---
    logging.info(f"Writing {len(all_subjects)} records to {args.output_file}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_subjects)
        
        print("")
        print(f"{BColors.GREEN}Master subject database created successfully. ✨{BColors.ENDC}")
        print("")
    except IOError as e:
        print(f"\n{BColors.RED}Failed to write to output file: {e}{BColors.ENDC}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/create_subject_db.py ===
