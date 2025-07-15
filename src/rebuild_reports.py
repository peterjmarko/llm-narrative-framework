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
# Filename: src/rebuild_reports.py

"""
Rebuilds all replication reports from ground-truth data.

This script is a powerful reprocessing tool that allows for applying fixes to the
data processing or analysis logic without re-running expensive LLM calls.

For each run directory found, it:
1.  Reads the ground-truth parameters from `config.ini.archived`.
2.  Re-runs `process_llm_responses.py` (Stage 3) and `analyze_llm_performance.py`
    (Stage 4) to generate fresh results.
3.  Safely archives any old report as `.corrupted`.
4.  Assembles a new, complete `replication_report.txt` with the updated analysis.
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

# tqdm is a library that provides a clean progress bar.
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

# --- Setup ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# This allows the script to find config_loader for PROJECT_ROOT
try:
    from config_loader import PROJECT_ROOT, load_config, get_config_compatibility_map
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

def rebuild_report_for_run(run_dir, compat_map):
    """Rebuilds the report for a single run directory using a compatibility map."""
    dir_basename = os.path.basename(run_dir)
    logging.info(f"--- Processing: {dir_basename} ---")

    archive_path = os.path.join(run_dir, 'config.ini.archived')
    if not os.path.exists(archive_path):
        logging.warning(f"Skipping: No 'config.ini.archived' found. Please run patcher first.")
        return False

    archived_config = configparser.ConfigParser()
    archived_config.read(archive_path)

    def get_param(param_name):
        """Finds a parameter in the archived config using the compatibility map."""
        locations = compat_map.get(param_name)
        if not locations:
            raise configparser.NoOptionError(f"'{param_name}' is not defined in the compatibility map.", "N/A")
        
        for section, key in locations:
            if archived_config.has_option(section, key):
                return archived_config.get(section, key)
        
        raise configparser.NoOptionError(f"Could not find '{param_name}' in any of its expected locations.", "N/A")

    try:
        params = {
            'model_name':         get_param('model_name'),
            'num_iterations':     get_param('num_trials'),
            'k_per_query':        get_param('num_subjects'),
            'mapping_strategy':   get_param('mapping_strategy'),
            'personalities_file': os.path.basename(get_param('personalities_db_path'))
        }
    except configparser.NoOptionError as e:
        logging.error(f"Skipping {dir_basename}: Archived config is incomplete. Error: {e}")
        return False

    # --- 2. Re-run Stage 3 (Process) and Stage 4 (Analyze) ---
    process_script = os.path.join(PROJECT_ROOT, 'src', 'process_llm_responses.py')
    analyze_script = os.path.join(PROJECT_ROOT, 'src', 'analyze_llm_performance.py')
    
    # NOTE: Removed --quiet from Stage 3 to ensure its summary line is captured.
    cmd3 = [sys.executable, process_script, "--run_output_dir", run_dir]
    output3 = run_script(cmd3, "Process LLM Responses")

    # --- FAIL-FAST IMPROVEMENT ---
    # If Stage 3 failed, don't run Stage 4. Use Stage 3's error output for the report.
    if "STAGE FAILED" in output3:
        output4 = output3
    else:
        cmd4 = [sys.executable, analyze_script, "--run_output_dir", run_dir, "--quiet"]
        output4 = run_script(cmd4, "Analyze Performance")

    # --- 3. Extract status information from the fresh script outputs ---
    parsing_status = "N/A"
    # New regex to catch the detailed parser summary from Stage 3
    parser_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+):(\d+)>>>", output3)
    if parser_match:
        parsed_count = int(parser_match.group(1))
        total_count = int(parser_match.group(2))
        warning_count = int(parser_match.group(3))
        parsing_status = f"{parsed_count}/{total_count} responses parsed"
        if warning_count > 0:
            parsing_status += f" ({warning_count} warnings)"

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
    
    # Extract original run date from directory name for the report header.
    original_run_date = "N/A"
    date_match = re.search(r'run_(\d{8})_(\d{6})', dir_basename)
    if date_match:
        try:
            date_str = f"{date_match.group(1)}{date_match.group(2)}"
            original_run_date = datetime.datetime.strptime(date_str, "%Y%m%d%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass # Keep "N/A" if parsing fails

    with open(report_path, 'w', encoding='utf-8') as report_file:
        # Header Section
        header = f"""
================================================================================
 REPLICATION RUN REPORT (REBUILT ON {datetime.datetime.now().strftime("%Y-%m-%d")})
================================================================================
Date:            {original_run_date}
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
        base_query_filename = archived_config.get('Filenames', 'base_query_src', fallback='base_query.txt')
        base_query_path = os.path.join(PROJECT_ROOT, 'data', base_query_filename)
        report_file.write("\n--- Base Query Prompt Used ---\n")
        try:
            with open(base_query_path, 'r', encoding='utf-8') as f_prompt:
                report_file.write(f_prompt.read())
        except FileNotFoundError:
            report_file.write(f"ERROR: Could not find base query file at {base_query_path}\n")
        report_file.write("\n-------------------------------\n\n")

        # Full Analysis Output Section
        analysis_header = (
            "================================================================================\n"
            "### OVERALL META-ANALYSIS RESULTS ###\n"
            "================================================================================\n\n"
        )
        report_file.write(analysis_header)

        text_match = re.search(r'<<<ANALYSIS_SUMMARY_START>>>(.*?)<<<METRICS_JSON_START>>>', output4, re.DOTALL)
        json_match = re.search(r'(<<<METRICS_JSON_START>>>.*?<<<METRICS_JSON_END>>>)', output4, re.DOTALL)

        if text_match:
            analysis_text = text_match.group(1).strip()
            report_file.write(analysis_text + "\n\n")
        
        if json_match:
            json_block = json_match.group(1).strip()
            report_file.write(json_block + "\n")

        if not text_match and not json_match:
            logging.warning("Could not find analysis markers in Stage 4 output. Writing raw output.")
            report_file.write(output4)

    logging.info(f"  -> Successfully rebuilt report: {report_filename}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Rebuilds replication reports to their original high-fidelity format.")
    parser.add_argument('base_dir', help="The base directory to scan for experiment runs (e.g., 'output/reports/6_Study_4').")
    parser.add_argument('--verbose', '-v', action='store_true', help="Enable detailed, per-directory logging instead of a progress bar.")
    args = parser.parse_args()

    # --- Load the main config and the compatibility map ONCE ---
    try:
        # Import the globally loaded config and the map parser function
        from config_loader import APP_CONFIG, get_config_compatibility_map

        compat_map = get_config_compatibility_map(APP_CONFIG)
        if not compat_map:
            logging.warning("No [ConfigCompatibility] map found in config.ini. Assuming all configs are modern.")

    except Exception as e:
        logging.error(f"Could not load main config or compatibility map. Error: {e}")
        sys.exit(1)

    if not os.path.isdir(args.base_dir):
        logging.error(f"Error: Provided directory does not exist: {args.base_dir}")
        return

    run_dirs = glob.glob(os.path.join(args.base_dir, '**', 'run_*'), recursive=True)
    if not run_dirs:
        logging.info(f"No 'run_*' directories found in {args.base_dir}.")
        return

    logging.info(f"Found {len(run_dirs)} total run directories. Rebuilding reports...")

    iterable = run_dirs
    if not args.verbose:
        # Suppress INFO-level logs to keep the progress bar clean
        logging.getLogger().setLevel(logging.WARNING)
        iterable = tqdm(run_dirs, desc="Progress", unit="dir", ncols=80)

    success_count = 0
    total_count = 0
    try:
        for run_dir in iterable:
            if os.path.isdir(run_dir):
                total_count += 1
                # --- Pass the map to the worker function ---
                if rebuild_report_for_run(run_dir, compat_map):
                    success_count += 1

        # Reset logger to INFO to ensure final summary is always displayed
        logging.getLogger().setLevel(logging.INFO)
        logging.info(f"\nReport rebuilding complete. Successfully processed {success_count}/{total_count} directories.")

    except KeyboardInterrupt:
        # Ensure the cursor moves to a new line after the progress bar is interrupted
        print("\n", file=sys.stderr)
        logging.warning("Operation interrupted by user (Ctrl+C). Exiting gracefully.")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/rebuild_reports.py ===
