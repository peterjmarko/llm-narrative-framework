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
# Filename: tests/test_compile_study_results.py

"""
Unit Tests for the Study-Level Results Compiler.

This script validates the recursive file discovery, data aggregation, and CSV
generation logic of compile_study_results.py in an isolated environment.
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
from src import compile_study_results

class TestCompileStudyResults(unittest.TestCase):
    """Test suite for compile_study_results.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="compile_study_test_")
        self.study_dir = Path(self.test_dir.name) / "My_Study"
        self.study_dir.mkdir()

        self.sys_exit_patcher = patch('src.compile_study_results.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

        # Mock the config_loader module
        self.header_order = ['run_directory', 'replication', 'mean_mrr']
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = configparser.ConfigParser()
        def dummy_get_config_list(config, section, key):
            return self.header_order
        fake_mod.get_config_list = dummy_get_config_list
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(compile_study_results)

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.config_patcher.stop()

    def _create_experiment_file(self, exp_path, data):
        """Helper to create a single experiment results file."""
        exp_path.mkdir(parents=True, exist_ok=True)
        csv_path = exp_path / "EXPERIMENT_results.csv"
        pd.DataFrame(data).to_csv(csv_path, index=False)

    def test_main_happy_path_aggregates_recursively(self):
        """Verify results from nested experiment dirs are correctly aggregated."""
        # --- Arrange ---
        exp1_path = self.study_dir / "exp1"
        exp2_path = self.study_dir / "nested" / "exp2"
        self._create_experiment_file(exp1_path, {'mean_mrr': [0.8, 0.85]})
        self._create_experiment_file(exp2_path, {'mean_mrr': [0.7, 0.75]})
        
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        output_csv = self.study_dir / "STUDY_results.csv"
        self.assertTrue(output_csv.is_file())
        
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 4)
        self.assertAlmostEqual(df['mean_mrr'].sum(), 3.1)

    def test_main_handles_empty_experiment_file(self):
        """Verify an empty experiment file is skipped with a warning."""
        # --- Arrange ---
        exp1_path = self.study_dir / "exp1"
        self._create_experiment_file(exp1_path, {'mean_mrr': [0.8]})
        
        empty_exp_path = self.study_dir / "exp2"
        empty_exp_path.mkdir()
        (empty_exp_path / "EXPERIMENT_results.csv").touch()
        
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        # --- Act ---
        with self.assertLogs(level='WARNING') as cm:
            with patch.object(sys, 'argv', test_argv):
                compile_study_results.main()
            self.assertIn("Skipping empty results file", cm.output[0])
            
        # --- Assert ---
        output_csv = self.study_dir / "STUDY_results.csv"
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 1)

    def test_main_exits_cleanly_if_no_files_found(self):
        """Verify the script exits with code 0 if no experiment files are found."""
        # --- Arrange ---
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(0)
        self.assertFalse((self.study_dir / "STUDY_results.csv").exists())

    def test_main_exits_with_error_if_no_valid_data(self):
        """Verify the script exits with code 1 if all found files are empty."""
        # --- Arrange ---
        empty_exp_path = self.study_dir / "exp1"
        empty_exp_path.mkdir()
        (empty_exp_path / "EXPERIMENT_results.csv").touch()
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_compile_study_results.py ===
