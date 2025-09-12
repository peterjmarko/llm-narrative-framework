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
# Filename: tests/test_upgrade_legacy_experiment.py

"""
Unit Tests for the Legacy Experiment Upgrader.

This script validates the batch processing and error handling logic of
upgrade_legacy_experiment.py, ensuring it correctly calls its worker script.
"""

import unittest
from unittest.mock import patch, call
import sys
import tempfile
from pathlib import Path

# Import the module to test
from src import upgrade_legacy_experiment

class TestUpgradeLegacyExperiment(unittest.TestCase):
    """Test suite for upgrade_legacy_experiment.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="upgrader_test_")
        self.exp_dir = Path(self.test_dir.name)
        
        self.sys_exit_patcher = patch('src.upgrade_legacy_experiment.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()
        
        # We mock subprocess.run to isolate this script from its worker
        self.subprocess_patcher = patch('src.upgrade_legacy_experiment.subprocess.run')
        self.mock_subprocess_run = self.subprocess_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.subprocess_patcher.stop()

    def test_upgrade_legacy_experiment_happy_path(self):
        """Verify the script finds and processes all run directories."""
        # --- Arrange ---
        # Create mock run directories
        (self.exp_dir / "run_01").mkdir()
        (self.exp_dir / "run_02").mkdir()
        (self.exp_dir / "not_a_run_dir").mkdir() # Should be ignored

        # Configure the mock to simulate the worker script succeeding
        mock_result = unittest.mock.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        self.mock_subprocess_run.return_value = mock_result
        
        test_argv = ['upgrade_legacy_experiment.py', str(self.exp_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            upgrade_legacy_experiment.main()

        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        # Verify that the restore script was called for each run_* directory
        self.assertEqual(self.mock_subprocess_run.call_count, 2)
        
        # Check that the calls were made with the correct directory paths
        calls = self.mock_subprocess_run.call_args_list
        expected_paths = [str(self.exp_dir / "run_01"), str(self.exp_dir / "run_02")]
        
        # Extract the directory argument from each call's command list
        called_paths = [c.args[0][2] for c in calls]
        self.assertCountEqual(called_paths, expected_paths)

    def test_upgrade_halts_on_worker_failure(self):
        """Verify the script exits immediately if the worker script fails."""
        # --- Arrange ---
        (self.exp_dir / "run_01").mkdir()
        
        # Configure the mock to simulate the worker script failing
        mock_result = unittest.mock.Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""  # Ensure stdout is an iterable (string)
        mock_result.stderr = "Worker script failed"
        self.mock_subprocess_run.return_value = mock_result
        
        test_argv = ['upgrade_legacy_experiment.py', str(self.exp_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            upgrade_legacy_experiment.main()

        # --- Assert ---
        # The script should be called once, fail, and then exit.
        self.mock_subprocess_run.assert_called_once()
        self.mock_sys_exit.assert_called_with(1)


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_upgrade_legacy_experiment.py ===
