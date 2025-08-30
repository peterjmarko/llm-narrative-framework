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
# Filename: src/prepare_sf_import.py

"""
Format filtered ADB data for Solar Fire import.

This script takes the clean, final list of subjects and transforms it into the
specific Comma Quote Delimited (CQD) format required for import into the Solar
Fire astrology software.

Its primary functions are:
1.  Reads the structured, tab-delimited data from `adb_filtered_final.txt`.
2.  Encodes each subject's unique `idADB` into a compact, human-friendly
    Base58 string (e.g., 102076 -> "2b4L").
3.  Injects this encoded ID into the `ZoneAbbr` field of the import record.
    This is the key step that allows a unique identifier to pass through the
    manual Solar Fire processing step, ensuring robust data integrity.
4.  Assembles and writes the final 9-field CQD records to `sf_data_import.txt`.
"""

import argparse
import calendar
import csv
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Local Imports ---
from colorama import Fore, init

# Ensure the src directory is in the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config_loader import get_path  # noqa: E402
from id_encoder import to_base58  # noqa: E402

# Initialize colorama
init(autoreset=True)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def format_coordinate(coord_str: str) -> str:
    """
    Formats a raw coordinate string (e.g., '74w0') into the required
    DDvMM/DDDhMM format by padding minutes with a leading zero if necessary.
    """
    if not coord_str:
        return ""
    
    match = re.match(r"(\d+)([nswe])(\d+)", coord_str, re.IGNORECASE)
    if not match:
        return coord_str.upper()
        
    degrees, direction, min_sec_digits = match.groups()
    minutes = min_sec_digits[:2].zfill(2)
    return f"{degrees}{direction.upper()}{minutes}"

def main():
    """Main function to read, format, and write the Solar Fire import file."""
    parser = argparse.ArgumentParser(
        description="Prepare filtered ADB data for Solar Fire import.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--sandbox-path",
        type=str,
        help="Path to the sandbox directory for testing.",
    )
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    if args.sandbox_path:
        os.environ["PROJECT_SANDBOX_PATH"] = args.sandbox_path

    input_path = Path(get_path("data/intermediate/adb_final_candidates.txt"))
    output_path = Path(get_path("data/intermediate/sf_data_import.txt"))

    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}")
        sys.exit(1)

    # --- Intelligent Startup Logic ---
    is_stale = False
    if not args.force and output_path.exists():
        output_mtime = os.path.getmtime(output_path)
        if os.path.exists(input_path) and os.path.getmtime(input_path) > output_mtime:
            is_stale = True
            print(f"{Fore.YELLOW}\nInput file is newer than the existing output. Stale data detected.")
            print("Automatically re-running...")
            args.force = True

    if not args.force and output_path.exists() and not is_stale:
        print(f"\n{Fore.YELLOW}WARNING: The import file at '{output_path}' is already up to date. ✨")
        print(f"{Fore.YELLOW}If you decide to go ahead with the update, a backup of the existing file will be created.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            args.force = True
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
            sys.exit(0)

    if args.force and output_path.exists():
        try:
            backup_dir = Path('data/backup')
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak"
            shutil.copy2(output_path, backup_path)
            print(f"{Fore.CYAN}Created backup of existing file at: {backup_path}{Fore.RESET}")
        except (IOError, OSError) as e:
            logging.error(f"{Fore.RED}Failed to create backup file: {e}")
            sys.exit(1)

    print("")
    print(f"Reading filtered data from: {input_path}")
    print(f"{Fore.CYAN}Writing Solar Fire import file to: {output_path}{Fore.RESET}")

    processed_records = []
    try:
        with open(input_path, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile, delimiter='\t')
            for row in reader:
                # 1. Assemble and clean the name
                # Handles cases where FirstName or LastName might be empty (e.g., 'Pelé')
                full_name = " ".join(filter(None, [row['FirstName'], row['LastName']]))
                full_name = full_name.replace('"', '')

                # 2. Format the date
                try:
                    month_name = calendar.month_name[int(row['Month'])]
                    sf_date_str = f"{row['Day']} {month_name} {row['Year']}"
                except (ValueError, KeyError):
                    logging.warning(f"Skipping record for {full_name} due to invalid date.")
                    continue

                # 3. Assemble the final 9-field CQD record
                # Encode the idADB for safe transport in the ZoneAbbr field
                encoded_id = to_base58(int(row['idADB']))

                output_record = [
                    full_name,
                    sf_date_str,
                    row['Time'],
                    encoded_id,
                    row['ZoneTimeOffset'],
                    row['City'],
                    row['Country'],
                    format_coordinate(row['Latitude']),
                    format_coordinate(row['Longitude'])
                ]
                processed_records.append(output_record)

    except Exception as e:
        logging.error(f"An unexpected error occurred while processing the input file: {e}")
        sys.exit(1)

    if not processed_records:
        logging.error("No valid records were processed. Output file will not be created.")
        sys.exit(1)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            for record in processed_records:
                # Manually construct the CQD line to ensure all fields are quoted
                formatted_line = ",".join([f'"{field}"' for field in record])
                outfile.write(formatted_line + "\n")
        
        print(f"\n{Fore.YELLOW}--- Final Output ---")
        print(f"{Fore.CYAN} - Solar Fire import file saved to: {output_path}")
        key_metric = f"Final Count: {len(processed_records)} subjects"
        print(
            f"\n{Fore.GREEN}SUCCESS: {key_metric}. Solar Fire import file "
            f"created successfully. ✨\n"
        )
    except IOError as e:
        logging.error(f"Failed to write to output file {output_path}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/prepare_sf_import.py ===
