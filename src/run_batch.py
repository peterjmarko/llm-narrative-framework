# Filename: src/run_batch.py

import sys
import os
import subprocess
import logging
import glob

# Add src to path to find config_loader
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

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
    # --- Load Configuration ---
    try:
        num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int)
        project_root = os.path.dirname(current_dir)
        base_output_dir = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
        final_output_dir = os.path.join(project_root, base_output_dir)
    except Exception as e:
        logging.error(f"Error reading required parameters from config.ini: {e}")
        sys.exit(1)

    if num_reps is None:
        logging.error("Could not find 'num_replications' in the [Study] section of config.ini. Aborting.")
        sys.exit(1)

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

    print(f"--- Starting Batch Experiment: {num_reps} Replications ---")
    
    # --- Main Replication Loop ---
    for i in range(1, num_reps + 1):
        print("\n" + "="*80)
        print(f"### RUNNING REPLICATION {i} of {num_reps} ###")
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