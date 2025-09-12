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
# Filename: tests/test_restore_experiment_config.py

"""
Unit Tests for the Experiment Configuration Restore Utility.

This script validates the report parsing and config generation logic of
restore_experiment_config.py in an isolated environment.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
from pathlib import Path
import configparser

# Import the module to test
from src import restore_experiment_config

class TestRestoreExperimentConfiguration(unittest.TestCase):
    """Test suite for restore_experiment_config.py."""

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="restore_config_test_")
        self.run_dir = Path(self.test_dir.name)
        
        self.sys_exit_patcher = patch('src.restore_experiment_config.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()

    def _create_mock_report(self, run_dir, params):
        """Helper to create a mock replication report file."""
        report_content = f"""
REPLICATION RUN REPORT
========================================
Run Directory:              {run_dir.as_posix()}_sbj-{params['group_size']}_trl-{params['num_trials']}_tmp-{params['temperature']}
Model Name:                 {params['model_name']}
Mapping Strategy:           {params['mapping_strategy']}
Personalities DB:           {params['personalities_src']}
"""
        report_filename = "replication_report_20240101-120100.txt"
        (run_dir / report_filename).write_text(report_content)

    def test_restore_config_happy_path(self):
        """Verify the script correctly creates config.ini.archived from a report."""
        # --- Arrange ---
        mock_params = {
            'model_name': 'google/gemini-1.0',
            'temperature': '0.7',
            'mapping_strategy': 'random',
            'group_size': '12',
            'num_trials': '50',
            'personalities_src': 'data/legacy_db.txt'
        }
        self._create_mock_report(self.run_dir, mock_params)
        test_argv = ['restore_experiment_config.py', str(self.run_dir)]
        config_path = self.run_dir / "config.ini.archived"

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            restore_experiment_config.main()

        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        self.assertTrue(config_path.exists(), "config.ini.archived should be created.")

        # Verify the content of the created config file
        parser = configparser.ConfigParser()
        parser.read(config_path)
        
        self.assertEqual(parser.get('LLM', 'model_name'), mock_params['model_name'])
        self.assertEqual(parser.get('LLM', 'temperature'), mock_params['temperature'])
        self.assertEqual(parser.get('Study', 'mapping_strategy'), mock_params['mapping_strategy'])
        self.assertEqual(parser.get('Study', 'group_size'), mock_params['group_size'])
        self.assertEqual(parser.get('Study', 'num_trials'), mock_params['num_trials'])
        self.assertEqual(parser.get('Filenames', 'personalities_src'), mock_params['personalities_src'])

    def test_main_exits_if_directory_not_found(self):
        """Verify the script exits if the target directory does not exist."""
        # --- Arrange ---
        non_existent_dir = self.run_dir / "non_existent"
        test_argv = ['restore_experiment_config.py', str(non_existent_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            restore_experiment_config.main()

        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)

    def test_main_exits_if_no_report_found(self):
        """Verify the script exits if no report file is found in the directory."""
        # --- Arrange ---
        # The run_dir exists but is empty
        test_argv = ['restore_experiment_config.py', str(self.run_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            restore_experiment_config.main()

        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_restore_experiment_config.py ===
