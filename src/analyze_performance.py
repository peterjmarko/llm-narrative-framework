#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/analyze_performance.py

"""
Performance Analysis Script for LLM Matching Task (analyze_performance.py)

Purpose:
This script takes aggregated score matrices and their corresponding true mappings
from a specific experimental run to perform a final statistical analysis of the
LLM's performance.

Workflow (when called by orchestrator):
1.  Receives the path to a unique run directory via the `--run_output_dir` argument.
2.  Reads `all_scores.txt`, `all_mappings.txt`, and `successful_query_indices.txt`
    from the `<run_output_dir>/analysis_inputs/` directory.
3.  Performs a **final validation step**: uses the successful indices list to ensure
    the mappings in `all_mappings.txt` align with their original `manifest.txt`
    files located in `<run_output_dir>/session_queries/`.
4.  If validation passes, it calculates and prints a full statistical summary,
    including Mann-Whitney U tests, effect sizes, MRR, and Top-K Accuracy.
5.  Saves the raw data distributions for each key metric (e.g., MRR values for
    each trial) to text files within the `analysis_inputs` directory for further
    analysis or visualization.

Input Files (within the provided `<run_output_dir>`):
- `<run_output_dir>/analysis_inputs/all_scores.txt`
- `<run_output_dir>/analysis_inputs/all_mappings.txt`
- `<run_output_dir>/analysis_inputs/successful_query_indices.txt`
- `<run_output_dir>/session_queries/llm_query_XXX_manifest.txt` (for validation)

Output Files (within the provided `<run_output_dir>`):
- `<run_output_dir>/analysis_inputs/mrr_distribution_kX.txt`
- `<run_output_dir>/analysis_inputs/top_1_accuracy_distribution_kX.txt`
- ... (and other metric distribution files)

Command-Line Usage (for orchestrated runs):
    python src/analyze_performance.py --run_output_dir <path_to_run_dir> --quiet

Required Argument for Orchestrated Runs:
    --run_output_dir      The absolute path to the self-contained output
                          directory for this specific run.
Optional Arguments:
    --quiet               Suppress verbose progress and info messages, showing
                          only the final summary statistics. Used by the orchestrator.
"""

# === Start of src/analyze_performance.py ===

import numpy as np
from scipy.stats import mannwhitneyu, norm, chi2, ttest_1samp, wilcoxon, rankdata, linregress
import argparse
import math
import os
import sys
import logging
import json
from collections import Counter

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    # This fallback is for standalone execution if the script is moved
    class DummyConfig:
        def has_option(self, section, key): return False
        def get(self, section, key, fallback=None): return fallback
    APP_CONFIG = DummyConfig()
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    def get_config_value(cfg, section, key, fallback=None, value_type=str): return fallback

# --- I. Per-Test Evaluation Function (Enhanced) ---
def evaluate_single_test(score_matrix, correct_mapping_indices_1_based, k_val, top_k_value_for_accuracy=3):
    matrix = np.array(score_matrix) 
    if matrix.shape != (k_val, k_val):
        print(f"Warning: evaluate_single_test received matrix with incorrect shape {matrix.shape}, expected ({k_val},{k_val}). Skipping this test.")
        return None
    if len(correct_mapping_indices_1_based) != k_val:
        print(f"Warning: correct_mapping_indices_1_based has {len(correct_mapping_indices_1_based)} elements, expected {k_val}. Skipping this test.")
        return None
    if not all(1 <= idx <= k_val for idx in correct_mapping_indices_1_based):
        print(f"Warning: Invalid value in correct_mapping_indices_1_based (not between 1 and {k_val}). Skipping this test.")
        return None

    correct_scores = []
    incorrect_scores = []
    ranks_of_correct_ids = []
    chosen_positions = []

    for person_idx in range(k_val):
        try:
            correct_id_idx_0_based = correct_mapping_indices_1_based[person_idx] - 1
            person_scores = matrix[person_idx, :] 
            chosen_positions.append(np.argmax(person_scores))

            for id_idx_0_based in range(k_val): 
                score = person_scores[id_idx_0_based]
                if id_idx_0_based == correct_id_idx_0_based:
                    correct_scores.append(score)
                else:
                    incorrect_scores.append(score)
            
            # Use scipy.stats.rankdata for robust ranking that handles ties correctly.
            # rankdata assigns rank 1 to the smallest value, so we rank the negative scores
            # to get ranks in descending order of score (1 for the highest score).
            # The 'average' method for ties is the standard for ranking.
            person_scores_1d = np.array(person_scores).flatten()
            ranks = rankdata(-person_scores_1d, method='average')
            rank_of_correct_desc = ranks[correct_id_idx_0_based]
            ranks_of_correct_ids.append(rank_of_correct_desc)
        except IndexError as e:
            print(f"Warning: IndexError during evaluation for person index {person_idx}. Error: {e}. Skipping rank.")
            ranks_of_correct_ids.append(float('nan'))
            continue 

    p_value_mwu, effect_size_r, u_statistic = None, None, None
    if not correct_scores or not incorrect_scores:
        print("Warning: No correct or incorrect scores collected for a test. Skipping MWU.")
    else:
        is_variable = False
        if correct_scores and incorrect_scores:
            all_scores_combined = np.array(correct_scores + incorrect_scores)
            if len(np.unique(all_scores_combined)) > 1:
                 is_variable = True
        
        if is_variable:
            try:
                u_statistic, p_value_mwu = mannwhitneyu(correct_scores,
                                                        incorrect_scores,
                                                        alternative='greater')
                if p_value_mwu is not None and not np.isnan(p_value_mwu):
                    p_clamped = np.clip(p_value_mwu, 1e-10, 1 - 1e-10) 
                    z_score = norm.ppf(1 - p_clamped) 
                    n_total = len(correct_scores) + len(incorrect_scores)
                    if n_total > 0 :
                        effect_size_r = z_score / np.sqrt(n_total)
            except ValueError as e: 
                print(f"Mann-Whitney U error for a test: {e}.")
        else:
            print("Warning: Insufficient variance for Mann-Whitney U test. Assigning non-significant p-value.")
            p_value_mwu = 1.0 
            effect_size_r = 0.0

    num_people_for_ranks = len(ranks_of_correct_ids)
    valid_ranks = [r for r in ranks_of_correct_ids if not np.isnan(r)]

    top_1_hits = sum(1 for rank in valid_ranks if rank == 1)
    top_1_accuracy = top_1_hits / num_people_for_ranks if num_people_for_ranks > 0 else 0.0

    top_k_hits = sum(1 for rank in valid_ranks if rank <= top_k_value_for_accuracy)
    top_k_accuracy_val = top_k_hits / num_people_for_ranks if num_people_for_ranks > 0 else 0.0
    
    reciprocal_ranks = [1.0/rank if rank > 0 else 0.0 for rank in valid_ranks]
    mean_reciprocal_rank = np.mean(reciprocal_ranks) if reciprocal_ranks else 0.0

    # --- FIX: Calculate and add the mean rank of the correct ID ---
    mean_rank_of_correct_id = np.mean(valid_ranks) if valid_ranks else np.nan
    
    return {
        'k_val': k_val, 'p_value_mwu': p_value_mwu, 'effect_size_r': effect_size_r,
        'mrr': mean_reciprocal_rank, 'top_1_accuracy': top_1_accuracy,
        f'top_{top_k_value_for_accuracy}_accuracy': top_k_accuracy_val,
        'u_statistic': u_statistic,
        'mean_rank_of_correct_id': mean_rank_of_correct_id, # Add the new metric
        'raw_correct_scores': correct_scores,
        'raw_incorrect_scores': incorrect_scores,
        'raw_chosen_positions': chosen_positions
    }

# --- II. Meta-Analysis Functions ---
def combine_p_values_stouffer(p_values):
    p_values = [p for p in p_values if p is not None and not np.isnan(p)]
    if not p_values: return None, None
    p_values_clamped = np.clip(p_values, 1e-10, 1.0 - 1e-10)
    z_scores = norm.ppf(1 - p_values_clamped)
    if len(z_scores) == 0: return None, None
    combined_z = np.sum(z_scores) / np.sqrt(len(z_scores))
    combined_p = 1 - norm.cdf(combined_z)
    return combined_z, combined_p

def combine_p_values_fisher(p_values):
    p_values = [p for p in p_values if p is not None and not np.isnan(p) and p > 0]
    if not p_values: return None, None
    p_values_clamped = np.clip(p_values, 1e-300, 1.0)
    if len(p_values_clamped) == 0: return None, None
    chi_squared_stat = -2 * np.sum(np.log(p_values_clamped))
    df = 2 * len(p_values_clamped)
    combined_p = chi2.sf(chi_squared_stat, df)
    return chi_squared_stat, combined_p

def analyze_metric_distribution(metric_values, chance_level, metric_name):
    metric_values = [m for m in metric_values if m is not None and not np.isnan(m)]
    base_return = {
        'name': metric_name, 'count': len(metric_values), 
        'mean': np.nan, 'median': np.nan, 'std': np.nan,
        'chance_level': chance_level, 'ttest_1samp_stat': None, 'ttest_1samp_p': None,
        'wilcoxon_signed_rank_stat': None, 'wilcoxon_signed_rank_p': None
    }
    if not metric_values: return base_return
    
    base_return['mean'] = np.mean(metric_values)
    base_return['median'] = np.median(metric_values)
    base_return['std'] = np.std(metric_values) if len(metric_values) > 1 else 0.0
    
    if len(metric_values) >= 2:
        try:
            stat, p_val = ttest_1samp(metric_values, chance_level, alternative='greater', nan_policy='omit')
            base_return['ttest_1samp_stat'], base_return['ttest_1samp_p'] = stat, p_val
        except Exception as e: print(f"Error during t-test for {metric_name}: {e}")
    elif len(metric_values) == 1:
        print(f"Warning: Only one sample for {metric_name}, t-test not meaningfully computed.")

    if len(metric_values) >=1:
        differences = np.array(metric_values) - chance_level
        if differences.size == 0: pass
        elif np.all(np.isclose(differences,0)):
             base_return['wilcoxon_signed_rank_p'] = 1.0
             base_return['wilcoxon_signed_rank_stat'] = 0.0
        else:
            try:
                stat, p_val = wilcoxon(differences, alternative='greater', zero_method='wilcox')
                base_return['wilcoxon_signed_rank_stat'], base_return['wilcoxon_signed_rank_p'] = stat, p_val
            except ValueError as e: 
                print(f"Error during Wilcoxon test for {metric_name} (data: {differences[:5]}...): {e}")
                if len(np.unique(differences)) == 1 and differences.size > 0 and differences[0] != 0:
                    print(f"  Wilcoxon edge case: all non-zero differences are '{differences[0]}'.")
                    if differences[0] > 0: base_return['wilcoxon_signed_rank_p'] = 0.0 if len(differences) >= 6 else 0.5 # Min N for significance in Wilcoxon often ~6
                    else: base_return['wilcoxon_signed_rank_p'] = 1.0
    return base_return

def calculate_mrr_chance(k_val):
    if k_val <= 0: return 0.0
    return (1.0/k_val) * sum(1.0/j for j in range(1, int(k_val) + 1))

def calculate_top_k_accuracy_chance(K, k_val):
    if k_val <= 0: return 0.0
    return min(float(K), float(k_val)) / float(k_val)

# --- III. File Parsing Functions ---
def try_parse_mapping_line(line, k_val_if_known, delimiter_char=None):
    try:
        items_str = line.strip().split(delimiter_char) if delimiter_char else line.strip().split()
        items_str_cleaned = [s for s in items_str if s] 
        if not items_str_cleaned and line.strip(): return None, 0 
        if not items_str_cleaned and not line.strip(): return None, 0
        items_int = [int(x) for x in items_str_cleaned]
        num_items = len(items_int)
        if k_val_if_known is not None and num_items != k_val_if_known: return None, num_items 
        return items_int, num_items
    except ValueError: return None, 0 

def read_mappings_and_deduce_k(filepath, k_override=None, specified_delimiter_keyword=None):
    mappings_list = []
    deduced_k_from_file = None
    actual_delimiter_char_used = None 
    header_skipped_this_read = False # Tracks if header was skipped in this specific call

    delimiter_char_to_try_first = None
    if specified_delimiter_keyword:
        if specified_delimiter_keyword == ',': delimiter_char_to_try_first = ','
        elif specified_delimiter_keyword.lower() == 'tab': delimiter_char_to_try_first = '\t'
        elif specified_delimiter_keyword.lower() == 'space': delimiter_char_to_try_first = ' ' 
    
    actual_delimiter_to_parse_with = delimiter_char_to_try_first

    lines_for_detection_and_first_data = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for _ in range(15): 
                line = f.readline()
                if not line: break
                stripped_line = line.strip()
                if stripped_line: lines_for_detection_and_first_data.append(stripped_line)
            if not lines_for_detection_and_first_data:
                print(f"Error: Mappings file {filepath} is empty.")
                return None, None, None
    except FileNotFoundError:
        print(f"Error: Mappings file not found at {filepath}")
        return None, None, None

    if actual_delimiter_to_parse_with is None: # Auto-detect
        first_line_sample = lines_for_detection_and_first_data[0]
        first_line_parts_tab = first_line_sample.split('\t')
        first_line_parts_comma = first_line_sample.split(',')
        
        # Heuristic: if the first line is non-numeric when split by tab/comma, it's likely a header using that delimiter
        is_tab_header = len(first_line_parts_tab) > 1 and not all(p.strip().isdigit() for p in first_line_parts_tab if p.strip())
        is_comma_header = len(first_line_parts_comma) > 1 and not all(p.strip().isdigit() for p in first_line_parts_comma if p.strip())

        if is_tab_header and (len(first_line_parts_tab) >= len(first_line_parts_comma) or not is_comma_header):
            actual_delimiter_to_parse_with = '\t'
        elif is_comma_header:
            actual_delimiter_to_parse_with = ','

        if actual_delimiter_to_parse_with:
             print(f"Info (File: {filepath}): Deduced delimiter '{repr(actual_delimiter_to_parse_with)}' from first line structure.")
             header_skipped_this_read = True # Assume first line was header used for deduction
        else: 
            # If header didn't give a clear delimiter, try on data lines
            for delim_char_candidate in [',', '\t']: # Order of preference
                temp_k_for_this_delim = None; consistent_k_count = 0; parsed_lines_with_this_delim = 0
                start_idx_data_sniff = 1 if header_skipped_this_read else 0 # Sniff data after assumed header
                if start_idx_data_sniff >= len(lines_for_detection_and_first_data): continue

                for line_sample in lines_for_detection_and_first_data[start_idx_data_sniff:]:
                    parsed_items, num_items = try_parse_mapping_line(line_sample, None, delim_char_candidate)
                    if parsed_items and num_items > 0:
                        parsed_lines_with_this_delim +=1
                        if temp_k_for_this_delim is None: temp_k_for_this_delim = num_items
                        if temp_k_for_this_delim == num_items: consistent_k_count +=1
                
                if temp_k_for_this_delim and parsed_lines_with_this_delim > 0 and \
                   (consistent_k_count / parsed_lines_with_this_delim) >= 0.8:
                    actual_delimiter_to_parse_with = delim_char_candidate
                    print(f"Info (File: {filepath}): Auto-detected data delimiter as '{repr(actual_delimiter_to_parse_with)}'.")
                    break
            if actual_delimiter_to_parse_with is None:
                print(f"Info (File: {filepath}): Could not auto-detect comma or tab. Assuming whitespace.")

    # Determine k
    final_k_to_use = k_override
    if final_k_to_use is None: # Deduce k if not overridden
        temp_k_deduced = None
        # Start from line 0 if no header was sniffed, line 1 if header was sniffed
        start_idx_k_deduce = 1 if header_skipped_this_read else 0
        if start_idx_k_deduce < len(lines_for_detection_and_first_data):
            for line_sample in lines_for_detection_and_first_data[start_idx_k_deduce:]:
                parsed_data, num_items = try_parse_mapping_line(line_sample, None, actual_delimiter_to_parse_with)
                if parsed_data and num_items > 0:
                    temp_k_deduced = num_items
                    break 
        if temp_k_deduced is None or temp_k_deduced <=0 :
            print(f"Error: Could not deduce a valid k > 0 from {filepath} with delimiter '{repr(actual_delimiter_to_parse_with)}'.")
            return None, None, actual_delimiter_to_parse_with
        final_k_to_use = temp_k_deduced
        print(f"Info (File: {filepath}): Deduced k as {final_k_to_use} using delimiter '{repr(actual_delimiter_to_parse_with)}'.")
    else:
        print(f"Info (File: {filepath}): Using overridden k={final_k_to_use}.")


    # Re-read entire file for parsing all data lines
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Skip header if one was identified or assumed
            # This logic needs to be careful not to re-skip if already implicitly skipped
            # Or, simply try to parse the first line as data. If it fails, then it's a header.
            first_line_content = f.readline()
            if not first_line_content: # Empty file
                print(f"Error: Mappings file {filepath} is empty (on full read).")
                return None, final_k_to_use, actual_delimiter_to_parse_with

            parsed_first_line, num_first_line_items = try_parse_mapping_line(first_line_content, final_k_to_use, actual_delimiter_to_parse_with)
            if parsed_first_line and num_first_line_items == final_k_to_use:
                mappings_list.append(parsed_first_line) # First line was data
            else:
                print(f"Info (File: {filepath}): First line assumed to be header based on parsing attempt: '{first_line_content.strip()}'")
                # Header consumed, do nothing more with it
            
            # Process remaining lines
            for line_num, line_content in enumerate(f, 2): # Start from 2 as first line handled
                line = line_content.strip()
                if line:
                    parsed_indices, num_items = try_parse_mapping_line(line, final_k_to_use, actual_delimiter_to_parse_with)
                    if parsed_indices and num_items == final_k_to_use:
                        mappings_list.append(parsed_indices)
                    elif num_items != final_k_to_use and num_items > 0 :
                        print(f"Warning (File: {filepath}, line ~{line_num}): Parsed with {num_items} elements, expected k={final_k_to_use}. Delim='{repr(actual_delimiter_to_parse_with)}'. Skip: '{line}'")
                    elif not parsed_indices and line: 
                         print(f"Warning (File: {filepath}, line ~{line_num}): Could not parse as data. Delim='{repr(actual_delimiter_to_parse_with)}'. Skip: '{line}'")
    except FileNotFoundError:
        print(f"Error: Mappings file not found at {filepath} (during full read).")
        return None, None, None

    if not mappings_list:
        print(f"Error: No valid mapping data lines found in {filepath} for k={final_k_to_use} with delim='{repr(actual_delimiter_to_parse_with)}'.")
        return None, final_k_to_use, actual_delimiter_to_parse_with

    return mappings_list, final_k_to_use, actual_delimiter_to_parse_with


def calculate_positional_bias(performance_scores):
    """
    Performs a linear regression on a list of performance scores over time (trials).

    Args:
        performance_scores (list of float): A list of performance metrics (e.g., MRR, rank)
                                            for each trial in chronological order.

    Returns:
        dict: A dictionary containing the slope, intercept, p-value, and r-value
              of the linear regression. Returns NaNs if input is insufficient.
    """
    if not performance_scores or len(performance_scores) < 2:
        return {
            'bias_slope': np.nan,
            'bias_intercept': np.nan,
            'bias_p_value': np.nan,
            'bias_r_value': np.nan
        }

    trials = np.arange(len(performance_scores))
    # Note: linregress is imported from scipy.stats at the top of the file
    slope, intercept, r_value, p_value, std_err = linregress(trials, performance_scores)

    return {
        'bias_slope': slope,
        'bias_intercept': intercept,
        'bias_p_value': p_value,
        'bias_r_value': r_value,
        'bias_std_err': std_err
    }


def read_score_matrices(filepath, expected_k, delimiter_char=None):
    if expected_k is None or expected_k <=0:
        print(f"Error: Invalid expected_k ({expected_k}) for reading score matrices.")
        return None

    matrices = []
    current_matrix_str_rows = [] 
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line_num, line_content in enumerate(f, 1):
                line = line_content.strip()
                if not line: 
                    if current_matrix_str_rows:
                        if len(current_matrix_str_rows) == expected_k:
                            try:
                                matrix_data_float = []
                                for row_str_list_of_str in current_matrix_str_rows:
                                    matrix_data_float.append([float(x.strip()) for x in row_str_list_of_str])
                                matrix = np.array(matrix_data_float)
                                if matrix.shape == (expected_k, expected_k):
                                    matrices.append(matrix)
                                else: 
                                    print(f"W (File: {filepath}, mat end ~L{line_num}): Shape {matrix.shape}, exp ({expected_k},{expected_k}). Skip.")
                            except ValueError:
                                print(f"W (File: {filepath}, mat end ~L{line_num}): Not float. Delim='{repr(delimiter_char)}'. Data: {current_matrix_str_rows}. Skip.")
                        else: 
                             print(f"W (File: {filepath}, mat end ~L{line_num}): {len(current_matrix_str_rows)} lines, exp {expected_k}. Skip.")
                        current_matrix_str_rows = [] 
                else: 
                    ### NEW LOGIC ###
                    # This block is enhanced to handle complex formats like Markdown tables
                    # and tables with row/column headers.
                    
                    row_items_str_cleaned = None

                    # 1. Handle Markdown table format
                    if line.startswith('|'):
                        if '---' in line: continue # Skip separator line
                        # Parse cells, removing empty strings from start/end pipes
                        parts = [p.strip() for p in line.strip('|').split('|')]
                        if len(parts) > 1:
                            try:
                                # Heuristic: if the second element is a number, it's a data row.
                                float(parts[1])
                                # Data row found, skip the first element (row label)
                                row_items_str_cleaned = parts[1:]
                            except (ValueError, IndexError):
                                # This is likely the header row. Skip it.
                                continue
                        else:
                            # Not a valid data line (e.g., just `| |`)
                            continue
                    
                    # 2. Handle standard delimited formats (tab, space, comma)
                    else:
                        parts = line.split(delimiter_char) if delimiter_char else line.split()
                        try:
                            # First, try to parse the row as-is (all numbers)
                            [float(p.strip()) for p in parts]
                            row_items_str_cleaned = [p.strip() for p in parts]
                        except ValueError:
                            # If that fails, it might have a text label in the first column.
                            # Try parsing it again, skipping the first element.
                            if len(parts) > 1:
                                try:
                                    [float(p.strip()) for p in parts[1:]]
                                    row_items_str_cleaned = [p.strip() for p in parts[1:]]
                                except (ValueError, IndexError):
                                    # Still fails. It's probably a header or malformed. Skip.
                                    continue
                            else:
                                # Not enough columns to be data-with-a-label. Skip.
                                continue
                    
                    # If the line was identified as a header/separator, skip to the next line
                    if row_items_str_cleaned is None:
                        continue
                    ### END NEW LOGIC ###

                    if len(row_items_str_cleaned) != expected_k:
                        print(f"W (File: {filepath}, L{line_num}): {len(row_items_str_cleaned)} cols, exp {expected_k}. Delim='{repr(delimiter_char)}'. Line: '{line}'. Skip block.")
                        current_matrix_str_rows = [] 
                        # Consume rest of malformed block until blank line
                        while line.strip():
                            try: line = next(f,'').strip()
                            except StopIteration: break
                        continue 
                    current_matrix_str_rows.append(row_items_str_cleaned) 
            
            if current_matrix_str_rows: 
                if len(current_matrix_str_rows) == expected_k:
                    try:
                        matrix_data_float = [[float(x.strip()) for x in row_str_list] for row_str_list in current_matrix_str_rows]
                        matrix = np.array(matrix_data_float)
                        if matrix.shape == (expected_k, expected_k): 
                             matrices.append(matrix)
                        else:
                             print(f"W (File: {filepath}, EOF): Last mat shape {matrix.shape}, exp ({expected_k},{expected_k}). Skip.")
                    except ValueError:
                        print(f"W (File: {filepath}, EOF): Last mat not float. Delim='{repr(delimiter_char)}'. Data: {current_matrix_str_rows}. Skip.")
                else:
                    print(f"W (File: {filepath}, EOF): Last mat block {len(current_matrix_str_rows)} lines, exp {expected_k}. Skip.")

    except FileNotFoundError:
        print(f"Error: Score matrices file not found at {filepath}")
        return None
    if not matrices:
        print(f"No valid matrices loaded: {filepath}, k={expected_k}, Delim='{repr(delimiter_char)}'.")
    return matrices

def read_successful_indices(filepath):
    """Reads the list of original query indices that were successfully processed."""
    if not os.path.exists(filepath):
        logging.error(f"VALIDATION ERROR: Successful indices file not found at '{filepath}'. Cannot perform final validation.")
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read each line, strip whitespace, and convert to int. Ignore blank lines.
            indices = [int(line.strip()) for line in f if line.strip()]
        return indices
    except (ValueError, IOError) as e:
        logging.error(f"VALIDATION ERROR: Could not read or parse successful indices file '{filepath}': {e}")
        return None
    
# --- IV. Main Orchestration Function ---
def print_metric_analysis(analysis_result, metric_title_segment, chance_level_format_str):
    # Check if analysis_result itself is None (e.g., if analyze_metric_distribution returned None)
    if not analysis_result: # Catches if analysis_result is None
        print(f"\n{metric_title_segment}: Analysis result is None or empty.")
        return

    # Check if 'count' key exists and its value
    count = analysis_result.get('count', 0)
    if count == 0:
        metric_name = analysis_result.get('name', 'Metric') # Get name even if count is 0
        print(f"\n{metric_title_segment} ({metric_name}): No valid values to analyze.")
        return

    # ---- If count > 0, proceed to print details ----
    chance_val = analysis_result.get('chance_level')
    chance_str = "N/A" 
    is_percentage_metric = "%%" in chance_level_format_str 

    if chance_val is not None:
        try:
            if is_percentage_metric:
                chance_str = f"{float(chance_val):.2%}" 
            else:
                chance_str = chance_level_format_str % float(chance_val)
        except (TypeError, ValueError) as e:
            print(f"Warning: Could not format chance_level ({chance_val}) with format '{chance_level_format_str}'. Error: {e}")
            chance_str = str(chance_val) 

    print(f"\n{metric_title_segment} (vs Chance={chance_str}):")
    print(f"   Number of valid values: {count}")

    mean_val = analysis_result.get('mean', np.nan)
    median_val = analysis_result.get('median', np.nan)
    std_val = analysis_result.get('std', np.nan)

    mean_str = "N/A"
    if not np.isnan(mean_val):
        mean_str = f"{mean_val:.2%}" if is_percentage_metric else f"{mean_val:.4f}"
    
    median_str = "N/A"
    if not np.isnan(median_val):
        median_str = f"{median_val:.2%}" if is_percentage_metric else f"{median_val:.4f}"
    
    std_str = f"{std_val:.4f}" if not np.isnan(std_val) else "N/A"

    print(f"   Mean: {mean_str}, Median: {median_str}, Std: {std_str}")
    
    t_stat = analysis_result.get('ttest_1samp_stat')
    t_p = analysis_result.get('ttest_1samp_p')
    if t_stat is not None and not np.isnan(t_stat) and t_p is not None and not np.isnan(t_p):
        print(f"   One-sample t-test (vs chance): t = {t_stat:.4f}, p = {t_p:.4g}")
    
    w_stat = analysis_result.get('wilcoxon_signed_rank_stat')
    w_p = analysis_result.get('wilcoxon_signed_rank_p')
    if w_stat is not None and not np.isnan(w_stat) and w_p is not None and not np.isnan(w_p):
        print(f"   Wilcoxon signed-rank (vs chance): W = {w_stat:.4f}, p = {w_p:.4g}")

# --- V. Optional Helper to Save Data Distributions ---
def save_metric_distribution(metric_values, output_dir, filename, quiet=False):
    """Saves a list of metric values to a text file, one value per line."""
    if not metric_values:
        if not quiet:
            print(f"Info: No data to save for {filename}.")
        return
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for value in metric_values:
                f.write(f"{value}\n")
        
        if not quiet:
            print(f"Successfully saved distribution of {len(metric_values)} values to: {filepath}")

    except Exception as e:
        # Errors should always be printed.
        print(f"Error: Could not save metric distribution to {filename}. Reason: {e}")

    except Exception as e:
        print(f"Error: Could not save metric distribution to {filename}. Reason: {e}")


def main():
    parser = argparse.ArgumentParser(description="Performs statistical analysis on LLM matching scores.")
    # Make run_output_dir a required argument for analyze_performance.py
    parser.add_argument("--run_output_dir", required=True,
                        help="The absolute path to the self-contained output directory for this specific run.")
    
    # Removed scores_file and mappings_file as direct arguments, they will be derived from run_output_dir
    parser.add_argument("-k", "--k_value", type=int, default=None,
                        help="The dimension 'k'. If not provided, it's deduced from mappings_file.")
    parser.add_argument("-d", "--delimiter", type=str, default=None,
                        help="Specify delimiter for input files: ',' for comma, 'tab' for tab, "
                             "'space' for single space, or 'None' to trigger auto-detection. "
                             "If unset, auto-detection is used. (default: None, for auto-detect).")
    parser.add_argument("--top_k_acc", type=int, default=3,
                        help="The 'K' for Top-K accuracy calculation (default: 3).")
    parser.add_argument("--num_valid_responses", type=int, default=None, 
                        help="The number of successfully parsed responses, passed by the orchestrator.")
    parser.add_argument("--verbose_per_test", action='store_true',
                        help="Print detailed results for each individual test.")
    parser.add_argument("--quiet", action='store_true',
                        help="Suppress verbose progress and info messages, showing only the final summary.")

    args = parser.parse_args()

    # Set logging level based on --quiet flag
    log_level = logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=log_level,
                        format='%(levelname)s (analyze_performance): %(message)s',
                        stream=sys.stdout)

    # --- Path Resolution Logic ---
    # Since --run_output_dir is now required, we can directly use it.
    analysis_inputs_subdir_cfg = get_config_value(APP_CONFIG, 'General', 'analysis_inputs_subdir', fallback="analysis_inputs")
    analysis_inputs_dir = os.path.join(args.run_output_dir, analysis_inputs_subdir_cfg)
    
    # Define the filenames directly, as they are no longer command-line arguments
    scores_filename = get_config_value(APP_CONFIG, 'Filenames', 'all_scores_file', fallback="all_scores.txt")
    mappings_filename = get_config_value(APP_CONFIG, 'Filenames', 'all_mappings_file', fallback="all_mappings.txt")

    scores_filepath_abs = os.path.join(analysis_inputs_dir, scores_filename)
    mappings_filepath_abs = os.path.join(analysis_inputs_dir, mappings_filename)

    actual_delimiter_for_parsing = None
    if args.delimiter is not None:
        if args.delimiter.lower() == 'none': actual_delimiter_for_parsing = None
        elif args.delimiter.lower() == 'tab': actual_delimiter_for_parsing = '\t'
        elif args.delimiter.lower() == 'space': actual_delimiter_for_parsing = ' '
        else: actual_delimiter_for_parsing = args.delimiter

    # --- Start of Processing ---
    if not args.quiet:
        print(f"Attempting to read mappings from: {mappings_filepath_abs}")
    
    mappings_list, k_val_from_map_func, delimiter_determined_for_map = \
        read_mappings_and_deduce_k(mappings_filepath_abs, args.k_value, actual_delimiter_for_parsing)

    if mappings_list is None or k_val_from_map_func is None:
        print("Halting due to issues reading mappings or deducing/validating k.")
        sys.exit(1)
    
    k_to_use = k_val_from_map_func 
    delimiter_for_scores = delimiter_determined_for_map
    
    if not args.quiet:
        print(f"Using k={k_to_use}. Delimiter for mappings: '{repr(delimiter_determined_for_map)}'.")
        print(f"Attempting to read scores from: {scores_filepath_abs} (using same delimiter: '{repr(delimiter_for_scores)}')")
    
    score_matrices = read_score_matrices(scores_filepath_abs, k_to_use, delimiter_for_scores)

    if score_matrices is None: print("Halting due to issues reading score matrices."); sys.exit(1)
    if not mappings_list: print(f"No valid mappings loaded for k={k_to_use} from {mappings_filepath_abs}. Cannot proceed."); sys.exit(1)
    if not score_matrices: print(f"No valid score matrices loaded for k={k_to_use} from {scores_filepath_abs}. Cannot proceed."); sys.exit(1)
    if len(score_matrices) != len(mappings_list): print(f"Error: Number of score matrices ({len(score_matrices)}) does not match mappings ({len(mappings_list)})."); sys.exit(1)

    # --- FINAL VALIDATION STEP ---

    successful_indices_filename = get_config_value(APP_CONFIG, 'Filenames', 'successful_indices_log', fallback="successful_query_indices.txt")
    
    # Correctly locate successful_indices.txt relative to the run-specific directory.
    # It is expected to be in the same directory as the scores and mappings files.
    analysis_inputs_dir_for_validation = os.path.dirname(mappings_filepath_abs)
    successful_indices_path = os.path.join(analysis_inputs_dir_for_validation, successful_indices_filename)
    
    # The queries directory is still needed to find the manifests.
    queries_dir_for_validation = os.path.join(args.run_output_dir if args.run_output_dir else os.path.dirname(analysis_inputs_dir_for_validation), 'session_queries')

    original_indices = read_successful_indices(successful_indices_path)

    if original_indices and len(original_indices) == len(mappings_list):
        if not args.quiet:
            logging.info("--- Performing Final Validation: Checking all_mappings.txt against manifests ---")
        
        validation_errors = 0
        for i, mapping_line in enumerate(mappings_list):
            original_index = original_indices[i]
            manifest_path = os.path.join(queries_dir_for_validation, f"llm_query_{original_index:03d}_manifest.txt")
            if not os.path.exists(manifest_path):
                logging.error(f"  VALIDATION FAIL: Manifest for original index {original_index} not found at '{manifest_path}'")
                validation_errors += 1
                continue
            # ... (rest of validation loop logic remains the same)
            try:
                with open(manifest_path, 'r', encoding='utf-8') as f_manifest:
                    manifest_lines = f_manifest.read().strip().split('\n')[1:] # Skip header
                    manifest_indices = [line.split('\t')[2] for line in manifest_lines]
                    mapping_from_file = [str(m) for m in mapping_line]
                    if manifest_indices != mapping_from_file:
                        logging.error(f"  VALIDATION FAIL: Mismatch for original index {original_index}!")
                        validation_errors += 1
            except Exception as e:
                logging.error(f"  VALIDATION ERROR: Could not process manifest for original index {original_index}: {e}")
                validation_errors += 1

        if validation_errors > 0:
            print(f"\nCRITICAL: ANALYZER VALIDATION FAILED WITH {validation_errors} ERRORS. Halting analysis.\n")
            sys.exit(1)
        else:
            # This success message MUST always be printed for the orchestrator to see.
            print("\nANALYZER_VALIDATION_SUCCESS\n")
    else:
        logging.warning("Could not perform final validation: success index file missing or length mismatch.")

    num_tests_loaded = len(score_matrices)
    
    if not args.quiet:
        print(f"Successfully loaded {num_tests_loaded} score matrices and {len(mappings_list)} mappings for k={k_to_use}.\n")
        print(f"Starting analysis with k={k_to_use}, Top-K Accuracy for K={args.top_k_acc}\n")

    all_test_results = []
    all_correct_scores_flat = []
    all_incorrect_scores_flat = []
    all_chosen_positions_flat = []
    for i in range(num_tests_loaded):
        if not args.quiet:
            print(f"Processing Test {i+1}/{num_tests_loaded}...")
        
        try:
            current_score_matrix_np = np.array(score_matrices[i], dtype=float)
        except ValueError:
            print(f"  Warning: Could not convert score matrix for Test {i+1} to numbers. Skipping this test.")
            continue 

        results_single_test = evaluate_single_test(current_score_matrix_np, mappings_list[i], k_to_use, args.top_k_acc)

        if results_single_test:
            all_test_results.append(results_single_test)
            all_correct_scores_flat.extend(results_single_test.get('raw_correct_scores', []))
            all_incorrect_scores_flat.extend(results_single_test.get('raw_incorrect_scores', []))
            all_chosen_positions_flat.extend(results_single_test.get('raw_chosen_positions', []))
            if args.verbose_per_test:
                # ... (verbose printing logic remains the same) ...
                p_val_mwu = results_single_test.get('p_value_mwu')
                eff_r = results_single_test.get('effect_size_r')
                mrr_val = results_single_test.get('mrr')
                top1_val = results_single_test.get('top_1_accuracy')
                topk_val = results_single_test.get(f'top_{args.top_k_acc}_accuracy')
                print(f"  Test {i+1} MWU p-value: {p_val_mwu:.4f if p_val_mwu is not None else 'N/A'}, Effect Size r: {eff_r:.4f if eff_r is not None else 'N/A'}")
        else:
            print(f"  Skipped Test {i+1} due to issues in evaluate_single_test (returned None).")
    
    if not all_test_results:
        print("\nNo valid test results to aggregate after individual processing. Exiting.")
        sys.exit(1)

    # --- Overall Meta-Analysis Printing ---
    num_valid_tests_processed = len(all_test_results)
    # Print a machine-readable tag that the orchestrator can find to start the summary.
    print("\n<<<ANALYSIS_SUMMARY_START>>>\n")

    # (The analysis and printing logic is moved from the previous change)
    # 1. Analyze MWU p-values
    mwu_p_values = [res['p_value_mwu'] for res in all_test_results if res.get('p_value_mwu') is not None and not np.isnan(res.get('p_value_mwu'))]
    if mwu_p_values:
        stouffer_z, stouffer_p = combine_p_values_stouffer(mwu_p_values)
        fisher_chi2, fisher_p = combine_p_values_fisher(mwu_p_values)
        print("\n1. Combined Significance of Score Differentiation (Mann-Whitney U p-values):")
        if stouffer_z is not None: print(f"   Stouffer's Method: Combined Z = {stouffer_z:.4f}, Combined p-value = {stouffer_p:.4g} (N={len(mwu_p_values)})")
        if fisher_chi2 is not None: print(f"   Fisher's Method: Combined Chi2 = {fisher_chi2:.4f}, Combined p-value = {fisher_p:.4g} (N={len(mwu_p_values)})")
    else: print("\n1. Combined Significance of Score Differentiation: No valid MWU p-values to combine.")

    # 2. Analyze Effect Sizes (r)
    effect_sizes_r = [res['effect_size_r'] for res in all_test_results if res.get('effect_size_r') is not None]
    effect_size_analysis = analyze_metric_distribution(effect_sizes_r, 0, "MWU Effect Size r")
    print_metric_analysis(effect_size_analysis, "2. Overall Magnitude of Score Differentiation (MWU Effect Size 'r')", "%.4f")

    # 3. Analyze MRR
    mrrs = [res['mrr'] for res in all_test_results if res.get('mrr') is not None]
    mrr_chance = calculate_mrr_chance(k_to_use)
    mrr_analysis = analyze_metric_distribution(mrrs, mrr_chance, "Mean Reciprocal Rank (MRR)")
    print_metric_analysis(mrr_analysis, "3. Overall Ranking Performance (MRR)", "%.4f")

    # 4. Analyze Top-1 Accuracy
    top_1_accs = [res['top_1_accuracy'] for res in all_test_results if res.get('top_1_accuracy') is not None]
    top_1_chance = calculate_top_k_accuracy_chance(1, k_to_use)
    top_1_analysis = analyze_metric_distribution(top_1_accs, top_1_chance, "Top-1 Accuracy")
    print_metric_analysis(top_1_analysis, "4. Overall Ranking Performance (Top-1 Accuracy)", "%.2%%")

    # 5. Analyze Top-K Accuracy
    top_k_label = f'top_{args.top_k_acc}_accuracy'
    top_k_accs = [res[top_k_label] for res in all_test_results if res.get(top_k_label) is not None]
    top_k_chance = calculate_top_k_accuracy_chance(args.top_k_acc, k_to_use)
    top_k_analysis = analyze_metric_distribution(top_k_accs, top_k_chance, f"Top-{args.top_k_acc} Accuracy")
    print_metric_analysis(top_k_analysis, f"5. Overall Ranking Performance (Top-{args.top_k_acc} Accuracy)", "%.2%%")

    # --- FIX: Add analysis for the mean rank of the correct ID ---
    mean_ranks = [res['mean_rank_of_correct_id'] for res in all_test_results if res.get('mean_rank_of_correct_id') is not None]
    # For rank, chance is the average of ranks 1 through k
    mean_rank_chance = (k_to_use + 1) / 2.0
    mean_rank_analysis = analyze_metric_distribution(mean_ranks, mean_rank_chance, "Mean Rank of Correct ID")
    # For rank, lower is better, so the alternative hypothesis for the test is 'less'
    mean_rank_analysis['wilcoxon_signed_rank_p'] = wilcoxon(np.array(mean_ranks) - mean_rank_chance, alternative='less')[1] if mean_ranks else None
    print_metric_analysis(mean_rank_analysis, "6. Overall Ranking Performance (Mean Rank of Correct ID)", "%.2f")


    print("\nAnalysis complete.")

    # --- Saving Section ---
    data_output_dir = os.path.dirname(scores_filepath_abs)
    if not args.quiet:
        print(f"\n--- Saving Raw Metric Distributions ---")
        print(f"Output directory: {data_output_dir}")

    save_metric_distribution(mwu_p_values, data_output_dir, f"mwu_p_value_distribution_k{k_to_use}.txt", quiet=args.quiet)
    save_metric_distribution(effect_sizes_r, data_output_dir, f"effect_size_r_distribution_k{k_to_use}.txt", quiet=args.quiet)
    save_metric_distribution(mrrs, data_output_dir, f"mrr_distribution_k{k_to_use}.txt", quiet=args.quiet)
    save_metric_distribution(top_1_accs, data_output_dir, f"top_1_accuracy_distribution_k{k_to_use}.txt", quiet=args.quiet)
    save_metric_distribution(top_k_accs, data_output_dir, f"top_{args.top_k_acc}_accuracy_distribution_k{k_to_use}.txt", quiet=args.quiet)
    # --- FIX: Save the mean rank distribution ---
    save_metric_distribution(mean_ranks, data_output_dir, f"mean_rank_distribution_k{k_to_use}.txt", quiet=args.quiet)

    if not args.quiet:
        print("---------------------------------------\n")

    # --- Final Machine-Readable Summary ---
    # This JSON line is for easy parsing by the final results compiler.

    # Calculate the final aggregate metrics that were missing
    true_false_score_diff = np.mean(all_correct_scores_flat) - np.mean(all_incorrect_scores_flat) if all_correct_scores_flat and all_incorrect_scores_flat else np.nan
    position_counts = Counter(all_chosen_positions_flat)
    counts_for_std = [position_counts.get(i, 0) for i in range(k_to_use)]
    top1_pred_bias_std = np.std(counts_for_std) if counts_for_std else np.nan
    
    # Calculate performance trend over trials for positional bias metrics
    performance_over_time = [res['mean_rank_of_correct_id'] for res in all_test_results]
    positional_bias_metrics = calculate_positional_bias(performance_over_time)

    summary_data = {
        # Combined Significance
        'mwu_stouffer_z': stouffer_z,
        'mwu_stouffer_p': stouffer_p,
        'mwu_fisher_chi2': fisher_chi2,
        'mwu_fisher_p': fisher_p,
        # Effect Size
        'mean_effect_size_r': effect_size_analysis.get('mean'),
        'effect_size_r_p': effect_size_analysis.get('wilcoxon_signed_rank_p'),
        # MRR
        'mean_mrr': mrr_analysis.get('mean'),
        'mrr_p': mrr_analysis.get('wilcoxon_signed_rank_p'),
        # Top-1 Accuracy
        'mean_top_1_acc': top_1_analysis.get('mean'),
        'top_1_acc_p': top_1_analysis.get('wilcoxon_signed_rank_p'),
        # Top-K Accuracy
        f'mean_top_{args.top_k_acc}_acc': top_k_analysis.get('mean'),
        f'top_{args.top_k_acc}_acc_p': top_k_analysis.get('wilcoxon_signed_rank_p'),
        # Mean Rank
        'mean_rank_of_correct_id': mean_rank_analysis.get('mean'),
        'rank_of_correct_id_p': mean_rank_analysis.get('wilcoxon_signed_rank_p'),
        # Newly added metrics
        'top1_pred_bias_std': top1_pred_bias_std,
        'true_false_score_diff': true_false_score_diff,
        'bias_slope': positional_bias_metrics.get('bias_slope'),
        'bias_intercept': positional_bias_metrics.get('bias_intercept'),
        'bias_r_value': positional_bias_metrics.get('bias_r_value'),
        'bias_p_value': positional_bias_metrics.get('bias_p_value'),
        'bias_std_err': positional_bias_metrics.get('bias_std_err')
    }

    # Embed the number of valid responses into the results dictionary
    if args.num_valid_responses is not None:
        summary_data['n_valid_responses'] = args.num_valid_responses
    else:
        # Fallback for backward compatibility: count the loaded mappings
        summary_data['n_valid_responses'] = len(mappings_list) if mappings_list is not None else 0

    print("\n<<<METRICS_JSON_START>>>")
    print(json.dumps(summary_data))
    print("<<<METRICS_JSON_END>>>")

if __name__ == "__main__":
    main()
    
# === End of src/analyze_performance.py ===