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
# Filename: src/utils/patch_eminence_scores.py

"""
One-time patch script to clean and enrich the eminence_scores.csv file.

This script performs a local-only transformation to:
1.  Load both the eminence scores and the eligible candidates files.
2.  Merge them to bring in the authoritative 'Year' for each subject.
3.  Create and populate a new 'BirthYear' column for all subjects.
4.  Extract birth years from disambiguated names (e.g., "Jerry (1934) Lewis")
    and use them to clean the 'Name' field.
5.  Re-order the columns to the new standard format.

It performs a mandatory backup of the original file before overwriting it.
"""

import logging
import os
import re
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

# --- File Paths ---
EMINENCE_SCORES_PATH = Path("data/foundational_assets/eminence_scores.csv")
ELIGIBLE_CANDIDATES_PATH = Path("data/intermediate/adb_eligible_candidates.txt")


def main():
    """Main function to execute the patch."""
    print(f"\n{Fore.YELLOW}--- Starting Eminence Scores Patch ---")

    for path in [EMINENCE_SCORES_PATH, ELIGIBLE_CANDIDATES_PATH]:
        if not path.exists():
            logging.error(f"Required file not found: {path}. Cannot proceed.")
            sys.exit(1)

    # --- Step 1: Mandatory Backup ---
    try:
        backup_dir = Path("data/backup")
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = (
            backup_dir / f"{EMINENCE_SCORES_PATH.stem}.{timestamp}.patch.bak"
        )
        shutil.copy2(EMINENCE_SCORES_PATH, backup_path)
        logging.info(f"Successfully created backup at: {backup_path}")
    except (IOError, OSError) as e:
        logging.error(f"{Fore.RED}Failed to create backup file: {e}")
        sys.exit(1)

    # --- Step 2: Load and Merge Data ---
    logging.info(f"Loading {EMINENCE_SCORES_PATH.name}...")
    eminence_df = pd.read_csv(EMINENCE_SCORES_PATH)

    logging.info(f"Loading {ELIGIBLE_CANDIDATES_PATH.name} to source birth years...")
    candidates_df = pd.read_csv(ELIGIBLE_CANDIDATES_PATH, sep="\t", usecols=["idADB", "Year"])

    # Ensure keys are the same type for a clean merge
    eminence_df["idADB"] = eminence_df["idADB"].astype(str)
    candidates_df["idADB"] = candidates_df["idADB"].astype(str)

    # Merge to bring the 'Year' column into the eminence data
    merged_df = pd.merge(eminence_df, candidates_df, on="idADB", how="left")
    
    # --- Step 3: Populate BirthYear and Clean Names ---
    # Create the new 'BirthYear' column from the authoritative 'Year' column
    merged_df["BirthYear"] = merged_df["Year"].astype('Int64').astype(str).replace('<NA>', '')

    names_cleaned_count = 0
    for index, row in merged_df.iterrows():
        name = str(row["Name"])
        # Find a year in parentheses anywhere in the name string
        match = re.search(r"\s*\((\d{4})\)", name)
        if match:
            # The year in the name is for disambiguation; it's the source of truth
            year_in_name = match.group(1)
            clean_name = re.sub(r"\s*\(\d{4}\)\s*", " ", name).strip()
            
            # Update the DataFrame with the cleaned name and the year from the name
            merged_df.at[index, "Name"] = clean_name
            merged_df.at[index, "BirthYear"] = year_in_name
            names_cleaned_count += 1
            
    logging.info(f"Found and cleaned {names_cleaned_count} names with appended birth years.")

    # --- Step 4: Re-order columns and Save ---
    final_columns = ["Index", "idADB", "Name", "BirthYear", "EminenceScore"]
    
    # Drop the temporary 'Year' column
    final_df = merged_df[final_columns]

    final_df.to_csv(EMINENCE_SCORES_PATH, index=False, float_format="%.2f")
    logging.info(f"Successfully overwrote {EMINENCE_SCORES_PATH.name} with cleaned and enriched data.")

    print(f"\n{Fore.GREEN}Patch complete. ✨")
    print()


if __name__ == "__main__":
    main()

# === End of src/utils/patch_eminence_scores.py ===
