#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/process_llm_responses.py

"""
Process LLM Responses Script (process_llm_responses.py)

Purpose:
This script processes raw text responses from the LLM, parses them to extract
score matrices, and prepares these matrices along with validated ground truth
mappings for the final analysis stage.

Workflow (when called by orchestrator):
1.  Receives the path to a unique run directory via the `--run_output_dir` argument.
2.  Creates an `analysis_inputs` subdirectory inside the run directory.
3.  Reads response files from `<run_output_dir>/session_responses/`.
4.  For each successful response, it performs a **validation step**: it reads the
    master `mappings.txt` from `<run_output_dir>/session_queries/` and cross-references
    the relevant line against the corresponding `llm_query_XXX_manifest.txt` file.
5.  Only validated mappings are used.
6.  It aggregates all successfully parsed score matrices into `all_scores.txt`
    and the validated, filtered mappings into `all_mappings.txt`, both inside the
    run-specific `analysis_inputs` directory.
7.  It also creates `successful_query_indices.txt` for the final validation stage.

Input Files (within the provided `<run_output_dir>`):
- `<run_output_dir>/session_responses/llm_response_XXX.txt`
- `<run_output_dir>/session_queries/llm_query_XXX.txt`
- `<run_output_dir>/session_queries/llm_query_XXX_manifest.txt`
- `<run_output_dir>/session_queries/mappings.txt`

Output Files (within the provided `<run_output_dir>`):
- `<run_output_dir>/analysis_inputs/all_scores.txt`
- `<run_output_dir>/analysis_inputs/all_mappings.txt` (Validated)
- `<run_output_dir>/analysis_inputs/successful_query_indices.txt`

Command-Line Usage (for orchestrated runs):
    python src/process_llm_responses.py --run_output_dir <path_to_run_dir> [options]
"""

# === Start of src/process_llm_responses.py ===

import argparse
import os
import sys
import glob
import logging
import re
import numpy as np
import shutil

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    current_script_dir = os.path.dirname(os.path.abspath(__file__))
    if current_script_dir not in sys.path: sys.path.insert(0, current_script_dir)
    try:
        from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
    except ImportError:
        project_root_for_loader = os.path.dirname(current_script_dir)
        if project_root_for_loader not in sys.path: sys.path.insert(0, project_root_for_loader)
        from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT

DEFAULT_LOG_LEVEL_PROC = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')
numeric_log_level_proc = getattr(logging, DEFAULT_LOG_LEVEL_PROC.upper(), logging.INFO)
logging.basicConfig(level=numeric_log_level_proc,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

def normalize_text_for_llm(text):
    """
    Normalizes text to a simple ASCII representation to prevent encoding issues.
    This function must be identical to the one in query_generator.py.
    """
    import unicodedata
    try:
        # Decompose unicode characters (e.g., 'è' -> 'e' + '`'), then encode to ASCII, ignoring non-ASCII marks.
        return unicodedata.normalize('NFKD', str(text)).encode('ascii', 'ignore').decode('ascii')
    except (TypeError, AttributeError):
        return str(text) # Return original if not a string or fails

def filter_mappings_by_index(source_mapping_path, dest_mapping_path, successful_indices, queries_dir_for_manifests):
    """
    Reads a source mappings file, filters it to include only mappings for successful
    indices, validates each mapping against its manifest, and writes the result.
    """
    logging.info(f"Filtering and validating mappings for {len(successful_indices)} successful responses.")
    validation_errors = 0
    try:
        # Read all source mappings into memory for easy access by index
        with open(source_mapping_path, 'r', encoding='utf-8') as f_in:
            source_header = f_in.readline()
            source_mappings = f_in.readlines()  # 0-indexed list for 1-indexed lines

        with open(dest_mapping_path, 'w', encoding='utf-8') as f_out:
            if not source_header:
                logging.warning(f"Source mappings file '{source_mapping_path}' is empty or has no header.")
                return False
            f_out.write(source_header)  # Write header to the new file

            for index in sorted(successful_indices):
                # --- Validation Step ---
                manifest_path = os.path.join(queries_dir_for_manifests, f"llm_query_{index:03d}_manifest.txt")
                
                # Check if the index is valid for the source_mappings list
                if index > len(source_mappings):
                    logging.error(f"  VALIDATION FAIL: Index {index} is out of bounds for the source mappings file (size: {len(source_mappings)}).")
                    validation_errors += 1
                    continue
                
                map_line_from_source = source_mappings[index - 1].strip()  # Get the specific line
                
                if not os.path.exists(manifest_path):
                    logging.error(f"  VALIDATION FAIL: Manifest file not found for index {index} at '{manifest_path}'. Cannot validate.")
                    validation_errors += 1
                    continue  # Skip writing this mapping if manifest is missing
                
                try:
                    with open(manifest_path, 'r', encoding='utf-8') as f_manifest:
                        manifest_lines = f_manifest.read().strip().split('\n')
                    
                    if len(manifest_lines) < 2:
                        logging.error(f"  VALIDATION ERROR: Manifest for index {index} is empty or has no data rows.")
                        validation_errors += 1
                        continue

                    # Extract the 'Shuffled_Desc_Index' column from the manifest
                    manifest_indices = [line.split('\t')[2] for line in manifest_lines[1:]]
                    manifest_indices_str = "\t".join(manifest_indices)

                    if map_line_from_source == manifest_indices_str:
                        logging.debug(f"  VALIDATION OK: Mapping for index {index} matches its manifest.")
                        f_out.write(map_line_from_source + "\n")
                    else:
                        logging.error(f"  VALIDATION FAIL: Mismatch for index {index}!")
                        logging.error(f"    - From mappings.txt: {map_line_from_source}")
                        logging.error(f"    - From manifest.txt: {manifest_indices_str}")
                        validation_errors += 1
                except IndexError:
                    logging.error(f"  VALIDATION ERROR: Could not parse manifest for index {index}. It may have incorrect column count.")
                    validation_errors += 1
                except Exception as e:
                    logging.error(f"  VALIDATION ERROR: An unexpected error occurred while processing manifest for index {index}: {e}")
                    validation_errors += 1

        if validation_errors > 0:
            # Use print for critical errors to ensure visibility and capture
            print(f"\nCRITICAL: PROCESSOR VALIDATION FAILED WITH {validation_errors} ERRORS.\n")
            return False

        # Print a clear success message for the orchestrator to find
        print("\nPROCESSOR_VALIDATION_SUCCESS\n")
        logging.info(f"Successfully wrote validated and filtered mappings to '{dest_mapping_path}'.")
        return True

    except FileNotFoundError:
        logging.error(f"Could not find a required source file. Source mappings: '{source_mapping_path}'.")
        return False
    except Exception as e:
        logging.error(f"A critical error occurred during the mapping filter/validation process: {e}", exc_info=True)
        return False

def get_list_a_details_from_query(query_filepath):
    """
    Determines 'k' and extracts the ordered list of List A item names
    from a llm_query_XXX.txt file.
    """
    try:
        with open(query_filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        in_list_a = False
        list_a_items = []
        for line in lines:
            stripped_line = line.strip()
            if not stripped_line:
                continue
            if stripped_line.lower() == "list a":
                in_list_a = True
                continue
            if stripped_line.lower() == "list b":
                # List A section ends
                in_list_a = False # Set this to false so we don't accidentally pick up List B items
                break 
            if in_list_a and stripped_line:
                list_a_items.append(stripped_line) # These are "Name (Year)"
        
        k = len(list_a_items)
        if k > 0:
            return k, list_a_items
        else:
            # Fallback: try counting List B items if List A parsing failed, but List A names are needed.
            # This part of fallback is less useful if names are essential for row mapping.
            logging.warning(f"Could not determine k/List A items from List A section in {query_filepath}.")
            return None, []
    except FileNotFoundError:
        logging.error(f"Query file not found for k-determination: {query_filepath}")
        return None, []
    except Exception as e:
        logging.error(f"Error reading query file {query_filepath} for k-determination: {e}")
        return None, []

def get_core_name(name_with_details):
    """
    Extracts a 'core' name part for matching, e.g., from "Some Name (1990)" -> "some name".
    This helps match LLM output names to query names if there are minor formatting differences.
    Adjust regex as needed for your specific name format.
    """
    name = name_with_details
    # 1. Remove (YYYY) or (YYYY-YYYY) from the end of the string
    name = re.sub(r'\s*\(\d{4}(?:-\d{2,4})?\)$', '', name)
    
    # 2. Normalize to plain ASCII to handle Unicode differences (e.g., Dieudonné vs Dieudonne)
    name = normalize_text_for_llm(name)

    # 3. Optional: Remove very specific prefixes if they are expected from LLM or query.
    #    For example, if List A items are always "Item N: Actual Name", you could strip "Item N: ".
    #    The current test data like "Person A (1900)" does not require aggressive prefix stripping
    #    that would remove "Person A". If the LLM might add "Speaker A: Person A (1900)", then
    #    a prefix stripper would be needed. For now, let's assume names are relatively clean
    #    after year removal.
    # Example of a more targeted prefix removal (if needed):
    # name = re.sub(r'^(?:item\s+\d+:\s*|speaker\s+\w+:\s*)', '', name, flags=re.IGNORECASE)

    return name.strip().lower()


def parse_llm_response_table_to_matrix(response_text, k_value, list_a_names_ordered_from_query, is_rank_based=False):
    """
    Parses LLM response text, handling various table formats including tab-separated,
    pipe-delimited (Markdown), and backslash-delimited, with or without headers
    and optional code fences.
    """
    table_text = response_text
    code_block_match = re.search(r"```(?:[a-zA-Z]+\n)?(.*?)```", response_text, re.DOTALL)
    if code_block_match:
        logging.debug("  Found a fenced code block. Parsing content within it.")
        table_text = code_block_match.group(1).strip()

    lines = [line.strip() for line in table_text.strip().split('\n') if line.strip()]
    if not lines: return np.full((k_value, k_value), 0.0)

    # Detect delimiter
    delimiter = '\t' # Default
    if '|' in lines[0] and len(lines[0].split('|')) > k_value / 2:
        delimiter = '|'
    elif '\\' in lines[0] and len(lines[0].split('\\')) > k_value / 2:
        delimiter = '\\'

    score_matrix = np.full((k_value, k_value), 0.0)
    query_list_a_core_names_map = {get_core_name(name): i for i, name in enumerate(list_a_names_ordered_from_query)}
    filled_row_indices = [False] * k_value
    
    data_lines = []
    header_found = False
    for line in lines:
        if '---' in line and delimiter == '|': continue
        
        # A simple header check: does it contain "ID" and not start with a number?
        is_header = "ID" in line and not line.lstrip(' |').strip()[0].isdigit()
        if is_header and not header_found:
            header_found = True
            continue
        data_lines.append(line)

    for line_content in data_lines:
        if len(filled_row_indices) == sum(filled_row_indices): break # Matrix is full

        parts = [p.strip() for p in line_content.strip(' |').split(delimiter)]
        
        # Determine if the row starts with a name label or just scores
        try:
            float(parts[0])
            has_name_label = False
            score_strings = parts
        except (ValueError, IndexError):
            has_name_label = True
            llm_person_name_raw = parts[0]
            score_strings = parts[1:]
        
        if len(score_strings) != k_value:
            logging.warning(f"  Row has {len(score_strings)} scores, expected {k_value}. Skipping row: '{line_content}'")
            continue
        
        # Find the correct row in the matrix to place the scores
        matrix_row_idx = -1
        unfilled_indices = [i for i, filled in enumerate(filled_row_indices) if not filled]
        if not unfilled_indices: continue

        if has_name_label:
            core_llm_name = get_core_name(llm_person_name_raw)
            if core_llm_name in query_list_a_core_names_map:
                matrix_row_idx = query_list_a_core_names_map[core_llm_name]
                if filled_row_indices[matrix_row_idx]:
                    logging.warning(f"  Duplicate List A item name '{llm_person_name_raw}' found. Skipping row.")
                    continue
            else:
                matrix_row_idx = unfilled_indices[0] # Fallback to sequential
                logging.warning(f"  LLM name '{llm_person_name_raw}' not matched. Assigning sequentially.")
        else:
            matrix_row_idx = unfilled_indices[0] # No name, must be sequential
            
        try:
            numerical_scores = [float(s) for s in score_strings]
            processed_scores = [float(k_value - r + 1) if 1 <= r <= k_value else 0.0 for r in numerical_scores] if is_rank_based else numerical_scores
            score_matrix[matrix_row_idx, :] = processed_scores
            filled_row_indices[matrix_row_idx] = True
        except (ValueError, IndexError) as e:
            logging.warning(f"  Could not parse scores in row: '{score_strings}'. Error: {e}. Skipping.")
            continue
            
    if sum(filled_row_indices) < k_value:
        logging.warning(f"  Parsed only {sum(filled_row_indices)} data rows for a k={k_value} matrix.")
        
    return score_matrix


def main():
    parser = argparse.ArgumentParser(description="Processes LLM responses into score matrices for analysis.")
    parser.add_argument("--llm_output_ranks", action="store_true", help="Set if LLM output is ranks (1=best) not direct scores, to be converted.")
    parser.add_argument("--score_format", type=str, default=".2f", help="Format string for scores in output file, e.g., '.2f' for 2 decimal places (default: .2f).")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
    parser.add_argument("--run_output_dir", required=True, help="The absolute path to the self-contained output directory for this specific run.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-response progress messages.")

    args = parser.parse_args()

    # --- Adjust Log Level ---
    log_level_final_proc = DEFAULT_LOG_LEVEL_PROC
    if args.verbose == 1: log_level_final_proc = "INFO"
    elif args.verbose >= 2: log_level_final_proc = "DEBUG"
    numeric_final_log_level = getattr(logging, log_level_final_proc.upper(), logging.INFO)
    logging.getLogger().setLevel(numeric_final_log_level)
    for handler in logging.getLogger().handlers: handler.setLevel(numeric_final_log_level)
    logging.info(f"Response Processor log level set to: {log_level_final_proc}")

    # --- NEW: Path Resolution based on run_output_dir ---
    responses_subdir_cfg = get_config_value(APP_CONFIG, 'General', 'responses_subdir', fallback="session_responses")
    queries_subdir_cfg = get_config_value(APP_CONFIG, 'General', 'queries_subdir', fallback="session_queries")
    analysis_inputs_subdir_cfg = get_config_value(APP_CONFIG, 'General', 'analysis_inputs_subdir', fallback="analysis_inputs")

    responses_dir = os.path.join(args.run_output_dir, responses_subdir_cfg)
    queries_dir = os.path.join(args.run_output_dir, queries_subdir_cfg)
    analysis_inputs_dir = os.path.join(args.run_output_dir, analysis_inputs_subdir_cfg)

    # Clean up old analysis inputs directory if it exists to ensure a clean re-run
    if os.path.exists(analysis_inputs_dir):
        logging.warning(f"Found existing analysis directory. Removing for a clean re-run: {analysis_inputs_dir}")
        shutil.rmtree(analysis_inputs_dir)

    os.makedirs(analysis_inputs_dir, exist_ok=True)
    logging.info(f"Reading LLM responses from: {responses_dir}")
    logging.info(f"Reading original queries from: {queries_dir}")
    logging.info(f"Writing processed outputs to: {analysis_inputs_dir}")
    if args.llm_output_ranks:
        logging.info("LLM output will be treated as ranks (1=best) and converted to scores.")

    # --- Main Processing Loop ---
    # The rest of the function (finding files, parsing, etc.) remains the same
    # as it now uses the correctly defined directory variables.
    response_files_pattern = os.path.join(responses_dir, "llm_response_*.txt")
    response_files = sorted(glob.glob(response_files_pattern))

    if not response_files:
        logging.warning(f"No response files found matching '{response_files_pattern}'. Exiting."); sys.exit(0)
    logging.info(f"Found {len(response_files)} LLM response files to process.")

    all_parsed_score_matrices = []; successful_indices = []; processed_count = 0; error_count = 0

    for resp_filepath in response_files:
        base_filename = os.path.basename(resp_filepath)
        match = re.search(r"llm_response_(\d+)\.txt", base_filename)
        if not match:
            logging.warning(f"Could not parse index from response filename: {base_filename}. Skipping.")
            continue

        query_index_str = match.group(1)
        query_index_int = int(query_index_str)
        
        if not args.quiet:
            logging.info(f"Processing response file: {base_filename} (Index: {query_index_str})")

        query_filename = f"llm_query_{query_index_str}.txt"
        query_filepath = os.path.join(queries_dir, query_filename)

        k, list_a_names = get_list_a_details_from_query(query_filepath)
        if k is None or not list_a_names or len(list_a_names) != k:
            logging.error(f"  Could not determine k or List A names for query {query_index_str} (k={k}, names found={len(list_a_names)}). Skipping.")
            error_count += 1
            continue
        
        if not args.quiet:
            logging.info(f"  Determined k = {k} for this query. List A names retrieved.")

        try:
            with open(resp_filepath, 'r', encoding='utf-8') as f_resp: response_content = f_resp.read()
            if not response_content.strip():
                logging.warning(f"  Response file {base_filename} is empty. Generating matrix with default scores (0.0).")
                score_matrix = np.full((k, k), 0.0)
            else:
                score_matrix = parse_llm_response_table_to_matrix(response_content, k, list_a_names, args.llm_output_ranks)
            
            all_parsed_score_matrices.append(score_matrix)
            successful_indices.append(query_index_int)
            processed_count += 1; logging.debug(f"  Successfully parsed. Matrix shape: {score_matrix.shape}")

        except FileNotFoundError: logging.error(f"  Response file not found: {resp_filepath}. Skipping."); error_count += 1
        except Exception as e: logging.error(f"  Error processing response file {base_filename}: {e}", exc_info=True); error_count += 1
            
    all_scores_output_filename = get_config_value(APP_CONFIG, 'Filenames', 'all_scores_for_analysis', fallback="all_scores.txt")
    all_scores_output_path = os.path.join(analysis_inputs_dir, all_scores_output_filename)
    
    if all_parsed_score_matrices:
        try:
            with open(all_scores_output_path, 'w', encoding='utf-8') as f_out:
                for i, matrix in enumerate(all_parsed_score_matrices):
                    if i > 0: f_out.write("\n") 
                    for row in matrix: f_out.write("\t".join(map(lambda x: f"{x:{args.score_format}}", row)) + "\n")
            logging.info(f"Successfully wrote {len(all_parsed_score_matrices)} score matrices to {all_scores_output_path}")
        except IOError as e: logging.error(f"Error writing aggregated scores to {all_scores_output_path}: {e}")
    else:
        logging.warning(f"No score matrices were successfully parsed. '{all_scores_output_path}' will not be created or will be empty.")

    source_mappings_filename = get_config_value(APP_CONFIG, 'Filenames', 'aggregated_mappings_in_queries_dir', fallback="mappings.txt")
    source_mappings_path = os.path.join(queries_dir, source_mappings_filename)
    dest_mappings_filename = get_config_value(APP_CONFIG, 'Filenames', 'all_mappings_for_analysis', fallback="all_mappings.txt")
    dest_mappings_path = os.path.join(analysis_inputs_dir, dest_mappings_filename)

    # Capture the return value of the validation function
    validation_passed = filter_mappings_by_index(source_mappings_path, dest_mappings_path, successful_indices, queries_dir)

    # If validation fails, halt the entire process.
    if not validation_passed:
        logging.critical("Halting due to critical validation failures.")
        sys.exit(1)

    # Create the successful indices file for the analyzer to use for validation
    successful_indices_filename = get_config_value(APP_CONFIG, 'Filenames', 'successful_indices_log', fallback="successful_query_indices.txt")
    successful_indices_path = os.path.join(analysis_inputs_dir, successful_indices_filename)
    try:
        with open(successful_indices_path, 'w', encoding='utf-8') as f_indices:
            for index in sorted(successful_indices): f_indices.write(f"{index}\n")
        logging.info(f"Successfully wrote {len(successful_indices)} successful indices to {successful_indices_path}")
    except IOError as e:
        logging.error(f"Error writing successful indices file to {successful_indices_path}: {e}")

    logging.info(f"Processing complete. Successfully processed: {processed_count}, Errors/Skipped: {error_count}")

    # Add a machine-readable summary for the orchestrator to capture.
    # Format: <<<PARSER_SUMMARY:processed_count:total_files_found>>>
    print(f"\n<<<PARSER_SUMMARY:{processed_count}:{len(response_files)}>>>\n")

if __name__ == "__main__":
    main()

# === End of src/process_llm_responses.py ===