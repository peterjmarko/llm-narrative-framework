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


def main():
    parser = argparse.ArgumentParser(
        description="Automatically finds and retries failed LLM sessions across all runs, then updates analysis.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--parent_dir", default="output",
                        help="The parent directory containing all the 'run_*' folders (defaults to 'output').")
    args = parser.parse_args()

    parent_dir = os.path.abspath(args.parent_dir)
    if not os.path.isdir(parent_dir):
        logging.error(f"Error: Provided parent directory does not exist: {parent_dir}")
        sys.exit(1)

    # Find the location of the scripts relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sessions_script_path = os.path.join(script_dir, "run_llm_sessions.py")
    processor_script_path = os.path.join(script_dir, "process_llm_responses.py")
    analyzer_script_path = os.path.join(script_dir, "analyze_performance.py")
    compiler_script_path = os.path.join(script_dir, "compile_results.py")

    required_scripts = {
        "LLM Sessions Runner": sessions_script_path, "Response Processor": processor_script_path,
        "Performance Analyzer": analyzer_script_path, "Results Compiler": compiler_script_path,
    }

    for name, path in required_scripts.items():
        if not os.path.exists(path):
            logging.error(f"Error: Could not find required script '{name}' at: {path}"); sys.exit(1)

    # --- Part 1: Discover all failed sessions ---
    failures_by_run = find_failed_sessions(parent_dir)

    if not failures_by_run:
        logging.info("--- Discovery Complete: No failed sessions found across all runs. Nothing to do. ---")
        sys.exit(0)

    logging.info("--- Discovery Complete: Found failures in the following runs ---")
    runs_to_update = list(failures_by_run.keys())
    for run_path, indices in failures_by_run.items():
        logging.info(f"  - In '{os.path.basename(run_path)}': Found {len(indices)} failed session(s) at indices {indices}")
    
    # --- Part 2: Retry all discovered failures ---
    logging.info("\n--- Starting Retry Phase ---")
    successful_retries = 0; failed_retries = 0

    for run_dir, indices_to_retry in failures_by_run.items():
        logging.info(f"\n--- Processing Run: {os.path.basename(run_dir)} ---")
        for index in indices_to_retry:
            logging.info(f"  >>> Retrying session for index: {index}")
            try:
                retry_cmd = [
                    sys.executable, sessions_script_path,
                    "--run_output_dir", run_dir,
                    "--start_index", str(index), "--end_index", str(index),
                    "--force-rerun", "-v"
                ]
                subprocess.run(retry_cmd, check=True, text=True)
                logging.info(f"  <<< Successfully retried session for index: {index}")
                successful_retries += 1
            except subprocess.CalledProcessError:
                logging.error(f"  !!! FAILED to retry session for index: {index}. The worker script exited with an error.")
                failed_retries += 1
            except Exception as e:
                logging.error(f"  !!! An unexpected error occurred while trying to retry index {index}: {e}")
                failed_retries += 1
    
    logging.info(f"\n--- Retry Phase Complete: {successful_retries} successful, {failed_retries} failed. ---")

    if successful_retries == 0:
        logging.warning("No sessions were successfully retried. Halting before re-analysis.")
        sys.exit(1)
        
    if failed_retries > 0:
        logging.warning(f"{failed_retries} sessions still failed to retry. The analysis will be updated, but may still be incomplete.")

    # --- Part 3: Re-run the full analysis pipeline on updated runs ---
    logging.info("\n--- Starting Full Analysis Update for Modified Runs ---")
    try:
        for i, run_dir_to_update in enumerate(runs_to_update):
            run_basename = os.path.basename(run_dir_to_update)
            logging.info(f"\n--- Updating analysis for '{run_basename}' ({i+1}/{len(runs_to_update)}) ---")
            
            # Step 3a: Re-process responses
            logging.info(f"  (1/2) Re-processing all LLM responses for '{run_basename}'...")
            subprocess.run([sys.executable, processor_script_path, "--run_output_dir", run_dir_to_update, "--quiet"], check=True)

            # Step 3b: Re-run analysis and capture output
            logging.info(f"  (2/2) Re-analyzing performance and updating report for '{run_basename}'...")
            analysis_result = subprocess.run([sys.executable, analyzer_script_path, "--run_output_dir", run_dir_to_update, "--quiet"], capture_output=True, text=True, check=True)
            
            report_pattern = os.path.join(run_dir_to_update, "replication_report_*.txt")
            existing_reports = glob.glob(report_pattern)
            if existing_reports:
                with open(existing_reports[0], 'w', encoding='utf-8') as f_report:
                    f_report.write(analysis_result.stdout)
                logging.info(f"      Overwrote report file: {os.path.basename(existing_reports[0])}")
            else:
                new_report_path = os.path.join(run_dir_to_update, f"replication_report_{datetime.now().strftime('%Y%m%d-%H%M%S')}_RETRY.txt")
                with open(new_report_path, 'w', encoding='utf-8') as f_report:
                     f_report.write(analysis_result.stdout)
                logging.warning(f"      Original report not found. Created new report: {os.path.basename(new_report_path)}")

        # Step 3c: Re-compile master results from all runs in the parent directory
        logging.info("\n--- Final Step: Re-compiling master results CSV for all runs ---")
        subprocess.run([sys.executable, compiler_script_path, parent_dir], check=True, capture_output=True, text=True)
        logging.info(f"Successfully updated 'final_summary_results.csv' in '{parent_dir}'.")

    except subprocess.CalledProcessError as e:
        logging.error("\n!!! A failure occurred during the analysis update phase. The results may be inconsistent.")
        logging.error(f"Command failed: {' '.join(e.cmd)}")
        logging.error(f"Output:\n{e.stdout}\n{e.stderr}")
        sys.exit(1)
    
    logging.info("\n--- Retry and Analysis Update Complete. ---")


if __name__ == "__main__":
    main()