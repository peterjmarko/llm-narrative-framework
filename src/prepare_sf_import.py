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
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# --- Local Imports ---
from id_encoder import to_base58

# --- ANSI Color Codes ---
class BColors:
    """A helper class for terminal colors."""
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

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
        "-i", "--input-file",
        default="data/intermediate/adb_final_candidates.txt",
        help="Path to the final, tab-delimited subject data file."
    )
    parser.add_argument(
        "-o", "--output-file",
        default="data/intermediate/sf_data_import.txt",
        help="Path to write the final CQD-formatted output file."
    )
    args = parser.parse_args()

    input_path = Path(args.input_file)
    output_path = Path(args.output_file)

    if not input_path.exists():
        logging.error(f"Input file not found: {input_path}")
        sys.exit(1)

    if output_path.exists():
        print("")
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
            logging.info(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            logging.error(f"Failed to create backup file: {e}")
            sys.exit(1)

    print("")
    logging.info(f"Reading filtered data from: {input_path}")
    logging.info(f"Writing Solar Fire import file to: {output_path}")

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
        print(f"{BColors.RED}No valid records were processed. Output file will not be created.{BColors.ENDC}")
        sys.exit(1)

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8', newline='') as outfile:
            for record in processed_records:
                # Manually construct the CQD line to ensure all fields are quoted
                formatted_line = ",".join([f'"{field}"' for field in record])
                outfile.write(formatted_line + "\n")
        
        print(f"{BColors.GREEN}\nSuccessfully wrote {len(processed_records)} records to {output_path}.{BColors.ENDC}")
        print("")
    except IOError as e:
        print(f"{BColors.RED}Failed to write to output file {output_path}: {e}{BColors.ENDC}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/prepare_sf_import.py ===
