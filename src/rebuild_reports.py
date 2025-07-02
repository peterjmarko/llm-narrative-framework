#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/rebuild_reports.py

"""
Rebuilds replication reports to their original, high-fidelity format.

This script is a data recovery tool. It iterates through each run directory,
reads the ground-truth parameters from 'config.ini.archived', then re-runs
the processing (Stage 3) and analysis (Stage 4) scripts to generate fresh,
complete output. 

SAFETY FEATURE: It archives old, corrupted reports by renaming them with a
'.corrupted' extension instead of deleting them.
"""

import argparse
import os
import sys
import datetime
import subprocess
import logging
import re
import glob
import configparser

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# This allows the script to find config_loader for PROJECT_ROOT
try:
    from config_loader import PROJECT_ROOT
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    try:
        from config_loader import PROJECT_ROOT
    except ImportError as e:
        logging.error(f"FATAL: Could not import PROJECT_ROOT from config_loader.py. Error: {e}")
        sys.exit(1)

def run_script(command, title):
    """Helper to run a script and capture its full output."""
    logging.info(f"  -> Re-running Stage: {title}...")
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        return result.stdout + result.stderr
    except subprocess.CalledProcessError as e:
        error_output = e.stdout + e.stderr
        logging.error(f"Failed to run '{title}'. Error:\n{error_output}")
        # Return the captured error output so it can be logged in the final report if needed
        return f"STAGE FAILED: {title}\n{error_output}"

def rebuild_report_for_run(run_dir):
    """Rebuilds the report for a single run directory with high fidelity."""
    dir_basename = os.path.basename(run_dir)
    logging.info(f"--- Processing: {dir_basename} ---")

    archive_path = os.path.join(run_dir, 'config.ini.archived')
    if not os.path.exists(archive_path):
        logging.warning(f"Skipping: No 'config.ini.archived' found. Please run patcher first.")
        return False

    # --- 1. Load ground-truth parameters from the archived config ---
    config = configparser.ConfigParser()
    config.read(archive_path)
    try:
        params = {
            'model_name': config.get('Model', 'model_name'),
            'num_iterations': config.get('Study', 'num_trials'),
            'k_per_query': config.get('Study', 'num_subjects'),
            'mapping_strategy': config.get('Study', 'mapping_strategy'),
            'personalities_file': os.path.basename(config.get('General', 'personalities_db_path'))
        }
    except (configparser.NoSectionError, configparser.NoOptionError) as e:
        logging.error(f"Skipping {dir_basename}: Archived config is incomplete. Error: {e}")
        return False

    # --- 2. Re-run Stage 3 (Process) and Stage 4 (Analyze) ---
    process_script = os.path.join(PROJECT_ROOT, 'src', 'process_llm_responses.py')
    analyze_script = os.path.join(PROJECT_ROOT, 'src', 'analyze_performance.py')
    
    cmd3 = [sys.executable, process_script, "--run_output_dir", run_dir, "--quiet"]
    output3 = run_script(cmd3, "Process LLM Responses")

    cmd4 = [sys.executable, analyze_script, "--run_output_dir", run_dir, "--quiet"]
    output4 = run_script(cmd4, "Analyze Performance")

    # --- 3. Extract status information from the fresh script outputs ---
    parsing_status = "N/A"
    parser_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+)>>>", output3)
    if parser_match:
        parsing_status = f"{parser_match.group(1)}/{parser_match.group(2)} responses parsed"

    validation_status = "UNKNOWN"
    if "PROCESSOR VALIDATION FAILED" in output3:
        validation_status = "FAILED at Stage 3 (Process Responses)"
    elif "ANALYZER VALIDATION FAILED" in output4:
        validation_status = "FAILED at Stage 4 (Analyze Performance)"
    elif "PROCESSOR_VALIDATION_SUCCESS" in output3 and "ANALYZER_VALIDATION_SUCCESS" in output4:
        validation_status = "OK (All checks passed)"

    # =========================================================================
    # === SAFETY MODIFICATION: Archive old reports instead of deleting them ===
    # =========================================================================
    for report in glob.glob(os.path.join(run_dir, 'replication_report_*.txt')):
        archive_name = report + '.corrupted'
        try:
            os.rename(report, archive_name)
            logging.info(f"  -> Archived corrupted report to: {os.path.basename(archive_name)}")
        except OSError as e:
            logging.warning(f"  -> Could not archive report {os.path.basename(report)}: {e}")

    # --- 5. Assemble and write the new, high-fidelity report ---
    timestamp_for_file = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_filename = f"replication_report_{timestamp_for_file}.txt"
    report_path = os.path.join(run_dir, report_filename)

    with open(report_path, 'w', encoding='utf-8') as report_file:
        # Header Section
        header = f"""
================================================================================
 REPLICATION RUN REPORT (REBUILT ON {datetime.datetime.now().strftime("%Y-%m-%d")})
================================================================================
Date:            {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Final Status:    COMPLETED
Run Directory:   {dir_basename}
Parsing Status:  {parsing_status}
Validation Status: {validation_status}
Report File:     {report_filename}

--- Run Parameters ---
Num Iterations (m): {params['num_iterations']}
Items per Query (k): {params['k_per_query']}
Mapping Strategy: {params['mapping_strategy']}
Personalities Source: {params['personalities_file']}
LLM Model:       {params['model_name']}
Run Notes:       N/A (Original notes cannot be recovered)
================================================================================
"""
        report_file.write(header.strip() + "\n\n")

        # Base Query Prompt Section
        base_query_filename = config.get('Filenames', 'base_query_src', fallback='base_query.txt')
        base_query_path = os.path.join(PROJECT_ROOT, 'data', base_query_filename)
        report_file.write("\n--- Base Query Prompt Used ---\n")
        try:
            with open(base_query_path, 'r', encoding='utf-8') as f_prompt:
                report_file.write(f_prompt.read())
        except FileNotFoundError:
            report_file.write(f"ERROR: Could not find base query file at {base_query_path}\n")
        report_file.write("\n-------------------------------\n\n")

        # Full Analysis Output Section
        report_file.write(output4)

    logging.info(f"  -> Successfully rebuilt report: {report_filename}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Rebuilds replication reports to their original high-fidelity format.")
    parser.add_argument('base_dir', help="The base directory to scan for experiment runs (e.g., 'output/reports/6_Study_4').")
    args = parser.parse_args()

    if not os.path.isdir(args.base_dir):
        logging.error(f"Error: Provided directory does not exist: {args.base_dir}")
        return

    run_dirs = glob.glob(os.path.join(args.base_dir, '**', 'run_*'), recursive=True)
    if not run_dirs:
        logging.info(f"No 'run_*' directories found in {args.base_dir}.")
        return

    logging.info(f"Found {len(run_dirs)} total run directories. Rebuilding reports...")
    
    success_count = 0
    total_count = 0
    for run_dir in run_dirs:
        if os.path.isdir(run_dir):
            total_count += 1
            if rebuild_report_for_run(run_dir):
                success_count += 1

    logging.info(f"\nReport rebuilding complete. Successfully processed {success_count}/{total_count} directories.")

if __name__ == "__main__":
    main()

# === End of src/rebuild_reports.py ===