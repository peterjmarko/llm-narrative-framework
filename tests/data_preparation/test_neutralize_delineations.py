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
# Filename: tests/data_preparation/test_neutralize_delineations.py

"""
Unit tests for the delineation neutralization script (src/neutralize_delineations.py).

This test suite validates the script's critical offline logic, focusing on:
1.  Parsing the unique, esoteric format of the raw Solar Fire delineation library.
2.  Correctly grouping the parsed delineations into distinct, logical tasks for
    the LLM worker.
3.  The main processing loop, including --fast mode, resumability, and error handling.
"""

import csv
from pathlib import Path
import re
from unittest.mock import patch
from types import SimpleNamespace

import pytest
from src import neutralize_delineations
from src.neutralize_delineations import group_delineations, parse_llm_response
from types import SimpleNamespace

# --- Test Data ---
MOCK_DELINEATION_CONTENT = """
; This is a comment and should be ignored.
*Title
Sample Delineations

*Sun in Aries
You are a pioneer.
|This is a continuation line.

*Sun in Taurus
You are steadfast.

*Quadrant 1 Strong
You are independent.

*Element Fire Strong
You are passionate.
"""

# --- Mocks and Fixtures ---

class MockLLMWorker:
    """A mock for subprocess.run that simulates various llm_prompter.py outcomes."""
    def __init__(self, fail_on_task=None):
        self.fail_on_task = fail_on_task

    def run(self, cmd, check, **kwargs):
        task_name = cmd[2]
        
        args = {cmd[i].lstrip('-'): cmd[i+1] for i in range(1, len(cmd), 2) if i + 1 < len(cmd)}
        query_file = Path(args['input_query_file'])
        response_file = Path(args['output_response_file'])
        error_file = Path(args['output_error_file'])

        if self.fail_on_task and self.fail_on_task in task_name:
            error_file.write_text(f"Simulated failure for {task_name}")
        else:
            # Simulate success by writing the core delineation block back as the response
            query_text = query_file.read_text()
            match = re.search(r'---\n(.*)\n---', query_text, re.DOTALL)
            if match:
                delineation_block = match.group(1).strip()
                response_file.write_text(delineation_block)
        
        return SimpleNamespace(returncode=0, stdout="", stderr="")

@pytest.fixture
def mock_sandbox(tmp_path: Path) -> dict:
    """Creates a sandbox environment with mock input files."""
    assets_dir = tmp_path / "data/foundational_assets"
    assets_dir.mkdir(parents=True)
    delineation_path = assets_dir / "sf_delineations_library.txt"
    delineation_path.write_text(MOCK_DELINEATION_CONTENT)
    
    (tmp_path / "config.ini").write_text("[DataGeneration]\npoints_for_neutralization=Sun\n")

    return {
        "sandbox_path": tmp_path,
        "output_dir": assets_dir / "neutralized_delineations",
    }

# --- Core Logic Tests ---

def test_parse_llm_response(tmp_path):
    """
    Tests the parsing of the raw delineation file format, including comments,
    multi-line entries, and line continuations.
    """
    mock_file = tmp_path / "test.txt"
    mock_file.write_text(MOCK_DELINEATION_CONTENT)
    delineations = parse_llm_response(mock_file)
    
    assert delineations["Title"] == "Sample Delineations"
    assert delineations["Sun in Aries"] == "You are a pioneer. This is a continuation line."
    assert delineations["Quadrant 1 Strong"] == "You are independent."
    assert ";" not in str(delineations)

def test_group_delineations():
    """
    Tests the logic for grouping parsed delineations into their target output files.
    """
    mock_dels = {"Quadrant 1 Strong": "Text", "Sun in Leo": "Text", "Other": "Text"}
    groups = group_delineations(mock_dels, ["Sun"])
    assert groups["balances_quadrants.csv"] == {"Quadrant 1 Strong": "Text"}
    assert groups["points_in_signs.csv"] == {"Sun in Leo": "Text"}
    assert "Other" not in str(groups)

# --- Main Workflow and Orchestration Tests ---

def test_full_run_default_mode(mock_sandbox):
    """Tests a successful run from scratch in default (atomic task) mode."""
    paths = mock_sandbox
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]
    
    with patch("sys.argv", test_args), \
         patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run) as mock_run:
        neutralize_delineations.main()

    # Should be 4 tasks: Q1S, EFS, SiA, SiT
    assert mock_run.call_count == 4
    quadrants_file = paths["output_dir"] / "balances_quadrants.csv"
    assert "You are independent." in quadrants_file.read_text()

def test_full_run_fast_mode(mock_sandbox):
    """Tests a successful run from scratch in --fast (bundled task) mode."""
    paths = mock_sandbox
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force", "--fast"]
    
    with patch("sys.argv", test_args), \
         patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run) as mock_run:
        neutralize_delineations.main()

    # Should be 2 tasks: one for all balances, one for all "Sun in Signs"
    assert mock_run.call_count == 2
    elements_file = paths["output_dir"] / "balances_elements.csv"
    assert "You are passionate." in elements_file.read_text()

def test_resume_run_skips_completed_tasks(mock_sandbox, capsys):
    """Tests that the script correctly skips already completed tasks."""
    paths = mock_sandbox
    paths["output_dir"].mkdir()
    
    # Pre-create a complete balance file and a partial points file
    (paths["output_dir"] / "balances_quadrants.csv").write_text('"Quadrant 1 Strong","You are independent."\n')
    (paths["output_dir"] / "points_in_signs.csv").write_text('"Sun in Aries","You are a pioneer."\n')

    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"])]
    with patch("sys.argv", test_args), \
         patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run) as mock_run:
        neutralize_delineations.main()

    # Should only run the 2 missing tasks: Element Fire Strong and Sun in Taurus
    assert mock_run.call_count == 2
    captured = capsys.readouterr()
    # The partial points file is for generating, so only 1 file is truly skipped.
    assert "Found 1 existing/complete file(s) that will be skipped" in captured.out

def test_worker_failure_is_handled_gracefully(mock_sandbox, capsys):
    """Tests that a worker failure is logged but does not crash the script."""
    paths = mock_sandbox
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]

    # Mock the worker to fail specifically on the 'Sun in Aries' task
    mock_worker = MockLLMWorker(fail_on_task="Sun in Aries")
    with patch("sys.argv", test_args), \
         patch("src.neutralize_delineations.subprocess.run", side_effect=mock_worker.run):
        neutralize_delineations.main()
    
    captured = capsys.readouterr()
    assert "Failed:    1 tasks" in captured.out
    assert "Simulated failure for Sun in Aries" in captured.out

def test_debug_task_workflow(mock_sandbox, capsys):
    """Tests that the --debug-task flag isolates a task and exits."""
    paths = mock_sandbox
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--debug-task", "Sun in Aries"]

    with patch("sys.argv", test_args), \
         patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run) as mock_run:
        with pytest.raises(SystemExit) as e:
            neutralize_delineations.main()
        assert e.value.code == 0
    
    mock_run.assert_called_once()
    captured = capsys.readouterr()
    assert "DEBUG MODE: ISOLATING TASK 'Sun in Aries'" in captured.out
    assert "PROMPT SENT TO LLM" in captured.out

def test_bypass_llm_functionality(tmp_path):
    """
    Tests that the --bypass-llm flag correctly writes original content to output.
    """
    sandbox_path = tmp_path
    
    assets_dir = sandbox_path / "data/foundational_assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "sf_delineations_library.txt").write_text(MOCK_DELINEATION_CONTENT)
    (sandbox_path / "config.ini").write_text("[DataGeneration]\npoints_for_neutralization=Sun\n")

    test_args = ["script.py", "--sandbox-path", str(sandbox_path), "--bypass-llm"]

    with patch("sys.argv", test_args):
        with pytest.raises(SystemExit) as e:
            neutralize_delineations.main()
        assert e.value.code == 0

    quadrants_file = assets_dir / "neutralized_delineations/balances_quadrants.csv"
    assert "You are independent." in quadrants_file.read_text()

# === End of tests/data_preparation/test_neutralize_delineations.py ===
