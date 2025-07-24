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
# Filename: src/replication_log_manager.py

"""
Manages the lifecycle of the human-readable `batch_run_log.csv`.

This script provides a robust, command-based interface for creating and
maintaining the experiment's batch log. It is called by `experiment_manager.py`
at key stages of a run to ensure the log is always accurate and complete.

Core Commands:
-   `start`: Initializes a new experiment. It archives any existing log file
    and creates a fresh `batch_run_log.csv` with only a header.

-   `rebuild`: The primary method for ensuring log integrity. It scans the
    experiment directory, parses every `replication_report.txt`, and builds a
    new, clean log from scratch, ensuring it perfectly reflects the state of
    all completed replications.

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

# --- Core Logic Functions (Shared by all modes) ---

def parse_report_file(report_path):
    """Parses a single report file to extract all necessary fields for the log."""
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    params = {}
    metrics = {}

    def extract(pattern, text):
        match = re.search(pattern, text, re.MULTILINE)
        return match.group(1).strip() if match else None

    # --- Extract from Header ---
    params['run_directory'] = extract(r"^Run Directory:\s*(run_.*)", content)
    params['status'] = extract(r"^Final Status:\s*(.*)", content)
    params['parsing_status'] = extract(r"^Parsing Status:\s*(.*)", content)
    params['replication'] = extract(r"^Replication Number:\s*(\d+)", content)
    
    start_time_str = extract(r"^Date:\s*(.*)", content)
    start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S') if start_time_str and 'N/A' not in start_time_str else None

    # --- Extract from JSON ---
    json_match = re.search(r"<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>", content, re.DOTALL)
    if json_match:
        try:
            metrics = json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            print(f"Warning: Malformed JSON in {os.path.basename(report_path)}")
            
    # --- EndTime and Duration ---
    end_time = None
    duration_str = "N/A"
    report_filename = os.path.basename(report_path)
    time_match_end = re.search(r'_(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})\.txt$', report_filename)
    if time_match_end:
        try:
            report_time = datetime.strptime(time_match_end.group(1), '%Y-%m-%d_%H-%M-%S')
            
            # For original runs, EndTime IS the report time.
            if "(Reprocessed:" not in content:
                end_time = report_time
                if start_time:
                    duration_seconds = (end_time - start_time).total_seconds()
                    if duration_seconds >= 0:
                        hours, rem = divmod(duration_seconds, 3600)
                        minutes, secs = divmod(rem, 60)
                        duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(round(secs)):02d}"
            else:
                # For reprocessed runs, EndTime and Duration are not applicable.
                end_time = None
                duration_str = "N/A"
        except (ValueError, TypeError):
            end_time = None

    mrr_val = metrics.get('mean_mrr')
    top1_val = metrics.get('mean_top_1_acc')

    return {
        'ReplicationNum': params.get('replication', 'N/A'),
        'Status': params.get('status', 'UNKNOWN'),
        'StartTime': start_time.strftime('%Y-%m-%d %H:%M:%S') if start_time else 'N/A',
        'EndTime': end_time.strftime('%Y-%m-%d %H:%M:%S') if end_time else 'N/A',
        'Duration': duration_str,
        'ParsingStatus': params.get('parsing_status', 'N/A'),
        'MeanMRR': f"{mrr_val:.4f}" if isinstance(mrr_val, (float, int)) else 'N/A',
        'MeanTop1Acc': f"{top1_val:.2%}" if isinstance(top1_val, (float, int)) else 'N/A',
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
    print(f"Cleaned and appended batch summary to:\n{log_file_path}")

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
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        if os.path.exists(log_file_path):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = f"{log_file_path}.{timestamp}.bak"
            try:
                # Back up the old log by moving it
                os.rename(log_file_path, backup_path)
                print(f"Archived existing log to:\n{backup_path}")
            except OSError as e:
                print(f"Error: Could not back up existing log file: {e}", file=sys.stderr)
                sys.exit(1)
        # Create a new, empty log with only a header
        write_log_row(log_file_path, {}, fieldnames) # Pass empty dict to just write header
        # The write_log_row needs a slight modification to handle this
        print("Initialized new batch run log with header.")

    # The 'update' command has been removed.

    elif args.mode == 'rebuild':
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        if os.path.exists(log_file_path):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = f"{log_file_path}.{timestamp}.bak"
            try:
                os.rename(log_file_path, backup_path)
                print(f"Backed up existing log to:\n{backup_path}\nbefore rebuild.")
            except OSError as e:
                print(f"Error: Could not back up existing log file: {e}", file=sys.stderr)
                sys.exit(1)
        
        # --- Manifest-Aware Refactoring ---
        # 1. Load the experiment manifest to get global parameters
        manifest_path = os.path.join(args.output_dir, "experiment_manifest.json")
        manifest_params = {}
        try:
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            manifest_params = manifest_data.get("parameters", {})
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"FATAL: Could not load or parse experiment_manifest.json. Error: {e}", file=sys.stderr)
            sys.exit(1)

        # 2. Update fieldnames to include parameters from the manifest
        param_keys = ['model_name', 'temperature', 'mapping_strategy', 'group_size']
        # Ensure fieldnames are updated correctly, inserting new keys in a sensible order
        fieldnames.insert(5, 'model_name')
        fieldnames.insert(6, 'temperature')
        fieldnames.insert(7, 'mapping_strategy')
        fieldnames.insert(8, 'group_size')

        report_files = glob.glob(os.path.join(args.output_dir, "run_*", "replication_report_*.txt"))
        if not report_files:
            print("No report files found. Creating empty log.", file=sys.stderr)
            write_log_row(log_file_path, {}, fieldnames)
            sys.exit(0)

        # Use a more robust sorting key
        def get_rep_num_from_path(path):
            try:
                dir_name = os.path.basename(os.path.dirname(path))
                match = re.search(r'rep-(\d+)', dir_name)
                return int(match.group(1)) if match else 9999
            except (ValueError, TypeError, AttributeError):
                return 9999
        report_files.sort(key=get_rep_num_from_path)

        # 3. For each report, merge its data with the manifest parameters
        for report_path in report_files:
            try:
                log_entry = parse_report_file(report_path)
                # Inject the global parameters from the manifest into each log row
                for key in param_keys:
                    log_entry[key] = manifest_params.get(key, 'N/A')
                
                write_log_row(log_file_path, log_entry, fieldnames)
            except Exception as e:
                # If any report fails to parse, print a detailed error and continue.
                # This prevents a single bad report from crashing the entire process.
                print(f"\nERROR: Failed to parse report file: {report_path}", file=sys.stderr)
                print(f"       Reason: {e}", file=sys.stderr)
                # Write a placeholder error row to the log for diagnostics
                error_entry = {fn: 'N/A' for fn in fieldnames}
                error_entry.update({
                    'ReplicationNum': 'ERR',
                    'Status': 'PARSE_FAILED',
                    'RunDirectory': os.path.basename(os.path.dirname(report_path)),
                    'ErrorMessage': f"Parsing failed: {e}"
                })
                write_log_row(log_file_path, error_entry, fieldnames)
        print(f"Successfully rebuilt {os.path.basename(log_file_path)} from {len(report_files)} reports.")

    elif args.mode == 'finalize':
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        finalize_log(log_file_path)

if __name__ == "__main__":
    main()

# === End of src/replication_log_manager.py ===
