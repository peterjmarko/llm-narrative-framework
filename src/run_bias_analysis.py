#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/run_bias_analysis.py

"""
Calculates key numerical metrics for positional bias on a per-replication basis
and appends them to the replication_report.txt for study-wide analysis.
"""

import argparse
import os
import pandas as pd
import numpy as np
import logging
import json
from io import StringIO

logging.basicConfig(level=logging.INFO, format='%(levelname)s (run_bias_analysis): %(message)s')

def build_long_format_df(replication_dir, k_value):
    """Builds the detailed DataFrame for a single replication, validating against k."""
    analysis_dir = os.path.join(replication_dir, "analysis_inputs")
    scores_file = os.path.join(analysis_dir, "all_scores.txt")
    mappings_file = os.path.join(analysis_dir, "all_mappings.txt")

    if not all(os.path.exists(p) for p in [scores_file, mappings_file]):
        logging.warning(f"Missing scores or mappings file in {analysis_dir}.")
        return None

    try:
        # Use a context manager for reading the file
        with open(scores_file, 'r') as f:
            content = f.read().strip()
        # Handle empty file case
        if not content:
            score_matrices = []
        else:
            # Manually split by the double newline, then process each block.
            # This is more robust than relying on loadtxt's newline handling.
            blocks = content.strip().split('\n\n')
            score_matrices = [np.loadtxt(StringIO(block)) for block in blocks if block.strip()]
        
        with open(mappings_file, 'r') as f:
            mappings_list = [list(map(int, line.strip().split())) for line in f if line.strip() and line.strip()[0].isdigit()]
    except Exception as e:
        logging.error(f"Could not read score/mapping files in {analysis_dir}: {e}")
        return None

    all_points = []
    
    # Ensure we don't process more matrices than we have mappings for
    num_trials = min(len(score_matrices), len(mappings_list))
    if len(score_matrices) != len(mappings_list):
        logging.warning(f"Mismatch between number of score matrices ({len(score_matrices)}) and mappings ({len(mappings_list)}). Processing the minimum ({num_trials}).")

    for i in range(num_trials):
        matrix = score_matrices[i]
        true_map = mappings_list[i]

        # Validate that the matrix is 2D and has the expected shape
        if matrix.ndim != 2 or matrix.shape != (k_value, k_value):
            logging.warning(f"Matrix {i} in {scores_file} has shape {matrix.shape}, expected ({k_value}, {k_value}). Skipping.")
            continue
        for row_idx in range(matrix.shape[0]):
            true_col_for_row = true_map[row_idx]
            max_score = np.max(matrix[row_idx, :])
            for col_idx in range(matrix.shape[1]):
                all_points.append({
                    'person_row': row_idx + 1,
                    'desc_col': col_idx + 1,
                    'score': matrix[row_idx, col_idx],
                    'is_true_match': (col_idx + 1 == true_col_for_row),
                    'is_top_1': (matrix[row_idx, col_idx] == max_score)
                })
    return pd.DataFrame(all_points)

def calculate_bias_metrics(df, k_value):
    """Calculates numerical summary metrics for bias."""
    if df is None or df.empty: return {}
    
    num_trials = len(df) / (k_value * k_value)
    if num_trials == 0: return {}

    # Metric 1: Std Dev of top-1 prediction proportions across columns
    top1_props = df[df['is_top_1']].groupby('desc_col').size() / num_trials
    top1_props = top1_props.reindex(range(1, k_value + 1), fill_value=0)
    top1_pred_bias_std = top1_props.std()

    # Metric 2: Difference between mean score of true matches and false matches
    true_scores = df[df['is_true_match']]['score']
    false_scores = df[~df['is_true_match']]['score']
    true_false_score_diff = true_scores.mean() - false_scores.mean() if not true_scores.empty and not false_scores.empty else 0

    return {
        "top1_pred_bias_std": top1_pred_bias_std,
        "true_false_score_diff": true_false_score_diff,
    }

def main():
    parser = argparse.ArgumentParser(description="Calculate bias metrics and update a replication report.")
    parser.add_argument("replication_dir", help="Path to the replication run directory.")
    parser.add_argument("--k_value", type=int, required=True, help="The 'k' dimension (num_subjects).")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose (INFO level) logging.")
    args = parser.parse_args()

    # If --verbose is NOT specified, suppress INFO logs.
    if not args.verbose:
        logging.getLogger().setLevel(logging.WARNING)

    report_files = [f for f in os.listdir(args.replication_dir) if f.startswith("replication_report_") and f.endswith(".txt")]
    if not report_files:
        logging.error(f"No replication_report_*.txt file found in {args.replication_dir}. Aborting.")
        return

    report_filepath = os.path.join(args.replication_dir, sorted(report_files)[-1])

    df_long = build_long_format_df(args.replication_dir, args.k_value)
    if df_long is None or df_long.empty:
        logging.warning("DataFrame is empty or could not be built. No bias metrics will be calculated.")
        return

    bias_metrics = calculate_bias_metrics(df_long, args.k_value)

    try:
        with open(report_filepath, 'r', encoding='utf-8') as f:
            report_content = f.read()

        json_start_tag = "<<<METRICS_JSON_START>>>"
        json_end_tag = "<<<METRICS_JSON_END>>>"
        start_idx = report_content.find(json_start_tag)
        end_idx = report_content.find(json_end_tag)

        if start_idx == -1 or end_idx == -1:
            logging.error(f"Could not find JSON block in {report_filepath}. Aborting update.")
            return

        json_string = report_content[start_idx + len(json_start_tag):end_idx].strip()
        report_data = json.loads(json_string)
        report_data["positional_bias_metrics"] = bias_metrics
        new_json_string = json.dumps(report_data, indent=4)
        new_report_content = (
            report_content[:start_idx + len(json_start_tag)] + "\n" + new_json_string + "\n" + report_content[end_idx:]
        )

        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(new_report_content)
        logging.info(f"Successfully updated bias metrics in {report_filepath}")

    except Exception as e:
        logging.error(f"Failed to update report file {report_filepath}: {e}", exc_info=True)

if __name__ == "__main__":
    main()