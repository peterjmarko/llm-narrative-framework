#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: src/process_llm_responses.py

"""
Stage 3: LLM Response Parser and Validator.

This script is the critical data-cleaning stage of the pipeline. It takes the
raw, potentially inconsistent text responses from the LLM and transforms them
into clean, validated, and structured numerical data ready for analysis.

Key Features:
-   **Simplified Matrix Extraction**: Identifies exactly k consecutive lines containing
    exactly k numeric values at the end of each line, extracting k×k score matrices.
    Includes preprocessing to handle mixed formatting (removes "|" characters with
    adjacent tabs) while maintaining focus on measuring true LLM performance.
-   **Rank Conversion Support**: Preserves `is_rank_based` parameter for legitimate
    experimental conditions where LLM outputs ranks instead of scores.
-   **Parsing Diagnostics**: Generates detailed parsing summaries showing success/failure
    status for each response, saved to `parsing_summary.txt` and included in
    replication reports for troubleshooting.
-   **Ground-Truth Validation**: Before accepting a trial's data, it performs a
    critical validation by cross-referencing the master `mappings.txt` against
    the individual trial's `manifest.txt`, ensuring data integrity.
-   **Output Self-Validation**: After writing the final `all_scores.txt`, it
    performs a "read-after-write" check to validate the file's content against
    the in-memory data, preventing data corruption.
-   **Clear Orchestration Signals**: Prints machine-readable tags upon success
    (e.g., `PROCESSOR_VALIDATION_SUCCESS`) for the calling script to interpret.

This script's rigorous validation ensures that the final performance analysis
is built upon a foundation of verifiably correct data while measuring actual
LLM capabilities rather than parser-corrected performance.
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
import pandas as pd
from io import StringIO
import unicodedata

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

# REMOVED: The top-level DEFAULT_LOG_LEVEL_PROC and logging.basicConfig call.
# These will now be handled inside main() after args are parsed.

def normalize_text_for_llm(text):
    """
    Normalizes text to a simple ASCII representation to prevent encoding issues.
    This function must be identical to the one in query_generator.py.
    """
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

def parse_llm_response_table_to_matrix(response_text, k_value, list_a_names_ordered_from_query, is_rank_based=False):
    """
    Extracts a k x k numerical score matrix from LLM response text.
    
    Finds exactly k consecutive lines that each contain exactly k numeric values at the end.
    """
    warning_count = 0
    is_rejected = False

    try:
        # Get all non-empty lines
        all_lines = [line.strip() for line in response_text.split('\n') if line.strip()]
        
        if len(all_lines) < k_value:
            logging.error(f"Insufficient lines: found {len(all_lines)}, need at least {k_value}")
            return np.full((k_value, k_value), 0.0), 1, True

        # Find k consecutive lines with exactly k numeric values at the end of each line
        for start_idx in range(len(all_lines) - k_value + 1):
            candidate_lines = all_lines[start_idx:start_idx + k_value]
            valid_rows = []
            
            # Check if all k lines have exactly k numeric values at the end
            for line in candidate_lines:
                # Preprocessing: Remove any "|" characters together with adjacent tabs
                cleaned_line = re.sub(r'\t*\|\t*', ' ', line)
                
                # Split by any whitespace
                parts = cleaned_line.replace('\t', ' ').split()
                
                if len(parts) < k_value:
                    break  # Not enough parts on this line
                
                # Extract last k parts and try to convert to floats
                last_k_parts = parts[-k_value:]
                try:
                    scores = [float(part) for part in last_k_parts]
                    valid_rows.append(scores)
                except ValueError:
                    break  # Non-numeric data in last k positions
            
            # If we found exactly k valid rows, we have our matrix
            if len(valid_rows) == k_value:
                score_matrix = np.array(valid_rows)
                
                # Convert ranks to scores if needed
                if is_rank_based:
                    if k_value == 1:
                        score_matrix = np.ones((1, 1))  # Single rank maps to 1.0
                    else:
                        score_matrix = (k_value - score_matrix) / (k_value - 1)
                else:
                    # Reject if any score is out of [0, 1] range
                    if np.any((score_matrix < 0.0) | (score_matrix > 1.0)):
                        logging.error(f"Score out of range [0, 1] detected")
                        return np.full((k_value, k_value), 0.0), 1, True

                logging.debug(f"Successfully parsed {k_value}x{k_value} matrix from lines {start_idx+1}-{start_idx+k_value}")
                return score_matrix, warning_count, is_rejected

        # If we get here, no valid k×k block was found
        logging.error(f"No valid {k_value}×{k_value} block found in response")
        return np.full((k_value, k_value), 0.0), 1, True

    except Exception as e:
        logging.error(f"Unexpected parsing error: {e}")
        return np.full((k_value, k_value), 0.0), 1, True

def validate_all_scores_file_content(filepath, expected_matrices_map, k_value):
    """
    Validates the content of the generated all_scores.txt file against in-memory parsed matrices.
    
    Args:
        filepath (str): Path to the all_scores.txt file.
        expected_matrices_map (dict): A dictionary mapping query_index (int) to the
                                      expected k x k numpy array.
        k_value (int): The expected dimension (k) of the square matrices.

    Returns:
        bool: True if validation passes, False otherwise.
    """
    logging.info(f"Starting cross-validation of '{filepath}'...")
    validation_errors = 0
    loaded_matrices = []

    # A simplified reader for the clean all_scores.txt format
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            current_matrix_rows = []
            for line_num, line_content in enumerate(f, 1):
                line = line_content.strip()
                if not line: # Blank line indicates end of a matrix
                    if current_matrix_rows:
                        try:
                            matrix = np.array(current_matrix_rows, dtype=float)
                            loaded_matrices.append(matrix)
                        except ValueError:
                            logging.error(f"  VALIDATION FAIL: Non-float data in loaded matrix from '{filepath}' near line {line_num-1}. Skipping this matrix.")
                            validation_errors += 1
                        current_matrix_rows = []
                    continue
                
                parts = line.split('\t') # Assume tab-separated for clean output
                try:
                    row_data = [float(p) for p in parts]
                    current_matrix_rows.append(row_data)
                except ValueError:
                    logging.error(f"  VALIDATION FAIL: Malformed line in '{filepath}' at line {line_num}. Expected floats, saw '{line}'. Skipping this row.")
                    validation_errors += 1
            
            # Handle the last matrix if file doesn't end with a blank line
            if current_matrix_rows:
                try:
                    matrix = np.array(current_matrix_rows, dtype=float)
                    loaded_matrices.append(matrix)
                except ValueError:
                    logging.error(f"  VALIDATION FAIL: Non-float data in last loaded matrix from '{filepath}'. Skipping this matrix.")
                    validation_errors += 1

    except FileNotFoundError:
        logging.error(f"  VALIDATION FAIL: '{filepath}' not found for validation.")
        return False
    except Exception as e:
        logging.error(f"  VALIDATION FAIL: Unexpected error reading '{filepath}': {e}", exc_info=True)
        return False

    # 1. Count Check
    if len(loaded_matrices) != len(expected_matrices_map):
        logging.error(f"  VALIDATION FAIL: Mismatch in total matrix count. Loaded {len(loaded_matrices)}, Expected {len(expected_matrices_map)}.")
        validation_errors += 1

    # Sort expected matrices by index for consistent comparison
    sorted_expected_items = sorted(expected_matrices_map.items(), key=lambda item: item[0])

    # 2. Shape and Content Fidelity Check
    for i, (expected_idx, expected_matrix) in enumerate(sorted_expected_items):
        if i >= len(loaded_matrices):
            logging.warning(f"  VALIDATION WARNING: No loaded matrix found for expected index {expected_idx}. (Already reported count mismatch).")
            break # Already past the end of loaded_matrices

        loaded_matrix = loaded_matrices[i]

        # Shape check
        if loaded_matrix.shape != (k_value, k_value):
            logging.error(f"  VALIDATION FAIL: Matrix {i+1} (expected index {expected_idx}) has incorrect shape. Loaded {loaded_matrix.shape}, Expected ({k_value},{k_value}).")
            validation_errors += 1
        
        # Content check (using allclose for float comparisons)
        # We need to ensure both matrices are of the same shape before comparing
        if loaded_matrix.shape == expected_matrix.shape:
            if not np.allclose(loaded_matrix, expected_matrix, atol=1e-6): # Using a small absolute tolerance for floats
                logging.error(f"  VALIDATION FAIL: Content mismatch for matrix {i+1} (expected index {expected_idx}).")
                # Optionally, print diffs for debugging:
                # logging.debug(f"    Expected:\n{expected_matrix}\n    Loaded:\n{loaded_matrix}\n    Diff:\n{expected_matrix - loaded_matrix}")
                validation_errors += 1
        else:
            # Shape mismatch already reported, but ensure this doesn't cause another error
            logging.error(f"  VALIDATION FAIL: Cannot compare content for matrix {i+1} (expected index {expected_idx}) due to shape mismatch.")
            validation_errors += 1
            
    if validation_errors > 0:
        print(f"\nCRITICAL: ALL_SCORES_FILE_VALIDATION FAILED WITH {validation_errors} ERRORS.\n")
        return False
    
    logging.info(f"Successfully cross-validated '{filepath}'. All checks passed.")
    print("\nALL_SCORES_FILE_VALIDATION_SUCCESS\n")
    return True


def main():
    parser = argparse.ArgumentParser(description="Processes LLM responses into score matrices for analysis.")
    parser.add_argument("--llm_output_ranks", action="store_true", help="Set if LLM output is ranks (1=best) not direct scores, to be converted.")
    parser.add_argument("--score_format", type=str, default=".2f", help="Format string for scores in output file, e.g., '.2f' for 2 decimal places (default: .2f).")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
    parser.add_argument("--run_output_dir", required=True, help="The absolute or relative path to the self-contained output directory for this specific run.")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-response progress messages.")

    args = parser.parse_args()

    # Define DEFAULT_LOG_LEVEL_PROC here, after APP_CONFIG is loaded and args are parsed
    DEFAULT_LOG_LEVEL_PROC = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')

    # --- Adjust Log Level ---
    # Determine the base log level based on --quiet and --verbose flags.
    if args.quiet:
        # If quiet, suppress INFO and DEBUG messages, only show WARNING and above
        log_level_to_set = logging.WARNING # Directly set to WARNING for quiet mode
    elif args.verbose == 1:
        log_level_to_set = logging.INFO
    elif args.verbose >= 2:
        log_level_to_set = logging.DEBUG
    else:
        # Default level if not quiet and no verbose flags are set
        # This will only be used if neither --quiet nor -v is specified
        log_level_to_set = getattr(logging, get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO').upper(), logging.INFO)
    
    root_logger = logging.getLogger()
    
    # Clear existing handlers to prevent duplicate messages or inherited levels
    # This is crucial for subprocesses to fully control their logging output
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
        root_logger.handlers = [] # Ensure the list is empty

    # Add a new StreamHandler if none exist after clearing (or if it was explicitly cleared)
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    
    # Set the level for the root logger and all its handlers
    root_logger.setLevel(log_level_to_set)
    for handler in root_logger.handlers:
        handler.setLevel(log_level_to_set)

    # Only log the confirmation message if not in quiet mode
    if not args.quiet:
        logging.info(f"Response Processor log level set to: {logging.getLevelName(log_level_to_set)}")

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

    all_parsed_score_matrices = []
    successful_indices = []
    processed_count = 0
    error_count = 0
    total_parsing_warnings = 0 # This line should already be there from the previous step

    # NEW: Dictionary to store successfully parsed matrices for validation
    parsed_matrices_for_validation = {}

    for resp_filepath in response_files:
        base_filename = os.path.basename(resp_filepath)
        match = re.search(r"llm_response_(\d+)\.txt", base_filename)
        if not match:
            logging.warning(f"Could not parse index from response filename: {base_filename}. Skipping.")
            continue

        query_index_str = match.group(1)
        query_index_int = int(query_index_str)
        
        # This logging.info will now respect the --quiet flag because handlers are cleared.
        if not args.quiet:
            logging.info(f"Processing response file: {base_filename} (Index: {query_index_str})")

        query_filename = f"llm_query_{query_index_str}.txt"
        query_filepath = os.path.join(queries_dir, query_filename)

        k, list_a_names = get_list_a_details_from_query(query_filepath)
        if k is None or not list_a_names or len(list_a_names) != k:
            logging.error(f"  Could not determine k or List A names for query {query_index_str} (k={k}, names found={len(list_a_names)}). Skipping.")
            error_count += 1
            continue
        
        # This logging.info will now respect the --quiet flag.
        if not args.quiet:
            logging.info(f"  Determined k = {k} for this query. List A names retrieved.")

        try:
            with open(resp_filepath, 'r', encoding='utf-8') as f_resp: response_content = f_resp.read()
            
            score_matrix = np.full((k, k), 0.0) # Default to zero matrix
            response_warnings = 0
            current_response_rejected = False

            if not response_content.strip():
                logging.warning(f"  Response {base_filename}: EMPTY - contains no content")
                response_warnings = 1
                current_response_rejected = True # Empty response is a rejection
            else:
                score_matrix, response_warnings, current_response_rejected = parse_llm_response_table_to_matrix(
                    response_content, k, list_a_names, args.llm_output_ranks
                )
            
            total_parsing_warnings += response_warnings # Aggregate warnings from this response

            if current_response_rejected:
                logging.error(f"  Response {base_filename}: REJECTED - parsing failed")
                error_count += 1
                # Do NOT add to all_parsed_score_matrices or successful_indices
            else:
                all_parsed_score_matrices.append(score_matrix)
                successful_indices.append(query_index_int)
                processed_count += 1
                # Store the parsed matrix in the dictionary for validation
                parsed_matrices_for_validation[query_index_int] = score_matrix
                logging.info(f"  Response {base_filename}: SUCCESS - parsed {k}x{k} matrix")

        except FileNotFoundError:
            logging.error(f"  Response file not found: {resp_filepath}. Skipping."); error_count += 1
        except Exception as e:
            logging.error(f"  Error processing response file {base_filename}: {e}", exc_info=True); error_count += 1
            
    all_scores_output_filename = get_config_value(APP_CONFIG, 'Filenames', 'all_scores_for_analysis', fallback="all_scores.txt")
    all_scores_output_path = os.path.join(analysis_inputs_dir, all_scores_output_filename)

    try:
        # Always create the file to ensure a consistent state for downstream scripts.
        with open(all_scores_output_path, 'w', encoding='utf-8') as f_out:
            if all_parsed_score_matrices:
                for i, matrix in enumerate(all_parsed_score_matrices):
                    if i > 0: f_out.write("\n")
                    for row in matrix: f_out.write("\t".join(map(lambda x: f"{x:{args.score_format}}", row)) + "\n")
                logging.info(f"Successfully wrote {len(all_parsed_score_matrices)} score matrices to {all_scores_output_path}")
            else:
                # This block runs inside the 'with open...' context.
                # The file is created but remains empty, which is the desired behavior.
                logging.warning(f"No score matrices were successfully parsed. Creating empty file at '{all_scores_output_path}'.")

        # After writing, whether empty or not, run validation only if there's data to validate.
        if all_parsed_score_matrices:
            scores_file_validation_passed = validate_all_scores_file_content(
                all_scores_output_path,
                parsed_matrices_for_validation,
                k  # 'k' is from the last successfully processed item
            )
            if not scores_file_validation_passed:
                logging.critical("Halting due to critical all_scores.txt file validation failures.")
                sys.exit(1)

    except IOError as e:
        logging.error(f"Error writing aggregated scores to {all_scores_output_path}: {e}")
        sys.exit(1)

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

    # Create parsing summary file for the report generator
    parsing_summary_path = os.path.join(analysis_inputs_dir, "parsing_summary.txt")
    try:
        with open(parsing_summary_path, 'w', encoding='utf-8') as f_summary:
            f_summary.write("--- Response Parsing Summary ---\n")
            # Get all response files that were found
            all_response_indices = []
            for resp_filepath in response_files:
                match = re.search(r"llm_response_(\d+)\.txt", os.path.basename(resp_filepath))
                if match:
                    all_response_indices.append(int(match.group(1)))
            
            # Write status for each response file
            for index in sorted(all_response_indices):
                filename = f"llm_response_{index:03d}.txt"
                if index in successful_indices:
                    f_summary.write(f"{filename}: SUCCESS - parsed matrix\n")
                else:
                    f_summary.write(f"{filename}: REJECTED - parsing failed\n")
    except IOError as e:
        logging.error(f"Error writing parsing summary file to {parsing_summary_path}: {e}")

    logging.info(f"Processing complete. Successfully processed: {processed_count}, Errors/Skipped: {error_count}")

    # Add a machine-readable summary for the orchestrator to capture.
    # Format: <<<PARSER_SUMMARY:processed_count:total_files_found>>>
    print(f"\n<<<PARSER_SUMMARY:{processed_count}:{len(response_files)}:warnings={total_parsing_warnings}>>>\n")

if __name__ == "__main__":
    main()

# === End of src/process_llm_responses.py ===
