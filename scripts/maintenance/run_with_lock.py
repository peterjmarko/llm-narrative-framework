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
# Filename: scripts/maintenance/run_with_lock.py

"""
Universal lock wrapper for preventing race conditions in PDM operations.

This script wraps any command execution with a global lock to prevent
concurrent operations that could corrupt data or experiments.

Usage:
    python scripts/maintenance/run_with_lock.py <operation_name> <command> [args...]

Example:
    python scripts/maintenance/run_with_lock.py "test-data-prep" pytest tests/data_preparation/

Exit Codes:
    0: Success
    1: Lock already held by another operation
    2: Command execution failed
"""

import sys
import os
import subprocess
from pathlib import Path


def get_lock_dir():
    """Get the project-relative lock directory."""
    project_root = Path(__file__).resolve().parent.parent.parent
    lock_dir = project_root / ".pdm-locks"
    lock_dir.mkdir(exist_ok=True)
    return lock_dir


def acquire_lock(operation_name):
    """
    Attempt to acquire the global operation lock.
    
    Returns:
        Path to lock file if acquired, None otherwise
    """
    lock_file = get_lock_dir() / "operations.lock"
    
    try:
        # Try to create lock file exclusively (fails if exists)
        # Use 'x' mode - exclusive creation, fails if file exists
        with open(lock_file, 'x') as f:
            f.write(operation_name)
        return lock_file
    except FileExistsError:
        # Lock is held by another process
        # Read the operation name from the lock file
        try:
            with open(lock_file, 'r') as f:
                holding_operation = f.read().strip()
        except:
            holding_operation = "unknown operation"
        
        # ANSI color codes
        YELLOW = '\033[93m'
        RESET = '\033[0m'
        
        print(f"\n{YELLOW}ERROR: Cannot acquire lock. Another operation is currently running: {holding_operation}{RESET}", file=sys.stderr)
        print(f"Wait for the operation to complete, or use 'pdm run unlock' if the lock is stale.\n", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: Failed to acquire lock: {e}", file=sys.stderr)
        return None


def release_lock(lock_file):
    """Release the operation lock."""
    if lock_file and lock_file.exists():
        try:
            lock_file.unlink()
        except:
            pass


def main():
    if len(sys.argv) < 3:
        print("Usage: run_with_lock.py <operation_name> <command> [args...]", file=sys.stderr)
        return 2
    
    operation_name = sys.argv[1]
    command = sys.argv[2:]
    
    # Acquire lock
    lock_file = acquire_lock(operation_name)
    if not lock_file:
        return 1
    
    try:
        # Run the command
        result = subprocess.run(command)
        return result.returncode
    finally:
        # Always release lock
        release_lock(lock_file)


if __name__ == "__main__":
    sys.exit(main())

# === End of scripts/maintenance/run_with_lock.py ===
