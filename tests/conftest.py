#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
# Filename: tests/conftest.py

import sys
import os

# Add the 'src' directory to the Python path
# This ensures that modules like 'run_batch', 'llm_prompter', etc.,
# can be imported directly from the 'src' directory by tests,
# allowing coverage.py to correctly track their execution.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
src_path = os.path.join(project_root, 'src')

if src_path not in sys.path:
    sys.path.insert(0, src_path)

# You can add common fixtures here if needed for multiple tests.
# For example:
# @pytest.fixture(scope="function")
# def temp_output_dir():
#     with tempfile.TemporaryDirectory() as tmpdir:
#         yield tmpdir


import pytest


def pytest_addoption(parser):
    """Adds the --test-record-number command-line option to pytest."""
    parser.addoption(
        "--test-record-number",
        action="store",
        type=int,
        default=None,
        help="Specify a single record number (e.g., 1-18) to test for assembly logic.",
    )


@pytest.fixture
def test_record_number(request):
    """A fixture to retrieve the value of the --test-record-number option."""
    return request.config.getoption("--test-record-number")


# === Lock Management for Race Condition Prevention ===
from pathlib import Path

# Add maintenance scripts to path
maintenance_path = Path(project_root) / "scripts" / "maintenance"
if str(maintenance_path) not in sys.path:
    sys.path.insert(0, str(maintenance_path))

from run_with_lock import acquire_lock, release_lock


@pytest.fixture(scope="session", autouse=True)
def session_lock():
    """
    Automatically acquire lock for entire pytest session.
    
    If pytest is called through PDM wrapper, the lock is already held,
    so we skip acquisition to avoid blocking ourselves.
    """
    lock_dir = Path(project_root) / ".pdm-locks"
    lock_file_path = lock_dir / "operations.lock"
    
    lock_acquired = False
    lock_file = None
    
    # Only try to acquire if lock doesn't exist
    if not lock_file_path.exists():
        lock_file = acquire_lock("pytest")
        if not lock_file:
            pytest.exit("Cannot run tests: lock held by another operation", returncode=1)
        lock_acquired = True
    
    yield
    
    # Only release if we acquired it
    if lock_acquired and lock_file:
        release_lock(lock_file)

# === End of tests/conftest.py ===
