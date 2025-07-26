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
"""

import os
import argparse
import re
import sys
import glob

# --- Configuration ---

EXCLUDED_FILENAMES = [
    "__init__.py",
    "conftest.py",
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
    """Analyzes a file and optionally fixes its header and footer using procedural parsing."""
    if os.path.basename(file_path) in EXCLUDED_FILENAMES:
        print(f"SKIPPED: {os.path.relpath(file_path, project_root)} (in exclusion list)")
        return True # Return True as it's not a failure

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return False

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
        return True # Unsupported file type

    # Normalize line endings for comparison
    normalized_original_content = original_content.replace('\r\n', '\n')

    if normalized_original_content != correct_content:
        if fix:
            try:
                with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(correct_content)
                print(f"FIXED: {relative_path}")
                return True
            except Exception as e:
                print(f"Error writing to {file_path}: {e}")
                return False
        else:
            print(f"INVALID: {relative_path}")
            return False
    
    print(f"VALID: {relative_path}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Linter for script file headers and footers.")
    parser.add_argument("files", nargs='+', help="One or more file paths or glob patterns.")
    parser.add_argument("--fix", action="store_true", help="Apply fixes to files that fail validation.")
    args = parser.parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    
    files_to_process = []
    for pattern in args.files:
        expanded_files = glob.glob(pattern, recursive=True)
        if not expanded_files:
            print(f"Warning: No files found matching pattern '{pattern}'")
        files_to_process.extend(expanded_files)

    all_valid = True
    for file_path in sorted(list(set(files_to_process))):
        if not process_file(file_path, project_root, args.fix):
            all_valid = False
            
    if not all_valid and not args.fix:
        print("\nOne or more files failed validation. Run with --fix to apply changes.")
        sys.exit(1)
        
    print("\nLinting complete.")

if __name__ == "__main__":
    main()

# === End of src/lint_file_headers.py ===
