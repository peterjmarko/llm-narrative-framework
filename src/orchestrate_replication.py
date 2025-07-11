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
experimental run. It calls the various pipeline stages (build queries, run LLM,
process, analyze) in sequence as subprocesses.

It operates in two modes:
1.  **New Run Mode (default):**
    -   Creates a new, unique run directory.
    -   Archives the `config.ini` for reproducibility.
    -   Executes the full pipeline:
        -   Stage 1: `build_llm_queries.py`
        -   Stage 2: `run_llm_sessions.py`
        -   Stage 3: `process_llm_responses.py`
        -   Stage 4: `analyze_llm_performance.py`
2.  **Reprocess Mode (`--reprocess`):**
    -   Operates on an existing `run_output_dir`.
    -   Skips Stages 1 and 2 (query building and LLM interaction).
    -   Re-runs only Stage 3 (processing) and Stage 4 (analysis). This is
        useful for fixing bugs in the analysis code without re-running the
        expensive LLM calls.

Finally, it compiles all captured output from the subprocesses into a single,
comprehensive `replication_report.txt` within the run directory.

Usage (for a new run, typically called by experiment_manager.py):
    python src/orchestrate_replication.py --replication_num 1

Usage (for reprocessing an existing run):
    python src/orchestrate_replication.py --reprocess --run_output_dir /path/to/run_dir
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

    try:
        if not args.reprocess:
            cmd1 = [sys.executable, build_script, "--run_output_dir", run_specific_dir_path] # ADDED --run_output_dir
            if args.quiet: cmd1.append("--quiet")
            if args.base_seed: cmd1.extend(["--base_seed", str(args.base_seed)])
            if args.qgen_base_seed: cmd1.extend(["--qgen_base_seed", str(args.qgen_base_seed)])
            
            output1, return_code1, error_obj1 = run_script(cmd1, "1. Build Queries", quiet=args.quiet)
            all_stage_outputs.append(output1)
            if return_code1 != 0: raise error_obj1 # Propagate error if not clean exit
            
            cmd2 = [sys.executable, run_sessions_script, "--run_output_dir", run_specific_dir_path] # ADDED --run_output_dir
            if args.quiet: cmd2.append("--quiet")
            output2, return_code2, error_obj2 = run_script(cmd2, "2. Run LLM Sessions", quiet=args.quiet)
            all_stage_outputs.append(output2)
            if return_code2 != 0: raise error_obj2 # Propagate error if not clean exit

        else:
            logging.info("Skipping Stage 1 (Build Queries) and Stage 2 (Run LLM Sessions) due to --reprocess flag.")

        # Stage 3: Process LLM Responses
        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path] # Changed to named argument
        if args.quiet: cmd3.append("--quiet")
        
        output3, return_code3, error_obj3 = run_script(cmd3, "3. Process LLM Responses", quiet=args.quiet)
        all_stage_outputs.append(output3)

        stage3_successful = False
        if return_code3 == 0: # Process exited cleanly
            stage3_successful = True
        else: # Process exited with non-zero code
            # Check if this failure is tolerable (partial success)
            if "PROCESSOR_VALIDATION_SUCCESS" in output3: # Check the full captured output
                summary_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+):", output3)
                if summary_match:
                    processed_count = int(summary_match.group(1))
                    if processed_count > 0:
                        logging.warning(f"Stage 3 (Process LLM Responses) returned non-zero exit code, but successfully processed {processed_count} responses. Tolerating this partial success.")
                        stage3_successful = True # Mark as successful for pipeline continuation
                    else:
                        logging.error(f"Stage 3 (Process LLM Responses) returned non-zero exit code and processed 0 responses. This is a true failure.")
                        raise error_obj3 # Re-raise if no responses were processed
                else:
                    logging.error(f"Stage 3 (Process LLM Responses) returned non-zero exit code, but PARSER_SUMMARY is missing. This is a true failure.")
                    raise error_obj3 # Re-raise if PARSER_SUMMARY is missing
            else:
                logging.error(f"Stage 3 (Process LLM Responses) returned non-zero exit code and PROCESSOR_VALIDATION_SUCCESS is missing. This is a true failure.")
                raise error_obj3 # Re-raise if PROCESSOR_VALIDATION_SUCCESS is missing

        # Proceed to Stage 4 only if Stage 3 was successful (fully or tolerated)
        if stage3_successful:
            # --- NEW: Extract parser summary to pass to Stage 4 ---
            n_valid_responses = -1 # Default to -1 to indicate not found
            parser_summary_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+)", output3)
            if parser_summary_match:
                n_valid_responses = int(parser_summary_match.group(1))

            cmd4 = [sys.executable, analyze_script, "--run_output_dir", run_specific_dir_path]
            if args.quiet: cmd4.append("--quiet")
            # --- NEW: Pass the number of valid responses to the analyzer ---
            if n_valid_responses != -1:
                cmd4.extend(["--num_valid_responses", str(n_valid_responses)])

            output4, return_code4, error_obj4 = run_script(cmd4, "4. Analyze Performance", quiet=args.quiet)
            all_stage_outputs.append(output4)
            if return_code4 != 0: raise error_obj4 # Propagate error if not clean exit
            
            pipeline_status = "COMPLETED" # All stages completed (or tolerated)
        else:
            # This 'else' block should ideally not be reached if exceptions are raised correctly
            # The outer except block will catch the re-raised error_obj3
            pass

    except KeyboardInterrupt:
        pipeline_status = "INTERRUPTED BY USER"
        logging.warning(f"\n\n--- {pipeline_status} ---")
    except subprocess.CalledProcessError as e:
        pipeline_status = "FAILED"
        logging.error(f"\n\n--- {pipeline_status} ---")
        # e.full_log should be set by the modified run_script function
        if hasattr(e, 'full_log'):
            all_stage_outputs.append(e.full_log)
        else:
            # Fallback if full_log wasn't set (e.g., FileNotFoundError before run_script could set it)
            error_details = f"STDOUT: {e.stdout}\nSTDERR: {e.stderr}" if hasattr(e, 'stdout') else "No captured output."
            logging.error(f"Error object did not contain full_log. Details: {error_details}")
            all_stage_outputs.append(f"\n\n--- FAILED STAGE UNKNOWN ---\nError: {e}\nDetails:\n{error_details}\n")
    except Exception as e: # Catch any other unexpected errors
        pipeline_status = "FAILED"
        logging.error(f"\n\n--- UNEXPECTED ERROR ---")
        logging.error(f"Error: {e}")
        import traceback
        logging.error(traceback.format_exc())
        all_stage_outputs.append(f"\n\n--- UNEXPECTED ERROR ---\n{traceback.format_exc()}")
    
    for old_report in glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')):
        os.remove(old_report)

    report_filename = f"replication_report_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    report_path = os.path.join(run_specific_dir_path, report_filename)

    # Read base query prompt for inclusion in the report
    base_query_prompt_content = "--- Base query prompt file not found or could not be read. ---"
    try:
        # Try the new key 'base_query_template' first, then fall back to 'base_query_src' for compatibility.
        base_query_filename = get_config_value(APP_CONFIG, 'Filenames', 'base_query_template')
        if not base_query_filename:
            base_query_filename = get_config_value(APP_CONFIG, 'Filenames', 'base_query_src')

        if base_query_filename:
            # Construct the path relative to the project root, inside the 'data' directory.
            base_query_path = os.path.join(PROJECT_ROOT, "data", base_query_filename)
            if os.path.exists(base_query_path):
                with open(base_query_path, 'r', encoding='utf-8') as f:
                    base_query_prompt_content = f.read().strip()
            else:
                base_query_prompt_content = f"--- Base query prompt file '{base_query_filename}' specified in config but not found at '{base_query_path}'. ---"
        else:
            base_query_prompt_content = "--- Neither 'base_query_template' nor 'base_query_src' key found in config.ini [Filenames] section. ---"
    except Exception as e:
        base_query_prompt_content = f"--- Error processing base query prompt: {e} ---"

    # Extract the JSON block from the analyzer's output
    metrics_json_str = None
    metrics_data = {}
    if output4:
        match = re.search(r'<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>', output4, re.DOTALL)
        if match:
            metrics_json_str = match.group(1).strip()
            try:
                metrics_data = json.loads(metrics_json_str)
            except json.JSONDecodeError:
                logging.error("Failed to decode metrics JSON from analyzer.")
                metrics_data = {}

    # Centralized formatting of the analysis summary
    analysis_summary_text = ""
    if metrics_data:
        k_val = int(get_config_value(APP_CONFIG, 'Study', 'group_size', fallback_key='k_per_query', value_type=int, fallback=10))
        top_k_val = 3
        n_valid = metrics_data.get('n_valid_responses', 0)
        def format_metric(title, mean_key, p_key, chance_val, is_percent=False):
            mean_val = metrics_data.get(mean_key)
            p_val = metrics_data.get(p_key)
            if mean_val is None: return ""
            chance_str = f"{chance_val:.2%}" if is_percent else f"{chance_val:.4f}"
            mean_str = f"{mean_val:.2%}" if is_percent else f"{mean_val:.4f}"
            p_str = f"p = {p_val:.4g}" if p_val is not None else "p = N/A"
            return f"{title} (vs Chance={chance_str}):\n   Mean: {mean_str}, Wilcoxon p-value: {p_str}"

        summary_lines = ["\n\n================================================================================",
                         "### OVERALL META-ANALYSIS RESULTS ###",
                         "================================================================================"]
        stouffer_p = metrics_data.get("mwu_stouffer_p")
        fisher_p = metrics_data.get("mwu_fisher_p")
        if stouffer_p is not None:
             summary_lines.append(f"\n1. Combined Significance of Score Differentiation (N={n_valid}):")
             summary_lines.append(f"   Stouffer's Method: Combined p-value = {stouffer_p:.4g}")
             if fisher_p is not None:
                 summary_lines.append(f"   Fisher's Method: Combined p-value = {fisher_p:.4g}")

        summary_lines.append("\n" + format_metric("2. Overall Magnitude of Score Differentiation (MWU Effect Size 'r')", 'mean_effect_size_r', 'effect_size_r_p', 0.0))
        mrr_chance = (1.0 / k_val) * sum(1.0 / j for j in range(1, k_val + 1))
        summary_lines.append("\n" + format_metric("3. Overall Ranking Performance (MRR)", 'mean_mrr', 'mrr_p', mrr_chance))
        summary_lines.append("\n" + format_metric("4. Overall Ranking Performance (Top-1 Accuracy)", 'mean_top_1_acc', 'top_1_acc_p', 1.0/k_val, is_percent=True))
        summary_lines.append("\n" + format_metric(f"5. Overall Ranking Performance (Top-{top_k_val} Accuracy)", f'mean_top_{top_k_val}_acc', f'top_{top_k_val}_acc_p', float(top_k_val)/k_val, is_percent=True))
        
        bias_std = metrics_data.get('top1_pred_bias_std')
        score_diff = metrics_data.get('true_false_score_diff')
        if bias_std is not None or score_diff is not None:
            summary_lines.append(f"\n6. Bias and Other Metrics:")
            if bias_std is not None:
                summary_lines.append(f"   Top-1 Prediction Bias (StdDev of choice counts): {bias_std:.4f}")
            if score_diff is not None:
                summary_lines.append(f"   Mean Score Difference (Correct - Incorrect): {score_diff:.4f}")
        analysis_summary_text = "\n".join(summary_lines)

    with open(report_path, 'w', encoding='utf-8') as report_file:
        final_config_path = os.path.join(run_specific_dir_path, 'config.ini.archived')
        config = configparser.ConfigParser()
        config.read(final_config_path)

        def get_robust(section_keys, key_keys):
            for section in section_keys:
                for key in key_keys:
                    if config.has_option(section, key): return config.get(section, key)
            return 'N/A'
        
        report_title = "REPLICATION RUN REPORT"
        run_date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if args.reprocess:
            report_title = f"REPLICATION RUN REPORT ({datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
            dir_name = os.path.basename(run_specific_dir_path)
            match = re.search(r'run_(\d{8}_\d{6})', dir_name)
            if match:
                try:
                    original_dt = datetime.datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
                    run_date_str = original_dt.strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    run_date_str = "Unknown (could not parse from dirname)"
            else:
                run_date_str = "Unknown (not found in dirname)"

        parser_summary_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+):warnings=(\d+)>>>", output3)
        parsing_status_report = f"{parser_summary_match.group(1)}/{parser_summary_match.group(2)} responses parsed ({parser_summary_match.group(3)} warnings)" if parser_summary_match else "N/A"
        validation_status = "OK (All checks passed)" if "ANALYZER_VALIDATION_SUCCESS" in output4 else "Validation FAILED or was skipped"

        header = f"""
================================================================================
 {report_title.strip()}
================================================================================
Date:            {run_date_str}
Final Status:    {pipeline_status}
Run Directory:   {os.path.basename(run_specific_dir_path)}
Parsing Status:  {parsing_status_report}
Validation Status: {validation_status}
Report File:     {report_filename}

--- Run Parameters ---
Num Iterations (m): {get_robust(['Study'], ['num_iterations', 'num_trials'])}
Items per Query (k): {get_robust(['Study'], ['k_per_query', 'num_subjects', 'group_size'])}
Mapping Strategy: {get_robust(['Study'], ['mapping_strategy'])}
Personalities Source: {os.path.basename(get_robust(['General', 'Filenames'], ['personalities_db_path', 'personalities_src']))}
LLM Model:       {get_robust(['Model', 'LLM'], ['model_name', 'model'])}
Run Notes:       {args.notes}
================================================================================


--- Base Query Prompt Used ---
{base_query_prompt_content}
-------------------------------
"""
        report_file.write(header.strip())
        report_file.write(analysis_summary_text)

        # If the metrics data was successfully parsed into a dictionary,
        # write it back out as a nicely formatted JSON block.
        if metrics_data:
            report_file.write("\n\n\n<<<METRICS_JSON_START>>>\n")
            # Use json.dumps with indent=4 for pretty-printing
            pretty_json_str = json.dumps(metrics_data, indent=4)
            report_file.write(pretty_json_str)
            report_file.write("\n<<<METRICS_JSON_END>>>")
        elif metrics_json_str:
            # Fallback for debugging: if we have a string but couldn't parse it, write it as-is
            report_file.write("\n\n\n<<<METRICS_JSON_START>>>\n")
            report_file.write("--- WARNING: The following JSON block was unparseable ---\n")
            report_file.write(metrics_json_str)
            report_file.write("\n<<<METRICS_JSON_END>>>")

    logging.info(f"Replication run finished. Report saved in directory: {os.path.basename(run_specific_dir_path)}")


if __name__ == "__main__":
    main()

# === End of src/orchestrate_replication.py ===
