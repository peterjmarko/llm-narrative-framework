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
# Filename: src/restore_config.py

"""
Reverse-engineers a config.ini.archived file from a legacy report.

This single-purpose utility operates on a single run directory. It reads a
human-readable 'replication_report.txt' file, parses key experimental
parameters using a robust set of regular expressions, and writes them into a
new, structured 'config.ini.archived' file.

It is designed to handle multiple legacy report formats. If more than one report
exists in a directory, it deterministically selects the most recent one to
ensure the restored parameters are as accurate as possible. The script is called
in a loop by `patch_old_experiment.py` to upgrade legacy datasets.
"""

import os
import sys
import glob
import re
import configparser

def parse_report_header(report_content):
    """Extracts key parameters from the report header using multiple robust regex patterns."""
    params = {}
    def extract_robust(patterns, text, default='unknown'):
        """Tries a list of regex patterns and returns the first match."""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return default

    # Define modern and legacy patterns for each parameter.
    patterns_model = [r"Model Name:\s*(.*)", r"LLM Model:\s*(.*)", r"Model:\s*(.*)"]
    patterns_mapping = [r"Mapping Strategy:\s*(.*)"]
    patterns_k = [r"Group Size \(k\):\s*(\d+)", r"Items per Query \(k\):\s*(\d+)", r"k_per_query:\s*(\d+)"]
    patterns_m = [r"Num Trials \(m\):\s*(\d+)", r"Num Iterations \(m\):\s*(\d+)"]
    patterns_db = [r"Personalities DB:\s*(.*)", r"Personalities Source:\s*(.*)"]
    patterns_run_dir = [r"Run Directory:\s*(.*)"]

    params['model_name'] = extract_robust(patterns_model, report_content)
    params['mapping_strategy'] = extract_robust(patterns_mapping, report_content)
    params['group_size'] = extract_robust(patterns_k, report_content, default='0')
    params['num_trials'] = extract_robust(patterns_m, report_content, default='0')
    params['personalities_src'] = extract_robust(patterns_db, report_content)
    
    run_directory = extract_robust(patterns_run_dir, report_content)
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

    # The calling script is responsible for checking if work needs to be done.
    # This worker will now always attempt to create or overwrite the file.
    dest_config_path = os.path.join(run_dir, 'config.ini.archived')

    # Find all report files
    report_files = glob.glob(os.path.join(run_dir, "replication_report_*.txt"))
    if not report_files:
        print(f"\nError: No 'replication_report_*.txt' file found in:\n'{run_dir}'")
        sys.exit(1)

    # FIX: Sort the files alphabetically by name and select the LAST one.
    # Since the timestamp is at the beginning of the filename suffix, this reliably
    # selects the newest report.
    latest_report_path = sorted(report_files)[-1]
    
    print(f"\nProcessing:\n'{run_dir}'")
    print(f"  - Using latest report: '{os.path.basename(latest_report_path)}'")
    with open(latest_report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Reverse-engineer the parameters
    params = parse_report_header(content)

    # Create a configparser object and populate it
    config = configparser.ConfigParser()
    config['LLM'] = {
        'model_name': params['model_name'],
        'temperature': params['temperature']
    }
    config['Study'] = {
        'mapping_strategy': params['mapping_strategy'],
        'group_size': params['group_size'],
        'num_trials': params['num_trials']
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
    
    print(f"  -> Success: Created:\n     '{dest_config_path}'")

if __name__ == "__main__":
    main()

# === End of src/restore_config.py ===
