#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: src/select_final_candidates.py

"""
Determines the final subject pool size and performs final transformations.

This script is the final, decisive step in the "LLM-based Candidate Selection"
stage. It can operate in two modes based on the `bypass_candidate_selection`
flag in `config.ini`:

-   **Default Mode:** Performs a sophisticated analysis on the full set of
    OCEAN scores. It calculates a cumulative personality variance curve, finds
    the "point of diminishing returns" using slope analysis, and determines an
    optimal, data-driven cohort size. It then filters the list to this size.
-   **Bypass Mode:** Skips the LLM-based selection and uses the entire
    "eligible candidates" list as the final subject pool.

In both modes, it performs final data transformations: resolving country codes,
merging eminence scores for sorting, and re-indexing the final list.

Inputs:
  - `data/intermediate/adb_eligible_candidates.txt`: The full list of subjects
    from the "Candidate Qualification" stage.
  - `data/foundational_assets/ocean_scores.csv`: (Default Mode) The full set of
    OCEAN scores for all eligible candidates.
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
import numpy as np
from colorama import Fore, init
import matplotlib.pyplot as plt
from tqdm import tqdm

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


def generate_variance_plot(x_values, raw_variances, smoothed_variances, cutoff_point, search_start, smoothing_window_size, output_path, interactive=True):
    """Generates and saves a diagnostic plot of the variance curve analysis."""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.figure(figsize=(12, 7))

    plt.plot(x_values, raw_variances, color='lightblue', alpha=0.7, label='Raw Cumulative Variance')
    plt.plot(x_values, smoothed_variances, color='blue', linewidth=2, label=f'Smoothed Variance ({smoothing_window_size}-pt MA)')
    
    plt.axvline(x=search_start, color='green', linestyle=':', linewidth=2, label=f'Search Start ({search_start})')
    plt.axvline(x=cutoff_point, color='red', linestyle='--', linewidth=2, label=f'Final Cutoff ({cutoff_point})')

    plt.title('Cumulative Personality Variance vs. Cohort Size', fontsize=16)
    plt.xlabel('Number of Subjects (Sorted by Eminence)', fontsize=12)
    plt.ylabel('Average Cumulative Variance', fontsize=12)
    plt.legend()
    plt.xlim(0, len(x_values) + 100)
    plt.tight_layout()

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150)
        logging.info(f"Diagnostic plot saved to '{output_path}'.")
        if interactive:
            plt.show()
    except Exception as e:
        logging.error(f"Failed to save or show plot: {e}")
    finally:
        plt.close()

def main():
    """Main function to orchestrate the final candidate selection."""
    os.system('')
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
    # Read config, prioritizing sandbox if it exists
    config = APP_CONFIG
    if args.sandbox_path:
        import configparser
        sandbox_config_path = Path(args.sandbox_path) / "config.ini"
        if sandbox_config_path.exists():
            config = configparser.ConfigParser()
            config.read(sandbox_config_path)

    bypass_candidate_selection = get_config_value(config, "DataGeneration", "bypass_candidate_selection", "false").lower() == 'true'

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
        from config_loader import PROJECT_ROOT
        relative_path = os.path.relpath(e.filename, PROJECT_ROOT)
        logging.error(f"{Fore.RED}FATAL: Input file not found: {relative_path}")
        sys.exit(1)

    print(f"\n{Fore.YELLOW}--- Selecting and Transforming Final Candidates ---")

    if bypass_candidate_selection:
        logging.info("Bypass mode is active: using all eligible candidates as the final set.")
        final_df = eligible_df.copy()
        # Add a placeholder eminence score for sorting if it doesn't exist
        if 'EminenceScore' not in final_df.columns:
            final_df['EminenceScore'] = 0
    else:
        # Step 1: Find the optimal cohort size using slope analysis of the variance curve
        logging.info("Applying slope analysis to determine final subject count...")

        # Load analysis parameters from config
        min_pop_size = get_config_value(config, "DataGeneration", "min_population_size", 100, int)
        search_start_point = get_config_value(config, "DataGeneration", "cutoff_search_start_point", 500, int)
        slope_threshold = get_config_value(config, "DataGeneration", "slope_threshold", -0.00001, float)
        smoothing_window = get_config_value(config, "DataGeneration", "smoothing_window_size", 100, int)

        final_count = len(ocean_df)  # Default to all subjects

        if len(ocean_df) < search_start_point:
            logging.warning(
                f"Not enough subjects ({len(ocean_df)}) to perform analysis beyond start point of {search_start_point}. "
                "Using all available subjects."
            )
        else:
            # Calculate the full cumulative average variance curve.
            x_values = np.array(range(2, len(ocean_df) + 1))
            variances = np.array([
                calculate_average_variance(ocean_df.head(i))
                for i in tqdm(x_values, desc="Calculating Variance Curve", ncols=100)
            ])
            
            # Smooth the variance curve to remove local noise and reveal the global trend.
            smoothed_variances = pd.Series(variances).rolling(window=smoothing_window, center=True).mean().bfill().ffill().to_numpy()

            # Calculate the gradient (slope) of the SMOOTHED curve.
            gradient = np.gradient(smoothed_variances, x_values)

            # Find the index corresponding to the search start point.
            start_index = np.where(x_values >= search_start_point)[0][0]

            # Find the first point *after* the start index where the slope flattens.
            cutoff_index = -1
            for i in range(start_index, len(gradient)):
                if gradient[i] > slope_threshold:
                    cutoff_index = i
                    break
            
            if cutoff_index != -1:
                final_count = x_values[cutoff_index]
                logging.info(
                    f"{Fore.YELLOW}Plateau detected. Optimal subject count set to {final_count}."
                )
            else:
                logging.warning(
                    "Could not find a plateau in the variance curve. Using all available subjects."
                )
            
            # Always generate the diagnostic plot (non-interactive)
            variance_plot_output = get_config_value(config, "DataGeneration", "variance_plot_output", "data/foundational_assets/variance_curve_analysis.png", str)
            plot_path = Path(get_path(variance_plot_output))
            generate_variance_plot(x_values, variances, smoothed_variances, final_count, search_start_point, smoothing_window, plot_path, interactive=False)

        ocean_df = ocean_df.head(final_count)

        # Step 2: Filter the main eligible list by the now-finalized OCEAN set
        ocean_subject_ids = set(ocean_df["idADB"])
        final_df = eligible_df[eligible_df["idADB"].isin(ocean_subject_ids)].copy()
        logging.info(
            f"Filtered to {len(final_df):,} final candidates based on optimal cohort size."
        )

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
    # To get a clean project-relative path, find the project root
    project_root = Path.cwd()
    while not (project_root / ".git").exists() and project_root != project_root.parent:
        project_root = project_root.parent
    
    try:
        display_path = output_path.relative_to(project_root)
    except ValueError:
        display_path = output_path # Fallback to absolute if not within project
    
    # Standardize path separators for consistent output
    display_path = str(display_path).replace('\\', '/')

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
