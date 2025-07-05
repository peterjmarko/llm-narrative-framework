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
    # MODIFIED: Changed --quiet to --verbose and inverted the logic. Default is now quiet.
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the report.')
    args = parser.parse_args()

    orchestrator_script = os.path.join(current_dir, "orchestrate_replication.py")
    log_manager_script = os.path.join(current_dir, "log_manager.py")
    compile_script = os.path.join(current_dir, "compile_results.py")
    # Correctly point to the new per-replication bias analysis script
    bias_analysis_script = os.path.join(current_dir, "run_bias_analysis.py")
    
    if args.target_dir:
        final_output_dir = os.path.abspath(args.target_dir)
    else:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        model_name = get_config_value(APP_CONFIG, 'LLM', 'model_identifier', value_type=str, fallback='llm')
        safe_model_name = re.sub(r'[<>:"/\\|?*]', '-', model_name)
        project_root = os.path.dirname(current_dir)
        base_output_path = os.path.join(project_root, 'output')
        study_dir_name = f"study_{timestamp}_{safe_model_name}"
        final_output_dir = os.path.join(base_output_path, study_dir_name)
        print(f"{C_CYAN}No target directory specified. Using default: {final_output_dir}{C_RESET}")

    failed_reps = [] # Initialize for all modes

    if args.reprocess:
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
        # failed_reps = [] # <-- This line is now removed from here

        for i, run_dir in enumerate(dirs_to_reprocess):
            header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(dirs_to_reprocess)}) "
            print("\n" + "="*80)
            print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
            print("="*80)
            cmd = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", run_dir]
            if not args.verbose: cmd.append("--quiet")
            if args.notes:
                cmd.extend(["--notes", args.notes])
            try:
                subprocess.run(cmd, check=True)

                # --- ADDED: Run the new per-replication bias analysis stage ---
                cmd_bias = [sys.executable, bias_analysis_script, run_dir]
                subprocess.run(cmd_bias, check=True, text=True, capture_output=False)
                # --- END OF ADDED BLOCK ---

            except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
                logging.error(f"!!! Reprocessing failed or was interrupted for {os.path.basename(run_dir)}. Continuing... !!!")
                failed_reps.append(os.path.basename(run_dir)) # Add failed run to the list
                if isinstance(e, KeyboardInterrupt): sys.exit(1)
        
        # --- ADDED: Log rebuilding for reprocess mode ---
        print("\n" + "="*80)
        print("### REPROCESSING PHASE COMPLETE. REBUILDING BATCH LOG. ###")
        print("="*80)
        try:
            subprocess.run([sys.executable, log_manager_script, "rebuild", final_output_dir], check=True)
            print("Batch run log successfully rebuilt.")
        except Exception as e:
            logging.error(f"An error occurred while rebuilding the batch log after reprocessing: {e}")

    else:
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
            interrupted = False

            for i, rep_num in enumerate(reps_to_run):
                header_text = f" RUNNING REPLICATION {rep_num} of {end_rep} "
                print("\n" + "="*80)
                print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
                print("="*80)
                
                cmd = [sys.executable, orchestrator_script, 
                    "--replication_num", str(rep_num),
                    "--base_output_dir", final_output_dir]
                if args.notes:
                    cmd.extend(["--notes", args.notes])
                # MODIFIED: Pass --quiet to the orchestrator unless --verbose is specified.
                if not args.verbose: cmd.append("--quiet")
                
                try:
                    subprocess.run(cmd, check=True)

                    # --- ADDED: Find the run directory and run bias analysis for consistency ---
                    search_pattern = os.path.join(final_output_dir, f'run_*_rep-{rep_num:03d}_*')
                    found_dirs = [d for d in glob.glob(search_pattern) if os.path.isdir(d)]
                    
                    if len(found_dirs) == 1:
                        run_dir = found_dirs[0]
                        cmd_bias = [sys.executable, bias_analysis_script, run_dir]
                        subprocess.run(cmd_bias, check=True, text=True, capture_output=False)
                    else:
                        logging.warning(f"Could not find unique run directory for rep {rep_num} to run bias analysis. Found: {len(found_dirs)}")
                    # --- END OF ADDED BLOCK ---

                    newly_completed_count += 1
                    elapsed = time.time() - batch_start_time
                    avg_time = elapsed / newly_completed_count
                    remaining_reps = len(reps_to_run) - (i + 1)
                    eta = datetime.datetime.now() + datetime.timedelta(seconds=remaining_reps * avg_time)
                    print(f"\n--- Replication {rep_num} Finished ({newly_completed_count}/{len(reps_to_run)}) ---")
                    print(f"{C_GREEN}Time Elapsed: {format_seconds(elapsed)} | Remaining: {format_seconds(remaining_reps * avg_time)} | ETA: {eta.strftime('%H:%M:%S')}{C_RESET}")

                except subprocess.CalledProcessError:
                    logging.error(f"!!! Replication {rep_num} failed. Check its report for details. Continuing... !!!")
                    failed_reps.append(rep_num) # Add the failed replication number to our list
                except KeyboardInterrupt:
                    logging.warning(f"\n!!! Batch run interrupted by user during replication {rep_num}. Halting... !!!")
                    interrupted = True
                
                if interrupted:
                    break
            
            # --- THIS IS THE NEW LOGIC BLOCK ---
            # It runs once after the entire replication loop is finished or interrupted.
            print("\n" + "="*80)
            print("### REPLICATION PHASE COMPLETE. REBUILDING BATCH LOG. ###")
            print("="*80)
            try:
                # Rebuild the entire log from the completed reports in one go.
                subprocess.run([sys.executable, log_manager_script, "rebuild", final_output_dir], check=True)
                print("Batch run log successfully rebuilt.")
            except Exception as e:
                logging.error(f"An error occurred while rebuilding the batch run log: {e}")

    # --- Post-Processing Stage ---
    print("\n" + "="*80)
    print("### ALL TASKS COMPLETE. BEGINNING POST-PROCESSING. ###")
    print("="*80)
    
    # Call compile_results.py
    print("\n--- Compiling final statistical summary... ---")
    try:
        subprocess.run([sys.executable, compile_script, final_output_dir, "--mode", "hierarchical"], check=True, capture_output=True, text=True)
    except Exception as e:
        logging.error(f"An error occurred while running the final compilation script: {e}")
    
    # Call the existing 'finalize' command in log_manager.py to append the summary.
    print("\n--- Finalizing batch log with summary... ---")
    try:
        subprocess.run([sys.executable, log_manager_script, "finalize", final_output_dir], check=True, capture_output=True, text=True)
    except Exception as e:
        logging.error(f"An error occurred while finalizing the batch log: {e}")

    # NEW: Add a summary of any failures at the very end.
    if failed_reps:
        print("\n" + "="*80)
        print(f"### BATCH RUN COMPLETE WITH {len(failed_reps)} FAILURE(S) ###")
        print("The following replications failed and should be investigated:")
        for rep in failed_reps:
            print(f"  - {rep}")
        print("Check the 'replication_report.txt' inside each failed directory for details.")
        print("="*80)
    else:
        print("\n--- Batch Run Finished Successfully ---")

if __name__ == "__main__":
    main()

# === End of src/replication_manager.py ===