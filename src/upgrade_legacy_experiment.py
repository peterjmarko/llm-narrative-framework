#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
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
# Filename: src/upgrade_legacy_experiment.py

"""
Upgrades a legacy experiment by creating missing config archives.

This script serves as a batch controller that recursively scans a target
experiment directory for all `run_*` subfolders. For each run, it calls the
`restore_experiment_config.py` utility to reverse-engineer a
`config.ini.archived` file from a `replication_report.txt`.

This process makes legacy data compatible with the modern reprocessing and
analysis pipeline. It is a key part of the `migrate_experiment.ps1` workflow.
"""

import os
import sys
import glob
import subprocess

def main():
    if len(sys.argv) != 2:
        print("Usage: python patch_old_experiment.py <path_to_root_output_directory>")
        sys.exit(1)
    
    root_dir = sys.argv[1]
    if not os.path.isdir(root_dir):
        print(f"Error: Root directory not found at '{root_dir}'")
        sys.exit(1)

    # Find the restore_experiment_config.py script relative to this script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    restore_script_path = os.path.join(current_dir, "restore_experiment_config.py")

    if not os.path.exists(restore_script_path):
        print(f"Error: Cannot find 'restore_experiment_config.py' in the same directory.")
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
        # We now run the patcher with check=False to manually control output and exit.
        result = subprocess.run(
            [sys.executable, restore_script_path, run_dir],
            capture_output=True,
            text=True,
            encoding='utf-8',
            check=False
        )

        # Always print the output from the worker for full transparency.
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)

        # If the worker script returned a non-zero exit code, it failed.
        if result.returncode != 0:
            print(f"FATAL: Worker script failed for '{os.path.basename(run_dir)}'. Halting patch process.", file=sys.stderr)
            sys.exit(1) # Exit the patcher with an error code.
        
        # Only count as patched if we see the success message.
        if "Success" in result.stdout:
            patched_count += 1

    print("\n--- Patching complete ---")
    print(f"Scanned {len(run_dirs)} directories.")
    print(f"Created new config archives for {patched_count} directories.")

if __name__ == "__main__":
    main()

# === End of src/upgrade_legacy_experiment.py ===
