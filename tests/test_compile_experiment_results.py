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
# Filename: tests/test_compile_experiment_results.py

"""
Unit Tests for the Experiment-Level Results Compiler.

This script validates the file discovery, data aggregation, and CSV generation
logic of compile_experiment_results.py in an isolated environment.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
from pathlib import Path
import pandas as pd
import configparser
import types
import importlib

# Import the module to test
from src import compile_experiment_results

class TestCompileExperimentResults(unittest.TestCase):
    """Test suite for compile_experiment_results.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="compile_exp_test_")
        self.exp_dir = Path(self.test_dir.name) / "experiment_1"
        self.exp_dir.mkdir()

        self.sys_exit_patcher = patch('src.compile_experiment_results.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

        # Mock the config_loader module
        self.header_order = ['run_directory', 'replication', 'mean_mrr']
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = configparser.ConfigParser()
        fake_mod.PROJECT_ROOT = self.test_dir.name
        def dummy_get_config_list(config, section, key):
            return self.header_order
        fake_mod.get_config_list = dummy_get_config_list
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(compile_experiment_results)

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.config_patcher.stop()

    def _create_replication_file(self, run_num, mrr_val):
        """Helper to create a single replication results file."""
        run_dir = self.exp_dir / f"run_{run_num}"
        run_dir.mkdir()
        csv_path = run_dir / "REPLICATION_results.csv"
        data = {'run_directory': [f"run_{run_num}"], 'replication': [run_num], 'mean_mrr': [mrr_val]}
        pd.DataFrame(data).to_csv(csv_path, index=False)
        return csv_path

    def test_main_happy_path_aggregates_results(self):
        """Verify results from multiple replications are correctly aggregated."""
        # --- Arrange ---
        self._create_replication_file(run_num=1, mrr_val=0.8)
        self._create_replication_file(run_num=2, mrr_val=0.7)
        test_argv = ['compile_exp_results.py', str(self.exp_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_experiment_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        output_csv = self.exp_dir / "EXPERIMENT_results.csv"
        self.assertTrue(output_csv.is_file())
        
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 2)
        self.assertEqual(df['mean_mrr'].sum(), 1.5)
        self.assertListEqual(list(df.columns), self.header_order)

    def test_main_handles_empty_replication_file(self):
        """Verify an empty replication file is skipped with a warning."""
        # --- Arrange ---
        self._create_replication_file(run_num=1, mrr_val=0.8)
        empty_run_dir = self.exp_dir / "run_3"
        empty_run_dir.mkdir()
        (empty_run_dir / "REPLICATION_results.csv").touch()
        
        test_argv = ['compile_exp_results.py', str(self.exp_dir)]
        
        # --- Act ---
        with self.assertLogs(level='WARNING') as cm:
            with patch.object(sys, 'argv', test_argv):
                compile_experiment_results.main()
            self.assertIn("Skipping empty results file", cm.output[0])
            
        # --- Assert ---
        output_csv = self.exp_dir / "EXPERIMENT_results.csv"
        self.assertTrue(output_csv.is_file())
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 1) # Only the valid file was processed

    def test_main_exits_cleanly_if_no_files_found(self):
        """Verify the script exits with code 0 if no replication files are found."""
        # --- Arrange ---
        test_argv = ['compile_exp_results.py', str(self.exp_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_experiment_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(0)
        self.assertFalse((self.exp_dir / "EXPERIMENT_results.csv").exists())

    def test_main_exits_with_error_if_no_valid_data(self):
        """Verify the script exits with code 1 if all found files are empty."""
        # --- Arrange ---
        empty_run_dir = self.exp_dir / "run_1"
        empty_run_dir.mkdir()
        (empty_run_dir / "REPLICATION_results.csv").touch()
        test_argv = ['compile_exp_results.py', str(self.exp_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_experiment_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_compile_experiment_results.py ===
