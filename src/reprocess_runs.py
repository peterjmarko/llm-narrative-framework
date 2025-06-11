#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/reprocess_runs.py

"""
Re-process and Re-analyze All Experiment Runs

Purpose:
This script orchestrates the re-processing of all completed experimental runs
found within a parent directory. It is useful for applying updated analysis logic
to an entire batch of existing raw data without re-running the costly LLM queries.

Workflow:
1.  Takes a parent directory (e.g., 'output') as input.
2.  Identifies all 'run_*' subdirectories within the parent directory.
3.  For each 'run_*' directory found:
    a. Calls `process_llm_responses.py` to delete the old `analysis_inputs`
       folder and regenerate it from the raw `session_responses`.
    b. If processing is successful, it calls `analyze_performance.py`.
    c. It captures the full standard output from the analysis script.
    d. It finds the existing `replication_report_*.txt` in the run directory
       and **overwrites** it with the newly captured analysis output.
4.  After all runs have been re-analyzed, it calls `compile_results.py` on the
    parent directory to generate a fresh, updated `final_summary_results.csv`.

Command-Line Usage:
    # Re-process all runs located in the default 'output' directory
    python src/reprocess_runs.py --parent_dir output
"""

import argparse
import os
import sys
import glob
import subprocess
import logging
from datetime import datetime
import re
import os

try:
    from config_loader import APP_CONFIG, get_config_value
except ImportError:
    print("FATAL: Could not import from config_loader.py. Ensure it is in the same directory as reprocess_runs.py.")
    sys.exit(1)

# --- Basic Logging Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    stream=sys.stdout)

def main():
    parser = argparse.ArgumentParser(description="Re-process and re-analyze completed LLM experiment runs.")
    parser.add_argument("--target_dir", default="output",
                        help="Path to the directory to process. Can be a parent containing multiple 'run_*' folders, or a single 'run_*' folder. Defaults to 'output'.")
    args = parser.parse_args()

    # Find the location of the scripts relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    processor_script_path = os.path.join(script_dir, "process_llm_responses.py")
    analyzer_script_path = os.path.join(script_dir, "analyze_performance.py")
    compiler_script_path = os.path.join(script_dir, "compile_results.py")

    if not os.path.exists(processor_script_path) or not os.path.exists(analyzer_script_path) or not os.path.exists(compiler_script_path):
        logging.error(f"Error: Could not find one or more required scripts (processor, analyzer, compiler) in the directory: {script_dir}")
        sys.exit(1)

    # Determine which directories to process
    target_dir = os.path.abspath(args.target_dir)
    if not os.path.isdir(target_dir):
        logging.error(f"Error: Target directory does not exist: {target_dir}")
        sys.exit(1)

    run_directories = []
    parent_dir_for_compilation = None

    # Check if the target_dir is a run directory itself or a parent of run directories
    if os.path.basename(target_dir).startswith("run_"):
        run_directories.append(target_dir)
        parent_dir_for_compilation = None # Do not recompile master summary for a single run
        logging.info(f"Processing single specified run directory: {target_dir}")
    else:
        run_directories = sorted(glob.glob(os.path.join(target_dir, "run_*")))
        parent_dir_for_compilation = target_dir
        logging.info(f"Found {len(run_directories)} run directories to re-process in parent: {target_dir}")

    if not run_directories:
        logging.warning(f"No 'run_*' directories found to process in '{target_dir}'. Nothing to do.")
        sys.exit(0)

    total_runs = len(run_directories)
    
    success_count = 0
    fail_count = 0

    for i, run_path in enumerate(run_directories):
        run_name = os.path.basename(run_path)
        logging.info(f"\n--- [{i+1}/{total_runs}] STARTING RE-PROCESSING FOR: {run_name} ---")

        try:
            # === Step 1: Re-run the processor script ===
            logging.info(f"  (1/3) Calling process_llm_responses.py for {run_name}...")
            proc_result = subprocess.run(
                [sys.executable, processor_script_path, "--run_output_dir", run_path, "--quiet"],
                capture_output=True, text=True, check=True  # check=True will raise an exception on non-zero exit codes
            )
            logging.info(f"  Processor finished successfully.")

            # === Step 2: Re-run the analyzer script and capture its output ===
            logging.info(f"  (2/3) Calling analyze_performance.py for {run_name}...")
            analysis_result = subprocess.run(
                [sys.executable, analyzer_script_path, "--run_output_dir", run_path, "--quiet"],
                capture_output=True, text=True, check=True
            )
            analysis_output = analysis_result.stdout
            logging.info(f"  Analyzer finished successfully. Captured report output.")
            
            # === Step 3: Find and overwrite the replication report ===
            logging.info(f"  (3/3) Re-generating replication report...")
            report_pattern = os.path.join(run_path, "replication_report_*.txt")
            existing_reports = glob.glob(report_pattern)
            
            if existing_reports:
                report_path = existing_reports[0]
                if len(existing_reports) > 1:
                    logging.warning(f"    Multiple reports found for {run_name}. Overwriting the first one: {report_path}")
            else:
                # If no report exists, create one with a new timestamp.
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = os.path.join(run_path, f"replication_report_{timestamp}.txt")
                logging.warning(f"    No existing report found for {run_name}. Creating a new one: {report_path}")

            # --- Reconstruct the full report content ---
            # Get static parameters from config file
            personalities_file = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src', 'N/A')
            llm_model = get_config_value(APP_CONFIG, 'LLM', 'model_name', 'N/A')
            
            # Extract dynamic parameters from the run directory name
            k_match = re.search(r"sbj-(\d+)", run_name)
            m_match = re.search(r"trl-(\d+)", run_name)
            k_val = k_match.group(1) if k_match else "N/A"
            m_val = m_match.group(1) if m_match else "N/A"

            header = f"""
================================================================================
 REPLICATION RUN REPORT (Re-processed on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
================================================================================
Date:            {run_name.split('_')[1]}
Final Status:    COMPLETED
Run Directory:   {run_name}
Validation Status: OK (Re-processed run)
Report File:     {os.path.basename(report_path)}

--- Run Parameters ---
Num Iterations (m): {m_val}
Items per Query (k): {k_val}
Personalities Source: {personalities_file}
LLM Model:       {llm_model}
Run Notes:       This report was regenerated by reprocess_runs.py.
================================================================================

{analysis_output}
"""
            with open(report_path, 'w', encoding='utf-8') as f_report:
                f_report.write(header.strip())
            
            logging.info(f"  Successfully updated report file: {report_path}")
            success_count += 1

        except subprocess.CalledProcessError as e:
            logging.error(f"  !!! FAILED to re-process {run_name}. Subprocess returned non-zero exit code.")
            logging.error(f"  - Command: {' '.join(e.cmd)}")
            logging.error(f"  - stdout:\n{e.stdout}")
            logging.error(f"  - stderr:\n{e.stderr}")
            fail_count += 1
        except Exception as e:
            logging.error(f"  !!! FAILED to re-process {run_name} with an unexpected Python error: {e}")
            fail_count += 1

    # === Final Step: Re-compile the master results CSV ===
    # Only run the compiler if we processed a whole parent directory
    if success_count > 0 and parent_dir_for_compilation:
        logging.info(f"\n--- Re-compiling master results file ---")
        try:
            logging.info(f"  (Final Step) Calling compile_results.py for parent directory: {target_dir}...")
            compiler_result = subprocess.run(
                [sys.executable, compiler_script_path, target_dir],
                capture_output=True, text=True, check=True
            )
            # The compiler prints its own success message, so we can just log that it's done.
            logging.info(f"  Compiler finished successfully.")
            # Print the compiler's output for confirmation
            if compiler_result.stdout:
                logging.info("  Compiler output:\n" + compiler_result.stdout.strip())

        except subprocess.CalledProcessError as e:
            logging.error(f"  !!! FAILED to re-compile master results.")
            logging.error(f"  - Command: {' '.join(e.cmd)}")
            logging.error(f"  - stdout:\n{e.stdout}")
            logging.error(f"  - stderr:\n{e.stderr}")
            fail_count += 1 # Increment fail count to reflect this final failure
        except Exception as e:
            logging.error(f"  !!! FAILED to re-compile master results with an unexpected Python error: {e}")
            fail_count += 1

    logging.info(f"\n--- RE-PROCESSING AND COMPILATION COMPLETE ---")
    logging.info(f"Total Runs Processed: {total_runs} | Successful Runs: {success_count} | Total Failures (runs + compilation): {fail_count}")

if __name__ == "__main__":
    main()