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
Selects eligible candidates for LL-M scoring from the raw ADB data export.

This script serves as a key filtering stage in the data preparation pipeline. It
takes the raw data dump and the validation report to produce a clean list of all
subjects who are potentially viable for the study. This pre-filtering ensures
that subsequent, expensive LLM-based scoring is only performed on high-quality,
valid data.

Key Features:
-   **Sandbox-Aware**: Fully supports sandboxed execution via a `--sandbox-path`
    argument for isolated testing.
-   **Robust Filtering**: Applies a series of deterministic quality checks:
    -   Excludes non-person "Research" entries.
    -   Keeps only subjects with a final validation status of 'OK'.
    -   Filters by birth year (1900-1999).
    -   Validates the birth time format.
-   **Deduplication**: Uses a normalized name and birth date to identify and
    remove duplicate entries.
-   **Resumability**: Can be safely re-run, as it will only append newly
    eligible candidates that are not already present in the output file.
"""

import argparse
import logging
import os
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


def backup_and_overwrite(file_path: Path):
    """Creates a backup of the file before overwriting."""
    from config_loader import get_path, PROJECT_ROOT
    try:
        backup_dir = Path(get_path('data/backup'))
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{file_path.stem}.{timestamp}{file_path.suffix}.bak"
        shutil.copy2(file_path, backup_path)
        display_backup_path = os.path.relpath(backup_path, PROJECT_ROOT)
        print(f"\n{Fore.CYAN}Created backup of existing file at: {display_backup_path}{Fore.RESET}")
    except (IOError, OSError) as e:
        logging.error(f"{Fore.RED}Failed to create backup file: {e}")
        sys.exit(1)

def finalize_and_report(output_path: Path, new_count: int, was_interrupted: bool = False):
    """Generates the final summary and prints the status message."""
    from config_loader import PROJECT_ROOT
    display_path = os.path.relpath(output_path, PROJECT_ROOT)
    try:
        total_eligible = len(pd.read_csv(output_path, sep='\t'))
        summary_msg = f"Found {new_count:,} new eligible candidates. Total now saved: {total_eligible:,}."
    except (FileNotFoundError, pd.errors.EmptyDataError):
        summary_msg = f"Saved {new_count:,} eligible candidates to new file."

    if was_interrupted:
        print(f"\n{Fore.YELLOW}WARNING: Processing interrupted by user.")
        print(summary_msg)
        print(f"{Fore.CYAN}Partial results saved to: {display_path} ✨{Fore.RESET}\n")
        os._exit(1)
    else:
        try:
            total_eligible = len(pd.read_csv(output_path, sep='\t'))
            key_metric = f"Found {total_eligible:,} eligible candidates"
        except (FileNotFoundError, pd.errors.EmptyDataError):
            key_metric = f"Found {new_count:,} eligible candidates"

        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Eligible candidates saved to: {display_path}{Fore.RESET}")
        print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. Selection completed successfully. ✨{Fore.RESET}\n")


def normalize_name_for_deduplication(series: pd.Series) -> pd.Series:
    """
    Normalizes a name series for robust duplicate detection.
    It strips parenthetical content and sorts name parts alphabetically.
    """
    def process_name(raw_name):
        if not isinstance(raw_name, str):
            return tuple()
        name = re.sub(r"\(.*\)", "", raw_name).strip()
        parts = re.split(r"[,\s-]+", name)
        return tuple(sorted([part.lower() for part in parts if part]))

    return series.apply(process_name)

def main():
    """Main function to orchestrate the filtering process."""
    parser = argparse.ArgumentParser(
        description="Filter raw ADB data to generate a list of eligible candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--sandbox-path", help="Specify a sandbox directory for all file operations.")
    parser.add_argument("--force", action="store_true", help="Force overwrite of the output file if it exists.")
    args = parser.parse_args()

    if args.sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(args.sandbox_path)

    from config_loader import get_path, PROJECT_ROOT

    input_path = Path(get_path("data/sources/adb_raw_export.txt"))
    validation_path = Path(get_path("data/reports/adb_validation_report.csv"))
    output_path = Path(get_path("data/intermediate/adb_eligible_candidates.txt"))

    if not args.force and output_path.exists():
        output_mtime = os.path.getmtime(output_path)
        input_stale = os.path.exists(input_path) and os.path.getmtime(input_path) > output_mtime
        validation_stale = os.path.exists(validation_path) and os.path.getmtime(validation_path) > output_mtime
        if input_stale or validation_stale:
            print(f"{Fore.YELLOW}\nInput file(s) are newer than the existing output. Stale data detected.")
            print("Automatically re-running full selection process...")
            backup_and_overwrite(output_path)
            args.force = True

    try:
        raw_df = pd.read_csv(input_path, sep='\t', dtype={'idADB': str})
        # The validation report is now the source of truth for Entry_Type
        validation_df = pd.read_csv(validation_path, usecols=['idADB', 'Status', 'Entry_Type'], dtype={'idADB': str})
    except FileNotFoundError as e:
        logging.error(f"{Fore.RED}FATAL: Input file not found: {e.filename}")
        sys.exit(1)

    # --- Step 1: Find ALL theoretically eligible candidates from source ---
    print(f"\n{Fore.YELLOW}--- Analyzing Full Dataset ---")
    # Join the raw data with the validation report to get the Status and Entry_Type for each subject.
    df = pd.merge(raw_df, validation_df, on="idADB", how="left")

    # The core filter: only keep 'Person' entries with a final status of 'OK'.
    # Research entries (status 'VALID') and other failures are now correctly excluded.
    df = df[(df['Status'] == 'OK') & (df['Entry_Type'] == 'Person')]
    logging.info(f"Initial filtering complete. {len(df)} records passed status check.")
    
    # --- Step 2: Apply all deterministic filters ---
    df['Year'] = pd.to_numeric(df['Year'], errors='coerce')
    df.dropna(subset=['Year'], inplace=True)
    df['Year'] = df['Year'].astype(int)
    df = df[df['Year'].between(1900, 1999)]
    df = df[df['Time'].astype(str).str.match(r"^\d{1,2}:\d{2}$", na=False)]
    df['FullName'] = df['LastName'].fillna('') + ", " + df['FirstName'].fillna('')
    df['NormalizedName'] = normalize_name_for_deduplication(df['FullName'])
    df['BirthDate'] = df['Year'].astype(str) + '-' + df['Month'].astype(str) + '-' + df['Day'].astype(str)
    df.drop_duplicates(subset=['NormalizedName', 'BirthDate'], keep='first', inplace=True)
    all_eligible_df = df[raw_df.columns].copy()
    logging.info(f"Found {len(all_eligible_df):,} total potential candidates in source files.")

    # --- Step 3: Determine which candidates are new ---
    processed_ids = set()
    if not args.force and output_path.exists():
        try:
            processed_df = pd.read_csv(output_path, sep='\t', usecols=['idADB'], dtype={'idADB': str})
            processed_ids = set(processed_df['idADB'])
        except (pd.errors.EmptyDataError, FileNotFoundError, KeyError):
            pass
    
    final_candidates_to_save = all_eligible_df[~all_eligible_df['idADB'].isin(processed_ids)]

    # --- Step 4: Decide whether to run ---
    if final_candidates_to_save.empty and not args.force:
        display_path = os.path.relpath(output_path, PROJECT_ROOT)
        print(f"\n{Fore.YELLOW}WARNING: The candidates file at '{display_path}' is already up to date. ✨")
        print(f"{Fore.YELLOW}If you decide to go ahead with updating the list of candidates, a backup of the the existing file will be created first.{Fore.RESET}")
        confirm = input("Do you wish to proceed? (Y/N): ").lower().strip()
        if confirm == 'y':
            backup_and_overwrite(output_path)
            args.force = True
        else:
            print(f"\n{Fore.YELLOW}Operation cancelled by user.\n")
            sys.exit(0)

    # --- Step 5: Execute ---
    if args.force:
        # If forcing, the "new" candidates are ALL eligible candidates
        final_candidates_to_save = all_eligible_df
        print(f"\n{Fore.YELLOW}--- Reprocessing Full Dataset ---{Fore.RESET}")
        logging.info(f"Processing all {len(final_candidates_to_save)} eligible candidates.")
    else:
        logging.info(f"Resuming: Processing {len(final_candidates_to_save)} new eligible candidates.")
    
    # --- Step 6: Save ---
    is_new_file = not output_path.exists() or args.force
    final_candidates_to_save.to_csv(
        output_path, sep='\t', index=False, mode='w' if is_new_file else 'a', header=is_new_file
    )
    
    finalize_and_report(output_path, len(final_candidates_to_save))


if __name__ == "__main__":
    main()

# === End of src/select_eligible_candidates.py ===
