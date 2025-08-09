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
# Filename: scripts/generate_scope_report.py

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
# The root of the project, determined by going up one level from this script's location.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT_FILENAME = PROJECT_ROOT / "project_scope_report.md"

# Directories to completely exclude from the scan.
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "output",
    "htmlcov", ".pytest_cache", "main_archive", "archive", "images",
    "llm_personality_matching.egg-info", "dist", "build",
    "data/backup", "data/temp", "linter_backups"
}

# File extensions to exclude.
EXCLUDE_EXTS = {".pyc", ".pyo", ".pyd", ".log", ".tmp", ".swp", ".lock", ".coverage", ".pdf", ".bak"}

# Proxy for calculating document pages.
WORDS_PER_PAGE = 250

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
    # Get the full path of the directory
    full_dir_path = root_path / dir_name
    
    # Get the relative path from project root
    try:
        rel_path = full_dir_path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        # If path is not relative to project root, don't exclude
        return False
    
    # Check against all exclusion patterns
    for excluded in EXCLUDE_DIRS:
        # Check exact match of directory name
        if dir_name == excluded:
            return True
        # Check exact match of relative path
        if rel_path == excluded:
            return True
        # Check if the relative path starts with an excluded path (for nested exclusions)
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


def main():
    """Main function to generate the project scope report."""
    print("--- Starting Project Scope Analysis ---")

    documents = []
    scripts = []
    diagrams = []
    data_files = []

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
            
            # Categorize files
            if path.suffix == ".md":
                words = count_words(path)
                pages = round(words / WORDS_PER_PAGE, 1)
                documents.append((f"`{rel_path}`", words, f"~{pages}"))
            elif path.suffix in [".py", ".ps1"]:
                lines = count_non_empty_lines(path)
                scripts.append((f"`{rel_path}`", lines))
            elif path.parent.name == "diagrams" and path.suffix == ".mmd":
                lines = count_non_empty_lines(path)
                diagrams.append((f"`{rel_path}`", lines))
            elif "data" in path.parts and path.name != "README.md":
                size_kb = get_file_size_kb(path)
                data_files.append((f"`{rel_path}`", size_kb))

    print(f"   ...found and processed {file_count} files (excluded {excluded_dirs_count} directories).")

    print("2. Assembling the report content...")
    # --- Generate Report Content ---
    report_content = [f"# Project Scope & Extent Report\n\n**Generated on:** {datetime.now().strftime('%Y-%m-%d')}\n\n---\n"]

    # Documents Section
    total_words = sum(row[1] for row in documents)
    total_pages = round(total_words / WORDS_PER_PAGE, 1)
    report_content.append("## 📄 Documents\n")
    report_content.append(f"-   **Total Files:** {len(documents)}")
    report_content.append(f"-   **Total Estimated Pages:** ~{total_pages} (based on {total_words:,} words)\n")
    report_content.append(generate_table(
        ["File", "Word Count", "Estimated Pages"],
        sorted(documents),
        ["Total", f"{total_words:,}", f"~{total_pages}"]
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
    print(f"3. Writing final report to {REPORT_FILENAME.name}...")
    try:
        with open(REPORT_FILENAME, "w", encoding="utf-8") as f:
            f.write("\n".join(report_content))
        print(f"\n--- Analysis Complete ---")
        print(f"Successfully generated report: {REPORT_FILENAME}")
    except IOError as e:
        print(f"\nError: Could not write report to {REPORT_FILENAME}. Details: {e}")

if __name__ == "__main__":
    main()

# === End of scripts/generate_scope_report.py ===
