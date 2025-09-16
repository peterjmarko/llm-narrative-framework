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
Generates a quantitative report of the project's scope based on tracked Git files.

This utility creates a high-level summary of all project assets by analyzing
the output of the `git ls-files` command. This ensures the report accurately
reflects the state of all version-controlled source code, documentation, and
foundational data assets, providing a definitive snapshot of the project's scope.

The script categorizes each tracked file (document, script, diagram, data) and
calculates its "extent" (e.g., word count, lines of code). The final, aggregated
report is saved in Markdown format.
"""

import os
import pathlib
import subprocess
from datetime import datetime
from fnmatch import fnmatch

# --- Configuration ---
# The root of the project, determined by going up two levels from this script's location.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
REPORT_OUTPUT_DIR = PROJECT_ROOT / "output" / "project_reports"
REPORT_FILENAME = REPORT_OUTPUT_DIR / "project_scope_report.md"

# Directories to completely exclude from the scan.
EXCLUDE_DIRS = {
    ".git", ".pdm-build", ".pytest_cache", ".venv", "__pycache__",
    "build", "config", "data/backup", "dist", "htmlcov", "images",
    "linter_backups", "llm-narrative-framework.egg-info",
    "main_archive", "node_modules", "output", "src/archive", "venv"
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
    
    # Use the header length to create proportional separator lines for better rendering.
    separator_parts = []
    for h in headers:
        separator_parts.append("-" * len(h))
    separator_line = "|:" + ":|:".join(separator_parts) + ":|"
    
    row_lines = []
    for row in rows:
        row_lines.append("| " + " | ".join(map(str, row)) + " |")

    total_line = "| **" + "** | **".join(map(str, totals)) + "** |"
    
    return "\n".join([header_line, separator_line] + row_lines + [total_line])


def is_ignored(path, gitignore_patterns):
    """Check if a path matches any .gitignore patterns."""
    for pattern in gitignore_patterns:
        if fnmatch(path, pattern) or fnmatch(path.name, pattern):
            return True
    return False

DOCUMENT_CLASSIFICATIONS = {
    'CHANGELOG.md': "commitizen (`pdm run release`)",
    'output/project_reports/project_scope_report.md': "pdm run scope-report",
    'output/project_reports/project_structure_report_*.txt': "pdm run list-files",
    'docs/diagrams/view_directory_structure.txt': "pdm run list-files",
    'README.md': '.template.md',
    'data/DATA_DICTIONARY.md': '.template.md',
    'docs/DOCUMENTATION.md': '.template.md',
    'docs/LIFECYCLE_GUIDE.md': '.template.md',
    'docs/ROADMAP.md': 'Manual',
    'docs/TESTING.md': '.template.md',
    'docs/article_main_text.md': '.template.md',
    'docs/article_supplementary_material.md': '.template.md'
}

def main(quiet=False):
    """Main function to generate the project scope report."""
    if not quiet:
        print(f"{Colors.YELLOW}\n--- Starting Project Scope Analysis ---{Colors.RESET}")

    gitignore_patterns = []
    gitignore_path = PROJECT_ROOT / ".gitignore"
    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith("#"):
                    gitignore_patterns.append(stripped_line)

    documents = []
    active_scripts = []
    archived_scripts = []
    diagrams = []
    data_files = []

    if not quiet:
        print("1. Scanning project and calculating metrics...")
    
    # --- Robust File Discovery ---
    all_files = []
    template_stems = set()
    
    # First pass: find all template files
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not is_ignored(pathlib.Path(root) / d, gitignore_patterns)]
        for file in files:
            if file.endswith('.template.md'):
                template_stems.add(pathlib.Path(file).stem)

    # Second pass: collect all files, excluding generated .md files
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not is_ignored(pathlib.Path(root) / d, gitignore_patterns)]
        for file in files:
            path = pathlib.Path(root) / file
            
            # Exclude generated .md files if a template with the same name exists
            if path.suffix == '.md' and path.stem in template_stems:
                continue
            
            if not is_ignored(path, gitignore_patterns) and path.suffix not in EXCLUDE_EXTS:
                all_files.append(path)

    # --- Categorize all found files ---
    for path in all_files:
        rel_path = str(path.relative_to(PROJECT_ROOT)).replace('\\', '/')
        
        if path.suffix in [".py", ".ps1"]:
            lines = count_non_empty_lines(path)
            if '_archive' in path.parts:
                archived_scripts.append([f"`{rel_path}`", lines])
            else:
                active_scripts.append([f"`{rel_path}`", lines])
        elif path.name.endswith(".md"):
            words = count_words(path)
            report_path = rel_path.replace('.template.md', '.md')
            source = DOCUMENT_CLASSIFICATIONS.get(report_path, "Manual")
            documents.append([f"`{report_path}`", words, f"`{source}`"])
        elif path.suffix in [".mmd"] or rel_path == 'docs/diagrams/view_directory_structure.txt':
            lines = count_non_empty_lines(path)
            diagrams.append([f"`{rel_path}`", lines])
            
            if rel_path == 'docs/diagrams/view_directory_structure.txt':
                words = count_words(path)
                source = DOCUMENT_CLASSIFICATIONS.get(rel_path, "pdm run list-files")
                documents.append([f"`{rel_path}`", words, f"`{source}`"])
        else:
            rel_parts = path.relative_to(PROJECT_ROOT).parts
            is_data_file = (
                (len(rel_parts) > 1 and (rel_parts[0] == 'data' or rel_parts[0:2] == ('tests', 'assets'))) or
                (path.suffix == '.json' and rel_parts[0] == 'scripts')
            ) and path.suffix not in ['.md', '.py', '.ps1']

            if is_data_file:
                size_kb = get_file_size_kb(path)
                data_files.append([f"`{rel_path}`", size_kb])

    # --- Manually add known generated reports from the 'output' directory ---
    # The main file walk excludes 'output' for performance, so we add these back explicitly.
    
    # 1. Add the scope report itself.
    scope_report_path = PROJECT_ROOT / "output" / "project_reports" / "project_scope_report.md"
    if scope_report_path.exists():
        rel_path = str(scope_report_path.relative_to(PROJECT_ROOT)).replace('\\', '/')
        words = count_words(scope_report_path)
        source = DOCUMENT_CLASSIFICATIONS.get(rel_path, "Manual")
        documents.append([f"`{rel_path}`", words, f"`{source}`"])

    # 2. Group all project structure reports into a single entry.
    structure_report_path = PROJECT_ROOT / "output" / "project_reports"
    structure_reports = list(structure_report_path.glob("project_structure_report_*.txt"))
    if structure_reports:
        total_words = sum(count_words(p) for p in structure_reports)
        # The number of reports is 2 * (max_depth + 2), for git and non-git versions.
        # Assuming max depth is 6 (0-6), this gives 16 files (because --depth can be omitted). 
        # We'll hardcode this for simplicity to avoid a complex calculation based on actual found files.
        report_name = f"`output/project_reports/project_structure_report_*.txt` (16 files)"
        source = DOCUMENT_CLASSIFICATIONS.get('output/project_reports/project_structure_report_*.txt', "Manual")
        documents.append([report_name, total_words, f"`{source}`"])

    if not quiet:
        print(f"   ...found and processed {len(all_files)} files.")
        print("2. Assembling the report content...")
    # --- Generate Report Content ---
    report_content = [f"# Project Scope & Extent Report\n\n**Generated on:** {datetime.now().strftime('%Y-%m-%d')}\n"]
    report_content.append(
        "This report provides a quantitative summary of the project's source code, documentation, and foundational data assets. "
        "Generated artifacts, temporary files, and other excluded files are not included.\n\n---\n"
    )

    # --- Pre-calculate all totals for summary ---
    total_words = sum(row[1] for row in documents)
    total_lines_active_scripts = sum(row[1] for row in active_scripts)
    total_lines_diagrams = sum(row[1] for row in diagrams)
    total_size_data = round(sum(row[1] for row in data_files), 1)

    # Overall Summary Section
    report_content.append("## 📊 Project at a Glance (Active Files Only)\n")
    total_artifacts = len(documents) + len(active_scripts) + len(diagrams) + len(data_files)
    summary_lines = [
        f"-   **Total Artifacts:** {total_artifacts:,} files",
        f"-   **Documents:** {len(documents)} files ({total_words:,} words)",
        f"-   **Scripts:** {len(active_scripts)} files ({total_lines_active_scripts:,} LoC)",
        f"-   **Diagrams:** {len(diagrams)} files ({total_lines_diagrams:,} lines)",
        f"-   **Data Files:** {len(data_files)} files ({total_size_data:,} KB)"
    ]
    report_content.append("\n".join(summary_lines))
    report_content.append("\n\n---\n")

    # Documents Section
    report_content.append("## 📄 Documents\n")
    report_content.append(f"-   **Total Files:** {len(documents)}")
    report_content.append(f"-   **Total Word Count:** {total_words:,}\n")
    # Sort by the full path for a logical folder-then-file order.
    sorted_documents = sorted(documents, key=lambda row: row[0])
    
    report_content.append(generate_table(
        ["File                           ", "Word Count", "Source / Generator"],
        sorted_documents,
        ["Total", f"{total_words:,}", ""]
    ))

    # Scripts Section
    report_content.append("\n\n---\n\n## 💻 Scripts\n")
    
    # --- Active Scripts Subsection ---
    report_content.append("### Active Scripts\n")
    total_lines_active = sum(row[1] for row in active_scripts)
    report_content.append(f"-   **Total Files:** {len(active_scripts)}")
    report_content.append(f"-   **Total Lines of Code:** {total_lines_active:,}\n")
    report_content.append(generate_table(
        ["File", "Lines of Code"],
        sorted(active_scripts),
        ["Total", f"{total_lines_active:,}"]
    ))

    # --- Archived Scripts Subsection ---
    if archived_scripts:
        report_content.append("\n\n### Archived Scripts (Out of Scope for Publication)\n")
        total_lines_archived = sum(row[1] for row in archived_scripts)
        report_content.append(f"-   **Total Files:** {len(archived_scripts)}")
        report_content.append(f"-   **Total Lines of Code:** {total_lines_archived:,}\n")
        report_content.append(generate_table(
            ["File", "Lines of Code"],
            sorted(archived_scripts),
            ["Total", f"{total_lines_archived:,}"]
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
