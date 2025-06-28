#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/build_queries.py

"""
Batch LLM Query and Mapping Generator (build_queries.py)

Purpose:
This script orchestrates the generation of multiple unique sets of queries for
a single experimental run. It is designed to be called by `orchestrate_experiment.py`
and operates within a unique run-specific directory provided to it.

Key Features:
-   Generates a specified number of query sets for the experiment.
-   Accepts seeds from the caller to ensure deterministic, reproducible selection
    and shuffling of personalities.
-   Ensures personalities are selected "without replacement" from a master list.
-   Creates all its output within the designated run-specific directory.

Workflow:
1.  Receives the path to a unique run directory via the `--run_output_dir` argument.
2.  Receives seeds for selection (`--base_seed`) and shuffling (`--qgen_base_seed`).
3.  Creates a `session_queries` subdirectory inside the run directory.
4.  For the specified number of iterations:
    a.  Selects 'k' unique, available personalities deterministically using the seed.
    b.  Invokes `query_generator.py` as a worker with a derived seed.
    c.  Copies the generated query, manifest, and mapping files from the worker
        into the run-specific `session_queries` directory.
5.  Updates the `used_personality_indices.txt` log for the current run.

Input Files:
    - Master Personalities File (e.g., 'data/personalities.txt')

Output Files/Directories (within the provided `<run_output_dir>`):
    - `<run_output_dir>/session_queries/`:
        - `llm_query_XXX.txt`: Numbered query files for the LLM.
        - `llm_query_XXX_manifest.txt`: Audit file for each query.
        - `mappings.txt`: Consolidated file of all true mappings for the run.
        - `used_personality_indices.txt`: Log of used personalities for the run.
"""

# === Start of src/build_queries.py ===

import argparse
import random
import os
import sys
import subprocess 
import shutil     
import pandas as pd 
import glob 
import logging

# --- Import from config_loader ---
try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    # ... (fallback import logic as before) ...
    current_script_dir_bq = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir_bq not in sys.path: sys.path.insert(0, current_script_dir_bq)
    try:
        from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
    except ImportError:
        project_root_for_loader_bq = os.path.dirname(current_script_dir_bq)
        if project_root_for_loader_bq not in sys.path: sys.path.insert(0, project_root_for_loader_bq)
        try:
            from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
        except ImportError as e_bq:
            print(f"FATAL: build_queries.py - Could not import config_loader.py. Error: {e_bq}")
            sys.exit(1)

# --- Configuration from Config or Defaults (defined at module level) ---
QUERY_GENERATOR_SCRIPT_NAME = "query_generator.py" 

# Default filenames (these are just the names, paths resolved later)
DEFAULT_MASTER_PERSONALITIES_FN = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src', fallback="personalities.txt")
# DEFAULT_BASE_QUERY_FN is used by query_generator.py, not directly by build_queries.py

DEFAULT_BASE_OUTPUT_DIR_CFG = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback="output") 
DEFAULT_QUERIES_SUBDIR_CFG = get_config_value(APP_CONFIG, 'General', 'queries_subdir', fallback="session_queries")

DEFAULT_TEMP_SUBSET_FN = get_config_value(APP_CONFIG, 'Filenames', 'temp_subset_personalities', fallback="temp_subset_personalities.txt")
DEFAULT_USED_INDICES_FN = get_config_value(APP_CONFIG, 'Filenames', 'used_indices_log', fallback="used_personality_indices.txt")
DEFAULT_AGGREGATE_MAPPINGS_FN = get_config_value(APP_CONFIG, 'Filenames', 'aggregated_mappings_in_queries_dir', fallback="mappings.txt")

# --- Setup Logging ---
DEFAULT_LOG_LEVEL_BUILD = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')
numeric_log_level_build = getattr(logging, DEFAULT_LOG_LEVEL_BUILD.upper(), logging.INFO)
logging.basicConfig(level=numeric_log_level_build,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

# --- Helper Functions ---
# ... (load_all_personalities_df, load_used_indices, append_used_indices, 
#      get_next_start_index, clear_output_files_for_fresh_run functions remain the same) ...
def load_all_personalities_df(filepath):
    original_header_line = None
    try:
        with open(filepath, 'r', encoding='utf-8') as f_header:
            original_header_line = f_header.readline().strip() 
            if not original_header_line:
                 logging.error(f"Master personalities file '{filepath}' seems to be missing a header.")
                 sys.exit(1)

        df = pd.read_csv(filepath, sep='\t', encoding='utf-8', dtype={'BirthYear': str}, header=0)
        required_cols = ['Index', 'Name', 'BirthYear', 'DescriptionText']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logging.error(f"'{filepath}' is missing required header columns: {', '.join(missing_cols)}")
            sys.exit(1)

        df['Index'] = pd.to_numeric(df['Index'], errors='coerce')
        df['BirthYear_Clean'] = df['BirthYear'].astype(str).str.extract(r'(-?\d+)').iloc[:,0]
        df['BirthYear_Numeric'] = pd.to_numeric(df['BirthYear_Clean'], errors='coerce')
        df.dropna(subset=['Index', 'Name', 'DescriptionText', 'BirthYear_Numeric'], inplace=True)
        df['Index'] = df['Index'].astype(int)
        df['BirthYear_Numeric'] = df['BirthYear_Numeric'].astype(int)
        df.rename(columns={'BirthYear_Numeric': 'BirthYearInt'}, inplace=True) # Keep original 'BirthYear' as string from dtype

        if df.empty:
            logging.error(f"No valid data rows found in '{filepath}' after cleaning.")
            sys.exit(1)
        return df, original_header_line
    except FileNotFoundError:
        logging.error(f"Master personalities file '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading master personalities file '{filepath}': {e}")
        sys.exit(1)

def load_used_indices(filepath):
    used_indices = set()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    stripped_line = line.strip()
                    if stripped_line:
                        try: used_indices.add(int(stripped_line))
                        except ValueError: logging.warning(f"Invalid index in '{filepath}': {stripped_line}")
        except Exception as e: logging.warning(f"Could not read used indices file '{filepath}': {e}")
    return used_indices

def append_used_indices(filepath, new_indices_to_add):
    if not new_indices_to_add: return
    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            for idx in new_indices_to_add: f.write(f"{idx}\n")
        logging.info(f"Appended {len(new_indices_to_add)} newly used indices to {os.path.basename(filepath)}.")
    except Exception as e: logging.warning(f"Could not append to used indices file '{filepath}': {e}")

def get_next_start_index(output_dir, file_prefix="llm_query_"):
    max_index = 0
    pattern = os.path.join(output_dir, f"{file_prefix}*.txt")
    for filepath in glob.glob(pattern):
        try:
            filename = os.path.basename(filepath)
            index_str = filename.replace(file_prefix, "").replace(".txt", "")
            if index_str.isdigit():
                index = int(index_str)
                if index > max_index: max_index = index
        except ValueError: continue 
    return max_index + 1

def clear_output_files_for_fresh_run(output_dir, aggregate_mappings_filepath, used_indices_filepath):
    logging.info(f"Clearing previous query output files in '{output_dir}' for a fresh run...")
    cleared_any_query_files = False
    # Use a more robust wildcard pattern to catch all numbered query files.
    for pattern in ["llm_query_*.txt", "llm_query_*_full.json"]:
        for filepath_to_delete in glob.glob(os.path.join(output_dir, pattern)):
            try:
                os.remove(filepath_to_delete)
                logging.info(f"  Deleted: {os.path.basename(filepath_to_delete)}")
                cleared_any_query_files = True
            except OSError as e:
                logging.warning(f"  Warning: Could not delete {os.path.basename(filepath_to_delete)}: {e}")
    if not cleared_any_query_files:
        logging.info("  No 'llm_query_*.txt' or JSON files found to clear.")

    if os.path.exists(aggregate_mappings_filepath):
        try:
            os.remove(aggregate_mappings_filepath)
            logging.info(f"Deleted existing aggregate mappings file: {aggregate_mappings_filepath}")
        except OSError as e: logging.warning(f"Could not delete aggregate mappings file {aggregate_mappings_filepath}: {e}")
    
    if os.path.exists(used_indices_filepath):
        try:
            os.remove(used_indices_filepath)
            logging.info(f"Deleted existing used indices file: {used_indices_filepath}")
        except OSError as e: logging.warning(f"Could not delete used indices file {used_indices_filepath}: {e}")
    
    if os.path.exists(used_indices_filepath):
        try:
            os.remove(used_indices_filepath)
            logging.info(f"Deleted existing used indices file: {os.path.basename(used_indices_filepath)}")
        except OSError as e: logging.warning(f"Could not delete used indices file {os.path.basename(used_indices_filepath)}: {e}")


def main():
    # Get defaults for argparse from module-level constants (which were loaded from config)
    default_k_arg = get_config_value(APP_CONFIG, 'General', 'default_k', fallback=6, value_type=int)
    default_iter_arg = get_config_value(APP_CONFIG, 'General', 'default_build_iterations', fallback=5, value_type=int)

    parser = argparse.ArgumentParser(
        description="Generates multiple unique LLM query sets and a consolidated mapping file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-m", "--num_iterations", type=int, default=default_iter_arg,
                        help="Number of unique query sets to generate in this run.")
    parser.add_argument("-k", "--k_per_query", type=int, default=default_k_arg,
                        help="Number of items (k) per individual query set.")
    parser.add_argument("--master_personalities_file", default=DEFAULT_MASTER_PERSONALITIES_FN, # Use module const
                        help=f"Filename of the master personalities file (expected in PROJECT_ROOT/data/). Default: {DEFAULT_MASTER_PERSONALITIES_FN}")
    parser.add_argument("--base_output_dir", default=DEFAULT_BASE_OUTPUT_DIR_CFG, # Use module const
                        help=f"Base directory for all pipeline outputs. Default: {DEFAULT_BASE_OUTPUT_DIR_CFG}")
    parser.add_argument("--queries_subdir", default=DEFAULT_QUERIES_SUBDIR_CFG, # Use module const
                        help=f"Subdirectory under base_output_dir for generated query sets and mappings. Default: {DEFAULT_QUERIES_SUBDIR_CFG}")
    parser.add_argument("--base_seed", type=int, default=None,
                        help="Base random seed for personality selection. Iteration seed: base_seed + global_iteration_index -1.")
    parser.add_argument("--qgen_base_seed", type=int, default=None,
                        help="Base random seed for query_generator.py internal shuffles. Iteration seed: qgen_base_seed + global_iteration_index -1.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
    parser.add_argument("--mode", choices=['new', 'continue'], default=None,
                        help="Run mode ('new' or 'continue'). If provided, skips the interactive prompt.")
    parser.add_argument("--quiet-worker", action="store_true",
                        help="Suppress the detailed stdout/stderr from the query_generator.py worker during the run.")
    parser.add_argument("--run_output_dir", required=True,
                        help="The absolute path to the self-contained output directory for this specific run.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-iteration progress messages.")

    args = parser.parse_args()
    
    # --- Adjust Log Level ---
    log_level_final_build = DEFAULT_LOG_LEVEL_BUILD
    if args.verbose == 1: log_level_final_build = "INFO"
    elif args.verbose >= 2: log_level_final_build = "DEBUG"
    numeric_final_log_level = getattr(logging, log_level_final_build.upper(), logging.INFO)
    root_logger = logging.getLogger(); root_logger.setLevel(numeric_final_log_level)
    if not root_logger.hasHandlers() or not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        for handler_old in root_logger.handlers[:]: root_logger.removeHandler(handler_old)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        root_logger.addHandler(stream_handler)
    else:
        for handler_curr in root_logger.handlers: handler_curr.setLevel(numeric_final_log_level)
    logging.info(f"Build Queries log level set to: {log_level_final_build}")

    # --- Get run_mode from user input ---
    run_mode = 'new'
    if args.mode:
        run_mode = args.mode
    else:
        try:
            run_mode_input = input("Is this a New run or a Continued run? ([Enter/N/n] for New, [C/c] for Continued): ").strip().lower()
            if run_mode_input in ['c', 'continue']: run_mode = 'continue'
            elif run_mode_input in ['', 'n', 'new', 'fresh']: run_mode = 'new'
            else: logging.warning("Invalid input for run mode. Assuming 'new' run.")
        except KeyboardInterrupt: logging.info("\nOperation cancelled by user during run mode selection. Exiting."); sys.exit(0)
    logging.info(f"Selected run mode: {run_mode}")

    # --- Validate k and iterations ---
    if args.num_iterations <= 0: logging.error("Number of iterations must be positive."); sys.exit(1)
    if args.k_per_query <= 0: logging.error("k per query must be a positive integer."); sys.exit(1)

    # --- Resolve Paths ---
    # script_dir is src/
    script_dir = os.path.dirname(os.path.abspath(__file__)) 
    query_generator_path = os.path.join(script_dir, QUERY_GENERATOR_SCRIPT_NAME)
    if not os.path.exists(query_generator_path):
        logging.error(f"'{QUERY_GENERATOR_SCRIPT_NAME}' not found at '{query_generator_path}'."); sys.exit(1)

    # The --run_output_dir is now the single source of truth for all outputs for this stage.
    resolved_base_output_dir = args.run_output_dir

    final_queries_output_dir = os.path.join(resolved_base_output_dir, args.queries_subdir)
    # The os.makedirs call ensures the subdirectory (e.g., 'session_queries') exists inside the run_... directory.
    if not os.path.exists(final_queries_output_dir):
        try:
            os.makedirs(final_queries_output_dir, exist_ok=True)
            logging.info(f"Created queries subdirectory: {final_queries_output_dir}")
        except OSError as e:
            logging.error(f"Could not create queries subdirectory {final_queries_output_dir}: {e}")
            sys.exit(1)
    else:
        logging.info(f"Using queries subdirectory: {final_queries_output_dir}")

    used_indices_filepath = os.path.join(final_queries_output_dir, DEFAULT_USED_INDICES_FN)
    aggregate_mappings_filepath = os.path.join(final_queries_output_dir, DEFAULT_AGGREGATE_MAPPINGS_FN)
    
    # Temporary input file for query_generator.py will be in src/
    temp_subset_qgen_input_path = os.path.join(script_dir, DEFAULT_TEMP_SUBSET_FN) 
    
    newly_used_indices_this_batch = set()

    try: 
        start_index = 1
        if run_mode == 'new':
            clear_output_files_for_fresh_run(final_queries_output_dir, aggregate_mappings_filepath, used_indices_filepath)
        elif run_mode == 'continue':
            start_index = get_next_start_index(final_queries_output_dir, "llm_query_")
            logging.info(f"Continuing run, starting new files with global index {start_index}.")

        master_personalities_src_path = os.path.join(PROJECT_ROOT, "data", args.master_personalities_file)
        logging.info(f"Loading master personalities from: {master_personalities_src_path}")
        master_personalities_df, original_master_header = load_all_personalities_df(master_personalities_src_path)
        
        globally_used_indices = load_used_indices(used_indices_filepath)
        logging.info(f"Loaded {len(globally_used_indices)} previously used personality indices.")
        
        available_personalities_df = master_personalities_df[~master_personalities_df['Index'].isin(globally_used_indices)].copy()
        
        total_needed_for_this_run = args.num_iterations * args.k_per_query
        if len(available_personalities_df) < total_needed_for_this_run:
            logging.error(f"Not enough unique *available* personalities ({len(available_personalities_df)}) "
                          f"to generate {args.num_iterations} new sets of {args.k_per_query} items "
                          f"({total_needed_for_this_run} needed).")
            sys.exit(1)

        logging.info(f"Total available *unused* personalities: {len(available_personalities_df)}")

        # Add a warning if the available pool is getting low
        # Rule of thumb: warn if available pool is less than 5x the items needed for the run.
        if len(available_personalities_df) < 5 * total_needed_for_this_run:
            logging.warning(f"Caution: The pool of {len(available_personalities_df)} available personalities is getting low "
                            f"compared to the {total_needed_for_this_run} required for this batch. "
                            f"The diversity of later queries may be reduced.")
        logging.info(f"Generating {args.num_iterations} query sets, each with k={args.k_per_query}, starting from global index {start_index}.\n")

        if run_mode == 'new' or not os.path.exists(aggregate_mappings_filepath) or os.path.getsize(aggregate_mappings_filepath) == 0:
            try:
                with open(aggregate_mappings_filepath, 'w', encoding='utf-8') as f_map_agg:
                    map_header_parts = [f"Map_idx{j+1}" for j in range(args.k_per_query)]
                    f_map_agg.write("\t".join(map_header_parts) + "\n")
                logging.info(f"Initialized aggregate mappings file: {aggregate_mappings_filepath}")
            except Exception as e: logging.error(f"Error initializing aggregate mappings file: {e}"); sys.exit(1)

        for i_loop in range(args.num_iterations):
            current_global_iteration_index = start_index + i_loop
            
            qgen_iter_temp_subdir_name = f"temp_qgen_outputs_iter_{current_global_iteration_index:03d}"
            qgen_iter_temp_dir_abs = os.path.join(script_dir, qgen_iter_temp_subdir_name)
            qgen_output_prefix_for_arg = os.path.join(qgen_iter_temp_subdir_name, f"iter_{current_global_iteration_index:03d}_")

            if not args.quiet:
                logging.info(f"--- Generating Set (Global Index {current_global_iteration_index}) / Iteration {i_loop+1} of {args.num_iterations} ---")

            if len(available_personalities_df) < args.k_per_query:
                logging.error("Ran out of unique available personalities during generation loop."); break
            
            current_selection_seed = None
            if args.base_seed is not None:
                current_selection_seed = args.base_seed + current_global_iteration_index - 1
                if not args.quiet:
                    logging.info(f"  Using deterministic seed {current_selection_seed} for personality selection.")
            else:
                if not args.quiet:
                    logging.info("  No base_seed provided; selecting personalities randomly.")

            selected_subset_df = available_personalities_df.sample(n=args.k_per_query, random_state=current_selection_seed)
            current_iter_indices = selected_subset_df['Index'].tolist()
            
            df_to_write = selected_subset_df[['Index', 'Name', 'BirthYearInt', 'DescriptionText']].copy()
            df_to_write.rename(columns={'BirthYearInt': 'BirthYear'}, inplace=True)
            
            with open(temp_subset_qgen_input_path, 'w', encoding='utf-8') as f_temp:
                f_temp.write(original_master_header + "\n") 
                df_to_write.to_csv(f_temp, sep='\t', index=False, header=False, encoding='utf-8')
            logging.debug(f"  Created temporary input for query_generator: {temp_subset_qgen_input_path}")

            qgen_base_query_filename = get_config_value(APP_CONFIG, 'Filenames', 'base_query_src', fallback="base_query.txt")

            cmd = [
                sys.executable, query_generator_path, "-k", str(args.k_per_query),
                "--personalities_file", DEFAULT_TEMP_SUBSET_FN, 
                "--base_query_file", qgen_base_query_filename,
                "--output_basename_prefix", qgen_output_prefix_for_arg 
            ]
            if args.verbose >=2: cmd.append("-vv") 
            elif args.verbose ==1: cmd.append("-v")
            
            iteration_qgen_seed_value = None
            if args.qgen_base_seed is not None:
                iteration_qgen_seed_value = args.qgen_base_seed + current_global_iteration_index - 1
            else:
                iteration_qgen_seed_value = random.randint(0, 2**32 - 1)
            cmd.extend(["--seed", str(iteration_qgen_seed_value)])
            
            if not args.quiet:
                logging.info(f"  Running query_generator.py (output prefix target: '{qgen_output_prefix_for_arg}')...")
            logging.debug(f"  QGEN Command: {' '.join(cmd)}")
            
            try:
                process_qgen = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=script_dir, encoding='utf-8')
                if not args.quiet_worker and process_qgen.stderr:
                    logging.warning(f"  query_generator.py stderr:\n{process_qgen.stderr.strip()}")
                if not args.quiet:
                    logging.info("  query_generator.py completed successfully.")
                
                newly_used_indices_this_batch.update(current_iter_indices)
                available_personalities_df = available_personalities_df.drop(selected_subset_df.index)

                src_full_query_path = os.path.join(qgen_iter_temp_dir_abs, f"iter_{current_global_iteration_index:03d}_llm_query.txt")
                src_mapping_path = os.path.join(qgen_iter_temp_dir_abs, f"iter_{current_global_iteration_index:03d}_mapping.txt")
                src_manifest_path = os.path.join(qgen_iter_temp_dir_abs, f"iter_{current_global_iteration_index:03d}_manifest.txt")

                dest_query_filename_base = f"llm_query_{current_global_iteration_index:03d}"
                dest_query_txt_path = os.path.join(final_queries_output_dir, f"{dest_query_filename_base}.txt")
                
                query_text_content = ""
                if os.path.exists(src_full_query_path):
                    shutil.copy2(src_full_query_path, dest_query_txt_path)
                    if not args.quiet:
                        logging.info(f"  Copied '{os.path.basename(src_full_query_path)}' to '{dest_query_txt_path}'")
                    with open(src_full_query_path, 'r', encoding='utf-8') as f_q:
                        query_text_content = f_q.read()
                else:
                    logging.warning(f"  Source query text file not found in {qgen_iter_temp_dir_abs}.")

                if query_text_content:
                    import json
                    request_payload = {"model": get_config_value(APP_CONFIG, 'LLM', 'model_name', fallback=""), "messages": [{"role": "user", "content": query_text_content}]}
                    max_tokens = get_config_value(APP_CONFIG, 'LLM', 'max_tokens', fallback=None, value_type=int)
                    if max_tokens is not None: request_payload['max_tokens'] = max_tokens
                    temperature = get_config_value(APP_CONFIG, 'LLM', 'temperature', fallback=None, value_type=float)
                    if temperature is not None: request_payload['temperature'] = temperature
                    dest_query_json_path = os.path.join(final_queries_output_dir, f"{dest_query_filename_base}_full.json")
                    with open(dest_query_json_path, 'w', encoding='utf-8') as f_json:
                        json.dump(request_payload, f_json, indent=2, ensure_ascii=False)
                    if not args.quiet:
                        logging.info(f"  Saved full LLM request payload to '{os.path.basename(dest_query_json_path)}'")
                else: logging.warning(f"  Source '{os.path.basename(src_full_query_path)}' not found in {qgen_iter_temp_dir_abs}.")

                if os.path.exists(src_manifest_path):
                    dest_manifest_path = os.path.join(final_queries_output_dir, f"{dest_query_filename_base}_manifest.txt")
                    shutil.copy2(src_manifest_path, dest_manifest_path)
                    if not args.quiet:
                        logging.info(f"  Copied audit manifest to '{os.path.basename(dest_manifest_path)}'")
                else:
                    logging.warning(f"  Source manifest file not found in {qgen_iter_temp_dir_abs}.")

                if os.path.exists(src_mapping_path):
                    with open(src_mapping_path, 'r', encoding='utf-8') as f_qgen_map:
                        qgen_map_lines = f_qgen_map.readlines()
                        if len(qgen_map_lines) > 1: 
                            mapping_data_line = qgen_map_lines[1].strip()
                            with open(aggregate_mappings_filepath, 'a', encoding='utf-8') as f_map_agg:
                                f_map_agg.write(mapping_data_line + "\n")
                            if not args.quiet:
                                logging.info(f"  Appended mapping for set {current_global_iteration_index} to {os.path.basename(aggregate_mappings_filepath)}")
                        else: logging.warning(f"  qgen mapping file ('{os.path.basename(src_mapping_path)}') empty/no data.")
                else: logging.warning(f"  qgen mapping file ('{os.path.basename(src_mapping_path)}') not found in {qgen_iter_temp_dir_abs}.")
                
            except subprocess.CalledProcessError as e:
                logging.error(f"query_generator.py failed for set index {current_global_iteration_index}."); raise 
            finally: 
                if os.path.exists(qgen_iter_temp_dir_abs):
                    try: shutil.rmtree(qgen_iter_temp_dir_abs); logging.debug(f"Cleaned up temp qgen output dir: {qgen_iter_temp_dir_abs}")
                    except OSError as e_rm: logging.warning(f"Could not remove temp qgen output dir {qgen_iter_temp_dir_abs}: {e_rm}")
            
            if not args.quiet:
                logging.info(f"--- Set (Global Index {current_global_iteration_index}) Generation Complete ---\n")

    except KeyboardInterrupt:
        logging.info("\nBatch generation interrupted by user (Ctrl+C).")
    except Exception as e_global: 
        logging.exception(f"\nAn unexpected error occurred during batch processing: {e_global}")
    finally: 
        if newly_used_indices_this_batch:
            append_used_indices(used_indices_filepath, newly_used_indices_this_batch)

        if os.path.exists(temp_subset_qgen_input_path):
            try: os.remove(temp_subset_qgen_input_path); logging.info(f"Cleaned up temporary subset input file: {temp_subset_qgen_input_path}")
            except OSError as e: logging.warning(f"Could not remove temp subset input file {temp_subset_qgen_input_path}: {e}")
        
        logging.info(f"Batch query generation finished or was terminated. Output files are in: {final_queries_output_dir}")

if __name__ == "__main__":
    main()

# === End of src/batch_query_runner.py ===