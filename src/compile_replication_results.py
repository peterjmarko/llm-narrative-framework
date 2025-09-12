#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: src/compile_replication_results.py

"""
Stage 6: Replication Results Compiler.

This script is responsible for the sixth and final stage of the replication
pipeline. It creates a single-row summary CSV file for a single replication run.

It reads the final `replication_metrics.json` and `config.ini.archived` from
the specified run directory, combines all parameters and metrics into a single
record, and writes it to `REPLICATION_results.csv`.

This creates a standardized, machine-readable artifact for each run, which can
then be aggregated at the experiment and study levels. It is called by
`orchestrate_replication.py`.

Usage:
    python src/compile_replication_results.py /path/to/run_directory
"""

import os
import sys
import pandas as pd
import logging
import json
import re
import configparser
import argparse

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
        bias_metrics = data.pop('positional_bias_metrics')
        data.update(bias_metrics)
    return data

def parse_config_params(config_path):
    """
    Robustly parses key parameters from a config.ini.archived file.
    """
    params = {}
    config = configparser.ConfigParser(allow_no_value=True)
    try:
        config.read(config_path)
        def get_robust(section_keys, key_keys, value_type=str, default=None):
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
    logging.info(f"  -> Generated summary:\n    {output_path} ({len(df)} rows)")

def main():
    parser = argparse.ArgumentParser(description="Create a summary CSV for a single replication run.")
    parser.add_argument("run_directory", help="The path to the specific run_* directory.")
    args = parser.parse_args()

    if not os.path.isdir(args.run_directory) or not os.path.basename(args.run_directory).startswith('run_'):
        logging.error(f"Error: The specified path is not a valid run directory: {args.run_directory}")
        sys.exit(1)
        return  # Eject for testability

    metrics_filepath = os.path.join(args.run_directory, "analysis_inputs", "replication_metrics.json")
    config_path = os.path.join(args.run_directory, 'config.ini.archived')

    if not os.path.exists(metrics_filepath) or not os.path.exists(config_path):
        logging.error(f"Error: Required file (metrics.json or config.ini.archived) not found in {args.run_directory}")
        sys.exit(1)
        return  # Eject for testability

    try:
        with open(metrics_filepath, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error: Could not read or parse {os.path.basename(metrics_filepath)}. Error: {e}")
        sys.exit(1)
        return  # Eject for testability

    metrics = _flatten_bias_metrics(metrics)
    run_params = parse_config_params(config_path)
    run_dir_name = os.path.basename(args.run_directory)
    rep_match = re.search(r'rep-(\d+)', run_dir_name)
    run_params['replication'] = int(rep_match.group(1)) if rep_match else 0
    
    run_data = {'run_directory': run_dir_name}
    run_data.update(run_params)
    run_data.update(metrics)
    
    output_csv_path = os.path.join(args.run_directory, "REPLICATION_results.csv")
    write_summary_csv(output_csv_path, [run_data])
    print("\nReplication summarization complete.")

if __name__ == "__main__":
    main()

# === End of src/compile_replication_results.py ===
