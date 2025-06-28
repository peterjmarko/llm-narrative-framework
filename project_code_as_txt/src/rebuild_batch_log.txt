#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/rebuild_batch_log.py

"""
Rebuild Batch Run Log (rebuild_batch_log.py)

Purpose:
This utility script reverse-engineers a 'batch_run_log.csv' file by parsing
the data from existing replication run directories (e.g., 'run_*'). It is
useful for creating a summary log after the fact if the original was lost or
if the batch runner was executed without this logging capability.

The script iterates through each run directory, extracting metrics from various
source files:
-   Replication Number, Start Time: From the run directory name.
-   End Time, Mean MRR, Mean Top-1 Acc: From the 'replication_report_...txt' file,
  with a fallback to parsing the text summary if the JSON block is missing.
-   Duration: From the final 'Total_Elapsed_s' value in 'api_times.log'.

It then compiles all this information into a new 'batch_run_log_rebuilt.csv' file in
the specified output directory.
"""

import os
import sys
import glob
import re
import json
import csv
from datetime import datetime
import fnmatch

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
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
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

    run_dirs = sorted(glob.glob(os.path.join(base_dir, "run_*")))
    if not run_dirs:
        print(f"No 'run_*' directories found in '{base_dir}'.")
        return
        
    all_run_data = []
    print(f"Found {len(run_dirs)} run directories. Processing...")

    for run_dir in run_dirs:
        print(f"  - Processing {os.path.basename(run_dir)}...")
        
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