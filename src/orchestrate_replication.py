#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/orchestrate_experiment.py

"""
Orchestrates the execution of a single, complete replication of the experiment.

This script manages the four sequential stages required to run one replication,
from generating queries to analyzing the final results. It is called by the
`replication_manager.py` for each replication in a batch run.

When the `--quiet` flag is received from the manager, this script passes it down
to each of the four stage scripts it calls. This ensures that the console output
remains clean and high-level during a standard run, suppressing detailed logs
from the child processes.

A single replication consists of:
1.  **Stage 1: Build Queries**: Generates trial queries.
2.  **Stage 2: Run LLM Sessions**: Sends queries to the LLM.
3.  **Stage 3: Process LLM Responses**: Parses raw text into structured data.
4.  **Stage 4: Analyze Performance**: Calculates metrics and generates a report.

All artifacts for the replication are saved into a unique, descriptive directory.
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

# --- Setup ---
# Setup basic logging for the master script itself
logging.basicConfig(level=logging.INFO,
                    format='%(message)s')

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    # This fallback allows the script to be run from different locations
    # by ensuring the 'src' directory is in the Python path.
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    try:
        from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
    except ImportError as e:
        logging.error(f"FATAL: Could not import from config_loader.py even after path adjustment. Error: {e}")
        sys.exit(1)

def run_script(command, title, is_interactive=False, quiet=False):
    """
    Helper to run a script as a subprocess.
    In interactive mode, it lets the subprocess write directly to the console.
    In normal mode, it captures all output robustly for the report.
    """
    # Always print the high-level stage to the console, independent of logging.
    print(f"--- Running Stage: {title} ---")

    header = (
        f"\n\n{'='*80}\n"
        f"### STAGE: {title} ###\n"
        f"COMMAND: {' '.join(command)}\n"
        f"{'='*80}\n\n"
    )
    
    try:
        if is_interactive:
            # For the LLM runner stage, let it take over the console to show the spinner.
            # We will not capture its output for the final report to ensure the spinner works.
            if not quiet:
                logging.info("Running interactive stage, output will appear directly on console...")
            subprocess.run(
                command,
                check=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            return header + "[Interactive stage output was displayed on the console and not captured in this report.]\n"
        else:
            # For all other stages, use the most robust capture method.
            if not quiet:
                logging.info("Capturing all output for report...")
            result = subprocess.run(
                command,
                capture_output=True, # This captures both stdout and stderr
                check=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            captured_output = result.stdout + result.stderr
            
            lines = captured_output.splitlines()
            filtered_lines = [line for line in lines if "RuntimeWarning" not in line]
            filtered_output = "\n".join(filtered_lines)

            # The captured output is returned to be stored for the final report,
            # but it is no longer printed to the console during the run.
            return header + filtered_output

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Re-raise the exception to be handled by the main try...except block
        raise e

def generate_run_dir_name(model_name, temperature, num_iterations, k_per_query, personalities_db, replication_num):
    """
    Generates a descriptive, sanitized directory name from key experiment parameters.
    Example: run_20250608_134313_rep-01_claude-sonnet-4_tmp-0.20_personalities_db_01_sbj-04_trl-045
    """
    # 1. Format Timestamp (using underscore for consistency)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    # 2. Format LLM Model Name (e.g., "anthropic/claude-sonnet-4" -> "claude-sonnet-4")
    model_short = model_name.split('/')[-1] if model_name else "unknown_model"

    # 3. Format Temperature with "tmp-" prefix and 2 decimal places
    try:
        temp_str = f"tmp-{float(temperature):.2f}"
    except (ValueError, TypeError):
        # Fallback for non-numeric temperature values
        temp_str = "tmp-0.00"

    # 4. Format Personalities Database Filename (e.g., "personalities_db_01.txt" -> "personalities_db_01")
    db_base = os.path.splitext(os.path.basename(personalities_db))[0] if personalities_db else "unknown_db"
    
    # 5. Format Group Size (k) with "sbj-" prefix and zero-padding
    subjects_str = f"sbj-{k_per_query:02d}"
    
    # 6. Format Number of Trials (m) with "trl-" prefix and zero-padding
    trials_str = f"trl-{num_iterations:03d}"

    # 7. Format Replication Number with "rep-" prefix and zero-padding
    replication_str = f"rep-{replication_num:02d}"

    # 8. Assemble all parts in a more readable order
    parts = [
        "run",
        timestamp_str,
        replication_str,
        model_short,
        temp_str,
        db_base,
        subjects_str,
        trials_str,
    ]
    
    # 9. Sanitize and Join
    # Replace any potentially problematic characters in any part with an underscore
    sanitized_parts = [re.sub(r'[^a-zA-Z0-9_.-]', '_', part) for part in parts]
    
    return "_".join(sanitized_parts)


def main():
    # --- Argparse ---
    parser = argparse.ArgumentParser(
        description="Runs or re-processes the full personality matching pipeline.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # K and M are now read from config, so they are no longer CLI arguments.
    parser.add_argument("--notes", type=str, default="N/A",
                        help="Optional notes to include in the report header (for new runs).")
    
    parser.add_argument("--replication_num", type=int, default=1,
                        help="The replication number for this specific run (for new runs).")
    parser.add_argument("--base_seed", type=int, default=None,
                        help="The base random seed for personality selection (for new runs).")
    parser.add_argument("--qgen_base_seed", type=int, default=None,
                        help="The base random seed for shuffling (for new runs).")
    parser.add_argument("--quiet", action="store_true", 
                        help="Run all pipeline stages in quiet mode.")
    
    # New arguments for reprocessing mode
    parser.add_argument("--reprocess", action="store_true",
                        help="Skip query building and LLM calls; re-process existing responses.")
    parser.add_argument("--run_output_dir", type=str, default=None,
                        help="Path to a specific run output directory. Used for --reprocess mode.")
    
    args = parser.parse_args()
    
    # --- Load main study parameters from config.ini ---
    args.num_iterations = get_config_value(APP_CONFIG, 'Study', 'num_trials', fallback=100, value_type=int)
    args.k_per_query = get_config_value(APP_CONFIG, 'Study', 'group_size', fallback=10, value_type=int)


    # --- Configure Logging Level ---
    # The orchestrator's INFO logs are the primary progress indicators,
    # so we no longer change its own logging level based on the quiet flag.
    # The --quiet flag will be passed down to child scripts to control their verbosity.

    # --- Prepare for execution ---
    all_stage_outputs = []
    final_analysis_output = ""
    pipeline_status = "UNKNOWN"
    validation_status_report = "Validation checks did not run or were inconclusive."
    parsing_status_report = "N/A"

    # --- Determine Run Directory Path ---
    if args.reprocess:
        if not args.run_output_dir:
            logging.error("FATAL: --run_output_dir is required when using --reprocess mode.")
            sys.exit(1)
        if not os.path.isdir(args.run_output_dir):
            logging.error(f"FATAL: The specified run directory for reprocessing does not exist: {args.run_output_dir}")
            sys.exit(1)
        run_specific_dir_path = args.run_output_dir
        logging.info(f"--- REPROCESS MODE ACTIVATED for directory: {os.path.basename(run_specific_dir_path)} ---")
        
        # In reprocess mode, discover k and m from the directory name to ensure the report is accurate,
        # overriding any defaults that may have been loaded from config.ini.
        dir_basename = os.path.basename(run_specific_dir_path)
        k_match = re.search(r'_sbj-(\d+)', dir_basename)
        m_match = re.search(r'_trl-(\d+)', dir_basename)

        if k_match:
            discovered_k = int(k_match.group(1))
            if args.k_per_query != discovered_k:
                logging.info(f"Discovered k={discovered_k} from directory name, overriding default {args.k_per_query}.")
                args.k_per_query = discovered_k
        else:
            logging.warning("Could not discover 'k' (sbj-XX) from directory name during reprocess.")

        if m_match:
            discovered_m = int(m_match.group(1))
            if args.num_iterations != discovered_m:
                logging.info(f"Discovered m={discovered_m} from directory name, overriding default {args.num_iterations}.")
                args.num_iterations = discovered_m
        else:
            logging.warning("Could not discover 'm' (trl-XXX) from directory name during reprocess.")
            
    else:
        # --- Generate Descriptive Run Directory Name (Normal Mode) ---
        if not args.quiet:
            logging.info("Gathering parameters for descriptive run directory name...")
        model_name_raw = get_config_value(APP_CONFIG, 'LLM', 'model_name', fallback="unknown_model")
        temp_raw = get_config_value(APP_CONFIG, 'LLM', 'temperature', fallback=0.0, value_type=float)
        personalities_db_raw = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src', fallback="unknown_db.txt")
        
        run_dir_name = generate_run_dir_name(
            model_name=model_name_raw,
            temperature=temp_raw,
            num_iterations=args.num_iterations,
            k_per_query=args.k_per_query,
            personalities_db=personalities_db_raw,
            replication_num=args.replication_num
        )
        base_output_dir_cfg = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback="output")
        resolved_base_output_dir = os.path.join(PROJECT_ROOT, base_output_dir_cfg)
        run_specific_dir_path = os.path.join(resolved_base_output_dir, run_dir_name)
        os.makedirs(run_specific_dir_path, exist_ok=True)
        if not args.quiet:
            logging.info(f"Created unique output directory for this run: {run_specific_dir_path}")

        try:
            source_config_path = os.path.join(PROJECT_ROOT, 'config.ini')
            dest_config_path = os.path.join(run_specific_dir_path, 'config.ini.archived')
            shutil.copy2(source_config_path, dest_config_path)
            if not args.quiet:
                logging.info(f"Successfully archived config file to: {os.path.basename(dest_config_path)}")
        except FileNotFoundError:
            logging.error(f"FATAL: Could not find config.ini at '{source_config_path}' to archive it. Halting run.")
            sys.exit(1)
        except Exception as e:
            logging.error(f"FATAL: An unexpected error occurred while archiving config.ini. Error: {e}")
            sys.exit(1)


    # --- Define Script Paths ---
    src_dir = os.path.join(PROJECT_ROOT, 'src')
    build_script = os.path.join(src_dir, 'build_queries.py')
    run_sessions_script = os.path.join(src_dir, 'run_llm_sessions.py')
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_performance.py')

    try:
        if not args.reprocess:
            # Stage 1: Build Queries (passing the unique run directory)
            cmd1 = [sys.executable, build_script, "-m", str(args.num_iterations), "-k", str(args.k_per_query), "--mode", "new", "--quiet-worker", "--run_output_dir", run_specific_dir_path]
            if args.quiet: cmd1.append("--quiet")
            if args.base_seed is not None:
                cmd1.extend(["--base_seed", str(args.base_seed)])
            if args.qgen_base_seed is not None:
                cmd1.extend(["--qgen_base_seed", str(args.qgen_base_seed)])
            output1 = run_script(cmd1, "1. Build Queries", quiet=args.quiet)
            all_stage_outputs.append(output1)
            
            # Stage 2: Run LLM Sessions (passing the unique run directory)
            # We now always run this stage interactively to see progress,
            # but the script itself will be quiet or verbose based on the flag.
            cmd2 = [sys.executable, run_sessions_script, "--run_output_dir", run_specific_dir_path]
            if args.quiet:
                cmd2.append("--quiet")
            else:
                # Only add verbose flag if not in quiet mode
                cmd2.append("-v")
            output2 = run_script(cmd2, "2. Run LLM Sessions", is_interactive=True, quiet=args.quiet)
            all_stage_outputs.append(output2)
        else:
            logging.info("Skipping Stage 1 (Build Queries) and Stage 2 (Run LLM Sessions) due to --reprocess flag.")

        # Stage 3: Process Responses (passing the unique run directory)
        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd3.append("--quiet")
        output3 = run_script(cmd3, "3. Process LLM Responses", quiet=args.quiet)
        all_stage_outputs.append(output3)
        
        # Check for the parser summary in the output of stage 3
        parser_summary_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+)>>>", output3)
        if parser_summary_match:
            processed_count = parser_summary_match.group(1)
            total_count = parser_summary_match.group(2)
            parsing_status_report = f"{processed_count}/{total_count} responses parsed"

        # Stage 4: Analyze Performance (passing the unique run directory and --quiet)
        cmd4 = [sys.executable, analyze_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd4.append("--quiet")
        output4 = run_script(cmd4, "4. Analyze Performance", quiet=args.quiet)
        all_stage_outputs.append(output4)
        final_analysis_output = output4
        
        pipeline_status = "COMPLETED"

        # --- Check validation status from captured logs ---
        if "PROCESSOR VALIDATION FAILED" in output3:
            validation_status_report = "FAILED at Stage 3 (Process Responses)"
        elif "ANALYZER VALIDATION FAILED" in output4:
            validation_status_report = "FAILED at Stage 4 (Analyze Performance)"
        elif "PROCESSOR_VALIDATION_SUCCESS" in output3 and "ANALYZER_VALIDATION_SUCCESS" in output4:
            validation_status_report = "OK (All checks passed)"

    except KeyboardInterrupt:
        pipeline_status = "INTERRUPTED BY USER"
        logging.warning(f"\n\n--- {pipeline_status} ---")
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        pipeline_status = "FAILED"
        logging.error(f"\n\n--- {pipeline_status} ---")
        if hasattr(e, 'output') and e.output:
            error_text = e.stdout + "\n" + e.stderr if hasattr(e, 'stdout') else e.output
            all_stage_outputs.append(error_text)
    
    # --- Clean up old reports before creating a new one ---
    # This is crucial for reprocess mode to prevent duplicate entries in final compilations.
    logging.info(f"Searching for and removing old report files in {os.path.basename(run_specific_dir_path)}...")
    old_reports = glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt'))
    if old_reports:
        for report in old_reports:
            try:
                os.remove(report)
                logging.info(f"Removed old report: {os.path.basename(report)}")
            except OSError as e:
                logging.warning(f"Could not remove old report {os.path.basename(report)}: {e}")
    else:
        logging.info("No old reports found to remove.")

    # --- Write the Final Report (inside the new run-specific directory) ---
    timestamp_for_file = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_filename = f"replication_report_{timestamp_for_file}.txt"
    report_path = os.path.join(run_specific_dir_path, report_filename)

    with open(report_path, 'w', encoding='utf-8') as report_file:
        personalities_file = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src', 'N/A')
        
        if args.reprocess:
            # For reprocessing, the model name must be discovered from the run's artifacts
            # to ensure accuracy, as config.ini may have changed.
            llm_model = "Unknown (Reprocess)" # Default value
            query_json_path = os.path.join(run_specific_dir_path, 'session_queries', 'llm_query_001_full.json')
            try:
                with open(query_json_path, 'r', encoding='utf-8') as f:
                    query_data = json.load(f)
                    llm_model = query_data.get('model', 'Unknown (key not in JSON)')
                logging.info(f"Discovered model name for report: {llm_model}")
            except FileNotFoundError:
                logging.warning(f"Could not find '{os.path.basename(query_json_path)}' to determine model name. Report will show a fallback value.")
            except (json.JSONDecodeError, KeyError) as e:
                logging.warning(f"Error parsing model name from '{os.path.basename(query_json_path)}': {e}. Report will show a fallback value.")
        else:
            # For a new run, the model name comes from the current configuration.
            llm_model = get_config_value(APP_CONFIG, 'LLM', 'model_name', 'N/A')

        # Get the mapping strategy from the config to include in the report
        mapping_strategy = get_config_value(APP_CONFIG, 'Study', 'mapping_strategy', fallback='unknown')

        header = f"""
================================================================================
 REPLICATION RUN REPORT
================================================================================
Date:            {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Final Status:    {pipeline_status}
Run Directory:   {os.path.basename(run_specific_dir_path)}
Parsing Status:  {parsing_status_report}
Validation Status: {validation_status_report}
Report File:     {report_filename}

--- Run Parameters ---
Num Iterations (m): {args.num_iterations}
Items per Query (k): {args.k_per_query}
Mapping Strategy: {mapping_strategy}
Personalities Source: {personalities_file}
LLM Model:       {llm_model}
Run Notes:       {args.notes}
================================================================================
"""
        report_file.write(header)

        base_query_filename = get_config_value(APP_CONFIG, 'Filenames', 'base_query_src', 'base_query.txt')
        base_query_path = os.path.join(PROJECT_ROOT, 'data', base_query_filename)
        report_file.write("\n\n--- Base Query Prompt Used ---\n")
        try:
            with open(base_query_path, 'r', encoding='utf-8') as f_prompt:
                report_file.write(f_prompt.read())
        except FileNotFoundError:
            report_file.write(f"ERROR: Could not find base query file at {base_query_path}\n")
        report_file.write("\n-------------------------------\n")

        # --- Final Analysis Summary Section ---
        report_file.write("\n\n================================================================================\n")
        report_file.write("### OVERALL META-ANALYSIS RESULTS ###\n")
        report_file.write("================================================================================\n\n")

        if final_analysis_output:
            # Define all relevant tags
            summary_start_tag = "<<<ANALYSIS_SUMMARY_START>>>"
            json_start_tag = "<<<METRICS_JSON_START>>>"
            json_end_tag = "<<<METRICS_JSON_END>>>"

            # Find the positions of the summary and JSON blocks
            summary_start_index = final_analysis_output.find(summary_start_tag)
            json_start_index = final_analysis_output.find(json_start_tag)

            # --- Part A: Write the human-readable summary ONLY ---
            if summary_start_index != -1:
                # The summary text ends where the JSON block begins.
                # If the JSON block isn't found, take everything to the end.
                summary_end_index = json_start_index if json_start_index != -1 else len(final_analysis_output)
                
                # Extract the text ONLY between the summary start and the JSON start.
                analysis_summary_text = final_analysis_output[summary_start_index + len(summary_start_tag) : summary_end_index].strip()
                report_file.write(analysis_summary_text)
                report_file.write("\n")
            else:
                report_file.write("Could not find human-readable analysis summary section in the script output.\n")
                report_file.write("Full log from analysis stage is included below for debugging:\n\n")
                report_file.write(final_analysis_output)

            # --- Part B: Write the machine-readable JSON block ---
            if json_start_index != -1:
                json_end_index = final_analysis_output.find(json_end_tag, json_start_index)
                if json_end_index != -1:
                    # Extract the entire block, including the tags, and write it to the report.
                    json_block = final_analysis_output[json_start_index : json_end_index + len(json_end_tag)]
                    report_file.write("\n\n" + json_block + "\n")
                else:
                    report_file.write(f"\n\nWARNING: Found '{json_start_tag}' but not its corresponding end tag.\n")
            # Only show this warning if a summary was present but the JSON was not.
            elif summary_start_index != -1:
                report_file.write("\n\nWARNING: Machine-readable metrics JSON block was not found in the analyzer output.\n")
        else:
            report_file.write("Analysis stage did not complete successfully or was not run.\n")

        # If the run failed, append the full diagnostic log for debugging
        if pipeline_status != "COMPLETED":
            report_file.write("\n\n================================================================================\n")
            report_file.write("                  FULL DIAGNOSTIC LOG\n")
            report_file.write("================================================================================\n")
            report_file.write("".join(all_stage_outputs))
    
    # Use more specific terminology.
    logging.info(f"Replication run finished. Report saved in directory: {os.path.basename(run_specific_dir_path)}")


if __name__ == "__main__":
    main()

# === End of src/orchestrate_experiment.py ===