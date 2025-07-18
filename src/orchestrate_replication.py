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
# Filename: src/orchestrate_replication.py

"""
Orchestrator for a Single Experimental Replication.

This script is the engine for executing or reprocessing a single, self-contained
experimental replication. It is typically called in a loop by the main batch
runner, `experiment_manager.py`.

It operates in two primary modes:

1.  **New Run Mode (default):**
    -   Creates a new, timestamped directory for the replication's artifacts.
    -   Archives the root `config.ini` file to the new directory for perfect
        reproducibility.
    -   Executes the complete six-stage pipeline by calling each script:
        1. `build_llm_queries.py`: Generates queries and trial data.
        2. `run_llm_sessions.py`: Interacts with the LLM API.
        3. `process_llm_responses.py`: Parses LLM responses into scores.
        4. `analyze_llm_performance.py`: Generates the base report and metrics.
        5. `run_bias_analysis.py`: Injects bias metrics into the report.
        6. `experiment_aggregator.py`: Creates the final `REPLICATION_results.csv`.

2.  **Reprocess Mode (`--reprocess`):**
    -   Operates on a specified, existing replication directory.
    -   Skips the expensive query generation and LLM interaction stages (1 & 2).
    -   Re-runs only the data processing and analysis stages (3 & 4), making it
        ideal for applying fixes or updates to the analysis logic.

In both modes, the script's final action is to generate a comprehensive
`replication_report.txt` file. This report contains all run parameters, the
final status, a human-readable summary, a machine-parsable JSON block of all
metrics, and the full logs from all pipeline stages.

Usage (as called by experiment_manager.py):
    python src/orchestrate_replication.py --replication_num 1 --base_output_dir path/to/exp

Usage (for manual reprocessing):
    python src/orchestrate_replication.py --reprocess --run_output_dir path/to/run_dir
"""

import argparse
import os
import sys
import datetime
import subprocess
import logging
import re
import shutil
import json
import glob
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

# --- Setup ---
try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT

def run_script(command, title, quiet=False):
    """
    Helper to run a script as a subprocess and capture its output.
    Returns a tuple: (full_output_string, return_code, error_object_if_any)
    The error_object_if_any will be a CalledProcessError if the subprocess
    returned a non-zero exit code.
    """
    print(f"--- Running Stage: {title} ---")
    header = (
        f"\n\n{'='*80}\n"
        f"### STAGE: {title} ###\n"
        f"COMMAND: {' '.join(command)}\n"
        f"{'='*80}\n\n"
    )
    
    result = None
    captured_stdout = ""
    captured_stderr = ""
    
    try:
        # Always run with check=False to capture all output regardless of exit code
        if title == "2. Run LLM Sessions":
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=None, check=False,
                text=True, encoding='utf-8', errors='replace'
            )
            captured_stdout = result.stdout
        else:
            result = subprocess.run(
                command, capture_output=True, check=False,
                text=True, encoding='utf-8', errors='replace'
            )
            captured_stdout = result.stdout
            captured_stderr = result.stderr

    except FileNotFoundError as e:
        error_message = (
            f"\n\n--- FAILED STAGE: {title} ---\n"
            f"Error: {e}\n"
            f"Details: Script not found or executable: {' '.join(command)}\n"
        )
        # For FileNotFoundError, there's no subprocess result, so we return a synthetic error
        return header + error_message, 1, e # Return code 1 for FileNotFoundError
    
    # Combine stdout and stderr for general processing and display
    full_captured_output = captured_stdout + captured_stderr

    lines = full_captured_output.splitlines()
    filtered_lines = [line for line in lines if "RuntimeWarning" not in line and "UserWarning" not in line]
    filtered_output = "\n".join(filtered_lines)

    # The orchestrator should only print the subprocess's output if it's NOT in quiet mode
    # and the subprocess itself is not handling its own output (e.g., Stage 2).
    # For quiet mode, the orchestrator should capture but not print.
    if not quiet:
        # For Stage 2, output is already streamed, so we don't print the captured stdout again.
        # For other stages, print the captured and filtered output.
        if title != "2. Run LLM Sessions":
            print(filtered_output)

    # The returned output should contain the header and the filtered output
    final_output_string = header + filtered_output
    
    # Return the full output, the return code, and the CalledProcessError if applicable
    if result.returncode != 0:
        # Manually create a CalledProcessError to attach the full captured output
        err = subprocess.CalledProcessError(result.returncode, command, output=captured_stdout, stderr=captured_stderr)
        err.full_log = final_output_string # Attach the complete output for inspection
        return final_output_string, result.returncode, err
    else:
        return final_output_string, 0, None # Success, no error object

def generate_run_dir_name(model_name, temperature, num_iterations, k_per_query, personalities_db, replication_num):
    """Generates a descriptive, sanitized directory name."""
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_short = model_name.split('/')[-1] if model_name else "unknown_model"
    try:
        temp_str = f"tmp-{float(temperature):.2f}"
    except (ValueError, TypeError):
        temp_str = "tmp-NA"
    db_base = os.path.splitext(os.path.basename(personalities_db))[0]
    subjects_str = f"sbj-{k_per_query:02d}"
    trials_str = f"trl-{num_iterations:03d}"
    replication_str = f"rep-{replication_num:03d}"
    parts = ["run", timestamp_str, replication_str, model_short, temp_str, db_base, subjects_str, trials_str]
    sanitized_parts = [re.sub(r'[^a-zA-Z0-9_.-]', '_', part) for part in parts]
    return "_".join(sanitized_parts)

def main():
    parser = argparse.ArgumentParser(description="Runs or re-processes a single replication.")
    parser.add_argument("--notes", type=str, default="N/A", help="Optional notes for the report.")
    parser.add_argument("--replication_num", type=int, default=1, help="Replication number for new runs.")
    parser.add_argument("--base_seed", type=int, default=None, help="Base random seed for personality selection.")
    parser.add_argument("--qgen_base_seed", type=int, default=None, help="Base random seed for shuffling.")
    parser.add_argument("--quiet", action="store_true", help="Run all stages in quiet mode.")
    parser.add_argument("--reprocess", action="store_true", help="Re-process existing responses.")
    parser.add_argument("--run_output_dir", type=str, default=None, help="Path to a specific run output directory for reprocessing.")
    parser.add_argument("--base_output_dir", type=str, default=None, help="The base directory where the new run folder should be created.")
    parser.add_argument("--indices", type=int, nargs='+', help="A specific list of trial indices to run. If provided, only these trials will be executed.")
    
    args = parser.parse_args()
    
    all_stage_outputs = []
    pipeline_status = "FAILED" # Default to FAILED, changed to COMPLETED only on full success
    output3, output4, output5 = "", "", ""

    if args.reprocess:
        if not args.run_output_dir or not os.path.isdir(args.run_output_dir):
            logging.error("FATAL: --run_output_dir must be a valid directory in --reprocess mode.")
            sys.exit(1)
        run_specific_dir_path = args.run_output_dir
        logging.info(f"--- REPROCESS MODE for: {os.path.basename(run_specific_dir_path)} ---")
        
        config_path = os.path.join(run_specific_dir_path, 'config.ini.archived')
        if not os.path.exists(config_path):
            logging.error(f"FATAL: Archived config not found at {config_path}. Cannot reprocess.")
            sys.exit(1)
        config = configparser.ConfigParser()
        config.read(config_path)
        args.num_iterations = config.getint('Study', 'num_trials', fallback=100)
        args.k_per_query = config.getint('Study', 'group_size', fallback=10)
    else:
        # --- Robust Parameter Reading ---
        model_name = get_config_value(APP_CONFIG, 'LLM', 'model_name', fallback_key='model')
        temp = get_config_value(APP_CONFIG, 'LLM', 'temperature', value_type=float)
        db_file = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src')
        args.num_iterations = get_config_value(APP_CONFIG, 'Study', 'num_trials', fallback_key='num_iterations', value_type=int)
        args.k_per_query = get_config_value(APP_CONFIG, 'Study', 'group_size', fallback_key='k_per_query', value_type=int)
        
        run_dir_name = generate_run_dir_name(model_name, temp, args.num_iterations, args.k_per_query, db_file, args.replication_num)

        # Use the provided base_output_dir if available, otherwise fall back to the config setting
        if args.base_output_dir:
            base_output_dir = args.base_output_dir
        else:
            # Fallback for standalone runs: use the path from config.ini
            base_output_dir = os.path.join(PROJECT_ROOT, get_config_value(APP_CONFIG, 'General', 'base_output_dir'))

        run_specific_dir_path = os.path.join(base_output_dir, run_dir_name)
        os.makedirs(run_specific_dir_path, exist_ok=True)
        logging.info(f"Created unique output directory: {run_specific_dir_path}")
        shutil.copy2(os.path.join(PROJECT_ROOT, 'config.ini'), os.path.join(run_specific_dir_path, 'config.ini.archived'))

    src_dir = os.path.join(PROJECT_ROOT, 'src')
    build_script = os.path.join(src_dir, 'build_llm_queries.py')
    run_sessions_script = os.path.join(src_dir, 'run_llm_sessions.py')
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_llm_performance.py')
    bias_script = os.path.join(src_dir, 'run_bias_analysis.py')
    aggregator_script = os.path.join(src_dir, 'experiment_aggregator.py')

    try:
        # Stage 1: Build Queries (only for new runs)
        if not args.reprocess:
            cmd1 = [sys.executable, build_script, "--run_output_dir", run_specific_dir_path]
            if args.quiet: cmd1.append("--quiet")
            if args.base_seed: cmd1.extend(["--base_seed", str(args.base_seed)])
            if args.qgen_base_seed: cmd1.extend(["--qgen_base_seed", str(args.qgen_base_seed)])
            output1, rc1, err1 = run_script(cmd1, "1. Build LLM Queries", quiet=args.quiet)
            all_stage_outputs.append(output1)
            if rc1 != 0: raise err1

        # Stage 2: Run LLM Sessions (Parallel by default)
        stage_title = "2. Run LLM Sessions (Parallel)"
        header = (f"\n\n{'='*80}\n### STAGE: {stage_title} ###\n{'='*80}\n\n")
        print(f"--- Running Stage: {stage_title} ---")

        # Determine which indices to run based on the mode.
        if args.indices:
            # Repair mode: run only the specified failed indices.
            indices_to_run = args.indices
            force_rerun = True # Force re-run for failed trials.
        else:
            # New/Continue mode: find all queries and run only those without responses.
            queries_dir = os.path.join(run_specific_dir_path, "session_queries")
            query_files = glob.glob(os.path.join(queries_dir, "llm_query_*.txt"))
            
            # Robustly parse indices from filenames
            all_indices = []
            for f in query_files:
                match = re.search(r'_(\d+)\.txt$', f)
                if match:
                    all_indices.append(int(match.group(1)))
            all_indices.sort()
            
            indices_to_run = []
            responses_dir = os.path.join(run_specific_dir_path, "session_responses")
            for i in all_indices:
                if not os.path.exists(os.path.join(responses_dir, f"llm_response_{i:03d}.txt")):
                    indices_to_run.append(i)
            force_rerun = False # Don't force re-run, just continue.

        if not indices_to_run:
            all_stage_outputs.append(header + "All required LLM response files already exist. Nothing to do.")
        else:
            max_workers = get_config_value(APP_CONFIG, 'LLM', 'max_parallel_sessions', value_type=int, fallback=10)
            
            def session_worker(index):
                cmd = [sys.executable, run_sessions_script, "--run_output_dir", run_specific_dir_path, "--indices", str(index), "--quiet"]
                if force_rerun: cmd.append("--force-rerun")
                else: cmd.append("--continue-run")
                try:
                    subprocess.run(cmd, check=True, text=True, capture_output=True)
                    return (index, True, None)
                except subprocess.CalledProcessError as e:
                    return (index, False, f"LLM session FAILED for index {index}\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}")

            all_logs = [header]
            failed_sessions = 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                tasks = {executor.submit(session_worker, i) for i in indices_to_run}
                for future in tqdm(as_completed(tasks), total=len(tasks), desc="Processing LLM Sessions", ncols=80):
                    _, success, log = future.result()
                    if not success:
                        failed_sessions += 1
                        all_logs.append(log)
            
            all_stage_outputs.append("\n".join(all_logs))
            if failed_sessions > 0:
                raise Exception(f"{failed_sessions} LLM session(s) failed. See logs for details.")

        # The rest of the pipeline proceeds only after sessions are complete.
        # Stage 3: Process LLM Responses
        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd3.append("--quiet")
        output3, rc3, err3 = run_script(cmd3, "3. Process LLM Responses", quiet=args.quiet)
        all_stage_outputs.append(output3)
        if rc3 != 0: raise err3
        
        n_valid_str = (re.search(r"<<<PARSER_SUMMARY:(\d+):", output3) or ['0','0'])[1]
        
        # Stage 4: Analyze Performance
        cmd4 = [sys.executable, analyze_script, "--run_output_dir", run_specific_dir_path, "--num_valid_responses", n_valid_str]
        if args.quiet: cmd4.append("--quiet")
        output4, rc4, err4 = run_script(cmd4, "4. Analyze LLM Performance", quiet=args.quiet)
        all_stage_outputs.append(output4)
        if rc4 != 0: raise err4

        # Stage 5: Run Bias Analysis
        k_val = int(get_config_value(APP_CONFIG, 'Study', 'group_size', fallback_key='k_per_query', value_type=int, fallback=10))
        cmd5 = [sys.executable, bias_script, run_specific_dir_path, "--k_value", str(k_val)]
        if not args.quiet: cmd5.append("--verbose")
        output5, rc5, err5 = run_script(cmd5, "5. Run Bias Analysis", quiet=args.quiet)
        all_stage_outputs.append(output5)
        if rc5 != 0: raise err5

        # Stage 6: Generate Final Report
        stage_title_6 = "6. Generate Final Report"
        header_6 = (f"\n\n{'='*80}\n### STAGE: {stage_title_6} ###\n{'='*80}\n\n")
        print(f"--- Running Stage: {stage_title_6} ---")
        for old_report in glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')): os.remove(old_report)
        report_path = os.path.join(run_specific_dir_path, f"replication_report_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")
        try:
            with open(os.path.join(run_specific_dir_path, 'analysis_inputs', 'replication_metrics.json'), 'r') as f: metrics_data = json.load(f)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(f"REPLICATION RUN REPORT\n{'='*80}\n")
                f.write(f"Run Directory: {os.path.basename(run_specific_dir_path)}\nDate: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M%S')}\nStatus: PENDING\n")
                f.write("### Machine-Readable Metrics (JSON) ###\n<<<METRICS_JSON_START>>>\n")
                f.write(json.dumps(metrics_data, indent=4) + "\n<<<METRICS_JSON_END>>>\n")
            all_stage_outputs.append(header_6 + f"Successfully generated report shell: {report_path}")
        except Exception as e:
            logging.error(f"Failed during Stage 6 (Report Generation): {e}"); raise

        # Stage 7: Create Replication Summary
        cmd7 = [sys.executable, aggregator_script, run_specific_dir_path, "--mode", "hierarchical"]
        output7, rc7, err7 = run_script(cmd7, "7. Create Replication Summary", quiet=args.quiet)
        all_stage_outputs.append(output7)
        if rc7 != 0: raise err7

        pipeline_status = "COMPLETED"

    except (KeyboardInterrupt, subprocess.CalledProcessError, Exception) as e:
        if isinstance(e, KeyboardInterrupt):
            pipeline_status = "INTERRUPTED BY USER"
        else:
            pipeline_status = "FAILED"
        
        # Minimalist error logging
        logging.error(f"\n\n--- PIPELINE {pipeline_status} ---")
        if isinstance(e, subprocess.CalledProcessError) and hasattr(e, 'full_log'):
            all_stage_outputs.append(e.full_log)
        else:
            import traceback
            all_stage_outputs.append(f"\n--- ERROR DETAILS ---\n{traceback.format_exc()}")
        
        # The orchestrator still needs to generate a final report, even on failure.
        # The logic for this is now consolidated with the success path.
        pass

    # --- Finalization: Update Report Status and Append Logs ---
    # This block runs regardless of success or failure. It finds the report
    # created in Stage 6 and updates its status and appends full logs.
    latest_report_files = sorted(glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')))
    if latest_report_files:
        report_path = latest_report_files[-1]
        try:
            # First, append the full logs to the existing file
            with open(report_path, 'a', encoding='utf-8') as f:
                f.write("\n\n" + "="*80 + "\n### FULL STAGE LOGS ###\n" + "="*80)
                f.write("".join(all_stage_outputs))
            
            # Then, read the entire file and replace the status line
            with open(report_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                content = re.sub(r"^(Status: PENDING)$", f"Status: {pipeline_status}", content, flags=re.MULTILINE)
                f.seek(0)
                f.write(content)
                f.truncate()
        except IOError as e:
            logging.error(f"Could not update final report {report_path}: {e}")
    else:
        # If no report exists (major failure before Stage 6), create a simple failure log.
        fail_log_path = os.path.join(run_specific_dir_path, 'orchestration_FAILURE.log')
        with open(fail_log_path, 'w', encoding='utf-8') as f:
             f.write(f"PIPELINE {pipeline_status}\n\n" + "".join(all_stage_outputs))

    logging.info(f"Replication run finished. Final status: {pipeline_status}")


if __name__ == "__main__":
    main()

# === End of src/orchestrate_replication.py ===
