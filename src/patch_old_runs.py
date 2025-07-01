#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/patch_old_runs.py

"""
Batch-processes historical experiment run directories to create an archived
config.ini file in each one.

This script scans a root directory for all subfolders matching the 'run_*'
pattern. For each folder that does not already contain a 'config.ini.archived',
it calls the `restore_config.py` utility to generate one.

This allows older data to be used with newer analysis scripts that rely on
the archived config for parameter information.
"""

import os
import sys
import glob
import subprocess

def main():
    if len(sys.argv) != 2:
        print("Usage: python patch_old_runs.py <path_to_root_output_directory>")
        sys.exit(1)
    
    root_dir = sys.argv[1]
    if not os.path.isdir(root_dir):
        print(f"Error: Root directory not found at '{root_dir}'")
        sys.exit(1)

    # Find the restore_config.py script relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    restore_script_path = os.path.join(current_dir, "restore_config.py")

    if not os.path.exists(restore_script_path):
        print(f"Error: Cannot find 'restore_config.py' in the same directory.")
        sys.exit(1)

    # Find all potential run directories recursively
    search_pattern = os.path.join(root_dir, "**", "run_*")
    run_dirs = [d for d in glob.glob(search_pattern, recursive=True) if os.path.isdir(d)]

    if not run_dirs:
        print(f"No directories matching 'run_*' found within '{root_dir}'.")
        return

    print(f"Found {len(run_dirs)} total run directories. Checking for patching needs...")
    
    patched_count = 0
    for run_dir in sorted(run_dirs):
        # The restore script handles the check for existing files,
        # but we can call it unconditionally.
        try:
            # We capture output to check if it did any work.
            result = subprocess.run(
                [sys.executable, restore_script_path, run_dir],
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            # If the script printed "Success", it means it did work.
            if "Success" in result.stdout:
                patched_count += 1
                # Print the output from the worker script so the user sees the progress.
                print(result.stdout.strip())

        except subprocess.CalledProcessError as e:
            print(f"Failed to process '{os.path.basename(run_dir)}'. Error:\n{e.stderr}")

    print("\n--- Patching complete ---")
    print(f"Scanned {len(run_dirs)} directories.")
    print(f"Created new config archives for {patched_count} directories.")

if __name__ == "__main__":
    main()