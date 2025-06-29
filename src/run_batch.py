# Filename: src/run_batch.py

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

def main():
    """
    Main entry point to run a full batch of experimental replications.
    This script reads the configuration and then calls orchestrate_experiment.py
    for each replication.
    """
    # --- MODIFICATION: Add command-line argument parsing ---
    parser = argparse.ArgumentParser(description="Main batch runner for experiments.")
    parser.add_argument("--start-rep", type=int, default=None, help="The replication number to start from (inclusive).")
    parser.add_argument("--end-rep", type=int, default=None, help="The replication number to end at (inclusive).")
    args = parser.parse_args()
    # --- END MODIFICATION ---

    # --- Load Configuration ---
    try:
        # Load the total number of replications from config as a default
        config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int)
        project_root = os.path.dirname(current_dir)
        base_output_dir = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
        final_output_dir = os.path.join(project_root, base_output_dir)
    except Exception as e:
        logging.error(f"Error reading required parameters from config.ini: {e}")
        sys.exit(1)

    # --- MODIFICATION: Determine the run range from args or config ---
    start_rep = args.start_rep if args.start_rep is not None else 1
    end_rep = args.end_rep if args.end_rep is not None else config_num_reps

    if start_rep > end_rep:
        logging.error(f"Error: Start replication ({start_rep}) cannot be greater than end replication ({end_rep}).")
        sys.exit(1)
    
    num_reps = end_rep # The highest replication number to consider.

    # --- Define Paths ---
    orchestrator_script = os.path.join(current_dir, "orchestrate_experiment.py")
    log_manager_script = os.path.join(current_dir, "log_manager.py") # The new unified log manager
    retry_script = os.path.join(current_dir, "retry_failed_sessions.py")
    compile_script = os.path.join(current_dir, "compile_results.py")

    # Clean up old batch log if it exists to ensure a fresh run
    old_log_path = os.path.join(final_output_dir, "batch_run_log.csv")
    if os.path.exists(old_log_path):
        try:
            os.remove(old_log_path)
            print(f"Removed old batch run log: {os.path.basename(old_log_path)}")
        except OSError as e:
            logging.error(f"Could not remove old log file at {old_log_path}: {e}")

    print(f"--- Starting Batch Experiment for range {start_rep}-{end_rep} ---")

    # --- MODIFICATION: Scan for already completed replications within the desired range ---
    completed_reps = get_completed_replications(final_output_dir)
    reps_to_run = [r for r in range(start_rep, end_rep + 1) if r not in completed_reps]

    if completed_reps:
        completed_in_range = {r for r in completed_reps if start_rep <= r <= end_rep}
        if completed_in_range:
            print(f"Found {len(completed_in_range)} completed replications in the specified range. They will be skipped.")
    
    if not reps_to_run:
        print("All replications in the specified range are already complete. Proceeding to post-processing.")
    else:
        print(f"Will execute {len(reps_to_run)} new replication(s).")

    # Record batch start time for the *new* work
    batch_start_time = time.time()
    newly_completed_count = 0
    
    # --- Main Replication Loop ---
    # Initialize color support in terminal (especially for Windows)
    os.system('') 

    # Loop through the full desired range, but skip if already complete
    for i in range(start_rep, end_rep + 1):
        if i not in reps_to_run:
            continue

        # --- MODIFICATION: Create a centered, colored header ---
        header_text = f" RUNNING REPLICATION {i} of {num_reps} "
        # Center the text within the 74 characters between the '###' guards
        centered_header = f"###{header_text.center(74, ' ')}###"
        
        print("\n" + "="*80)
        print(f"{C_CYAN}{centered_header}{C_RESET}")
        print("="*80)

        # Seeds are derived from the replication number for reproducibility
        base_seed = 1000 * i
        qgen_seed = base_seed + 500

        cmd = [
            sys.executable, orchestrator_script,
            "--replication_num", str(i),
            "--base_seed", str(base_seed),
            "--qgen_base_seed", str(qgen_seed),
            "--quiet"
        ]
        
        try:
            # Use subprocess.run and let it stream output directly to the console
            subprocess.run(cmd, check=True)

            # --- NEW: Update batch log after successful replication ---
            latest_report = find_latest_report(final_output_dir)
            if latest_report:
                # Call the log manager in 'update' mode
                subprocess.run([sys.executable, log_manager_script, 'update', latest_report], check=True)
            else:
                logging.warning(f"Could not find report file for replication {i} to update the batch log.")
            # --- END NEW ---

            # --- MODIFICATION START: Calculate and display timing info ---
            newly_completed_count += 1
            elapsed_seconds = time.time() - batch_start_time
            
            # Base calculations only on the work done in *this* session
            avg_seconds_per_rep = elapsed_seconds / newly_completed_count
            reps_remaining_in_this_batch = len(reps_to_run) - newly_completed_count
            estimated_remaining_seconds = avg_seconds_per_rep * reps_remaining_in_this_batch

            # Calculate the estimated finish time in the user's local timezone
            now = datetime.datetime.now()
            finish_time = now + datetime.timedelta(seconds=estimated_remaining_seconds)
            finish_time_str = finish_time.strftime('%H:%M:%S') # Format as 24-hour HH:MM:SS

            elapsed_str = format_seconds(elapsed_seconds)
            remaining_str = format_seconds(estimated_remaining_seconds)

            print(f"\n--- Replication {i} Finished ({newly_completed_count}/{len(reps_to_run)} in this session) ---")
            print(f"Time Elapsed: {elapsed_str} | Remaining: {remaining_str} | ETA: {finish_time_str}")
            # --- MODIFICATION END ---

        except subprocess.CalledProcessError:
            logging.error(f"!!! Replication {i} failed. See logs above. Continuing with next replication. !!!")
            # Even on failure, we try to log it if a report was generated
            latest_report = find_latest_report(final_output_dir)
            if latest_report:
                subprocess.run([sys.executable, log_manager_script, 'update', latest_report]) # Don't check=True here
            continue
        except KeyboardInterrupt:
            logging.warning("\nBatch run interrupted by user. Halting.")
            sys.exit(1)

    print("\n" + "="*80)
    print("### ALL REPLICATIONS COMPLETE. BEGINNING POST-PROCESSING. ###")
    print("="*80)

    # --- NEW: Finalize Batch Log ---
    print("\n--- Finalizing batch run log with summary... ---")
    try:
        # Call the log manager in 'finalize' mode
        subprocess.run([sys.executable, log_manager_script, 'finalize', final_output_dir], check=True)
    except Exception as e:
        logging.error(f"An error occurred while finalizing the batch log: {e}")
    # --- END NEW ---

    # --- Auto-Repair Phase ---
    print("\n--- Attempting to repair any failed sessions... ---")
    try:
        # We don't use check=True here because the script has its own exit codes we want to see.
        subprocess.run([sys.executable, retry_script, final_output_dir])
    except Exception as e:
        logging.error(f"An error occurred while running the retry script: {e}")

    # --- Final Compilation Phase (for statistical summary) ---
    print("\n--- Compiling final statistical summary... ---")
    try:
        subprocess.run([sys.executable, compile_script, final_output_dir], check=True)
    except Exception as e:
        logging.error(f"An error occurred while running the final compilation script: {e}")
    
    print("\n--- Batch Run Finished ---")


if __name__ == "__main__":
    main()