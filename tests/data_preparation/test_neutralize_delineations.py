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
    def __init__(self, fail_on_task=None, crash_on_task=None, malform_on_task=None):
        self.fail_on_task = fail_on_task
        self.crash_on_task = crash_on_task
        self.malform_on_task = malform_on_task

    def run(self, cmd, check, **kwargs):
        task_name = cmd[2]

        if self.crash_on_task and self.crash_on_task in task_name:
            return SimpleNamespace(returncode=1, stdout="Worker stdout", stderr="Simulated worker crash")

        args = {cmd[i].lstrip('-'): cmd[i+1] for i in range(1, len(cmd), 2) if i + 1 < len(cmd)}
        query_file = Path(args['input_query_file'])
        response_file = Path(args['output_response_file'])
        error_file = Path(args['output_error_file'])

        if self.fail_on_task and self.fail_on_task in task_name:
            error_file.write_text(f"Simulated failure for {task_name}")
        elif self.malform_on_task and self.malform_on_task in task_name:
            # Simulate a malformed response (e.g., missing a key from a bundle)
            query_text = query_file.read_text()
            match = re.search(r'---\n(.*)\n---', query_text, re.DOTALL)
            if match:
                delineation_block = match.group(1).strip()
                lines = delineation_block.splitlines()
                # Remove the first key-value pair to cause a mismatch
                if lines and lines[0].startswith('*') and len(lines) > 2:
                    response_file.write_text("\n".join(lines[2:]))
                else: # Fallback for single-item tasks
                     response_file.write_text("*Malformed\nResponse")
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


def test_worker_crash_is_handled_gracefully(mock_sandbox, capsys):
    """Tests that a worker crash (non-zero exit) is logged."""
    paths = mock_sandbox
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]

    # Mock the worker to crash specifically on the 'Sun in Aries' task
    mock_worker = MockLLMWorker(crash_on_task="Sun in Aries")
    with patch("sys.argv", test_args), \
         patch("src.neutralize_delineations.subprocess.run", side_effect=mock_worker.run):
        neutralize_delineations.main()
    
    captured = capsys.readouterr()
    assert "Failed:    1 tasks" in captured.out
    assert "LLM worker crashed with exit code 1" in captured.out
    assert "Worker stdout" in captured.out
    assert "Simulated worker crash" in captured.out

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


class TestCoverageAndEdgeCases:
    """Additional tests for uncovered lines and edge cases."""

    def test_bypass_llm_exits_if_input_missing(self, mock_sandbox):
        """Verify bypass mode exits if the delineation library is missing."""
        paths = mock_sandbox
        (paths["sandbox_path"] / "data/foundational_assets/sf_delineations_library.txt").unlink()
        
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--bypass-llm"]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                neutralize_delineations.main()
            assert e.value.code == 1

    def test_parse_llm_response_no_file(self, tmp_path):
        """Verify parse_llm_response returns {} if the file does not exist."""
        from src.neutralize_delineations import parse_llm_response
        non_existent_file = tmp_path / "no_such_file.txt"
        assert parse_llm_response(non_existent_file) == {}

    def test_parse_sf_content_edge_cases(self):
        """Tests parsing of Solar Fire content with edge cases."""
        from src.neutralize_delineations import parse_sf_content

        # Empty content
        assert parse_sf_content([]) == {}

        # Comments and whitespace only
        content = ["; a comment", "   ", "; another comment"]
        assert parse_sf_content(content) == {}

        # Key with no text
        content = ["*Key1", "  ", "*Key2", "Some text"]
        dels = parse_sf_content(content)
        assert dels["Key1"] == ""
        assert dels["Key2"] == "Some text"

        # Content ends with a key
        content = ["*Key1", "Some text", "*Key2"]
        dels = parse_sf_content(content)
        assert dels["Key1"] == "Some text"
        assert dels["Key2"] == ""

    @pytest.mark.parametrize("task, expected_group", [
        ({'type': 'point_in_sign', 'name': 'Moon in Cancer'}, "The Moon in Signs"),
        ({'type': 'point_in_sign', 'name': 'Sun in Leo'}, "The Sun in Signs"),
        ({'type': 'point_bundle', 'name': 'Mars in Signs'}, "Mars in Signs"),
        ({'type': 'balance', 'name': 'quadrants'}, "Balance Delineations"),
        ({'type': 'other', 'name': 'Some Task'}, "Miscellaneous Tasks"),
    ])
    def test_get_task_group(self, task, expected_group):
        """Test the logic for determining a task's display group."""
        from src.neutralize_delineations import get_task_group
        assert get_task_group(task) == expected_group

    def test_resort_csv_handles_non_existent_file(self, tmp_path):
        """Verify resort_csv does not fail if the input file does not exist."""
        from src.neutralize_delineations import resort_csv_by_key_order
        non_existent_file = tmp_path / "no_such_file.csv"
        # Should run without raising an exception
        resort_csv_by_key_order(non_existent_file, [])
    
    def test_resort_csv_positive_case(self, tmp_path):
        """Verify resort_csv correctly sorts an existing file."""
        from src.neutralize_delineations import resort_csv_by_key_order
        
        csv_file = tmp_path / "data.csv"
        # Write data in a jumbled order
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["C", "3"])
            writer.writerow(["A", "1"])
            writer.writerow(["D", "4"])
            writer.writerow(["B", "2"])

        key_order = ["A", "B", "C", "D"]
        resort_csv_by_key_order(csv_file, key_order)

        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            sorted_rows = list(reader)
        
        assert sorted_rows == [["A", "1"], ["B", "2"], ["C", "3"], ["D", "4"]]

    def test_get_processed_keys_handles_io_error(self, tmp_path):
        """Verify get_processed_keys returns an empty set on file read error."""
        from src.neutralize_delineations import get_processed_keys_from_csv
        # The file exists but we mock `open` to fail
        file_path = tmp_path / "file.csv"
        file_path.touch()
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            keys = get_processed_keys_from_csv(file_path)
        assert keys == set()

    def test_get_processed_keys_handles_csv_error(self, tmp_path):
        """Verify get_processed_keys returns an empty set on CSV parsing error."""
        from src.neutralize_delineations import get_processed_keys_from_csv
        import csv

        file_path = tmp_path / "bad.csv"
        file_path.write_text("this content doesn't matter, the mock will raise an error")

        # Mock csv.reader to raise an error to directly test the except block.
        with patch('csv.reader', side_effect=csv.Error("Simulated CSV error")):
            keys = get_processed_keys_from_csv(file_path)
        
        assert keys == set()

    def test_get_processed_keys_with_empty_row(self, tmp_path):
        """Verify get_processed_keys skips empty rows in a CSV."""
        from src.neutralize_delineations import get_processed_keys_from_csv
        file_path = tmp_path / "test.csv"
        file_path.write_text('"key1","val1"\n\n"key2","val2"')
        keys = get_processed_keys_from_csv(file_path)
        assert keys == {"key1", "key2"}

    def test_main_non_interactive_mode(self, mock_sandbox, capsys):
        """Tests the script's output in a non-interactive (non-TTY) session."""
        paths = mock_sandbox
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]

        with patch("sys.argv", test_args), \
             patch("sys.stdout.isatty", return_value=False), \
             patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run):
            neutralize_delineations.main()
        
        captured = capsys.readouterr()
        # Should use simple print statements, not tqdm progress bars
        assert "[1/4] Neutralizing quadrants" in captured.out
        assert "->" in captured.out
    
    def test_main_with_no_tasks_to_run(self, mock_sandbox, capsys):
        """Tests the exit path when all output files are already present."""
        paths = mock_sandbox
        # Pre-create all expected output files
        output_dir = paths["output_dir"]
        output_dir.mkdir()
        (output_dir / "balances_quadrants.csv").touch()
        (output_dir / "balances_elements.csv").touch()
        # For points_in_signs, it needs to be "complete"
        points_file = output_dir / "points_in_signs.csv"
        with open(points_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Sun in Aries", ""])
            writer.writerow(["Sun in Taurus", ""])

        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"])]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                neutralize_delineations.main()
            assert e.value.code == 0
        
        captured = capsys.readouterr()
        assert "All delineation files are already up to date" in captured.out

    def test_main_debug_task_not_found(self, mock_sandbox, capsys):
        """Tests the error message when a debug task is not found."""
        paths = mock_sandbox
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--debug-task", "NonExistentTask"]
        
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                neutralize_delineations.main()
            assert e.value.code == 0

        captured = capsys.readouterr()
        assert "Debug task 'NonExistentTask' not found" in captured.out

    def test_main_stale_check_triggers_force(self, mock_sandbox, capsys):
        """Tests that a newer input file triggers a forced re-run."""
        import os
        import time

        paths = mock_sandbox
        output_dir = paths["output_dir"]
        output_dir.mkdir()
        input_path = paths["sandbox_path"] / "data/foundational_assets/sf_delineations_library.txt"

        # Make output dir older than input file
        now = time.time()
        os.utime(output_dir, (now - 10, now - 10))
        os.utime(input_path, (now, now))

        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"])]
        
        with patch("sys.argv", test_args), \
             patch("src.neutralize_delineations.backup_and_remove") as mock_backup, \
             patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run):
            neutralize_delineations.main()
        
        captured = capsys.readouterr()
        assert "Stale data detected" in captured.out
        mock_backup.assert_called_once_with(output_dir)

    def test_main_unsets_sandbox_env_var(self):
        """Tests that the sandbox env var is unset in a normal run."""
        import os
        os.environ["PROJECT_SANDBOX_PATH"] = "/tmp/fake_sandbox"

        with patch("sys.argv", ["script.py"]), \
             patch("src.neutralize_delineations.Path.exists", return_value=False), \
             patch("src.neutralize_delineations.logging.error"):
             # We expect a sys.exit because the input file doesn't exist
            with pytest.raises(SystemExit):
                neutralize_delineations.main()
        
        assert "PROJECT_SANDBOX_PATH" not in os.environ

    def test_force_flag_interactive_warning(self, mock_sandbox, capsys):
        """Tests that the --force warning is shown in interactive mode."""
        paths = mock_sandbox
        paths["output_dir"].mkdir()
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]

        with patch("sys.argv", test_args), \
             patch("sys.stdout.isatty", return_value=True), \
             patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run):
            neutralize_delineations.main()
        
        captured = capsys.readouterr()
        assert "WARNING: The --force flag is active." in captured.out

    def test_main_handles_keyboard_interrupt(self, mock_sandbox, capsys):
        """Tests that KeyboardInterrupt is handled gracefully."""
        paths = mock_sandbox
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]

        with patch("sys.argv", test_args), \
             patch("src.neutralize_delineations.run_llm_worker", side_effect=KeyboardInterrupt):
            neutralize_delineations.main()
        
        captured = capsys.readouterr()
        assert "Process interrupted by user" in captured.out

    def test_llm_malformed_response_is_handled(self, mock_sandbox, capsys):
        """Tests that a malformed LLM response is handled as a failure."""
        paths = mock_sandbox
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force", "--fast"]

        mock_worker = MockLLMWorker(malform_on_task="All Balances")
        with patch("sys.argv", test_args), \
             patch("src.neutralize_delineations.subprocess.run", side_effect=mock_worker.run):
            neutralize_delineations.main()

        captured = capsys.readouterr()
        assert "Failed:    1 tasks" in captured.out
        assert "Processed: 1 tasks" in captured.out

    def test_fast_mode_removes_existing_points_file(self, mock_sandbox):
        """Tests that --fast mode correctly deletes a pre-existing points file."""
        paths = mock_sandbox
        output_dir = paths["output_dir"]
        output_dir.mkdir()
        points_file = output_dir / "points_in_signs.csv"
        points_file.write_text("old content")
        
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--force", "--fast"]
        
        with patch("sys.argv", test_args), \
             patch("src.neutralize_delineations.subprocess.run", side_effect=MockLLMWorker().run):
            neutralize_delineations.main()
        
        assert "old content" not in points_file.read_text()
        assert "Sun in Aries" in points_file.read_text()

# === End of tests/data_preparation/test_neutralize_delineations.py ===
