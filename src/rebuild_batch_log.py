#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/rebuild_batch_log.py

"""
Rebuild Batch Log Utility (rebuild_batch_log.py)

Purpose:
This script reconstructs a comprehensive batch run log by scanning a directory
for 'run_*' subdirectories and extracting metadata and results from various
log files within each run. It is a recovery tool for when the original
'batch_run_log.csv' is missing or incomplete.

Workflow:
1.  Scans a target directory for 'run_*' subdirectories.
2.  The scan depth is controlled by the --depth argument.
3.  For each run, it extracts:
    - Run parameters (model, temp, etc.) from the directory name.
    - Start and end timestamps from 'api_times.log'.
    - Performance metrics (MRR, Top-K) from the JSON block in 'report.txt'.
    - If JSON fails, it falls back to regex parsing on 'report.txt'.
4.  It compiles this information into a new CSV file named 'batch_run_log_rebuilt.csv'.
5.  A summary of total runs and time elapsed is appended to the CSV.

Command-Line Usage:
    # Rebuild log from the './output' directory (depth 0)
    python src/rebuild_batch_log.py ./output

    # Rebuild from a directory and its immediate subdirectories
    python src/rebuild_batch_log.py /path/to/batch --depth 1

    # Rebuild from an entire directory tree recursively
    python src/rebuild_batch_log.py /path/to/batch --depth -1
"""

import os
import sys
import glob
import re
import json
import csv
from datetime import datetime
import fnmatch
import pathlib
import argparse

def format_seconds_to_mm_ss(seconds: float) -> str:
    """Formats total seconds into MM:SS string."""
    if seconds is None or seconds < 0:
        return "N/A"
    total_seconds = round(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{int(minutes):02d}:{int(secs):02d}"

def format_seconds_to_hh_mm_ss(seconds: float) -> str:
    """Formats total seconds into HH:MM:SS string."""
    if seconds is None or seconds < 0:
        return "N/A"
    total_seconds = round(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}"

def parse_run_directory(dir_path):
    """Extracts metadata directly from the run directory's name."""
    dir_name = os.path.basename(dir_path)
    data = {'RunDirectory': dir_name, 'Status': 'UNKNOWN'}
    
    rep_match = re.search(r'rep-(\d+)', dir_name)
    if rep_match:
        data['ReplicationNum'] = int(rep_match.group(1))

    time_match = re.search(r'run_(\d{8}_\d{6})', dir_name)
    if time_match:
        try:
            dt_obj = datetime.strptime(time_match.group(1), '%Y%m%d_%H%M%S')
            data['StartTime'] = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            data['StartTime'] = "N/A"
            
    return data

def get_report_metrics(run_dir_path):
    """Finds and robustly parses the report file for metrics and EndTime."""
    data = {'EndTime': "N/A", 'ParsingStatus': "N/A", 'MeanMRR': "N/A", 'MeanTop1Acc': "N/A", 'ErrorMessage': "N/A", 'Status': 'UNKNOWN'}

    try:
        # Since run_dir_path is already absolute, we can directly list its contents.
        # os.listdir works with long paths, even if open() does not without a prefix.
        if not os.path.isdir(run_dir_path):
            data['ErrorMessage'] = "Run directory does not exist."
            return data
        
        all_filenames = os.listdir(run_dir_path)
        
        patterns_to_try = [
            'pipeline_run_report_*.txt',
            'replication_report_*.txt',
        ]
        
        report_filename = None
        for pattern in patterns_to_try:
            matching_files = sorted([f for f in all_filenames if fnmatch.fnmatch(f, pattern)])
            if matching_files:
                report_filename = matching_files[0]
                break
        
        if not report_filename:
            data['ErrorMessage'] = "Report file not found."
            return data

        # Construct the full path to the report file.
        full_report_path = os.path.join(run_dir_path, report_filename)
        
        # On Windows, prepend the long-path-aware prefix to the final path.
        # This is the correct and definitive way to bypass the MAX_PATH limit.
        path_to_open = full_report_path
        if sys.platform == "win32":
            path_to_open = "\\\\?\\" + os.path.abspath(full_report_path)
        
        with open(path_to_open, 'r', encoding='utf-8') as f:
            content = f.read()

        data['Status'] = "COMPLETED"

        parsing_match = re.search(r"Parsing Status:\s*(.*)", content)
        if parsing_match:
            data['ParsingStatus'] = parsing_match.group(1).strip()

        time_match = re.search(r'_(\d{8}-\d{6})\.txt$', report_filename)
        if time_match:
            try:
                dt_obj = datetime.strptime(time_match.group(1), '%Y%m%d-%H%M%S')
                data['EndTime'] = dt_obj.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        
        json_match = re.search(r'<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>', content, re.DOTALL)
        if json_match:
            try:
                metrics = json.loads(json_match.group(1).strip())
                data['MeanMRR'] = f"{metrics.get('mean_mrr', 0.0):.4f}"
                data['MeanTop1Acc'] = f"{metrics.get('mean_top_1_acc', 0.0):.2%}"
                data['ErrorMessage'] = "N/A"
                return data
            except (json.JSONDecodeError, KeyError):
                data['ErrorMessage'] = "Could not parse metrics JSON. "
        
        mrr_match = re.search(r"Overall Ranking Performance \(MRR\).*?Mean:\s+([\d.]+)", content)
        top1_match = re.search(r"Overall Ranking Performance \(Top-1 Accuracy\).*?Mean:\s+([\d.]+)%", content)

        if mrr_match and top1_match:
            data['MeanMRR'] = f"{float(mrr_match.group(1)):.4f}"
            top1_val_as_float = float(top1_match.group(1)) / 100.0
            data['MeanTop1Acc'] = f"{top1_val_as_float:.2%}"
            data['ErrorMessage'] = "N/A"
        else:
            if 'ErrorMessage' not in data or data['ErrorMessage'] == 'N/A':
                data['ErrorMessage'] = "Metrics not found in report."

    except FileNotFoundError:
        data['ErrorMessage'] = "OS error: MAX_PATH limit exceeded or file does not exist."
    except Exception as e:
        data['ErrorMessage'] = f"Error processing directory: {type(e).__name__}"

    return data

def get_duration_from_api_log(run_dir_path):
    """Finds the api_times.log and gets the final total elapsed time."""
    api_log_path = os.path.join(run_dir_path, 'api_times.log')
    if not os.path.exists(api_log_path):
        return None
        
    last_elapsed_seconds = None
    try:
        with open(api_log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in reversed(lines):
                parts = line.strip().split('\t')
                if len(parts) >= 3:
                    try:
                        last_elapsed_seconds = float(parts[2])
                        return last_elapsed_seconds
                    except (ValueError, IndexError):
                        continue
    except Exception:
        return None
    return last_elapsed_seconds

def main():
    parser = argparse.ArgumentParser(description="Rebuilds a 'batch_run_log.csv' from existing run directories.")
    parser.add_argument("target_dir", nargs='?', default=None, help="The top-level directory to scan. Defaults to the project's 'output' directory.")
    parser.add_argument("--depth", type=int, default=0, help="Directory scan depth. 0 for target dir only, N for N levels deep, -1 for infinite recursion.")
    args = parser.parse_args()

    if args.target_dir:
        base_dir = args.target_dir
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        base_dir = os.path.join(project_root, 'output')
        print(f"No directory specified. Defaulting to '{base_dir}'")

    # Convert to an absolute path to prevent ambiguity with relative paths.
    base_dir = os.path.abspath(base_dir)

    if not os.path.isdir(base_dir):
        print(f"Error: Specified directory '{base_dir}' does not exist.")
        sys.exit(1)

    run_dirs = []
    if args.depth == -1:
        # Infinite recursion
        glob_path = os.path.join(base_dir, "**", "run_*")
        run_dirs = sorted(glob.glob(glob_path, recursive=True))
    else:
        # Controlled depth from 0 to N.
        # We collect all dirs at each level up to the specified depth.
        
        # Level 0 (the base_dir itself)
        path_pattern = os.path.join(base_dir, "run_*")
        run_dirs.extend(glob.glob(path_pattern))
        
        # Levels 1 to N
        current_pattern = base_dir
        for i in range(args.depth):
            current_pattern = os.path.join(current_pattern, "*")
            path_pattern = os.path.join(current_pattern, "run_*")
            run_dirs.extend(glob.glob(path_pattern))
            
    # Filter out any paths that are not directories, which can happen with glob.
    run_dirs = [d for d in run_dirs if os.path.isdir(d)]
    
    # Using set to remove duplicates and then sorting.
    run_dirs = sorted(list(set(run_dirs)))

    if not run_dirs:
        print(f"No 'run_*' directories found in '{base_dir}'.")
        return
        
    all_run_data = []
    print(f"Found {len(run_dirs)} run directories. Processing...")

    for run_dir in run_dirs:
        # Use relpath for cleaner logging in recursive mode
        relative_path = os.path.relpath(run_dir, base_dir)
        print(f"  - Processing {relative_path}...")
        
        run_data = parse_run_directory(run_dir)
        report_data = get_report_metrics(run_dir)
        run_data.update(report_data)

        duration_seconds = get_duration_from_api_log(run_dir)
        
        if duration_seconds is None and run_data['StartTime'] != "N/A" and run_data['EndTime'] != "N/A":
            try:
                start_dt = datetime.strptime(run_data['StartTime'], '%Y-%m-%d %H:%M:%S')
                end_dt = datetime.strptime(run_data['EndTime'], '%Y-%m-%d %H:%M:%S')
                duration_seconds = (end_dt - start_dt).total_seconds()
            except ValueError:
                duration_seconds = None
        
        run_data['Duration'] = format_seconds_to_mm_ss(duration_seconds)
        
        all_run_data.append(run_data)

    all_run_data.sort(key=lambda x: x.get('ReplicationNum', 9999))
    
    batch_log_path = os.path.join(base_dir, "batch_run_log_rebuilt.csv")
    fieldnames = ["ReplicationNum", "Status", "StartTime", "EndTime", "Duration", "ParsingStatus", "MeanMRR", "MeanTop1Acc", "RunDirectory", "ErrorMessage"]
    
    try:
        with open(batch_log_path, 'w', newline='', encoding='utf-8') as f:
            # Create a writer that does not quote any fields.
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_NONE)
            writer.writeheader() # This will write the header without quotes.
            writer.writerows(all_run_data)

            # --- Calculate and append the batch summary ---
            if all_run_data:
                summary_start_time = all_run_data[0]['StartTime']
                summary_end_time = all_run_data[-1]['EndTime']
                
                total_duration_str = "N/A"
                try:
                    start_dt = datetime.strptime(summary_start_time, '%Y-%m-%d %H:%M:%S')
                    end_dt = datetime.strptime(summary_end_time, '%Y-%m-%d %H:%M:%S')
                    total_seconds = (end_dt - start_dt).total_seconds()
                    total_duration_str = format_seconds_to_hh_mm_ss(total_seconds)
                except (ValueError, TypeError):
                    pass
                
                completed_count = sum(1 for run in all_run_data if run['Status'] == 'COMPLETED')
                failed_count = len(all_run_data) - completed_count
                
                # Write the summary block manually (already unquoted).
                f.write('\n')
                f.write('BatchSummary,StartTime,EndTime,TotalDuration,Completed,Failed\n')
                f.write(f'Totals,{summary_start_time},{summary_end_time},{total_duration_str},{completed_count},{failed_count}\n')

        print(f"\nSuccessfully rebuilt batch log for {len(all_run_data)} runs.")
        print(f"Log file saved to: {batch_log_path}")
    except IOError as e:
        print(f"\nError writing to {batch_log_path}: {e}")

if __name__ == "__main__":
    main()