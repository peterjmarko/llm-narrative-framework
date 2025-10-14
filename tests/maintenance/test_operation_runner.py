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
# Filename: tests/maintenance/test_operation_runner.py

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pyfakefs.fake_filesystem import FakeFilesystem

# Add src to path to allow importing the script under test
import sys
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir / "scripts" / "maintenance"))

from operation_runner import main as operation_runner_main

@pytest.fixture
def mock_project(fs: FakeFilesystem, mocker) -> Path:
    """Sets up a fake project structure with a pyproject.toml file."""
    project_root = Path("/app")
    # Define the path where the script *thinks* it is located
    fake_script_path = project_root / "scripts" / "maintenance" / "operation_runner.py"

    # Create the fake directory structure for the script
    fs.create_dir(fake_script_path.parent)

    # This is the critical fix: Patch the __file__ attribute of the module under test.
    # This tricks the script into believing it lives inside our fake filesystem.
    mocker.patch('operation_runner.__file__', str(fake_script_path))

    fs.cwd = project_root
    pyproject_content = """
[tool.pdm.scripts]
# === TESTING ===
test-op = "echo 'testing'"

# === DATA PREPARATION ===
prep-data = "echo 'prepping data'"

# === CORE PROJECT WORKFLOWS ===
new-exp = "echo 'new experiment'"
    """
    fs.create_file("pyproject.toml", contents=pyproject_content)
    return project_root

@pytest.mark.usefixtures('fs')
def test_lock_acquire_and_release(mock_project: Path, mocker):
    """Tests that a lock is acquired during execution and released afterward."""
    # Correctly mock subprocess.run to return an object with an integer returncode
    mocker.patch('subprocess.run', return_value=mocker.Mock(returncode=0))
    lock_file = mock_project / ".pdm-locks" / "operations.lock"

    assert not lock_file.exists()

    with patch('sys.argv', ["script.py", "test-op", "echo", "hello"]):
        result_code = operation_runner_main()

    assert not lock_file.exists()
    assert result_code == 0

@pytest.mark.usefixtures('fs')
def test_lock_prevents_concurrent_run(mock_project: Path, capsys):
    """Tests that an existing lock file prevents a new operation from running."""
    lock_dir = mock_project / ".pdm-locks"
    lock_dir.mkdir()
    (lock_dir / "operations.lock").write_text("previous-op")

    with patch('sys.argv', ["script.py", "test-op", "echo", "hello"]):
        result_code = operation_runner_main()
    
    assert result_code == 1
    captured = capsys.readouterr()
    assert "ERROR: Cannot acquire lock" in captured.err

@pytest.mark.parametrize("op_name, command, expected_log_file", [
    ("test-op", ["echo", "test"], "test_summary.jsonl"),
    ("prep-data", ["echo", "data"], "data_prep_summary.jsonl"),
    ("new-exp", ["echo", "workflow"], "workflow_summary.jsonl"),
])
@pytest.mark.usefixtures('fs')
def test_operation_categorization_and_logging(mock_project: Path, mocker, op_name, command, expected_log_file):
    """Tests that operations are correctly categorized and logged to the right file."""
    mocker.patch('subprocess.run', return_value=mocker.Mock(returncode=0))
    
    with patch('sys.argv', ["script.py", op_name, *command]):
        operation_runner_main()
    
    log_path = mock_project / "output" / "operation_logs" / expected_log_file
    assert log_path.exists()
    
    log_content = log_path.read_text()
    log_entry = json.loads(log_content)
    
    assert log_entry["operation"] == op_name
    assert log_entry["status"] == "PASS"

@pytest.mark.usefixtures('fs')
def test_command_failure_is_logged_correctly(mock_project: Path, mocker):
    """Tests that a failed command is logged with a 'FAIL' status."""
    mocker.patch('subprocess.run', return_value=mocker.Mock(returncode=127))

    with patch('sys.argv', ["script.py", "test-op", "bad-command"]):
        result_code = operation_runner_main()
    
    assert result_code == 127
    log_path = mock_project / "output" / "operation_logs" / "test_summary.jsonl"
    assert log_path.exists()

    log_entry = json.loads(log_path.read_text())
    assert log_entry["status"] == "FAIL"
    assert log_entry["exit_code"] == 127

# === End of tests/maintenance/test_operation_runner.py ===
