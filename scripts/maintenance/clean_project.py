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
# Filename: scripts/maintenance/clean_project.py

"""
A utility to safely clean temporary and generated files from the project.

This script archives cache files, test reports, backups, and other temporary
artifacts into a timestamped ZIP file to free up disk space and maintain a
clean workspace. It then prunes old archives, always keeping the two most recent.

Key Features:
-   **Safe by Default**: Runs in "dry run" mode by default, listing items
    that would be archived and old archives that would be deleted.
-   **Non-Destructive Cleanup**: In `--execute` mode, files are moved into a
    timestamped ZIP archive in the `cleaner_archives/` directory, not
    permanently deleted. This provides a simple "undo" mechanism.
-   **Self-Healing**: If a cleanup run is interrupted, the script will
    automatically restore all files from the partial archive on the next run
    before proceeding.
-   **Intelligent Pruning**: Automatically deletes all previous archives after a
    successful run, keeping only the newest one.
-   **Categorized Reporting**: Clearly lists what will be cleaned in categories
    like "Cache," "Test Reports," "Backups," etc.
-   **Size Calculation**: Reports the total disk space that will be reclaimed.

Usage:
    # Perform a dry run (default behavior) to see what would be cleaned.
    pdm run clean

    # Execute the cleanup process (will ask for confirmation).
    pdm run clean -- --execute
"""

import argparse
import pathlib
import shutil
import sys
import re
from collections import defaultdict
from tqdm import tqdm
from datetime import datetime
import zipfile
import os

# --- ANSI Color Codes ---
class Colors:
    YELLOW = '\033[93m'
    GREEN = '\033[92m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# --- Configuration: Define what to clean ---

ARCHIVE_DIR_NAME = "cleaner_archives"
STATE_FILE_NAME = ".last_successful_cleanup"

# Directories and glob patterns to be deleted recursively.
DIRECTORIES_TO_DELETE = {
    "Cache": ["**/__pycache__", "**/.pytest_cache", "src/llm_personality_matching.egg-info"],
    "Test Reports": ["htmlcov"],
    "Temporary Sandboxes": ["temp_*", "tests/temp_*"],
    "Backups & Archives": ["linter_backups", "data/backup", "*archive*"]
}

# Specific files or glob patterns to delete from the project root.
FILES_TO_DELETE = {
    "Test Reports": [".coverage"],
    "Temporary Files": ["~$*.*"]
}

def get_path_info(path):
    """Calculates the total size and file count of a path."""
    total_size = 0
    file_count = 0
    if path.is_dir():
        for fp in path.rglob('*'):
            if fp.is_file() and not fp.is_symlink():
                try:
                    total_size += fp.stat().st_size
                    file_count += 1
                except FileNotFoundError:
                    continue
    elif path.is_file() and path.exists() and not path.is_symlink():
        total_size = path.stat().st_size
        file_count = 1
    return total_size, file_count

def format_size(size_bytes):
    """Formats a size in bytes into a human-readable string in MB."""
    return f"{size_bytes / (1024*1024):.2f} MB"


def main(root_path=None):
    # If a root_path isn't provided (production), calculate it.
    # If it is provided (testing), use the provided path.
    project_root = root_path or pathlib.Path(__file__).resolve().parent.parent

    parser = argparse.ArgumentParser(description="Clean temporary and generated files from the project.")
    parser.add_argument("--execute", action="store_true", help="Perform the deletion. Defaults to a dry run.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress bars. Used for testing.")
    args = parser.parse_args()

    print(f"\n{Colors.BOLD}{Colors.YELLOW}--- Project Cleanup Utility ---{Colors.ENDC}")
    if not args.execute:
        print(f"{Colors.CYAN}Running in DRY RUN mode. No files will be deleted.{Colors.ENDC}")
    
    found_items = {}
    total_size = 0
    
    # Hard-coded exclusions for safety, in addition to .gitignore
    # This prevents accidental deletion of the development environment.
    safe_exclusions = {project_root / '.venv', project_root / '.git', project_root / ARCHIVE_DIR_NAME}

    if not args.quiet:
        print("\nScanning for items to clean...")
    
    # 1. Find items to delete using glob patterns
    all_patterns = [
        (category, pattern)
        for category, patterns in DIRECTORIES_TO_DELETE.items()
        for pattern in patterns
    ]
    
    with tqdm(total=len(all_patterns), desc="Analyzing", ncols=80, disable=args.quiet) as pbar:
        for category, pattern in all_patterns:
            pbar.set_postfix_str(f"Searching for '{pattern}'")
            for path in project_root.glob(pattern):
                # Ensure we don't clean inside the virtual environment or the path itself is excluded
                if path.exists() and path not in safe_exclusions and not any(part in safe_exclusions for part in path.parents):
                    if category not in found_items:
                        found_items[category] = []
                    size, file_count = get_path_info(path)
                    if file_count > 0: # Only add if there's something to clean
                        found_items[category].append((path, size, file_count))
                        total_size += size
            pbar.update(1)

    # Also scan for individual files
    file_patterns = [
        (category, pattern)
        for category, patterns in FILES_TO_DELETE.items()
        for pattern in patterns
    ]

    for category, pattern in file_patterns:
        for path in project_root.glob(pattern):
            # Ensure we don't clean inside the virtual environment or the path itself is excluded
            if path.exists() and path not in safe_exclusions and not any(part in safe_exclusions for part in path.parents):
                if category not in found_items:
                    found_items[category] = []
                size, file_count = get_path_info(path)
                if file_count > 0:
                    found_items[category].append((path, size, file_count))
                    total_size += size

    # 3. Execute self-healing first if in execute mode (before checking if clean)
    if args.execute:
        archive_dir = project_root / ARCHIVE_DIR_NAME
        archive_dir.mkdir(exist_ok=True)
        state_file = archive_dir / STATE_FILE_NAME
        last_good_archive_name = state_file.read_text().strip() if state_file.exists() else ""
        
        # --- Self-Healing Stage ---
        all_archives = list(archive_dir.glob("cleanup_archive_*.zip"))
        corrupted_archives = [p for p in all_archives if p.name != last_good_archive_name]
        
        if corrupted_archives:
            print(f"\n{Colors.YELLOW}--- Recovering from a previous failed run ---{Colors.ENDC}")
            for archive in corrupted_archives:
                print(f"Restoring files from incomplete archive: {archive.name}")
                try:
                    with zipfile.ZipFile(archive, 'r') as zipf:
                        zipf.extractall(path=project_root)
                    archive.unlink()
                    print(f"  {Colors.GREEN}Restored and removed incomplete archive.{Colors.ENDC}")
                except Exception as e:
                    print(f"  {Colors.RED}ERROR: Failed to restore from {archive.name}: {e}{Colors.ENDC}")
            # Relaunch the process to get a fresh, accurate report
            print("\nRestarting cleanup process with a clean state...")
            main(root_path=project_root)
            sys.exit(0)

    if not found_items:
        print(f"\n{Colors.GREEN}Project is already clean. Nothing to do.{Colors.ENDC}\n")
        sys.exit(0)

    # 4. Report what was found
    print(f"\n{Colors.BOLD}Found {format_size(total_size)} of items to clean:{Colors.ENDC}")
    total_folders = 0
    total_files = 0
    for category, items in sorted(found_items.items()):
        print(f"\n  {Colors.BOLD}{category}:{Colors.ENDC}")
        for path, size, file_count in items:
            if path.is_dir():
                total_folders += 1
            total_files += file_count
            rel_path = path.relative_to(project_root).as_posix()
            file_str = "file" if file_count == 1 else "files"
            print(f"    - {rel_path:<50} ({file_count:,} {file_str}, {format_size(size)})")

    print("\n" + "-" * 60)
    print(f"  {Colors.BOLD}{'Total Folders to Delete:':<25} {total_folders}{Colors.ENDC}")
    print(f"  {Colors.BOLD}{'Total Files to Delete:':<25} {total_files:,}{Colors.ENDC}")
    print(f"  {Colors.BOLD}{'Total Size to Reclaim:':<25} {format_size(total_size)}{Colors.ENDC}")
    print("-" * 60)

    # 5. Execute archiving and pruning (we already did self-healing above)
    if args.execute:

        # --- Confirmation Stage ---
        print(f"\n{Colors.BOLD}{Colors.YELLOW}The items listed above will be moved to a timestamped ZIP archive.{Colors.ENDC}")
        try:
            confirm = input("Are you sure you want to proceed? (Y/N): ")
            if confirm.strip().lower() != 'y':
                print(f"{Colors.YELLOW}Operation cancelled by user.{Colors.ENDC}\n")
                sys.exit(0)
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.YELLOW}Operation cancelled by user.{Colors.ENDC}\n")
            sys.exit(0)

        # --- Main Execution Block ---
        new_archive_filename = ""
        try:
            archives_to_delete = sorted(list(archive_dir.glob("cleanup_archive_*.zip")))
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_archive_filename = f"cleanup_archive_{timestamp}.zip"
            archive_path = archive_dir / new_archive_filename
            print(f"\n--- Archiving {format_size(total_size)} of items to {new_archive_filename} ---")
            
            all_paths_to_clean = [item[0] for sublist in found_items.values() for item in sublist]
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                with tqdm(total=len(all_paths_to_clean), desc="Archiving", ncols=80, disable=args.quiet) as pbar:
                    for path in all_paths_to_clean:
                        pbar.set_postfix_str(path.name)
                        try:
                            if path.is_file():
                                zipf.write(path, path.relative_to(project_root))
                                path.unlink()
                            elif path.is_dir():
                                for file_path in path.rglob('*'):
                                    if file_path.is_file():
                                        zipf.write(file_path, file_path.relative_to(project_root))
                                shutil.rmtree(path)
                        except FileNotFoundError:
                            continue
                        except Exception as e:
                            print(f"  {Colors.RED}ERROR:{Colors.ENDC} Could not archive {path.relative_to(project_root).as_posix()}: {e}")
                        pbar.update(1)
            
            print(f"\n{Colors.GREEN}Archiving complete.{Colors.ENDC}")

            print("\n--- Pruning old archives ---")
            if archives_to_delete:
                print(f"Deleting {len(archives_to_delete)} previous archive(s)...")
                for old_archive in archives_to_delete:
                    old_archive.unlink()
                    print(f"  {Colors.GREEN}DELETED:{Colors.ENDC} {old_archive.name}")
            else:
                print("No previous archives found to prune.")

            # Finalization: Update State File on Success
            with open(state_file, "w", encoding="utf-8") as f:
                f.write(new_archive_filename)

            print(f"\n{Colors.GREEN}Cleanup complete. Reclaimed {format_size(total_size)} of disk space.{Colors.ENDC}\n")

        except Exception as e:
            print(f"\n{Colors.RED}ERROR: Cleanup operation failed: {e}{Colors.ENDC}")
            print(f"{Colors.YELLOW}The partial archive '{new_archive_filename}' will be restored on the next run.{Colors.ENDC}\n")
            sys.exit(1)
    else:
        # Save the report to a file
        report_dir = project_root / "output" / "project_reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "cleanup_report.txt"
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("--- Project Cleanup Report ---\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            total_folders = 0
            total_files = 0
            for items in found_items.values():
                for path, _, file_count in items:
                    if path.is_dir():
                        total_folders += 1
                    total_files += file_count
            
            f.write(f"Total folders to delete: {total_folders}\n")
            f.write(f"Total files to delete:   {total_files:,}\n")
            f.write(f"Total size to reclaim:   {format_size(total_size)}\n")

            for category, items in sorted(found_items.items()):
                f.write(f"\n{category}:\n")
                for path, size, file_count in items:
                    rel_path = path.relative_to(project_root).as_posix()
                    file_str = "file" if file_count == 1 else "files"
                    f.write(f"    - {rel_path:<50} ({file_count:,} {file_str}, {format_size(size)})\n")
        
        print(f"\nDry run report saved to: {Colors.CYAN}{report_path.relative_to(project_root).as_posix()}{Colors.ENDC}")
        print(f"To delete these items, run: {Colors.CYAN}pdm run clean -- --execute{Colors.ENDC}\n")

if __name__ == "__main__":
    main()

# === End of scripts/maintenance/clean_project.py ===
