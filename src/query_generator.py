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
# Filename: src/query_generator.py

"""
Worker script to generate a single, complete LLM query set.

This script is the "worker" in the query generation stage. It is called by
`build_llm_queries.py` and is responsible for taking a pre-selected subset of
`k` personalities and generating one self-contained set of query artifacts.

Key Operations:
1.  Assigns a temporary `internal_ref_id` to each person to maintain the true
    link between their name and description.
2.  Handles the `mapping_strategy` ('correct' or 'random') to define the ground
    truth for the trial.
3.  Shuffles the list of names and the list of descriptions independently.
4.  Generates the three critical output files for a single trial:
    - `llm_query.txt`: The final prompt for the LLM.
    - `mapping.txt`: The ground truth mapping for scoring.
    - `manifest.txt`: A detailed audit file to validate the shuffling and mapping.
"""

# === Start of personality_matching_project/src/query_generator.py ===

import random
import argparse
import os
import sys
import logging
import unicodedata
import csv

from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT

# --- Configuration: Default Filenames from config.ini (via config_loader) ---
DEFAULT_PERSONALITIES_SRC_FN = get_config_value(APP_CONFIG, 'Filenames', 'personalities_src', fallback="personalities_db.txt")
DEFAULT_BASE_QUERY_SRC_FN = get_config_value(APP_CONFIG, 'Filenames', 'base_query_src', fallback="base_query.txt")
DEFAULT_QGEN_TEMP_PREFIX = get_config_value(APP_CONFIG, 'Filenames', 'qgen_temp_prefix', fallback="", value_type=str)
DEFAULT_TEMP_SUBSET_FN_QGEN = get_config_value(APP_CONFIG, 'Filenames', 'temp_subset_personalities', fallback="temp_subset_personalities.txt")

# --- Default Output Subdirectory ---
DEFAULT_STANDALONE_OUTPUT_SUBDIR_NAME = "qgen_standalone_output"

# --- Output file suffixes ---
NAMES_FILE_SUFFIX = "names.txt"
DESCRIPTIONS_FILE_SUFFIX = "descriptions.txt"
SHUFFLED_NAMES_FILE_SUFFIX = "shuffled_names.txt"
SHUFFLED_DESCRIPTIONS_FILE_SUFFIX = "shuffled_descriptions.txt"
MAPPING_FILE_SUFFIX = "mapping.txt"
MANIFEST_FILE_SUFFIX = "manifest.txt"
FULL_QUERY_FILE_SUFFIX = "llm_query.txt"

# --- Setup Logging ---
DEFAULT_LOG_LEVEL_QGEN = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')
numeric_log_level_qgen = getattr(logging, DEFAULT_LOG_LEVEL_QGEN.upper(), logging.INFO)
logging.basicConfig(level=numeric_log_level_qgen,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def normalize_text_for_llm(text):
    """
    Normalizes text to a simple ASCII representation to prevent encoding issues
    when sending to the LLM or when the LLM echoes input.
    """
    try:
        # Decompose unicode characters (e.g., 'è' -> 'e' + '`'), then encode to ASCII, ignoring non-ASCII marks.
        return unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('ascii')
    except (TypeError, AttributeError):
        return text # Return original if not a string

# --- Helper Functions (Assumed to be defined as previously, using logging) ---
def load_base_query(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read the entire content of the file without skipping any lines.
            content = f.read()
            if not content.strip():
                logging.warning(f"Base query file '{filepath}' is empty.")
                return ""
            return content
    except FileNotFoundError:
        logging.error(f"Base query file '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading base query file '{filepath}': {e}")
        sys.exit(1)

def load_personalities(filepath, required_k_value):
    personalities = []
    try:
        with open(filepath, 'r', encoding='utf-8', newline='') as f:
            # Use DictReader to handle columns by name, which is robust to column count/order.
            reader = csv.DictReader(f, delimiter='\t')
            for line_num, row in enumerate(reader, 2): # Start line count from 2 for logging
                try:
                    # The worker only needs these specific keys. It will ignore 'idADB'.
                    personalities.append({
                        'original_index_from_file': int(row['Index']),
                        'name': row['Name'],
                        'year': int(row['BirthYear']),
                        'description': row['DescriptionText']
                    })
                except (ValueError, KeyError) as e:
                    logging.warning(f"Line {line_num} in '{filepath}' has invalid data type or missing key ({e}). Skipping: '{row}'")
                    continue
        
        if len(personalities) < required_k_value:
            logging.error(f"Not enough valid entries in source personalities file '{filepath}' ({len(personalities)}) "
                          f"to select {required_k_value} items. Need at least {required_k_value}.")
            sys.exit(1)
            
        return personalities
    except FileNotFoundError:
        logging.error(f"Personalities file '{filepath}' not found.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error reading personalities file '{filepath}': {e}")
        sys.exit(1)

def select_and_prepare_k_items(all_personalities, k_to_select):
    if len(all_personalities) < k_to_select: 
        logging.error(f"Internal Error: Cannot select {k_to_select} items, only {len(all_personalities)} available.")
        sys.exit(1)
        
    raw_selected_entries = random.sample(all_personalities, k_to_select)
    
    selected_items_with_ref = []
    for i, entry in enumerate(raw_selected_entries):
        selected_items_with_ref.append({
            'original_index_from_file': entry['original_index_from_file'],
            'name': entry['name'],
            'year': entry['year'],
            'description': entry['description'],
            'internal_ref_id': i 
        })
    return selected_items_with_ref

def write_tab_separated_file(filepath, header, data_rows):
    try:
        output_file_dir = os.path.dirname(filepath)
        if output_file_dir and not os.path.exists(output_file_dir):
            os.makedirs(output_file_dir, exist_ok=True)
            logging.debug(f"Helper: Ensured directory exists for {filepath}: {output_file_dir}")

        logging.debug(f"Attempting to open and write to: {filepath}") # DEBUG ADDED
        with open(filepath, 'w', encoding='utf-8') as f:
            logging.debug(f"Successfully opened for writing: {filepath}") # DEBUG ADDED
            f.write(header + "\n")
            for row_items in data_rows:
                f.write("\t".join(map(str, row_items)) + "\n")
        logging.debug(f"Finished writing, closed: {filepath}") # DEBUG ADDED
        logging.info(f"Successfully wrote: {filepath}")
    except IOError as e:
        logging.error(f"IOError writing {filepath}: {e}")
        raise 
    except Exception as e:
        logging.error(f"Unexpected error writing {filepath}: {e}")
        raise

def create_shuffled_names_file(selected_items_with_ref, filepath):
    name_year_to_shuffle = [
        (normalize_text_for_llm(item['name']), item['year'], item['internal_ref_id']) for item in selected_items_with_ref
    ]
    shuffled_name_year_list = list(name_year_to_shuffle) 
    random.shuffle(shuffled_name_year_list)
    
    try:
        output_file_dir = os.path.dirname(filepath)
        if output_file_dir and not os.path.exists(output_file_dir):
            os.makedirs(output_file_dir, exist_ok=True)
            logging.debug(f"Ensured directory exists for {filepath}: {output_file_dir}")

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("Name_BirthYear\n")
            for name, year, _ in shuffled_name_year_list:
                f.write(f"{name} ({year})\n")
        logging.info(f"Successfully wrote: {filepath}")
        return shuffled_name_year_list
    except Exception as e:
        logging.error(f"Error writing {filepath}: {e}")
        sys.exit(1)

def create_shuffled_descriptions_file(selected_items_with_ref, filepath, k_val):
    description_to_shuffle = [
        (item['description'], item['internal_ref_id']) for item in selected_items_with_ref
    ]
    shuffled_description_list = list(description_to_shuffle) 
    random.shuffle(shuffled_description_list)
    
    data_rows = []
    for j in range(k_val):
        desc, _ = shuffled_description_list[j]
        data_rows.append([j + 1, desc]) 
    
    write_tab_separated_file(filepath, "Index\tDescriptionText", data_rows) # write_tab_separated_file handles os.makedirs
    return shuffled_description_list

def create_mapping_file(shuffled_name_year_list, shuffled_description_list, filepath, k_val):
    mapping_indices_1_based = []
    for _, _, ref_id_from_name_list in shuffled_name_year_list:
        found_match = False
        for j, (_, ref_id_from_desc_list) in enumerate(shuffled_description_list):
            if ref_id_from_desc_list == ref_id_from_name_list:
                mapping_indices_1_based.append(j + 1) 
                found_match = True
                break
        if not found_match:
            logging.critical("CRITICAL ERROR: Could not find matching description for a name during mapping generation.")
            sys.exit(1)
            
    header_parts = [f"Map_idx{i+1}" for i in range(k_val)]
    write_tab_separated_file(filepath, "\t".join(header_parts), [mapping_indices_1_based]) # write_tab_separated_file handles os.makedirs

def create_manifest_file(shuffled_name_year_list, shuffled_description_list, filepath, k_val, desc_text_to_original_id_map):
    """
    Creates a manifest file for auditing the name-to-description mapping.
    """
    header = "Name_in_Query\tName_Ref_ID\tShuffled_Desc_Index\tDesc_Ref_ID\tDesc_in_Query"
    data_rows = []

    # Create a lookup map from the mapping_ref_id to its new shuffled index and text
    desc_mapping_ref_id_to_details = {
        ref_id: (idx + 1, desc) for idx, (desc, ref_id) in enumerate(shuffled_description_list)
    }

    for name, year, name_ref_id in shuffled_name_year_list:
        if name_ref_id in desc_mapping_ref_id_to_details:
            shuffled_desc_index, desc_text = desc_mapping_ref_id_to_details[name_ref_id]

            # Look up the original ID of the description text to correctly report it.
            original_desc_ref_id = desc_text_to_original_id_map.get(desc_text, "ERROR_NOT_FOUND")

            data_rows.append([
                f"{name} ({year})",
                name_ref_id,
                shuffled_desc_index,
                original_desc_ref_id, # This is the fix for random mapping reporting
                desc_text[:75] + '...' if len(desc_text) > 75 else desc_text
            ])
        else:
            logging.critical(f"CRITICAL: Manifest generation failed. No matching description for name_ref_id {name_ref_id}.")
            # This should ideally never happen if the logic is sound
            data_rows.append([f"{name} ({year})", name_ref_id, "ERROR", "ERROR", "ERROR"])
    
    write_tab_separated_file(filepath, header, data_rows)

def assemble_full_query(base_prompt_content, shuffled_name_year_list, shuffled_description_list, filepath, k_val):
    # --- NEW: Fill in the dynamic placeholders ---
    formatted_prompt = base_prompt_content.format(
        k=k_val,
        k_squared=(k_val * k_val),
        k_plus_1=(k_val + 1)
    )
    # --- END NEW ---

    try:
        output_file_dir = os.path.dirname(filepath)
        if output_file_dir and not os.path.exists(output_file_dir):
            os.makedirs(output_file_dir, exist_ok=True)
            logging.debug(f"Ensured directory exists for {filepath}: {output_file_dir}")

        with open(filepath, 'w', encoding='utf-8') as f:
            # Write the instructions (now with correct 'k' value)
            if formatted_prompt.strip():
                f.write(formatted_prompt.strip() + "\n\n")
            
            # Append List A
            f.write("List A\n")
            for name, year, _ in shuffled_name_year_list:
                f.write(f"{name} ({year})\n")
            
            # Append List B
            f.write("\nList B\n")
            for j in range(k_val):
                desc, _ = shuffled_description_list[j]
                f.write(f"ID {j+1}: {desc}\n")
                
        logging.info(f"Successfully wrote: {filepath}")
    except Exception as e:
        logging.error(f"Error writing {filepath}: {e}")
        sys.exit(1)


# --- Main Orchestration ---
def main():
    # 1. Setup Argparse (using config values for defaults)
    default_k_cfg = get_config_value(APP_CONFIG, 'General', 'default_k', fallback=6, value_type=int)
    default_qgen_prefix_cfg = get_config_value(APP_CONFIG, 'Filenames', 'qgen_temp_prefix', fallback="", value_type=str)
    default_mapping_strategy_cfg = get_config_value(APP_CONFIG, 'Study', 'mapping_strategy', fallback='correct')

    parser = argparse.ArgumentParser(
        description="Generates LLM query files and mappings from a source personalities file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter 
    )
    parser.add_argument("-k", type=int, default=default_k_cfg, help="Number of people/descriptions for the query.")
    parser.add_argument("--seed", type=int, default=None, help="Optional random seed for reproducibility.")
    parser.add_argument("--mapping_strategy", default=default_mapping_strategy_cfg, choices=['correct', 'random'],
                        help="The ground truth mapping strategy to use. Overrides config.ini.")
    parser.add_argument("--personalities_file", default=DEFAULT_PERSONALITIES_SRC_FN, help=f"Filename of the source personalities file (expected in data/ dir relative to project root). Default: {DEFAULT_PERSONALITIES_SRC_FN}")
    parser.add_argument("--base_query_file", default=DEFAULT_BASE_QUERY_SRC_FN, help=f"Filename of the base query file (expected in data/ dir relative to project root). Default: {DEFAULT_BASE_QUERY_SRC_FN}")
    parser.add_argument("--output_basename_prefix", default=default_qgen_prefix_cfg, help="Prefix for all output filenames. Can include relative path components from this script's location (e.g., 'temp_outputs/iter_001_'). Default is from config or empty string.")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
    
    args = parser.parse_args()

    # 2. Configure Logging Level (based on CLI -v flags and config)
    # Set log level based on verbosity flags. Default to WARNING.
    if args.verbose == 1:
        log_level_final_qgen = "INFO"
    elif args.verbose >= 2:
        log_level_final_qgen = "DEBUG"
    else:
        log_level_final_qgen = "WARNING" # Default to a quiet level
    numeric_final_log_level = getattr(logging, log_level_final_qgen.upper(), logging.WARNING)
    root_logger = logging.getLogger(); root_logger.setLevel(numeric_final_log_level)
    # ... (ensure handler setup as before) ...
    if not root_logger.hasHandlers() or not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        for handler_old in root_logger.handlers[:]: root_logger.removeHandler(handler_old)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
        root_logger.addHandler(stream_handler)
    else:
        for handler_curr in root_logger.handlers: handler_curr.setLevel(numeric_final_log_level)
    logging.info(f"Query Generator log level set to: {log_level_final_qgen}")


    # 3. Process k_value and seed
    k_value = args.k
    if k_value <= 0: logging.error("k must be a positive integer."); sys.exit(1)
    if args.seed is not None: random.seed(args.seed); logging.info(f"Using random seed: {args.seed}")
    else: logging.info("No random seed specified by user; results will vary each run for this generator.")

    # 4. Determine script directory and resolve INPUT file paths
    script_dir_of_qgen = os.path.dirname(os.path.abspath(__file__)) 
    # Resolve source file paths
    # script_dir_of_qgen is defined earlier as os.path.dirname(os.path.abspath(__file__))
    # PROJECT_ROOT is imported from config_loader

    if args.personalities_file == DEFAULT_TEMP_SUBSET_FN_QGEN:
        # This specific temporary file is expected in script_dir_of_qgen (src/)
        personalities_filepath = os.path.join(script_dir_of_qgen, args.personalities_file)
        logging.info(f"Using temporary subset personalities file: {personalities_filepath}")
    else:
        # All other personalities files are expected in PROJECT_ROOT/data/
        personalities_filepath = os.path.join(PROJECT_ROOT, "data", args.personalities_file)
        logging.info(f"Using master/other personalities file from data dir: {personalities_filepath}")

    # Base query path resolution remains the same
    base_query_filepath = os.path.join(PROJECT_ROOT, "data", args.base_query_file)
    
    # 5. Determine OUTPUT file paths
    user_provided_prefix = args.output_basename_prefix
    output_dir_for_files = "" # Will be determined
    actual_file_prefix_in_dir = ""
    is_orchestrator_temp_output = False

    if user_provided_prefix and (os.path.sep in user_provided_prefix or (os.altsep and os.altsep in user_provided_prefix)):
        dir_part_of_prefix = os.path.dirname(user_provided_prefix)
        # Specific check for build_llm_queries.py's temporary output pattern
        if dir_part_of_prefix.startswith("temp_qgen_outputs_iter_"):
            is_orchestrator_temp_output = True
        
        if is_orchestrator_temp_output:
            # Orchestrator (build_queries) provides a prefix like "temp_subdir/file_prefix_"
            # These temp subdirs are created by build_queries *within src/* (where query_generator runs)
            output_dir_for_files = os.path.join(script_dir_of_qgen, dir_part_of_prefix)
            actual_file_prefix_in_dir = os.path.basename(user_provided_prefix)
            logging.info(f"Orchestrated run: Outputting to temporary directory within 'src/': '{output_dir_for_files}' with prefix '{actual_file_prefix_in_dir}'")
        else:
            # User provided a prefix with path components, not matching orchestrator's temp pattern.
            # Output to <PROJECT_ROOT>/<config:base_output_dir>/<dir_part_of_prefix>/
            cfg_base_output_dir = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback="output")
            resolved_cfg_base_output_dir = os.path.join(PROJECT_ROOT, cfg_base_output_dir)
            output_dir_for_files = os.path.join(resolved_cfg_base_output_dir, dir_part_of_prefix)
            actual_file_prefix_in_dir = os.path.basename(user_provided_prefix)
            logging.info(f"Standalone run with custom path in prefix: Outputting to '{output_dir_for_files}' with prefix '{actual_file_prefix_in_dir}'")
    else: 
        # No path components in prefix (or prefix is empty) -> Standalone run default location
        cfg_base_output_dir = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback="output")
        resolved_cfg_base_output_dir = os.path.join(PROJECT_ROOT, cfg_base_output_dir)
        # Output to "PROJECT_ROOT/output/qgen_standalone_output/" (using configured names)
        output_dir_for_files = os.path.join(resolved_cfg_base_output_dir, DEFAULT_STANDALONE_OUTPUT_SUBDIR_NAME)
        actual_file_prefix_in_dir = user_provided_prefix # This could be "" or "myrun_"
        if actual_file_prefix_in_dir:
            logging.info(f"Standalone run with filename prefix: Outputting to '{output_dir_for_files}' with prefix '{actual_file_prefix_in_dir}'")
        else:
            logging.info(f"Standalone run: Outputting to '{output_dir_for_files}' with no additional file prefix.")


    # Ensure the final base output directory for these files exists
    if not os.path.exists(output_dir_for_files):
        try:
            os.makedirs(output_dir_for_files, exist_ok=True)
            # Log creation only if it was actually created now, not if it already existed.
            logging.info(f"Created output directory: {output_dir_for_files}")
        except OSError as e:
            logging.error(f"Could not create output directory {output_dir_for_files}: {e}"); sys.exit(1)
    
    # 6. Define all output filepaths using the determined directory and prefix
    names_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{NAMES_FILE_SUFFIX}")
    descriptions_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{DESCRIPTIONS_FILE_SUFFIX}")
    shuffled_names_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{SHUFFLED_NAMES_FILE_SUFFIX}")
    shuffled_descriptions_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{SHUFFLED_DESCRIPTIONS_FILE_SUFFIX}")
    mapping_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{MAPPING_FILE_SUFFIX}")
    manifest_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{MANIFEST_FILE_SUFFIX}")
    full_query_out_filepath = os.path.join(output_dir_for_files, f"{actual_file_prefix_in_dir}{FULL_QUERY_FILE_SUFFIX}")

    # 7. Start main processing logs
    logging.info(f"Starting query generation with k={k_value}...")
    # The specific logging about output location is now handled within the if/else block above.


    # 8. Perform operations
    logging.info(f"Loading base query from '{base_query_filepath}'...")
    base_prompt_content = load_base_query(base_query_filepath)

    logging.info(f"Loading personalities from '{personalities_filepath}'...")
    all_personalities = load_personalities(personalities_filepath, k_value)

    selected_items = []
    # If using the temporary subset file, this is an orchestrated run. Assume it has exactly k items.
    # Otherwise, this is a standalone run and we must sample k items from the full database.
    if args.personalities_file == DEFAULT_TEMP_SUBSET_FN_QGEN:
        logging.info("Orchestrated run detected. Using pre-selected subset of personalities.")
        if len(all_personalities) != k_value:
            logging.error(f"Error: Temporary subset file should contain k={k_value} items, but found {len(all_personalities)}.")
            sys.exit(1)

        # Add internal ref ID to the k pre-selected items
        for i, entry in enumerate(all_personalities):
            entry['internal_ref_id'] = i
            selected_items.append(entry)
    else:
        # Standalone mode: Sample k items from the full list.
        logging.info(f"Standalone run detected. Sampling {k_value} items from the {len(all_personalities)} available.")
        # This function handles the sampling and adds the internal_ref_id
        selected_items = select_and_prepare_k_items(all_personalities, k_value)

    if not selected_items:
        logging.error("No items were selected for processing. This should not happen.")
        sys.exit(1)

    logging.info(f"Selected {len(selected_items)} items for processing.")

    # Determine mapping strategy from args (which defaults to config value)
    mapping_strategy = args.mapping_strategy
    logging.info(f"Using mapping strategy: {mapping_strategy}")

    # By default, the items for names and descriptions are the same, ensuring a correct map.
    name_items = selected_items
    description_items = selected_items

    if mapping_strategy == 'random':
        logging.warning("Applying 'random' mapping strategy. The ground truth will be a random permutation.")
        
        # Get the list of original internal reference IDs.
        original_ref_ids = [item['internal_ref_id'] for item in selected_items]
        
        # Shuffle these reference IDs using the script's seeded random state.
        random.shuffle(original_ref_ids)
        
        # Create a new list of items for the descriptions. Each original item
        # is now paired with a RANDOMLY chosen reference ID. This breaks the
        # original name-to-description link while keeping the sets of names and descriptions identical.
        description_items = []
        for i, item in enumerate(selected_items):
            new_item = item.copy()
            new_item['internal_ref_id'] = original_ref_ids[i]
            description_items.append(new_item)

    logging.info("Writing intermediate files...")
    names_data_rows = [[i + 1, item['name'], item['year']] for i, item in enumerate(name_items)]
    write_tab_separated_file(names_out_filepath, "Seq\tName\tBirthYear", names_data_rows)
    
    descriptions_data_rows = [[i + 1, item['description']] for i, item in enumerate(description_items)]
    write_tab_separated_file(descriptions_out_filepath, "Seq\tDescriptionText", descriptions_data_rows)

    logging.info("Creating shuffled files, mapping, and manifest file...")
    shuffled_name_year_list = create_shuffled_names_file(name_items, shuffled_names_out_filepath)
    shuffled_description_list = create_shuffled_descriptions_file(description_items, shuffled_descriptions_out_filepath, k_value)
    create_mapping_file(shuffled_name_year_list, shuffled_description_list, mapping_out_filepath, k_value)
    
    # Create a lookup map from description text to its original, pre-randomization ref ID.
    # This is necessary for the manifest to report the true original ID for a description.
    desc_text_to_original_id_map = {item['description']: item['internal_ref_id'] for item in selected_items}
    create_manifest_file(shuffled_name_year_list, shuffled_description_list, manifest_out_filepath, k_value, desc_text_to_original_id_map)

    logging.info(f"Assembling final query file '{os.path.basename(full_query_out_filepath)}'...")
    assemble_full_query(base_prompt_content, shuffled_name_year_list, shuffled_description_list, full_query_out_filepath, k_value)

    # 9. Final summary logs
    logging.info("\nQuery generation process complete.")
    logging.info(f"  - Input personalities used: {personalities_filepath}")
    logging.info(f"  - Input base query used: {base_query_filepath}")
    logging.info(f"  Generated files in: {os.path.abspath(output_dir_for_files)}") # Use the resolved output_dir_for_files
    output_file_list_paths = [
        names_out_filepath, descriptions_out_filepath,
        shuffled_names_out_filepath, shuffled_descriptions_out_filepath,
        mapping_out_filepath, manifest_out_filepath, full_query_out_filepath
    ]
    for fpath in output_file_list_paths:
        logging.info(f"    - {os.path.basename(fpath)}")

if __name__ == "__main__":
    main()

# === End of src/query_generator.py ===
