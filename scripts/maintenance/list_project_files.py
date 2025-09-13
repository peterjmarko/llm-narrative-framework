#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: scripts/maintenance/list_project_files.py

"""
Generates a detailed text report of the project's file and directory structure.

This utility creates a snapshot of the project's layout, providing a
hierarchical tree view of all directories and files. The report is useful for
documentation, project handovers, and gaining a quick overview of the codebase.

Key Features:
-   **Configurable Scan Depth**: Control the recursion depth of the file scan
    via the `--depth` command-line argument.
-   **Git-Aware Filtering**: Use the `--git` flag to limit the report to only
    files and directories tracked by the Git repository.
-   **Intelligent Exclusions**: Automatically excludes configured directories
    (like `.venv`, `.git`) and file types using exact names and wildcard
    patterns, producing a clean and relevant report.
-   **Dynamic Output Naming**: The output filename includes the scan depth and a
    `_git` suffix when the Git filter is active.
-   **Automatic Backups**: Automatically backs up any existing report to
    `output/backup/` with a timestamp before generating a new one.

Usage:
    # Scan the project root directory only (default depth=0)
    pdm run list-files

    # Scan the entire project recursively
    pdm run list-files -- --depth -1

    # Scan only files tracked by Git (recursively)
    pdm run list-files -- --git --depth -1
"""

# === Start of maintenance/list_project_files.py ===

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
import fnmatch
from tqdm import tqdm
import time
import subprocess

# --- Configuration ---

# --- Configuration ---
# Directories to completely exclude from the scan (exact names)
EXCLUDE_DIRS_SET = {
    # General Python/dev environment folders
    ".venv", "venv", "__pycache__", ".git", ".vscode", ".idea",
    ".pytest_cache", "node_modules",
    # Build and distribution artifacts
    "build", "dist", "htmlcov",
    # Other common folders to exclude
    "instance"
}
# Directory name patterns to exclude (uses glob-style matching)
EXCLUDE_DIR_PATTERNS = {
    "*.egg-info",
    "*archive*",
    "*backup*",
    "temp_*",
}
# Specific files to always exclude by name
EXCLUDE_FILES_SET = {".DS_Store", "Thumbs.db"}

# File name patterns to exclude (uses glob-style matching)
EXCLUDE_FILE_PATTERNS = {"~$*.*"}

# File extensions to exclude (case-insensitive)
EXCLUDE_EXTENSIONS_SET = {".bak", ".log", ".pyc", ".pyd", ".pyo", ".swp", ".tmp"}

OUTPUT_FILENAME = "project_structure_report.txt"
REPORT_SUBDIR = "project_reports" # Subdirectory within 'output' for these reports
FILE_COUNT_ALIGN_COLUMN = 90 # Column where the file count will END (right-justified)
# --- End Configuration ---

def get_git_tracked_paths(project_root: pathlib.Path):
    """
    Retrieves a set of all file and directory paths tracked by Git.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=project_root,
            capture_output=True,
            text=True,
            check=True
        )
    except FileNotFoundError:
        print(f"{Colors.RED}Error: 'git' command not found. Is Git installed and in your PATH?{Colors.RESET}")
        sys.exit(1)
    except subprocess.CalledProcessError:
        print(f"{Colors.RED}Error: Project root is not a Git repository, or another 'git' error occurred.{Colors.RESET}")
        sys.exit(1)

    tracked_files = result.stdout.strip().split('\n')
    git_tracked_paths = set()
    for file_path_str in filter(None, tracked_files): # Filter out empty strings
        p = pathlib.Path(file_path_str)
        git_tracked_paths.add(p)
    return git_tracked_paths

def get_project_root():
    """Determines the project root, assuming this script is in utilities/"""
    try:
        # If __file__ is defined (standard case)
        script_path = pathlib.Path(__file__).resolve()
        # scripts/maintenance -> scripts -> project_root
        project_root = script_path.parent.parent.parent
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
    Checks if a path should be excluded based on configured exclusion lists.
    Supports exact name, glob pattern, and file extension matching.
    """
    item_name = path_item.name

    if path_item.is_dir():
        # Exclude by exact directory name
        if item_name in EXCLUDE_DIRS_SET:
            return True
        # Exclude by directory name pattern
        for pattern in EXCLUDE_DIR_PATTERNS:
            if fnmatch.fnmatch(item_name, pattern):
                return True
    elif path_item.is_file():
        # Exclude by exact file name
        if item_name in EXCLUDE_FILES_SET:
            return True
        # Exclude by file name pattern
        for pattern in EXCLUDE_FILE_PATTERNS:
            if fnmatch.fnmatch(item_name, pattern):
                return True
        # Exclude by file extension
        if path_item.suffix.lower() in EXCLUDE_EXTENSIONS_SET:
            return True

    return False


def count_reportable_items(current_path: pathlib.Path, project_root: pathlib.Path, args, feedback_counter, dir_file_counts, scan_depth=0, git_tracked_paths=None):
    """
    Recursively counts all items and simultaneously calculates the number of
    reportable files within each directory, respecting the scan depth.
    Returns the aggregate counts and populates the dir_file_counts map.
    """
    counts = {'total': 0, 'excluded_by_rule': 0, 'final_included': 0}
    local_file_count = 0
    try:
        items_in_dir = sorted(list(current_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    except (PermissionError, FileNotFoundError):
        return counts # Cannot access contents, so content count is 0.

    for item in items_in_dir:
        feedback_counter['discovered'] += 1
        current_time = time.time()
        if current_time - feedback_counter['last_update'] >= 0.1:
            print(f"  -> Scanned {feedback_counter['discovered']:,} items from disk...", end='\r')
            feedback_counter['last_update'] = current_time

        counts['total'] += 1
        is_excluded_by_rule = should_exclude_path(item, project_root)
        is_excluded_by_git = (git_tracked_paths is not None and item.relative_to(project_root) not in git_tracked_paths)

        if is_excluded_by_rule:
            counts['excluded_by_rule'] += 1
        elif is_excluded_by_git:
            pass # Not included in final count, but not a rule-based exclusion.
        else:
            counts['final_included'] += 1

        if item.is_file() and not is_excluded_by_rule and not is_excluded_by_git:
            local_file_count += 1

        if item.is_dir() and not is_excluded_by_rule:
            if scan_depth == -1 or scan_depth > 0:
                sub_counts = count_reportable_items(
                    item, project_root, args, feedback_counter, dir_file_counts,
                    scan_depth - 1 if scan_depth > 0 else -1,
                    git_tracked_paths
                )
                counts = {k: v + sub_counts.get(k, 0) for k, v in counts.items()}
                # Add the file count from the subdirectory to the current directory's count.
                local_file_count += dir_file_counts.get(item, 0)

    dir_file_counts[current_path] = local_file_count
    return counts


def format_count_str(count):
    """Formats a number into a right-aligned file count string."""
    num_width = 8  # Fixed width for the number part to ensure alignment
    num_str = f"{count:,}".rjust(num_width)
    word_str = " file" if count == 1 else " files"
    return f"{num_str}{word_str}"


def build_git_tree(git_files):
    """Builds a hierarchical dictionary tree from a flat list of Git files."""
    tree = {}
    for file_path in git_files:
        parts = file_path.parts
        current_level = tree
        for part in parts[:-1]:  # Iterate through directories
            current_level = current_level.setdefault(part, {})
        current_level[parts[-1]] = None  # Mark file with None
    return tree


def count_from_git_tree(tree, dir_file_counts, current_path, scan_depth):
    """Recursively counts items and files from the in-memory Git tree."""
    counts = {'final_included': 0}
    local_file_count = 0
    # Sort to process directories before files, then alphabetically
    sorted_keys = sorted(tree.keys(), key=lambda k: (tree[k] is None, k.lower()))

    for name in sorted_keys:
        counts['final_included'] += 1
        is_dir = isinstance(tree[name], dict)
        
        if is_dir:
            sub_path = current_path / name
            if scan_depth == -1 or scan_depth > 0:
                sub_counts = count_from_git_tree(
                    tree[name], dir_file_counts, sub_path,
                    scan_depth - 1 if scan_depth > 0 else -1
                )
                counts['final_included'] += sub_counts['final_included']
                local_file_count += dir_file_counts[sub_path]
        else:
            local_file_count += 1
            
    dir_file_counts[current_path] = local_file_count
    return counts


def generate_from_git_tree(outfile, tree, pbar, dir_file_counts, current_path, indent_level, scan_depth):
    """Recursively generates the report from the in-memory Git tree."""
    indent = "  " * indent_level
    prefix_dir, prefix_file = "📁 ", "📄 "
    # Sort to process directories before files, then alphabetically
    sorted_keys = sorted(tree.keys(), key=lambda k: (tree[k] is None, k.lower()))
    
    for name in sorted_keys:
        pbar.update(1)
        is_dir = isinstance(tree[name], dict)

        if is_dir:
            base_line = f"{indent}{prefix_dir}{name}/"
            count = dir_file_counts.get(current_path / name, 0)
            count_str = format_count_str(count)
            padding_needed = FILE_COUNT_ALIGN_COLUMN - len(base_line) - len(count_str)
            padding = " " * (padding_needed if padding_needed > 1 else 2)
            outfile.write(f"{base_line}{padding}{count_str}\n")
            
            if scan_depth == -1 or scan_depth > 0:
                generate_from_git_tree(
                    outfile, tree[name], pbar, dir_file_counts,
                    current_path / name, indent_level + 1,
                    scan_depth - 1 if scan_depth > 0 else -1
                )
        else:
            outfile.write(f"{indent}{prefix_file}{name}\n")


def generate_file_listing(outfile, current_path: pathlib.Path, project_root: pathlib.Path, args, pbar, dir_file_counts, indent_level=0, scan_depth=0, git_tracked_paths=None):
    """
    Recursively generates a file listing for the contents of a directory.
    """
    indent = "  " * indent_level
    prefix_dir = "📁 "
    prefix_file = "📄 "

    try:
        items_in_dir = sorted(list(current_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    except (PermissionError, FileNotFoundError):
        # The parent directory was already written, we just cannot list its contents.
        # This could be noted by modifying the parent's line, but for simplicity, we just stop.
        return

    for item in items_in_dir:
        is_excluded_by_rule = should_exclude_path(item, project_root)
        is_excluded_by_git = (git_tracked_paths is not None and item.relative_to(project_root) not in git_tracked_paths)

        if is_excluded_by_rule or is_excluded_by_git:
            continue

        pbar.update(1)

        if item.is_dir():
            base_line = f"{indent}{prefix_dir}{item.name}/"
            count = dir_file_counts.get(item, 0)
            count_str = format_count_str(count)

            padding_needed = FILE_COUNT_ALIGN_COLUMN - len(base_line) - len(count_str)
            padding = " " * (padding_needed if padding_needed > 1 else 2)
            final_line = f"{base_line}{padding}{count_str}"

            try:
                # Check accessibility before recursing.
                _ = next(item.iterdir(), None)
                outfile.write(final_line + "\n")
            except (PermissionError, FileNotFoundError):
                access_error_str = "(Cannot Access)"
                padding_needed = FILE_COUNT_ALIGN_COLUMN - len(base_line) - len(access_error_str)
                padding = " " * (padding_needed if padding_needed > 1 else 2)
                outfile.write(f"{base_line}{padding}{access_error_str}\n")
                continue

            if scan_depth == -1 or scan_depth > 0:
                generate_file_listing(
                    outfile, item, project_root, args, pbar, dir_file_counts,
                    indent_level + 1,
                    scan_depth - 1 if scan_depth > 0 else -1,
                    git_tracked_paths
                )
        elif item.is_file():
            outfile.write(f"{indent}{prefix_file}{item.name}\n")

def main():
    try:
        parser = argparse.ArgumentParser(
            description="Generates a report of the project's file structure.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
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
        parser.add_argument(
            "--git",
            action="store_true",
            help="Only include files and directories tracked by Git."
        )
        args = parser.parse_args()

        if args.target_directory:
            project_root = pathlib.Path(args.target_directory).resolve()
        else:
            project_root = get_project_root()

        if not project_root.exists() or not project_root.is_dir():
            print(f"Error: Determined project directory not found or invalid: {project_root}")
            sys.exit(1)

        if args.depth == -1:
            depth_suffix = "all"
        else:
            depth_suffix = str(args.depth)

        base_name = pathlib.Path(OUTPUT_FILENAME).stem
        extension = pathlib.Path(OUTPUT_FILENAME).suffix
        git_suffix = "_git" if args.git else ""
        dynamic_filename = f"{base_name}{git_suffix}_depth_{depth_suffix}{extension}"

        print(f"\n{Colors.YELLOW}--- Starting Project Structure Analysis ---{Colors.RESET}")
        print(f"1. Determined project root: {project_root}")

        report_output_dir = project_root / "output" / REPORT_SUBDIR
        try:
            report_output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"{Colors.RED}Error: Could not create output directory '{report_output_dir}': {e}{Colors.RESET}")
            sys.exit(1)
            
        output_file_path = report_output_dir / dynamic_filename
        print(f"2. Output will be saved to: {output_file_path.relative_to(project_root)}")

        dir_file_counts = {}
        total_on_disk, excluded_by_rule, excluded_by_git, final_item_count = 0, 0, 0, 0

        if args.git:
            # --- Efficient Git-based Workflow ---
            print("3. Using efficient Git-based discovery.")
            git_files_only = get_git_tracked_paths(project_root)
            git_tree = build_git_tree(git_files_only)

            # The +1 accounts for the root directory itself.
            content_counts = count_from_git_tree(git_tree, dir_file_counts, project_root, args.depth)
            final_item_count = content_counts['final_included'] + 1
            
            print(f"4. Discovery complete: Found {final_item_count:,} Git-tracked items to report.")

        else:
            # --- Standard Filesystem Workflow ---
            if args.depth >= 6:
                print("3. Discovering files and calculating report size... (expecting to scan about 1.5 million items)")
            else:
                print("3. Discovering files and calculating report size...")
            
            feedback_counter = {'discovered': 0, 'last_update': time.time()}

            # Get counts for items *inside* the project root.
            content_counts = count_reportable_items(
                project_root, project_root, args, feedback_counter, dir_file_counts,
                scan_depth=args.depth, git_tracked_paths=None
            )
            
            print(" " * 80, end='\r'); print()
            
            total_on_disk = content_counts['total'] + 1
            excluded_by_rule = content_counts['excluded_by_rule']
            final_item_count = content_counts['final_included'] + 1

            print(f"4. Discovery complete:")
            print(f"   - Found {total_on_disk:,} total items on disk.")
            print(f"   - Excluded {excluded_by_rule:,} items based on script rules.")
            print(f"   - Final report will include {final_item_count:,} items.")

        # Backup existing report if it exists
        if output_file_path.exists():
            try:
                # Define and create the backup directory
                backup_dir = project_root / "output" / "backup"
                backup_dir.mkdir(parents=True, exist_ok=True)

                # Create a timestamped backup filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_filename = f"{output_file_path.stem}_{timestamp}{output_file_path.suffix}"
                backup_path = backup_dir / backup_filename

                # Move the old report to the backup location
                output_file_path.rename(backup_path)
                print(f"   -> Backed up existing report to: {backup_path.relative_to(project_root)}")
            except OSError as e:
                print(f"{Colors.YELLOW}Warning: Could not back up existing report: {e}{Colors.RESET}")

        print("5. Assembling report...")
        pbar = tqdm(total=final_item_count,
                    desc="Assembling Report",
                    bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
                    ncols=60)
        try:
            with open(output_file_path, 'w', encoding='utf-8') as outfile:
                outfile.write(f"Project Structure & File Report\n")
                outfile.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if args.git:
                    outfile.write("Filter: Git-tracked files only\n")
                outfile.write(f"Project Root: {project_root.resolve()}\n")
                outfile.write(f"Report Location: {output_file_path.resolve()}\n")
                outfile.write(f"Excluded Directory Names: {', '.join(sorted(list(EXCLUDE_DIRS_SET)))}\n")
                outfile.write(f"Excluded Directory Patterns: {', '.join(sorted(list(EXCLUDE_DIR_PATTERNS)))}\n")
                outfile.write(f"Excluded File Names: {', '.join(sorted(list(EXCLUDE_FILES_SET)))}\n")
                outfile.write(f"Excluded File Patterns: {', '.join(sorted(list(EXCLUDE_FILE_PATTERNS)))}\n")
                outfile.write(f"Excluded File Extensions: {', '.join(sorted(list(EXCLUDE_EXTENSIONS_SET)))}\n")
                outfile.write(f"File Collection Scan Depth: {'Infinite (recursive)' if args.depth == -1 else args.depth}\n")
                outfile.write("\n--- About File Counts ---\n")
                outfile.write("The count next to each directory shows the number of reportable files within it.\n")
                outfile.write("This count respects both the --depth and --git flags.\n")
                outfile.write("\n--- Discovery Statistics ---\n")
                outfile.write(f"Total items found on disk: {total_on_disk:,}\n")
                outfile.write(f"Excluded by script rules: {excluded_by_rule:,}\n")
                if args.git:
                    outfile.write(f"Excluded (not tracked by Git): {excluded_by_git:,}\n")
                outfile.write(f"Final items in report: {final_item_count:,}\n")
                outfile.write("="*70 + "\n\n")
                # Write the root directory line with its aligned file count
                outfile.write("--- Hierarchical Directory Structure ---\n")
                root_count = dir_file_counts.get(project_root, 0)
                root_count_str = format_count_str(root_count)
                root_line = f"{project_root.name}/"
                
                padding_needed = FILE_COUNT_ALIGN_COLUMN - len(root_line) - len(root_count_str)
                padding = " " * (padding_needed if padding_needed > 1 else 2)
                outfile.write(f"{root_line}{padding}{root_count_str}\n")
                pbar.update(1) # Manually account for the root directory.

                if args.git:
                    # Use the in-memory tree for generation
                    generate_from_git_tree(
                        outfile, git_tree, pbar, dir_file_counts,
                        project_root, indent_level=1, scan_depth=args.depth
                    )
                else:
                    # Use the standard filesystem traversal for generation
                    generate_file_listing(
                        outfile, project_root, project_root, args, pbar, dir_file_counts,
                        indent_level=1, scan_depth=args.depth, git_tracked_paths=None
                    )
                outfile.write("\n\n" + "="*70 + "\n")
                outfile.write("Report generation complete.\n")

        except IOError as e:
            print(f"{Colors.RED}Error: Could not write to output file: {output_file_path}\nDetails: {e}{Colors.RESET}")
            sys.exit(1)
        except Exception as e_main:
            print(f"An unexpected error occurred: {e_main}")
            traceback.print_exc()
            sys.exit(1)
        finally:
            if pbar:
                pbar.close()

        print(f"\n{Colors.YELLOW}--- Analysis Complete ---{Colors.RESET}")
        print(f"{Colors.CYAN} - Report saved to: {output_file_path.relative_to(project_root)}{Colors.RESET}")
        print(f"{Colors.GREEN}SUCCESS: Project structure report generated successfully.{Colors.RESET}\n")

    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Operation cancelled by user.{Colors.RESET}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of scripts/maintenance/list_project_files.py ===
