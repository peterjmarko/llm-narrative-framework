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
`adb_filtered_5000.txt`.

Its key function is to bridge the manual software step deterministically:
1.  It reads the Base58 encoded ID from the `ZoneAbbr` field of the chart export.
2.  It decodes this string back into the original `idADB` integer.
3.  It uses this recovered `idADB` to perform a direct, robust 1-to-1 merge
    with the master filtered list, eliminating any need for fuzzy name matching.
4.  The final output is a clean `subject_db.csv` file, which serves as the
    primary input for the final database generation script.
"""

import argparse
import csv
import logging
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Local Imports ---
from id_encoder import from_base58

class BColors:
    """A helper class for terminal colors."""
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(message)s')

# --- Helper Functions ---

# The normalize_name function is no longer needed with idADB-based matching.

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
    Parses sf_chart_export.csv and returns a dictionary keyed by idADB.
    The idADB is read from the 'ZoneAbbr' field in the export file.
    Uses Python's built-in CSV parser for robust handling of special characters.
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

        try:
            # Use the robust csv module instead of a fragile regex
            person_info_parts = next(csv.reader([block[0]]))
        except Exception as e:
            logging.warning(f"CSV parser failed on line: {block[0]}. Error: {e}. Skipping record.")
            continue
            
        if len(person_info_parts) < 9:
            logging.warning(f"Skipping malformed person info line (found {len(person_info_parts)}/9 fields): {block[0]}")
            continue
        
        raw_name = person_info_parts[0]
        encoded_id_str = person_info_parts[3].strip()  # Encoded ID is in the ZoneAbbr field

        try:
            id_adb = from_base58(encoded_id_str)
        except Exception:
            logging.warning(f"Could not decode idADB from ZoneAbbr field: '{encoded_id_str}'. Skipping record for '{raw_name}'.")
            continue

        # Attempt to repair mojibake by reversing the incorrect latin-1 decode
        try:
            repaired_name = raw_name.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            repaired_name = raw_name  # Keep original if repair fails

        placements_raw = {next(csv.reader([line]))[0]: next(csv.reader([line]))[2] for line in block[2:]}
        placements = {p: placements_raw.get(p, '') for p in chart_points_order}

        chart_map[id_adb] = {
            "Name": repaired_name,
            "Date": person_info_parts[1], "Time": person_info_parts[2], "ZoneAbbrev": person_info_parts[3],
            "ZoneTime": person_info_parts[4], "Place": person_info_parts[5], "Country": person_info_parts[6],
            "Latitude": person_info_parts[7], "Longitude": person_info_parts[8],
            **placements
        }
    return chart_map

def main():
    parser = argparse.ArgumentParser(description="Create a master subject database.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--chart-export", default="data/foundational_assets/sf_chart_export.csv")
    parser.add_argument("--final-candidates", default="data/intermediate/adb_final_candidates.txt")
    parser.add_argument("--output-file", default="data/processed/subject_db.csv")
    args = parser.parse_args()

    print("")
    output_path = Path(args.output_file)
    if output_path.exists():
        print(f"{BColors.YELLOW}WARNING: The output file '{output_path}' already exists and will be overwritten.{BColors.ENDC}")
        confirm = input("A backup will be created. Are you sure you want to continue? (Y/N): ").lower()
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
            print(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            print(f"{BColors.RED}Failed to create backup file: {e}{BColors.ENDC}\n")
            sys.exit(1)

    # --- Pre-process the chart export into a searchable map ---
    print(f"Loading and parsing chart data from {args.chart_export}...")
    chart_data_map = load_chart_data_map(Path(args.chart_export))

    # --- Assemble final list by merging the filtered list and chart export ---
    print(f"Assembling master database from primary list: {args.final_candidates}")
    all_subjects = []
    missing_subjects_log = []  # Initialize list before the try block
    header = ["Index", "idADB", "Name", "Date", "Time", "ZoneAbbrev", "ZoneTime", "Place", "Country", "Latitude", "Longitude", 
              "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"]
    
    try:
        with open(args.final_candidates, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                full_name = " ".join(filter(None, [row['FirstName'], row['LastName']]))
                try:
                    id_adb_key = int(row['idADB'])
                    chart_data = chart_data_map.get(id_adb_key)
                except (ValueError, TypeError):
                    missing_subjects_log.append({ 'Index': row['Index'], 'idADB': row['idADB'], 'Name': full_name, 'Reason': 'Invalid idADB' })
                    continue
                
                if not chart_data:
                    missing_subjects_log.append({ 'Index': row['Index'], 'idADB': id_adb_key, 'Name': full_name, 'Reason': 'Not found in chart export' })
                    continue
                
                subject_data = { "Index": int(row['Index']), "idADB": id_adb_key, **chart_data }
                all_subjects.append(subject_data)

    except FileNotFoundError:
        logging.error(f"Filtered list not found: {args.final_candidates}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing expected column {e} in {args.final_candidates}. Please ensure it is correctly formatted.")
        sys.exit(1)

    # --- Final Validation and Output ---
    if missing_subjects_log:
        reports_dir = Path('data/reports')
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / 'missing_sf_subjects.csv'
        
        with open(report_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['Index', 'idADB', 'Name', 'Reason'])
            writer.writeheader()
            writer.writerows(missing_subjects_log)
            
        print(f"\n{BColors.RED}ERROR: Found {len(missing_subjects_log)} missing subjects during processing.{BColors.ENDC}")
        print(f"{BColors.YELLOW}A diagnostic report has been created at: {report_path}{BColors.ENDC}")
        print(f"{BColors.YELLOW}The master subject DB has NOT been created. Please resolve the discrepancies and run again.{BColors.ENDC}\n")
        sys.exit(1)

    # --- Write final output if validation passes ---
    logging.info(f"Writing {len(all_subjects)} records to {args.output_file}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_subjects)
        
        print(f"\n{BColors.GREEN}SUCCESS: Master subject database with {len(all_subjects)} records created successfully. ✨{BColors.ENDC}\n")
    except IOError as e:
        print(f"\n{BColors.RED}Failed to write to output file: {e}{BColors.ENDC}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/create_subject_db.py ===
