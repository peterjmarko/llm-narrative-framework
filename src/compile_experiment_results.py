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
# Filename: src/compile_experiment_results.py

"""
Experiment-Level Results Compiler.

This script compiles results from all individual replication runs within a single
experiment directory into a unified `EXPERIMENT_results.csv` file.

It takes an experiment directory as input, searches its subdirectories for all
`REPLICATION_results.csv` files, and concatenates them into a single,
comprehensive dataset for that experiment.

This script is called by `experiment_manager.py` during the finalization stage
of an experiment run.

Usage:
    python src/compile_experiment_results.py /path/to/experiment_directory
"""

import os
import sys
import pandas as pd
import logging
import argparse
import glob

logging.basicConfig(level=logging.INFO, format='%(message)s')

try:
    from config_loader import APP_CONFIG, get_config_list, PROJECT_ROOT
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_list, PROJECT_ROOT

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
    for col in fieldnames:
        if col not in df.columns:
            df[col] = pd.NA
    
    df = df[fieldnames]
    df.to_csv(output_path, index=False)
    relative_path = os.path.relpath(output_path, PROJECT_ROOT)
    logging.info(f"  -> Generated experiment summary:\n    {relative_path} ({len(df)} rows)")

def main():
    parser = argparse.ArgumentParser(description="Compile all replication results for a single experiment.")
    parser.add_argument("experiment_directory", help="The path to the experiment directory containing run_* subfolders.")
    args = parser.parse_args()

    if not os.path.isdir(args.experiment_directory):
        logging.error(f"Error: The specified directory does not exist: {args.experiment_directory}")
        sys.exit(1)

    search_pattern = os.path.join(args.experiment_directory, 'run_*', 'REPLICATION_results.csv')
    replication_files = glob.glob(search_pattern)

    if not replication_files:
        logging.warning(f"No 'REPLICATION_results.csv' files found in subdirectories of {args.experiment_directory}. Nothing to compile.")
        sys.exit(0)
        return  # Eject for testability
    
    logging.info(f"Found {len(replication_files)} replication result files to compile.")

    all_replication_data = []
    for f in replication_files:
        try:
            df = pd.read_csv(f)
            if not df.empty:
                all_replication_data.append(df)
        except pd.errors.EmptyDataError:
            logging.warning(f"  - Warning: Skipping empty results file: {f}")
        except Exception as e:
            logging.error(f"  - Error: Could not read or process {f}. Reason: {e}")
            
    if not all_replication_data:
        logging.error("No valid data could be read from any replication files. Halting.")
        sys.exit(1)
        return  # Eject for testability

    experiment_df = pd.concat(all_replication_data, ignore_index=True)

    output_filename = "EXPERIMENT_results.csv"
    output_path = os.path.join(args.experiment_directory, output_filename)
    
    write_summary_csv(output_path, experiment_df.to_dict('records'))
    
    print("\nExperiment compilation complete.")

if __name__ == "__main__":
    main()

# === End of src/compile_experiment_results.py ===
