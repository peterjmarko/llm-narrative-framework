#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/verify_pipeline_completeness.py

"""
Verify Pipeline Completeness Utility

Purpose:
This script audits the entire output directory to verify that every query in
every replication run was successfully processed and included in the final
analysis data. It provides a definitive, high-level summary of data integrity.

Workflow:
1.  Scans a parent directory (e.g., 'output') for all `run_*` subdirectories.
2.  For each run, it compares three key counts:
    a. The number of query files (`llm_query_*.txt`) generated.
    b. The number of score matrices parsed into `all_scores.txt`.
    c. The number of ground-truth mappings in `all_mappings.txt`.
3.  A run is marked "COMPLETE" only if all three counts are equal.
4.  It prints a summary table with the status of each run and a final
    overall completeness percentage.

Command-Line Usage:
    # Audit the default 'output' directory
    python src/verify_pipeline_completeness.py

    # Audit a specific directory
    python src/verify_pipeline_completeness.py --parent_dir /path/to/my/experiments
"""

# === Start of src/verify_pipeline_completeness.py ===

import os
import glob
import re
import argparse
import sys
import logging

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(message)s', stream=sys.stdout)

def count_matrices_in_file(filepath: str, k: int) -> int:
    """Counts how many k x k matrices are in a file."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line for line in f.read().splitlines() if line.strip()]
        # Each matrix has k lines, so total lines should be a multiple of k.
        # This is a robust way to count even with blank lines between matrices.
        return len(lines) // k
    except Exception as e:
        logging.error(f"  - Could not read or parse matrix file {filepath}: {e}")
        return 0

def count_lines_in_file(filepath: str, skip_header: bool = True) -> int:
    """Counts data lines in a file, optionally skipping a header."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        start_index = 1 if skip_header and lines else 0
        return len([line for line in lines[start_index:] if line.strip()])
    except Exception as e:
        logging.error(f"  - Could not read line count from {filepath}: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Verify data completeness across all experiment runs.")
    parser.add_argument("--parent_dir", default="output",
                        help="The parent directory containing 'run_*' folders. Defaults to 'output'.")
    args = parser.parse_args()

    parent_dir = os.path.abspath(args.parent_dir)
    if not os.path.isdir(parent_dir):
        logging.error(f"Error: Directory not found at '{parent_dir}'")
        sys.exit(1)

    run_dirs = sorted(glob.glob(os.path.join(parent_dir, "run_*")))
    if not run_dirs:
        logging.info(f"No 'run_*' directories found in '{parent_dir}'. Nothing to verify.")
        return

    logging.info(f"--- Verifying Data Completeness for {len(run_dirs)} Runs in '{parent_dir}' ---\n")
    
    all_runs_data = []
    total_expected_queries = 0
    total_actual_queries = 0

    for run_dir in run_dirs:
        run_name = os.path.basename(run_dir)
        run_data = {"name": run_name, "status": "INCOMPLETE", "details": ""}

        # 1. Get expected number of queries (m) and group size (k) from the run name
        m_match = re.search(r"trl-(\d+)", run_name)
        k_match = re.search(r"sbj-(\d+)", run_name)
        
        if not m_match or not k_match:
            run_data["details"] = "Could not parse m (trials) or k (subjects) from directory name."
            all_runs_data.append(run_data)
            continue
        
        expected_queries = int(m_match.group(1))
        k = int(k_match.group(1))
        
        # 2. Count actual query and response files generated
        queries_path = os.path.join(run_dir, "session_queries")
        responses_path = os.path.join(run_dir, "session_responses")
        num_query_files = len(glob.glob(os.path.join(queries_path, "llm_query_*.txt")))
        num_response_files = len(glob.glob(os.path.join(responses_path, "llm_response_*.txt")))


        # 3. Count parsed matrices and mappings
        analysis_path = os.path.join(run_dir, "analysis_inputs")
        num_matrices = count_matrices_in_file(os.path.join(analysis_path, "all_scores.txt"), k)
        num_mappings = count_lines_in_file(os.path.join(analysis_path, "all_mappings.txt"), skip_header=True)

        # 4. Compare and determine status
        total_expected_queries += expected_queries
        total_actual_queries += num_matrices

        if num_query_files == expected_queries and num_response_files == expected_queries and num_matrices == expected_queries and num_mappings == expected_queries:
            run_data["status"] = "COMPLETE"
            run_data["details"] = f"{expected_queries}/{expected_queries} trials processed."
        else:
            details = []
            if num_query_files != expected_queries:
                details.append(f"Queries: {num_query_files}/{expected_queries}")
            # Add the new, more specific check for responses
            if num_response_files != expected_queries:
                details.append(f"Responses: {num_response_files}/{expected_queries}")
            if num_matrices != expected_queries:
                details.append(f"Matrices: {num_matrices}/{expected_queries}")
            if num_mappings != expected_queries:
                details.append(f"Mappings: {num_mappings}/{expected_queries}")
            run_data["details"] = ", ".join(details)
        
        all_runs_data.append(run_data)

    # Print summary table
    logging.info(f"{'Run Directory Name':<100} {'Status':<12} {'Details'}")
    logging.info(f"{'-'*100} {'-'*12} {'-'*20}")

    for run in all_runs_data:
        status_color = "\033[92m" if run['status'] == "COMPLETE" else "\033[91m"
        end_color = "\033[0m"
        logging.info(f"{run['name']:<100} {status_color}{run['status']:<12}{end_color} {run['details']}")

    # Print final summary
    if total_expected_queries > 0:
        completeness_percent = (total_actual_queries / total_expected_queries) * 100
        logging.info("\n--- Overall Summary ---")
        logging.info(f"Total Expected Trials Across All Runs: {total_expected_queries}")
        logging.info(f"Total Successfully Processed Trials:   {total_actual_queries}")
        logging.info(f"Overall Pipeline Completeness: {completeness_percent:.2f}%")
    else:
        logging.info("\nNo trials were expected across the scanned runs.")

if __name__ == "__main__":
    main()

# === End of src/verify_pipeline_completeness.py ===