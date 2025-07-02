#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        -   Stage 1: `build_queries.py`
        -   Stage 2: `run_llm_sessions.py`
        -   Stage 3: `process_llm_responses.py`
        -   Stage 4: `analyze_performance.py`
2.  **Reprocess Mode (`--reprocess`):**
    -   Operates on an existing `run_output_dir`.
    -   Skips Stages 1 and 2 (query building and LLM interaction).
    -   Re-runs only Stage 3 (processing) and Stage 4 (analysis). This is
        useful for fixing bugs in the analysis code without re-running the
        expensive LLM calls.

Finally, it compiles all captured output from the subprocesses into a single,
comprehensive `replication_report.txt` within the run directory.

Usage (for a new run, typically called by replication_manager.py):
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
logging.basicConfig(level=logging.INFO, format='%(message)s')

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path:
        sys.path.insert(0, current_script_dir)
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT

def run_script(command, title, quiet=False):
    """Helper to run a script as a subprocess and capture its output."""
    print(f"--- Running Stage: {title} ---")
    header = (
        f"\n\n{'='*80}\n"
        f"### STAGE: {title} ###\n"
        f"COMMAND: {' '.join(command)}\n"
        f"{'='*80}\n\n"
    )
    try:
        # For Stage 2, let stderr pass through for the spinner. For all other stages, capture it.
        if title == "2. Run LLM Sessions":
            result = subprocess.run(
                command, stdout=subprocess.PIPE, stderr=None, check=True,
                text=True, encoding='utf-8', errors='replace'
            )
            captured_output = result.stdout
        else:
            result = subprocess.run(
                command, capture_output=True, check=True,
                text=True, encoding='utf-8', errors='replace'
            )
            captured_output = result.stdout + result.stderr

        lines = captured_output.splitlines()
        filtered_lines = [line for line in lines if "RuntimeWarning" not in line and "UserWarning" not in line]
        filtered_output = "\n".join(filtered_lines)

        if not quiet and title != "2. Run LLM Sessions":
            # Don't re-print output for Stage 2, as it has no meaningful stdout.
            print(filtered_output)
            
        return header + filtered_output

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # Error details will now appear on the console in real-time for Stage 2.
        # For other stages, they are captured and logged here.
        error_details = "See console for real-time error from this stage."
        if hasattr(e, 'stdout') and e.stdout:
            error_details = f"STDOUT: {e.stdout}"
        if hasattr(e, 'stderr') and e.stderr:
            error_details += f"\nSTDERR: {e.stderr}"
        
        error_message = (
            f"\n\n--- FAILED STAGE: {title} ---\n"
            f"Error: {e}\n"
            f"Details:\n{error_details}\n"
        )
        e.full_log = header + error_message
        raise e

def generate_run_dir_name(model_name, temperature, num_iterations, k_per_query, personalities_db, replication_num):
    """Generates a descriptive, sanitized directory name."""
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    model_short = model_name.split('/')[-1] if model_name else "unknown_model"
    temp_str = f"tmp-{float(temperature):.2f}"
    db_base = os.path.splitext(os.path.basename(personalities_db))[0]
    subjects_str = f"sbj-{k_per_query:02d}"
    trials_str = f"trl-{num_iterations:03d}"
    replication_str = f"rep-{replication_num:02d}"
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
    pipeline_status = "UNKNOWN"
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
    build_script = os.path.join(src_dir, 'build_queries.py')
    run_sessions_script = os.path.join(src_dir, 'run_llm_sessions.py')
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_performance.py')

    try:
        if not args.reprocess:
            cmd1 = [sys.executable, build_script, "--run_output_dir", run_specific_dir_path]
            if args.quiet: cmd1.append("--quiet")
            if args.base_seed: cmd1.extend(["--base_seed", str(args.base_seed)])
            if args.qgen_base_seed: cmd1.extend(["--qgen_base_seed", str(args.qgen_base_seed)])
            all_stage_outputs.append(run_script(cmd1, "1. Build Queries", quiet=args.quiet))
            
            cmd2 = [sys.executable, run_sessions_script, "--run_output_dir", run_specific_dir_path]
            if args.quiet: cmd2.append("--quiet")
            all_stage_outputs.append(run_script(cmd2, "2. Run LLM Sessions", quiet=args.quiet))
        else:
            logging.info("Skipping Stage 1 (Build Queries) and Stage 2 (Run LLM Sessions) due to --reprocess flag.")

        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd3.append("--quiet")
        output3 = run_script(cmd3, "3. Process LLM Responses", quiet=args.quiet)
        all_stage_outputs.append(output3)
        
        cmd4 = [sys.executable, analyze_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd4.append("--quiet")
        output4 = run_script(cmd4, "4. Analyze Performance", quiet=args.quiet)
        all_stage_outputs.append(output4)
        
        pipeline_status = "COMPLETED"
    except KeyboardInterrupt:
        pipeline_status = "INTERRUPTED BY USER"
        logging.warning(f"\n\n--- {pipeline_status} ---")
    except subprocess.CalledProcessError as e:
        pipeline_status = "FAILED"
        logging.error(f"\n\n--- {pipeline_status} ---")
        all_stage_outputs.append(e.full_log)
    
    for old_report in glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')):
        os.remove(old_report)

    report_filename = f"replication_report_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
    report_path = os.path.join(run_specific_dir_path, report_filename)

    with open(report_path, 'w', encoding='utf-8') as report_file:
        final_config_path = os.path.join(run_specific_dir_path, 'config.ini.archived')
        config = configparser.ConfigParser()
        config.read(final_config_path)

        # --- Robust Parameter Reading from Archived Config ---
        def get_robust(section_keys, key_keys):
            for section in section_keys:
                for key in key_keys:
                    if config.has_option(section, key):
                        return config.get(section, key)
            return 'N/A'

        llm_model = get_robust(['Model', 'LLM'], ['model_name', 'model'])
        mapping_strategy = get_robust(['Study'], ['mapping_strategy'])
        personalities_file_path = get_robust(['General', 'Filenames'], ['personalities_db_path', 'personalities_src'])
        personalities_file = os.path.basename(personalities_file_path) if personalities_file_path != 'N/A' else 'N/A'
        
        k_val = get_robust(['Study'], ['k_per_query', 'num_subjects', 'group_size'])
        m_val = get_robust(['Study'], ['num_iterations', 'num_trials'])
        
        parser_summary_match = re.search(r"<<<PARSER_SUMMARY:(\d+):(\d+)>>>", output3)
        parsing_status_report = f"{parser_summary_match.group(1)}/{parser_summary_match.group(2)} responses parsed" if parser_summary_match else "N/A"

        header = f"""
================================================================================
 REPLICATION RUN REPORT
================================================================================
Date:            {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Final Status:    {pipeline_status}
Run Directory:   {os.path.basename(run_specific_dir_path)}
Parsing Status:  {parsing_status_report}
Report File:     {report_filename}

--- Run Parameters ---
Num Iterations (m): {m_val}
Items per Query (k): {k_val}
Mapping Strategy: {mapping_strategy}
Personalities Source: {personalities_file}
LLM Model:       {llm_model}
Run Notes:       {args.notes}
================================================================================
"""
        # Write the "front end" of the report
        report_file.write(header.strip())

        # --- THIS IS THE MODIFIED BLOCK ---
        # If the pipeline completed successfully, write only the "back end" analysis summary.
        # Otherwise, write all the detailed logs for debugging purposes.
        if pipeline_status == "COMPLETED":
            analysis_summary_start_index = output4.find("<<<ANALYSIS_SUMMARY_START>>>")
            if analysis_summary_start_index != -1:
                # Extract just the analysis part from the Stage 4 output
                analysis_summary = output4[analysis_summary_start_index:]
                report_file.write("\n\n" + analysis_summary.strip())
            else:
                # Fallback in case the analysis summary tag is missing
                report_file.write("\n\n--- ANALYSIS SUMMARY NOT FOUND IN STAGE 4 OUTPUT ---")
                report_file.write("".join(all_stage_outputs)) # Write full log as a fallback
        else:
            # For FAILED or INTERRUPTED runs, write the full, detailed logs.
            report_file.write("".join(all_stage_outputs))
    
    logging.info(f"Replication run finished. Report saved in directory: {os.path.basename(run_specific_dir_path)}")


if __name__ == "__main__":
    main()

# === End of src/orchestrate_experiment.py ===