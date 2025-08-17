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
# Filename: src/select_final_candidates.py

"""
Selects and transforms the final set of candidates for the experiment.

This script takes the full list of eligible candidates and performs the final
selection and transformation steps:
1.  Filters the list to match the definitive set of subjects determined by the
    OCEAN scoring process.
2.  Resolves the 'CountryState' abbreviation into a full 'Country' name using
    the `country_codes.csv` mapping file.
3.  Sorts the final list by eminence score to ensure a consistent order for
    downstream processing.

Inputs:
  - `data/intermediate/adb_eligible_candidates.txt`: The full list of subjects
    who have passed all initial data quality checks.
  - `data/foundational_assets/ocean_scores.csv`: The definitive subject set.
  - `data/foundational_assets/eminence_scores.csv`: Used for sorting.
  - `data/foundational_assets/country_codes.csv`: The mapping file for country
    abbreviations.

Output:
  - `data/intermediate/adb_final_candidates.txt`: The final, sorted list
    of subjects, now including a resolved 'Country' column, ready for the
    next pipeline step.
"""

import argparse
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
from colorama import Fore, init

# Initialize colorama
init(autoreset=True)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")


def main():
    """Main function to orchestrate the final candidate selection."""
    parser = argparse.ArgumentParser(
        description="Select and transform the final set of candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--eligible-candidates", default="data/intermediate/adb_eligible_candidates.txt", help="Path to the eligible candidates input file.")
    parser.add_argument("--ocean-scores", default="data/foundational_assets/ocean_scores.csv", help="Path to the OCEAN scores file (defines the final set).")
    parser.add_argument("--eminence-scores", default="data/foundational_assets/eminence_scores.csv", help="Path to the eminence scores file (for sorting).")
    parser.add_argument("--country-codes", default="data/foundational_assets/country_codes.csv", help="Path to the country codes mapping file.")
    parser.add_argument("-o", "--output-file", default="data/intermediate/adb_final_candidates.txt", help="Path for the final candidates output file.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    # Define all file paths from arguments
    eligible_path = Path(args.eligible_candidates)
    ocean_path = Path(args.ocean_scores)
    eminence_path = Path(args.eminence_scores)
    country_codes_path = Path(args.country_codes)
    output_path = Path(args.output_file)
    input_files = [eligible_path, ocean_path, eminence_path, country_codes_path]

    # --- Intelligent Startup Logic ---
    is_stale = False
    if not args.force and output_path.exists():
        output_mtime = os.path.getmtime(output_path)
        is_stale = any(p.exists() and os.path.getmtime(p) > output_mtime for p in input_files)

        if is_stale:
            print(f"{Fore.YELLOW}\nInput file(s) are newer than the existing output. Stale data detected.")
            print("Automatically re-running full selection process...")
            args.force = True
    
    # If the file is not stale and exists, it's up-to-date. Prompt user for re-run.
    if not args.force and output_path.exists() and not is_stale:
        print(f"\n{Fore.YELLOW}WARNING: The candidates file at '{output_path}' is already up to date. ✨")
        print(f"{Fore.YELLOW}If you decide to go ahead with recreating the list of final candidates, a backup will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            args.force = True
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.{Fore.RESET}\n")
            sys.exit(0)

    # Perform the backup and overwrite if a re-run has been triggered (either by --force or by the prompts)
    if args.force and output_path.exists():
        try:
            backup_dir = Path("data/backup")
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = (backup_dir / f"{output_path.stem}.{timestamp}{output_path.suffix}.bak")
            shutil.copy2(output_path, backup_path)
            print(f"{Fore.CYAN}Created backup of existing file at: {backup_path}{Fore.RESET}")
        except (IOError, OSError) as e:
            logging.error(f"{Fore.RED}Failed to create backup file: {e}")
            sys.exit(1)

    print(f"\n{Fore.YELLOW}--- Loading Files ---")
    try:
        eligible_df = pd.read_csv(eligible_path, sep="\t")
        eminence_df = pd.read_csv(eminence_path)
        ocean_df = pd.read_csv(ocean_path)
        country_codes_df = pd.read_csv(country_codes_path)
    except FileNotFoundError as e:
        logging.error(f"{Fore.RED}FATAL: Input file not found: {e.filename}")
        sys.exit(1)

    logging.info(f"Loaded {len(eligible_df):,} records from {eligible_path.name}.")
    logging.info(f"Loaded {len(eminence_df):,} records from {eminence_path.name}.")
    logging.info(f"Loaded {len(ocean_df):,} records from {ocean_path.name} (defines final set).")
    logging.info(f"Loaded {len(country_codes_df):,} mappings from {country_codes_path.name}.")

    print(f"\n{Fore.YELLOW}--- Selecting and Transforming Final Candidates ---")

    # Step 1: Filter by OCEAN set
    ocean_subject_ids = set(ocean_df["idADB"])
    final_df = eligible_df[eligible_df["idADB"].isin(ocean_subject_ids)].copy()
    logging.info(f"Filtered to {len(final_df):,} candidates present in the OCEAN scores file.")

    # Step 2: Resolve Country Codes
    country_map = dict(zip(country_codes_df["Abbreviation"], country_codes_df["Country"]))
    final_df["Country"] = final_df["CountryState"].map(country_map)
    unmapped_count = final_df["Country"].isna().sum()
    if unmapped_count > 0:
        logging.warning(f"Could not map {unmapped_count} 'CountryState' values. 'Country' will be blank for these.")
    final_df["Country"] = final_df["Country"].fillna("")
    logging.info("Resolved 'CountryState' abbreviations to full 'Country' names.")
    
    # Step 3: Merge with eminence scores and sort
    final_df["idADB"] = final_df["idADB"].astype(str)
    eminence_df["idADB"] = eminence_df["idADB"].astype(str)
    final_df = pd.merge(final_df, eminence_df[["idADB", "EminenceScore"]], on="idADB", how="left")
    final_df.sort_values(by="EminenceScore", ascending=False, inplace=True)
    logging.info("Sorted final candidates by eminence score.")

    # Step 4: Finalize columns for output
    # Re-index the 'Index' column to be sequential from 1 to N
    final_df.reset_index(drop=True, inplace=True)
    final_df['Index'] = final_df.index + 1
    logging.info("Re-indexed the final list to be sequential.")

    # Define the exact final column order, replacing 'CountryState' with 'Country'
    final_column_order = [
        'Index', 'idADB', 'LastName', 'FirstName', 'Gender', 'Day', 'Month', 'Year',
        'Time', 'ZoneAbbr', 'ZoneTimeOffset', 'City', 'Country', 'Longitude',
        'Latitude', 'Rating', 'Bio', 'Categories', 'Link'
    ]
    final_df = final_df[final_column_order]

    # --- Save the final list ---
    final_df.to_csv(args.output_file, sep="\t", index=False, encoding="utf-8")

    print(f"\n{Fore.GREEN}SUCCESS: Successfully saved {len(final_df)} final candidates to {args.output_file}. ✨\n")


if __name__ == "__main__":
    main()

# === End of src/select_final_candidates.py ===
