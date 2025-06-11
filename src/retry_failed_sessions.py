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
            
    return failures_to_retry


def _retry_worker(run_dir: str, sessions_script_path: str, index: int) -> tuple[int, bool]:
    """
    A worker function to be run in a thread. Retries a single session.
    Returns the index and a boolean indicating success.
    """
    try:
        retry_cmd = [
            sys.executable, sessions_script_path,
            "--run_output_dir", run_dir,
            "--start_index", str(index), "--end_index", str(index),
            "--force-rerun", "--quiet"  # Run worker quietly to avoid jumbled logs
        ]
        # We don't capture output here to keep the main process responsive
        subprocess.run(retry_cmd, check=True, text=True, capture_output=True)
        return index, True
    except subprocess.CalledProcessError as e:
        # Log the specific error from the failed subprocess
        logging.error(f"  Retry for index {index} in {os.path.basename(run_dir)} FAILED. Subprocess stderr:\n{e.stderr}")
        return index, False
    except Exception as e:
        logging.error(f"  An unexpected error occurred while retrying index {index}: {e}")
        return index, False


def main():
    parser = argparse.ArgumentParser(
        description="Automatically finds and retries failed LLM sessions across all runs, then updates analysis.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--parent_dir",
                        help="The parent directory containing 'run_*' folders to automatically find and retry all failures.")
    group.add_argument("--run_dir",
                        help="The path to a specific 'run_*' folder to manually retry specific indices within it.")

    parser.add_argument("--indices", type=int, nargs='+',
                        help="A space-separated list of specific indices to retry. Must be used with --run_dir.")
    parser.add_argument("--parallel", type=int, default=10,
                        help="Number of parallel sessions to retry at once. Defaults to 10.")
    args = parser.parse_args()

    if args.indices and not args.run_dir:
        parser.error("--indices can only be used when a specific --run_dir is provided.")

    # --- Find all necessary pipeline scripts ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sessions_script_path = os.path.join(script_dir, "run_llm_sessions.py")
    reprocess_script_path = os.path.join(script_dir, "reprocess_runs.py")
    compiler_script_path = os.path.join(script_dir, "compile_results.py")
    
    for path in [sessions_script_path, reprocess_script_path, compiler_script_path]:
        if not os.path.exists(path):
            logging.error(f"Error: Could not find required script at: {path}")
            sys.exit(1)

    # --- Part 1: Determine work to be done ---
    failures_by_run = {}
    compile_dir = ""

    if args.run_dir:
        # MANUAL MODE: User provides a specific run and specific indices
        run_dir = os.path.abspath(args.run_dir)
        compile_dir = os.path.dirname(run_dir) # The parent of the run_dir
        if not os.path.isdir(run_dir):
            logging.error(f"Error: Provided run directory does not exist: {run_dir}")
            sys.exit(1)
        if not args.indices:
            parser.error("--indices must be provided when using --run_dir.")
        failures_by_run[run_dir] = args.indices
    else:
        # AUTOMATIC MODE: Find all failures in a parent directory
        compile_dir = os.path.abspath(args.parent_dir)
        if not os.path.isdir(compile_dir):
            logging.error(f"Error: Provided parent directory does not exist: {compile_dir}")
            sys.exit(1)
        failures_by_run = find_failed_sessions(compile_dir)

    if not failures_by_run:
        logging.info("--- Discovery Complete: No sessions to retry. Nothing to do. ---")
        sys.exit(0)

    runs_to_update = list(failures_by_run.keys())
    
    # --- Part 2: Retry all discovered failures in parallel ---
    logging.info(f"\n--- Starting Retry Phase (up to {args.parallel} parallel workers) ---")
    successful_retries = 0; failed_retries = 0

    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        for run_dir, indices_to_retry in failures_by_run.items():
            run_basename = os.path.basename(run_dir)
            logging.info(f"\n--- Submitting {len(indices_to_retry)} tasks for: {run_basename} ---")
            
            task_func = partial(_retry_worker, run_dir, sessions_script_path)
            future_to_index = {executor.submit(task_func, index): index for index in indices_to_retry}

            for future in tqdm(as_completed(future_to_index), total=len(indices_to_retry), desc=f"Retrying {run_basename}"):
                index, success = future.result()
                if success:
                    successful_retries += 1
                else:
                    failed_retries += 1

    logging.info(f"\n--- Retry Phase Complete: {successful_retries} successful, {failed_retries} failed. ---")

    if successful_retries == 0:
        logging.warning("No sessions were successfully retried. Halting before re-analysis.")
        sys.exit(1)
        
    if failed_retries > 0:
        logging.warning(f"{failed_retries} sessions still failed to retry. The analysis will be updated, but may still be incomplete.")

    # --- Part 3: Re-run the full analysis pipeline on updated runs ---
    logging.info("\n--- Starting Full Analysis Update for Modified Runs ---")
    processor_script_path = os.path.join(script_dir, "process_llm_responses.py")
    analyzer_script_path = os.path.join(script_dir, "analyze_performance.py")
    try:
        # Step 3a: Re-process and re-analyze each run directory that had retries.
        for i, run_dir_to_update in enumerate(runs_to_update):
            run_basename = os.path.basename(run_dir_to_update)
            logging.info(f"\n--- Re-analyzing '{run_basename}' ({i+1}/{len(runs_to_update)}) ---")
            
            # Call processor
            subprocess.run([sys.executable, processor_script_path, "--run_output_dir", run_dir_to_update, "--quiet"], check=True, capture_output=True, text=True)
            
            # Call analyzer and get new report content
            analysis_result = subprocess.run([sys.executable, analyzer_script_path, "--run_output_dir", run_dir_to_update, "--quiet"], check=True, capture_output=True, text=True)
            
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
        subprocess.run([sys.executable, compiler_script_path, compile_dir], check=True, capture_output=True, text=True)
        logging.info(f"Successfully updated 'final_summary_results.csv' in '{compile_dir}'.")

    except subprocess.CalledProcessError as e:
        logging.error("\n!!! A failure occurred during the analysis update phase. The results may be inconsistent.")
        logging.error(f"Command failed: {' '.join(e.cmd)}")
        logging.error(f"Output:\n{e.stdout}\n{e.stderr}")
        sys.exit(1)
    
    logging.info("\n--- Retry and Analysis Update Complete. ---")


if __name__ == "__main__":
    main()