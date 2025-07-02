#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/compile_results.py

"""
Compiles All Experiment Results into a Master Summary CSV.

This script recursively scans a directory structure to find all individual
replication reports and aggregates their data into a master CSV file named
`final_summary_results.csv`.

It operates in a hierarchical, bottom-up fashion:
1.  It starts from the deepest directories in the specified path.
2.  In each directory, it looks for `replication_report_*.txt` files and
    any `final_summary_results.csv` files from subdirectories.
3.  It parses the metrics (from a JSON block) and parameters (from the
    archived config) for each replication.
4.  It combines all found data into a new `final_summary_results.csv` at
    the current directory level.
5.  This process repeats up the directory tree, with each parent directory
    aggregating the summaries from its children.

The final result is a master CSV at the top level of the specified base
directory, containing the complete data for the entire study, ready for
statistical analysis.

Usage:
    python src/compile_results.py /path/to/study_output_dir
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

def parse_metrics_json(report_content):
    json_start_tag = "<<<METRICS_JSON_START>>>"
    json_end_tag = "<<<METRICS_JSON_END>>>"
    try:
        match = re.search(f"{re.escape(json_start_tag)}(.*?){re.escape(json_end_tag)}", report_content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)
    except json.JSONDecodeError as e:
        logging.warning(f"  - Warning: Failed to parse JSON in report. Error: {e}")
    return None

def parse_config_params(config_path):
    """
    Robustly parses key parameters from a config.ini.archived file.
    It checks for multiple possible section and key names to handle all config versions.
    """
    params = {}
    config = configparser.ConfigParser(allow_no_value=True)
    try:
        config.read(config_path)

        def get_robust(section_keys, key_keys, value_type=str, default=None):
            """Internal helper to find a value across multiple sections and keys."""
            for section in section_keys:
                if config.has_section(section):
                    for key in key_keys:
                        if config.has_option(section, key):
                            try:
                                if value_type == int: return config.getint(section, key)
                                if value_type == float: return config.getfloat(section, key)
                                if value_type == bool: return config.getboolean(section, key)
                                return config.get(section, key)
                            except (ValueError, TypeError):
                                continue
            return default

        # --- TRULY ROBUST PARAMETER EXTRACTION ---
        params['model'] = get_robust(['Model', 'LLM'], ['model_name', 'model'], default='unknown_model')
        params['mapping_strategy'] = get_robust(['Study'], ['mapping_strategy'], default='unknown_strategy')
        params['temperature'] = get_robust(['Model', 'LLM'], ['temperature'], value_type=float, default=0.0)
        params['k'] = get_robust(['Study'], ['k_per_query', 'num_subjects', 'group_size'], value_type=int, default=0)
        params['m'] = get_robust(['Study'], ['num_iterations', 'num_trials'], value_type=int, default=0)
        
        db_path = get_robust(['General', 'Filenames'], ['personalities_db_path', 'personalities_src'], default='unknown_db.file')
        params['db'] = os.path.basename(db_path)

    except Exception as e:
        logging.warning(f"  - Could not fully parse config {os.path.basename(config_path)}. Error: {e}")
    return params

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
    logging.info(f"  -> Generated summary: {output_path} ({len(df)} rows)")

def run_hierarchical_mode(base_dir):
    logging.info(f"Running in hierarchical mode on: {base_dir}")
    for current_dir, subdirs, files in os.walk(base_dir, topdown=False):
        print(f"\nProcessing directory: {current_dir}")
        level_results = []
        
        report_files = glob.glob(os.path.join(current_dir, 'replication_report_*.txt'))
        if report_files and os.path.basename(current_dir).startswith('run_'):
            run_dir_name = os.path.basename(current_dir)
            logging.info(f"  - Found report in run folder: {run_dir_name}")
            report_path = report_files[0]
            config_path = os.path.join(current_dir, 'config.ini.archived')

            if not os.path.exists(config_path):
                logging.warning(f"    - Warning: 'config.ini.archived' not found in {run_dir_name}. Skipping.")
                continue

            with open(report_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            metrics = parse_metrics_json(content)
            if not metrics:
                logging.warning(f"    - Warning: Could not parse metrics from {os.path.basename(report_path)}. Skipping.")
                continue
            
            run_params = parse_config_params(config_path)
            rep_match = re.search(r'rep-(\d+)', run_dir_name)
            run_params['replication'] = int(rep_match.group(1)) if rep_match else 0
            
            run_data = {'run_directory': run_dir_name}
            run_data.update(run_params)
            run_data.update(metrics)
            level_results.append(run_data)

        for subdir_name in subdirs:
            summary_path = os.path.join(current_dir, subdir_name, 'final_summary_results.csv')
            if os.path.exists(summary_path):
                logging.info(f"  - Aggregating results from: {os.path.join(subdir_name, 'final_summary_results.csv')}")
                try:
                    df_sub = pd.read_csv(summary_path)
                    if not df_sub.empty:
                        level_results.extend(df_sub.to_dict('records'))
                except pd.errors.EmptyDataError:
                    logging.warning(f"    - Warning: {summary_path} is empty. Skipping.")
                except Exception as e:
                    logging.warning(f"    - Warning: Could not read or process {summary_path}. Error: {e}")

        if level_results:
            output_csv_path = os.path.join(current_dir, "final_summary_results.csv")
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

# === End of src/compile_results.py ===