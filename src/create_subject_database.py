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
import shutil
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

class BColors:
    """A helper class for terminal colors."""
    YELLOW = '\033[93m'
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
        
        name = person_info_parts[0]
        # Key the map with a truncated normalized name to handle export inconsistencies.
        norm_name_truncated = normalize_name(name)[:25]

        placements_raw = {next(csv.reader([line]))[0]: next(csv.reader([line]))[2] for line in block[2:]}
        placements = {p: placements_raw.get(p, '') for p in chart_points_order}

        chart_map[norm_name_truncated] = {
            "Name": name,
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
    parser.add_argument("--eminence-scores", default="data/foundational_assets/eminence_scores.csv")
    parser.add_argument("--raw-export", default="data/sources/adb_raw_export.txt")
    parser.add_argument("--output-file", default="data/subject_db.csv")
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

    # --- Load all necessary lookup tables ---
    logging.info("Loading lookup data...")

    eminence_scores = load_lookup_data(Path(args.eminence_scores), 'ARN', 'EminenceScore')
    
    arn_map = {}
    for line in Path(args.raw_export).read_text(encoding='utf-8').splitlines():
        parts = line.split('\t')
        if len(parts) > 1 and parts[0].isdigit():
            # URL-decode the name field from the raw export first
            decoded_name = unquote(parts[1])
            name_no_slug = re.sub(r'\(.*\)', '', decoded_name).strip()
            arn_map[normalize_name(name_no_slug)] = parts[0]

    # --- Pre-process the chart export into a searchable map ---
    logging.info(f"Loading and parsing chart data from {args.chart_export}...")
    chart_data_map = load_chart_data_map(Path(args.chart_export))

    # --- Assemble final list using the filtered list as the source of truth ---
    logging.info(f"Assembling master database from primary list: {args.filtered_5000}")
    all_subjects = []
    header = ["Rank", "ARN", "Name", "Date", "Time", "ZoneAbbrev", "ZoneTime", "Place", "Country", "Latitude", "Longitude", 
              "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven", "EminenceScore"]
    
    try:
        with open(args.filtered_5000, 'r', encoding='utf-8') as f:
            filtered_lines = f.readlines()
    except FileNotFoundError:
        logging.error(f"Filtered list not found: {args.filtered_5000}")
        sys.exit(1)

    subjects_not_in_chart_export = 0
    for line in filtered_lines:
        parts = line.strip().split('\t')
        rank, name_from_filter = parts[0], parts[1]
        
        norm_name_from_filter = normalize_name(name_from_filter)
        
        # First, try to find the ARN using the normalized name. This should work for most cases.
        arn = arn_map.get(norm_name_from_filter)
        if not arn:
            logging.warning(f"Could not find ARN for '{name_from_filter}'. Skipping.")
            continue

        # Find chart data using a truncated normalized name.
        norm_name_truncated = norm_name_from_filter[:25]
        chart_data = chart_data_map.get(norm_name_truncated)
        
        if not chart_data:
            subjects_not_in_chart_export += 1
            logging.warning(f"Rank {rank}: '{name_from_filter}' could not be matched in the chart export file. Skipping.")
            continue

        subject_data = {
            "Rank": int(rank),
            "ARN": int(arn),
            "EminenceScore": float(eminence_scores.get(arn, 0.0)),
            **chart_data
        }
        all_subjects.append(subject_data)

    if subjects_not_in_chart_export > 0:
        logging.warning(f"A total of {subjects_not_in_chart_export} subjects from the filtered list were missing from the chart export.")
    
    # --- Write final output (no sorting needed) ---
    logging.info(f"Writing {len(all_subjects)} records to {args.output_file}...")
    try:
        # Before writing, remove the temporary 'OriginalName' key used for diagnostics
        for subject in all_subjects:
            subject.pop('OriginalName', None)

        with open(args.output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_subjects)
        logging.info("Master subject database created successfully. ✨\n")
    except IOError as e:
        logging.error(f"Failed to write to output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/create_subject_database.py ===
