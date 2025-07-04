#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: src/list_project_files.py

"""
Project File Lister (list_project_files.py)

Purpose:
This script scans a directory structure and generates a single text file,
`all_project_files.txt`, which contains the concatenated content of all specified
source code files. It's designed to create a comprehensive snapshot of a
project for analysis or archival.

Workflow:
1.  Accepts a root directory to scan.
2.  The scan depth is controlled by the --depth argument.
3.  Finds all files with specified extensions (e.g., .py, .md, .txt).
4.  Excludes files from specified directories (e.g., .venv, __pycache__).
5.  Concatenates the content of all found files into one output file.
6.  Each file's content is preceded by a header indicating its original path.

Command-Line Usage:
    # Scan the current project directory '.' (depth 0)
    python src/list_project_files.py .

    # Scan the project directory and its immediate subdirectories
    python src/list_project_files.py . --depth 1

    # Scan the entire project directory tree recursively
    python src/list_project_files.py . --depth -1
"""

# === Start of utilities/list_project_files.py ===

import pathlib
import sys
import os # Keep os for os.stat if needed, though pathlib usually suffices
from datetime import datetime
import traceback # For detailed error logging if needed
import argparse

# --- Configuration ---
# Directories to completely exclude from the scan (names, not paths)
EXCLUDE_DIRS_SET = {
    ".venv", "venv", "__pycache__", ".git", ".vscode", ".idea",
    ".pytest_cache", "node_modules", "build", "dist", "docs",
    "archive", "instance", "*.egg-info", # Common build/dist/docs/archive folders
    "weather", "project_code_as_txt/weather" # Specific to this project (weather scripts and data)
}
# Specific files to always exclude by name
EXCLUDE_FILES_SET = {".DS_Store", "Thumbs.db", "*.pyc", "*.pyo", "*.pyd"}
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
            if current_path_iter.parent == project_root and current_path_iter.name.startswith(".") and current_path_iter.name not in {".git", ".vscode", ".idea"}: # Allow common dev hidden dirs
                if current_path_iter.name not in EXCLUDE_DIRS_SET: # If it's like ".pytest_cache" and already excluded, fine.
                    pass
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
    Respects scan_depth for how deep to list contents.
    """
    indent = "  " * indent_level
    prefix_dir = "📁 "
    prefix_file = "📄 "

    try:
        items_in_dir = sorted(list(current_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    except (PermissionError, FileNotFoundError):
        # This part remains the same, handles directories that can't be read.
        outfile.write(f"{indent}{prefix_dir}{current_path.name}/  (Cannot Access)\n")
        return

    for item in items_in_dir:
        if should_exclude_path(item, project_root):
            continue

        if item.is_dir():
            outfile.write(f"{indent}{prefix_dir}{item.name}/\n")
            # CORRECTED LOGIC: Recurse only if depth is infinite (-1) or not yet reached.
            if scan_depth == -1 or indent_level < scan_depth:
                generate_file_listing(outfile, item, project_root, indent_level + 1, scan_depth)
        elif item.is_file():
            outfile.write(f"{indent}{prefix_file}{item.name}\n")

def count_lines_in_file(file_path: pathlib.Path) -> int:
    """Counts non-empty lines in a text file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = [line for line in f if line.strip()] # Count lines with content
            return len(lines)
    except Exception:
        return 0 # Or some indicator of error, like -1

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

    # Define the dedicated output directory for reports
    report_output_dir = project_root / "output" / REPORT_SUBDIR
    
    # Ensure the output directory exists, creating it if necessary
    try:
        report_output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Error: Could not create output directory '{report_output_dir}': {e}")
        sys.exit(1)
        
    # MODIFIED: Use the new dynamic filename instead of the static constant
    output_file_path = report_output_dir / dynamic_filename

    if not project_root.exists() or not project_root.is_dir():
        print(f"Error: Determined project directory not found or invalid: {project_root}")
        sys.exit(1)

    print(f"Determined project root: {project_root}")
    print(f"Output will be saved to: {output_file_path}")

    # Store tuples of (relative_path_str, line_count) for .py files
    py_scripts_with_lines = []
    other_key_files_summary = []

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
            "Do you want to proceed? (y/n): "
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

    for item in all_items_to_process:
        if not should_exclude_path(item, project_root):
            if item.is_file():
                if item.suffix.lower() == '.py':
                    line_count = count_lines_in_file(item)
                    # Store as tuple: (relative path string, line count)
                    py_scripts_with_lines.append((str(item.relative_to(project_root)), line_count))
                elif item.parent == project_root and item.name in (
                    "config.py", "keys.py", ".env", "requirements.txt", "README.md",
                    "noon_price_predictor.py", "backtest_controller.py",
                    "daily_model_history_generation.py", # Deprecated name, kept for template matching
                    "market_dashboard.py", # Renamed from realtime_market_analysis_dashboard.py
                    "daily_performance_analyzer.py" # Renamed from daily_market_vs_model_analysis.py
                ):
                    other_key_files_summary.append(item.name)

    # Sort Python scripts by path string
    py_scripts_with_lines.sort(key=lambda x: x[0])
    other_key_files_summary.sort()
    total_py_lines = sum(count for _, count in py_scripts_with_lines)


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
            outfile.write("--- Summary: Python Scripts (.py) ---\n")
            if py_scripts_with_lines:
                max_path_len = 0
                if py_scripts_with_lines: # Check if list is not empty
                    # Calculate max_path_len based on existing script paths
                    max_path_len = max(len(f"./{rel_path}") for rel_path, _ in py_scripts_with_lines)

                for rel_path_str, count in py_scripts_with_lines:
                    # Format path string and count string
                    path_str_formatted = f"./{rel_path_str}".ljust(max_path_len + 4) # +4 for "  (L: "
                    count_str_formatted = f" (Lines: {count})"
                    outfile.write(f"{path_str_formatted}{count_str_formatted}\n")
                outfile.write("-" * (max_path_len + 4 + 20) + "\n") # Adjust separator length
                total_str_formatted = "Total Lines in .py files:".ljust(max_path_len + 4)
                outfile.write(f"{total_str_formatted} {total_py_lines}\n")
            else:
                outfile.write("(No .py files found meeting criteria)\n")

            outfile.write("\n\n" + "="*70 + "\n")
            outfile.write("--- Summary: Key Files at Project Root ---\n")
            if other_key_files_summary:
                for f_name in other_key_files_summary:
                    outfile.write(f"./{f_name}\n")
            else:
                outfile.write("(No predefined key files found at project root)\n")

            outfile.write("\n\n" + "="*70 + "\n")
            outfile.write("Report generation complete.\n")

        print(f"Successfully wrote project structure report to: {output_file_path}")

    except IOError as e:
        print(f"Error: Could not write to output file: {output_file_path}\nDetails: {e}")
        sys.exit(1)
    except Exception as e_main:
        print(f"An unexpected error occurred: {e_main}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/list_project_files.py ===