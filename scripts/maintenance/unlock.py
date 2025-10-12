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
# Filename: scripts/maintenance/unlock.py

"""
Manual unlock utility for removing stale operation locks.

This script forcefully removes the operation lock file. Use only when:
- A process crashed without releasing the lock
- You're certain no operations are actually running

Usage:
    python scripts/maintenance/unlock.py

Exit Codes:
    0: Lock removed successfully (or didn't exist)
    1: Failed to remove lock
"""

import sys
from pathlib import Path


def main():
    project_root = Path(__file__).resolve().parent.parent.parent
    lock_file = project_root / ".pdm-locks" / "operations.lock"
    
    if not lock_file.exists():
        print("No lock file found. Nothing to unlock.")
        return 0
    
    try:
        # Read current lock holder before removing
        with open(lock_file, 'r') as f:
            operation = f.read().strip()
        
        lock_file.unlink()
        print(f"Lock removed. Previous operation was: {operation}")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to remove lock: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

# === End of scripts/maintenance/unlock.py ===
