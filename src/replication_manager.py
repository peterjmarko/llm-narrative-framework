#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/replication_manager.py

"""
Manages the execution of a batch of replications for an experiment.

This script is the primary workhorse for running an experiment. It is typically
called by the main entry point script (e.g., `run_experiment.ps1`).

Key Responsibilities:
- Determines the range of replications to run (e.g., 1 to 30).
- Initializes or rebuilds the master log file (`batch_run_log.csv`) by calling
  the `log_manager.py` utility, ensuring a clean and robust state before any
  replications are run.
- Checks for already completed replications and skips them, allowing for the
  resumption of interrupted batch runs.
- Iterates through the required replications and calls the orchestrator script
  (`orchestrate_replication.py`) for each one.
- Controls the verbosity of the entire batch run via the `--quiet` flag.
- Monitors overall progress and displays session-aware timing estimates (Elapsed,
  Remaining, ETA).
- Uses colored and centered console output for clear visual feedback.
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

# Add src to path to find config_loader
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

# --- MODIFICATION: ANSI color codes for console output ---
C_CYAN = '\033[96m'
C_GREEN = '\033[92m'
C_RESET = '\033[0m'

def get_completed_replications(output_dir):
    """Scans the output directory to find which replications are already complete."""
    completed = set()
    search_pattern = os.path.join(output_dir, 'run_*')
    
    try:
        run_dirs = glob.glob(search_pattern)
    except Exception as e:
        logging.error(f"Failed to scan for existing run directories: {e}")
        return completed

    for dir_path in run_dirs:
        dir_name = os.path.basename(dir_path)
        # Extract replication number (e.g., from '..._rep-05_...')
        match = re.search(r'_rep-(\d+)_', dir_name)
        if match:
            # Check if a report file exists, indicating completion
            if glob.glob(os.path.join(dir_path, 'replication_report_*.txt')):
                rep_num = int(match.group(1))
                completed.add(rep_num)
    
    return completed

def format_seconds(seconds):
    """Formats a duration in seconds into an HH:MM:SS string."""
    if seconds < 0:
        return "00:00:00"
    # Create a timedelta object to handle formatting easily
    delta = datetime.timedelta(seconds=seconds)
    return str(delta).split('.')[0]  # Remove microseconds for cleaner output

def find_latest_report(base_dir):
    """Finds the most recently created replication report file."""
    try:
        # Use a wildcard to search inside all 'run_*' directories
        search_pattern = os.path.join(base_dir, "run_*", "replication_report_*.txt")
        report_files = glob.glob(search_pattern)
        if not report_files:
            return None
        # Return the file with the most recent modification time
        latest_report = max(report_files, key=os.path.getmtime)
        return latest_report
    except Exception as e:
        logging.error(f"Error finding latest report file: {e}")
        return None

def find_run_dirs_by_depth(base_dir, pattern, depth):
    """
    Finds directories matching a pattern up to a specified depth.
    - depth = -1: Fully recursive search.
    - depth = 0:  Search only in the immediate subdirectories of base_dir.
    - depth = n:  Search n levels deep.
    """
    if depth < -1:
        depth = -1
    
    if depth == -1:
        search_pattern = os.path.join(base_dir, '**', pattern)
        return sorted([p for p in glob.glob(search_pattern, recursive=True) if os.path.isdir(p)])

    all_paths = set()
    for d in range(depth + 1):
        wildcards = ['*'] * d
        path_parts = [base_dir] + wildcards + [pattern]
        current_pattern = os.path.join(*path_parts)
        all_paths.update(glob.glob(current_pattern))

    return sorted([p for p in all_paths if os.path.isdir(p)])

def main():
    """
    Main entry point to run a full batch of experimental replications.
    This script reads the configuration and then calls orchestrate_experiment.py
    for each replication.
    """
    # --- MODIFICATION: Add command-line argument parsing ---
    parser = argparse.ArgumentParser(description="Main batch runner for experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="The target directory for the operation. For new runs, this is the base output "
                             "directory. For reprocessing, this is the experiment folder to scan.")
    # Arguments for creating new replications
    parser.add_argument('--start-rep', type=int, default=None, help='The starting replication number (inclusive).')
    parser.add_argument('--end-rep', type=int, default=None, help='The ending replication number (inclusive).')
    # Argument for switching to reprocess mode
    parser.add_argument('--reprocess', action='store_true', help='Run in reprocessing mode on an existing experiment folder.')
    parser.add_argument('--depth', type=int, default=0, help="Recursion depth for finding run_* folders in reprocess mode.")
    
    parser.add_argument('--quiet', action='store_true', help='Suppress per-replication status updates.')

    args = parser.parse_args()
    # --- END MODIFICATION ---

    # --- Define Paths ---
    orchestrator_script = os.path.join(current_dir, "orchestrate_replication.py")
    log_manager_script = os.path.join(current_dir, "log_manager.py")
    retry_script = os.path.join(current_dir, "retry_failed_sessions.py")
    compile_script = os.path.join(current_dir, "compile_results.py")
    restore_script = os.path.join(current_dir, "restore_config.py") # Path to the restore utility
    
    final_output_dir = "" # Will be determined based on mode

    if args.reprocess:
        # --- BATCH REPROCESS MODE ---
        if not args.target_dir:
            logging.error("FATAL: You must specify a target_dir for --reprocess mode.")
            sys.exit(1)
        
        final_output_dir = os.path.abspath(args.target_dir)
        if not os.path.isdir(final_output_dir):
            logging.error(f"FATAL: Target directory for reprocessing does not exist: {final_output_dir}")
            sys.exit(1)

        print(f"--- Starting Batch Reprocess on: {final_output_dir} (Depth: {args.depth}) ---")
        
        dirs_to_reprocess = find_run_dirs_by_depth(final_output_dir, 'run_*', args.depth)

        if not dirs_to_reprocess:
            print("No 'run_*' directories found to reprocess. Exiting.")
            sys.exit(0)

        print(f"Found {len(dirs_to_reprocess)} replication directories to reprocess.")
        os.system('') # Initialize color support

        for i, run_dir in enumerate(dirs_to_reprocess):
            # --- NEW: Auto-restore config logic ---
            config_path = os.path.join(run_dir, 'config.ini.archived')
            if not os.path.exists(config_path):
                print(f"  -> Config file missing. Attempting to restore for '{os.path.basename(run_dir)}'...")
                try:
                    # Call the dedicated restore script as a subprocess
                    restore_cmd = [sys.executable, restore_script, run_dir]
                    # We don't capture output so the user sees the restore script's messages
                    subprocess.run(restore_cmd, check=True)
                except subprocess.CalledProcessError:
                    logging.error(f"  -> !!! Failed to restore config for {os.path.basename(run_dir)}. Skipping this directory. !!!")
                    continue # Move to the next directory
            
            # --- Original reprocessing logic continues ---
            header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(dirs_to_reprocess)}) "
            centered_header = f"###{header_text.center(74, ' ')}###"
            print("\n" + "="*80)
            print(f"{C_CYAN}{centered_header}{C_RESET}")
            print("="*80)

            cmd = [
                sys.executable, orchestrator_script,
                "--reprocess",
                "--run_output_dir", run_dir
            ]
            if args.quiet:
                cmd.append("--quiet")

            try:
                subprocess.run(cmd, check=True)
            except subprocess.CalledProcessError:
                logging.error(f"!!! Reprocessing failed for {os.path.basename(run_dir)}. See logs. Continuing... !!!")
                continue
            except KeyboardInterrupt:
                logging.warning("\nBatch reprocess interrupted by user. Halting.")
                sys.exit(1)
    
    else:
        # --- NEW REPLICATION MODE ---
        try:
            config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int)
            project_root = os.path.dirname(current_dir)
            base_output_dir_name = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
            final_output_dir = os.path.abspath(args.target_dir) if args.target_dir else os.path.join(project_root, base_output_dir_name)
        except Exception as e:
            logging.error(f"Error reading required parameters from config.ini: {e}")
            sys.exit(1)

        start_rep = args.start_rep if args.start_rep is not None else 1
        end_rep = args.end_rep if args.end_rep is not None else config_num_reps

        if start_rep > end_rep:
            logging.error(f"Error: Start replication ({start_rep}) cannot be greater than end replication ({end_rep}).")
            sys.exit(1)
        
        num_reps = end_rep

        # --- Robust Log Initialization ---
        completed_reps = get_completed_replications(final_output_dir)
        is_fresh_start = (start_rep == 1 and not completed_reps)

        if is_fresh_start:
            # For a true fresh start, initialize a new, empty log.
            print("\n--- Initializing a new batch experiment... ---")
            log_command = 'start'
        else:
            # For any other case (resuming, recovering), always rebuild the log from
            # the existing reports to ensure a clean, appendable state.
            print("\n--- Resuming experiment. Rebuilding log from reports to ensure integrity... ---")
            log_command = 'rebuild'

        try:
            cmd = [sys.executable, log_manager_script, log_command, final_output_dir]
            # Capture output to prevent log_manager's messages from cluttering the main console
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8')
            # Print the output from the log manager so the user knows what happened
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip(), file=sys.stderr)

        except subprocess.CalledProcessError as e:
            logging.error(f"FATAL: Could not prepare the batch run log. Halting. Error: {e}")
            logging.error(f"--- Log Manager STDOUT ---\n{e.stdout}")
            logging.error(f"--- Log Manager STDERR ---\n{e.stderr}")
            sys.exit(1)
        except FileNotFoundError as e:
            logging.error(f"FATAL: Could not find a script. Halting. Error: {e}")
            sys.exit(1)

        print(f"\n--- Starting Batch Experiment for range {start_rep}-{end_rep} ---")
        reps_to_run = [r for r in range(start_rep, end_rep + 1) if r not in completed_reps]

        if completed_reps:
            completed_in_range = {r for r in completed_reps if start_rep <= r <= end_rep}
            if completed_in_range:
                print(f"Found {len(completed_in_range)} completed replications in the specified range. They will be skipped.")
        
        if not reps_to_run:
            print("All replications in the specified range are already complete. Proceeding to post-processing.")
        else:
            print(f"Will execute {len(reps_to_run)} new replication(s).")

        batch_start_time = time.time()
        newly_completed_count = 0
        
        os.system('') 

        for i in range(start_rep, end_rep + 1):
            if i not in reps_to_run:
                continue

            header_text = f" RUNNING REPLICATION {i} of {num_reps} "
            centered_header = f"###{header_text.center(74, ' ')}###"
            
            print("\n" + "="*80)
            print(f"{C_CYAN}{centered_header}{C_RESET}")
            print("="*80)

            base_seed = 1000 * i
            qgen_seed = base_seed + 500

            cmd = [
                sys.executable, orchestrator_script,
                "--replication_num", str(i),
                "--base_seed", str(base_seed),
                "--qgen_base_seed", str(qgen_seed),
            ]
            if args.quiet:
                cmd.append("--quiet")
            
            try:
                subprocess.run(cmd, check=True)

                latest_report = find_latest_report(final_output_dir)
                if latest_report:
                    subprocess.run([sys.executable, log_manager_script, 'update', latest_report], check=True)
                else:
                    logging.warning(f"Could not find report file for replication {i} to update the batch log.")

                newly_completed_count += 1
                elapsed_seconds = time.time() - batch_start_time
                
                avg_seconds_per_rep = elapsed_seconds / newly_completed_count
                reps_remaining_in_this_batch = len(reps_to_run) - newly_completed_count
                estimated_remaining_seconds = avg_seconds_per_rep * reps_remaining_in_this_batch

                now = datetime.datetime.now()
                finish_time = now + datetime.timedelta(seconds=estimated_remaining_seconds)
                finish_time_str = finish_time.strftime('%H:%M:%S')

                elapsed_str = format_seconds(elapsed_seconds)
                remaining_str = format_seconds(estimated_remaining_seconds)

                print(f"\n--- Replication {i} Finished ({newly_completed_count}/{len(reps_to_run)} in this session) ---")
                print(f"{C_GREEN}Time Elapsed: {elapsed_str} | Remaining: {remaining_str} | ETA: {finish_time_str}{C_RESET}")

            except subprocess.CalledProcessError:
                logging.error(f"!!! Replication {i} failed. See logs above. Continuing with next replication. !!!")
                latest_report = find_latest_report(final_output_dir)
                if latest_report:
                    subprocess.run([sys.executable, log_manager_script, 'update', latest_report])
                continue
            except KeyboardInterrupt:
                logging.warning("\nBatch run interrupted by user. Halting.")
                sys.exit(1)

    print("\n" + "="*80)
    print("### ALL TASKS COMPLETE. BEGINNING POST-PROCESSING. ###")
    print("="*80)

    print("\n--- Finalizing batch run log with summary... ---")
    try:
        subprocess.run([sys.executable, log_manager_script, 'finalize', final_output_dir], check=True)
    except Exception as e:
        logging.error(f"An error occurred while finalizing the batch log: {e}")

    print("\n--- Attempting to repair any failed sessions... ---")
    try:
        subprocess.run([sys.executable, retry_script, final_output_dir])
    except Exception as e:
        logging.error(f"An error occurred while running the retry script: {e}")

    print("\n--- Compiling final statistical summary... ---")
    try:
        subprocess.run([sys.executable, compile_script, final_output_dir], check=True)
    except Exception as e:
        logging.error(f"An error occurred while running the final compilation script: {e}")
    
    print("\n--- Batch Run Finished ---")


if __name__ == "__main__":
    main()

# === End of src/replication_manager.py ===