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
# Filename: scripts/lint/lint_docstrings.py

"""
A custom linter to enforce docstring standards in Python files.

This script scans Python files to ensure they meet a minimum standard of
internal documentation. It operates in two modes:
-   **High-Level (default):** Checks only for the presence and length of
    module-level docstrings.
-   **Deep Scan (`--deep`):** Checks all items, including functions, classes,
    and methods.

It is a read-only tool and does not modify files.

Usage:
    # Run a high-level scan (default)
    python scripts/lint/lint_docstrings.py

    # Run a deep scan to check all functions and classes
    python scripts/lint/lint_docstrings.py --deep
"""

import os
import ast
import glob
import pathlib
import sys
import argparse

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'

# --- Configuration ---
MIN_MODULE_DOCSTRING_LINES = 3
MIN_FUNCTION_DOCSTRING_WORDS = 8

EXCLUDED_FILENAMES = [
    "__init__.py",    # Not a script, just a package marker
    "conftest.py",    # Pytest fixture file, not a standard script
]

def analyze_docstrings(file_path: str, deep_scan: bool = False) -> list:
    """
    Analyzes a Python file using AST and returns a list of docstring warnings.
    """
    warnings = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content.strip():
                return [] # Skip empty files
            tree = ast.parse(content)
    except Exception as e:
        return [f"L0: Could not parse file: {e}"]

    # 1. Check Module-level docstring
    module_docstring = ast.get_docstring(tree, clean=False)
    if not module_docstring:
        warnings.append("L1: Missing module-level docstring.")
    elif len(module_docstring.splitlines()) < MIN_MODULE_DOCSTRING_LINES:
        warnings.append(f"L1: Module docstring is too short ({len(module_docstring.splitlines())} lines, {MIN_MODULE_DOCSTRING_LINES} required).")

    # 2. Check Function, Class, and Method docstrings (if deep scan is enabled)
    if deep_scan:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                # Ignore dunder methods for length checks
                is_dunder = node.name.startswith('__') and node.name.endswith('__')
                
                docstring = ast.get_docstring(node)
                if not docstring:
                    if not is_dunder:
                        warnings.append(f"L{node.lineno}: Missing docstring for {type(node).__name__.lower()} '{node.name}'.")
                elif not is_dunder and len(docstring.split()) < MIN_FUNCTION_DOCSTRING_WORDS:
                    warnings.append(f"L{node.lineno}: Docstring for {type(node).__name__.lower()} '{node.name}' is too short ({len(docstring.split())} words, {MIN_FUNCTION_DOCSTRING_WORDS} required).")

    return warnings

def main():
    parser = argparse.ArgumentParser(description="Linter for Python docstring standards.")
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Perform a deep scan, checking all functions, classes, and methods."
    )
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    scan_mode = "Deep Scan" if args.deep else "High-Level Scan"
    print(f"\n{Colors.YELLOW}Scanning project for Python docstrings ({scan_mode})...{Colors.ENDC}")
    
    results = {'COMPLIANT': [], 'NON_COMPLIANT': {}, 'SKIPPED': [], 'UNSCANNED': []}
    
    # --- Categorize all top-level directories ---
    explicitly_scanned_dirs = {'scripts', 'src', 'tests'}
    tooling_dirs_to_skip = {'.pytest_cache', '.venv', 'htmlcov', 'node_modules', '.git', '.idea', '.vscode', 'linter_backups'}
    all_top_level_dirs = {item.name for item in os.scandir(project_root) if item.is_dir()}
    unscanned_project_dirs = all_top_level_dirs - explicitly_scanned_dirs - tooling_dirs_to_skip
    results['UNSCANNED'].extend(sorted(list(unscanned_project_dirs)))
    existing_tooling_dirs = tooling_dirs_to_skip & all_top_level_dirs
    results['SKIPPED'].extend([f"{d}/ (tooling directory)" for d in sorted(list(existing_tooling_dirs))])

    # --- Collect and categorize files ---
    dirs_to_scan = [project_root] + [os.path.join(project_root, d) for d in ['scripts', 'src', 'tests']]
    all_candidate_files = []
    for d in dirs_to_scan:
        search_pattern = os.path.join(d, '**' if d != project_root else '', '*.py')
        all_candidate_files.extend(glob.glob(search_pattern, recursive=True))
    
    files_to_process = []
    for f in sorted(list(set(all_candidate_files))):
        rel_path = os.path.relpath(f, project_root).replace(os.sep, '/')
        path_parts = pathlib.Path(f).parts
        if 'archive' in path_parts:
            results['SKIPPED'].append(f"{rel_path} (in archive directory)")
        elif 'testing_harness' in path_parts:
            results['SKIPPED'].append(f"{rel_path} (in testing harness)")
        elif os.path.basename(f) in EXCLUDED_FILENAMES:
            results['SKIPPED'].append(rel_path)
        else:
            files_to_process.append(f)

    print(f"Found {len(files_to_process)} Python files to analyze.")

    # --- Perform Docstring Scan ---
    for file_path in files_to_process:
        rel_path = os.path.relpath(file_path, project_root).replace(os.sep, '/')
        warnings = analyze_docstrings(file_path, deep_scan=args.deep)
        if warnings:
            results['NON_COMPLIANT'][rel_path] = warnings
        else:
            results['COMPLIANT'].append(rel_path)

    # --- Print Detailed Report ---
    if results['NON_COMPLIANT']:
        print(f"\n{Colors.YELLOW}🔴 NON-COMPLIANT ({len(results['NON_COMPLIANT'])}):{Colors.ENDC}")
        for f, warns in results['NON_COMPLIANT'].items():
            print(f"   - {f}")
            for w in warns:
                print(f"     - {w}")

    if results['COMPLIANT']:
        print(f"\n{Colors.YELLOW}✅ COMPLIANT ({len(results['COMPLIANT'])}):{Colors.ENDC}")
        for f in results['COMPLIANT']: print(f"   - {f}")
        
    if results['SKIPPED']:
        print(f"\n{Colors.YELLOW}⚪ SKIPPED ({len(results['SKIPPED'])}):{Colors.ENDC}")
        for f in results['SKIPPED']: print(f"   - {f} (excluded by rule)")

    if results['UNSCANNED']:
        print(f"\n{Colors.YELLOW}⚫ UNSCANNED ({len(results['UNSCANNED'])}):{Colors.ENDC}")
        for d in results['UNSCANNED']: print(f"   - {d}/ (directory not scanned for docstrings)")

    # --- Print Final Summary ---
    print(f"\n{Colors.YELLOW}--- Docstring Linting Summary ---{Colors.ENDC}")
    print(f"Total Python files analyzed: {len(files_to_process)}")
    if results['NON_COMPLIANT']: print(f"🔴 Non-compliant files: {len(results['NON_COMPLIANT'])}")
    if results['COMPLIANT']: print(f"✅ Compliant files: {len(results['COMPLIANT'])}")
    if results['SKIPPED']: print(f"⚪ Skipped items: {len(results['SKIPPED'])}")
    if results['UNSCANNED']: print(f"⚫ Unscanned directories: {len(results['UNSCANNED'])}")
    print("----------------------------------\n")
    
    if results['NON_COMPLIANT']:
        print("Docstring linting finished with non-compliant files.\n")
        sys.exit(1)
    
    print("All analyzed files are compliant.")
    print("\nLinting complete.\n")

if __name__ == "__main__":
    main()

# === End of scripts/lint/lint_docstrings.py ===

