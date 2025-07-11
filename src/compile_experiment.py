#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/compile_experiment.py

"""
Compiles all replication results within an experiment into a single CSV file.
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
    parser = argparse.ArgumentParser(description="Compiles an experiment's replications into EXPERIMENT_results.csv.")
    parser.add_argument("experiment_directory", help="The path to the experiment directory containing run_* subfolders.")
    args = parser.parse_args()

    if not os.path.isdir(args.experiment_directory):
        logging.error(f"Error: Provided path is not a valid directory: {args.experiment_directory}")
        sys.exit(1)
        return

    print(f"Processing experiment directory: {os.path.basename(args.experiment_directory)}")

    replication_csvs = glob.glob(os.path.join(args.experiment_directory, 'run_*', 'REPLICATION_results.csv'))
    
    if not replication_csvs:
        logging.warning("  - Warning: No 'REPLICATION_results.csv' files found in any run_* subdirectories. Nothing to compile.")
        return # Return is fine here, as it's a "nothing to do" scenario, not a critical error.

    all_dfs = []
    for csv_path in replication_csvs:
        try:
            df = pd.read_csv(csv_path)
            if not df.empty:
                all_dfs.append(df)
            else:
                # Log if a CSV file was read but contained no data (empty DataFrame)
                logging.warning(f"  - Skipping empty CSV (no data rows): {csv_path}")
        except pd.errors.EmptyDataError:
            logging.warning(f"  - Skipping empty replication CSV: {csv_path}")
        except Exception as e:
            logging.error(f"  - Error reading {csv_path}: {e}")

    if not all_dfs:
        logging.error("  - Error: All found replication CSVs were empty or unreadable.")
        sys.exit(1) # Exit before attempting concat on empty list
        return
        
    final_df = pd.concat(all_dfs, ignore_index=True)
    output_path = os.path.join(args.experiment_directory, "EXPERIMENT_results.csv")
    write_summary_csv(output_path, final_df.to_dict('records'))

if __name__ == "__main__":
    main()

# === End of src/compile_experiment.py ===