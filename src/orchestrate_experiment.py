#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/orchestrate_experiment.py

"""
Single Experiment Orchestrator (orchestrate_experiment.py)

Purpose:
This master script is the main entry point for conducting a **single, complete
experimental run**. It is designed to be called repeatedly by a higher-level
batch script (e.g., `run_replications.ps1`) to execute multiple, seeded replications.

The script manages the entire personality matching pipeline in sequence:
1.  build_queries.py
2.  run_llm_sessions.py
3.  process_llm_responses.py
4.  analyze_performance.py

Its most important function is to create a unique, self-contained, and
self-documenting directory for the experimental run. It passes the path to this
unique directory to each pipeline stage, ensuring all inputs and outputs for
the run are isolated.

Output:
A unique, descriptively named directory. For example:
'run_20250609_140000_rep-01_claude-3-opus_tmp-0.20_personalities_sbj-10_trl-100/'
This directory contains:
-   All generated queries, manifests, and mappings.
-   All raw LLM responses and the API timing log.
-   All processed data and metric distribution files.
-   A final, comprehensive `replication_report_...txt` file summarizing the run's
    parameters, status, validation checks, and performance metrics.

Command-Line Usage (called from a batch script):
    python src/orchestrate_experiment.py [options]

Key Arguments:
    --replication_num     Identifier for this specific replication run.
    -m, --num_iterations  Number of unique query sets (trials) to generate.
    -k, --k_per_query     Number of items (k) per query set.
    --base_seed           Seed for selecting personalities from the master list.
    --qgen_base_seed      Seed for shuffling within the query generator.
    --notes "..."         Optional notes for the report header.
    --quiet               Run all pipeline stages in quiet mode to reduce console output.

Dependencies:
    - All other pipeline scripts in the `src/` directory.
    - src/config_loader.py
"""

# === Start of src/orchestrate_experiment.py ===

import argparse
import os
import sys
import datetime
import subprocess
import logging
import re
import shutil

# --- Setup ---
# Setup basic logging for the master script itself
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    logging.error("FATAL: Could not import from config_loader.py. Ensure it is in the same directory.")
    sys.exit(1)

def run_script(command, title, is_interactive=False):
    """
    Helper to run a script as a subprocess.
    In interactive mode, it lets the subprocess write directly to the console.
    In normal mode, it captures all output robustly for the report.
    """
    logging.info(f"--- Running Stage: {title} ---")

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
    default_k = get_config_value(APP_CONFIG, 'General', 'default_k', fallback=6, value_type=int)
    default_m = get_config_value(APP_CONFIG, 'General', 'default_build_iterations', fallback=5, value_type=int)

    parser = argparse.ArgumentParser(
        description="Runs the full personality matching pipeline and generates a summary report.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-m", "--num_iterations", type=int, default=default_m,
                        help="Number of unique query sets to generate. Overrides config.")
    parser.add_argument("-k", "--k_per_query", type=int, default=default_k,
                        help="Number of items (k) per query set. Overrides config.")
    parser.add_argument("--notes", type=str, default="N/A",
                        help="Optional notes to include in the report header for this run.")
    
    parser.add_argument("--replication_num", type=int, default=1,
                        help="The replication number for this specific run (for naming the output directory).")
    parser.add_argument("--base_seed", type=int, default=None,
                        help="The base random seed for personality selection in build_queries.")
    parser.add_argument("--qgen_base_seed", type=int, default=None,
                        help="The base random seed for shuffling within query_generator.")
    # --- MODIFICATION START ---
    parser.add_argument("--quiet", action="store_true", 
                        help="Run all pipeline stages in quiet mode to reduce console output.")
    # --- MODIFICATION END ---
    
    args = parser.parse_args()

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

    # --- Generate Descriptive Run Directory Name ---
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
    logging.info(f"Created unique output directory for this run: {run_specific_dir_path}")


    # --- Define Script Paths ---
    src_dir = os.path.join(PROJECT_ROOT, 'src')
    build_script = os.path.join(src_dir, 'build_queries.py')
    run_sessions_script = os.path.join(src_dir, 'run_llm_sessions.py')
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_performance.py')

    try:
        # Stage 1: Build Queries (passing the unique run directory)
        cmd1 = [sys.executable, build_script, "-m", str(args.num_iterations), "-k", str(args.k_per_query), "--mode", "new", "--quiet-worker", "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd1.append("--quiet")
        if args.base_seed is not None:
            cmd1.extend(["--base_seed", str(args.base_seed)])
        if args.qgen_base_seed is not None:
            cmd1.extend(["--qgen_base_seed", str(args.qgen_base_seed)])
        output1 = run_script(cmd1, "1. Build Queries")
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
        output2 = run_script(cmd2, "2. Run LLM Sessions", is_interactive=True)
        all_stage_outputs.append(output2)
            
        # Stage 3: Process Responses (passing the unique run directory)
        cmd3 = [sys.executable, process_script, "--run_output_dir", run_specific_dir_path]
        if args.quiet: cmd3.append("--quiet")
        output3 = run_script(cmd3, "3. Process LLM Responses")
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
        output4 = run_script(cmd4, "4. Analyze Performance")
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
    
    # --- Write the Final Report (inside the new run-specific directory) ---
    timestamp_for_file = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    report_filename = f"replication_report_{timestamp_for_file}.txt"
    report_path = os.path.join(run_specific_dir_path, report_filename)
    # The "Writing final report..." log message has been removed.

    with open(report_path, 'w', encoding='utf-8') as report_file:
        personalities_file = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src', 'N/A')
        llm_model = get_config_value(APP_CONFIG, 'LLM', 'model_name', 'N/A')
        
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
        # Add the high-level header the user wants.
        report_file.write("\n\n================================================================================\n")
        report_file.write("### OVERALL META-ANALYSIS RESULTS ###\n")
        report_file.write("================================================================================\n\n")

        if final_analysis_output:
            # Define the unique tag to look for in the analyzer's output.
            start_tag = "<<<ANALYSIS_SUMMARY_START>>>"
            
            # Find the position of the tag in the captured output.
            summary_start_index = final_analysis_output.find(start_tag)
            
            if summary_start_index != -1:
                # If the tag is found, extract everything *after* the tag.
                analysis_summary_text = final_analysis_output[summary_start_index + len(start_tag):].strip()
                report_file.write(analysis_summary_text)
                report_file.write("\n") # Add a final newline for spacing
            else:
                # Fallback if the tag isn't found, indicating a problem.
                report_file.write("Could not find analysis summary section in the script output.\n")
                report_file.write("Full log from analysis stage is included below for debugging:\n\n")
                report_file.write(final_analysis_output)
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