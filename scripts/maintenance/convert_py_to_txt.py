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
# Filename: scripts/maintenance/convert_py_to_txt.py

"""
A utility to create text-based copies of all project script files.

This script scans the project for Python (.py) and PowerShell (.ps1) files and
creates a mirror of the directory structure in a dedicated output folder,
converting each script into a plain text (.txt) file. This is useful for
preparing the entire codebase for analysis by language models.

Key Features:
-   **Comprehensive Scan**: Processes both Python and PowerShell scripts.
-   **Structure Preservation**: Recreates the original directory hierarchy in the
    output folder to maintain project context.
-   **Automated Archiving**: Before each run, it archives the previous set of
    text files, providing a simple version history.
-   **Configurable Depth**: The scan depth can be controlled via a command-line
    argument, allowing for full recursive scans or shallow copies.

Usage:
    # Create .txt copies for scripts in the project root only (depth=0)
    pdm run txt-copy -- --depth 0

    # Recursively create .txt copies for all scripts in the project
    pdm run txt-copy -- --depth -1
"""

# === Start of maintenance/convert_py_to_txt.py ===

import pathlib
import shutil
import os
import argparse
import sys

class TxtColors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def cprint(text, color=None):
    """Prints text in a specified color if the output is a TTY."""
    if color and sys.stdout.isatty():
        print(f"{color}{text}{TxtColors.ENDC}")
    else:
        print(text)

# --- Configuration ---
# Directories to explicitly exclude from the search for script files (relative to project root)
# Add any other directories you want to skip.
EXCLUDE_SCAN_DIRS = {".venv", "archive", "__pycache__", "scripts_txt", "project_code_as_txt"}

# Path relative to the project root for the .txt files
TXT_OUTPUT_SUBDIR_NAME = "output/project_code_as_txt"
# Name of the sub-subdirectory within TXT_OUTPUT_SUBDIR_NAME for archiving previous versions
ARCHIVE_SUBDIR_NAME = "Archive"
# --- End Configuration ---

def archive_previous_txt_versions(project_root_path: pathlib.Path,
                                  txt_output_subdir_name: str,
                                  archive_subdir_name: str):
    """
    Archives the current contents of the TXT output directory
    (excluding the archive folder itself) into its 'Archive' subfolder.
    Copies files and directories, overwriting existing items in the archive
    if they share the same name. Items in the archive not present in the
    source TXT output directory will be preserved.
    Requires Python 3.8+ for shutil.copytree(..., dirs_exist_ok=True).
    """
    source_dir = project_root_path / txt_output_subdir_name
    archive_base_dir = source_dir / archive_subdir_name  # e.g., project_code_as_txt/Archive

    if not source_dir.exists() or not source_dir.is_dir():
        cprint(f"Info: Source directory '{source_dir.resolve()}' for archiving does not exist. Nothing to archive.", TxtColors.CYAN)
        return

    # 1. Ensure archive_base_dir exists and is a directory.
    if archive_base_dir.is_file():  # If it's a file, remove it
        cprint(f"Warning: Archive path '{archive_base_dir.resolve()}' is a file. Removing it to create a directory.", TxtColors.WARNING)
        try:
            archive_base_dir.unlink()
        except OSError as e:
            cprint(f"Error: Could not remove file '{archive_base_dir.resolve()}': {e}. Archiving aborted.", TxtColors.FAIL)
            return
    elif archive_base_dir.exists() and not archive_base_dir.is_dir(): # Exists but not a file and not a dir (e.g. broken symlink)
        cprint(f"Warning: Archive path '{archive_base_dir.resolve()}' is an unexpected item. Attempting to remove with shutil.rmtree.", TxtColors.WARNING)
        try:
            shutil.rmtree(archive_base_dir) # More forceful removal
        except OSError as e:
            cprint(f"Error: Could not remove item '{archive_base_dir.resolve()}': {e}. Archiving aborted.", TxtColors.FAIL)
            return

    try:
        archive_base_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        cprint(f"Error: Could not create/ensure archive directory '{archive_base_dir.resolve()}': {e}. Archiving aborted.", TxtColors.FAIL)
        return

    print(f"\nArchiving contents of '{source_dir.resolve()}' to '{archive_base_dir.resolve()}' (merging/overwriting)...")
    archived_items_count = 0
    error_count = 0

    # 2. Iterate through items in source_dir and copy them to archive_base_dir
    for item_path in source_dir.iterdir():
        # Skip the archive directory itself to prevent recursion or errors
        if item_path.name == archive_subdir_name:
            continue

        destination_path = archive_base_dir / item_path.name

        try:
            # Handle pre-existing conflicting types at destination
            if destination_path.exists():
                if item_path.is_dir() and not destination_path.is_dir():  # Source is dir, dest is file
                    print(f"  - Destination '{destination_path.resolve()}' is a file, removing to copy directory.")
                    destination_path.unlink()
                elif item_path.is_file() and not destination_path.is_file():  # Source is file, dest is dir
                    print(f"  - Destination '{destination_path.resolve()}' is a directory, removing to copy file.")
                    shutil.rmtree(destination_path)

            if item_path.is_file():
                shutil.copy2(item_path, destination_path)
                archived_items_count += 1
            elif item_path.is_dir():
                shutil.copytree(item_path, destination_path, dirs_exist_ok=True)
                archived_items_count += 1
        except TypeError as te: # Specifically catch if dirs_exist_ok is not supported
            if "dirs_exist_ok" in str(te):
                cprint(f"Error: Archiving directory '{item_path.name}' failed. This script requires Python 3.8+ for the 'dirs_exist_ok' feature in shutil.copytree. Please upgrade Python or modify the script for older versions.", TxtColors.FAIL)
                error_count +=1
            else:
                cprint(f"Error archiving '{item_path.resolve()}' to '{destination_path.resolve()}': {te}", TxtColors.FAIL)
                error_count += 1
        except Exception as e:
            cprint(f"Error archiving '{item_path.resolve()}' to '{destination_path.resolve()}': {e}", TxtColors.FAIL)
            error_count += 1

    cprint(f"Archiving summary: {archived_items_count} items from '{source_dir.name}' processed for archiving into '{archive_base_dir.name}'.", TxtColors.GREEN)
    if error_count > 0:
        cprint(f"Archiving encountered {error_count} errors during item copying.", TxtColors.WARNING)
    cprint("--- End Archiving ---", TxtColors.BLUE)


def convert_scripts_to_txt(project_root_path, output_subdir_name, exclude_dirs, depth):
    """
    Copies all .py and .ps1 files from the project directory, respecting recursion depth,
    into a new subdirectory, renaming them to .txt.

    Args:
        project_root_path (pathlib.Path): The root path of the project to scan.
        output_subdir_name (str): The name of the subdirectory for .txt files.
        exclude_dirs (set): A set of directory names to exclude from scanning.
        depth (int): The recursion depth to scan for files.
    """
    output_dir = project_root_path / output_subdir_name
    
    if not output_dir.exists():
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created output directory: {output_dir.resolve()}")
        except Exception as e:
            print(f"Error: Could not create output directory '{output_dir.resolve()}': {e}")
            return

    print(f"\nScanning for .py and .ps1 files in: {project_root_path.resolve()} with depth={depth}")
    cprint(f"Excluding directories: {', '.join(sorted(list(exclude_dirs))) if exclude_dirs else 'None'}", TxtColors.CYAN)

    copied_count = 0
    error_count = 0
    
    source_root_str = str(project_root_path.resolve())
    base_depth = source_root_str.count(os.sep)

    for root, dirs, files in os.walk(source_root_str, topdown=True):
        # Prune excluded directories before descending into them
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        # Prune directories based on depth
        if depth != -1:
            current_depth = root.count(os.sep) - base_depth
            if current_depth >= depth:
                dirs[:] = []  # Clear subdirectories to prevent further descent

        for filename in files:
            if not (filename.endswith(".py") or filename.endswith(".ps1")):
                continue

            script_file_path = pathlib.Path(root) / filename
            try:
                relative_path = script_file_path.relative_to(project_root_path)
            except ValueError:
                print(f"Error: Could not make '{script_file_path}' relative to '{project_root_path}'. Skipping.")
                error_count += 1
                continue

            target_txt_dir = output_dir / relative_path.parent
            try:
                target_txt_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error: Could not create target subdirectory '{target_txt_dir}': {e}")
                error_count += 1
                continue

            txt_filename = script_file_path.stem + ".txt"
            target_txt_path = target_txt_dir / txt_filename

            try:
                shutil.copy2(script_file_path, target_txt_path)
                copied_count += 1
            except Exception as e:
                print(f"Error: Could not copy '{script_file_path}' to '{target_txt_path}': {e}")
                error_count += 1

    cprint("\n--- Conversion Summary ---", TxtColors.HEADER)
    cprint(f"Script files (.py, .ps1) found and copied as .txt: {copied_count}", TxtColors.GREEN)
    cprint(f"Errors during copy/directory creation: {error_count}", TxtColors.WARNING if error_count > 0 else TxtColors.GREEN)
    if error_count > 0:
        cprint("Please review error messages above.", TxtColors.FAIL)
    relative_output = output_dir.relative_to(project_root_path)
    cprint(f"Output directory: {relative_output}", TxtColors.BLUE)


def main():
    """
    Main function to parse arguments and drive the archiving and conversion process.
    """
    parser = argparse.ArgumentParser(
        description="Archive old and generate new .txt versions of .py and .ps1 files.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "project_dir",
        nargs='?',
        default=os.getcwd(),
        help="The root directory of the project to scan. Defaults to the current working directory."
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="Recursion depth for scanning script files.\n"
             "  0: Target folder only (default).\n"
             " -1: Infinite recursion.\n"
             " >0: Descend N levels deep."
    )
    args = parser.parse_args()

    project_directory = pathlib.Path(args.project_dir).resolve()

    if not project_directory.is_dir():
        print(f"Error: The specified project directory does not exist or is not a directory: '{project_directory}'")
        return

    cprint(f"Using project root: {project_directory}", TxtColors.BLUE)

    # --- Archiving Step ---
    print(f"\n--- Starting Archiving Process ---")
    archive_previous_txt_versions(project_directory, TXT_OUTPUT_SUBDIR_NAME, ARCHIVE_SUBDIR_NAME)

    # --- Conversion Step ---
    print(f"\n--- Starting Script Conversion ---")
    convert_scripts_to_txt(project_directory, TXT_OUTPUT_SUBDIR_NAME, EXCLUDE_SCAN_DIRS, args.depth)
    cprint("\nConversion process finished.", TxtColors.GREEN)


if __name__ == "__main__":  # pragma: no cover
    main()

# === End of scripts/maintenance/convert_py_to_txt.py ===
