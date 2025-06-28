# Filename: src/log_manager.py

import os
import sys
import re
import json
import csv
import glob
import argparse
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
    write_header = not os.path.exists(log_file_path)
    with open(log_file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(log_entry)

def finalize_log(log_file_path):
    """Reads the generated log and appends a summary footer."""
    if not os.path.exists(log_file_path): return
    with open(log_file_path, 'r', newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    if not rows: return

    summary_start_time = rows[0]['StartTime']
    summary_end_time = rows[-1]['EndTime']
    total_duration_str = "N/A"
    try:
        # The format string for both start and end times must be identical
        time_format = '%Y-%m-%d %H:%M:%S'
        start_dt = datetime.strptime(summary_start_time, time_format)
        end_dt = datetime.strptime(summary_end_time, time_format) # <-- This line is now corrected
        
        total_seconds = (end_dt - start_dt).total_seconds()
        hours, rem = divmod(total_seconds, 3600)
        minutes, secs = divmod(rem, 60)
        total_duration_str = f"{int(hours):02d}:{int(minutes):02d}:{int(round(secs)):02d}"
    except (ValueError, TypeError) as e:
        # Added a print statement for better debugging in the future
        print(f"Warning: Could not calculate total duration. Error: {e}", file=sys.stderr)
    
    completed_count = sum(1 for r in rows if r["Status"] == "COMPLETED")
    failed_count = len(rows) - completed_count
    
    with open(log_file_path, 'a', newline='', encoding='utf-8') as f:
        f.write('\n')
        f.write('BatchSummary,StartTime,EndTime,TotalDuration,Completed,Failed\n')
        f.write(f'Totals,{summary_start_time},{summary_end_time},{total_duration_str},{completed_count},{failed_count}\n')
    print(f"Appended batch summary to {os.path.basename(log_file_path)}")

# --- Main Execution ---

def main():
    """Main entry point to manage the batch run log."""
    parser = argparse.ArgumentParser(description="A tool to update, rebuild, or finalize the batch run log.")
    subparsers = parser.add_subparsers(dest='mode', required=True, help="The operation to perform")

    # --- 'update' command ---
    parser_update = subparsers.add_parser('update', help="Append a single replication's data to the log.")
    parser_update.add_argument('report_file', type=str, help="Path to the single replication_report.txt file.")

    # --- 'rebuild' command ---
    parser_rebuild = subparsers.add_parser('rebuild', help="Recreate the entire log from all existing reports.")
    parser_rebuild.add_argument('output_dir', type=str, help="Path to the base output directory containing all run folders.")

    # --- 'finalize' command ---
    parser_finalize = subparsers.add_parser('finalize', help="Append the summary footer to an existing log.")
    parser_finalize.add_argument('output_dir', type=str, help="Path to the base output directory where the log is located.")
    
    args = parser.parse_args()

    # --- Define shared variables ---
    fieldnames = ["ReplicationNum", "Status", "StartTime", "EndTime", "Duration", "ParsingStatus", "MeanMRR", "MeanTop1Acc", "RunDirectory", "ErrorMessage"]
    
    if args.mode == 'update':
        if not os.path.exists(args.report_file):
            print(f"Error: Report file not found at '{args.report_file}'", file=sys.stderr)
            sys.exit(1)
        log_entry = parse_report_file(args.report_file)
        # Assume the log is in the parent of the parent of the report file (output/run_.../report.txt -> output)
        log_file_path = os.path.join(os.path.dirname(os.path.dirname(args.report_file)), "batch_run_log.csv")
        write_log_row(log_file_path, log_entry, fieldnames)
        print(f"Updated {os.path.basename(log_file_path)} for replication {log_entry['ReplicationNum']}")

    elif args.mode == 'rebuild':
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
            print(f"Removed old log file for clean rebuild: {os.path.basename(log_file_path)}")
        
        report_files = glob.glob(os.path.join(args.output_dir, "run_*", "replication_report_*.txt"))
        # Sort reports by creation time to ensure correct order in the log
        report_files.sort(key=os.path.getmtime)

        if not report_files:
            print("No report files found to rebuild the log.", file=sys.stderr)
            sys.exit(1)

        for report_path in report_files:
            log_entry = parse_report_file(report_path)
            write_log_row(log_file_path, log_entry, fieldnames)
        print(f"Successfully rebuilt {os.path.basename(log_file_path)} from {len(report_files)} reports.")

    elif args.mode == 'finalize':
        log_file_path = os.path.join(args.output_dir, "batch_run_log.csv")
        finalize_log(log_file_path)

if __name__ == "__main__":
    main()