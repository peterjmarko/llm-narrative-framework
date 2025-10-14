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
# Filename: scripts/maintenance/operation_runner.py

"""
Universal operation runner with locking and audit logging.

This script wraps command execution with:
- Global lock to prevent race conditions
- Automatic audit logging organized by operation category
- Category detection via pyproject.toml section headers

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
import json
import time
from pathlib import Path
from datetime import datetime
try:
    import tomllib
except ImportError:
    import tomli as tomllib


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

def get_operation_category(operation_name):
    """
    Determine the category of an operation by parsing pyproject.toml sections.
    
    Returns:
        A tuple of (log_filename, log_directory) e.g., ("test_summary.jsonl", "output/operation_logs")
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    pyproject_path = project_root / "pyproject.toml"
    log_dir = project_root / "output" / "operation_logs"
    
    try:
        with open(pyproject_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        current_section = None
        for line in lines:
            # Detect section headers based on the convention in pyproject.toml
            if '===' in line:
                line_upper = line.upper()
                if 'TESTING' in line_upper:
                    current_section = 'test'
                elif 'DATA PREPARATION' in line_upper:
                    current_section = 'data_prep'
                elif 'CORE PROJECT WORKFLOWS' in line_upper:
                    current_section = 'workflow'
            
            # Check if this line defines our specific operation
            if f'{operation_name} =' in line or f'"{operation_name}"' in line:
                if current_section == 'test':
                    return 'test_summary.jsonl', log_dir
                elif current_section == 'data_prep':
                    return 'data_prep_summary.jsonl', log_dir
                elif current_section == 'workflow':
                    return 'workflow_summary.jsonl', log_dir
                
                # If a match is found, stop searching
                return None, None
        
        return None, None
        
    except Exception:
        return None, None

def log_operation_summary(operation_name, exit_code, duration, filename, directory, command_args=None):
    """Log operation execution summary to structured file."""
    directory.mkdir(parents=True, exist_ok=True)
    summary_file = directory / filename
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "operation": operation_name,
        "status": "PASS" if exit_code == 0 else "FAIL",
        "exit_code": exit_code,
        "duration_seconds": round(duration, 2)
    }
    
    # Add command details if provided
    if command_args:
        entry["command"] = " ".join(command_args)
    
    with open(summary_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


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
        # shell=True is required to ensure PDM's virtual environment is properly used,
        # making all installed packages available to subprocesses on Windows
        start_time = time.time()
        try:
            result = subprocess.run(command, shell=True)
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return 130  # Standard exit code for Ctrl+C
        duration = time.time() - start_time
        
        # Log summary based on operation type (pattern matching)
        log_file, log_dir = get_operation_category(operation_name)
        if log_file and log_dir:
            log_operation_summary(operation_name, result.returncode, duration, log_file, log_dir, command)
        
        return result.returncode
    finally:
        # Always release lock
        release_lock(lock_file)


if __name__ == "__main__":
    sys.exit(main())

# === End of scripts/maintenance/operation_runner.py ===
