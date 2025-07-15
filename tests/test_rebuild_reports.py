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
# Filename: tests/test_rebuild_reports.py

# tests/test_rebuild_reports.py
import configparser
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from src import rebuild_reports

# --- Sample Data and Mocks ---
MOCK_CONFIG_INI_ARCHIVED = """
[LLM]
model = mock-model/from-archive
[Study]
num_iterations = 100
k_per_query = 10
mapping_strategy = correct
[Filenames]
personalities_src = personalities_db_1-5000.txt
base_query_src = base_query.txt
"""

MOCK_PROCESS_OUTPUT = "<<<PARSER_SUMMARY:95:100:5>>>"
MOCK_ANALYZE_OUTPUT = """
<<<ANALYSIS_SUMMARY_START>>>
This is the mock analysis summary.
<<<METRICS_JSON_START>>>
{"mean_mrr": 0.9}
<<<METRICS_JSON_END>>>
"""
MOCK_ANALYZE_OUTPUT_VALIDATION = MOCK_ANALYZE_OUTPUT + "ANALYZER_VALIDATION_SUCCESS"
MOCK_PROCESS_OUTPUT_VALIDATION = MOCK_PROCESS_OUTPUT + "PROCESSOR_VALIDATION_SUCCESS"


@pytest.fixture
def temp_study_dir(tmp_path: Path) -> Path:
    """Creates a temporary study directory with a sample run folder."""
    study_dir = tmp_path / "study"
    run_dir = study_dir / "run_20230101_120000_rep-1"
    run_dir.mkdir(parents=True)
    # Create the archived config
    (run_dir / "config.ini.archived").write_text(MOCK_CONFIG_INI_ARCHIVED)
    # Create a dummy old report to be archived
    (run_dir / "replication_report_old.txt").touch()
    return study_dir


@patch("src.rebuild_reports.logging")
class TestRebuildReportWorker:
    """Tests the core rebuild_report_for_run function."""

    @patch("src.rebuild_reports.subprocess.run")
    def test_rebuild_success(self, mock_subprocess_run, mock_logging, temp_study_dir):
        """Test the successful, 'happy path' rebuild of a single report."""
        with patch("src.rebuild_reports.PROJECT_ROOT", temp_study_dir):
            run_dir = temp_study_dir / "run_20230101_120000_rep-1"
            # FIX: Create the parent 'data' directory, not the file itself.
            (temp_study_dir / "data").mkdir(parents=True, exist_ok=True)
            (temp_study_dir / "data" / "base_query.txt").write_text("Mock query")

            mock_subprocess_run.side_effect = [
                MagicMock(stdout=MOCK_PROCESS_OUTPUT_VALIDATION, stderr="", check_returncode=None),
                MagicMock(stdout=MOCK_ANALYZE_OUTPUT_VALIDATION, stderr="", check_returncode=None),
            ]
            compat_map = {
                "model_name": [("LLM", "model")],
                "num_trials": [("Study", "num_iterations")],
                "num_subjects": [("Study", "k_per_query")],
                "mapping_strategy": [("Study", "mapping_strategy")],
                "personalities_db_path": [("Filenames", "personalities_src")],
            }

            result = rebuild_reports.rebuild_report_for_run(str(run_dir), compat_map)

            assert result is True
            assert (run_dir / "replication_report_old.txt.corrupted").exists()
            new_reports = list(run_dir.glob("replication_report_*.txt"))
            assert len(new_reports) == 1
            new_report_content = new_reports[0].read_text()
            assert "REBUILT ON" in new_report_content
            assert "Validation Status: OK (All checks passed)" in new_report_content
            assert "Parsing Status:  95/100 responses parsed (5 warnings)" in new_report_content
            assert "This is the mock analysis summary." in new_report_content
            assert '"mean_mrr": 0.9' in new_report_content

    def test_rebuild_skips_no_archive(self, mock_logging, temp_study_dir):
        """Test that the function skips if config.ini.archived is missing."""
        with patch("src.rebuild_reports.PROJECT_ROOT", temp_study_dir):
            run_dir = temp_study_dir / "run_20230101_120000_rep-1"
            (run_dir / "config.ini.archived").unlink()

            result = rebuild_reports.rebuild_report_for_run(str(run_dir), {})
            assert result is False
            mock_logging.warning.assert_called_with(
                "Skipping: No 'config.ini.archived' found. Please run patcher first."
            )

    @patch("src.rebuild_reports.subprocess.run")
    def test_rebuild_subprocess_fails(self, mock_subprocess_run, mock_logging, temp_study_dir):
        """Test that a subprocess failure is handled and logged."""
        with patch("src.rebuild_reports.PROJECT_ROOT", temp_study_dir):
            run_dir = temp_study_dir / "run_20230101_120000_rep-1"
            # FIX: Use the imported subprocess module
            mock_subprocess_run.side_effect = subprocess.CalledProcessError(
                1, "cmd", "stdout", "stderr"
            )
            compat_map = {
                "model_name": [("LLM", "model")],
                "num_trials": [("Study", "num_iterations")],
                "num_subjects": [("Study", "k_per_query")],
                "mapping_strategy": [("Study", "mapping_strategy")],
                "personalities_db_path": [("Filenames", "personalities_src")],
            }
            result = rebuild_reports.rebuild_report_for_run(str(run_dir), compat_map)

            new_reports = list(run_dir.glob("replication_report_*.txt"))
            content = new_reports[0].read_text()
            assert "STAGE FAILED: Process LLM Responses" in content


class TestRebuildReportsMain:
    """Tests the main orchestration function."""

# Fix for tests/test_rebuild_reports.py in the test_main_success method

    @patch("glob.glob")
    @patch("os.path.isdir", return_value=True)
    @patch("src.config_loader.get_config_compatibility_map")
    @patch("src.rebuild_reports.rebuild_report_for_run")
    @patch("src.rebuild_reports.logging")
    def test_main_success(self, mock_logging, mock_worker, mock_map, mock_isdir, mock_glob, temp_study_dir):
        """Test main finds and processes directories."""
        # Arrange: Force glob to find one mock directory.
        mock_run_dir = str(temp_study_dir / "run_dir_1")
        mock_glob.return_value = [mock_run_dir]
        mock_worker.return_value = True
        
        # Determine the actual compatibility map that will be used
        expected_compat_map = {
            "model_name": [("Model", "model_name"), ("LLM", "model")],
            "num_trials": [("Study", "num_trials"), ("Study", "num_iterations")],
            "num_subjects": [("Study", "num_subjects"), ("Study", "k_per_query")],
            "mapping_strategy": [("Study", "mapping_strategy")],
            "personalities_db_path": [("General", "personalities_db_path"), ("Filenames", "personalities_src")]
        }
        mock_map.return_value = expected_compat_map

        # Act
        with patch("sys.argv", ["script", str(temp_study_dir)]):
            # Let the real tqdm be replaced with a simple iterable
            with patch("src.rebuild_reports.tqdm", lambda x, **kwargs: x):
                rebuild_reports.main()

        # Assert
        mock_worker.assert_called_once_with(mock_run_dir, expected_compat_map)
        mock_logging.info.assert_any_call(
            "\nReport rebuilding complete. Successfully processed 1/1 directories."
        )

    @patch("src.rebuild_reports.logging")
    def test_main_dir_not_found(self, mock_logging, tmp_path):
        """Test main exits if the base directory is not found."""
        non_existent_dir = tmp_path / "non_existent"
        with patch("sys.argv", ["script", str(non_existent_dir)]):
            with patch("sys.exit"):  # Mock exit to prevent actual exit
                rebuild_reports.main()
        mock_logging.error.assert_called_with(
            f"Error: Provided directory does not exist: {non_existent_dir}"
        )

    @patch("src.rebuild_reports.logging")
    def test_main_no_run_dirs_found(self, mock_logging, tmp_path):
        """Test main exits gracefully if no run directories are found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with patch("sys.argv", ["script", str(empty_dir)]):
            rebuild_reports.main()
        mock_logging.info.assert_any_call(
            f"No 'run_*' directories found in {empty_dir}."
        )

    @patch("glob.glob")
    @patch("os.path.isdir", return_value=True)
    @patch("src.config_loader.get_config_compatibility_map", return_value={})
    @patch("src.rebuild_reports.rebuild_report_for_run")
    @patch("src.rebuild_reports.logging")
    def test_main_keyboard_interrupt(self, mock_logging, mock_worker, mock_map, mock_isdir, mock_glob, temp_study_dir):
        """Test that KeyboardInterrupt is handled gracefully."""
        # Arrange
        mock_run_dir = str(temp_study_dir / "run_dir_1")
        mock_glob.return_value = [mock_run_dir]
        mock_worker.side_effect = KeyboardInterrupt
        
        # Act & Assert
        with patch("sys.argv", ["script", str(temp_study_dir)]):
            with pytest.raises(SystemExit) as excinfo:
                with patch("src.rebuild_reports.tqdm", lambda x, **kwargs: x):
                    rebuild_reports.main()

            assert excinfo.value.code == 1
            mock_logging.warning.assert_called_with(
                "Operation interrupted by user (Ctrl+C). Exiting gracefully."
            )

    @patch("src.rebuild_reports.tqdm")
    @patch("os.path.isdir", return_value=True)
    @patch("src.config_loader.get_config_compatibility_map", return_value={})
    @patch("src.rebuild_reports.rebuild_report_for_run")
    @patch("src.rebuild_reports.logging")
    def test_main_verbose_flag(self, mock_logging, mock_worker, mock_map, mock_isdir, mock_tqdm, temp_study_dir):
        """Test that --verbose flag disables tqdm and keeps INFO logging."""
        mock_worker.return_value = True
        
        # Case 1: --verbose is used
        with patch("sys.argv", ["script", str(temp_study_dir), "--verbose"]):
            rebuild_reports.main()

        # Assert tqdm was NOT used and logger level was NOT changed
        mock_tqdm.assert_not_called()
        
        # Reset mocks for Case 2
        mock_tqdm.reset_mock()
        mock_logging.reset_mock()
        mock_worker.reset_mock() # Also reset the worker

        # Case 2: --verbose is NOT used
        with patch("sys.argv", ["script", str(temp_study_dir)]):
             rebuild_reports.main()
        
        # Assert tqdm was used and logger was set to WARNING
        mock_tqdm.assert_called_once()
        # Be specific: Check that WARNING was set, then INFO was set later.
        log_level_calls = mock_logging.getLogger.return_value.setLevel.call_args_list
        assert call(mock_logging.WARNING) in log_level_calls
        assert call(mock_logging.INFO) in log_level_calls

# === End of tests/test_rebuild_reports.py ===