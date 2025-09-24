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
# Filename: src/utils/file_utils.py

"""
Provides shared utility functions for file and directory operations.
"""
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from colorama import Fore

# Ensure the src directory is in the Python path for nested imports
sys.path.append(str(Path(__file__).resolve().parents[2]))
from config_loader import get_path, PROJECT_ROOT


def backup_and_remove(path_to_remove: Path):
    """
    Creates a timestamped backup of a file or directory, then removes the original.

    This ensures a clean state for a forced re-run while preserving the old data.
    The backup is placed in the project's `data/backup/` directory.

    Args:
        path_to_remove (Path): The file or directory to back up and remove.
    """
    if not path_to_remove.exists():
        return  # Nothing to do

    try:
        backup_dir = Path(get_path('data/backup'))
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if path_to_remove.is_dir():
            backup_name = f"{path_to_remove.name}_{timestamp}.zip"
            backup_path = backup_dir / backup_name
            shutil.make_archive(str(backup_path.with_suffix('')), 'zip', path_to_remove)
            shutil.rmtree(path_to_remove)
            logging.info(f"{Fore.CYAN}Backed up directory '{path_to_remove.name}' to '{os.path.relpath(backup_path, PROJECT_ROOT)}'{Fore.RESET}")
        else:
            backup_name = f"{path_to_remove.stem}.{timestamp}{path_to_remove.suffix}.bak"
            backup_path = backup_dir / backup_name
            shutil.copy2(path_to_remove, backup_path)
            path_to_remove.unlink()
            logging.info(f"{Fore.CYAN}Backed up file '{path_to_remove.name}' to '{os.path.relpath(backup_path, PROJECT_ROOT)}'{Fore.RESET}")

    except Exception as e:
        logging.error(f"{Fore.RED}Failed during backup/removal of {path_to_remove.name}: {e}")
        sys.exit(1)

# === End of src/utils/file_utils.py ===
