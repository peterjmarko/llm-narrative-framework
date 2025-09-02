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
# Filename: scripts/list_project_files.py

"""
Project Structure Reporter (list_project_files.py)

Purpose:
This script scans a project directory and generates a detailed text report,
`project_structure_report_depth_[N].txt`. It provides a snapshot of the
project's layout, including a hierarchical file tree and summaries of key files.
This is useful for documentation, project handovers, and getting a quick
overview of a codebase.

Workflow:
1.  Accepts a target directory to scan (or auto-detects the project root).
2.  Generates a hierarchical tree view of directories and files.
3.  The overall scan depth is controlled by the `--depth` argument.
4.  **Custom Depths:** Scan depth can be customized for specific folders
    by editing the `CUSTOM_DEPTH_MAP` dictionary in the script's configuration.
    This allows for more detailed views of important folders (like `src`) while
    keeping others summarized (like `output`).
5.  Excludes configured directories (e.g., .venv, .git) and file types.
6.  Saves the complete report to a dedicated output directory.

Command-Line Usage:
    # Scan the current project directory (root level only, depth 0)
    python src/list_project_files.py .

    # Scan the project directory and its immediate subdirectories (depth 1)
    python src/list_project_files.py . --depth 1

    # Scan the entire project directory tree recursively (infinite depth)
    python src/list_project_files.py . --depth -1

Note: For custom depth control (e.g., `src` at depth 2, `output` at depth 0),
modify the `CUSTOM_DEPTH_MAP` dictionary within the script.
"""

# === Start of utilities/list_project_files.py ===

# ANSI color codes for better terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

import pathlib
import sys
import os # Keep os for os.stat if needed, though pathlib usually suffices
from datetime import datetime
import traceback # For detailed error logging if needed
import argparse

# --- Configuration ---
# Define custom scan depths for specific directories.
# Paths should be relative to the project root, using forward slashes.
# The integer value represents the desired depth *from that folder*.
#   - 0: Show the folder name, but do not list its contents.
#   - 1: Show the folder's immediate children.
#   - 2: Show children and grandchildren.
#   - -1: Show all contents recursively (infinite depth).
# Any folder NOT listed here will use the default --depth from the command line.
CUSTOM_DEPTH_MAP = {
    "archive": 0,           # Hide contents of 'archive'
    "data": 3,              # Show contents of 'data' down to 3 levels deep, except:
    "data/backup": 0,           # 'backup' (hide)
    "debug": 0,             # Hide contents of 'archive'
    "docs": 2,              # Show contents of 'docs' down to 2 levels deep
    "htmlcov": 0,           # Hide contents of 'htmlcov' folder
    "linter_backups": 0,    # Hide contents of 'linter_backups'
    "node_modules": 0,      # Hide contents of 'node_modules'
    "output": 1,            # Show contents of 'output' down to 3 levels deep, except:
    "output/project_code_as_txt": 0,    # 'project_code_as_txt' (hide)
    "output/project_reports": 0,        # 'project_reports' (hide)
    "output/test*": 0,      # Hide contents of 'output/test*' folders
    "scripts": 2,           # Show contents of 'scripts' down to 2 levels deep, except:
    "scripts/__pycache__": 0,   # '__pycache__' (hide)
    "src": 2,               # Show contents of 'src' down to 2 levels deep, except:
    "src/__pycache__": 0,                        # '__pycache__' (hide)
    "src/archive": 0,                           # 'archive' (hide)
    "src/llm_personality_matching.egg-info": 0, # 'llm_personality_matching.egg-info' (hide)
    "src/temp": 0,                              # 'temp' (hide)
    "test_backups": 0,      # Hide contents of 'test_backups'
    "tests": 1,             # Show contents of 'tests' down to 1 level deep, except:
    "tests/__pycache__": 0,     # '__pycache__' (hide)
    "tests/archive": 0,         # 'archive' (hide)
}

# Directories to completely exclude from the scan (names, not paths)
EXCLUDE_DIRS_SET = {
    ".venv", "venv", "__pycache__", ".git", ".vscode", ".idea",
    ".pytest_cache", "node_modules", "build", "dist",
    "archive", "instance", "*.egg-info", # Common build/dist/docs/archive folders
    "weather", "project_code_as_txt/weather" # Specific to this project (weather scripts and data)
}
# Specific files to always exclude by name
EXCLUDE_FILES_SET = {".DS_Store", "Thumbs.db", "*.pyc", "*.pyo", "*.pyd", "~$*.*"}
# File extensions to exclude (alternative to listing full names in EXCLUDE_FILES_SET)
EXCLUDE_EXTENSIONS_SET = {".pyc", ".pyo", ".pyd", ".log", ".tmp", ".swp"} # Add more as needed

OUTPUT_FILENAME = "project_structure_report.txt"
REPORT_SUBDIR = "project_reports" # Subdirectory within 'output' for these reports
FILE_COUNT_WARNING_THRESHOLD = 10000 # Warn if the number of items to inspect exceeds this.
# --- End Configuration ---

def get_project_root():
    """Determines the project root, assuming this script is in utilities/"""
    try:
        # If __file__ is defined (standard case)
        script_path = pathlib.Path(__file__).resolve()
        # utilities_dir -> project_root
        project_root = script_path.parent.parent
        if not (project_root / "config.py").exists() and not (project_root / "README.md").exists(): # Heuristic
             print(f"Warning: Heuristic check failed for project root at {project_root}. "
                   f"config.py or README.md not found. Falling back to script_dir.parent.")
    except NameError:
        # Fallback if __file__ is not defined (e.g., interactive session, rare)
        print("Warning: __file__ not defined. Attempting to use CWD's parent as project root.")
        current_working_dir = pathlib.Path.cwd()
        # Check if CWD looks like 'utilities' and parent has config.py
        if current_working_dir.name == "utilities" and (current_working_dir.parent / "config.py").exists():
            project_root = current_working_dir.parent
        else: # Default to CWD if unsure, user might be running it from project root
            project_root = current_working_dir
            print(f"  Using current working directory as project root: {project_root}")
    except Exception as e:
        print(f"Warning: Error resolving script path: {e}. Falling back to CWD.")
        project_root = pathlib.Path.cwd()
    return project_root

def should_exclude_path(path_item: pathlib.Path, project_root: pathlib.Path):
    """
    Checks if a path item should be excluded based on configured sets.
    Considers relative path to project root for directory exclusion.
    """
    # Exclude specific files by name
    if path_item.name in EXCLUDE_FILES_SET:
        return True
    # Exclude by extension
    if path_item.suffix.lower() in EXCLUDE_EXTENSIONS_SET:
        return True

    # Check directory exclusion (applies if path_item is a dir or inside an excluded dir)
    try:
        # Check if the item itself is an excluded directory name
        if path_item.is_dir() and path_item.name in EXCLUDE_DIRS_SET:
            return True
        # Check if any parent directory part within the project is in EXCLUDE_DIRS_SET
        # This ensures subdirectories of excluded dirs are also skipped
        current_path_iter = path_item # Renamed to avoid conflict with outer scope 'current_path'
        while current_path_iter != project_root and current_path_iter.parent != current_path_iter: # Loop until project_root or filesystem root
            if current_path_iter.name in EXCLUDE_DIRS_SET:
                return True
            # Special check for top-level hidden dirs not explicitly in EXCLUDE_DIRS_SET
            if current_path_iter.is_dir() and current_path_iter.parent == project_root and current_path_iter.name.startswith(".") and current_path_iter.name not in {".git", ".vscode", ".idea"}: # Allow common dev hidden dirs
                if current_path_iter.name not in EXCLUDE_DIRS_SET: # If it's like ".pytest_cache" and already excluded, fine.
                    return True
            current_path_iter = current_path_iter.parent
    except ValueError:
        if path_item.name in EXCLUDE_DIRS_SET or path_item.name in EXCLUDE_FILES_SET:
            return True
        return False
    except Exception:
        return False

    return False


def generate_file_listing(outfile, current_path: pathlib.Path, project_root: pathlib.Path, indent_level=0, scan_depth=0):
    """
    Recursively generates a file listing for the output file.
    Respects a global scan_depth and a CUSTOM_DEPTH_MAP for per-folder overrides.
    """
    indent = "  " * indent_level
    prefix_dir = "📁 "
    prefix_file = "📄 "

    try:
        # Sort items, directories first, then files, all alphabetically
        items_in_dir = sorted(list(current_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    except (PermissionError, FileNotFoundError):
        outfile.write(f"{indent}{prefix_dir}{current_path.name}/  (Cannot Access)\n")
        return

    for item in items_in_dir:
        if should_exclude_path(item, project_root):
            continue

        if item.is_dir():
            outfile.write(f"{indent}{prefix_dir}{item.name}/\n")

            # --- MODIFIED LOGIC FOR CUSTOM AND GLOBAL DEPTH ---
            # Determine the effective scan depth for this subdirectory.
            relative_path_str = str(item.relative_to(project_root).as_posix())

            # By default, use the inherited scan_depth from the parent.
            effective_depth = scan_depth

            # Check if a custom rule applies to this specific directory.
            if relative_path_str in CUSTOM_DEPTH_MAP:
                # A custom rule overrides the inherited depth.
                effective_depth = CUSTOM_DEPTH_MAP[relative_path_str]

            # Recurse only if the effective depth allows.
            # -1 means infinite depth.
            # A positive number means we can still go deeper.
            if effective_depth == -1:
                # Pass -1 along for infinite recursion in this branch.
                generate_file_listing(outfile, item, project_root, indent_level + 1, -1)
            elif effective_depth > 0:
                # Decrement the depth for the next level down.
                generate_file_listing(outfile, item, project_root, indent_level + 1, effective_depth - 1)
            # If effective_depth is 0, we do not recurse.

        elif item.is_file():
            outfile.write(f"{indent}{prefix_file}{item.name}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Generates a report of the project's file structure.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    # NEW: Add an optional argument for the target directory
    parser.add_argument(
        "target_directory",
        nargs='?',
        default=None,
        help="The path to the project directory to scan. If not provided, auto-detects the project root."
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=0,
        help="Directory scan depth for collecting files. 0 for root dir only, -1 for infinite, N for N levels."
    )
    args = parser.parse_args()

    # CORRECTED: Use the argument if provided, otherwise auto-detect
    if args.target_directory:
        project_root = pathlib.Path(args.target_directory).resolve()
    else:
        project_root = get_project_root()

    if not project_root.exists() or not project_root.is_dir():
        print(f"Error: Determined project directory not found or invalid: {project_root}")
        sys.exit(1)
    
    # --- MODIFICATION START ---
    # Create a dynamic filename based on the scan depth to avoid overwriting reports.
    if args.depth == -1:
        depth_suffix = "all"
    else:
        depth_suffix = str(args.depth)

    # Deconstruct the original filename constant to insert the depth suffix.
    # e.g., "project_structure_report.txt" becomes "project_structure_report_depth_0.txt"
    base_name = pathlib.Path(OUTPUT_FILENAME).stem
    extension = pathlib.Path(OUTPUT_FILENAME).suffix
    dynamic_filename = f"{base_name}_depth_{depth_suffix}{extension}"
    # --- MODIFICATION END ---

    print(f"\n{Colors.YELLOW}--- Starting Project Structure Analysis ---{Colors.RESET}")
    print(f"1. Determined project root: {project_root}")

    # Define the dedicated output directory for reports
    report_output_dir = project_root / "output" / REPORT_SUBDIR
    
    # Ensure the output directory exists, creating it if necessary
    try:
        report_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"{Colors.RED}Error: Could not create output directory '{report_output_dir}': {e}{Colors.RESET}")
        sys.exit(1)
        
    # MODIFIED: Use the new dynamic filename instead of the static constant
    output_file_path = report_output_dir / dynamic_filename

    print(f"2. Output will be saved to: {output_file_path}")

    # --- MODIFIED FOR DEPTH CONTROL ---
    all_items_to_process = []
    if args.depth == -1:
        print("Scanning with infinite depth... (collecting file list, this may take a moment)")
        # Convert the rglob generator to a list to allow for len() check
        all_items_to_process = list(project_root.rglob('*'))
    else:
        print(f"Scanning to a maximum depth of {args.depth} level(s)... (collecting file list, this may take a moment)")
        # Use a queue for a breadth-first search, which is ideal for depth-limiting
        queue = [(project_root, 0)]
        visited_dirs = {project_root}
        
        while queue:
            current_dir, current_depth = queue.pop(0)
            
            try:
                for item in current_dir.iterdir():
                    all_items_to_process.append(item)
                    
                    # If it's a directory and we can go deeper, add it to the queue
                    if item.is_dir() and item not in visited_dirs and current_depth < args.depth:
                        visited_dirs.add(item)
                        queue.append((item, current_depth + 1))
            except (PermissionError, FileNotFoundError):
                # Silently skip directories we cannot access
                continue
    # --- END MODIFICATION ---

    # Warn the user if the number of items to process is large
    if len(all_items_to_process) >= FILE_COUNT_WARNING_THRESHOLD:
        prompt = (
            f"\nWarning: Found {len(all_items_to_process)} files and directories to inspect. "
            "This operation could take some time.\n"
            "Do you want to proceed? (Y/N): "
        )
        try:
            response = input(prompt)
            if response.strip().lower() != 'y':
                print("Operation cancelled by user.")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.")
            sys.exit(0)
        print("-" * 20) # Visual separator after prompt

    try:
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            outfile.write(f"Project Structure & File Report\n")
            outfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            outfile.write(f"Project Root: {project_root.resolve()}\n")
            outfile.write(f"Report Location: {output_file_path.resolve()}\n")
            outfile.write(f"Excluded Directory Names: {', '.join(sorted(list(EXCLUDE_DIRS_SET)))}\n")
            outfile.write(f"Excluded File Names: {', '.join(sorted(list(EXCLUDE_FILES_SET)))}\n")
            outfile.write(f"Excluded File Extensions: {', '.join(sorted(list(EXCLUDE_EXTENSIONS_SET)))}\n")
            outfile.write(f"File Collection Scan Depth: {'Infinite (recursive)' if args.depth == -1 else args.depth}\n")
            outfile.write("="*70 + "\n\n")

            outfile.write("--- Hierarchical Directory Structure ---\n")
            outfile.write(f"{project_root.name}/\n")
            generate_file_listing(outfile, project_root, project_root, indent_level=0, scan_depth=args.depth)

            outfile.write("\n\n" + "="*70 + "\n")
            outfile.write("Report generation complete.\n")

        print(f"\n{Colors.YELLOW}--- Analysis Complete ---{Colors.RESET}")
        print(f"{Colors.CYAN} - Report saved to: {output_file_path.relative_to(project_root)}{Colors.RESET}")
        print(f"{Colors.GREEN}SUCCESS: Project structure report generated successfully.{Colors.RESET}\n")

    except IOError as e:
        print(f"{Colors.RED}Error: Could not write to output file: {output_file_path}\nDetails: {e}{Colors.RESET}")
        sys.exit(1)
    except Exception as e_main:
        print(f"An unexpected error occurred: {e_main}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of scripts/list_project_files.py ===
