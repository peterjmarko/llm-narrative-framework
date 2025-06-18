#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/compile_results.py

"""
Compile Batch Results (compile_results.py)

Purpose:
This script scans a directory for all individual run folders (e.g., 'run_*'),
parses the 'replication_report_...txt' from each to find a machine-readable JSON
block, and aggregates the key parameters and final performance metrics into a
single summary CSV (typically `final_summary_results.csv`).

This script is intended to be called automatically at the end of a batch process
(like `run_replications.ps1`) to summarize all runs within that batch. The final,
cross-batch aggregation is now handled by `run_anova.py`.
"""

import os
import sys
import glob
import re
import json
import csv
import numpy as np

def parse_report_header(report_content):
    """Extracts key parameters from the report header."""
    params = {}
    def extract(pattern, text):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    params['run_directory'] = extract(r"Run Directory:\s*(.*)", report_content)
    params['model'] = extract(r"LLM Model:\s*(.*)", report_content)
    params['k'] = extract(r"Items per Query \(k\):\s*(\d+)", report_content)
    params['m'] = extract(r"Num Iterations \(m\):\s*(\d+)", report_content)
    params['db'] = extract(r"Personalities Source:\s*(.*)", report_content)
    
    if params['run_directory']:
        temp_match = re.search(r"tmp-([\d.]+)", params['run_directory'])
        params['temperature'] = temp_match.group(1) if temp_match else None
        rep_match = re.search(r"rep-(\d+)", params['run_directory'])
        params['replication'] = rep_match.group(1) if rep_match else None

    return params

def parse_metrics_json(report_content):
    """
    Finds and parses the machine-readable JSON block from the report content.
    """
    try:
        # Find the content between the start and end tags.
        # re.DOTALL allows '.' to match newline characters.
        match = re.search(r"<<<METRICS_JSON_START>>>(.*?)<<<METRICS_JSON_END>>>", report_content, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)
        else:
            return None # Return None if tags are not found
    except (IndexError, json.JSONDecodeError):
        # Return None if the content is malformed or missing
        return None

def main():
    if len(sys.argv) > 1:
        output_dir = sys.argv[1]
    else:
        output_dir = 'output'
        print(f"No output directory specified. Defaulting to './{output_dir}'")

    if not os.path.isdir(output_dir):
        print(f"Error: Specified output directory '{output_dir}' does not exist.")
        sys.exit(1)

    report_files = glob.glob(os.path.join(output_dir, "run_*", "replication_report_*.txt"))
    
    if not report_files:
        print(f"No report files found in subdirectories of '{output_dir}'.")
        return

    all_results = []
    for report_path in sorted(report_files):
        print(f"Processing: {os.path.basename(os.path.dirname(report_path))}")
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        run_params = parse_report_header(content)
        metrics = parse_metrics_json(content)
        
        if metrics:
            # Round all float values for cleaner CSV output
            for key, value in metrics.items():
                if isinstance(value, float):
                    metrics[key] = round(value, 4)
            
            run_params.update(metrics)
            all_results.append(run_params)
        else:
            print(f"  - Warning: Could not find or parse metrics JSON in {os.path.basename(report_path)}")

    if not all_results:
        print("No valid results to compile.")
        return

    # Write to CSV
    output_csv_path = os.path.join(output_dir, "final_summary_results.csv")
    
    # Dynamically determine all possible headers from the collected data
    fieldnames = []
    if all_results:
        all_keys = set().union(*(d.keys() for d in all_results))
        # This order exactly matches the user's specification.
        preferred_order = [
            'run_directory', 'replication', 'model', 'temperature', 'k', 'm', 'db',
            'mwu_stouffer_z', 'mwu_stouffer_p', 'mwu_fisher_chi2', 'mwu_fisher_p',
            'mean_effect_size_r', 'effect_size_r_p',
            'mean_mrr', 'mrr_p',
            'mean_top_1_acc', 'top_1_acc_p',
            'mean_top_3_acc', 'top_3_acc_p'
        ]
        # Sort headers by preferred order, then alphabetically for any unexpected keys.
        # This handles dynamic keys like 'mean_top_5_acc' if the analysis was run with a different K.
        fieldnames = sorted(list(all_keys), key=lambda x: (preferred_order.index(x) if x in preferred_order else 99, x))

    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=fieldnames, quoting=csv.QUOTE_NONE)
        writer.writeheader()
        writer.writerows(all_results)
        
    print(f"\nSuccessfully compiled {len(all_results)} results into: {output_csv_path}")

if __name__ == "__main__":
    main()