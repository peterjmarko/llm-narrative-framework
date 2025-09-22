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
# Filename: src/compile_study_results.py

"""
Study-Level Results Compiler.

This script aggregates results from all individual experiment directories within
a single study into a unified `STUDY_results.csv` file.

It takes a study directory as input, searches its subdirectories for all
`EXPERIMENT_results.csv` files, and concatenates them into a single,
master dataset for the entire study.

This is the final data preparation step before running the main statistical
analysis with `analyze_study_results.py`. It is typically called by the main
`evaluate_study.ps1` user entry point.

Usage:
    python src/compile_study_results.py /path/to/study_directory
"""

import os
import sys
import pandas as pd
import logging
import argparse
import glob
import importlib

# Configure logging only if no handlers are already present. This makes the
# script compatible with testing frameworks like pytest or unittest's
# assertLogs that pre-configure a handler.
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO, format='%(message)s')

try:
    from config_loader import APP_CONFIG, get_config_list
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_list

def validate_experiment_consistency(dataframes, experiment_files):
    """
    Validate that all experiments use consistent parameters and schema.
    Returns (is_valid, warnings) tuple.
    """
    if not dataframes:
        return True, []
    
    warnings = []
    first_df = dataframes[0]
    reference_cols = set(first_df.columns)
    reference_factors = {}
    
    # Extract key experimental parameters from first experiment
    factor_cols = ['model', 'mapping_strategy', 'k', 'm', 'db']
    for col in factor_cols:
        if col in first_df.columns:
            reference_factors[col] = set(first_df[col].unique())
    
    # Check consistency across all experiments
    for i, (df, filepath) in enumerate(zip(dataframes[1:], experiment_files[1:]), 1):
        # Check column consistency
        current_cols = set(df.columns)
        if current_cols != reference_cols:
            missing = reference_cols - current_cols
            extra = current_cols - reference_cols
            exp_name = os.path.basename(os.path.dirname(filepath))
            warning_msg = f"Experiment '{exp_name}' has schema differences:"
            if missing:
                warning_msg += f" missing columns {sorted(missing)},"
            if extra:
                warning_msg += f" extra columns {sorted(extra)},"
            warnings.append(warning_msg.rstrip(','))
        
        # Check parameter consistency for key factors
        for col, ref_values in reference_factors.items():
            if col in df.columns:
                current_values = set(df[col].unique())
                if col in ['k', 'm']:  # These should be identical across experiments
                    if current_values != ref_values:
                        exp_name = os.path.basename(os.path.dirname(filepath))
                        warnings.append(f"Experiment '{exp_name}' has different {col} values: {sorted(current_values)} vs reference {sorted(ref_values)}")
    
    return len(warnings) == 0, warnings

def write_summary_csv(output_path, results_list):
    """Writes a list of result dictionaries to a structured CSV file."""
    if not results_list:
        logging.warning(f"No results to write to {output_path}.")
        return

    fieldnames = get_config_list(APP_CONFIG, 'Schema', 'csv_header_order')
    if not fieldnames:
        logging.error("FATAL: 'csv_header_order' not found in config.ini. Cannot write CSV.")
        sys.exit(1)

    df = pd.DataFrame(results_list)
    # Ensure all required columns from the schema exist, adding any that are missing
    for col in fieldnames:
        if col not in df.columns:
            df[col] = pd.NA
    
    # Reorder the DataFrame according to the schema
    df = df[fieldnames]
    df.to_csv(output_path, index=False)
    logging.info(f"  -> Generated study summary:\n    {output_path} ({len(df)} rows)")

def main():
    global APP_CONFIG
    parser = argparse.ArgumentParser(description="Compile all experiment results for a single study.")
    parser.add_argument("study_directory", help="The path to the study directory containing experiment subfolders.")
    parser.add_argument('--config-path', type=str, default=None, help=argparse.SUPPRESS) # For testing
    args = parser.parse_args()

    if args.config_path:
        os.environ['PROJECT_CONFIG_OVERRIDE'] = os.path.abspath(args.config_path)
        if 'config_loader' in sys.modules:
            importlib.reload(sys.modules['config_loader'])
        # Re-import and re-assign the global APP_CONFIG
        from config_loader import APP_CONFIG as RELOADED_APP_CONFIG
        APP_CONFIG = RELOADED_APP_CONFIG

    if not os.path.isdir(args.study_directory):
        logging.error(f"Error: The specified directory does not exist: {args.study_directory}")
        sys.exit(1)
        return  # Eject for testability

    # Search recursively for any EXPERIMENT_results.csv files within the study directory
    search_pattern = os.path.join(args.study_directory, '**', 'EXPERIMENT_results.csv')
    experiment_files = glob.glob(search_pattern, recursive=True)

    if not experiment_files:
        logging.warning(f"No 'EXPERIMENT_results.csv' files found in subdirectories of {args.study_directory}. Nothing to compile.")
        sys.exit(0)
        return  # Eject for testability
    
    logging.info(f"Found {len(experiment_files)} experiment result files to compile.")

    all_experiment_data = []
    valid_experiment_files = []
    for f in experiment_files:
        try:
            df = pd.read_csv(f)
            if not df.empty:
                all_experiment_data.append(df)
                valid_experiment_files.append(f)
            else:
                logging.warning(f"  - Warning: Skipping empty results file: {f}")
        except pd.errors.EmptyDataError:
            logging.warning(f"  - Warning: Skipping empty results file: {f}")
        except Exception as e:
            logging.error(f"  - Error: Could not read or process {f}. Reason: {e}")
            
    if not all_experiment_data:
        logging.error("No valid data could be read from any experiment files. Halting.")
        sys.exit(1)
        return  # Eject for testability

    # Validate experiment consistency before compilation
    is_consistent, validation_warnings = validate_experiment_consistency(all_experiment_data, valid_experiment_files)
    
    if validation_warnings:
        logging.warning(f"Found {len(validation_warnings)} consistency issue(s):")
        for warning in validation_warnings:
            logging.warning(f"  - {warning}")
        
        if not is_consistent:
            logging.warning("Proceeding with compilation despite consistency issues. Results may require manual review.")

    study_df = pd.concat(all_experiment_data, ignore_index=True)

    output_filename = "STUDY_results.csv"
    output_path = os.path.join(args.study_directory, output_filename)
    
    write_summary_csv(output_path, study_df.to_dict('records'))
    
    # Generate compilation metadata
    metadata_path = os.path.join(args.study_directory, "STUDY_compilation_metadata.txt")
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            from datetime import datetime
            f.write(f"Study Compilation Metadata\n")
            f.write(f"==========================\n\n")
            f.write(f"Compilation Time: {datetime.now().isoformat()}\n")
            f.write(f"Total Experiments: {len(valid_experiment_files)}\n")
            f.write(f"Total Replications: {len(study_df)}\n")
            f.write(f"Output File: {output_filename}\n\n")
            f.write(f"Source Experiments:\n")
            for i, filepath in enumerate(valid_experiment_files, 1):
                exp_name = os.path.basename(os.path.dirname(filepath))
                rows_from_exp = len(all_experiment_data[i-1])
                f.write(f"  {i:2d}. {exp_name} ({rows_from_exp} replications)\n")
            
            if validation_warnings:
                f.write(f"\nValidation Warnings ({len(validation_warnings)}):\n")
                for warning in validation_warnings:
                    f.write(f"  - {warning}\n")
        
        logging.info(f"  -> Compilation metadata saved to: {metadata_path}")
    except Exception as e:
        logging.warning(f"Could not write compilation metadata: {e}")
    
    print("\nStudy compilation complete.")

if __name__ == "__main__":
    main()

# === End of src/compile_study_results.py ===
