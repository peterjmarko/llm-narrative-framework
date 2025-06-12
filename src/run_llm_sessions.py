#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/run_llm_sessions.py

"""
LLM Session Runner (run_llm_sessions.py)

Purpose:
This script orchestrates the process of sending multiple pre-generated queries
to a Large Language Model (LLM). It finds query files within a specific run
directory and invokes the `llm_prompter.py` worker script for each one.

Workflow (when called by orchestrator):
1.  Receives the path to a unique run directory via the `--run_output_dir` argument.
2.  Locates the `session_queries` subdirectory inside the run directory.
3.  Creates a `session_responses` subdirectory inside the run directory.
4.  For each `llm_query_XXX.txt` file found, it invokes `llm_prompter.py`.
5.  Saves the LLM's text response to `llm_response_XXX.txt` and the full raw
    JSON response to `llm_response_XXX_full.json` inside the run-specific
    `session_responses` directory.

Input Files (within the provided `<run_output_dir>`):
- `<run_output_dir>/session_queries/llm_query_XXX.txt`
- `<run_output_dir>/session_queries/llm_query_XXX_full.json`

Output Files (within the provided `<run_output_dir>`):
- `<run_output_dir>/session_responses/llm_response_XXX.txt`
- `<run_output_dir>/session_responses/llm_response_XXX_full.json`
- `<run_output_dir>/session_responses/llm_response_XXX.error.txt`

Command-Line Usage (for orchestrated runs):
    python src/run_llm_sessions.py --run_output_dir <path_to_run_dir> [options]

Required Argument for Orchestrated Runs:
    --run_output_dir      The absolute path to the self-contained output
                          directory for this specific run.
"""

# === Start of src/run_llm_sessions.py ===

import argparse
import os
import sys
import glob
import logging
import subprocess 
import shutil 
import json
import time

# --- Import from config_loader ---
try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    # ... (Fallback import logic as you have it, defining dummy APP_CONFIG, etc.) ...
    print(f"FATAL: run_llm_sessions.py - Could not import config_loader.py for module-level setup.")
    class DummyConfig:
        def get(self, section, key, fallback=None): return fallback # Simplified dummy
    APP_CONFIG = DummyConfig()
    def get_config_value(cfg, section, key, fallback=None, value_type=str): return fallback
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


# --- Module-level constants ---
LLM_PROMPTER_SCRIPT_NAME = "llm_prompter.py" 

# Define these constants at module level using the imported APP_CONFIG.
# These are used by this script AND potentially by test scripts if they import them.
TEMP_INPUT_QUERY_FILE_BASENAME = get_config_value(APP_CONFIG, 'Filenames', 'llmprompter_temp_query_in', fallback="current_session_query.txt")
TEMP_OUTPUT_RESPONSE_FILE_BASENAME = get_config_value(APP_CONFIG, 'Filenames', 'llmprompter_temp_response_out', fallback="current_session_response.txt")
TEMP_OUTPUT_ERROR_FILE_BASENAME = get_config_value(APP_CONFIG, 'Filenames', 'llmprompter_temp_error_out', fallback="current_session_error.txt")

INITIAL_DEFAULT_LOG_LEVEL = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')
numeric_initial_log_level = getattr(logging, INITIAL_DEFAULT_LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(level=numeric_initial_log_level,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S', 
                    force=True) # force=True (Python 3.8+) allows reconfiguring
# The premature log message that was here has been removed.

def format_seconds_to_time_str(seconds: float) -> str:
    """Formats seconds into [HH:]MM:SS string, showing hours only if non-zero."""
    if seconds < 0:
        return "00:00"
    
    total_seconds = round(seconds)
    
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    
    if hours > 0:
        return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}"
    else:
        return f"{int(minutes):02d}:{int(secs):02d}"

def clear_response_files_for_fresh_run(response_dir, api_times_log_path):
    """Deletes old response, error, and log files from the response directory."""
    logging.info(f"Clearing previous response files in '{response_dir}' for a fresh run...")
    cleared_any_files = False
    
    # Delete response, error, and full JSON debug files
    for pattern in ["llm_response_*.txt", "llm_response_*.error.txt", "*_full.json"]:
        for filepath_to_delete in glob.glob(os.path.join(response_dir, pattern)):
            try:
                os.remove(filepath_to_delete)
                logging.info(f"  Deleted: {os.path.basename(filepath_to_delete)}")
                cleared_any_files = True
            except OSError as e:
                logging.warning(f"  Warning: Could not delete {filepath_to_delete}: {e}")
    
    # Delete API times log file
    if os.path.exists(api_times_log_path):
        try:
            os.remove(api_times_log_path)
            logging.info(f"  Deleted: {os.path.basename(api_times_log_path)}")
            cleared_any_files = True
        except OSError as e:
            logging.warning(f"  Warning: Could not delete API times log {api_times_log_path}: {e}")
            
    if not cleared_any_files:
        logging.info("  No previous response or log files found to clear.")

def main():
    # --- Fetch config-dependent defaults for argparse *inside* main ---
    default_log_level_main_cfg = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')

    parser = argparse.ArgumentParser(
        description="Orchestrates sending queries to LLM via a worker script.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # --- Arguments ---
    parser.add_argument("--start_index", type=int, default=1, help="The starting index for processing query files.")
    parser.add_argument("--end_index", type=int, default=None, help="The ending index for processing query files.")
    parser.add_argument("--indices", type=int, nargs='+', default=None, help="A specific list of indices to run, overriding start/end.")
    parser.add_argument("--continue-run", action="store_true", help="Resume a session, skipping queries that already have a response file.")
    parser.add_argument("--force-rerun", action="store_true", help="Force re-running a query, deleting any existing response or error file. Used for retrying failed sessions.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity level (-v for INFO, -vv for DEBUG). Propagates to worker.")
    parser.add_argument("--quiet", action="store_true", help="Suppress high-level progress messages and worker output.")
    parser.add_argument("--run_output_dir", required=True, help="The absolute path to the self-contained output directory for this specific run.")

    args = parser.parse_args()

    # --- Adjust Log Level ---
    if args.quiet:
        log_level_final_orch = "WARNING"
    elif args.verbose == 1:
        log_level_final_orch = "INFO"
    elif args.verbose >= 2:
        log_level_final_orch = "DEBUG"
    else:
        log_level_final_orch = default_log_level_main_cfg
    
    numeric_final_log_level = getattr(logging, log_level_final_orch.upper(), logging.INFO)
    logging.basicConfig(level=numeric_final_log_level,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        force=True) # Use force=True to robustly reconfigure the root logger
    logging.info(f"LLM Sessions log level set to: {log_level_final_orch}")

    # --- Path Resolution based on run_output_dir ---
    script_dir = os.path.dirname(os.path.abspath(__file__)) # src/
    llm_prompter_path = os.path.join(script_dir, LLM_PROMPTER_SCRIPT_NAME)
    if not os.path.exists(llm_prompter_path):
        logging.error(f"Worker script '{LLM_PROMPTER_SCRIPT_NAME}' not found at '{llm_prompter_path}'."); sys.exit(1)

    queries_subdir_cfg = get_config_value(APP_CONFIG, 'General', 'queries_subdir', fallback="session_queries")
    responses_subdir_cfg = get_config_value(APP_CONFIG, 'General', 'responses_subdir', fallback="session_responses")

    query_dir_abs = os.path.join(args.run_output_dir, queries_subdir_cfg)
    response_dir_abs = os.path.join(args.run_output_dir, responses_subdir_cfg)

    if not os.path.exists(query_dir_abs):
        logging.error(f"Query input directory '{query_dir_abs}' not found."); sys.exit(1)
    os.makedirs(response_dir_abs, exist_ok=True)
    
    api_times_log_filename_cfg = get_config_value(APP_CONFIG, 'Filenames', 'api_times_log', fallback="api_times.log")
    api_times_log_path_abs = os.path.join(args.run_output_dir, api_times_log_filename_cfg)

    if not args.quiet:
        logging.info(f"Reading queries from: {query_dir_abs}")
        logging.info(f"Writing responses to: {response_dir_abs}")
        logging.info(f"API timing log will be written to: {api_times_log_path_abs}")

    if not args.continue_run and not args.force_rerun:
        logging.info("--- Starting fresh run: Clearing all previous response files. ---")
        clear_response_files_for_fresh_run(response_dir_abs, api_times_log_path_abs)
        
        if api_times_log_path_abs:
            try:
                with open(api_times_log_path_abs, "w", encoding='utf-8') as f_times:
                    f_times.write("Query_ID\tCall_Duration_s\tTotal_Elapsed_s\tEstimated_Time_Remaining_s\n")
            except Exception as e_log:
                logging.warning(f"Could not write header to API times log {api_times_log_path_abs}: {e_log}")
    else:
        logging.info("--- CONTINUING previous session: Skipping existing results. ---")


    # --- Setup temporary directory for worker files ---
    temp_dir_path = os.path.join(script_dir, "temp")
    try:
        os.makedirs(temp_dir_path, exist_ok=True)
        for temp_file_basename in [TEMP_INPUT_QUERY_FILE_BASENAME, TEMP_OUTPUT_RESPONSE_FILE_BASENAME, TEMP_OUTPUT_ERROR_FILE_BASENAME]:
            stray_file = os.path.join(temp_dir_path, temp_file_basename)
            if os.path.exists(stray_file):
                os.remove(stray_file)
    except OSError as e:
        logging.error(f"Could not create or clean temporary directory at {temp_dir_path}: {e}")
        sys.exit(1)

    temp_query_path_abs = os.path.join(temp_dir_path, TEMP_INPUT_QUERY_FILE_BASENAME)
    temp_response_path_abs = os.path.join(temp_dir_path, TEMP_OUTPUT_RESPONSE_FILE_BASENAME)
    temp_error_path_abs = os.path.join(temp_dir_path, TEMP_OUTPUT_ERROR_FILE_BASENAME)


    query_files_pattern = os.path.join(query_dir_abs, "llm_query_[0-9][0-9][0-9].txt")
    all_query_files = sorted(glob.glob(query_files_pattern))
    if not all_query_files:
        logging.info(f"No query files matching '{query_files_pattern}' found in '{query_dir_abs}'. Nothing to do."); return

    # --- Filter which query files to process ---
    query_files_to_process = []
    if args.indices:
        logging.info(f"Targeting specific indices provided via --indices flag: {args.indices}")
        indices_set = set(args.indices)
        for qf in all_query_files:
            try:
                index_str = os.path.basename(qf).replace("llm_query_", "").replace(".txt", "")
                if int(index_str) in indices_set:
                    query_files_to_process.append(qf)
            except (ValueError, TypeError):
                continue
    else:
        # Fallback to original start/end index logic
        logging.info(f"Processing from index {args.start_index} up to {args.end_index if args.end_index is not None else 'last available'}.")
        for qf in all_query_files:
            try:
                index_str = os.path.basename(qf).replace("llm_query_", "").replace(".txt", "")
                current_index = int(index_str)
                if current_index >= args.start_index and (args.end_index is None or current_index <= args.end_index):
                    query_files_to_process.append(qf)
            except (ValueError, TypeError):
                continue

    if not query_files_to_process:
        logging.warning("After filtering, no query files remain to be processed.")
        return

    logging.info(f"Found {len(query_files_to_process)} query file(s) to process for this session.")
    
    successful_sessions = 0; failed_sessions = 0; skipped_sessions = 0
    total_elapsed_time = 0.0
    total_trials = len(query_files_to_process)

    try:
        for query_filepath_src in query_files_to_process:
            filename_src = os.path.basename(query_filepath_src)
            current_index = -1
            try:
                index_str = filename_src.replace("llm_query_", "").replace(".txt", "")
                if index_str.isdigit():
                    current_index = int(index_str)
                else:
                    logging.warning(f"Could not parse numeric index from filename '{filename_src}'. Skipping.")
                    continue
            except ValueError:
                logging.warning(f"Could not parse index from filename '{filename_src}'. Skipping.")
                continue

            if current_index < args.start_index: continue
            if args.end_index is not None and current_index > args.end_index:
                logging.info(f"Reached specified end_index {args.end_index}. Stopping query processing.")
                break

            if not args.quiet:
                logging.info(f"Orchestrating query: {filename_src} (Global Index: {current_index})")
            
            final_response_filename = f"llm_response_{current_index:03d}.txt"
            final_response_filepath_abs = os.path.join(response_dir_abs, final_response_filename)
            final_error_filename = f"llm_response_{current_index:03d}.error.txt"
            final_error_filepath_abs = os.path.join(response_dir_abs, final_error_filename)

            if args.force_rerun:
                logging.info(f"  --force-rerun enabled. Deleting existing output for index {current_index} before retry.")
                for file_to_remove in [final_response_filepath_abs, final_error_filepath_abs]:
                    if os.path.exists(file_to_remove):
                        try:
                            os.remove(file_to_remove)
                            logging.info(f"    Removed existing file: {os.path.basename(file_to_remove)}")
                        except OSError as e:
                            logging.warning(f"    Could not remove existing file {os.path.basename(file_to_remove)}: {e}")
            elif args.continue_run:
                if os.path.exists(final_response_filepath_abs):
                    logging.info(f"  Final response file '{os.path.basename(final_response_filepath_abs)}' already exists. Skipping.")
                    skipped_sessions += 1
                    continue
                if os.path.exists(final_error_filepath_abs):
                    logging.warning(f"  Final error file '{os.path.basename(final_error_filepath_abs)}' exists. Skipping.")
                    skipped_sessions += 1
                    continue

            try:
                shutil.copy2(query_filepath_src, temp_query_path_abs)
                logging.debug(f"  Prepared temp query file: {temp_query_path_abs}")
            except Exception as e_io:
                logging.error(f"  Error preparing temp query file for index {current_index}: {e_io}"); failed_sessions +=1
                with open(final_error_filepath_abs, 'w', encoding='utf-8') as f_err_orch: f_err_orch.write(f"Orchestrator failed to prepare input query file: {e_io}"); continue

            worker_cwd = os.path.dirname(llm_prompter_path)
            worker_cmd = [
                sys.executable, llm_prompter_path, f"{current_index:03d}",
                "--input_query_file", os.path.join("temp", TEMP_INPUT_QUERY_FILE_BASENAME),
                "--output_response_file", os.path.join("temp", TEMP_OUTPUT_RESPONSE_FILE_BASENAME),
                "--output_error_file", os.path.join("temp", TEMP_OUTPUT_ERROR_FILE_BASENAME)
            ]
            
            # --- MODIFICATION START ---
            # Propagate quiet flag correctly. It takes precedence over verbose.
            if args.quiet:
                worker_cmd.append("--quiet")
            elif args.verbose >= 2:
                worker_cmd.append("-vv")
            elif args.verbose == 1:
                worker_cmd.append("-v")
            # --- MODIFICATION END ---

            logging.debug(f"  Worker command: {' '.join(worker_cmd)}")
            
            try:
                start_time = time.time()
                # The worker's stdout now contains JSON, and stderr has the spinner/logs.
                # We need to capture both as UTF-8.
                # stderr is set to None so worker's stderr (including spinner) prints to console.
                # stdout is captured as it contains the JSON data.
                process_worker = subprocess.run(
                    worker_cmd, check=False, cwd=worker_cwd,
                    stdout=subprocess.PIPE, stderr=None,
                    text=True, encoding='utf-8', errors='replace'
                )
                call_duration = time.time() - start_time
                
                temp_worker_response_path = temp_response_path_abs
                temp_worker_error_path = temp_error_path_abs

                if process_worker.returncode == 0 and os.path.exists(temp_worker_response_path):
                    shutil.move(temp_worker_response_path, final_response_filepath_abs)
                    successful_sessions += 1
                    
                    total_elapsed_time += call_duration
                    average_time_per_trial = total_elapsed_time / successful_sessions
                    remaining_trials = total_trials - (successful_sessions + failed_sessions + skipped_sessions)
                    estimated_time_remaining = remaining_trials * average_time_per_trial

                    # Always write the full timing data to the log file.
                    if api_times_log_path_abs:
                        try:
                            with open(api_times_log_path_abs, "a", encoding='utf-8') as f_times:
                                f_times.write(f"QueryIdentifier_{current_index:03d}\t{call_duration:.2f}\t{total_elapsed_time:.2f}\t{estimated_time_remaining:.2f}\n")
                        except Exception as e_log:
                            logging.warning(f"Could not write to API times log {api_times_log_path_abs}: {e_log}")

                    # Conditionally log the status to the console.
                    if args.quiet:
                        # Format times into MM:SS or HH:MM:SS format.
                        formatted_duration = format_seconds_to_time_str(call_duration)
                        formatted_elapsed = format_seconds_to_time_str(total_elapsed_time)
                        formatted_remaining = format_seconds_to_time_str(estimated_time_remaining)
                        
                        # Use a simple print with carriage return to create a single, updating status line.
                        status_line = (f"Trial {current_index:03d}/{total_trials}: Completed "
                                       f"(Duration: {formatted_duration}, Elapsed: {formatted_elapsed}, "
                                       f"Remaining: {formatted_remaining})      ")
                        print(status_line, end="\r", flush=True)
                    else:
                        # Use the detailed logger for verbose mode.
                        logging.info(f"  LLM session for index {current_index} successful. Duration: {call_duration:.2f}s. ETR: {estimated_time_remaining:.2f}s.")

                    worker_stdout = process_worker.stdout
                    try:
                        json_start_tag = "---LLM_RESPONSE_JSON_START---"
                        json_end_tag = "---LLM_RESPONSE_JSON_END---"
                        start_idx = worker_stdout.find(json_start_tag)
                        end_idx = worker_stdout.find(json_end_tag)
                        
                        if start_idx != -1 and end_idx != -1:
                            json_str = worker_stdout[start_idx + len(json_start_tag):end_idx].strip()
                            json_data = json.loads(json_str)
                            
                            debug_json_filename = os.path.splitext(final_response_filepath_abs)[0] + "_full.json"
                            with open(debug_json_filename, 'w', encoding='utf-8') as f_debug:
                                json.dump(json_data, f_debug, indent=2, ensure_ascii=False)
                            if not args.quiet:
                                logging.info(f"  Saved full JSON debug data to '{os.path.basename(debug_json_filename)}'.")
                        else:
                            logging.warning(f"  Could not find JSON delimiters in worker stdout for index {current_index}.")
                            # Also log the stderr from the worker to see if it provides clues.
                            if process_worker.stderr:
                                logging.warning(f"  Worker stderr for index {current_index}:\n---\n{process_worker.stderr}\n---")
                    except Exception as e_json:
                        logging.warning(f"  Could not extract or save full JSON from worker stdout: {e_json}")

                else:
                    failed_sessions += 1
                    logging.error(f"  Worker script failed for query index {current_index} (exit code {process_worker.returncode}). Duration: {call_duration:.2f}s.")
                    if os.path.exists(temp_worker_error_path):
                        shutil.move(temp_worker_error_path, final_error_filepath_abs)
                        logging.info(f"  Moved worker error file to '{os.path.basename(final_error_filepath_abs)}'.")
                    else:
                        with open(final_error_filepath_abs, 'w', encoding='utf-8') as f_err_orch:
                            f_err_orch.write(f"Orchestrator noted worker script failed with exit code: {process_worker.returncode}.\n\n")
                            if process_worker.stdout:
                                f_err_orch.write(f"WORKER STDOUT:\n{process_worker.stdout}\n\n")
                            if process_worker.stderr:
                                f_err_orch.write(f"WORKER STDERR:\n{process_worker.stderr}\n")
                        logging.info(f"  Created orchestrator error file: '{os.path.basename(final_error_filepath_abs)}'.")

            except Exception as e_subproc: 
                failed_sessions += 1
                logging.exception(f"  Orchestrator failed to execute/manage worker for query index {current_index}: {e_subproc}")
                with open(final_error_filepath_abs, 'w', encoding='utf-8') as f_err: f_err.write(f"Orchestrator error managing worker: {e_subproc}")
            finally:
                if os.path.exists(temp_query_path_abs):
                    try: os.remove(temp_query_path_abs)
                    except OSError: logging.warning(f"Could not remove temp query input file {temp_query_path_abs}")
                for temp_fn_suffix in [TEMP_OUTPUT_RESPONSE_FILE_BASENAME, TEMP_OUTPUT_ERROR_FILE_BASENAME]:
                    stray_temp_f_path = os.path.join(temp_dir_path, temp_fn_suffix)
                    if os.path.exists(stray_temp_f_path):
                        logging.warning(f"Stray temporary worker file found and removed: {os.path.basename(stray_temp_f_path)}");
                        try: os.remove(stray_temp_f_path)
                        except OSError: pass
    
    except KeyboardInterrupt:
        logging.info("\nOrchestration interrupted by user (Ctrl+C).")
    finally:
        # The orchestrator is now responsible for printing the final newline.
        # This script must not print a newline, so the orchestrator can overwrite its last status message.
        total_processed_this_run = successful_sessions + failed_sessions
        logging.info("\nLLM session orchestration complete or terminated.")
        logging.info(f"Summary for this run: {successful_sessions} sessions got responses, {failed_sessions} resulted in errors. {skipped_sessions} were skipped (pre-existing).")

if __name__ == "__main__":
    main()

# === End of src/run_llm_sessions.py ===