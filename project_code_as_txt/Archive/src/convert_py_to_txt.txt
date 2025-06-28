# -*- coding: utf-8 -*-
# Filename: utilities/convert_py_to_txt.py

"""
Generates text (.txt) versions of specified script files (e.g., .py, .ps1)
within a project and maintains an archive of previously generated text files.

Purpose:
This script serves two main purposes:
1.  Archiving: Before generating new .txt files, it copies the current contents
    of the `project_code_as_txt` directory (excluding its 'Archive' subfolder)
    into the `project_code_as_txt/Archive` subfolder. This process merges
    and overwrites existing files/folders in the 'Archive' subfolder if they
    share the same name as items in `project_code_as_txt`. Items unique to
    the 'Archive' (e.g., older versions or files no longer present in the main
    .py codebase) are preserved. This effectively creates a versioned backup
    of the generated text files.
2.  Conversion: It scans the project directory (excluding specified folders)
    for all Python (.py) and PowerShell (.ps1) files. Each found script file is then copied and
    renamed with a .txt extension into a designated output directory
    (by default, 'project_code_as_txt' at the project root), preserving
    the original directory structure.

Key Features:
-   **Automated Archiving**: Preserves the state of `project_code_as_txt`
    before each new conversion run.
-   **Recursive Script Scan**: Finds .py and .ps1 files in subdirectories.
-   **Directory Structure Preservation**: Replicates the source directory
    structure in the output .txt directory.
-   **Configurable Exclusions**: Allows specifying directories to skip during
    the script file scan (e.g., .venv, __pycache__, the output directory itself).
-   **Configurable Output and Archive Names**: The names of the main output
    directory for .txt files and its archive subfolder can be customized
    via constants.

Configuration (at the top of the script):
-   `EXCLUDE_SCAN_DIRS`: A set of directory names (relative to project root)
    to exclude from the script file search.
-   `TXT_OUTPUT_SUBDIR_NAME`: The name of the subdirectory (at project root)
    where .txt files will be stored (default: "project_code_as_txt").
-   `ARCHIVE_SUBDIR_NAME`: The name of the sub-subdirectory within
    `TXT_OUTPUT_SUBDIR_NAME` used for archiving (default: "Archive").

Execution:
The script is intended to be run from the command line. It attempts to deduce
the project's root directory assuming it is located in a 'utilities' folder
directly under the project root (e.g., `my_project/utilities/convert_py_to_txt.py`).
If this deduction fails, it falls back to using the parent of the current
working directory, and then the current working directory itself, issuing warnings.

Example Usage:
    python utilities/convert_py_to_txt.py

Dependencies:
-   Python 3.8 or newer is required for the `shutil.copytree(..., dirs_exist_ok=True)`
    functionality used in the archiving process.

Assumed Directory Structure (for default configuration):
    project_root/
    ├── utilities/
    │   └── convert_py_to_txt.py  (this script)
    ├── project_code_as_txt/      (output directory for .txt files)
    │   ├── Archive/              (archive of previous .txt files)
    │   │   └── ...
    │   └── (current .txt files mirroring script structure)
    │       └── some_module.txt
    │       └── sub_package/
    │           └── another_module.txt
    ├── some_module.py
    ├── run_scripts.ps1
    ├── sub_package/
    │   └── another_module.py
    └── ... (other project files and folders)
"""

# === Start of utilities/convert_py_to_txt.py ===

import pathlib
import shutil
import os

# --- Configuration ---
# Directories to explicitly exclude from the search for script files (relative to project root)
# Add any other directories you want to skip.
EXCLUDE_SCAN_DIRS = {".venv", "archive", "__pycache__", "scripts_txt", "project_code_as_txt"}

# Name of the subdirectory to create at the project root for the .txt files
TXT_OUTPUT_SUBDIR_NAME = "project_code_as_txt"
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
        print(f"Info: Source directory '{source_dir.resolve()}' for archiving does not exist. Nothing to archive.")
        return

    # 1. Ensure archive_base_dir exists and is a directory.
    if archive_base_dir.is_file():  # If it's a file, remove it
        print(f"Warning: Archive path '{archive_base_dir.resolve()}' is a file. Removing it to create a directory.")
        try:
            archive_base_dir.unlink()
        except OSError as e:
            print(f"Error: Could not remove file '{archive_base_dir.resolve()}': {e}. Archiving aborted.")
            return
    elif archive_base_dir.exists() and not archive_base_dir.is_dir(): # Exists but not a file and not a dir (e.g. broken symlink)
        print(f"Warning: Archive path '{archive_base_dir.resolve()}' is an unexpected item. Attempting to remove with shutil.rmtree.")
        try:
            shutil.rmtree(archive_base_dir) # More forceful removal
        except OSError as e:
            print(f"Error: Could not remove item '{archive_base_dir.resolve()}': {e}. Archiving aborted.")
            return

    try:
        archive_base_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error: Could not create/ensure archive directory '{archive_base_dir.resolve()}': {e}. Archiving aborted.")
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
                print(f"Error: Archiving directory '{item_path.name}' failed. This script requires Python 3.8+ for the 'dirs_exist_ok' feature in shutil.copytree. Please upgrade Python or modify the script for older versions.")
                error_count +=1
            else:
                print(f"Error archiving '{item_path.resolve()}' to '{destination_path.resolve()}': {te}")
                error_count += 1
        except Exception as e:
            print(f"Error archiving '{item_path.resolve()}' to '{destination_path.resolve()}': {e}")
            error_count += 1

    print(f"Archiving summary: {archived_items_count} items from '{source_dir.name}' processed for archiving into '{archive_base_dir.name}'.")
    if error_count > 0:
        print(f"Archiving encountered {error_count} errors during item copying.")
    print("--- End Archiving ---")


def convert_scripts_to_txt(project_root_path, output_subdir_name, exclude_dirs):
    """
    Copies all .py and .ps1 files from the project directory and its subdirectories
    (excluding specified ones) into a new subdirectory, renaming them to .txt.

    Args:
        project_root_path (pathlib.Path): The root path of the project.
        output_subdir_name (str): The name of the subdirectory to create for .txt files.
        exclude_dirs (set): A set of directory names to exclude from scanning.
    """
    output_dir = project_root_path / output_subdir_name

    if output_dir.exists():
        print(f"Output directory '{output_dir.resolve()}' already exists. Files will be added/overwritten.")
    else:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            print(f"Created output directory: {output_dir.resolve()}")
        except Exception as e:
            print(f"Error: Could not create output directory '{output_dir.resolve()}': {e}")
            return

    print(f"\nScanning for .py and .ps1 files in: {project_root_path.resolve()}")
    print(f"Excluding directories: {', '.join(sorted(list(exclude_dirs))) if exclude_dirs else 'None'}")

    copied_count = 0
    skipped_count = 0
    error_count = 0
    
    # Create a combined list of all .py and .ps1 files
    script_files = list(project_root_path.glob('**/*.py')) + list(project_root_path.glob('**/*.ps1'))

    for script_file_path in script_files:
        if not script_file_path.is_file():
            continue

        is_excluded = False
        try:
            relative_to_project = script_file_path.relative_to(project_root_path)
            path_parts = list(relative_to_project.parts[:-1])

            if any(part in exclude_dirs for part in path_parts):
                is_excluded = True
        except ValueError:
            print(f"Warning: Could not determine relative path for {script_file_path.resolve()}. Skipping.")
            skipped_count +=1
            continue

        if is_excluded:
            skipped_count += 1
            continue

        try:
            relative_path = script_file_path.relative_to(project_root_path)
        except ValueError:
            print(f"Error: Could not make '{script_file_path.resolve()}' relative to '{project_root_path.resolve()}'. Skipping.")
            error_count += 1
            continue

        target_txt_dir = output_dir / relative_path.parent
        try:
            target_txt_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"Error: Could not create target subdirectory '{target_txt_dir.resolve()}': {e}")
            error_count += 1
            continue

        txt_filename = script_file_path.stem + ".txt"
        target_txt_path = target_txt_dir / txt_filename

        try:
            shutil.copy2(script_file_path, target_txt_path)
            copied_count += 1
        except Exception as e:
            print(f"Error: Could not copy '{script_file_path.resolve()}' to '{target_txt_path.resolve()}': {e}")
            error_count += 1

    print("\n--- Conversion Summary ---")
    print(f"Script files (.py, .ps1) found and copied as .txt: {copied_count}")
    print(f"Files skipped (e.g., in excluded directories): {skipped_count}")
    print(f"Errors during copy/directory creation: {error_count}")
    if error_count > 0:
        print("Please review error messages above.")
    print(f"Output directory: {output_dir.resolve()}")


if __name__ == "__main__":
    try:
        script_file_path = pathlib.Path(__file__).resolve()
        project_directory = script_file_path.parent.parent
    except NameError:
        print("Warning: __file__ not defined. Assuming script is run from 'utilities' under project root.")
        project_directory = pathlib.Path.cwd().parent # Assumes 'utilities' is a direct child of project root

    if not project_directory.is_dir():
        print(f"Error: Deduced project directory '{project_directory.resolve()}' seems invalid (e.g. does not exist or is not a directory).")
        project_directory = pathlib.Path.cwd()
        print(f"Warning: Using current working directory as project root: {project_directory.resolve()}")

    # --- Archiving Step ---
    print(f"Starting archiving process for TXT files in: {project_directory.resolve() / TXT_OUTPUT_SUBDIR_NAME}")
    archive_previous_txt_versions(project_directory, TXT_OUTPUT_SUBDIR_NAME, ARCHIVE_SUBDIR_NAME)

    # --- Conversion Step ---
    print(f"\nStarting script to TXT conversion for project: {project_directory.resolve()}")
    convert_scripts_to_txt(project_directory, TXT_OUTPUT_SUBDIR_NAME, EXCLUDE_SCAN_DIRS)
    print("\nConversion process finished.")

    # === End of script ===