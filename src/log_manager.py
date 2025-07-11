#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/log_manager.py

"""
Provides a command-line interface to manage the experiment's batch run log.

This script centralizes all interactions with `batch_run_log.csv`, ensuring that
logging is robust and maintainable. It is called by the main replication manager
to handle the state of the log file at different stages of the experiment.

Modes of Operation:
-   'start': Prepares for a new experiment. It safely archives any existing log
    file and creates a new, empty `batch_run_log.csv` with only a header.

-   'update': Appends a single entry to the log from a completed replication's
    report file. This provides a real-time record of progress.

-   'rebuild': Safely rebuilds the log to ensure integrity when resuming a run.
    It backs up the original log, then creates a new, clean version by parsing all
    existing replication reports. This ensures the log is in a clean, appendable
    state.

-   'finalize': Ccleans and finalizes the log. It first removes any existing summary
    blocks from the end of the file, then recalculates a fresh summary from the
    remaining clean data rows and appends it. This ensures the log always has a
    single, correct summary footer, making the command safe to re-run.
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
    print(f"Cleaned and appended batch summary to {os.path.basename(log_file_path)}")

# --- Main Execution ---

def main():
    """Main entry point to manage the batch run log."""
    parser = argparse.ArgumentParser(description="A tool to update, rebuild, or finalize the batch run log.")
    subparsers = parser.add_subparsers(dest='mode', required=True, help="The operation to perform")

    # --- 'start' command (NEW) ---
    parser_start = subparsers.add_parser('start', help="Start a new batch, backing up any old log and creating a fresh one.")
    parser_start.add_argument('output_dir', type=str, help="Path to the base output directory.")

    # --- 'update' command ---
    parser_update = subparsers.add_parser('update', help="Append a single replication's data to the log.")
    parser_update.add_argument('report_file', type=str, help="Path to the single replication_report.txt file.")

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
                print(f"Archived existing log to: {os.path.basename(backup_path)}")
            except OSError as e:
                print(f"Error: Could not back up existing log file: {e}", file=sys.stderr)
                sys.exit(1)
        # Create a new, empty log with only a header
        write_log_row(log_file_path, {}, fieldnames) # Pass empty dict to just write header
        # The write_log_row needs a slight modification to handle this
        print("Initialized new batch run log with header.")

    elif args.mode == 'update':
        if not os.path.exists(args.report_file):
            print(f"Error: Report file not found at '{args.report_file}'", file=sys.stderr)
            sys.exit(1)
        log_entry = parse_report_file(args.report_file)
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(args.report_file)), "batch_run_log.csv")
        write_log_row(log_file_path, log_entry, fieldnames)
        print(f"Updated {os.path.basename(log_file_path)} for replication {log_entry['ReplicationNum']}")

    elif args.mode == 'rebuild':
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        # --- MODIFICATION: Back up instead of deleting ---
        if os.path.exists(log_file_path):
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup_path = f"{log_file_path}.{timestamp}.bak"
            try:
                os.rename(log_file_path, backup_path)
                print(f"Backed up existing log to {os.path.basename(backup_path)} before rebuild.")
            except OSError as e:
                print(f"Error: Could not back up existing log file: {e}", file=sys.stderr)
                sys.exit(1)
        # --- END MODIFICATION ---
        
        report_files = glob.glob(os.path.join(args.output_dir, "run_*", "replication_report_*.txt"))
        if not report_files:
            print("No report files found. Creating empty log.", file=sys.stderr)
            # Still create an empty log so the pipeline doesn't fail
            write_log_row(log_file_path, {}, fieldnames)
            sys.exit(0)

        # Sort reports by replication number from the filename to ensure correct order
        report_files.sort(key=lambda p: int(re.search(r'rep-(\d+)', os.path.basename(os.path.dirname(p))).group(1)))

        for report_path in report_files:
            log_entry = parse_report_file(report_path)
            write_log_row(log_file_path, log_entry, fieldnames)
        print(f"Successfully rebuilt {os.path.basename(log_file_path)} from {len(report_files)} reports.")

    elif args.mode == 'finalize':
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        finalize_log(log_file_path)

if __name__ == "__main__":
    main()

# === End of src/log_manager.py ===