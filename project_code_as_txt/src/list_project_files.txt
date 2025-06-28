# -*- coding: utf-8 -*-
# Filename: utilities/list_project_files.py

"""
A utility script to scan a project directory, generate a report of its structure,
and list key files. This script is designed to be placed in a `utilities/`
subdirectory of the project it is intended to analyze.

Features:
- Automatically determines the project root, assuming the script is located in
  `project_root/utilities/`.
- Allows exclusion of common directories (e.g., .venv, __pycache__, .git),
  specific file names (e.g., .DS_Store), and file extensions (e.g., .pyc, .log).
- Generates a hierarchical, tree-like representation of the project's directory
  structure. The depth of file listing within this tree is configurable.
- Produces summaries of all Python (.py) scripts found within the project
  (excluding specified directories/files), including their line counts and a total.
- Produces a summary of other predefined key files located at the project root
  (e.g., config.py, requirements.txt, README.md).
- Writes the generated report to a text file, by default named
  `project_structure_report.txt`, in the same directory as this script.

Configuration:
The script's behavior can be customized by modifying the following constants
at the top of the file:
- `EXCLUDE_DIRS_SET`: A set of directory names to completely exclude from the scan.
- `EXCLUDE_FILES_SET`: A set of specific file names to exclude.
- `EXCLUDE_EXTENSIONS_SET`: A set of file extensions to exclude.
- `OUTPUT_FILENAME`: The name of the file where the report will be saved.
- `MAX_RECURSION_DEPTH_DISPLAY`: Controls how many levels deep individual files
  are listed in the hierarchical structure view. Directories are always listed.

Main Functions:
- `get_project_root()`: Determines the project's root directory.
- `should_exclude_path(path_item, project_root)`: Checks if a given path should be
  excluded based on the configuration.
- `generate_file_listing(outfile, current_path, project_root, indent_level)`:
  Recursively generates the hierarchical file and directory listing.
- `main()`: Orchestrates the scanning process, data collection, and report generation.

Usage:
1. Place this script in a `utilities/` directory within your project.
   Example: `my_project/utilities/list_project_files.py`
2. Ensure the configuration constants (exclusion sets, output filename, etc.) are
   set as desired.
3. Run the script from the command line:
   `python utilities/list_project_files.py`
   (Or `python path/to/your/project/utilities/list_project_files.py` if run from
   elsewhere, though running from within the project or its `utilities` dir is typical).
4. The report will be generated in the `utilities/` directory (e.g.,
   `my_project/utilities/project_structure_report.txt`).

The script aims to provide a clear overview of a project's layout, which can be
useful for documentation, onboarding new team members, or preparing context for
sharing with others (e.g., LLMs).
"""

# === Start of utilities/list_project_files.py ===

import pathlib
import sys
import os # Keep os for os.stat if needed, though pathlib usually suffices
from datetime import datetime
import traceback # For detailed error logging if needed

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
MAX_RECURSION_DEPTH_DISPLAY = 5 # How deep to show full file listing in structure view
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


def generate_file_listing(outfile, current_path: pathlib.Path, project_root: pathlib.Path, indent_level=0):
    """
    Recursively generates a file listing for the output file.
    Respects MAX_RECURSION_DEPTH_DISPLAY for how deep to list individual files.
    Always lists directories.
    """
    indent = "  " * indent_level
    prefix_dir = "📁 "
    prefix_file = "📄 "

    try:
        items_in_dir = sorted(list(current_path.iterdir()), key=lambda x: (x.is_file(), x.name.lower()))
    except PermissionError:
        outfile.write(f"{indent}{prefix_dir}{current_path.name}/  (Permission Denied)\n")
        return
    except FileNotFoundError:
        outfile.write(f"{indent}{prefix_dir}{current_path.name}/  (Not Found During Scan)\n")
        return

    for item in items_in_dir:
        if should_exclude_path(item, project_root):
            continue

        if item.is_dir():
            outfile.write(f"{indent}{prefix_dir}{item.name}/\n")
            if indent_level < MAX_RECURSION_DEPTH_DISPLAY -1:
                generate_file_listing(outfile, item, project_root, indent_level + 1)
            elif indent_level == MAX_RECURSION_DEPTH_DISPLAY -1:
                 outfile.write(f"{indent}  (... files not listed beyond depth {MAX_RECURSION_DEPTH_DISPLAY} ...)\n")
        elif item.is_file():
            if indent_level < MAX_RECURSION_DEPTH_DISPLAY:
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
    project_root = get_project_root()
    script_dir = pathlib.Path(__file__).resolve().parent
    output_file_path = script_dir / OUTPUT_FILENAME

    if not project_root.exists() or not project_root.is_dir():
        print(f"Error: Determined project directory not found or invalid: {project_root}")
        sys.exit(1)

    print(f"Determined project root: {project_root}")
    print(f"Output will be saved to: {output_file_path}")

    # Store tuples of (relative_path_str, line_count) for .py files
    py_scripts_with_lines = []
    other_key_files_summary = []

    for item in project_root.rglob('*'):
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
            outfile.write(f"Max Display Depth for Files in Structure: {MAX_RECURSION_DEPTH_DISPLAY}\n")
            outfile.write("="*70 + "\n\n")

            outfile.write("--- Hierarchical Directory Structure ---\n")
            outfile.write(f"{project_root.name}/\n")
            generate_file_listing(outfile, project_root, project_root, indent_level=0)

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

# === End of utilities/list_project_files.py ===