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
# Filename: tests/experiment_lifecycle/test_compile_replication_results.py

"""
Unit Tests for the Replication Results Compiler.

This script validates the file I/O, data merging, and CSV generation logic
of compile_replication_results.py in an isolated environment.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import tempfile
import json
import configparser
from pathlib import Path
import pandas as pd
import types

# Import the module to test
from src import compile_replication_results

class TestCompileReplicationResults(unittest.TestCase):
    """Test suite for compile_replication_results.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="compile_rep_test_")
        self.run_dir = Path(self.test_dir.name) / "run_20250101_120000_rep-1"
        self.analysis_dir = self.run_dir / "analysis_inputs"
        self.analysis_dir.mkdir(parents=True)

        self.sys_exit_patcher = patch('src.compile_replication_results.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

        # Mock the config_loader module
        self.mock_config = configparser.ConfigParser()
        # Define a more realistic header order that includes all generated fields
        self.header_order = [
            'run_directory', 'replication', 'model', 'mapping_strategy',
            'temperature', 'k', 'm', 'db', 'mean_mrr', 'top1_pred_bias_std'
        ]
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_list(config, section, key):
            return self.header_order
        fake_mod.get_config_list = dummy_get_config_list
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.config_patcher.stop()

    def _create_input_files(self):
        """Helper to create standard valid input files."""
        # Create metrics JSON with nested bias metrics
        metrics_data = {
            "mean_mrr": 0.75,
            "positional_bias_metrics": {"top1_pred_bias_std": 0.5}
        }
        with open(self.analysis_dir / "replication_metrics.json", 'w') as f:
            json.dump(metrics_data, f)
            
        # Create archived config with all expected fields
        config = configparser.ConfigParser()
        config['LLM'] = {'model_name': 'test-model/test-v1', 'temperature': '0.5'}
        config['Study'] = {
            'group_size': '10',
            'num_trials': '100',
            'mapping_strategy': 'correct'
        }
        config['Filenames'] = {'personalities_src': 'test_db.txt'}
        with open(self.run_dir / "config.ini.archived", 'w') as f:
            config.write(f)

    def test_main_happy_path_creates_summary_csv(self):
        """Verify a correct CSV is created from valid input files."""
        # --- Arrange ---
        self._create_input_files()
        test_argv = ['compile_results.py', str(self.run_dir)]
        
        # --- Act ---
        with patch('src.compile_replication_results.get_config_list', return_value=self.header_order):
            with patch.object(sys, 'argv', test_argv):
                compile_replication_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        output_csv = self.run_dir / "REPLICATION_results.csv"
        self.assertTrue(output_csv.is_file())
        
        df = pd.read_csv(output_csv)
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]['model'], 'test-model/test-v1')
        self.assertEqual(df.iloc[0]['k'], 10)
        self.assertEqual(df.iloc[0]['mean_mrr'], 0.75)
        self.assertEqual(df.iloc[0]['top1_pred_bias_std'], 0.5)
        self.assertEqual(df.iloc[0]['run_directory'], self.run_dir.name)
        # Verify columns are in the correct order defined by our mock
        self.assertListEqual(list(df.columns), self.header_order)

    def test_main_exits_if_metrics_file_missing(self):
        """Verify the script exits with an error if metrics.json is missing."""
        # --- Arrange ---
        self._create_input_files()
        (self.analysis_dir / "replication_metrics.json").unlink()
        test_argv = ['compile_results.py', str(self.run_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_replication_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)

    def test_main_exits_if_invalid_run_dir(self):
        """Verify the script exits with an error if the directory is not a valid run dir."""
        # --- Arrange ---
        invalid_dir = Path(self.test_dir.name) / "not_a_run_dir"
        invalid_dir.mkdir()
        test_argv = ['compile_results.py', str(invalid_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_replication_results.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)
        
    def test_flatten_bias_metrics(self):
        """Test the flattening of the nested bias metrics dictionary."""
        # Case 1: Nested dictionary exists
        data1 = {"a": 1, "positional_bias_metrics": {"b": 2, "c": 3}}
        flat1 = compile_replication_results._flatten_bias_metrics(data1)
        self.assertDictEqual(flat1, {"a": 1, "b": 2, "c": 3})
        
        # Case 2: Key does not exist
        data2 = {"a": 1, "d": 4}
        flat2 = compile_replication_results._flatten_bias_metrics(data2)
        self.assertDictEqual(flat2, {"a": 1, "d": 4})
        
        # Case 3: Key exists but is not a dictionary
        data3 = {"a": 1, "positional_bias_metrics": "not_a_dict"}
        flat3 = compile_replication_results._flatten_bias_metrics(data3)
        self.assertDictEqual(flat3, {"a": 1, "positional_bias_metrics": "not_a_dict"})

    def test_main_exits_if_metrics_file_is_malformed(self):
        """Verify script exits if replication_metrics.json is unparseable."""
        # --- Arrange ---
        self._create_input_files()
        # Overwrite with invalid JSON
        (self.analysis_dir / "replication_metrics.json").write_text("{'bad': json,}")
        test_argv = ['compile_results.py', str(self.run_dir)]
        
        # --- Act ---
        with self.assertLogs(level='ERROR') as cm:
            with patch.object(sys, 'argv', test_argv):
                compile_replication_results.main()
            self.assertIn("Could not read or parse replication_metrics.json", cm.output[0])
            
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(1)

    def test_parse_config_params_handles_missing_and_legacy_keys(self):
        """Verify config parser returns defaults for missing keys and finds legacy keys."""
        # --- Arrange ---
        config = configparser.ConfigParser()
        # Use legacy section and key names (e.g., [Model] instead of [LLM])
        config['Model'] = {'model': 'legacy-model/test-v1'}
        # Omit 'Study' section entirely to test defaults
        config_path = self.run_dir / "legacy_config.ini.archived"
        with open(config_path, 'w') as f:
            config.write(f)

        # --- Act ---
        params = compile_replication_results.parse_config_params(config_path)

        # --- Assert ---
        self.assertEqual(params['model'], 'legacy-model/test-v1') # Found legacy key
        self.assertEqual(params['mapping_strategy'], 'unknown_strategy') # Used default
        self.assertEqual(params['k'], 0) # Used default

    def test_parse_config_params_handles_malformed_config(self):
        """Verify config parser handles a completely malformed config file."""
        # --- Arrange ---
        config_path = self.run_dir / "malformed_config.ini.archived"
        config_path.write_text("this is not a valid ini file")

        # --- Act ---
        with self.assertLogs(level='WARNING') as cm:
            params = compile_replication_results.parse_config_params(config_path)
            self.assertIn("Could not fully parse config", cm.output[0])

        # --- Assert ---
        # Should return a dictionary of default values
        self.assertEqual(params['model'], 'unknown_model')

    def test_main_handles_run_dir_without_rep_number(self):
        """Verify replication number defaults to 0 if not in directory name."""
        # --- Arrange ---
        # Rename the run directory to remove the 'rep-1' part
        new_run_dir_name = "run_20250101_120000"
        new_run_dir = Path(self.test_dir.name) / new_run_dir_name
        self.run_dir.rename(new_run_dir)
        self.run_dir = new_run_dir # Update self for teardown
        self.analysis_dir = self.run_dir / "analysis_inputs" # Update analysis_dir path

        self._create_input_files()
        test_argv = ['compile_results.py', str(self.run_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            compile_replication_results.main()
        
        # --- Assert ---
        output_csv = self.run_dir / "REPLICATION_results.csv"
        self.assertTrue(output_csv.is_file())
        df = pd.read_csv(output_csv)
        self.assertEqual(df.iloc[0]['replication'], 0)

    def test_write_summary_csv_handles_no_results(self):
        """Verify a warning is logged when writing an empty list of results."""
        with self.assertLogs(level='WARNING') as cm:
            compile_replication_results.write_summary_csv("path.csv", [])
            self.assertIn("No results to write", cm.output[0])

    def test_write_summary_csv_returns_if_no_header_config(self):
        """Verify the function returns early if header config is missing."""
        with patch('src.compile_replication_results.get_config_list', return_value=[]), \
             self.assertLogs(level='ERROR') as cm:
            compile_replication_results.write_summary_csv("path.csv", [{'a': 1}])
            self.assertIn("'csv_header_order' not found", cm.output[0])
        # Assert that sys.exit was NOT called, as the function should return.
        self.mock_sys_exit.assert_not_called()

    def test_write_summary_csv_adds_missing_columns(self):
        """Verify that columns in header_order but not in data are added as NA."""
        # Arrange
        # self.header_order includes 'top1_pred_bias_std', which is missing from this data
        results_list = [{'run_directory': 'run_1', 'replication': 1, 'mean_mrr': 0.5}]
        output_path = self.run_dir / "summary_with_missing_col.csv"
        
        # Act
        compile_replication_results.write_summary_csv(output_path, results_list)
        
        # Assert
        self.assertTrue(output_path.is_file())
        df = pd.read_csv(output_path)
        self.assertIn('top1_pred_bias_std', df.columns)
        self.assertTrue(pd.isna(df['top1_pred_bias_std'].iloc[0]))


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_compile_replication_results.py ===
