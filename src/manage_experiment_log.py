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
# Filename: src/manage_experiment_log.py

"""
Manages the lifecycle of the `experiment_log.csv`.

This script provides a robust, command-based interface for creating and
maintaining the experiment's log. It is called by `experiment_manager.py`
at key stages of a run to ensure the log is always accurate and complete.

Core Commands:
-   `start`: Initializes a new experiment. It overwrites any existing log file
    and creates a fresh `experiment_log.csv` with only a header.

-   `rebuild`: The primary method for ensuring log integrity. It scans the
    experiment directory, parses every `replication_report.txt`, and builds a
    new, clean log from scratch by overwriting the existing file. This ensures
    the log perfectly reflects the state of all completed replications.

-   `finalize`: A safe, idempotent command to complete the log. It strips any
    pre-existing summary from the file, then recalculates and appends a fresh
    summary footer. This can be run multiple times without causing duplication.
"""

import os
import sys
import re
import json
import csv
import glob
import argparse
import io
from datetime import datetime

try:
    from config_loader import PROJECT_ROOT
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import PROJECT_ROOT

# --- Core Logic Functions (Shared by all modes) ---

def parse_report_file(report_path):
    """Parses a single report file to extract all necessary fields for the log."""
    # This function remains the same as it's the core parsing logic.
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    params = {}
    metrics = {'mean_mrr': 'N/A', 'mean_top_1_acc': 'N/A'}

    def extract(pattern, text):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    params['run_directory'] = extract(r"Run Directory:\s*(.*)", content)
    params['status'] = extract(r"Final Status:\s*(.*)", content)
    params['parsing_status'] = extract(r"Parsing Status:\s*(.*)", content)

    if params['run_directory']:
        rep_match = re.search(r"rep-(\d+)", params['run_directory'])
        params['replication'] = rep_match.group(1) if rep_match else 'N/A'
        time_match = re.search(r'run_(\d{8}_\d{6})', params['run_directory'])
        params['start_time'] = datetime.strptime(time_match.group(1), '%Y%m%d_%H%M%S') if time_match else None
    
    json_match = re.search(r"<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>", content, re.DOTALL)
    if json_match:
        try:
            json_data = json.loads(json_match.group(1).strip())
            metrics.update(json_data)
        except (json.JSONDecodeError, IndexError):
            print(f"Warning: Malformed JSON in {os.path.basename(report_path)}")
            
    end_time = None
    time_match_end = re.search(r'_(\d{8}-\d{6})\.txt$', os.path.basename(report_path))
    if time_match_end:
        end_time = datetime.strptime(time_match_end.group(1), '%Y%m%d-%H%M%S')

    duration_str = "N/A"
    if params.get('start_time') and end_time:
        duration_seconds = (end_time - params['start_time']).total_seconds()
        hours, rem = divmod(duration_seconds, 3600)
        minutes, secs = divmod(rem, 60)
        duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(round(secs)):02d}"

    mrr_val = metrics.get('mean_mrr')
    top1_val = metrics.get('mean_top_1_acc')

    return {
        'ReplicationNum': params.get('replication', 'N/A'),
        'Status': params.get('status', 'UNKNOWN'),
        'StartTime': params['start_time'].strftime('%Y-%m-%d %H:%M:%S') if params.get('start_time') else 'N/A',
        'EndTime': end_time.strftime('%Y-%m-%d %H:%M:%S') if end_time else 'N/A',
        'Duration': duration_str,
        'ParsingStatus': params.get('parsing_status', 'N/A'),
        'MeanMRR': f"{mrr_val:.4f}" if isinstance(mrr_val, (int, float)) else 'N/A',
        'MeanTop1Acc': f"{top1_val:.2%}" if isinstance(top1_val, (int, float)) else 'N/A',
        'RunDirectory': params.get('run_directory', 'N/A'),
        'ErrorMessage': 'N/A' if params.get('status') == 'COMPLETED' else 'See report'
    }

def write_log_row(log_file_path, log_entry, fieldnames):
    """Appends a single row to the CSV, writing a header if needed."""
    file_exists = os.path.exists(log_file_path)
    with open(log_file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        # Only write the row if the entry is not empty
        if log_entry:
            writer.writerow(log_entry)

def finalize_log(log_file_path):
    """Reads the log, cleans any old summary, and appends a new, correct summary."""
    if not os.path.exists(log_file_path): return

    # Step 1: Read all lines and find where any previous summary starts
    with open(log_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    data_lines = lines
    for i, line in enumerate(lines):
        # The summary starts with this header. We truncate the file here.
        if line.strip().startswith('BatchSummary'):
            data_lines = lines[:i]
            break
    
    # Remove any trailing blank lines from the data to prevent parsing errors
    while data_lines and not data_lines[-1].strip():
        data_lines.pop()

    clean_csv_content = "".join(data_lines)
    if not clean_csv_content.strip() or not data_lines:
        print("Warning: Log file contains no valid data rows. Cannot finalize.")
        return

    # Step 2: Parse only the cleaned CSV data in-memory
    rows = list(csv.DictReader(io.StringIO(clean_csv_content)))
    if not rows: return

    # Step 3: Perform calculations on the clean data (this logic is now safe)
    summary_start_time = rows[0]['StartTime']
    summary_end_time = rows[-1]['EndTime']
    total_duration_str = "N/A"
    try:
        time_format = '%Y-%m-%d %H:%M:%S'
        start_dt = datetime.strptime(summary_start_time, time_format)
        end_dt = datetime.strptime(summary_end_time, time_format)
        
        total_seconds = (end_dt - start_dt).total_seconds()
        hours, rem = divmod(total_seconds, 3600)
        minutes, secs = divmod(rem, 60)
        total_duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(round(secs)):02d}"
    except (ValueError, TypeError) as e:
        print(f"Warning: Could not calculate total duration. Error: {e}", file=sys.stderr)
    
    completed_count = sum(1 for r in rows if r["Status"] == "COMPLETED")
    failed_count = len(rows) - completed_count
    
    # Step 4: Atomically write the clean data AND the new summary back to the file
    with open(log_file_path, 'w', newline='', encoding='utf-8') as f:
        # Write back the original, clean data rows
        f.writelines(data_lines)
        # Append the new summary
        f.write('\n')
        f.write('BatchSummary,StartTime,EndTime,TotalDuration,Completed,Failed\n')
        f.write(f'Totals,{summary_start_time},{summary_end_time},{total_duration_str},{completed_count},{failed_count}\n')
    relative_path = os.path.relpath(log_file_path, PROJECT_ROOT)
    print(f"Cleaned and appended batch summary to:\n{relative_path}\n")

# --- Main Execution ---

def main():
    """Main entry point to manage the batch run log."""
    parser = argparse.ArgumentParser(description="A tool to update, rebuild, or finalize the batch run log.")
    subparsers = parser.add_subparsers(dest='mode', required=True, help="The operation to perform")

    # --- 'start' command (NEW) ---
    parser_start = subparsers.add_parser('start', help="Start a new batch, backing up any old log and creating a fresh one.")
    parser_start.add_argument('output_dir', type=str, help="Path to the base output directory.")

    # The 'update' command has been removed as it is legacy.
    # The 'rebuild' command is the primary method for populating the log.

    # --- 'rebuild' command ---
    parser_rebuild = subparsers.add_parser('rebuild', help="Recreate the entire log from all existing reports, backing up the original.")
    parser_rebuild.add_argument('output_dir', type=str, help="Path to the base output directory containing all run folders.")

    # --- 'finalize' command ---
    parser_finalize = subparsers.add_parser('finalize', help="Append the summary footer to an existing log.")
    parser_finalize.add_argument('output_dir', type=str, help="Path to the base output directory where the log is located.")
    
    args = parser.parse_args()

    # --- Define shared variables ---
    fieldnames = ["ReplicationNum", "Status", "StartTime", "EndTime", "Duration", "ParsingStatus", "MeanMRR", "MeanTop1Acc", "RunDirectory", "ErrorMessage"]
    
    if args.mode == 'start':
        log_file_path = os.path.join(args.output_dir, "experiment_log.csv")
        # Overwrite any existing log file by opening in 'w' mode.
        with open(log_file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        print("Initialized new batch run log with header.")

    # The 'update' command has been removed.

    elif args.mode == 'rebuild':
        log_file_path = os.path.join(args.output_dir, "experiment_log.csv")
        report_files = glob.glob(os.path.join(args.output_dir, "run_*", "replication_report_*.txt"))

        # Overwrite any existing log by opening in 'w' mode. This removes the need for backups.
        with open(log_file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            if report_files:
                # Sort reports by replication number to ensure correct order
                report_files.sort(key=lambda p: int(re.search(r'rep-(\d+)', os.path.basename(os.path.dirname(p))).group(1)))

                for report_path in report_files:
                    log_entry = parse_report_file(report_path)
                    writer.writerow(log_entry)
        
        if not report_files:
            print("No report files found. An empty log with a header has been created.", file=sys.stderr)
        else:
            print(f"\nSuccessfully rebuilt {os.path.basename(log_file_path)} from {len(report_files)} reports.")

    elif args.mode == 'finalize':
        log_file_path = os.path.join(args.output_dir, "experiment_log.csv")
        finalize_log(log_file_path)

if __name__ == "__main__":
    main()

# === End of src/manage_experiment_log.py ===
