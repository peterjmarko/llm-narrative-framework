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
    """Builds the detailed DataFrame for a single replication."""
    analysis_dir = os.path.join(replication_dir, "analysis_inputs")
    
    scores_file = os.path.join(analysis_dir, "all_scores.txt")
    mappings_file = os.path.join(analysis_dir, "all_mappings.txt")

    if not all(os.path.exists(p) for p in [scores_file, mappings_file]):
        logging.warning(f"Missing scores or mappings file in {analysis_dir}.")
        return None

    try:
        score_matrices = [np.loadtxt(StringIO(block)) for block in open(scores_file, 'r').read().strip().split('\n\n')]
        mappings_list = []
        with open(mappings_file, 'r') as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                try:
                    parsed_line = list(map(int, stripped_line.split()))
                    mappings_list.append(parsed_line)
                except ValueError:
                    # This is expected for the header row, so we log at DEBUG level.
                    logging.debug(f"Skipping non-integer row (likely header) in {mappings_file}: '{stripped_line}'")
                    continue
    except Exception as e:
        logging.error(f"Could not read score/mapping files in {analysis_dir}: {e}")
        return None

    all_points = []
    detected_k = 0  # Initialize to 0

    if not score_matrices:
        logging.warning(f"No score matrices found in {scores_file}.")
        return None, detected_k

    # Detect the actual 'k' from the first matrix's dimension.
    # This is safer than relying on the command-line argument.
    detected_k = score_matrices[0].shape[1]

    for i, matrix in enumerate(score_matrices):
        # Ensure matrix dimensions match the detected k
        if matrix.shape[1] != detected_k:
            logging.warning(f"Matrix {i} in {scores_file} has an inconsistent shape. Skipping.")
            continue
            
        true_map = mappings_list[i]
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
    return pd.DataFrame(all_points), detected_k

def calculate_bias_metrics(df, k_value):
    """Calculates numerical summary metrics for bias."""
    if df is None or df.empty: return {}

    # Metric 1: Std Dev of top-1 prediction proportions across columns
    top1_props = df[df['is_top_1']].groupby('desc_col').size() / df['person_row'].nunique()
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
    parser.add_argument("--k_value", type=int, default=10, help="The 'k' dimension.")
    args = parser.parse_args()

    # --- Dynamically find the timestamped report file ---
    report_files = [f for f in os.listdir(args.replication_dir) if f.startswith("replication_report_") and f.endswith(".txt")]

    if not report_files:
        logging.error(f"No replication_report_*.txt file found in {args.replication_dir}. Aborting bias analysis.")
        return

    if len(report_files) > 1:
        # Sort to ensure we get the latest file if multiple exist
        report_files.sort()
        logging.warning(f"Multiple report files found. Using the most recent: {report_files[-1]}")

    report_filepath = os.path.join(args.replication_dir, report_files[-1])
    logging.debug(f"Found report file to update: {report_filepath}")
    # --- End of file finding logic ---

    df_long, detected_k = build_long_format_df(args.replication_dir, args.k_value)
    if df_long is None or df_long.empty:
        # A more specific error is logged inside the function, so we can just exit.
        return

    bias_metrics = calculate_bias_metrics(df_long, detected_k)

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
            report_content[:start_idx + len(json_start_tag)] +
            "\n" + new_json_string + "\n" +
            report_content[end_idx:]
        )

        with open(report_filepath, 'w', encoding='utf-8') as f:
            f.write(new_report_content)

        logging.debug(f"Successfully updated bias metrics in {report_filepath}")

    except FileNotFoundError:
        # This case should not be hit due to the check at the start, but is good practice.
        logging.error(f"Report file disappeared before update: {report_filepath}")
    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON from report file: {report_filepath}")
    except Exception as e:
        logging.error(f"Failed to update report file {report_filepath}: {e}")

if __name__ == "__main__":
    main()