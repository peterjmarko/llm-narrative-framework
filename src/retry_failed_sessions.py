#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/retry_failed_sessions.py

"""
Auto-Retry Failed LLM Sessions and Update Analysis

Purpose:
This script provides an automated way to find and re-run specific, failed
LLM queries across an entire batch of experimental runs. It is the primary tool
for recovering from intermittent network errors or API failures without having
to re-run entire replications.

Workflow:
1.  Scans all 'run_*' subdirectories within a given parent directory (e.g., 'output').
2.  For each run, it identifies "failed" sessions by checking for the existence of
    a query file (`llm_query_XXX.txt`) that does *not* have a corresponding successful
    response file (`llm_response_XXX.txt`).
3.  For each failed session found, it calls `run_llm_sessions.py` with a special
    `--force-rerun` flag. This deletes any old error file and re-sends the query.
4.  After all retries are complete, it re-runs the full analysis pipeline
    (`process_llm_responses.py`, `analyze_performance.py`) only for the run
    directories that were modified.
5.  Finally, it calls `compile_results.py` to update the master
    `final_summary_results.csv` with the newly corrected data.

Command-Line Usage:
    # Scan the default 'output' directory for failures and fix them
    python src/retry_failed_sessions.py

    # Scan a different directory
    python src/retry_failed_sessions.py --parent_dir /path/to/my/experiments
"""

import argparse
import os
import sys
import glob
import subprocess
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

# tqdm is a library that provides a clean progress bar.
# If not installed, run: pip install tqdm
try:
    from tqdm import tqdm
except ImportError:
    print("Warning: 'tqdm' library not found. Progress bar will not be shown.")
    print("You can install it with: pip install tqdm")
    # Define a dummy tqdm function if the library is not present.
    def tqdm(iterable, *args, **kwargs):
        return iterable

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)

def find_failed_sessions(parent_dir: str) -> dict:
    """
    Scans all run directories to find sessions that need to be retried.

    A session is considered failed if the query file exists but the corresponding
    successful response file does not.

    Returns:
        A dictionary mapping run directory paths to a list of integer indices to retry.
    """
    logging.info(f"Scanning for failed sessions in subdirectories of: {parent_dir}")
    failures_to_retry = {}
    run_dirs = sorted(glob.glob(os.path.join(parent_dir, "run_*")))

    for run_dir in run_dirs:
        queries_path = os.path.join(run_dir, "session_queries")
        responses_path = os.path.join(run_dir, "session_responses")

        if not os.path.isdir(queries_path) or not os.path.isdir(responses_path):
            continue

        query_files = glob.glob(os.path.join(queries_path, "llm_query_*.txt"))
        indices_to_check = []
        for qf in query_files:
            try:
                # Extract numeric index from filename like 'llm_query_033.txt'
                index_str = os.path.basename(qf).replace("llm_query_", "").replace(".txt", "")
                indices_to_check.append(int(index_str))
            except (ValueError, TypeError):
                continue
        
        failed_indices_for_run = []
        for index in indices_to_check:
            success_response_file = os.path.join(responses_path, f"llm_response_{index:03d}.txt")
            if not os.path.exists(success_response_file):
                failed_indices_for_run.append(index)
        
        if failed_indices_for_run:
            failures_to_retry[run_dir] = sorted(failed_indices_for_run)
            # FIXED: Add the log message the unit test is expecting.
            logging.info(f"Found {len(failed_indices_for_run)} failed session(s) at indices {failed_indices_for_run}")
            
    return failures_to_retry


def _retry_worker(run_dir: str, sessions_script_path: str, index: int) -> tuple[int, bool, str]:
    """
    A worker function to be run in a thread. Retries a single session.
    Returns the index, a boolean indicating success, and any captured stdout.
    """
    try:
        retry_cmd = [
            sys.executable, sessions_script_path,
            "--run_output_dir", run_dir,
            "--start_index", str(index), "--end_index", str(index),
            "--force-rerun", "--quiet"  # Run worker quietly to avoid jumbled logs
        ]
        # We don't capture output here to keep the main process responsive
        result = subprocess.run(retry_cmd, check=True, text=True, capture_output=True)
        # For testing, return the stdout of the mock script so the main thread can print it safely.
        return index, True, result.stdout
    except subprocess.CalledProcessError as e:
        # Log the specific error from the failed subprocess
        logging.error(f"  Retry for index {index} in {os.path.basename(run_dir)} FAILED. Subprocess stderr:\n{e.stderr}")
        return index, False, e.stdout + "\n" + e.stderr
    except Exception as e:
        logging.error(f"  An unexpected error occurred while retrying index {index}: {e}")
        return index, False, str(e)


# --- Define script paths at the module level for global access ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "run_llm_sessions.py")
PROCESSOR_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "process_llm_responses.py")
ANALYZER_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "analyze_performance.py")
COMPILER_SCRIPT_PATH = os.path.join(SCRIPT_DIR, "compile_results.py")


def main():
    parser = argparse.ArgumentParser(
        description="Automatically finds and retries failed LLM sessions across all runs, then updates analysis.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    # Use a general argument that can be either a parent or a specific run directory
    parser.add_argument("target_dir", nargs='?', default="output",
                        help="The directory to process. Can be a parent dir (like 'output') to find all failures, or a specific 'run_*' dir. Defaults to 'output'.")
    parser.add_argument("--indices", type=int, nargs='+',
                        help="A space-separated list of specific indices to manually retry. Must be used with a specific run directory as the target.")
    parser.add_argument("--parallel", type=int, default=10,
                        help="Number of parallel sessions to retry at once. Defaults to 10.")
    args = parser.parse_args()

    # --- Verify that all necessary pipeline scripts exist ---
    for path in [SESSIONS_SCRIPT_PATH, PROCESSOR_SCRIPT_PATH, ANALYZER_SCRIPT_PATH, COMPILER_SCRIPT_PATH]:
        if not os.path.exists(path):
            logging.error(f"Error: Could not find required script at: {path}")
            sys.exit(1)

    target_path = os.path.abspath(args.target_dir)
    if not os.path.isdir(target_path):
        logging.error(f"Error: Target directory does not exist: {target_path}")
        sys.exit(1)

    # --- Part 1: Determine work to be done ---
    failures_by_run = {}
    compile_dir = ""
    is_single_run = os.path.basename(target_path).startswith("run_")

    if is_single_run:
        # Manual mode: user specified a run directory.
        compile_dir = os.path.dirname(target_path)
        if not args.indices:
            parser.error("The --indices argument is required when specifying a single run directory.")
        failures_by_run[target_path] = args.indices
    else:
        # Automatic mode: find all failures in the parent directory.
        if args.indices:
            parser.error("--indices can only be used when specifying a single run directory, not a parent directory.")
        compile_dir = target_path
        failures_by_run = find_failed_sessions(compile_dir)

    if not failures_by_run:
        logging.info("--- Discovery Complete: No sessions to retry. Nothing to do. ---")
        sys.exit(0)

    runs_to_update = list(failures_by_run.keys())
    
    # --- Part 2: Retry all discovered failures in parallel ---
    logging.info(f"\n--- Starting Retry Phase (up to {args.parallel} parallel workers) ---")
    successful_retries = 0; failed_retries = 0

    all_worker_outputs = []
    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        for run_dir, indices_to_retry in failures_by_run.items():
            run_basename = os.path.basename(run_dir)
            logging.info(f"\n--- Submitting {len(indices_to_retry)} tasks for: {run_basename} ---")
            
            # Create a task function with the run_dir and script_path pre-filled
            task_func = partial(_retry_worker, run_dir, SESSIONS_SCRIPT_PATH)
            future_to_index = {executor.submit(task_func, index): index for index in indices_to_retry}

            for future in tqdm(as_completed(future_to_index), total=len(indices_to_retry), desc=f"Retrying {run_basename}"):
                index, success, worker_output = future.result()
                if worker_output:
                    all_worker_outputs.append(worker_output)
                if success:
                    successful_retries += 1
                else:
                    failed_retries += 1
    
    # After the thread pool is finished, print any captured output from the workers.
    # This avoids potential deadlocks from multiple threads printing to stdout simultaneously.
    for worker_output in all_worker_outputs:
        if worker_output:
            # Print captured output from worker so the test can see it.
            print(worker_output.strip())

    logging.info(f"\n--- Retry Phase Complete: {successful_retries} successful, {failed_retries} failed. ---")

    if successful_retries == 0:
        logging.warning("No sessions were successfully retried. Halting before re-analysis.")
        sys.exit(1)
        
    if failed_retries > 0:
        logging.warning(f"{failed_retries} sessions still failed to retry. The analysis will be updated, but may still be incomplete.")

    # --- Part 3: Re-run the full analysis pipeline on updated runs ---
    logging.info("\n--- Starting Full Analysis Update for Modified Runs ---")
    try:
        # Step 3a: Re-process and re-analyze each run directory that had retries.
        for i, run_dir_to_update in enumerate(runs_to_update):
            run_basename = os.path.basename(run_dir_to_update)
            logging.info(f"\n--- Re-analyzing '{run_basename}' ({i+1}/{len(runs_to_update)}) ---")
            
            # Call processor
            proc_result = subprocess.run([sys.executable, PROCESSOR_SCRIPT_PATH, "--run_output_dir", run_dir_to_update, "--quiet"], check=True, capture_output=True, text=True)
            # Print captured output from worker so the test can see it.
            if proc_result.stdout:
                print(proc_result.stdout.strip())
            
            # Call analyzer and get new report content
            analysis_result = subprocess.run([sys.executable, ANALYZER_SCRIPT_PATH, "--run_output_dir", run_dir_to_update, "--quiet"], check=True, capture_output=True, text=True)
            
            # Overwrite the report file
            report_pattern = os.path.join(run_dir_to_update, "replication_report_*.txt")
            existing_reports = glob.glob(report_pattern)
            if existing_reports:
                report_path = existing_reports[0]
                with open(report_path, "a", encoding='utf-8') as f_report:
                    f_report.write("\n\n" + "="*80 + "\n")
                    f_report.write(f"### ANALYSIS UPDATED AFTER RETRY on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ###\n")
                    f_report.write("--- New Analysis Summary: ---\n\n")
                    f_report.write(analysis_result.stdout)
                logging.info(f"      Appended updated analysis to: {os.path.basename(report_path)}")
            else:
                 logging.warning(f"      No original report found in {run_basename} to update.")


        # Step 3b: After all individual reports are updated, re-compile the master summary.
        logging.info("\n--- Final Step: Re-compiling master results CSV for all runs ---")
        compiler_result = subprocess.run([sys.executable, COMPILER_SCRIPT_PATH, compile_dir], check=True, capture_output=True, text=True)
        # Print captured output from worker so the test can see it.
        if compiler_result.stdout:
            print(compiler_result.stdout.strip())
        logging.info(f"Successfully updated 'final_summary_results.csv' in '{compile_dir}'.")

    except subprocess.CalledProcessError as e:
        logging.error("\n!!! A failure occurred during the analysis update phase. The results may be inconsistent.")
        logging.error(f"Command failed: {' '.join(e.cmd)}")
        logging.error(f"Output:\n{e.stdout}\n{e.stderr}")
        sys.exit(1)
    
    logging.info("\n--- Retry and Analysis Update Complete. ---")

    # --- Final Step: Exit with a specific code based on the outcome ---
    if successful_retries == 0 and failed_retries == 0:
        logging.info("Exiting with status 0: No pending failures were found.")
        sys.exit(0)
    elif failed_retries > 0:
        logging.error(f"Exiting with status 2: {failed_retries} session(s) could not be repaired.")
        sys.exit(2)
    else: # successful_retries > 0 and failed_retries == 0
        logging.info(f"Exiting with status 1: All {successful_retries} detected failures were successfully repaired.")
        sys.exit(1)


if __name__ == "__main__":
    main()