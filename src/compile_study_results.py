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
# Filename: src/compile_study_results.py

"""
Study-Level Results Compiler.

This script aggregates results from all individual experiment directories within
a single study into a unified `STUDY_results.csv` file.

It takes a study directory as input, searches its subdirectories for all
`EXPERIMENT_results.csv` files, and concatenates them into a single,
master dataset for the entire study.

This is the final data preparation step before running the main statistical
analysis with `study_analyzer.py`. It is typically called by the main
`process_study.ps1` user entry point.

Usage:
    python src/compile_study_results.py /path/to/study_directory
"""

import os
import sys
import pandas as pd
import logging
import argparse
import glob

logging.basicConfig(level=logging.INFO, format='%(message)s')

try:
    from config_loader import APP_CONFIG, get_config_list
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_list

def write_summary_csv(output_path, results_list):
    """Writes a list of result dictionaries to a structured CSV file."""
    if not results_list:
        logging.warning(f"No results to write to {output_path}.")
        return

    fieldnames = get_config_list(APP_CONFIG, 'Schema', 'csv_header_order')
    if not fieldnames:
        logging.error("FATAL: 'csv_header_order' not found in config.ini. Cannot write CSV.")
        sys.exit(1)

    df = pd.DataFrame(results_list)
    # Ensure all required columns from the schema exist, adding any that are missing
    for col in fieldnames:
        if col not in df.columns:
            df[col] = pd.NA
    
    # Reorder the DataFrame according to the schema
    df = df[fieldnames]
    df.to_csv(output_path, index=False)
    logging.info(f"  -> Generated study summary:\n    {output_path} ({len(df)} rows)")

def main():
    parser = argparse.ArgumentParser(description="Compile all experiment results for a single study.")
    parser.add_argument("study_directory", help="The path to the study directory containing experiment subfolders.")
    args = parser.parse_args()

    if not os.path.isdir(args.study_directory):
        logging.error(f"Error: The specified directory does not exist: {args.study_directory}")
        sys.exit(1)

    # Search recursively for any EXPERIMENT_results.csv files within the study directory
    search_pattern = os.path.join(args.study_directory, '**', 'EXPERIMENT_results.csv')
    experiment_files = glob.glob(search_pattern, recursive=True)

    if not experiment_files:
        logging.warning(f"No 'EXPERIMENT_results.csv' files found in subdirectories of {args.study_directory}. Nothing to compile.")
        sys.exit(0)
    
    logging.info(f"Found {len(experiment_files)} experiment result files to compile.")

    all_experiment_data = []
    for f in experiment_files:
        try:
            df = pd.read_csv(f)
            if not df.empty:
                all_experiment_data.append(df)
        except pd.errors.EmptyDataError:
            logging.warning(f"  - Warning: Skipping empty results file: {f}")
        except Exception as e:
            logging.error(f"  - Error: Could not read or process {f}. Reason: {e}")
            
    if not all_experiment_data:
        logging.error("No valid data could be read from any experiment files. Halting.")
        sys.exit(1)

    study_df = pd.concat(all_experiment_data, ignore_index=True)

    output_filename = "STUDY_results.csv"
    output_path = os.path.join(args.study_directory, output_filename)
    
    write_summary_csv(output_path, study_df.to_dict('records'))
    
    print("\nStudy compilation complete.")

if __name__ == "__main__":
    main()

# === End of src/compile_study_results.py ===
