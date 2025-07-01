#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/inject_metadata.py

"""
Metadata Injection Utility (inject_metadata.py)

Purpose:
This script scans a directory for text files and injects the file's path and
name as a header into the file's content. This is essential for providing
context to language models that process file content without knowing its origin.

Workflow:
1.  Accepts a target directory to scan.
2.  The scan depth is controlled by the --depth argument.
3.  Identifies all files with a '.txt' extension.
4.  For each file, it prepends a header block containing the filename and path.
5.  The script is idempotent; it will not inject a header if one already exists.

Command-Line Usage:
    # Inject metadata into .txt files in the 'src' directory (depth 0)
    python src/inject_metadata.py src

    # Inject metadata into 'src' and its immediate subdirectories
    python src/inject_metadata.py src --depth 1

    # Inject metadata recursively throughout the entire 'src' tree
    python src/inject_metadata.py src --depth -1
"""

import argparse
import os
import glob
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def inject_metadata_into_report(report_path, key, value):
    """
    Reads a report file, injects a key-value pair into the header,
    and overwrites the original file.
    """
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except IOError as e:
        logging.error(f"  - ERROR: Could not read file {os.path.basename(report_path)}: {e}")
        return False

    # Check if the key already exists to prevent duplicate entries
    if any(line.strip().startswith(key + ":") for line in lines):
        logging.warning(f"  - Skipping: Metadata key '{key}' already exists in {os.path.basename(report_path)}.")
        return False

    # Find the injection point. We'll insert the new line before "Personalities Source:".
    # This is a stable anchor point in the report header.
    injection_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("Personalities Source:"):
            injection_index = i
            break

    if injection_index == -1:
        logging.error(f"  - ERROR: Could not find injection anchor ('Personalities Source:') in {os.path.basename(report_path)}.")
        return False

    # Insert the new metadata line
    lines.insert(injection_index, f"{key}: {value}\n")

    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        logging.info(f"  - Success: Injected '{key}: {value}' into {os.path.basename(report_path)}.")
        return True
    except IOError as e:
        logging.error(f"  - ERROR: Could not write to file {os.path.basename(report_path)}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Injects a metadata key-value pair into all replication reports within a target directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("target_directory", help="The path to the directory containing the run folders (e.g., 'output/.../map-correct').")
    parser.add_argument("--key", required=True, help="The metadata key to inject (e.g., 'Mapping Strategy').")
    parser.add_argument("--value", required=True, help="The metadata value to inject (e.g., 'correct').")
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="Directory traversal depth. 0 for target dir only, -1 for infinite, N for N levels."
    )
    args = parser.parse_args()

    if not os.path.isdir(args.target_directory):
        logging.error(f"FATAL: The specified target directory does not exist: {args.target_directory}")
        return

    logging.info(f"\nScanning for run directories in: '{args.target_directory}'")
    logging.info(f"Will inject -> {args.key}: {args.value}")

    # Find all 'run_*' directories based on the specified depth.
    if args.depth == -1:
        logging.info("Searching with infinite depth (recursive).")
        run_dirs = glob.glob(os.path.join(args.target_directory, '**', 'run_*'), recursive=True)
    else:
        logging.info(f"Searching to a maximum depth of {args.depth} level(s).")
        # Find run_* dirs in the root target_directory (depth 0)
        run_dirs = glob.glob(os.path.join(args.target_directory, 'run_*'))
        
        # Find run_* dirs in subdirectories up to the specified depth
        if args.depth > 0:
            pattern = args.target_directory
            for i in range(args.depth):
                pattern = os.path.join(pattern, '*')
                run_dirs.extend(glob.glob(os.path.join(pattern, 'run_*')))
    
    if not run_dirs:
        logging.error("No 'run_*' directories found to process.")
        return

    processed_count = 0
    success_count = 0
    for run_dir in run_dirs:
        if not os.path.isdir(run_dir):
            continue
        
        logging.info(f"\nProcessing directory: {os.path.relpath(run_dir, args.target_directory)}")
        
        # Find the report file within the run directory
        report_files = glob.glob(os.path.join(run_dir, 'replication_report_*.txt'))
        if not report_files:
            logging.warning("  - No report file found in this directory.")
            continue
        
        # There should only be one report file per run
        report_path = report_files[0]
        processed_count += 1
        if inject_metadata_into_report(report_path, args.key, args.value):
            success_count += 1

    logging.info(f"\n--- Injection Complete ---")
    logging.info(f"Successfully updated {success_count} of {processed_count} reports found.")

if __name__ == "__main__":
    main()

# === End src/inject_metadata.py ===