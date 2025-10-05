#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: scripts/maintenance/count_files.py

import os
from pathlib import Path

def count_files_in_dir(directory):
    """Count files in a directory recursively."""
    count = 0
    for root, dirs, files in os.walk(directory):
        count += len(files)
    return count

def main():
    project_root = Path(".")
    dir_counts = {}
    
    # Get all top-level directories
    for item in project_root.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            count = count_files_in_dir(item)
            dir_counts[item.name] = count
    
    # Sort by count (descending)
    sorted_dirs = sorted(dir_counts.items(), key=lambda x: x[1], reverse=True)
    
    print("Directory file counts:")
    for dir_name, count in sorted_dirs:
        print(f"{dir_name}: {count} files")
    
    total = sum(count for _, count in sorted_dirs)
    print(f"\nTotal: {total} files")

if __name__ == "__main__":
    main()

# === End of scripts/maintenance/count_files.py ===
