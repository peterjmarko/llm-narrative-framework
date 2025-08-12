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
    parser.add_argument("-o", "--output-file", default="data/intermediate/adb_final_candidates.txt", help="Path for the final candidates output file.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    # Define all file paths
    eligible_path = Path("data/intermediate/adb_eligible_candidates.txt")
    ocean_path = Path("data/foundational_assets/ocean_scores.csv")
    eminence_path = Path("data/foundational_assets/eminence_scores.csv")
    country_codes_path = Path("data/foundational_assets/country_codes.csv")
    output_path = Path(args.output_file)
    proceed = True

    if output_path.exists():
        if not args.force:
            print(f"\n{Fore.YELLOW}WARNING: The output file '{output_path}' already exists.")
            confirm = input("A backup will be created. Are you sure you want to continue? (Y/N): ").lower().strip()
            if confirm != 'y':
                proceed = False

        if proceed:
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
        else:
            print("\nOperation cancelled by user.\n")
            sys.exit(0)

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
    final_df["Country"].fillna("", inplace=True)
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
