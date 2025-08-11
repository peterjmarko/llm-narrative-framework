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
# Filename: src/select_eligible_candidates.py

"""
Selects eligible candidates for LLM scoring from the raw ADB data export.

This script serves as the first filtering stage in the data preparation pipeline.
It takes the raw data dump and the validation report to produce a clean list of
all subjects who are potentially viable for the study. This pre-filtering
ensures that subsequent, expensive LLM-based scoring is only performed on
high-quality, valid data.

Inputs:
  - `data/sources/adb_raw_export.txt`: Raw data from `fetch_adb_data.py`.
  - `data/reports/adb_validation_report.csv`: Status report from `validate_adb_data.py`.

Output:
  - `data/intermediate/adb_eligible_candidates.txt`: A clean, tab-delimited
    file containing all subjects who pass the initial quality checks.
"""

import argparse
import logging
import re
import sys
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")


def normalize_name_for_deduplication(raw_name: str) -> tuple:
    """
    Normalizes a name for robust duplicate detection.
    It strips parenthetical content and sorts name parts alphabetically.
    """
    # Remove anything in parentheses (including the URL)
    name = re.sub(r"\(.*\)", "", raw_name).strip()
    # Split into parts, handling both comma and space delimiters
    parts = re.split(r"[,\s-]+", name)
    # Filter out empty strings, convert to lowercase, and sort
    normalized_parts = sorted([part.lower() for part in parts if part])
    return tuple(normalized_parts)

def main():
    """Main function to orchestrate the filtering process."""
    parser = argparse.ArgumentParser(
        description="Filter raw ADB data to generate a list of eligible candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("-o", "--output-file", default="data/intermediate/adb_eligible_candidates.txt", help="Path for the eligible candidates output file.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    output_path = Path(args.output_file)
    if output_path.exists() and not args.force:
        print()
        print(f"{Fore.YELLOW}WARNING: The output file '{output_path}' already exists.")
        response = input("Are you sure you want to continue? (Y/N): ").lower()
        if response != "y":
            print("\nOperation cancelled by user.")
            sys.exit(0)

    if output_path.exists():
        try:
            backup_dir = Path("data/backup")
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = (backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak")
            shutil.copy2(output_path, backup_path)
            logging.info(f"Created backup of existing file at: {backup_path}")
        except (IOError, OSError) as e:
            logging.error(f"{Fore.RED}Failed to create backup file: {e}")
            sys.exit(1)

    print(f"\n{Fore.YELLOW}--- Loading Files ---")
    try:
        validation_df = pd.read_csv("data/reports/adb_validation_report.csv")
        with open("data/sources/adb_raw_export.txt", "r", encoding="utf-8") as f:
            header = f.readline().strip()
            raw_lines = f.readlines()
    except FileNotFoundError as e:
        logging.error(f"{Fore.RED}FATAL: Input file not found: {e.filename}")
        sys.exit(1)
    
    logging.info(f"Loaded {len(raw_lines):,} records from data/sources/adb_raw_export.txt.")
    logging.info(f"Loaded {len(validation_df):,} records from data/reports/adb_validation_report.csv.")

    print(f"\n{Fore.YELLOW}--- Selecting Eligible Candidates ---")
    
    # Pre-process raw lines into a list of lists (parts)
    parsed_lines = [line.strip().split("\t") for line in raw_lines]
    
    # Filter 1: 'OK' Status
    valid_ids = set(validation_df[validation_df["Status"] == "OK"]["idADB"].astype(str))
    stage1_candidates = [parts for parts in parsed_lines if parts[1] in valid_ids]
    logging.info(f"{len(stage1_candidates)} candidates remaining after filtering for 'OK' status from the validation report.")

    # Filter 2: Birth Year
    stage2_candidates = []
    for parts in stage1_candidates:
        try:
            if 1900 <= int(parts[7]) <= 1999:
                stage2_candidates.append(parts)
        except (ValueError, IndexError):
            continue
    logging.info(f"{len(stage2_candidates)} candidates remaining after filtering for birth year (1900-1999).")

    # Filter 3: Valid Time Format
    stage3_candidates = [parts for parts in stage2_candidates if re.match(r"^\d{1,2}:\d{2}$", parts[8])]
    logging.info(f"{len(stage3_candidates)} candidates remaining after filtering for valid birth time (HH:MM format).")
    
    # Filter 4: Uniqueness (LAST)
    final_candidates = []
    processed_identifiers = set()
    removed_duplicates_info = []
    for parts in stage3_candidates:
        if len(parts) < 9: continue
        id_adb, last_name, first_name, day, month, year = parts[1], parts[2], parts[3], parts[5], parts[6], parts[7]
        raw_name = f"{last_name}, {first_name}"
        unique_identifier = (normalize_name_for_deduplication(raw_name), f"{year}-{month}-{day}")
        
        if unique_identifier not in processed_identifiers:
            final_candidates.append(parts)
            processed_identifiers.add(unique_identifier)
        else:
            name_for_log = re.sub(r"\(.*\)", "", raw_name).strip()
            removed_duplicates_info.append(f"  - idADB {id_adb}: {name_for_log}")

    if removed_duplicates_info:
        logging.info(f"Dropped {len(removed_duplicates_info)} duplicate entries:")
        for info in removed_duplicates_info:
            logging.info(info)
        logging.info(f"{len(final_candidates)} candidates remaining.")
    else:
        duplicates_removed = len(stage3_candidates) - len(final_candidates)
        logging.info(f"Removed {duplicates_removed} duplicates. {len(final_candidates)} candidates remaining.")
        
    # --- Save the final list ---
    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for parts in final_candidates:
            f.write("\t".join(parts) + "\n")
    
    print()
    print(f"{Fore.GREEN}Successfully saved {len(final_candidates)} eligible candidates to {args.output_file}")
    print()


if __name__ == "__main__":
    main()

# === End of src/select_eligible_candidates.py ===
