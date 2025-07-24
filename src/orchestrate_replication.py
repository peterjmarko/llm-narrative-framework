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
experimental replication. It is called by `experiment_manager.py`.

It operates in two primary modes:

1.  **New Run Mode (default):**
    -   Creates a new, timestamped directory for the replication's artifacts.
    -   Executes a consolidated six-stage pipeline:
        1.  **Build LLM Queries**: Generates queries and trial data.
        2.  **Run LLM Sessions**: Interacts with the LLM API in parallel.
        3.  **Process LLM Responses**: Parses raw responses into structured scores.
        4.  **Analyze LLM Performance**: Calculates core and bias metrics, outputting
            only a `replication_metrics.json` file.
        5.  **Generate Final Report**: Assembles the final `replication_report.txt`
            by combining data from the `experiment_manifest.json` (for parameters)
            and the `replication_metrics.json` (for results).
        6.  **Create Replication Summary**: Creates the `REPLICATION_results.csv`.

2.  **Reprocess Mode (`--reprocess`):**
    -   Operates on an existing replication directory.
    -   Skips query generation and LLM interaction (Stages 1 & 2).
    -   Re-runs only the data processing and analysis pipeline (Stages 3-6) to
        apply logic updates or bug fixes to existing data.

This script is the single source of truth for generating the final replication
report, ensuring consistency across all run types.
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
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

# --- Setup ---
try:
    from config_loader import APP_CONFIG, get_config_value, get_config_list, PROJECT_ROOT
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

def _create_replication_summary_csv(run_dir_path, manifest_params, metrics_data):
    """Creates the REPLICATION_results.csv file for a single run."""
    run_dir_name = os.path.basename(run_dir_path)
    rep_match = re.search(r'rep-(\d+)', run_dir_name)
    
    # Combine all data into a single record
    run_data = {'run_directory': run_dir_name}
    run_data.update(manifest_params)
    run_data.update(metrics_data)
    run_data['replication'] = int(rep_match.group(1)) if rep_match else 0
    
    # Rename keys to match the CSV schema
    run_data['model'] = run_data.pop('model_name', None)
    run_data['k'] = run_data.pop('group_size', None)
    run_data['m'] = run_data.pop('num_trials', None)
    
    # Write to CSV using pandas to ensure correct header order
    output_path = os.path.join(run_dir_path, "REPLICATION_results.csv")
    fieldnames = get_config_list(APP_CONFIG, 'Schema', 'csv_header_order')
    df = pd.DataFrame([run_data])
    
    for col in fieldnames:
        if col not in df.columns:
            df[col] = pd.NA
            
    df = df[fieldnames]
    df.to_csv(output_path, index=False)

def _build_human_readable_summary(metrics, params):
    """Builds the human-readable summary section from final metrics."""
    k = params.get('group_size', 0)
    m = params.get('num_trials', 0)
    top_k_val = get_config_value(APP_CONFIG, 'Analysis', 'top_k_value_for_accuracy', 3)
    top_k_acc_key = f"mean_top_{top_k_val}_acc"

    # Helper to safely format a metric value, returning "N/A" if it's not a number.
    def f(key, fmt):
        val = metrics.get(key)
        return fmt.format(val) if isinstance(val, (int, float)) else "N/A"

    # Pre-calculate chance levels to avoid division by zero
    chance_mrr = (1/k * sum(1/i for i in range(1, k + 1))) if k > 0 else 0
    chance_top1 = 1/k if k > 0 else 0
    chance_topk = min(top_k_val, k) / k if k > 0 else 0

    summary = f"""
================================================================================
### OVERALL META-ANALYSIS RESULTS ###
================================================================================

1. Combined Significance of Score Differentiation (N={m}):
   Stouffer's Method: Combined p-value = {f('mwu_stouffer_p', '{:.4f}')}
   Fisher's Method: Combined p-value = {f('mwu_fisher_p', '{:.4f}')}

2. Overall Magnitude of Score Differentiation (MWU Effect Size 'r') (vs Chance=0.0000):
   Mean: {f('mean_effect_size_r', '{:.4f}')}, Wilcoxon p-value: p = {f('effect_size_r_p', '{:.3f}')}

3. Overall Ranking Performance (MRR) (vs Chance={chance_mrr:.4f}):
   Mean: {f('mean_mrr', '{:.4f}')}, Wilcoxon p-value: p = {f('mrr_p', '{:.4f}')}

4. Overall Ranking Performance (Top-1 Accuracy) (vs Chance={chance_top1:.2%}):
   Mean: {f('mean_top_1_acc', '{:.2%}')}, Wilcoxon p-value: p = {f('top_1_acc_p', '{:.4f}')}

5. Overall Ranking Performance (Top-{top_k_val} Accuracy) (vs Chance={chance_topk:.2%}):
   Mean: {f(top_k_acc_key, '{:.2%}')}, Wilcoxon p-value: p = {f(top_k_acc_key + '_p', '{:.4f}')}

6. Bias and Other Metrics:
   Top-1 Prediction Bias (StdDev of choice counts): {f('top1_pred_bias_std', '{:.4f}')}
   Mean Score Difference (Correct - Incorrect): {f('true_false_score_diff', '{:.4f}')}
"""
    return summary.lstrip()


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
    output3, output4 = "", ""

    if args.reprocess:
        if not args.run_output_dir or not os.path.isdir(args.run_output_dir):
            logging.error("FATAL: --run_output_dir must be a valid directory in --reprocess mode.")
            sys.exit(1)
        run_specific_dir_path = args.run_output_dir
        logging.info(f"--- REPROCESS MODE for: {os.path.basename(run_specific_dir_path)} ---")
        
        # Manifest is in the experiment's root (parent of the run directory)
        manifest_path = os.path.join(os.path.dirname(run_specific_dir_path), 'experiment_manifest.json')
        if not os.path.exists(manifest_path):
            logging.error(f"FATAL: Experiment manifest not found at {manifest_path}. Cannot reprocess.")
            sys.exit(1)
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        params = manifest.get('parameters', {})
        
        args.num_iterations = params.get('num_trials', 100)
        args.k_per_query = params.get('group_size', 10)
    else:
        # For a new run, read parameters from the experiment's manifest.
        base_output_dir = args.base_output_dir
        manifest_path = os.path.join(base_output_dir, 'experiment_manifest.json')
        if not os.path.exists(manifest_path):
            logging.error(f"FATAL: Experiment manifest not found at {manifest_path}. Cannot create new replication.")
            sys.exit(1)

        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        params = manifest['parameters']

        # Use parameters from manifest to build run directory name and for pipeline stages
        model_name = params['model_name']
        temp = params['temperature']
        args.k_per_query = params['group_size']
        args.num_iterations = params['num_trials']
        
        # The db_file part of the name is now for provenance, so we can use a placeholder.
        run_dir_name = generate_run_dir_name(model_name, temp, args.num_iterations, args.k_per_query, "db", args.replication_num)
        
        run_specific_dir_path = os.path.join(base_output_dir, run_dir_name)
        os.makedirs(run_specific_dir_path, exist_ok=True)
        logging.info(f"Created unique output directory: {run_specific_dir_path}")

    src_dir = os.path.join(PROJECT_ROOT, 'src')
    build_script = os.path.join(src_dir, 'build_llm_queries.py')
    run_sessions_script = os.path.join(src_dir, 'run_llm_sessions.py')
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_llm_performance.py')
    bias_script = os.path.join(src_dir, 'run_bias_analysis.py')
    aggregator_script = os.path.join(src_dir, 'aggregate_experiments.py')

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
        stage_title_2 = "2. Run LLM Sessions"
        header_2 = (f"\n\n{'='*80}\n### STAGE: {stage_title_2} ###\n{'='*80}\n\n")

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
            all_stage_outputs.append(header_2 + "All required LLM response files already exist. Nothing to do.")
        else:
            print(f"--- Running Stage: {stage_title_2} ---")
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

            all_logs = [header_2]
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

        # Stage 3: Process LLM Responses
        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd3.append("--quiet")
        output3, rc3, err3 = run_script(cmd3, "3. Process LLM Responses", quiet=args.quiet)
        all_stage_outputs.append(output3)
        if rc3 != 0: raise err3
        
        n_valid_str = (re.search(r"<<<PARSER_SUMMARY:(\d+):", output3) or ['0','0'])[1]
        
        # Stage 4: Analyze LLM Performance
        stage_title_4 = "4. Analyze LLM Performance"
        print(f"--- Running Stage: {stage_title_4} ---")
        header_4 = (f"\n\n{'='*80}\n### STAGE: {stage_title_4} ###\n{'='*80}\n\n")
        all_stage_outputs.append(header_4)
        
        # Sub-stage 4a: Core performance metrics
        print("   - Calculating core performance metrics...")
        cmd_analyze = [sys.executable, analyze_script, "--run_output_dir", run_specific_dir_path, "--num_valid_responses", n_valid_str]
        if args.quiet: cmd_analyze.append("--quiet")
        # Run subprocess directly to manage console output
        result4 = subprocess.run(cmd_analyze, capture_output=True, check=False, text=True, encoding='utf-8', errors='replace')
        output4 = result4.stdout # Keep stdout for report generation
        all_stage_outputs.append("\n--- Sub-stage: Core Performance Metrics ---\n" + output4 + result4.stderr)
        if result4.returncode != 0:
            raise subprocess.CalledProcessError(result4.returncode, cmd_analyze, output=result4.stdout, stderr=result4.stderr)

        # Sub-stage 4b: Positional bias metrics
        print("   - Calculating positional bias metrics...")
        k_val = args.k_per_query
        cmd_bias = [sys.executable, bias_script, run_specific_dir_path, "--k_value", str(k_val)]
        if not args.quiet: cmd_bias.append("--verbose")
        result5 = subprocess.run(cmd_bias, capture_output=True, check=False, text=True, encoding='utf-8', errors='replace')
        all_stage_outputs.append("\n--- Sub-stage: Positional Bias Metrics ---\n" + result5.stdout + result5.stderr)
        if result5.returncode != 0:
            raise subprocess.CalledProcessError(result5.returncode, cmd_bias, output=result5.stdout, stderr=result5.stderr)

        # Stage 5 is now just data gathering. The report is assembled at the end.
        human_readable_analysis = output4.split("<<<METRICS_JSON_START>>>")[0]
        with open(os.path.join(run_specific_dir_path, 'analysis_inputs', 'replication_metrics.json'), 'r', encoding='utf-8') as f:
            updated_metrics = json.load(f)

        # Stage 6: Create Replication Summary
        stage_title_6 = "6. Create Replication Summary"
        print(f"--- Running Stage: {stage_title_6} ---")
        try:
            manifest_path = os.path.join(os.path.dirname(run_specific_dir_path), 'experiment_manifest.json')
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            _create_replication_summary_csv(run_specific_dir_path, manifest['parameters'], updated_metrics)
            all_stage_outputs.append(f"\n--- STAGE {stage_title_6} SUCCEEDED ---")
        except Exception as e:
            logging.error(f"Failed during Stage 6 (Replication Summary): {e}")
            raise

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

    # --- Finalization: Assemble and Write Final Report ---
    for old_report in glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')):
        os.remove(old_report)
    
    report_timestamp = datetime.datetime.now()
    report_filename = f"replication_report_{report_timestamp.strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    report_path = os.path.join(run_specific_dir_path, report_filename)
    
    # --- Gather Data for Report ---
    run_dir_name = os.path.basename(run_specific_dir_path)
    manifest_path = os.path.join(os.path.dirname(run_specific_dir_path), 'experiment_manifest.json')
    with open(manifest_path, 'r') as f:
        manifest = json.load(f)
    params = manifest['parameters']
    
    original_run_dt = None
    time_match = re.search(r'run_(\d{8}_\d{6})', run_dir_name)
    if time_match:
        try:
            original_run_dt = datetime.datetime.strptime(time_match.group(1), '%Y%m%d_%H%M%S')
        except ValueError:
            pass
    
    # --- Build Report Content ---
    report_title = "REPLICATION RUN REPORT"
    if args.reprocess:
        report_title += f" (Reprocessed: {report_timestamp.strftime('%Y-%m-%d %H:%M:%S')})"

    parsing_summary_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+)>>>", output3)
    parsing_status_str = f"{parsing_summary_match.group(1)}/{parsing_summary_match.group(2)} responses parsed" if parsing_summary_match else "N/A"
    replication_num_str = str(int(re.search(r'rep-(\d+)', run_dir_name).group(1)))

    header_content = f"""
================================================================================
 {report_title}
================================================================================
Date:            {original_run_dt.strftime('%Y-%m-%d %H:%M:%S') if original_run_dt else 'N/A'}
Final Status:    {pipeline_status}
Replication Number: {replication_num_str}
Run Directory:   {run_dir_name}
Parsing Status:  {parsing_status_str}
Report File:     {report_filename}
""".lstrip()

    base_query_filename = get_config_value(APP_CONFIG, 'Filenames', 'base_query_src')
    base_query_path = os.path.join(PROJECT_ROOT, base_query_filename) # Corrected path
    try:
        with open(base_query_path, 'r', encoding='utf-8') as f:
            base_query_content = f.read()
    except FileNotFoundError:
        base_query_content = "--- BASE QUERY NOT FOUND ---"

    params_content = f"""
--- Run Parameters ---
Num Iterations (m): {params.get('num_trials', 'N/A')}
Items per Query (k): {params.get('group_size', 'N/A')}
Mapping Strategy: {params.get('mapping_strategy', 'N/A')}
Personalities Source: {params.get('db', 'N/A')}
LLM Model:       {params.get('model_name', 'N/A')}
Run Notes:       {args.notes}
================================================================================


--- Base Query Prompt Used ---
{base_query_content.strip()}
-------------------------------
""".rstrip()

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(header_content)
            f.write("\n" + params_content)
            
            if 'updated_metrics' in locals():
                human_readable_summary = _build_human_readable_summary(updated_metrics, params)
                f.write(human_readable_summary)
                f.write("\n\n<<<METRICS_JSON_START>>>\n")
                f.write(json.dumps(updated_metrics, indent=4))
                f.write("\n<<<METRICS_JSON_END>>>")
            else:
                f.write("\n\n--- PIPELINE FAILED: LOGS ---\n")
                f.write("".join(all_stage_outputs))
    except IOError as e:
        logging.error(f"FATAL: Could not write final report to {report_path}: {e}")


if __name__ == "__main__":
    main()

# === End of src/orchestrate_replication.py ===
