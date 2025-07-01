#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/compile_results.py

"""
Compile Results Utility (compile_results.py)

Purpose:
This script scans a directory for 'run_*' subdirectories and compiles key
performance metrics from each run's 'report.txt' file into a single,
aggregated CSV file named 'final_summary_results.csv'.

It is designed to be run at the batch level, processing all runs within a
single experimental batch directory.

Workflow:
1.  Scans a target directory for subdirectories matching the 'run_*' pattern.
2.  The scan depth is controlled by the --depth argument.
3.  For each 'run_*' directory, it reads the 'report.txt' file.
4.  Parses key metrics (MRR, Top-K Accuracy, etc.) from the report.
5.  Parses run parameters (model, temperature, etc.) from the directory name.
6.  Appends a summary row for the run to a master list.
7.  Saves the compiled list as 'final_summary_results.csv' in the target directory.
8.  Calculates and prints summary statistics (mean, median, std) for key metrics.

Command-Line Usage:
    # Scan the './output' directory (default, depth 0)
    python src/compile_results.py

    # Scan a specific directory with a depth of 1
    python src/compile_results.py /path/to/my/batch --depth 1

    # Scan a directory recursively
    python src/compile_results.py /path/to/my/batch --depth -1
"""

import os
import sys
import glob
import re
import json
import csv
import configparser
import argparse
from config_loader import APP_CONFIG, get_config_list

# --- Helper Functions ---

def parse_config_params(config_path):
    """
    Reads parameters from a config.ini.archived file and normalizes the keys
    to the standard schema for consistent output.
    """
    config = configparser.ConfigParser()
    config.read(config_path)
    
    raw_params = {}
    for section in config.sections():
        for key, value in config.items(section):
            raw_params[key] = value
            
    # --- Key Normalization ---
    # Maps all possible legacy keys to the single, standard key.
    key_map = {
        'model_name': 'model',
        'model': 'model',
        
        'group_size': 'k',
        'k_per_query': 'k',
        
        'num_trials': 'm',
        'num_iterations': 'm',
        
        'personalities_src': 'db'
    }
    
    normalized_params = {}
    for key, value in raw_params.items():
        # Find the standard key from the map; if not found, use the original key.
        standard_key = key_map.get(key)
        if standard_key:
            normalized_params[standard_key] = value
        else:
            # Keep keys that don't need mapping (like 'temperature', 'replication', etc.)
            normalized_params[key] = value
            
    return normalized_params

def parse_metrics_json(report_content):
    """Extracts the JSON block from the report content."""
    match = re.search(r'<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>', report_content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            return None
    return None

def write_summary_csv(output_path, results_data):
    """Writes a list of result dictionaries to a CSV file with sorted headers."""
    if not results_data:
        return
        
    # Load the standard header order directly from the central config file.
    # This list IS the definitive header for the CSV file.
    fieldnames = get_config_list(APP_CONFIG, 'Schema', 'csv_header_order')

    if not fieldnames:
        # This is a critical failure. The script cannot proceed without a defined schema.
        print("  -> FATAL ERROR: 'csv_header_order' not found in the [Schema] section of config.ini. Cannot write CSV.")
        return

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f_csv:
            writer = csv.DictWriter(f_csv, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results_data)
        print(f"  -> Generated summary: {output_path} ({len(results_data)} rows)")
    except IOError as e:
        print(f"  -> Warning: Could not write summary to {output_path}. Error: {e}")

# --- Mode-Specific Logic ---

def run_hierarchical_mode(base_dir):
    """Generates summaries at every level of the directory tree."""
    print(f"Running in hierarchical mode on: {base_dir}")
    # Walk the directory tree from the bottom up
    for current_dir, subdirs, files in os.walk(base_dir, topdown=False):
        print(f"\nProcessing directory: {current_dir}")
        level_results = []
        
        # 1. Process individual run reports in the current directory
        report_files = [f for f in files if f.startswith('replication_report') and f.endswith('.txt')]
        for report_file in report_files:
            run_dir_name = os.path.basename(current_dir)
            print(f"  - Found report in run folder: {run_dir_name}")
            
            config_path = os.path.join(current_dir, 'config.ini.archived')
            if not os.path.exists(config_path):
                print(f"    - Warning: 'config.ini.archived' not found. Skipping.")
                continue

            with open(os.path.join(current_dir, report_file), 'r', encoding='utf-8') as f:
                content = f.read()
            
            metrics = parse_metrics_json(content)
            if not metrics:
                print(f"    - Warning: Could not parse metrics from {report_file}. Skipping.")
                continue
            
            run_data = parse_config_params(config_path)
            run_data['run_directory'] = run_dir_name
            run_data.update(metrics)
            level_results.append(run_data)

        # 2. Aggregate results from immediate subdirectories
        for subdir_name in subdirs:
            summary_path = os.path.join(current_dir, subdir_name, 'final_summary_results.csv')
            if os.path.exists(summary_path):
                print(f"  - Aggregating results from: {subdir_name}/final_summary_results.csv")
                with open(summary_path, 'r', newline='', encoding='utf-8') as f_csv:
                    reader = csv.DictReader(f_csv)
                    level_results.extend(list(reader))

        # 3. Write the summary for the current level
        if level_results:
            output_csv_path = os.path.join(current_dir, "final_summary_results.csv")
            write_summary_csv(output_csv_path, level_results)

def find_files_by_depth(base_dir, pattern, depth):
    """Finds files matching a pattern up to a specified depth. (Used in flat mode)."""
    if depth < -1: depth = -1
    if depth == -1:
        # This correctly finds the pattern anywhere recursively
        search_pattern = os.path.join(base_dir, '**', pattern)
        return sorted(glob.glob(search_pattern, recursive=True))

    all_paths = set()
    # 'd' represents the number of intermediate directories.
    for d in range(depth + 1):
        # The path needs 'd' wildcards for intermediate folders, plus one more
        # wildcard for the run_* folder itself.
        wildcards = ['*'] * (d + 1)
        path_parts = [base_dir] + wildcards + [pattern]
        current_pattern = os.path.join(*path_parts)
        all_paths.update(glob.glob(current_pattern))
    return sorted([p for p in all_paths if os.path.isfile(p)])

def run_flat_mode(base_dir, depth):
    """Generates one master summary and individual run summaries."""
    print(f"Running in flat mode on: {base_dir} (Depth: {depth})")
    report_files = find_files_by_depth(base_dir, "replication_report_*.txt", depth)
    
    if not report_files:
        print(f"No report files found in '{base_dir}' at depth {depth}.")
        return

    all_results = []
    print(f"Found {len(report_files)} report files. Processing...")

    for report_path in report_files:
        run_dir = os.path.dirname(report_path)
        run_dir_name = os.path.basename(run_dir)
        print(f"\nProcessing: {run_dir_name}")
        
        config_path = os.path.join(run_dir, 'config.ini.archived')
        if not os.path.exists(config_path):
            print(f"  - Warning: 'config.ini.archived' not found in {run_dir}. Skipping.")
            continue
        
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        metrics = parse_metrics_json(content)
        if metrics:
            run_data = parse_config_params(config_path)
            run_data['run_directory'] = run_dir_name
            run_data.update(metrics)
            
            # Write individual summary inside the run folder
            write_summary_csv(os.path.join(run_dir, "final_summary_results.csv"), [run_data])
            all_results.append(run_data)
        else:
            print(f"  - Warning: Could not find or parse metrics JSON in {os.path.basename(report_path)}")

    if not all_results:
        print("\nNo valid results were compiled.")
        return

    # Write the single master summary file at the top level
    master_csv_path = os.path.join(base_dir, "final_summary_results.csv")
    print(f"\nWriting master summary file...")
    write_summary_csv(master_csv_path, all_results)

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Compile experiment results into summary CSV files.")
    parser.add_argument("target_dir", nargs='?', default=".",
                        help="The target directory to scan. Defaults to the current directory.")
    parser.add_argument("--mode", choices=['hierarchical', 'flat'], default='hierarchical',
                        help="'hierarchical' for multi-level summaries (default), 'flat' for a single master summary.")
    parser.add_argument("--depth", type=int, default=0,
                        help="Recursion depth for 'flat' mode. 0=target dir only, -1=infinite.")
    args = parser.parse_args()

    target_dir_abs = os.path.abspath(args.target_dir)
    if not os.path.isdir(target_dir_abs):
        print(f"Error: Specified target directory '{target_dir_abs}' does not exist.")
        sys.exit(1)

    if args.mode == 'hierarchical':
        if args.depth != 0:
            print("Warning: --depth argument is ignored in 'hierarchical' mode.")
        run_hierarchical_mode(target_dir_abs)
    elif args.mode == 'flat':
        run_flat_mode(target_dir_abs, args.depth)

    print("\nCompilation process finished.")

if __name__ == "__main__":
    main()

# === End of src/compile_results.py ===