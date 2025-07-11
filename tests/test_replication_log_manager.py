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
# Filename: tests/test_replication_replication_log_manager.py

# tests/test_replication_log_manager.py

from pathlib import Path
from unittest.mock import patch

import pytest

import src.replication_log_manager as replication_log_manager

# Sample data for tests
GOOD_REPORT_CONTENT = """
REPLICATION RUN REPORT (2023-01-01 12:05:00)
Date:               2023-01-01 12:00:00
Final Status:       COMPLETED
Run Directory:      /path/to/run_20230101_120000_rep-5
Parsing Status:     100 of 100 responses parsed successfully
Report File:        /path/to/run_20230101_120000_rep-5/replication_report_20230101-120500.txt
<<<METRICS_JSON_START>>>
{
    "mean_mrr": 0.85,
    "mean_top_1_acc": 0.80
}
<<<METRICS_JSON_END>>>
"""

FAILED_REPORT_CONTENT = """
REPLICATION RUN REPORT (2023-01-01 13:05:00)
Date:               2023-01-01 13:00:00
Final Status:       FAILED
Run Directory:      /path/to/run_20230101_130000_rep-6
Parsing Status:     0 of 100 responses parsed successfully
Report File:        /path/to/run_20230101_130000_rep-6/replication_report_20230101-130500.txt
<<<METRICS_JSON_START>>>
{}
<<<METRICS_JSON_END>>>
"""

MALFORMED_JSON_REPORT_CONTENT = """
Final Status:       COMPLETED
Run Directory:      /path/to/run_20230101_140000_rep-7
Report File:        /path/to/run_20230101_140000_rep-7/replication_report_20230101-140500.txt
<<<METRICS_JSON_START>>>
{ "mean_mrr": 0.75, }
<<<METRICS_JSON_END>>>
"""


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Creates a temporary directory structure for testing."""
    output_dir = tmp_path / "experiment_output"
    output_dir.mkdir()
    # rep-1 (good)
    run_01_dir = output_dir / "run_20230101_120000_rep-1"
    run_01_dir.mkdir()
    (run_01_dir / "replication_report_20230101-120500.txt").write_text(
        GOOD_REPORT_CONTENT.replace("-5", "-1")
    )
    # rep-2 (failed)
    run_02_dir = output_dir / "run_20230101_130000_rep-2"
    run_02_dir.mkdir()
    (run_02_dir / "replication_report_20230101-130500.txt").write_text(
        FAILED_REPORT_CONTENT.replace("-6", "-2")
    )
    return output_dir


class TestLogManagerHelpers:
    """Tests for helper functions like parsers and writers."""

    def test_parse_report_file_success(self, tmp_path):
        report_path = tmp_path / "report.txt"
        report_path.write_text(GOOD_REPORT_CONTENT)
        log_entry = replication_log_manager.parse_report_file(str(report_path))
        assert log_entry["ReplicationNum"] == "5"
        assert log_entry["Status"] == "COMPLETED"
        assert log_entry["MeanMRR"] == "0.8500"
        assert log_entry["MeanTop1Acc"] == "80.00%"
        assert log_entry["ErrorMessage"] == "N/A"

    def test_parse_report_file_failure(self, tmp_path):
        report_path = tmp_path / "report_failed.txt"
        report_path.write_text(FAILED_REPORT_CONTENT)
        log_entry = replication_log_manager.parse_report_file(str(report_path))
        assert log_entry["Status"] == "FAILED"
        assert log_entry["ErrorMessage"] == "See report"

    def test_parse_report_file_malformed_json(self, tmp_path):
        report_path = tmp_path / "report_malformed.txt"
        report_path.write_text(MALFORMED_JSON_REPORT_CONTENT)
        log_entry = replication_log_manager.parse_report_file(str(report_path))
        assert log_entry["Status"] == "COMPLETED"
        assert log_entry["MeanMRR"] == "N/A"

    def test_finalize_log_replaces_summary(self, tmp_path):
        log_path = tmp_path / "log_with_old_summary.csv"
        log_content = (
            "ReplicationNum,Status,StartTime,EndTime,Duration,MeanMRR\n"
            "1,COMPLETED,2023-01-01 10:00:00,2023-01-01 10:05:00,00:05:00,0.8\n"
            "\n"
            "BatchSummary,...\n"
            "Totals,old_data\n"
        )
        log_path.write_text(log_content)
        replication_log_manager.finalize_log(str(log_path))
        content = log_path.read_text()
        assert content.count("BatchSummary") == 1
        assert "Totals,2023-01-01 10:00:00,2023-01-01 10:05:00,00:05:00,1,0" in content


class TestLogManagerMain:
    """Tests for the main function and its command-line modes."""

    @patch("builtins.print")
    @patch("src.replication_log_manager.os.rename")
    @patch("src.replication_log_manager.os.path.exists", return_value=True)
    def test_main_start_archives_old_log(
        self, mock_exists, mock_rename, mock_print, temp_output_dir
    ):
        with patch("sys.argv", ["script", "start", str(temp_output_dir)]):
            replication_log_manager.main()
        mock_rename.assert_called_once()
        mock_print.assert_any_call("Initialized new batch run log with header.")

    def test_main_update(self, temp_output_dir):
        report_file = (
            temp_output_dir / "run_20230101_120000_rep-1" / "replication_report_20230101-120500.txt"
        )
        log_file = temp_output_dir / "batch_run_log.csv"
        with patch("sys.argv", ["script", "update", str(report_file)]):
            replication_log_manager.main()
        assert log_file.exists()
        assert "1,COMPLETED" in log_file.read_text()

    @patch("builtins.print")
    def test_main_rebuild(self, mock_print, temp_output_dir):
        # rep-0 is added to test sorting
        run_00_dir = temp_output_dir / "run_20230101_110000_rep-0"
        run_00_dir.mkdir()
        # Fix: The filename must match the glob pattern 'replication_report_*.txt'
        (run_00_dir / "replication_report_20230101-110500.txt").write_text(
            GOOD_REPORT_CONTENT.replace("-5", "-0")
        )
        with patch("sys.argv", ["script", "rebuild", str(temp_output_dir)]):
            replication_log_manager.main()
        log_file = temp_output_dir / "batch_run_log.csv"
        lines = log_file.read_text().replace("\r", "").strip().split("\n")
        assert len(lines) == 4  # Header + 3 reports
        assert lines[1].startswith("0,")  # Check sorting
        mock_print.assert_any_call("Successfully rebuilt batch_run_log.csv from 3 reports.")

    def test_main_finalize(self, temp_output_dir):
        log_file = temp_output_dir / "batch_run_log.csv"
        log_file.write_text(
            "ReplicationNum,Status,StartTime,EndTime,...\n"
            "1,COMPLETED,2023-01-01 10:00:00,2023-01-01 10:05:00,...\n"
        )
        with patch("sys.argv", ["script", "finalize", str(temp_output_dir)]):
            replication_log_manager.main()
        assert "BatchSummary" in log_file.read_text()

    def test_main_rebuild_no_reports(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with patch("sys.argv", ["script", "rebuild", str(empty_dir)]):
            with pytest.raises(SystemExit) as e:
                replication_log_manager.main()
        assert e.value.code == 0
        log_file = empty_dir / "batch_run_log.csv"
        assert log_file.exists()
        assert len(log_file.read_text().strip().splitlines()) == 1  # Header only

# === End of tests/test_replication_replication_log_manager.py ===
