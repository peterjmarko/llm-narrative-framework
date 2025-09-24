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
# Filename: tests/experiment_lifecycle/test_compile_study_results.py

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
import io
import logging

# Import the module to test
from src import compile_study_results


class TestWriteSummaryCSV(unittest.TestCase):
    """Directly tests the write_summary_csv helper function."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory()
        self.output_path = Path(self.test_dir.name) / "output.csv"
        self.sys_exit_patcher = patch('src.compile_study_results.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()

    def test_no_results_list(self):
        """Verify the function handles an empty results list gracefully."""
        with self.assertLogs(level='WARNING') as cm:
            compile_study_results.write_summary_csv(str(self.output_path), [])
            self.assertFalse(self.output_path.exists())
            self.assertIn("No results to write", cm.output[0])

    def test_missing_header_config_exits(self):
        """Verify the function exits if header config is missing."""
        self.mock_sys_exit.side_effect = SystemExit  # Make the mock raise an exception
        with patch('src.compile_study_results.get_config_list', return_value=None):
            with self.assertRaises(SystemExit):
                compile_study_results.write_summary_csv(str(self.output_path), [{'a': 1}])
            self.mock_sys_exit.assert_called_with(1)

    def test_adds_missing_columns_from_schema(self):
        """Verify that columns missing from data but present in schema are added."""
        results = [{'col_a': 1, 'col_b': 2}]
        header_order = ['col_a', 'col_b', 'col_c_missing']
        with patch('src.compile_study_results.get_config_list', return_value=header_order):
            compile_study_results.write_summary_csv(str(self.output_path), results)
        
        self.assertTrue(self.output_path.exists())
        df = pd.read_csv(self.output_path)
        self.assertEqual(list(df.columns), header_order)
        self.assertTrue(pd.isna(df['col_c_missing'].iloc[0]))


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
            # This mock must respect the config object it's given,
            # otherwise the override test will fail.
            if config.has_option(section, key):
                return [v.strip() for v in config.get(section, key).split(',')]
            return self.header_order
        fake_mod.get_config_list = dummy_get_config_list
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(compile_study_results)

        # Set up a manual log stream handler to robustly capture output
        # without conflicting with the script's basicConfig call.
        self.log_stream = io.StringIO()
        self.test_handler = logging.StreamHandler(self.log_stream)
        logging.getLogger().addHandler(self.test_handler)

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        logging.getLogger().removeHandler(self.test_handler)
        self.log_stream.close()
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
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with patch.object(sys, 'argv', test_argv):
                compile_study_results.main()
            self.assertIn("Study compilation complete.", mock_stdout.getvalue())
            
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
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
        
        # --- Assert ---
        log_content = self.log_stream.getvalue()
        self.assertIn("Skipping empty results file", log_content)
            
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

    def test_main_exits_if_directory_not_found(self):
        """Verify the script exits with code 1 if the study directory is invalid."""
        test_argv = ['compile_study_results.py', str(self.study_dir / "nonexistent")]
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
        self.mock_sys_exit.assert_called_with(1)

    def test_main_handles_corrupted_csv(self):
        """Verify a corrupted (unreadable) CSV is skipped with an error."""
        exp1_path = self.study_dir / "exp1"
        self._create_experiment_file(exp1_path, {'mean_mrr': [0.8]})

        corrupted_exp_path = self.study_dir / "exp2"
        corrupted_exp_path.mkdir()
        # Create a file that will definitely cause a pandas parsing error
        # Using unclosed quotes or severely malformed CSV structure
        (corrupted_exp_path / "EXPERIMENT_results.csv").write_text('header1,header2\n"unclosed quote,data2\ndata3,data4')

        test_argv = ['compile_study_results.py', str(self.study_dir)]

        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()

        log_content = self.log_stream.getvalue()
        self.assertIn("Could not read or process", log_content)

    def test_main_uses_config_path_override(self):
        """Verify the --config-path argument correctly overrides the default config."""
        # Create a temporary config file with a different header order
        temp_config = configparser.ConfigParser()
        override_header = ['mean_mrr', 'replication', 'run_directory'] # Reversed
        temp_config['Schema'] = {'csv_header_order': ','.join(override_header)}
        config_path = self.study_dir / "temp_config.ini"
        with open(config_path, 'w') as f:
            temp_config.write(f)

        self._create_experiment_file(self.study_dir / "exp1", {'mean_mrr': [0.8]})
        
        test_argv = ['compile_study_results.py', str(self.study_dir), '--config-path', str(config_path)]
        
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
            
        output_csv = self.study_dir / "STUDY_results.csv"
        df = pd.read_csv(output_csv)
        self.assertEqual(list(df.columns), override_header)

    def test_experiment_consistency_validation_warns_on_mismatches(self):
        """Verify validation function detects and warns about experiment inconsistencies."""
        # Create experiments with different column structures
        exp1_path = self.study_dir / "exp1"
        exp2_path = self.study_dir / "exp2"
        self._create_experiment_file(exp1_path, {'mean_mrr': [0.8], 'k': [2], 'm': [5]})
        self._create_experiment_file(exp2_path, {'mean_mrr': [0.7], 'k': [3], 'm': [5]})  # Different k
        
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
        
        log_content = self.log_stream.getvalue()
        self.assertIn("consistency issue(s)", log_content)
        self.assertIn("different k values", log_content)

    def test_compilation_metadata_generation(self):
        """Verify compilation metadata file is generated with correct information."""
        exp1_path = self.study_dir / "exp1"
        exp2_path = self.study_dir / "exp2"
        self._create_experiment_file(exp1_path, {'mean_mrr': [0.8, 0.82]})
        self._create_experiment_file(exp2_path, {'mean_mrr': [0.7]})
        
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
        
        metadata_file = self.study_dir / "STUDY_compilation_metadata.txt"
        self.assertTrue(metadata_file.exists())
        
        metadata_content = metadata_file.read_text()
        self.assertIn("Total Experiments: 2", metadata_content)
        self.assertIn("Total Replications: 3", metadata_content)
        self.assertIn("exp1 (2 replications)", metadata_content)
        self.assertIn("exp2 (1 replications)", metadata_content)

    def test_validation_handles_missing_columns_gracefully(self):
        """Verify validation handles experiments with completely different schemas."""
        exp1_path = self.study_dir / "exp1"
        exp2_path = self.study_dir / "exp2"
        self._create_experiment_file(exp1_path, {'mean_mrr': [0.8], 'model': ['test']})
        self._create_experiment_file(exp2_path, {'different_metric': [0.7], 'other_col': ['value']})
        
        test_argv = ['compile_study_results.py', str(self.study_dir)]
        
        with patch.object(sys, 'argv', test_argv):
            compile_study_results.main()
        
        log_content = self.log_stream.getvalue()
        self.assertIn("schema differences", log_content)
        self.assertIn("missing columns", log_content)
        self.assertIn("extra columns", log_content)


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_compile_study_results.py ===
