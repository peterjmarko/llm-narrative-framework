#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
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
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore, init

# Ensure the src directory is in the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config_loader import get_path  # noqa: E402
# --- Local Imports ---
from id_encoder import from_base58  # noqa: E402
from utils.file_utils import backup_and_remove  # noqa: E402

# Initialize colorama
init(autoreset=True, strip=False)

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
    parser.add_argument(
        "--sandbox-path",
        type=str,
        help="Path to the sandbox directory for testing.",
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    if args.sandbox_path:
        os.environ["PROJECT_SANDBOX_PATH"] = args.sandbox_path

    chart_export_path = Path(get_path("data/foundational_assets/sf_chart_export.csv"))
    final_candidates_path = Path(get_path("data/intermediate/adb_final_candidates.txt"))
    output_path = Path(get_path("data/processed/subject_db.csv"))

    # --- Intelligent Startup Logic ---
    is_stale = False
    if not args.force and output_path.exists():
        output_mtime = os.path.getmtime(output_path)
        # Check if any of the input files are newer than the output
        input_files = [chart_export_path, final_candidates_path]
        is_stale = any(p.exists() and os.path.getmtime(p) > output_mtime for p in input_files)

        if is_stale:
            print(f"{Fore.YELLOW}\nInput file(s) are newer than the existing output. Stale data detected.")
            print("Automatically re-running...")
            args.force = True

    if not args.force and output_path.exists() and not is_stale:
        print(f"\n{Fore.YELLOW}WARNING: The subject database at '{output_path}' is already up to date.")
        print(f"{Fore.YELLOW}If you decide to go ahead with the update, a backup of the existing database will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            args.force = True
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
            sys.exit(0)

    if args.force and output_path.exists():
        backup_and_remove(output_path)

    # --- Calculate project-relative paths for display ---
    project_root = Path.cwd()
    while not (project_root / ".git").exists() and project_root != project_root.parent:
        project_root = project_root.parent
    try:
        display_chart_path = chart_export_path.relative_to(project_root)
        display_candidates_path = final_candidates_path.relative_to(project_root)
    except ValueError:
        display_chart_path = chart_export_path
        display_candidates_path = final_candidates_path
    
    # Standardize path separators for consistent output
    display_chart_path = str(display_chart_path).replace('\\', '/')
    display_candidates_path = str(display_candidates_path).replace('\\', '/')

    print(f"\nLoading and parsing chart data from {display_chart_path}...")
    chart_data_map = load_chart_data_map(chart_export_path)

    # --- Assemble final list by merging the filtered list and chart export ---
    print(f"Assembling master database from primary list: {display_candidates_path}")
    all_subjects = []
    missing_subjects_log = []  # Initialize list before the try block
    header = ["Index", "idADB", "Name", "Date", "Time", "ZoneAbbrev", "ZoneTime", "Place", "Country", "Latitude", "Longitude", 
              "Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto", "Ascendant", "Midheaven"]
    
    try:
        with open(final_candidates_path, 'r', encoding='utf-8') as f:
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

                # Blank out the ZoneAbbrev field as it's no longer needed
                chart_data['ZoneAbbrev'] = ""
                
                subject_data = { "Index": int(row['Index']), "idADB": id_adb_key, **chart_data }

                # Ensure all floating point numbers are formatted as strings with consistent
                # precision, and all other types are converted to strings to match the
                # gold standard's object dtype for all columns.
                for key, value in subject_data.items():
                    if isinstance(value, float):
                        subject_data[key] = f"{value:.14f}".rstrip('0').rstrip('.')
                    else:
                        subject_data[key] = str(value if value is not None else "")
                
                all_subjects.append(subject_data)

    except FileNotFoundError:
        logging.error(f"Filtered list not found: {final_candidates_path}")
        sys.exit(1)
    except KeyError as e:
        logging.error(f"Missing expected column {e} in {final_candidates_path}. Please ensure it is correctly formatted.")
        sys.exit(1)

    # --- Final Validation and Output ---
    reports_dir = Path(get_path('data/reports'))
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / 'missing_sf_subjects.csv'
    
    with open(report_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['Index', 'idADB', 'Name', 'Reason'])
        writer.writeheader()
        if missing_subjects_log:
            writer.writerows(missing_subjects_log)

    if missing_subjects_log:
        logging.error(f"Found {len(missing_subjects_log)} missing subjects during processing.")
        logging.warning(f"A diagnostic report has been created at: {report_path}")
        logging.warning("The master subject DB has NOT been created. Please resolve the discrepancies and run again.\n")
        sys.exit(1)

    # --- Write final output if validation passes ---
    try:
        display_output_path = output_path.relative_to(project_root)
    except (ValueError, NameError):  # Handle if project_root fails to be found
        display_output_path = output_path
        
    display_output_path = str(display_output_path).replace('\\', '/')

    print(f"Writing {len(all_subjects)} records to {display_output_path}...")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=header)
            writer.writeheader()
            writer.writerows(all_subjects)

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Master subject database saved to: {display_output_path}{Fore.RESET}")
        
        final_count = len(all_subjects)
        key_metric = f"Final Count: {final_count:,} subjects"
        
        if final_count > 0:
            print(
                f"\n{Fore.GREEN}SUCCESS: {key_metric}. Master subject database "
                f"created successfully.{Fore.RESET}\n"
            )
        else:
            print(
                f"\n{Fore.RED}FAILURE: {key_metric}. No records were processed.{Fore.RESET}\n"
            )
            # No sys.exit(1) here as an empty file can be a valid outcome.

    except IOError as e:
        logging.error(f"Failed to write to output file: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/create_subject_db.py ===
