# Filename: src/run_batch.py

import sys
import os
import subprocess
import logging

# Add src to path to find config_loader
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)

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
    retry_script = os.path.join(current_dir, "retry_failed_sessions.py")
    compile_script = os.path.join(current_dir, "compile_results.py")

    logging.info(f"--- Starting Batch Experiment: {num_reps} Replications ---")
    
    # --- Main Replication Loop ---
    for i in range(1, num_reps + 1):
        logging.info("\n" + "="*80)
        logging.info(f"### RUNNING REPLICATION {i} of {num_reps} ###")
        logging.info("="*80)

        # Seeds are derived from the replication number for reproducibility
        base_seed = 1000 * i
        qgen_seed = base_seed + 500

        cmd = [
            sys.executable, orchestrator_script,
            "--replication_num", str(i),
            "--base_seed", str(base_seed),
            "--qgen_base_seed", str(qgen_seed)
        ]
        
        try:
            # Use subprocess.run and let it stream output directly to the console
            subprocess.run(cmd, check=True)
        except subprocess.CalledProcessError:
            logging.error(f"!!! Replication {i} failed. See logs above. Continuing with next replication. !!!")
            continue
        except KeyboardInterrupt:
            logging.warning("\nBatch run interrupted by user. Halting.")
            sys.exit(1)

    logging.info("\n" + "="*80)
    logging.info("### ALL REPLICATIONS COMPLETE. BEGINNING AUTO-REPAIR AND COMPILATION. ###")
    logging.info("="*80)

    # --- Auto-Repair Phase ---
    logging.info("\n--- Attempting to repair any failed sessions... ---")
    try:
        # We don't use check=True here because the script has its own exit codes we want to see.
        subprocess.run([sys.executable, retry_script, final_output_dir])
    except Exception as e:
        logging.error(f"An error occurred while running the retry script: {e}")

    # --- Final Compilation Phase ---
    logging.info("\n--- Compiling final batch results... ---")
    try:
        subprocess.run([sys.executable, compile_script, final_output_dir], check=True)
    except Exception as e:
        logging.error(f"An error occurred while running the final compilation script: {e}")
    
    logging.info("\n--- Batch Run Finished ---")


if __name__ == "__main__":
    main()