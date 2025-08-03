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
# Filename: src/lint_file_headers.py

"""
A custom linter to enforce a standard header and footer format for all project scripts.

This script ensures that all Python (.py) and PowerShell (.ps1) files adhere to
a consistent header and footer structure, which includes a copyright/license
block and a dynamic filename tag.

Key Features:
-   Validates the presence and format of a shebang, license block, and footer.
-   Can automatically fix non-compliant files with the `--fix` flag.
-   When fixing, it creates a timestamped backup of all original files in a
    `linter_backups/` directory in the project root, ensuring no data is lost.

Usage:
    # Check all scripts for compliance using the default patterns (.py, .ps1)
    python scripts/lint_file_headers.py

    # Automatically fix all non-compliant scripts
    python scripts/lint_file_headers.py --fix
    
    # Check a specific file or pattern
    python scripts/lint_file_headers.py "src/some_specific_script.py"
"""

import os
import argparse
import pathlib
import re
import sys
import glob
import shutil
from datetime import datetime

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- Configuration ---

EXCLUDED_FILENAMES = [
    "__init__.py",    # Not a script, just a package marker
    "conftest.py",    # Pytest fixture file, not a standard script
]

LICENSE_BLOCK = """
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
""".strip()

def get_shebang(file_extension):
    """Returns the correct shebang line for the file type."""
    if file_extension == '.py':
        return "#!/usr/bin/env python3"
    if file_extension == '.ps1':
        return "#!/usr/bin/env pwsh"
    return None

def generate_correct_content(core_content, relative_path, file_extension):
    """Generates the full, correctly formatted file content."""
    shebang = get_shebang(file_extension)
    if not shebang:
        return None  # Skip unsupported file types

    core_content = core_content.strip()
    posix_relative_path = relative_path.replace(os.path.sep, '/')

    header = [
        shebang,
        "#-*- coding: utf-8 -*-",
        "#",
        LICENSE_BLOCK,
        "#",
        f"# Filename: {posix_relative_path}",
    ]
    
    footer = f"# === End of {posix_relative_path} ==="
    
    # Use '\n' for all line endings for consistency.
    full_content = "\n".join(header) + "\n\n" + core_content + "\n\n" + footer + "\n"
    return full_content

def is_header_line(line):
    """Determines if a line is part of a file's header."""
    stripped = line.strip()
    return not stripped or stripped.startswith(('#!', '#-*-', '#'))

def process_file(file_path, project_root, fix=False):
    """
    Analyzes a file and optionally fixes it. Returns a status string:
    'VALID', 'INVALID', 'FIXED', 'SKIPPED', or 'ERROR'.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return 'ERROR'

    lines = original_content.splitlines()

    # Find the end of the header (first line that is not a comment/shebang/blank)
    header_end_index = 0
    for i, line in enumerate(lines):
        if not is_header_line(line):
            header_end_index = i
            break
    else: # If loop completes without break, file is all comments/blank
        header_end_index = len(lines)

    # Find the start of the footer (first footer line from the bottom)
    footer_start_index = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('# === End of'):
            footer_start_index = i
            break

    # The body is everything between the header and the footer.
    core_content = "\n".join(lines[header_end_index:footer_start_index]).strip()

    relative_path = os.path.relpath(file_path, project_root)
    _, file_extension = os.path.splitext(file_path)
    
    correct_content = generate_correct_content(core_content, relative_path, file_extension)
    
    if not correct_content:
        return 'SKIPPED' # Unsupported file type

    # Normalize line endings for comparison
    normalized_original_content = original_content.replace('\r\n', '\n')

    if normalized_original_content != correct_content:
        if fix:
            try:
                with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(correct_content)
                return 'FIXED'
            except Exception as e:
                print(f"Error writing to {file_path}: {e}")
                return 'ERROR'
        else:
            return 'INVALID'
    
    return 'VALID'

def main():
    # This script no longer uses command-line arguments.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    print(f"\n{Colors.YELLOW}Scanning project for script files...{Colors.ENDC}")
    
    results = {'COMPLIANT': [], 'NON_COMPLIANT': [], 'SKIPPED': [], 'ERROR': [], 'UNSCANNED': []}
    
    # --- Categorize all top-level directories ---
    explicitly_scanned_dirs = {'scripts', 'src', 'tests'}
    tooling_dirs_to_skip = {'.pytest_cache', '.venv', 'htmlcov', 'node_modules', '.git', '.idea', '.vscode', 'linter_backups'}
    
    all_top_level_dirs = {item.name for item in os.scandir(project_root) if item.is_dir()}
    
    unscanned_project_dirs = all_top_level_dirs - explicitly_scanned_dirs - tooling_dirs_to_skip
    results['UNSCANNED'].extend(sorted(list(unscanned_project_dirs)))
    
    # Add tooling directories that actually exist to the SKIPPED list
    existing_tooling_dirs = tooling_dirs_to_skip & all_top_level_dirs
    results['SKIPPED'].extend([f"{d}/ (tooling directory)" for d in sorted(list(existing_tooling_dirs))])

    # --- Collect and categorize files ---
    dirs_to_scan = [project_root] + [os.path.join(project_root, d) for d in ['scripts', 'src', 'tests']]
    all_candidate_files = []
    for d in dirs_to_scan:
        search_pattern_ps1 = os.path.join(d, '**' if d != project_root else '', '*.ps1')
        all_candidate_files.extend(glob.glob(search_pattern_ps1, recursive=True))
        search_pattern_py = os.path.join(d, '**' if d != project_root else '', '*.py')
        all_candidate_files.extend(glob.glob(search_pattern_py, recursive=True))
    
    files_to_process = []
    for f in sorted(list(set(all_candidate_files))):
        rel_path = os.path.relpath(f, project_root).replace(os.sep, '/')
        # Check for archive directory first, as it's a broad exclusion
        if 'archive' in pathlib.Path(f).parts:
            results['SKIPPED'].append(f"{rel_path} (in archive directory)")
        # Then check for filename-based exclusions
        elif os.path.basename(f) in EXCLUDED_FILENAMES:
            results['SKIPPED'].append(rel_path)
        else:
            files_to_process.append(f)

    print(f"Found {len(files_to_process)} files to analyze.")

    for file_path in files_to_process:
        status_map = {'VALID': 'COMPLIANT', 'INVALID': 'NON_COMPLIANT'}
        # Pass fix=False, as this is the initial scan. process_file no longer checks EXCLUDED_FILENAMES
        raw_status = process_file(file_path, project_root, fix=False)
        status = status_map.get(raw_status, raw_status)
        rel_path = os.path.relpath(file_path, project_root).replace(os.sep, '/')
        results[status].append(rel_path)

    # --- Print Detailed Lists ---
    if results['NON_COMPLIANT']:
        print(f"\n{Colors.YELLOW}🔴 NON-COMPLIANT ({len(results['NON_COMPLIANT'])}):{Colors.ENDC}")
        for f in results['NON_COMPLIANT']: print(f"   - {f}")

    if results['COMPLIANT']:
        print(f"\n{Colors.YELLOW}✅ COMPLIANT ({len(results['COMPLIANT'])}):{Colors.ENDC}")
        for f in results['COMPLIANT']: print(f"   - {f}")
        
    if results['SKIPPED']:
        print(f"\n{Colors.YELLOW}⚪ SKIPPED ({len(results['SKIPPED'])}):{Colors.ENDC}")
        for f in results['SKIPPED']: print(f"   - {f} (excluded by rule)")

    if results['UNSCANNED']:
        print(f"\n{Colors.YELLOW}⚫ UNSCANNED ({len(results['UNSCANNED'])}):{Colors.ENDC}")
        for d in results['UNSCANNED']: print(f"   - {d}/ (directory not scanned for scripts)")

    # --- Print High-Level Summary ---
    print(f"\n{Colors.YELLOW}--- Linting Summary ---{Colors.ENDC}")
    print(f"Total scripts found: {len(files_to_process)}")
    if results['NON_COMPLIANT']: print(f"🔴 Non-compliant scripts: {len(results['NON_COMPLIANT'])}")
    if results['COMPLIANT']: print(f"✅ Compliant scripts: {len(results['COMPLIANT'])}")
    if results['SKIPPED']: print(f"⚪ Skipped items: {len(results['SKIPPED'])}")
    if results['UNSCANNED']: print(f"⚫ Unscanned directories: {len(results['UNSCANNED'])}")
    if results['ERROR']: print(f"❌ Error scripts: {len(results['ERROR'])}")
    print("-----------------------\n")

    # --- Interactive Fix Prompt ---
    fix_was_run = False
    if results['NON_COMPLIANT']:
        should_fix = False
        try:
            prompt = "Do you want to fix the non-compliant files? (Y/N): "
            response = input(prompt)
            if response.strip().lower() == 'y':
                should_fix = True
        except (KeyboardInterrupt, EOFError):
            should_fix = False
        
        if not should_fix:
            print(f"\n{Colors.YELLOW}Operation cancelled by user.{Colors.ENDC}\n")
            sys.exit(1)

        # --- Backup Stage ---
        print(f"\n{Colors.YELLOW}--- Applying Fixes ---{Colors.ENDC}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(project_root, "linter_backups", f"backup_{timestamp}")
        try:
            os.makedirs(backup_dir, exist_ok=True)
            print("Backing up original files...")
            for rel_path in results['NON_COMPLIANT']:
                source_path = os.path.join(project_root, rel_path)
                dest_path = os.path.join(backup_dir, os.path.basename(source_path))
                shutil.copy2(source_path, dest_path)
            # Use relative path for the output message
            relative_backup_dir = os.path.relpath(backup_dir, project_root).replace(os.sep, '/')
            print(f"All {len(results['NON_COMPLIANT'])} original files backed up to: {relative_backup_dir}\n")
        except OSError as e:
            print(f"Error: Could not create backup directory or copy files: {e}")
            sys.exit(1)

        # --- Final Confirmation ---
        try:
            prompt = "Proceed with overwriting original files? (Y/N): "
            response = input(prompt)
            if response.strip().lower() != 'y':
                print(f"\n{Colors.YELLOW}Operation cancelled. Originals restored from backup are untouched.{Colors.ENDC}\n")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Operation cancelled. Originals restored from backup are untouched.{Colors.ENDC}\n")
            sys.exit(1)

        # --- Fixing Stage ---
        fix_was_run = True
        print("") # Add a newline for cleaner output
        fixed_count = 0
        for rel_path in results['NON_COMPLIANT']:
            full_path = os.path.join(project_root, rel_path)
            status = process_file(full_path, project_root, fix=True)
            if status == 'FIXED':
                print(f"🟢 FIXED: {rel_path}")
                fixed_count += 1
            else:
                print(f"❌ FAILED TO FIX: {rel_path} (Status: {status})")
        
        print(f"\nSuccessfully fixed {fixed_count} of {len(results['NON_COMPLIANT'])} non-compliant files.")
    
    print("\nLinting complete.")

if __name__ == "__main__":
    main()

# === End of src/lint_file_headers.py ===
