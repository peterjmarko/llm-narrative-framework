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
# Filename: scripts/maintenance/generate_scope_report.py

"""
This script generates a high-level quantitative report of the project's scope,
providing a summary of different asset types (documents, scripts, diagrams, data)
and their respective "extent" (e.g., pages, lines of code, complexity).

The report is saved in Markdown format to the project's root directory.
"""

import os
import pathlib
from datetime import datetime

# --- Configuration ---
# The root of the project, determined by going up two levels from this script's location.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
REPORT_OUTPUT_DIR = PROJECT_ROOT / "output" / "project_reports"
REPORT_FILENAME = REPORT_OUTPUT_DIR / "project_scope_report.md"

# Directories to completely exclude from the scan.
EXCLUDE_DIRS = {
    ".git", ".pdm-build", ".pytest_cache", ".venv", "__pycache__", "archive",
    "build", "config", "data/backup", "dist", "htmlcov", "images",
    "linter_backups", "llm_personality_matching.egg-info",
    "main_archive", "node_modules", "output", "venv"
}

# File extensions to exclude.
EXCLUDE_EXTS = {".pyc", ".pyo", ".pyd", ".log", ".tmp", ".swp", ".lock", ".coverage", ".pdf", ".bak"}

# ANSI color codes for better terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    CYAN = '\033[96m'
    RESET = '\033[0m'

# --- Helper Functions ---

def count_words(path: pathlib.Path) -> int:
    """Counts words in a text file."""
    try:
        return len(path.read_text(encoding='utf-8').split())
    except Exception:
        return 0

def count_non_empty_lines(path: pathlib.Path) -> int:
    """Counts non-empty lines in a text file."""
    try:
        with path.open(encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except Exception:
        return 0

def get_file_size_kb(path: pathlib.Path) -> float:
    """Gets file size in kilobytes."""
    try:
        return round(path.stat().st_size / 1024, 1)
    except Exception:
        return 0.0

def should_exclude(path: pathlib.Path) -> bool:
    """Checks if a file or directory should be excluded from the report."""
    # Exclude the documentation template to avoid double-counting
    if path.name == 'DOCUMENTATION.template.md':
        return True
        
    if path.suffix.lower() in EXCLUDE_EXTS:
        return True

    # Exclude hidden files at the root, except for specific config files
    if path.parent == PROJECT_ROOT and path.name.startswith('.') and path.is_file():
        allowed_hidden_files = {'.gitignore', '.pre-commit-config.yaml', '.coveragerc'}
        if path.name not in allowed_hidden_files:
            return True
            
    return False

def should_exclude_dir(root_path: pathlib.Path, dir_name: str) -> bool:
    """Checks if a directory should be excluded based on its path."""
    # Exclude any top-level directory starting with 'temp'
    if root_path == PROJECT_ROOT and dir_name.startswith("temp"):
        return True

    full_dir_path = root_path / dir_name
    try:
        rel_path = full_dir_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return False

    # Handle wildcard for temp directories in data/
    if rel_path.startswith("data/temp"):
        return True

    for excluded in EXCLUDE_DIRS:
        if dir_name == excluded:
            return True
        if rel_path == excluded:
            return True
        if rel_path.startswith(excluded + '/'):
            return True
    
    return False

def generate_table(headers: list, rows: list, totals: list) -> str:
    """Generates a Markdown table from headers, rows, and totals."""
    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "|:" + ":|:".join(["---"] * len(headers)) + ":|"
    
    row_lines = []
    for row in rows:
        row_lines.append("| " + " | ".join(map(str, row)) + " |")

    total_line = "| **" + "** | **".join(map(str, totals)) + "** |"
    
    return "\n".join([header_line, separator_line] + row_lines + [total_line])


def main(quiet=False):
    """Main function to generate the project scope report."""
    if not quiet:
        print(f"{Colors.YELLOW}\n--- Starting Project Scope Analysis ---{Colors.RESET}")

    documents = []
    scripts = []
    diagrams = []
    data_files = []

    if not quiet:
        print("1. Scanning project and calculating metrics...")
    
    file_count = 0
    excluded_dirs_count = 0
    
    for root, dirs, files in os.walk(PROJECT_ROOT, topdown=True):
        root_path = pathlib.Path(root)
        
        # --- Prune Directories In-Place ---
        # Filter out directories that should be excluded
        dirs_to_remove = []
        for d in dirs:
            if should_exclude_dir(root_path, d):
                dirs_to_remove.append(d)
                excluded_dirs_count += 1
        
        # Remove excluded directories from the walk
        for d in dirs_to_remove:
            dirs.remove(d)

        for filename in files:
            path = root_path / filename
            if should_exclude(path):
                continue

            file_count += 1
            rel_path = path.relative_to(PROJECT_ROOT).as_posix()
            
            # Categorize files. The order is important: specific types first, then fall back to location-based data files.
            rel_parts = path.relative_to(PROJECT_ROOT).parts

            if path.suffix in [".py", ".ps1"]:
                lines = count_non_empty_lines(path)
                scripts.append((f"`{rel_path}`", lines))
            elif path.suffix == ".md":
                words = count_words(path)
                documents.append((f"`{rel_path}`", words))
            elif path.parent.name == "diagrams" and path.suffix == ".mmd":
                lines = count_non_empty_lines(path)
                diagrams.append((f"`{rel_path}`", lines))
            else:
                # A file is considered a "data file" if it's under 'data/' or 'tests/assets/'
                is_data_file = (
                    len(rel_parts) > 1 and
                    (rel_parts[0] == 'data' or rel_parts[0:2] == ('tests', 'assets'))
                )
                if is_data_file and path.name != "README.md":
                    size_kb = get_file_size_kb(path)
                    data_files.append((f"`{rel_path}`", size_kb))

    if not quiet:
        print(f"   ...found and processed {file_count} files (excluded {excluded_dirs_count} directories).")
        print("2. Assembling the report content...")
    # --- Generate Report Content ---
    report_content = [f"# Project Scope & Extent Report\n\n**Generated on:** {datetime.now().strftime('%Y-%m-%d')}\n\n---\n"]

    # --- Pre-calculate all totals for summary ---
    total_words = sum(row[1] for row in documents)
    total_lines_scripts = sum(row[1] for row in scripts)
    total_lines_diagrams = sum(row[1] for row in diagrams)
    total_size_data = round(sum(row[1] for row in data_files), 1)

    # Overall Summary Section
    report_content.append("## 📊 Project at a Glance\n")
    total_artifacts = len(documents) + len(scripts) + len(diagrams) + len(data_files)
    summary_lines = [
        f"-   **Total Artifacts:** {total_artifacts:,} files",
        f"-   **Documents:** {len(documents)} files ({total_words:,} words)",
        f"-   **Scripts:** {len(scripts)} files ({total_lines_scripts:,} LoC)",
        f"-   **Diagrams:** {len(diagrams)} files ({total_lines_diagrams:,} lines)",
        f"-   **Data Files:** {len(data_files)} files ({total_size_data:,} KB)"
    ]
    report_content.append("\n".join(summary_lines))
    report_content.append("\n\n---\n")

    # Documents Section
    report_content.append("## 📄 Documents\n")
    report_content.append(f"-   **Total Files:** {len(documents)}")
    report_content.append(f"-   **Total Word Count:** {total_words:,}\n")
    report_content.append(generate_table(
        ["File", "Word Count"],
        sorted(documents),
        ["Total", f"{total_words:,}"]
    ))

    # Scripts Section
    total_lines_scripts = sum(row[1] for row in scripts)
    report_content.append("\n\n---\n\n## 💻 Scripts\n")
    report_content.append(f"-   **Total Files:** {len(scripts)}")
    report_content.append(f"-   **Total Lines of Code:** {total_lines_scripts:,}\n")
    report_content.append(generate_table(
        ["File", "Lines of Code"],
        sorted(scripts),
        ["Total", f"{total_lines_scripts:,}"]
    ))

    # Diagrams Section
    total_lines_diagrams = sum(row[1] for row in diagrams)
    report_content.append("\n\n---\n\n## 📊 Diagrams\n")
    report_content.append(f"-   **Total Files:** {len(diagrams)}")
    report_content.append(f"-   **Total Complexity Score (Lines):** {total_lines_diagrams:,}\n")
    report_content.append(generate_table(
        ["File", "Complexity (Lines)"],
        sorted(diagrams),
        ["Total", f"{total_lines_diagrams:,}"]
    ))

    # Data Files Section
    total_size_data = round(sum(row[1] for row in data_files), 1)
    report_content.append("\n\n---\n\n## 💾 Data Files\n")
    report_content.append(f"-   **Total Files:** {len(data_files)}")
    report_content.append(f"-   **Total Size:** {total_size_data:,} KB\n")
    report_content.append(generate_table(
        ["File", "Size (KB)"],
        sorted(data_files),
        ["Total", f"{total_size_data:,}"]
    ))

    # --- Write Report File ---
    if not quiet:
        print(f"3. Writing final report to {REPORT_FILENAME.relative_to(PROJECT_ROOT)}...")
    try:
        # Ensure the output directory exists before writing the file.
        REPORT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))
        if not quiet:
            print(f"\n{Colors.YELLOW}--- Analysis Complete ---{Colors.RESET}")
            print(f"{Colors.CYAN} - Report saved to: {REPORT_FILENAME.relative_to(PROJECT_ROOT)}{Colors.RESET}")
            print(f"{Colors.GREEN}SUCCESS: Project scope report generated successfully.{Colors.RESET}\n")
    except IOError as e:
        if not quiet:
            print(f"\n{Colors.RED}Error: Could not write report to {REPORT_FILENAME}. Details: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()

# === End of scripts/maintenance/generate_scope_report.py ===
