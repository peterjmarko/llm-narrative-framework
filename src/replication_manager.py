#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/replication_manager.py

"""
Main Batch Runner for Managing Multiple Replications.

This script is the primary user-facing tool for managing large-scale experiments.
It automates the process of running many replications or reprocessing entire
studies by calling the single-run orchestrator (`orchestrate_replication.py`)
in a loop.

Key Features:
-   **Batch Execution:** Runs a specified range of new replications, automatically
    skipping any that are already complete. Provides progress and ETA.
-   **Batch Reprocessing:** Scans a directory for existing run folders and
    re-runs the analysis stages (3 and 4) on all of them.
-   **Post-Processing:** After all tasks are complete, it automatically calls the
    `compile_results.py` script to generate the final statistical summary for
    the entire study.

Usage (to run replications 1 through 30):
    python src/replication_manager.py /path/to/study_output_dir --end-rep 30

Usage (to reprocess all runs in a directory):
    python src/replication_manager.py /path/to/study_output_dir --reprocess
"""

import sys
import os
import subprocess
import logging
import glob
import time
import datetime
import argparse
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_RESET = '\033[0m'

def get_completed_replications(output_dir):
    completed = set()
    search_pattern = os.path.join(output_dir, '**', 'run_*')
    run_dirs = glob.glob(search_pattern, recursive=True)

    for dir_path in run_dirs:
        if not os.path.isdir(dir_path): continue
        dir_name = os.path.basename(dir_path)
        match = re.search(r'_rep-(\d+)_', dir_name)
        if match:
            if glob.glob(os.path.join(dir_path, 'replication_report_*.txt')):
                completed.add(int(match.group(1)))
    return completed

def format_seconds(seconds):
    if seconds < 0: return "00:00:00"
    return str(datetime.timedelta(seconds=int(seconds)))

def find_latest_report(run_dir):
    report_files = glob.glob(os.path.join(run_dir, "replication_report_*.txt"))
    return max(report_files, key=os.path.getmtime) if report_files else None

def find_run_dirs_by_depth(base_dir, depth):
    if depth < -1: depth = -1
    pattern = 'run_*'
    if depth == -1:
        search_pattern = os.path.join(base_dir, '**', pattern)
        return sorted([p for p in glob.glob(search_pattern, recursive=True) if os.path.isdir(p)])
    
    all_paths = set()
    for d in range(depth + 1):
        wildcards = ['*'] * d
        path_parts = [base_dir] + wildcards
        current_pattern = os.path.join(*path_parts)
        run_dirs_at_level = glob.glob(os.path.join(current_pattern, pattern))
        all_paths.update(run_dirs_at_level)
        
    return sorted([p for p in all_paths if os.path.isdir(p)])

def main():
    parser = argparse.ArgumentParser(description="Main batch runner for experiments.")
    parser.add_argument('target_dir', nargs='?', default=None, 
                    help="Optional. The target directory for the operation. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1)
    parser.add_argument('--end-rep', type=int, default=None)
    parser.add_argument('--reprocess', action='store_true', help='Run in reprocessing mode.')
    parser.add_argument('--depth', type=int, default=0, help="Recursion depth for finding run folders.")
    parser.add_argument('--quiet', action='store_true', help='Suppress per-replication status updates.')
    args = parser.parse_args()

    orchestrator_script = os.path.join(current_dir, "orchestrate_replication.py")
    log_manager_script = os.path.join(current_dir, "log_manager.py")
    compile_script = os.path.join(current_dir, "compile_results.py")
    if args.target_dir:
        final_output_dir = os.path.abspath(args.target_dir)
    else:
        # Create a default, unique directory name
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Use the get_config_value function with the correct 'fallback' keyword
        model_name = get_config_value(APP_CONFIG, 'LLM', 'model_identifier', value_type=str, fallback='llm')
        
        safe_model_name = re.sub(r'[<>:"/\\|?*]', '-', model_name) # Sanitize for path
        
        # Assume project root is two levels up from this script (src/ -> project_root)
        project_root = os.path.dirname(current_dir)
        base_output_path = os.path.join(project_root, 'output')
        
        study_dir_name = f"study_{timestamp}_{safe_model_name}"
        final_output_dir = os.path.join(base_output_path, study_dir_name)
        print(f"{C_CYAN}No target directory specified. Using default: {final_output_dir}{C_RESET}")

    if args.reprocess:
    # Reprocessing logic requires a target_dir
        if not args.target_dir:
            print("ERROR: Reprocessing mode requires a target directory to be specified.", file=sys.stderr)
            sys.exit(1)
        print(f"--- Starting Batch Reprocess on: {final_output_dir} (Depth: {args.depth}) ---")
        dirs_to_reprocess = find_run_dirs_by_depth(final_output_dir, args.depth)
        if not dirs_to_reprocess:
            print("No 'run_*' directories found. Exiting.")
            return
        print(f"Found {len(dirs_to_reprocess)} replication directories to reprocess.")
        os.system('')

        for i, run_dir in enumerate(dirs_to_reprocess):
            header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(dirs_to_reprocess)}) "
            print("\n" + "="*80)
            print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
            print("="*80)
            cmd = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", run_dir]
            if args.quiet: cmd.append("--quiet")
            try:
                subprocess.run(cmd, check=True)
            except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
                logging.error(f"!!! Reprocessing failed or was interrupted for {os.path.basename(run_dir)}. Continuing... !!!")
                if isinstance(e, KeyboardInterrupt): sys.exit(1)
    else:
    # Ensure the final output directory exists before any operations
        if not os.path.exists(final_output_dir):
            os.makedirs(final_output_dir)
            print(f"Created target directory: {final_output_dir}")

        config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int)
        end_rep = args.end_rep if args.end_rep is not None else config_num_reps
        completed_reps = get_completed_replications(final_output_dir)
        
        log_command = 'rebuild' if completed_reps else 'start'
        print(f"\n--- Preparing log file with command: '{log_command}' ---")
        subprocess.run([sys.executable, log_manager_script, log_command, final_output_dir], check=True)

        reps_to_run = [r for r in range(args.start_rep, end_rep + 1) if r not in completed_reps]
        if not reps_to_run:
            print("All replications in the specified range are already complete.")
        else:
            print(f"Will execute {len(reps_to_run)} new replication(s).")
            batch_start_time = time.time()
            newly_completed_count = 0
            os.system('')

            for i, rep_num in enumerate(reps_to_run):
                header_text = f" RUNNING REPLICATION {rep_num} of {end_rep} "
                print("\n" + "="*80)
                print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
                print("="*80)
                cmd = [sys.executable, orchestrator_script, 
                    "--replication_num", str(rep_num),
                    "--base_output_dir", final_output_dir]
                if args.quiet: cmd.append("--quiet")
                try:
                    subprocess.run(cmd, check=True)
                    newly_completed_count += 1
                    elapsed = time.time() - batch_start_time
                    avg_time = elapsed / newly_completed_count
                    remaining_reps = len(reps_to_run) - newly_completed_count
                    eta = datetime.datetime.now() + datetime.timedelta(seconds=remaining_reps * avg_time)
                    print(f"\n--- Replication {rep_num} Finished ({newly_completed_count}/{len(reps_to_run)}) ---")
                    print(f"{C_GREEN}Time Elapsed: {format_seconds(elapsed)} | Remaining: {format_seconds(remaining_reps * avg_time)} | ETA: {eta.strftime('%H:%M:%S')}{C_RESET}")
                except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
                    logging.error(f"!!! Replication {rep_num} failed or was interrupted. Continuing... !!!")
                    if isinstance(e, KeyboardInterrupt): sys.exit(1)

    print("\n" + "="*80)
    print("### ALL TASKS COMPLETE. BEGINNING POST-PROCESSING. ###")
    print("="*80)
    print("\n--- Compiling final statistical summary... ---")
    try:
        subprocess.run([sys.executable, compile_script, final_output_dir, "--mode", "hierarchical"], check=True)
    except Exception as e:
        logging.error(f"An error occurred while running the final compilation script: {e}")
    
    print("\n--- Batch Run Finished ---")

if __name__ == "__main__":
    main()

# === End of src/replication_manager.py ===