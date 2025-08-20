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
# Filename: tests/test_compile_replication_results.py

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

if __name__ == '__main__':
    unittest.main()
