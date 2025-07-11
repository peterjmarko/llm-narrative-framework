#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/results_compiler.py

"""
A utility module (worker) with core functions for compiling experiment results.

This script provides the reusable logic for parsing report files, config files,
and writing standardized summary CSVs. It is intended to be imported by other
compiler scripts (e.g., compile_replication.py, compile_experiment.py), not
run directly.
"""

import os
import sys
import pandas as pd
import logging
import json
import re
import configparser

try:
    from config_loader import APP_CONFIG, get_config_list
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_list

def parse_metrics_json(report_content):
    """
    Parses the JSON block from a report file content and flattens nested bias metrics.
    """
    json_start_tag = "<<<METRICS_JSON_START>>>"
    json_end_tag = "<<<METRICS_JSON_END>>>"
    try:
        match = re.search(f"{re.escape(json_start_tag)}(.*?){re.escape(json_end_tag)}", report_content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            data = json.loads(json_str)

            # Check for the nested bias metrics dictionary and flatten it
            if 'positional_bias_metrics' in data and isinstance(data['positional_bias_metrics'], dict):
                # Remove the nested dictionary from the main data
                bias_metrics = data.pop('positional_bias_metrics')
                # Add its items to the main data, with a prefix to avoid name collisions
                for key, value in bias_metrics.items():
                    data[f"bias_{key}"] = value # e.g., creates 'bias_slope'

            return data

    except json.JSONDecodeError as e:
        logging.warning(f"  - Warning: Failed to parse JSON in report. Error: {e}")
    return None

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
    """
    Writes a list of result dictionaries to a CSV file using a standardized header.
    """
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
    
    # Ensure the output directory exists before writing
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    df.to_csv(output_path, index=False)
    logging.info(f"  -> Generated summary: {output_path} ({len(df)} rows)")

# === End of src/results_compiler.py ===