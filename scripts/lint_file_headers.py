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
# Filename: scripts/lint_file_headers.py

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
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- Configuration ---

EXCLUDED_FILENAMES = [
    "__init__.py",    # Not a script, just a package marker
    "conftest.py",    # Pytest fixture file, not a standard script
]

LICENSE_BLOCK = """
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

def analyze_file_content(original_content, relative_path):
    """
    Analyzes a file's content and returns its parts and compliance status.

    Returns:
        dict: A dictionary containing:
              'is_compliant' (bool),
              'core_content' (str),
              'correct_content' (str)
    """
    lines = original_content.splitlines()

    # Find the end of the header
    header_end_index = 0
    for i, line in enumerate(lines):
        if not is_header_line(line):
            header_end_index = i
            break
    else:
        header_end_index = len(lines)

    # Find the start of the footer
    footer_start_index = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().startswith('# === End of'):
            footer_start_index = i
            break

    core_content = "\n".join(lines[header_end_index:footer_start_index]).strip()
    
    _, file_extension = os.path.splitext(relative_path)
    correct_content = generate_correct_content(core_content, relative_path, file_extension)

    # Normalize line endings for a reliable comparison
    normalized_original = original_content.replace('\r\n', '\n')
    is_compliant = (normalized_original == correct_content)
    
    return {
        'is_compliant': is_compliant,
        'core_content': core_content,
        'correct_content': correct_content
    }

def main():
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    print(f"\n{Colors.YELLOW}Scanning project for script files...{Colors.ENDC}")
    
    # --- Initializing result categories ---
    results = {'COMPLIANT': [], 'NON_COMPLIANT': [], 'SKIPPED': [], 'ERROR': [], 'UNSCANNED': []}
    file_contents = {} # Store file contents to avoid re-reading

    # --- Categorize directories and collect files ---
    # (Code for this section remains the same as the last correct version)
    explicitly_scanned_dirs = {'scripts', 'src', 'tests'}
    tooling_dirs_to_skip = {'.pytest_cache', '.venv', 'htmlcov', 'node_modules', '.git', '.idea', '.vscode', 'linter_backups'}
    all_top_level_dirs = {item.name for item in os.scandir(project_root) if item.is_dir()}
    unscanned_project_dirs = all_top_level_dirs - explicitly_scanned_dirs - tooling_dirs_to_skip
    results['UNSCANNED'].extend(sorted(list(unscanned_project_dirs)))
    existing_tooling_dirs = tooling_dirs_to_skip & all_top_level_dirs
    results['SKIPPED'].extend([f"{d}/ (tooling directory)" for d in sorted(list(existing_tooling_dirs))])
    dirs_to_scan = [project_root] + [os.path.join(project_root, d) for d in ['scripts', 'src', 'tests']]
    all_candidate_files = []
    for d in dirs_to_scan:
        patterns = [os.path.join(d, '**' if d != project_root else '', '*.ps1'), os.path.join(d, '**' if d != project_root else '', '*.py')]
        for p in patterns: all_candidate_files.extend(glob.glob(p, recursive=True))
    
    # --- Perform initial scan ---
    print(f"Found {len(list(set(all_candidate_files)))} candidate files. Analyzing...")
    for f_path in sorted(list(set(all_candidate_files))):
        rel_path = os.path.relpath(f_path, project_root).replace(os.sep, '/')
        path_parts = pathlib.Path(f_path).parts
        if 'archive' in path_parts:
            results['SKIPPED'].append(f"{rel_path} (in archive directory)")
            continue
        if os.path.basename(f_path) in EXCLUDED_FILENAMES:
            results['SKIPPED'].append(rel_path)
            continue
        try:
            content = pathlib.Path(f_path).read_text(encoding='utf-8')
            file_contents[rel_path] = content
            analysis = analyze_file_content(content, rel_path)
            if analysis['is_compliant']:
                results['COMPLIANT'].append(rel_path)
            else:
                results['NON_COMPLIANT'].append(rel_path)
        except Exception:
            results['ERROR'].append(rel_path)

    # --- Display results and prompt ---
    # (Code for displaying lists and summary remains the same)
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
    print(f"\n{Colors.YELLOW}--- Linting Summary ---{Colors.ENDC}")
    print(f"Total files analyzed: {len(file_contents)}")
    if results['NON_COMPLIANT']: print(f"🔴 Non-compliant files: {len(results['NON_COMPLIANT'])}")
    if results['COMPLIANT']: print(f"✅ Compliant files: {len(results['COMPLIANT'])}")
    if results['SKIPPED']: print(f"⚪ Skipped items: {len(results['SKIPPED'])}")
    if results['UNSCANNED']: print(f"⚫ Unscanned directories: {len(results['UNSCANNED'])}")
    if results['ERROR']: print(f"❌ Error files: {len(results['ERROR'])}")
    print("-----------------------\n")

    # --- Safe Fixing Workflow ---
    if results['NON_COMPLIANT']:
        # ... (prompting logic remains the same)
        try:
            print("Non-compliant files found. If you decide to go ahead with fixing them, backups of the existing files will be created first.")
            if input("Do you wish to proceed? (Y/N): ").strip().lower() != 'y':
                raise KeyboardInterrupt
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Operation cancelled by user.{Colors.ENDC}\n")
            sys.exit(1)

        # Backup Stage
        print(f"\n{Colors.YELLOW}--- Applying Fixes ---{Colors.ENDC}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(project_root, "linter_backups", f"backup_{timestamp}")
        os.makedirs(backup_dir, exist_ok=True)
        print("Backing up original files...")
        for rel_path in results['NON_COMPLIANT']:
            shutil.copy2(os.path.join(project_root, rel_path), os.path.join(backup_dir, os.path.basename(rel_path)))
        relative_backup_dir = os.path.relpath(backup_dir, project_root).replace(os.sep, '/')
        print(f"{Colors.CYAN}All {len(results['NON_COMPLIANT'])} original files backed up to: {relative_backup_dir}{Colors.ENDC}")

        # Fixing Stage (No second confirmation needed)
        print(f"\n{Colors.YELLOW}--- Validating and Applying Fixes ---{Colors.ENDC}")
        fixed_count, integrity_failures, validation_failures = 0, [], []
        for rel_path in results['NON_COMPLIANT']:
            print(f"Validating fix for: {rel_path}")
            original_content = file_contents[rel_path]
            analysis = analyze_file_content(original_content, rel_path)
            new_analysis = analyze_file_content(analysis['correct_content'], rel_path)

            # 1. Integrity Check
            if analysis['core_content'] != new_analysis['core_content']:
                print(f"  - {Colors.RED}Integrity Check FAILED. Aborting fix.{Colors.ENDC}")
                integrity_failures.append(rel_path)
                continue
            print(f"  - {Colors.GREEN}Integrity Check PASSED.{Colors.ENDC}")

            # 2. Post-Fix Validation
            if not new_analysis['is_compliant']:
                print(f"  - {Colors.RED}Post-Fix Validation FAILED. Aborting fix.{Colors.ENDC}")
                validation_failures.append(rel_path)
                continue
            print(f"  - {Colors.GREEN}Post-Fix Validation PASSED.{Colors.ENDC}")
            
            # 3. Overwrite File
            try:
                with open(os.path.join(project_root, rel_path), 'w', encoding='utf-8', newline='\n') as f:
                    f.write(analysis['correct_content'])
                print(f"🟢 FIXED: {rel_path}")
                fixed_count += 1
            except Exception as e:
                print(f"❌ FAILED TO WRITE: {rel_path} ({e})\n")

        # Report on fixing results
        if integrity_failures:
            print(f"\n{Colors.RED}CRITICAL: {len(integrity_failures)} files failed integrity check and were NOT modified:{Colors.ENDC}")
            for f in integrity_failures: print(f"   - {f}")
        if validation_failures:
            print(f"\n{Colors.RED}ERROR: {len(validation_failures)} files failed post-fix validation and were NOT modified:{Colors.ENDC}")
            for f in validation_failures: print(f"   - {f}")
        
        print(f"\n{Colors.GREEN}Successfully fixed {fixed_count} of {len(results['NON_COMPLIANT'])} non-compliant files.{Colors.ENDC}")
    else:
        print(f"\n{Colors.GREEN}All files are compliant.{Colors.ENDC}")
    
    print("\nLinting complete.\n")

if __name__ == "__main__":
    main()

# === End of scripts/lint_file_headers.py ===
