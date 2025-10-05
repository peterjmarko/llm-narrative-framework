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
# Filename: tests/experiment_lifecycle/test_generate_replication_report.py

"""
Unit Tests for the Replication Report Generator.

This script validates the file I/O, data integration, and content formatting
logic of generate_replication_report.py in an isolated environment.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
import json
import configparser
from pathlib import Path
import datetime

# Import the module to test
from src import generate_replication_report

class TestGenerateReplicationReport(unittest.TestCase):
    """Test suite for generate_replication_report.py."""

    def setUp(self):
        """Set up a temporary directory and mock sys.exit for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="report_gen_test_")
        # Create a directory name that matches the expected format
        run_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = Path(self.test_dir.name) / f"run_{run_timestamp}"
        
        self.analysis_dir = self.run_dir / "analysis_inputs"
        self.queries_dir = self.run_dir / "session_queries"
        self.analysis_dir.mkdir(parents=True)
        self.queries_dir.mkdir(parents=True)
        
        self.sys_exit_patcher = patch('src.generate_replication_report.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()

    def _create_input_files(self):
        """Helper to create a standard set of valid input files."""
        # Create metrics JSON
        self.metrics_data = {"mean_mrr": 0.85, "mean_top_1_acc": 0.7}
        with open(self.analysis_dir / "replication_metrics.json", 'w') as f:
            json.dump(self.metrics_data, f)
            
        # Create archived config
        config = configparser.ConfigParser()
        config['Experiment'] = {'group_size': '10', 'num_trials': '100', 'mapping_strategy': 'correct'}
        config['Filenames'] = {'personalities_src': 'personalities_db.txt'}
        config['LLM'] = {'model_name': 'test-model/test-1.0'}
        with open(self.run_dir / "config.ini.archived", 'w') as f:
            config.write(f)
            
        # Create base query file
        (self.queries_dir / "llm_query_base.txt").write_text("This is the base query.")

    def test_main_happy_path_creates_report(self):
        """Verify a complete report is generated with all valid inputs."""
        # --- Arrange ---
        self._create_input_files()
        # Create a dummy old report to ensure it gets cleaned up
        (self.run_dir / "replication_report_old.txt").touch()
        
        test_argv = ['generate_report.py', '--run_output_dir', str(self.run_dir), '--replication_num', '1']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            generate_replication_report.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        
        # Check that old report was deleted
        self.assertFalse((self.run_dir / "replication_report_old.txt").exists())
        
        # Check that new report exists
        report_files = list(self.run_dir.glob("replication_report_*.txt"))
        self.assertEqual(len(report_files), 1)
        
        # Check content of the new report
        report_content = report_files[0].read_text()
        # The f-string formatting pads the label to 24 characters.
        # "LLM Model:" is 10 chars, so it requires 14 spaces for alignment.
        self.assertIn("LLM Model:              test-model/test-1.0", report_content)
        self.assertIn("This is the base query.", report_content)
        self.assertIn("1. Overall Ranking Performance (MRR)", report_content)
        self.assertIn("Mean: 0.8500, Wilcoxon p-value", report_content)
        self.assertIn(json.dumps(self.metrics_data, indent=4), report_content)

    def test_main_handles_missing_metrics_file(self):
        """Verify the script exits with an error if the metrics JSON is missing."""
        # --- Arrange ---
        self._create_input_files()
        (self.analysis_dir / "replication_metrics.json").unlink()
        test_argv = ['generate_report.py', '--run_output_dir', str(self.run_dir), '--replication_num', '1']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            generate_replication_report.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)

    def test_main_handles_malformed_json(self):
        """Verify the script exits with an error if the metrics JSON is corrupted."""
        # --- Arrange ---
        self._create_input_files()
        (self.analysis_dir / "replication_metrics.json").write_text("{'invalid': json,}")
        test_argv = ['generate_report.py', '--run_output_dir', str(self.run_dir), '--replication_num', '1']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            generate_replication_report.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)
        
    def test_main_handles_missing_base_query(self):
        """Verify the report is still generated with a fallback if the base query is missing."""
        # --- Arrange ---
        self._create_input_files()
        (self.queries_dir / "llm_query_base.txt").unlink()
        test_argv = ['generate_report.py', '--run_output_dir', str(self.run_dir), '--replication_num', '1']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            generate_replication_report.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        report_files = list(self.run_dir.glob("replication_report_*.txt"))
        self.assertEqual(len(report_files), 1)
        self.assertIn("--- BASE QUERY NOT FOUND ---", report_files[0].read_text())

if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_generate_replication_report.py ===
