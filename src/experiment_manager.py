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
# Filename: src/experiment_manager.py

"""
Main Batch Controller for Experiments.

This script is the high-level controller for running or reprocessing an entire
experimental batch (e.g., all 30 replications). It serves as the primary engine
called by the user-facing PowerShell wrappers. Its main job is to call the
single-run orchestrator (`orchestrate_replication.py`) in a loop.

Key Features:
-   **Batch Execution**: For new experiments, it runs a specified range of
    replications, intelligently skipping any that are already complete to allow
    for easy resumption of interrupted batches.
-   **Batch Reprocessing**: In `--reprocess` mode, it recursively scans a
    target directory for all existing replication folders and re-runs the
    analysis stages on each one.
-   **Integrated Bias Analysis**: After each successful replication (new or
    reprocessed), it automatically calls `run_bias_analysis.py` to ensure
    consistent analysis across the experiment.
-   **Robust Log Management**: At the end of the batch run, it calls
    `replication_log_manager.py rebuild` to create a clean, comprehensive
    `batch_run_log.csv` that accurately reflects the state of all completed runs.
-   **Automated Finalization**: After all replications are complete, it
    triggers the final post-processing steps:
    1.  `compile_study_results.py`: To aggregate all data into a master CSV.
    2.  `replication_log_manager.py finalize`: To append a final summary to the
        batch log.

Usage (to run replications 1-30 in a new experiment directory):
    python src/experiment_manager.py --end-rep 30

Usage (to reprocess all runs in an existing experiment directory):
    python src/experiment_manager.py /path/to/experiment_dir --reprocess
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
import configparser

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
    log_manager_script = os.path.join(current_dir, "replication_log_manager.py")
    compile_script = os.path.join(current_dir, "compile_study_results.py")
    # Correctly point to the new per-replication bias analysis script
    bias_analysis_script = os.path.join(current_dir, "run_bias_analysis.py")
    
    if args.target_dir:
        final_output_dir = os.path.abspath(args.target_dir)
    else:
        # Create a default directory by reading the structure from config.ini
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        project_root = os.path.abspath(os.path.join(current_dir, '..'))
        
        base_output = get_config_value(APP_CONFIG, 'General', 'base_output_dir', value_type=str, fallback='output')
        new_exp_subdir = get_config_value(APP_CONFIG, 'General', 'new_experiments_subdir', value_type=str, fallback='new_experiments')
        exp_prefix = get_config_value(APP_CONFIG, 'General', 'experiment_dir_prefix', value_type=str, fallback='experiment_')

        base_path = os.path.join(project_root, base_output, new_exp_subdir)
        final_output_dir = os.path.join(base_path, f"{exp_prefix}{timestamp}")
        
        print(f"{C_CYAN}No target directory specified. Using default from config: {final_output_dir}{C_RESET}")

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

                # --- FIX: Load the run-specific archived config to get the correct k value ---
                config_path = os.path.join(run_dir, 'config.ini.archived')
                k_value = None
                if os.path.exists(config_path):
                    config = configparser.ConfigParser()
                    config.read(config_path)
                    # Use robust key lookup to find the group size (k)
                    if config.has_option('Study', 'group_size'):
                        k_value = config.getint('Study', 'group_size')
                    elif config.has_option('Study', 'k_per_query'): # Fallback for older key names
                        k_value = config.getint('Study', 'k_per_query')

                if k_value:
                    # Run the bias analysis stage with the correct k_value
                    cmd_bias = [sys.executable, bias_analysis_script, run_dir, "--k_value", str(k_value)]
                    if args.verbose: cmd_bias.append("--verbose")
                    subprocess.run(cmd_bias, check=True, text=True, capture_output=False)
                else:
                    logging.warning(f"Could not find k_value in {config_path}. Skipping bias analysis for {os.path.basename(run_dir)}.")
                # --- END OF FIX ---

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
                        # Get k from the live config for the new run
                        k_value = get_config_value(APP_CONFIG, 'Study', 'group_size', 
                                                   value_type=int, 
                                                   fallback_key='k_per_query', 
                                                   fallback=10)
                        cmd_bias = [sys.executable, bias_analysis_script, run_dir, "--k_value", str(k_value)]
                        if args.verbose: cmd_bias.append("--verbose")
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
    
    # Call compile_study_results.py
    print("\n--- Compiling final statistical summary... ---")
    try:
        subprocess.run([sys.executable, compile_script, final_output_dir, "--mode", "hierarchical"], check=True, capture_output=True, text=True)
    except Exception as e:
        logging.error(f"An error occurred while running the final compilation script: {e}")
    
    # Call the existing 'finalize' command in replication_log_manager.py to append the summary.
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

# === End of src/experiment_manager.py ===
