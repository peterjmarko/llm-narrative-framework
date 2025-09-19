#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 Peter J. Marko
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
# Filename: src/replication_manager.py

"""
Manager for a Single Experimental Replication.

This script is the engine for executing or reprocessing a single, self-contained
experimental replication. It manages the entire lifecycle by calling a dedicated
script for each of the six pipeline stages.

It is typically called by `experiment_manager.py`.

Pipeline Stages:
1.  `build_llm_queries.py`: Generates all trial queries and supporting files.
2.  `run_llm_sessions.py`: Executes parallel API calls to the LLM.
3.  `process_llm_responses.py`: Parses raw text responses into structured data.
4.  `analyze_llm_performance.py` & `run_bias_analysis.py`: Calculate metrics.
5.  `generate_replication_report.py`: Creates the final formatted text report.
6.  `compile_replication_results.py`: Creates the final single-row summary CSV.

It can also operate in a `--reprocess` mode, which re-runs only the data
processing and analysis stages (3-6) on existing raw data.

Usage (as called by experiment_manager.py):
    python src/replication_manager.py --replication_num 1 --base_output_dir path/to/exp

Usage (for manual reprocessing):
    python src/replication_manager.py --reprocess --run_output_dir path/to/run_dir
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
import time
import configparser
from concurrent.futures import ThreadPoolExecutor, as_completed

from colorama import Fore, init

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

# Initialize colorama
init(autoreset=True)

# Define ANSI color codes for consistency with experiment_manager.py
C_YELLOW = '\033[93m'
C_RESET = '\033[0m'

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s (orchestrator): %(message)s', stream=sys.stderr)

# --- Setup ---
try:
    import config_loader
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    import config_loader

# For convenience, keep direct access to these as they are not the source of the patching issue.
APP_CONFIG = config_loader.APP_CONFIG
get_config_value = config_loader.get_config_value

def run_script(command, title, verbose=False):
    """
    Helper to run a script as a subprocess.
    Raises CalledProcessError on failure, which includes stdout/stderr.
    Returns the process's stdout on success.
    """
    # Use a different printer for sub-stages to avoid confusion.
    if not re.match(r"\d+[a-z]", title):
        # This is a main stage like "1. Build LLM Queries", not "4a."
        print(f"--- Running Stage: {title} ---")
    
    # Run the subprocess, capturing output. check=True raises an error on failure.
    result = subprocess.run(
        command,
        capture_output=True,
        check=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    # Only print the child's stdout if the orchestrator is in verbose mode.
    if verbose and result.stdout:
        print(result.stdout)
        
    return result.stdout

def generate_run_dir_name(model_name, temperature, num_iterations, k_per_query, personalities_db, replication_num, num_replications, mapping_strategy):
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
    total_reps_str = f"rps-{num_replications:03d}"
    strategy_str = f"mps-{mapping_strategy}"
    
    parts = ["run", timestamp_str, replication_str, model_short, temp_str, db_base, subjects_str, trials_str, total_reps_str, strategy_str]
    sanitized_parts = [re.sub(r'[^a-zA-Z0-9_.-]', '_', part) for part in parts]
    return "_".join(sanitized_parts)

def session_worker(index, run_specific_dir_path, responses_dir, llm_prompter_script, src_dir, verbose):
    """Executes a single LLM prompter session as a subprocess."""
    query_filepath = os.path.join(run_specific_dir_path, "session_queries", f"llm_query_{index:03d}.txt")
    final_response_filepath = os.path.join(responses_dir, f"llm_response_{index:03d}.txt")
    final_error_filepath = os.path.join(responses_dir, f"llm_response_{index:03d}.error.txt")
    final_json_filepath = os.path.splitext(final_response_filepath)[0] + "_full.json"
    config_path = os.path.join(run_specific_dir_path, 'config.ini.archived')

    worker_cmd = [sys.executable, llm_prompter_script, f"{index:03d}",
                    "--input_query_file", query_filepath,
                    "--output_response_file", final_response_filepath,
                    "--output_error_file", final_error_filepath,
                    "--output_json_file", final_json_filepath,
                    "--config_path", config_path]
    if verbose: worker_cmd.append("-v")
    
    start_time = time.time()
    try:
        result = subprocess.run(worker_cmd, check=False, cwd=src_dir, capture_output=True, text=True, encoding='utf-8', errors='replace')
        duration = time.time() - start_time
        if result.returncode == 0:
            return index, True, None, duration
        else:
            error_details = f"LLM prompter FAILED for index {index} with exit code {result.returncode}"
            if result.stderr:
                error_details += f"\n  STDERR: {result.stderr.strip()}"
            return index, False, error_details, duration
    except Exception as e:
        return index, False, f"Orchestrator worker failed for index {index}: {e}", time.time() - start_time


def main():
    all_stage_outputs = []
    parser = argparse.ArgumentParser(description="Runs or re-processes a single replication.")
    parser.add_argument("--notes", type=str, default="N/A", help="Optional notes for the report.")
    parser.add_argument("--replication_num", type=int, default=1, help="Replication number for new runs.")
    parser.add_argument("--base_seed", type=int, default=None, help="Base random seed for personality selection.")
    parser.add_argument("--qgen_base_seed", type=int, default=None, help="Base random seed for shuffling.")
    parser.add_argument("--reprocess", action="store_true", help="Re-process existing responses.")
    parser.add_argument("--run_output_dir", type=str, default=None, help="Path to a specific run output directory for reprocessing.")
    parser.add_argument("--base_output_dir", type=str, default=None, help="The base directory where the new run folder should be created.")
    parser.add_argument("--indices", type=int, nargs='+', help="A specific list of trial indices to run. If provided, only these trials will be executed.")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose (DEBUG level) output from child scripts.")
    
    args = parser.parse_args()
    
    pipeline_status = "FAILED" # Default to FAILED, changed to COMPLETED only on full success
    output3 = ""
    repair_had_failures = False

    if args.reprocess:
        if not args.run_output_dir or not os.path.isdir(args.run_output_dir):
            logging.error("FATAL: --run_output_dir must be a valid directory in --reprocess mode.")
            sys.exit(1)
        run_specific_dir_path = args.run_output_dir
        
        # Determine if this is a repair or a full reprocess for logging clarity
        mode_string = "REPAIR MODE" if args.indices else "REPROCESS MODE"
        print(f"\n{C_YELLOW}--- {mode_string} for: ---{C_RESET}")
        print(f"{os.path.basename(run_specific_dir_path)}")
        
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
        num_replications = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int)
        mapping_strategy = get_config_value(APP_CONFIG, 'Study', 'mapping_strategy')
        
        run_dir_name = generate_run_dir_name(model_name, temp, args.num_iterations, args.k_per_query, db_file, args.replication_num, num_replications, mapping_strategy)

        # Use the provided base_output_dir if available, otherwise fall back to the config setting
        if args.base_output_dir:
            base_output_dir = args.base_output_dir
        else:
            # Fallback for standalone runs: use the path from config.ini
            base_output_dir = os.path.join(config_loader.PROJECT_ROOT, get_config_value(APP_CONFIG, 'General', 'base_output_dir'))

        run_specific_dir_path = os.path.join(base_output_dir, run_dir_name)
        os.makedirs(run_specific_dir_path, exist_ok=True)
        logging.info(f"Created unique output directory: {run_specific_dir_path}")
        
        # Determine which config file to archive. Use the override if it exists.
        config_override_path = os.getenv('PROJECT_CONFIG_OVERRIDE')
        if config_override_path and os.path.exists(config_override_path):
            source_config_path = config_override_path
        else:
            source_config_path = os.path.join(config_loader.PROJECT_ROOT, 'config.ini')
            
        shutil.copy2(source_config_path, os.path.join(run_specific_dir_path, 'config.ini.archived'))

    src_dir = os.path.join(config_loader.PROJECT_ROOT, 'src')
    build_script = os.path.join(src_dir, 'build_llm_queries.py')
    run_sessions_script = os.path.join(src_dir, 'run_llm_sessions.py')
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_llm_performance.py')
    bias_script = os.path.join(src_dir, 'run_bias_analysis.py')
    generate_report_script = os.path.join(src_dir, 'generate_replication_report.py')
    summarize_script = os.path.join(src_dir, 'compile_replication_results.py')

    try:
        # Stage 1: Build Queries (only for new runs)
        if not args.reprocess:
            cmd1 = [sys.executable, build_script, "--run_output_dir", run_specific_dir_path]
            if args.verbose: cmd1.append("-v")
            if args.base_seed: cmd1.extend(["--base_seed", str(args.base_seed)])
            if args.qgen_base_seed: cmd1.extend(["--qgen_base_seed", str(args.qgen_base_seed)])
            run_script(cmd1, "1. Build LLM Queries", verbose=args.verbose)

        # Stage 2: Run LLM Sessions (Parallel by default)
        stage_title_2 = "2. Run LLM Sessions"
        header_2 = (f"\n\n{'='*80}\n### STAGE: {stage_title_2} ###\n{'='*80}\n\n")

        # Determine which indices to run based on the mode.
        if args.indices:
            indices_to_run = args.indices
        else:
            queries_dir = os.path.join(run_specific_dir_path, "session_queries")
            query_files = glob.glob(os.path.join(queries_dir, "llm_query_*.txt"))
            all_indices = sorted([int(re.search(r'_(\d+)\.txt$', f).group(1)) for f in query_files if re.search(r'_(\d+)\.txt$', f)])
            
            indices_to_run = []
            responses_dir = os.path.join(run_specific_dir_path, "session_responses")
            for i in all_indices:
                txt_path = os.path.join(responses_dir, f"llm_response_{i:03d}.txt")
                json_path = os.path.join(responses_dir, f"llm_response_{i:03d}_full.json")
                if not os.path.exists(txt_path) or not os.path.exists(json_path):
                    indices_to_run.append(i)

        if not indices_to_run:
            logging.info("All required LLM response files already exist. Nothing to do.")
        else:
            print(f"--- Running Stage: {stage_title_2} ---")
            max_workers = get_config_value(APP_CONFIG, 'LLM', 'max_parallel_sessions', value_type=int, fallback=10)
            llm_prompter_script = os.path.join(src_dir, 'llm_prompter.py')

            # Get the responses subdirectory name ONCE from the config for consistency.
            responses_subdir_name = get_config_value(APP_CONFIG, 'General', 'responses_subdir', fallback='session_responses')
            responses_dir = os.path.join(run_specific_dir_path, responses_subdir_name)
            
            # Ensure the response directory exists before starting workers.
            os.makedirs(responses_dir, exist_ok=True)
            
            # If in a repair context, clean up old artifacts for the target indices first.
            if args.reprocess or args.indices:
                logging.info(f"Repair mode: Cleaning previous artifacts for {len(indices_to_run)} trial(s)...")
                for index in indices_to_run:
                    base_path = os.path.join(responses_dir, f"llm_response_{index:03d}")
                    for ext in [".txt", "_full.json", ".error.txt"]:
                        file_to_delete = f"{base_path}{ext}"
                        if os.path.exists(file_to_delete):
                            try:
                                os.remove(file_to_delete)
                            except OSError as e:
                                logging.warning(f"Could not remove old artifact {os.path.basename(file_to_delete)}: {e}")

            api_times_log_path = os.path.join(run_specific_dir_path, get_config_value(APP_CONFIG, 'Filenames', 'api_times_log', fallback="api_times.log"))
            if not os.path.exists(api_times_log_path):
                with open(api_times_log_path, "w", encoding='utf-8') as f:
                    f.write("Query_ID\tCall_Duration_s\tTotal_Elapsed_s\tEstimated_Time_Remaining_s\n")

            all_logs = [header_2]
            failed_sessions, total_elapsed_time, completed_count = 0, 0.0, 0
            with ThreadPoolExecutor(max_workers=max_workers) as executor, \
                 tqdm(total=len(indices_to_run), desc="Processing LLM Sessions", ncols=80, file=sys.stderr) as pbar:
                
                tasks = {executor.submit(session_worker, i, run_specific_dir_path, responses_dir, llm_prompter_script, src_dir, args.verbose): i for i in indices_to_run}
                for future in as_completed(tasks):
                    completed_count += 1
                    index, success, log, duration = future.result()
                    total_elapsed_time += duration
                    if not success:
                        failed_sessions += 1
                        all_logs.append(log)
                    
                    avg_time = total_elapsed_time / completed_count
                    eta = avg_time * (len(indices_to_run) - completed_count)
                    pbar.update(1)
                    with open(api_times_log_path, "a", encoding='utf-8') as f:
                        f.write(f"Query_{index:03d}\t{duration:.2f}\t{total_elapsed_time:.2f}\t{eta:.2f}\n")
            
            if failed_sessions > 0:
                # Log the specific failures.
                for log_entry in all_logs:
                    if log_entry.strip() and "STAGE:" not in log_entry: # Avoid re-printing the header
                        logging.error(log_entry)
                
                # For NEW runs, a session failure is fatal to the entire replication.
                # For REPAIR/REPROCESS runs, we log the failure but continue gracefully.
                # The run will remain incomplete and can be re-repaired later.
                if not args.reprocess:
                    raise Exception(f"{failed_sessions}/{len(indices_to_run)} LLM session(s) failed. See logs for details.")
                else:
                    repair_had_failures = True
                    logging.warning(f"{failed_sessions}/{len(indices_to_run)} LLM session(s) failed to repair. The script will continue, but the run remains incomplete.")

        # Stage 3: Process LLM Responses
        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path]
        if args.verbose: cmd3.append("-v")
        output3 = run_script(cmd3, "3. Process LLM Responses", verbose=args.verbose)
        
        n_valid_str = (re.search(r"<<<PARSER_SUMMARY:(\d+):", output3) or ['0','0'])[1]
        
        # Stage 4: Analyze LLM Performance
        stage_title_4 = "4. Analyze LLM Performance"
        print(f"--- Running Stage: {stage_title_4} ---")
        
        # Sub-stage 4a: Core performance metrics
        print("   - Calculating core performance metrics...")
        cmd_analyze = [sys.executable, analyze_script, "--run_output_dir", run_specific_dir_path, "--num_valid_responses", n_valid_str]
        if args.verbose: cmd_analyze.append("--verbose")
        run_script(cmd_analyze, "4a. Core Performance Metrics", verbose=args.verbose)

        # Sub-stage 4b: Positional bias metrics
        print("   - Calculating positional bias metrics...")
        k_val = int(get_config_value(APP_CONFIG, 'Study', 'group_size', fallback_key='k_per_query', value_type=int, fallback=10))
        cmd_bias = [sys.executable, bias_script, run_specific_dir_path, "--k_value", str(k_val)]
        if args.verbose: cmd_bias.append("--verbose")
        run_script(cmd_bias, "4b. Positional Bias Metrics", verbose=args.verbose)

        # Stage 5: Generate Final Report
        cmd5 = [sys.executable, generate_report_script, "--run_output_dir", run_specific_dir_path, "--replication_num", str(args.replication_num), "--notes", args.notes]
        run_script(cmd5, "5. Generate Replication Report", verbose=args.verbose)

        # Stage 6: Create Replication Summary
        cmd6 = [sys.executable, summarize_script, run_specific_dir_path]
        run_script(cmd6, "6. Compile Replication Results", verbose=args.verbose)

        if not repair_had_failures:
            pipeline_status = "COMPLETED"

    except (KeyboardInterrupt, subprocess.CalledProcessError, Exception) as e:
        if isinstance(e, KeyboardInterrupt):
            pipeline_status = "INTERRUPTED BY USER"
        # Note: pipeline_status defaults to "FAILED"
        
        logging.error(f"\n\n{Fore.RED}--- PIPELINE {pipeline_status} ---{Fore.RESET}")

        if isinstance(e, subprocess.CalledProcessError):
            logging.error(e.stderr)
        else:
            logging.exception("An unexpected error occurred in the orchestrator.")

        # On any failure, attempt to generate a final report with the FAILED status.
        try:
            cmd_report = [sys.executable, generate_report_script, "--run_output_dir", run_specific_dir_path, "--replication_num", str(args.replication_num), "--notes", args.notes]
            run_script(cmd_report, "5. Generate Failure Report", verbose=args.verbose)
        except Exception as report_e:
            logging.error(f"Could not generate a failure report: {report_e}")
        
        # This block will now be handled by the finalization logic below.

    # --- Finalization: Update Report Status ---
    # This logic now runs on both success and failure, ensuring the report is always updated.
    latest_report_files = sorted(glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')))
    if latest_report_files:
        report_path = latest_report_files[-1]
        try:
            with open(report_path, 'r+', encoding='utf-8') as f:
                content = f.read()
                # Construct the full, correctly aligned replacement line.
                replacement_line = f"{'Final Status:':<24}{pipeline_status}"
                # Replace the entire placeholder line.
                content = re.sub(r"^Final Status:.*PENDING.*$", replacement_line, content, flags=re.MULTILINE)
                f.seek(0)
                f.write(content)
                f.truncate()
        except IOError as e:
            logging.error(f"Could not update final report {report_path}: {e}")

    if args.reprocess:
        final_status_msg = "REPAIRED" if pipeline_status == "COMPLETED" else "FAILED"
    else:
        final_status_msg = pipeline_status
    
    status_color = Fore.GREEN
    if final_status_msg not in ["COMPLETED", "REPAIRED"]:
        status_color = Fore.RED

    print(f"\n{status_color}Replication run finished. Final status: {final_status_msg}.{Fore.RESET}", file=sys.stderr)

    if final_status_msg not in ["COMPLETED", "REPAIRED"]:
        sys.exit(1)


if __name__ == "__main__":
    main()

# === End of src/replication_manager.py ===
