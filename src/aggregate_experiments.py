#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
# Filename: src/experiment_aggregator.py

"""
Hierarchical Results Compiler for Study-Wide Analysis.

This script is the primary data aggregation tool in the analysis workflow.
It systematically transforms the raw output from numerous individual replication
runs into a clean, unified, and analysis-ready dataset.

Its core mechanism is a **bottom-up hierarchical compilation**:
1.  It performs a post-order traversal (`os.walk(..., topdown=False)`) of a
    given study directory.
2.  At the "leaf" level (individual `run_*` directories), it parses metrics
    from the final `replication_metrics.json` file and experimental parameters
    from the `config.ini.archived` file. It saves this as a single-row
    `REPLICATION_results.csv`.
3.  As it moves up the directory tree, it aggregates the summary CSVs from all
    its child directories. For example, an "experiment" directory will
    combine all the `REPLICATION_results.csv` files from its children into a
    single, comprehensive `EXPERIMENT_results.csv`.
4.  This process continues until it reaches the top-level directory, where it
    creates a master `STUDY_results.csv` containing the data from every
    valid replication in the entire study.

The final output is a set of perfectly structured, level-aware CSV files that
create a fully auditable data archive, ready for the final statistical
analysis phase (`analyze_study_results.py`).

Usage (typically called by process_study.ps1):
    python src/compile_study_results.py /path/to/study_directory
"""

import os
import sys
import pandas as pd
import logging
import json
import re
import configparser
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

def _flatten_bias_metrics(data):
    """
    Finds a nested 'positional_bias_metrics' dictionary and flattens its
    contents into the top-level dictionary for easier CSV conversion.
    """
    if data and 'positional_bias_metrics' in data and isinstance(data.get('positional_bias_metrics'), dict):
        # Remove the nested dictionary from the main data
        bias_metrics = data.pop('positional_bias_metrics')
        # Add its items to the main data.
        data.update(bias_metrics)
    return data

def write_summary_csv(output_path, results_list):
    if not results_list:
        logging.warning(f"No results to write to {output_path}.")
        return
    
    fieldnames = get_config_list(APP_CONFIG, 'Schema', 'csv_header_order')
    if not fieldnames:
        logging.error("FATAL: 'csv_header_order' not found in config.ini. Cannot write CSV.")
        return

    df = pd.DataFrame(results_list)
    for col in fieldnames:
        if col not in df.columns:
            df[col] = pd.NA
    
    df = df[fieldnames]
    df.to_csv(output_path, index=False)
    logging.info(f"  -> Generated summary:\n    {output_path} ({len(df)} rows)")

def run_hierarchical_mode(base_dir):
    logging.info(f"Running in hierarchical mode on:\n{base_dir}")
    for current_dir, subdirs, files in os.walk(base_dir, topdown=False):
        print(f"\nProcessing directory:\n{current_dir}")
        level_results = []
        
        # In a run directory, we expect to find the final metrics JSON file.
        is_run_dir = os.path.basename(current_dir).startswith('run_')
        metrics_filepath = os.path.join(current_dir, "analysis_inputs", "replication_metrics.json")

        if is_run_dir and os.path.exists(metrics_filepath):
            run_dir_name = os.path.basename(current_dir)
            logging.info(f"  - Found metrics JSON in run folder: {run_dir_name}")
            
            # Manifest is in the experiment's root (parent of the run directory)
            manifest_path = os.path.join(os.path.dirname(current_dir), 'experiment_manifest.json')

            if not os.path.exists(manifest_path):
                logging.warning(f"    - Warning: 'experiment_manifest.json' not found for run {run_dir_name}. Skipping.")
                continue
            
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                run_params = manifest.get('parameters', {})
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"    - Warning: Could not read or parse manifest for {run_dir_name}. Error: {e}. Skipping.")
                continue

            try:
                with open(metrics_filepath, 'r', encoding='utf-8') as f:
                    metrics = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"    - Warning: Could not read or parse {os.path.basename(metrics_filepath)}. Error: {e}. Skipping.")
                continue

            # Flatten the nested bias metrics for easier CSV output
            metrics = _flatten_bias_metrics(metrics)
            if not metrics:
                logging.warning(f"    - Warning: Parsed metrics are empty. Skipping.")
                continue

            # Get replication number from the directory name
            rep_match = re.search(r'rep-(\d+)', run_dir_name)
            
            # Combine all data into a single record
            run_data = {'run_directory': run_dir_name}
            run_data.update(run_params) # Add parameters from manifest
            run_data.update(metrics)    # Add metrics from JSON
            run_data['replication'] = int(rep_match.group(1)) if rep_match else 0
            
            # Rename keys to match the CSV schema in config.ini
            run_data['model'] = run_data.pop('model_name', None)
            run_data['k'] = run_data.pop('group_size', None)
            run_data['m'] = run_data.pop('num_trials', None)
            
            level_results.append(run_data)

        for subdir_name in subdirs:
            summary_path = None
            # Look for summary files in a specific order, from most specific to most general
            for filename in ["REPLICATION_results.csv", "EXPERIMENT_results.csv", "final_summary_results.csv"]:
                path = os.path.join(current_dir, subdir_name, filename)
                if os.path.exists(path):
                    summary_path = path
                    break
            
            if summary_path:
                logging.info(f"  - Aggregating results from: {os.path.join(subdir_name, os.path.basename(summary_path))}")
                try:
                    df_sub = pd.read_csv(summary_path)
                    if not df_sub.empty:
                        level_results.extend(df_sub.to_dict('records'))
                except pd.errors.EmptyDataError:
                    logging.warning(f"    - Warning: {summary_path} is empty. Skipping.")
                except Exception as e:
                    logging.warning(f"    - Warning: Could not read or process {summary_path}. Error: {e}")

        if level_results:
            # Determine output filename based on directory type
            output_filename = "STUDY_results.csv"  # Default for Study level and above
            
            # A directory is a Replication directory if its name starts with 'run_'
            if os.path.basename(current_dir).startswith('run_'):
                output_filename = "REPLICATION_results.csv"
            # A directory is an Experiment directory if it contains 'run_*' subdirectories
            elif subdirs and any(s.startswith('run_') for s in subdirs):
                output_filename = "EXPERIMENT_results.csv"

            output_csv_path = os.path.join(current_dir, output_filename)
            write_summary_csv(output_csv_path, level_results)

def main():
    parser = argparse.ArgumentParser(description="Compile experiment results into a master CSV.")
    parser.add_argument("base_dir", help="The base directory to start the compilation from.")
    parser.add_argument("--mode", choices=['hierarchical'], default='hierarchical', help="Compilation mode.")
    args = parser.parse_args()

    if not os.path.isdir(args.base_dir):
        logging.error(f"Error: The specified directory does not exist: {args.base_dir}")
        return

    run_hierarchical_mode(args.base_dir)
    print("\nCompilation process finished.")

if __name__ == "__main__":
    main()

# === End of src/compile_study_results.py ===

