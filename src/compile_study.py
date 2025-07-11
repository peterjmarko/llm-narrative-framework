#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/compile_study.py

"""
Compiles all experiment results within a study into a single master CSV file.
"""

import argparse
import os
import sys
import pandas as pd
import glob
import logging
from results_compiler import write_summary_csv

logging.basicConfig(level=logging.INFO, format='%(message)s')

def main():
    parser = argparse.ArgumentParser(description="Compiles a study's experiments into STUDY_results.csv.")
    parser.add_argument("study_directory", help="The path to the study directory containing experiment subfolders.")
    args = parser.parse_args()

    if not os.path.isdir(args.study_directory):
        logging.error(f"Error: Provided path is not a valid directory: {args.study_directory}")
        sys.exit(1)
        return

    print(f"Processing study directory: {os.path.basename(args.study_directory)}")

    experiment_csvs = glob.glob(os.path.join(args.study_directory, '*', 'EXPERIMENT_results.csv'))
    
    if not experiment_csvs:
        logging.warning("  - Warning: No 'EXPERIMENT_results.csv' files found in any subdirectories. Nothing to compile.")
        return # Return is fine here, as it's a "nothing to do" scenario, not a critical error.

    all_dfs = []
    for csv_path in experiment_csvs:
        try:
            df = pd.read_csv(csv_path)
            if not df.empty:
                all_dfs.append(df)
            else:
                # Log if a CSV file was read but contained no data (empty DataFrame)
                logging.warning(f"  - Skipping empty CSV (no data rows): {csv_path}")
        except pd.errors.EmptyDataError:
            logging.warning(f"  - Skipping empty experiment CSV: {csv_path}")
        except Exception as e:
            logging.error(f"  - Error reading {csv_path}: {e}")

    if not all_dfs:
        logging.error("  - Error: All found experiment CSVs were empty or unreadable.")
        sys.exit(1) # Exit before attempting concat on empty list
        return

    final_df = pd.concat(all_dfs, ignore_index=True)
    output_path = os.path.join(args.study_directory, "STUDY_results.csv")
    write_summary_csv(output_path, final_df.to_dict('records'))

if __name__ == "__main__":
    main()

# === End of src/compile_study.py ===