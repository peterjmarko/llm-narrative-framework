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
Performs the final step of the LLM-based Candidate Selection stage.

This script can operate in two modes based on the `bypass_candidate_selection`
flag in `config.ini`:

-   **Default Mode:** Filters the "eligible candidates" list, retaining only
    subjects present in the `ocean_scores.csv` file. This produces the final,
    LLM-selected subject pool.
-   **Bypass Mode:** Uses the entire "eligible candidates" list as the final
    subject pool, skipping the LLM-based selection.

In both modes, it then performs final transformations: resolving country codes,
merging eminence scores for sorting, and re-indexing the final list.

Inputs:
  - `data/intermediate/adb_eligible_candidates.txt`: The full list of subjects
    from the "Candidate Qualification" stage.
  - `data/foundational_assets/ocean_scores.csv`: (Default Mode) The definitive
    subject set determined by OCEAN scoring.
  - `data/foundational_assets/eminence_scores.csv`: (Default Mode) Used for sorting.
  - `data/foundational_assets/country_codes.csv`: The mapping file for country
    abbreviations.

Output:
  - `data/intermediate/adb_final_candidates.txt`: The final, sorted list
    of subjects, ready for the "Profile Generation" stage.
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
from collections import deque

# Ensure the src directory is in the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config_loader import APP_CONFIG, get_config_value, get_path  # noqa: E402
from utils.file_utils import backup_and_remove  # noqa: E402

# Initialize colorama
init(autoreset=True, strip=False)

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO, format="%(message)s")

def calculate_average_variance(df: pd.DataFrame) -> float:
    """Calculates the average variance across the five OCEAN trait columns."""
    ocean_cols = ["Openness", "Conscientiousness", "Extraversion", "Agreeableness", "Neuroticism"]
    df = df.copy()
    for col in ocean_cols:
        if col not in df.columns: return 0.0
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df.dropna(subset=ocean_cols, inplace=True)
    if len(df) < 2: return 0.0
    return df[ocean_cols].var().mean()


def main():
    """Main function to orchestrate the final candidate selection."""
    parser = argparse.ArgumentParser(
        description="Select and transform the final set of candidates.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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

    # Define all file paths from arguments
    eligible_path = Path(get_path("data/intermediate/adb_eligible_candidates.txt"))
    country_codes_path = Path(get_path("data/foundational_assets/country_codes.csv"))
    output_path = Path(get_path("data/intermediate/adb_final_candidates.txt"))
    
    # Conditionally define paths for scoring files
    # Read bypass config after sandbox is established
    if args.sandbox_path:
        import configparser
        sandbox_config_path = Path(args.sandbox_path) / "config.ini"
        if sandbox_config_path.exists():
            sandbox_config = configparser.ConfigParser()
            sandbox_config.read(sandbox_config_path)
            bypass_candidate_selection = sandbox_config.get("DataGeneration", "bypass_candidate_selection", fallback="false").lower() == 'true'
        else:
            bypass_candidate_selection = False
    else:
        bypass_candidate_selection = get_config_value(APP_CONFIG, "DataGeneration", "bypass_candidate_selection", "false").lower() == 'true'
    if bypass_candidate_selection:
        input_files = [eligible_path, country_codes_path]
    else:
        ocean_path = Path(get_path("data/foundational_assets/ocean_scores.csv"))
        eminence_path = Path(get_path("data/foundational_assets/eminence_scores.csv"))
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
        backup_and_remove(output_path)

    print(f"\n{Fore.YELLOW}--- Loading Files ---")

    try:
        eligible_df = pd.read_csv(eligible_path, sep="\t")
        country_codes_df = pd.read_csv(country_codes_path)
        logging.info(f"Loaded {len(eligible_df):,} records from {eligible_path.name}.")
        logging.info(f"Loaded {len(country_codes_df):,} mappings from {country_codes_path.name}.")
        
        if not bypass_candidate_selection:
            eminence_df = pd.read_csv(eminence_path)
            ocean_df = pd.read_csv(ocean_path)
            logging.info(f"Loaded {len(eminence_df):,} records from {eminence_path.name}.")
            logging.info(f"Loaded {len(ocean_df):,} records from {ocean_path.name} (defines final set).")
    except FileNotFoundError as e:
        logging.error(f"{Fore.RED}FATAL: Input file not found: {e.filename}")
        sys.exit(1)

    print(f"\n{Fore.YELLOW}--- Selecting and Transforming Final Candidates ---")

    if bypass_candidate_selection:
        logging.info("Bypass mode is active: using all eligible candidates as the final set.")
        final_df = eligible_df.copy()
        # Add a placeholder eminence score for sorting if it doesn't exist
        if 'EminenceScore' not in final_df.columns:
            final_df['EminenceScore'] = 0
    else:
        # Step 1: Apply variance-based cutoff to the OCEAN scores to determine the final cohort size
        logging.info("Applying variance-based cutoff to determine final subject count...")
        
        # Load cutoff parameters from config
        benchmark_pop_size = get_config_value(APP_CONFIG, 'DataGeneration', 'benchmark_population_size', 500, int)
        cutoff_start_point = get_config_value(APP_CONFIG, 'DataGeneration', 'cutoff_start_point', 600, int)
        analysis_window = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_analysis_window', 100, int)
        check_window = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_check_window', 5, int)
        trigger_count = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_trigger_count', 4, int)
        cutoff_pct = get_config_value(APP_CONFIG, 'DataGeneration', 'variance_cutoff_percentage', 0.40, float)
        
        final_count = len(ocean_df) # Default to all subjects
        
        if len(ocean_df) >= cutoff_start_point:
            benchmark_variance = calculate_average_variance(ocean_df.head(benchmark_pop_size))
            logging.info(f"Benchmark variance from top {benchmark_pop_size} subjects: {benchmark_variance:.4f}")
            
            last_checks = deque(maxlen=check_window)
            
            for i in range(cutoff_start_point, len(ocean_df), analysis_window):
                window_df = ocean_df.iloc[i - analysis_window : i]
                if len(window_df) < analysis_window: continue

                v_avg = calculate_average_variance(window_df)
                is_met = v_avg < (cutoff_pct * benchmark_variance)
                last_checks.append(is_met)
                
                if sum(last_checks) >= trigger_count:
                    final_count = i - analysis_window
                    logging.info(f"{Fore.YELLOW}Cutoff condition met. Final subject count set to {final_count}.")
                    break
        else:
            logging.info("Not enough subjects to apply variance cutoff. Using all available subjects.")

        ocean_df = ocean_df.head(final_count)
        
        # Step 2: Filter the main eligible list by the now-finalized OCEAN set
        ocean_subject_ids = set(ocean_df["idADB"])
        final_df = eligible_df[eligible_df["idADB"].isin(ocean_subject_ids)].copy()
        logging.info(f"Filtered to {len(final_df):,} final candidates based on OCEAN scores.")

    # Step 3: Resolve Country Codes
    country_map = dict(zip(country_codes_df["Abbreviation"], country_codes_df["Country"]))
    final_df["Country"] = final_df["CountryState"].map(country_map)
    unmapped_count = final_df["Country"].isna().sum()
    if unmapped_count > 0:
        logging.warning(f"Could not map {unmapped_count} 'CountryState' values. 'Country' will be blank for these.")
    final_df["Country"] = final_df["Country"].fillna("")
    logging.info("Resolved 'CountryState' abbreviations to full 'Country' names.")
    
    # Step 3: Merge with eminence scores and sort
    final_df["idADB"] = final_df["idADB"].astype(str)
    if not bypass_candidate_selection:
        eminence_df["idADB"] = eminence_df["idADB"].astype(str)
        # Ensure we only merge scores for the subjects who made the final cut
        final_ids = set(final_df['idADB'])
        eminence_scores_to_merge = eminence_df[eminence_df['idADB'].isin(final_ids)]
        final_df = pd.merge(final_df, eminence_scores_to_merge[["idADB", "EminenceScore"]], on="idADB", how="left")
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
    
    # In bypass mode, include EminenceScore in the final output
    if bypass_candidate_selection:
        final_column_order.append('EminenceScore')
    
    final_df = final_df[final_column_order]

    # --- Save the final list ---
    final_df.to_csv(output_path, sep="\t", index=False, encoding="utf-8")

    # To get a clean project-relative path, find the project root
    project_root = Path.cwd()
    while not (project_root / ".git").exists() and project_root != project_root.parent:
        project_root = project_root.parent
    
    try:
        display_path = output_path.relative_to(project_root)
    except ValueError:
        display_path = output_path # Fallback to absolute if not within project

    print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
    print(f"{Fore.CYAN} - Final candidates list saved to: {display_path}{Fore.RESET}")
    
    final_count = len(final_df)
    key_metric = f"Final Count: {final_count:,} subjects"

    if final_count == 0:
        print(f"\n{Fore.RED}FAILURE: {key_metric}. No final candidates were selected.{Fore.RESET}\n")
    else:
        print(
            f"\n{Fore.GREEN}SUCCESS: {key_metric}. Final candidate selection "
            f"completed successfully.{Fore.RESET}\n"
        )


if __name__ == "__main__":
    main()

# === End of src/select_final_candidates.py ===
