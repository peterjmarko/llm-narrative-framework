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
# Filename: tests/test_manage_experiment_log.py

"""
Unit Tests for the Experiment Log Manager.

This script validates the file I/O, parsing, and CSV generation logic of
manage_experiment_log.py in an isolated environment with a mocked file system.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
from pathlib import Path
import csv

# Import the module to test
from src import manage_experiment_log

class TestManageExperimentLog(unittest.TestCase):
    """Test suite for manage_experiment_log.py."""

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="log_manager_test_")
        self.exp_dir = Path(self.test_dir.name)
        
        self.sys_exit_patcher = patch('src.manage_experiment_log.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()

    def _create_mock_report(self, rep_num, status="COMPLETED"):
        """Helper to create a mock replication report file."""
        run_name = f"run_20250101_120000_rep-{rep_num:03d}_model-name"
        run_dir = self.exp_dir / run_name
        run_dir.mkdir(exist_ok=True)
        
        report_content = f"""
Run Directory: {run_dir.as_posix()}
Final Status: {status}
Parsing Status: 10/10 OK
<<<METRICS_JSON_START>>>
{{
    "mean_mrr": 0.85,
    "mean_top_1_acc": 0.80
}}
<<<METRICS_JSON_END>>>
"""
        report_filename = f"replication_report_20250101-120100.txt"
        (run_dir / report_filename).write_text(report_content)

    def test_rebuild_command_creates_correct_log(self):
        """Verify the 'rebuild' command correctly parses reports and generates the CSV."""
        # --- Arrange ---
        self._create_mock_report(rep_num=1, status="COMPLETED")
        self._create_mock_report(rep_num=2, status="FAILED")
        
        test_argv = ['manage_experiment_log.py', 'rebuild', str(self.exp_dir)]
        log_path = self.exp_dir / "experiment_log.csv"

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            manage_experiment_log.main()

        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        self.assertTrue(log_path.exists(), "experiment_log.csv should be created.")

        with open(log_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2, "Log should contain two data rows.")
            
            # Check content of the first row (COMPLETED run)
            self.assertEqual(rows[0]['ReplicationNum'], '001')
            self.assertEqual(rows[0]['Status'], 'COMPLETED')
            self.assertEqual(rows[0]['MeanMRR'], '0.8500')
            self.assertEqual(rows[0]['MeanTop1Acc'], '80.00%')
            self.assertEqual(rows[0]['ErrorMessage'], 'N/A')

            # Check content of the second row (FAILED run)
            self.assertEqual(rows[1]['ReplicationNum'], '002')
            self.assertEqual(rows[1]['Status'], 'FAILED')
            self.assertEqual(rows[1]['ErrorMessage'], 'See report')

    def test_finalize_command_appends_summary(self):
        """Verify the 'finalize' command correctly adds a summary to a log file."""
        # --- Arrange ---
        log_path = self.exp_dir / "experiment_log.csv"
        log_content = """ReplicationNum,Status,StartTime,EndTime,Duration,ParsingStatus,MeanMRR,MeanTop1Acc,RunDirectory,ErrorMessage
001,COMPLETED,2025-01-01 12:00:00,2025-01-01 12:05:00,00:05:00,OK,0.8,80.00%,run_1,N/A
002,FAILED,2025-01-01 12:05:00,2025-01-01 12:10:00,00:05:00,OK,0.1,10.00%,run_2,See report
"""
        log_path.write_text(log_content)
        test_argv = ['manage_experiment_log.py', 'finalize', str(self.exp_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            manage_experiment_log.main()

        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        final_content = log_path.read_text()
        self.assertIn("BatchSummary,StartTime,EndTime,TotalDuration,Completed,Failed", final_content)
        self.assertIn("Totals,2025-01-01 12:00:00,2025-01-01 12:10:00,00:10:00,1,1", final_content)

    def test_finalize_idempotency(self):
        """Verify running 'finalize' multiple times doesn't create duplicate summaries."""
        # --- Arrange ---
        log_path = self.exp_dir / "experiment_log.csv"
        # Start with an already-finalized log
        log_content = """ReplicationNum,Status,StartTime,EndTime,Duration,ParsingStatus,MeanMRR,MeanTop1Acc,RunDirectory,ErrorMessage
001,COMPLETED,2025-01-01 12:00:00,2025-01-01 12:05:00,00:05:00,OK,0.8,80.00%,run_1,N/A

BatchSummary,StartTime,EndTime,TotalDuration,Completed,Failed
Totals,2025-01-01 12:00:00,2025-01-01 12:05:00,00:05:00,1,0
"""
        log_path.write_text(log_content)
        test_argv = ['manage_experiment_log.py', 'finalize', str(self.exp_dir)]

        # --- Act ---
        # Run finalize on the already-finalized log
        with patch.object(sys, 'argv', test_argv):
            manage_experiment_log.main()

        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        final_content = log_path.read_text()
        # Count occurrences of the summary header to ensure it's not duplicated
        summary_header_count = final_content.count("BatchSummary")
        self.assertEqual(summary_header_count, 1, "Finalize should be idempotent and not add duplicate summaries.")

    def test_start_command_creates_fresh_log(self):
        """Verify the 'start' command creates a new log with only a header."""
        # --- Arrange ---
        log_path = self.exp_dir / "experiment_log.csv"
        # Create a pre-existing log to ensure it gets overwritten
        log_path.write_text("old_content")
        
        test_argv = ['manage_experiment_log.py', 'start', str(self.exp_dir)]
        expected_header = "ReplicationNum,Status,StartTime,EndTime,Duration,ParsingStatus,MeanMRR,MeanTop1Acc,RunDirectory,ErrorMessage\n"

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            manage_experiment_log.main()

        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        self.assertTrue(log_path.exists())
        
        content = log_path.read_text()
        self.assertEqual(content, expected_header)


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_manage_experiment_log.py ===
