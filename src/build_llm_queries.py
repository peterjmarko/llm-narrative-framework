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
# Filename: src/build_llm_queries.py

"""
Orchestrates the generation of all query sets for a single replication.

This script is the first stage of the experimental pipeline, responsible for
creating all the trials for one replication. It orchestrates `query_generator.py`
in a loop to produce a batch of unique queries.

Key Workflow:
1.  Loads the master list of all personalities.
2.  Loads the list of personalities already used in the experiment to ensure
    sampling is done without replacement.
3.  For the specified number of iterations (`m`):
    a. Samples `k` unique, available personalities from the master list.
    b. Writes this subset to a temporary file.
    c. Invokes `query_generator.py` as a subprocess, passing it the temporary
       file and a derived seed for deterministic shuffling.
    d. Collects the output files from the worker (query, mapping, manifest)
       and places them in the final `session_queries` directory with the
       correct numbering.
4.  After the loop, it updates the `used_personality_indices.txt` log with all
    personalities selected during this run.
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
    default_k_arg = get_config_value(APP_CONFIG, 'Study', 'group_size', fallback=10, value_type=int)
    default_iter_arg = get_config_value(APP_CONFIG, 'Study', 'num_trials', fallback=100, value_type=int)

    parser = argparse.ArgumentParser(
        description="Generates multiple unique LLM query sets and a consolidated mapping file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("-m", "--num_iterations", type=int, default=default_iter_arg,
                        help="Number of unique query sets to generate in this run.")
    parser.add_argument("-k", "--k_per_query", type=int, default=default_k_arg,
                        help="Number of items (k) per individual query set.")
    parser.add_argument("--master_personalities_file", default=DEFAULT_MASTER_PERSONALITIES_FN,
                        help=f"Filename of the master personalities file (expected in PROJECT_ROOT/data/). Default: {DEFAULT_MASTER_PERSONALITIES_FN}")
    parser.add_argument("--base_output_dir", default=DEFAULT_BASE_OUTPUT_DIR_CFG,
                        help=f"Base directory for all pipeline outputs. Default: {DEFAULT_BASE_OUTPUT_DIR_CFG}")
    parser.add_argument("--queries_subdir", default=DEFAULT_QUERIES_SUBDIR_CFG,
                        help=f"Subdirectory under base_output_dir for generated query sets and mappings. Default: {DEFAULT_QUERIES_SUBDIR_CFG}")
    parser.add_argument("--base_seed", type=int, default=None,
                        help="Base random seed for personality selection. Iteration seed: base_seed + global_iteration_index -1.")
    parser.add_argument("--qgen_base_seed", type=int, default=None,
                        help="Base random seed for query_generator.py internal shuffles. Iteration seed: qgen_base_seed + global_iteration_index -1.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
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

    # --- Validate k and iterations ---
    if args.num_iterations <= 0: logging.error("Number of iterations must be positive."); sys.exit(1)
    if args.k_per_query <= 0: logging.error("k per query must be a positive integer."); sys.exit(1)

    # --- Resolve Paths ---
    script_dir = os.path.dirname(os.path.abspath(__file__)) 
    query_generator_path = os.path.join(script_dir, QUERY_GENERATOR_SCRIPT_NAME)
    if not os.path.exists(query_generator_path):
        logging.error(f"'{QUERY_GENERATOR_SCRIPT_NAME}' not found at '{query_generator_path}'."); sys.exit(1)

    # The --run_output_dir is now the single source of truth for all outputs for this stage.
    resolved_base_output_dir = args.run_output_dir
    final_queries_output_dir = os.path.join(resolved_base_output_dir, args.queries_subdir)
    if not os.path.exists(final_queries_output_dir):
        try:
            os.makedirs(final_queries_output_dir, exist_ok=True)
            logging.info(f"Created queries subdirectory: {final_queries_output_dir}")
        except OSError as e:
            logging.error(f"Could not create queries subdirectory {final_queries_output_dir}: {e}")
            sys.exit(1)
    else:
        logging.info(f"Using queries subdirectory: {final_queries_output_dir}")

    # --- Automatically determine run_mode ---
    if not glob.glob(os.path.join(final_queries_output_dir, "llm_query_*.txt")):
        run_mode = 'new'
    else:
        run_mode = 'continue'
    logging.info(f"Automatically determined run mode: {run_mode}")
    
    used_indices_filepath = os.path.join(final_queries_output_dir, DEFAULT_USED_INDICES_FN)
    aggregate_mappings_filepath = os.path.join(final_queries_output_dir, DEFAULT_AGGREGATE_MAPPINGS_FN)
    temp_subset_qgen_input_path = os.path.join(script_dir, DEFAULT_TEMP_SUBSET_FN) 
    
    newly_used_indices_this_batch = set()

    try: 
        start_index = 1
        if run_mode == 'new':
            clear_output_files_for_fresh_run(final_queries_output_dir, aggregate_mappings_filepath, used_indices_filepath)
        elif run_mode == 'continue':
            start_index = get_next_start_index(final_queries_output_dir, "llm_query_")
            logging.info(f"Continuing run, starting new files with global index {start_index}.")

        # --- Copy Base Query (AFTER cleanup) ---
        base_query_src_filename = get_config_value(APP_CONFIG, 'Filenames', 'base_query_src', fallback="base_query.txt")
        base_query_src_path = os.path.join(PROJECT_ROOT, "data", base_query_src_filename)
        base_query_dest_path = os.path.join(final_queries_output_dir, "llm_query_base.txt")
        if os.path.exists(base_query_src_path):
            # Only copy if it doesn't already exist (for 'continue' mode)
            if not os.path.exists(base_query_dest_path):
                shutil.copy2(base_query_src_path, base_query_dest_path)
                logging.info(f"Copied base query to: {os.path.basename(base_query_dest_path)}")
        else:
            logging.warning(f"Master base query file not found at: {base_query_src_path}. Report will show 'NOT FOUND'.")

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

        if len(available_personalities_df) < 5 * total_needed_for_this_run:
            logging.warning(f"Caution: The pool of {len(available_personalities_df)} available personalities is getting low.")
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
            
            selected_subset_df = available_personalities_df.sample(n=args.k_per_query, random_state=current_selection_seed)
            current_iter_indices = selected_subset_df['Index'].tolist()
            
            df_to_write = selected_subset_df[['Index', 'Name', 'BirthYearInt', 'DescriptionText']].copy()
            df_to_write.rename(columns={'BirthYearInt': 'BirthYear'}, inplace=True)
            
            with open(temp_subset_qgen_input_path, 'w', encoding='utf-8') as f_temp:
                f_temp.write(original_master_header + "\n") 
                df_to_write.to_csv(f_temp, sep='\t', index=False, header=False, encoding='utf-8')
            
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
            
            logging.debug(f"  QGEN Command: {' '.join(cmd)}")
            
            try:
                process_qgen = subprocess.run(cmd, check=True, capture_output=True, text=True, cwd=script_dir, encoding='utf-8')
                if not args.quiet_worker and process_qgen.stderr:
                    logging.warning(f"  query_generator.py stderr:\n{process_qgen.stderr.strip()}")
                
                newly_used_indices_this_batch.update(current_iter_indices)
                available_personalities_df = available_personalities_df.drop(selected_subset_df.index)

                src_full_query_path = os.path.join(qgen_iter_temp_dir_abs, f"iter_{current_global_iteration_index:03d}_llm_query.txt")
                src_mapping_path = os.path.join(qgen_iter_temp_dir_abs, f"iter_{current_global_iteration_index:03d}_mapping.txt")
                src_manifest_path = os.path.join(qgen_iter_temp_dir_abs, f"iter_{current_global_iteration_index:03d}_manifest.txt")

                dest_query_filename_base = f"llm_query_{current_global_iteration_index:03d}"
                dest_query_txt_path = os.path.join(final_queries_output_dir, f"{dest_query_filename_base}.txt")
                
                shutil.copy2(src_full_query_path, dest_query_txt_path)
                
                if os.path.exists(src_manifest_path):
                    dest_manifest_path = os.path.join(final_queries_output_dir, f"{dest_query_filename_base}_manifest.txt")
                    shutil.copy2(src_manifest_path, dest_manifest_path)
                
                if os.path.exists(src_mapping_path):
                    with open(src_mapping_path, 'r', encoding='utf-8') as f_qgen_map:
                        qgen_map_lines = f_qgen_map.readlines()
                        if len(qgen_map_lines) > 1: 
                            mapping_data_line = qgen_map_lines[1].strip()
                            with open(aggregate_mappings_filepath, 'a', encoding='utf-8') as f_map_agg:
                                f_map_agg.write(mapping_data_line + "\n")
                
            except subprocess.CalledProcessError as e:
                logging.error(f"query_generator.py failed for set index {current_global_iteration_index}. Stderr:\n{e.stderr}"); raise 
            finally: 
                if os.path.exists(qgen_iter_temp_dir_abs):
                    shutil.rmtree(qgen_iter_temp_dir_abs)
            
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
            os.remove(temp_subset_qgen_input_path)
        
        logging.info(f"Batch query generation finished or was terminated. Output files are in: {final_queries_output_dir}")

if __name__ == "__main__":
    main()

# === End of src/build_llm_queries.py ===
