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
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
# Filename: src/restore_config.py

"""
Restores a config.ini.archived file for a single, previously completed
experiment run by reverse-engineering its replication_report.txt file.

This utility is intended to be called by a batch script (like patch_old_experiment.py)
to bring older experiment data into compliance with the new standard of
having an archived config file in every run directory.
"""

import os
import sys
import glob
import re
import configparser

def parse_report_header(report_content):
    """Extracts key parameters from the report header using regex."""
    params = {}
    def extract(pattern, text):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else 'unknown'

    # Use the same logic as the old compile_study_results.py
    params['model_name'] = extract(r"LLM Model:\s*(.*)", report_content)
    params['mapping_strategy'] = extract(r"Mapping Strategy:\s*(.*)", report_content)
    params['group_size'] = extract(r"Items per Query \(k\):\s*(\d+)", report_content)
    params['num_trials'] = extract(r"Num Iterations \(m\):\s*(\d+)", report_content)
    params['personalities_src'] = extract(r"Personalities Source:\s*(.*)", report_content)
    
    run_directory = extract(r"Run Directory:\s*(.*)", report_content)
    if run_directory != 'unknown':
        temp_match = re.search(r"tmp-([\d.]+)", run_directory)
        params['temperature'] = temp_match.group(1) if temp_match else '0.0'
        
        rep_match = re.search(r"_rep-(\d+)", run_directory)
        params['replication'] = rep_match.group(1) if rep_match else '0'
    else:
        params['temperature'] = '0.0'
        params['replication'] = '0'

    return params

def main():
    if len(sys.argv) != 2:
        print("Usage: python restore_config.py <path_to_run_directory>")
        sys.exit(1)

    run_dir = sys.argv[1]
    if not os.path.isdir(run_dir):
        print(f"Error: Directory not found at '{run_dir}'")
        sys.exit(1)

    # Check if the work is already done
    dest_config_path = os.path.join(run_dir, 'config.ini.archived')
    if os.path.exists(dest_config_path):
        print(f"Skipping: '{os.path.basename(run_dir)}' already has an archived config.")
        sys.exit(0)

    # Find the report file
    report_files = glob.glob(os.path.join(run_dir, "replication_report_*.txt"))
    if not report_files:
        print(f"Error: No 'replication_report_*.txt' file found in '{run_dir}'")
        sys.exit(1)
    
    report_path = report_files[0] # Assume there's only one

    print(f"Processing: '{os.path.basename(run_dir)}'")
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Reverse-engineer the parameters
    params = parse_report_header(content)

    # Create a configparser object and populate it
    config = configparser.ConfigParser()
    config['LLM'] = {
        'model': params['model_name'],           # Standardized key
        'temperature': params['temperature']
    }
    config['Study'] = {
        'mapping_strategy': params['mapping_strategy'],
        'k_per_query': params['group_size'],     # Standardized key
        'num_iterations': params['num_trials']   # Standardized key
    }
    config['Filenames'] = {
        'personalities_src': params['personalities_src']
    }
    config['Replication'] = {
        'replication': params['replication']     # Add replication number
    }
    config['General'] = {
        'base_output_dir': 'output' # A sensible default
    }

    # Write the new config file
    with open(dest_config_path, 'w', encoding='utf-8') as config_file:
        config.write(config_file)
    
    print(f"  -> Success: Created '{os.path.basename(dest_config_path)}'")

if __name__ == "__main__":
    main()

# === End of src/restore_config.py ===
