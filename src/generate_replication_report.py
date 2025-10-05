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
# Filename: src/generate_replication_report.py

"""
Stage 5: Replication Report Generator.

This script is responsible for the fifth stage of the replication pipeline:
generating the final, comprehensive `replication_report.txt`.

It reads the final, authoritative `replication_metrics.json` file and the
`config.ini.archived` file from a given run directory. It then assembles a
complete report containing a detailed header, the base LLM query, parsing 
diagnostics showing success/failure status for each response, a human-readable
summary of key results, and the full, machine-parsable JSON block of all metrics.

Key Features:
-   **Comprehensive Status Reporting**: Includes Final Status, Parsing Status, and
    Validation Status to provide clear visibility into pipeline completion.
-   **Parsing Diagnostics Integration**: Embeds parsing summary showing which
    responses succeeded or failed, essential for troubleshooting.
-   **Statistical Summaries**: Provides human-readable performance metrics with
    chance-level comparisons and statistical significance testing.
-   **Machine-Readable JSON**: Includes complete metrics in JSON format for
    automated analysis and aggregation.

This modular approach ensures that report generation is a distinct, testable
step in the pipeline. It is called by `replication_manager.py`.

Usage:
    python src/generate_replication_report.py --run_output_dir /path/to/run_dir ...
"""

import os
import sys
import json
import re
import configparser
import datetime
import argparse
import glob

def calculate_mrr_chance(k_val):
    """Calculates the expected MRR for a random guess."""
    if k_val <= 0: return 0.0
    return (1.0 / k_val) * sum(1.0 / j for j in range(1, int(k_val) + 1))

def main():
    parser = argparse.ArgumentParser(description="Generates the final report for a single replication run.")
    parser.add_argument("--run_output_dir", required=True, help="Path to the specific run output directory.")
    parser.add_argument("--notes", type=str, default="N/A", help="Optional notes passed from the orchestrator.")
    parser.add_argument("--replication_num", type=int, required=True, help="The replication number.")
    args = parser.parse_args()

    run_specific_dir_path = args.run_output_dir

    # --- Load Data Sources ---
    try:
        # Load the final, authoritative metrics from the JSON file.
        metrics_path = os.path.join(run_specific_dir_path, 'analysis_inputs', 'replication_metrics.json')
        with open(metrics_path, 'r', encoding='utf-8') as f:
            metrics = json.load(f)

        # Load run parameters from the archived config.
        config = configparser.ConfigParser()
        config.read(os.path.join(run_specific_dir_path, 'config.ini.archived'))
        k_per_query = config.getint('Experiment', 'group_size', fallback=0)

    except FileNotFoundError as e:
        print(f"Error: A required file was not found. {e}", file=sys.stderr)
        sys.exit(1)
        return  # Eject for testability
    except (json.JSONDecodeError, configparser.Error) as e:
        print(f"Error: Could not parse a required data file. {e}", file=sys.stderr)
        sys.exit(1)
        return  # Eject for testability

    # --- Clean and Prepare for Writing ---
    for old_report in glob.glob(os.path.join(run_specific_dir_path, 'replication_report_*.txt')):
        os.remove(old_report)
    report_path = os.path.join(run_specific_dir_path, f"replication_report_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}.txt")

    # --- Build Report Components ---
    # 1. Header
    run_start_str_match = re.search(r'run_(\d{8}_\d{6})', os.path.basename(run_specific_dir_path))
    run_date_display = datetime.datetime.strptime(run_start_str_match.group(1), "%Y%m%d_%H%M%S").strftime('%Y-%m-%d %H:%M:%S') if run_start_str_match else "N/A"
    
    # Using f-string padding to align values at column 25.
    # The label (e.g., 'Date:') is left-aligned in a 24-character space.
    # Determine actual status based on pipeline completion
    n_valid = metrics.get('n_valid_responses', 0)
    total_trials = config.getint('Experiment', 'num_trials', fallback=0)
    
    final_status = "COMPLETED" if n_valid > 0 else "FAILED"
    parsing_status = "COMPLETED" if n_valid > 0 else ("PARTIAL" if n_valid < total_trials else "FAILED")
    validation_status = "COMPLETED" if metrics else "FAILED"
    
    header_lines = [
        "="*80, " REPLICATION RUN REPORT", "="*80,
        f"{'Date:':<24}{run_date_display}",
        f"{'Final Status:':<24}{final_status}",
        f"{'Parsing Status:':<24}{parsing_status}",
        f"{'Validation Status:':<24}{validation_status}",
        f"{'Replication Number:':<24}{args.replication_num}",
        f"{'Run Directory:':<24}{os.path.basename(run_specific_dir_path)}",
        f"{'Report File:':<24}{os.path.basename(report_path)}",
        "\n--- Run Parameters ---",
        f"{'Number of Trials (m):':<24}{config.getint('Experiment', 'num_trials', fallback=0)}",
        f"{'Group Size (k):':<24}{k_per_query}",
        f"{'Mapping Strategy:':<24}{config.get('Experiment', 'mapping_strategy', fallback='N/A')}",
        f"{'Personalities Source:':<24}{config.get('Filenames', 'personalities_src', fallback='N/A')}",
        f"{'LLM Model:':<24}{config.get('LLM', 'model_name', fallback='N/A')}",
        f"{'Run Notes:':<24}{args.notes}",
        "="*80, "\n--- Base Query Prompt Used ---"
    ]
    base_query_path = os.path.join(run_specific_dir_path, 'session_queries', 'llm_query_base.txt')
    if os.path.exists(base_query_path):
        with open(base_query_path, 'r', encoding='utf-8') as fq:
            header_lines.append(fq.read().strip())
    else:
        header_lines.append("--- BASE QUERY NOT FOUND ---")
    header_lines.append("-------------------------------")

    # 2. Human-Readable Summary Body
    # Correctly identify the Top-3 accuracy keys to avoid duplicating Top-1
    top_k_acc_key = 'mean_top_3_acc'
    top_k_p_key = 'top_3_acc_p'
    k_num = 3

    def format_metric(value, format_spec):
        """Format a metric value, showing 'N/A' for None values."""
        return f"{value:{format_spec}}" if value is not None else "N/A"

    # Add parsing summary before the results
    parsing_summary_lines = []
    parsing_summary_path = os.path.join(run_specific_dir_path, 'analysis_inputs', 'parsing_summary.txt')
    if os.path.exists(parsing_summary_path):
        with open(parsing_summary_path, 'r', encoding='utf-8') as f_parse:
            parsing_summary_lines = [f_parse.read().strip()]
    else:
        parsing_summary_lines = ["--- Response Parsing Summary ---\nParsing summary not available"]
    
    summary_lines = [
        "="*80, "### OVERALL META-ANALYSIS RESULTS ###", "="*80,
        f"Number of Valid Responses: {metrics.get('n_valid_responses', 0)}",
        ""
    ] + parsing_summary_lines + [
        ""
        f"\n1. Overall Ranking Performance (MRR) (vs Chance={calculate_mrr_chance(k_per_query):.4f}):",
        f"   Mean: {format_metric(metrics.get('mean_mrr'), '.4f')}, Wilcoxon p-value: p = {format_metric(metrics.get('mrr_p'), '.4f')}",
        f"\n2. Overall Ranking Performance (Top-1 Accuracy) (vs Chance={1/k_per_query:.2%}):",
        f"   Mean: {format_metric(metrics.get('mean_top_1_acc'), '.2%')}, Wilcoxon p-value: p = {format_metric(metrics.get('top_1_acc_p'), '.4f')}",
        f"\n3. Overall Ranking Performance (Top-{k_num} Accuracy) (vs Chance={min(k_num, k_per_query)/k_per_query:.2%}):",
        f"   Mean: {format_metric(metrics.get(top_k_acc_key), '.2%')}, Wilcoxon p-value: p = {format_metric(metrics.get(top_k_p_key), '.4f')}",
        f"\n4. Bias and Other Metrics:",
        f"   Top-1 Prediction Bias (StdDev of choice counts): {format_metric(metrics.get('top1_pred_bias_std'), '.4f')}",
        f"   Mean Score Difference (Correct - Incorrect): {format_metric(metrics.get('true_false_score_diff'), '.4f')}"
    ]

    # --- Assemble and Write Report ---
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(header_lines))
            f.write("\n\n")
            f.write("\n".join(summary_lines))
            f.write("\n\n\n<<<METRICS_JSON_START>>>\n")
            f.write(json.dumps(metrics, indent=4))
            f.write("\n<<<METRICS_JSON_END>>>")
        
        print(f"Successfully generated report: {report_path}")

    except IOError as e:
        print(f"Error: Could not write final report to {report_path}. Reason: {e}", file=sys.stderr)
        sys.exit(1)
        return  # Eject for testability

if __name__ == "__main__":
    main()

# === End of src/generate_replication_report.py ===
