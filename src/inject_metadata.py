#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/inject_metadata.py

"""
Metadata Injection Utility (inject_metadata.py)

Purpose:
This script scans a directory for specified files (e.g., .txt reports, .csv data)
and injects a key-value pair as a header or a new column into the file's content.
This provides context to systems or models processing the file content.

Workflow:
1.  Accepts a target directory to scan.
2.  The scan depth is controlled by the --depth argument.
3.  Identifies files based on the --file_pattern argument (defaults to 'replication_report_*.txt').
4.  For each identified file:
    - If it's a .txt file, it prepends a header block containing the specified key-value pair.
    - If it's a .csv file, it inserts a new column with the specified key as the header
      and the specified value for all rows. The position of this new column can be
      controlled by --column_position.
5.  The script is idempotent; it will not inject a header/column if the metadata
    (key) already exists in the file.

Command-Line Usage:
    # Inject metadata into 'replication_report_*.txt' files (original behavior)
    python src/inject_metadata.py src --key "Strategy" --value "A"

    # Inject metadata into all '.csv' files in the 'data' directory, prepending the column
    python src/inject_metadata.py data --key "Source" --value "External" --file_pattern "*.csv" --depth 0

    # Inject metadata into 'my_data_*.csv' files, inserting the column after the 2nd existing column
    python src/inject_metadata.py data --key "Version" --value "1.0" --file_pattern "my_data_*.csv" --depth -1 --column_position 2

    # Inject metadata into 'report.csv', appending the column (column_position > existing columns)
    python src/inject_metadata.py reports --key "Status" --value "Processed" --file_pattern "report.csv" --column_position 99
"""

import argparse
import os
import glob
import logging
import csv

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

def _inject_metadata_into_txt_report(report_path, key, value):
    """
    Reads a text report file, injects a key-value pair into the header,
    and overwrites the original file. Specifically designed for text reports
    with a 'Personalities Source:' anchor.
    """
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except IOError as e:
        logging.error(f"  - ERROR: Could not read file {os.path.basename(report_path)}: {e}")
        return False

    # Check if the key already exists to prevent duplicate entries
    # For TXT, we check for 'key:' at the start of any line
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

def _inject_metadata_into_csv(file_path, key, value, column_position=0):
    """
    Reads a CSV file, injects a new column with the specified key as header
    and value for all rows.
    """
    temp_file_path = file_path + ".tmp"
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as infile, \
             open(temp_file_path, 'w', newline='', encoding='utf-8') as outfile:
            reader = csv.reader(infile)
            writer = csv.writer(outfile)

            header = next(reader, None) # Read header row
            if header is None:
                logging.warning(f"  - Skipping: CSV file {os.path.basename(file_path)} is empty.")
                return False

            # Check if the key (new column name) already exists in the header
            if key in header:
                logging.warning(f"  - Skipping: Column '{key}' already exists in {os.path.basename(file_path)}.")
                return False

            # Determine insertion index (0-based)
            # column_position 0 or None: insert at index 0 (before first column)
            # column_position N (1-based): insert at index N (after column N, which is at N-1)
            # If N is larger than current number of columns, it will append.
            insertion_index = column_position if column_position >= 0 else 0
            
            # Insert new column header
            new_header = list(header) # Create a mutable copy
            new_header.insert(insertion_index, key)
            writer.writerow(new_header)

            # Insert new column value into each data row
            for row in reader:
                new_row = list(row) # Create a mutable copy
                new_row.insert(insertion_index, value)
                writer.writerow(new_row)

    except IOError as e:
        logging.error(f"  - ERROR: Could not process file {os.path.basename(file_path)}: {e}")
        return False
    except csv.Error as e:
        logging.error(f"  - ERROR: CSV parsing error in {os.path.basename(file_path)}: {e}")
        return False
    except Exception as e:
        logging.error(f"  - An unexpected error occurred with {os.path.basename(file_path)}: {e}")
        return False

    # Replace original file with the modified one
    try:
        os.replace(temp_file_path, file_path)
        logging.info(f"  - Success: Injected column '{key}' with value '{value}' into {os.path.basename(file_path)}.")
        return True
    except OSError as e:
        logging.error(f"  - ERROR: Could not replace original file {os.path.basename(file_path)}: {e}")
        return False


def inject_metadata(file_path, key, value, column_position=0):
    """
    Dispatches to the appropriate metadata injection function based on file extension.
    """
    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == '.txt':
        return _inject_metadata_into_txt_report(file_path, key, value)
    elif file_extension == '.csv':
        return _inject_metadata_into_csv(file_path, key, value, column_position)
    else:
        logging.error(f"  - ERROR: Unsupported file type '{file_extension}' for {os.path.basename(file_path)}. Only .txt and .csv are supported.")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Injects a metadata key-value pair into specified files within a target directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("target_directory", help="The path to the directory containing the files or run folders (e.g., 'output/.../map-correct').")
    parser.add_argument("--key", required=True, help="The metadata key (for .txt) or new column header (for .csv) to inject (e.g., 'Mapping Strategy').")
    parser.add_argument("--value", required=True, help="The metadata value (for .txt) or new column content (for .csv) to inject (e.g., 'correct').")
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="Directory traversal depth. 0 for target dir only, -1 for infinite, N for N levels. Note: For the default 'replication_report_*.txt' pattern, depth applies to 'run_*' subdirectories. For custom patterns, depth applies directly to the file pattern."
    )
    parser.add_argument(
        "--file_pattern",
        default="replication_report_*.txt",
        help="Glob pattern for files to process (e.g., '*.txt', 'data_*.csv')."
    )
    parser.add_argument(
        "--column_position",
        type=int,
        default=0,
        help="For CSV files only: The 1-based position after which to insert the new column. If 0 or omitted, the column is prepended (inserted before column 1). If N is greater than the number of existing columns, the column will be appended."
    )
    args = parser.parse_args()

    if not os.path.isdir(args.target_directory):
        logging.error(f"FATAL: The specified target directory does not exist: {args.target_directory}")
        return

    logging.info(f"\nScanning for files matching pattern '{args.file_pattern}' in: '{args.target_directory}'")
    logging.info(f"Will inject -> Key: '{args.key}', Value: '{args.value}'")
    if os.path.splitext(args.file_pattern)[1].lower() == '.csv':
        if args.column_position == 0:
            logging.info(f"  For CSVs: New column will be prepended (before column 1).")
        else:
            logging.info(f"  For CSVs: New column will be inserted after column {args.column_position}.")


    files_to_process = []
    
    # Determine if we are using the default 'replication_report_*.txt' pattern
    is_default_pattern = (args.file_pattern == "replication_report_*.txt")

    if is_default_pattern:
        logging.info("Using default file pattern, applying original 'run_*' directory traversal logic.")
        if args.depth == -1:
            logging.info("Searching with infinite depth (recursive) for 'run_*' directories.")
            run_dirs = glob.glob(os.path.join(args.target_directory, '**', 'run_*'), recursive=True)
        else:
            logging.info(f"Searching 'run_*' directories to a maximum depth of {args.depth} level(s).")
            run_dirs = []
            # Find run_* dirs in the root target_directory (depth 0 for run_dirs)
            if args.depth >= 0: # This covers the original depth 0 case
                run_dirs.extend(glob.glob(os.path.join(args.target_directory, 'run_*')))
            
            # Find run_* dirs in subdirectories up to the specified depth
            if args.depth > 0:
                current_pattern_base = args.target_directory
                for i in range(args.depth):
                    current_pattern_base = os.path.join(current_pattern_base, '*')
                    run_dirs.extend(glob.glob(os.path.join(current_pattern_base, 'run_*')))
        
        # Now, for each found run_dir, find the replication_report_*.txt
        for run_dir in run_dirs:
            if os.path.isdir(run_dir):
                report_files = glob.glob(os.path.join(run_dir, args.file_pattern))
                if report_files:
                    # Assuming there's only one report file per run directory based on original logic
                    files_to_process.append(report_files[0]) 
    else: # Custom file pattern, apply depth directly to the file pattern
        logging.info("Using custom file pattern, applying depth directly to file search.")
        if args.depth == -1:
            logging.info("Searching with infinite depth (recursive).")
            search_pattern = os.path.join(args.target_directory, '**', args.file_pattern)
            files_to_process = glob.glob(search_pattern, recursive=True)
        else:
            logging.info(f"Searching to a maximum depth of {args.depth} level(s).")
            current_pattern_base = args.target_directory
            # The range for depth needs to include the current directory (depth 0)
            # and then go down to args.depth levels.
            # So, for depth 0, we search target_directory.
            # For depth 1, we search target_directory and target_directory/*
            # This means the loop should run args.depth + 1 times.
            for i in range(args.depth + 1): 
                temp_pattern_base = current_pattern_base
                if i > 0: # For depths > 0, add a wildcard for subdirectory
                    temp_pattern_base = os.path.join(temp_pattern_base, '*')
                
                search_pattern = os.path.join(temp_pattern_base, args.file_pattern)
                files_to_process.extend(glob.glob(search_pattern))
                
                # Update current_pattern_base for the next iteration to go deeper
                current_pattern_base = os.path.join(current_pattern_base, '*')


    # Remove duplicates and sort for consistent processing order
    files_to_process = sorted(list(set(files_to_process)))

    if not files_to_process:
        logging.error(f"No files matching '{args.file_pattern}' found to process.")
        return

    processed_count = 0
    success_count = 0
    for file_path in files_to_process:
        if not os.path.isfile(file_path):
            continue
        
        logging.info(f"\nProcessing file: {os.path.relpath(file_path, args.target_directory)}")
        processed_count += 1
        if inject_metadata(file_path, args.key, args.value, args.column_position):
            success_count += 1

    logging.info(f"\n--- Injection Complete ---")
    logging.info(f"Successfully updated {success_count} of {processed_count} files found.")

if __name__ == "__main__":
    main()

# === End src/inject_metadata.py ===