#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/compile_replication.py

"""
Compiles the results of a single replication run into a CSV file.
"""

import argparse
import os
import sys
import glob
import logging
import re
from results_compiler import parse_metrics_json, parse_config_params, write_summary_csv

logging.basicConfig(level=logging.INFO, format='%(message)s')

def main():
    parser = argparse.ArgumentParser(description="Compiles a single replication's report into REPLICATION_results.csv.")
    parser.add_argument("run_directory", help="The path to the specific run_* directory.")
    args = parser.parse_args()

    if not os.path.isdir(args.run_directory) or not os.path.basename(args.run_directory).startswith('run_'):
        logging.error(f"Error: Provided path is not a valid run_* directory: {args.run_directory}")
        sys.exit(1)
        return

    run_dir_name = os.path.basename(args.run_directory)
    print(f"Processing replication directory: {run_dir_name}")

    report_files = glob.glob(os.path.join(args.run_directory, 'replication_report_*.txt'))
    config_path = os.path.join(args.run_directory, 'config.ini.archived')

    if not report_files:
        logging.error(f"  - Error: No 'replication_report_*.txt' found in {run_dir_name}.")
        sys.exit(1)
        return
    if not os.path.exists(config_path):
        logging.error(f"  - Error: 'config.ini.archived' not found in {run_dir_name}.")
        sys.exit(1)
        return

    with open(report_files[0], 'r', encoding='utf-8') as f:
        content = f.read()
    
    metrics = parse_metrics_json(content)
    if not metrics:
        logging.error(f"  - Error: Could not parse metrics from report in {run_dir_name}.")
        sys.exit(1)
        return

    run_params = parse_config_params(config_path)
    rep_match = re.search(r'rep-(\d+)', run_dir_name)
    run_params['replication'] = int(rep_match.group(1)) if rep_match else 0
    
    final_data = {'run_directory': run_dir_name}
    final_data.update(run_params)
    final_data.update(metrics)

    output_path = os.path.join(args.run_directory, "REPLICATION_results.csv")
    write_summary_csv(output_path, [final_data])

if __name__ == "__main__":
    main()

# === End of src/compile_replication.py ===