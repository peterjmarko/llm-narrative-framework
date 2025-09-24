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
# Filename: tests/experiment_lifecycle/test_compile_experiment_results.py

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

    def test_main_handles_non_existent_directory(self):
        """Verify the script exits with code 1 for a non-existent directory."""
        non_existent_dir = self.exp_dir / "does_not_exist"
        test_argv = ['compile_exp_results.py', str(non_existent_dir)]
        
        # The script should log an error and call sys.exit(1)
        # We don't need to check the log content if the exit code is correct,
        # as that path is only taken if the error is logged.
        with patch.object(sys, 'argv', test_argv):
            compile_experiment_results.main()
                
        self.mock_sys_exit.assert_called_with(1)

    def test_main_handles_malformed_csv(self):
        """Verify a malformed (unparseable) CSV is skipped with an error."""
        # --- Arrange ---
        valid_file_path = self._create_replication_file(run_num=1, mrr_val=0.8)
        malformed_run_dir = self.exp_dir / "run_malformed"
        malformed_run_dir.mkdir()
        malformed_file_path = malformed_run_dir / "REPLICATION_results.csv"
        malformed_file_path.touch()

        test_argv = ['compile_exp_results.py', str(self.exp_dir)]
        
        # --- Act & Assert ---
        # We mock pd.read_csv to force an exception for the malformed file.
        original_read_csv = pd.read_csv
        def read_csv_side_effect(filepath, *args, **kwargs):
            if str(filepath) == str(malformed_file_path):
                raise Exception("Simulated parse error")
            return original_read_csv(filepath, *args, **kwargs)

        with patch('pandas.read_csv', side_effect=read_csv_side_effect), \
             self.assertLogs(level='ERROR') as cm:
            with patch.object(sys, 'argv', test_argv):
                compile_experiment_results.main()
            self.assertIn("Could not read or process", cm.output[0])
            
        # --- Assert ---
        # The script should still create a summary from the one valid file.
        output_csv = self.exp_dir / "EXPERIMENT_results.csv"
        self.assertTrue(output_csv.is_file())
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 1)

    def test_write_summary_csv_handles_missing_column(self):
        """Verify that a missing column specified in the header is added with NA."""
        # --- Arrange ---
        # Note: self.header_order is ['run_directory', 'replication', 'mean_mrr']
        # This test data is intentionally missing the 'mean_mrr' column.
        results_list = [{'run_directory': 'run_1', 'replication': 1}]
        output_path = self.exp_dir / "summary_with_missing_col.csv"
        
        # --- Act ---
        compile_experiment_results.write_summary_csv(output_path, results_list)
        
        # --- Assert ---
        self.assertTrue(output_path.is_file())
        df = pd.read_csv(output_path)
        self.assertEqual(len(df), 1)
        self.assertIn('mean_mrr', df.columns)
        self.assertTrue(pd.isna(df['mean_mrr'].iloc[0]))

    def test_write_summary_csv_exits_if_no_header_in_config(self):
        """Verify sys.exit is called if 'csv_header_order' is missing from config."""
        # --- Arrange ---
        # Temporarily override the mock to simulate a missing config value.
        with patch.object(compile_experiment_results, 'get_config_list', return_value=[]):
            with self.assertLogs(level='ERROR') as cm:
                compile_experiment_results.write_summary_csv("any_path.csv", [{'a': 1}])
                self.assertIn("'csv_header_order' not found in config.ini", cm.output[0])
        
        self.mock_sys_exit.assert_called_with(1)
        
    def test_write_summary_csv_handles_no_results(self):
        """Verify a warning is logged when writing an empty list of results."""
        # --- Arrange ---
        output_path = self.exp_dir / "empty_summary.csv"
        
        # --- Act ---
        with self.assertLogs(level='WARNING') as cm:
            compile_experiment_results.write_summary_csv(output_path, [])
            self.assertIn("No results to write", cm.output[0])
            
        # --- Assert ---
        self.assertFalse(output_path.exists()) # The file should not be created.

if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_compile_experiment_results.py ===
