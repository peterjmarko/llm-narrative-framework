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
# Filename: tests/experiment_workflow/test_build_llm_queries.py

"""
Unit Tests for the LLM Query Builder (build_llm_queries.py).

This script validates the orchestration logic of the query builder, ensuring it
correctly calls its worker script (`query_generator.py`) and manages file I/O.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import configparser
import types
import pandas as pd
import importlib
from pathlib import Path
import subprocess
import logging

# Import the script to test
from src import build_llm_queries


class TestHelperFunctions(unittest.TestCase):
    """Directly tests the helper functions within build_llm_queries.py."""

    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = Path(self.test_dir.name)

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('src.build_llm_queries.sys.exit')
    def test_load_all_personalities_df(self, mock_exit):
        """Tests the personality data loading and validation logic."""
        # Happy path
        good_data = "Index\tidADB\tName\tBirthYear\tDescriptionText\n1\t101\tTest\t1990\tDesc"
        good_path = self.test_path / "good.txt"
        good_path.write_text(good_data, encoding='utf-8')
        df, header = build_llm_queries.load_all_personalities_df(str(good_path))
        self.assertEqual(len(df), 1)
        self.assertIn("BirthYearInt", df.columns)
        self.assertEqual(header, "Index\tidADB\tName\tBirthYear\tDescriptionText")

        # Missing file should exit
        build_llm_queries.load_all_personalities_df("nonexistent.txt")
        mock_exit.assert_called_with(1)

        # Missing required columns should exit
        bad_data = "Index\tName\n1\tTest"
        bad_path = self.test_path / "bad.txt"
        bad_path.write_text(bad_data, encoding='utf-8')
        build_llm_queries.load_all_personalities_df(str(bad_path))
        mock_exit.assert_called_with(1)

        # No valid data after cleaning should exit
        no_valid_data = "Index\tidADB\tName\tBirthYear\tDescriptionText\n\t101\tTest\t1990\tDesc"
        no_valid_path = self.test_path / "novalid.txt"
        no_valid_path.write_text(no_valid_data, encoding='utf-8')
        build_llm_queries.load_all_personalities_df(str(no_valid_path))
        mock_exit.assert_called_with(1)

    def test_load_used_indices(self):
        """Tests loading of the used indices log, including error handling."""
        # Happy path
        indices_data = "1\n2\n3\n"
        indices_path = self.test_path / "indices.txt"
        indices_path.write_text(indices_data, encoding='utf-8')
        indices = build_llm_queries.load_used_indices(str(indices_path))
        self.assertEqual(indices, {1, 2, 3})

        # File with non-integer data should log a warning and continue
        bad_indices_data = "1\nfoo\n3"
        bad_indices_path = self.test_path / "bad_indices.txt"
        bad_indices_path.write_text(bad_indices_data, encoding='utf-8')
        with self.assertLogs(level='WARNING') as cm:
            indices = build_llm_queries.load_used_indices(str(bad_indices_path))
            self.assertEqual(indices, {1, 3})
            self.assertIn("Invalid index", cm.output[0])

    def test_get_next_start_index(self):
        """Tests the logic for finding the next available file index."""
        queries_dir = self.test_path / "queries"
        queries_dir.mkdir()
        # No files should start at 1
        self.assertEqual(build_llm_queries.get_next_start_index(str(queries_dir)), 1)
        # With existing files
        (queries_dir / "llm_query_001.txt").touch()
        (queries_dir / "llm_query_005.txt").touch()
        self.assertEqual(build_llm_queries.get_next_start_index(str(queries_dir)), 6)
        # With malformed files
        (queries_dir / "llm_query_abc.txt").touch()
        self.assertEqual(build_llm_queries.get_next_start_index(str(queries_dir)), 6)


class TestBuildLLMQueries(unittest.TestCase):
    """Test suite for build_llm_queries.py."""

    def setUp(self):
        """Set up a temporary project structure and mock dependencies."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="build_queries_test_")
        self.project_root = self.test_dir.name
        self.run_output_dir = Path(self.project_root) / "run_123"
        self.run_output_dir.mkdir()
        
        # Create a dummy data directory and base_query file for a complete test environment
        (Path(self.project_root) / "data").mkdir()
        (Path(self.project_root) / "data" / "base_query.txt").touch()

        # Mock config_loader
        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Experiment': {'num_trials': '2', 'group_size': '3'},
            'Filenames': {
                'personalities_src': 'personalities.txt', 'base_query_src': 'base_query.txt',
                'used_indices_log': 'used_indices.txt',
                'aggregated_mappings_in_queries_dir': 'mappings.txt'
            },
            'General': {'queries_subdir': 'session_queries'}
        })
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.project_root
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str, **kwargs):
            val = config.get(section, key, fallback=fallback)
            return value_type(val)
        fake_mod.get_config_value = dummy_get_config_value
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        
        # Reload the module under test AFTER the mocks are in place
        importlib.reload(build_llm_queries)

        # Mock subprocess to prevent real calls to query_generator.py
        self.subprocess_patcher = patch('src.build_llm_queries.subprocess.run')
        self.mock_subprocess = self.subprocess_patcher.start()

        # Mock file system interactions
        self.shutil_copy_patcher = patch('src.build_llm_queries.shutil.copy2')
        self.mock_shutil_copy = self.shutil_copy_patcher.start()

        self.load_df_patcher = patch('src.build_llm_queries.load_all_personalities_df')
        self.mock_load_df = self.load_df_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.config_patcher.stop()
        self.subprocess_patcher.stop()
        self.shutil_copy_patcher.stop()
        self.load_df_patcher.stop()

    def _setup_happy_path_mocks(self):
        """Configures mocks for a successful run."""
        personalities_data = {
            'Index': range(1, 21), 'idADB': range(101, 121),
            'Name': [f'P_{i}' for i in range(1, 21)], 'BirthYear': ['1950'] * 20,
            'BirthYearInt': [1950] * 20, 'DescriptionText': [f'D_{i}' for i in range(1, 21)]
        }
        mock_df = pd.DataFrame(personalities_data)
        self.mock_load_df.return_value = (mock_df, "header_line")

        def subprocess_side_effect(command, **kwargs):
            script_dir = Path(build_llm_queries.__file__).parent
            prefix_index = command.index('--output_basename_prefix') + 1
            prefix = command[prefix_index]
            
            temp_qgen_dir = script_dir / Path(prefix).parent
            temp_qgen_dir.mkdir(exist_ok=True, parents=True)
            
            # Simulate worker creating its output files
            (temp_qgen_dir / (Path(prefix).name + "mapping.txt")).write_text("Map_idx1\tMap_idx2\tMap_idx3\n1\t2\t3")
            (temp_qgen_dir / (Path(prefix).name + "manifest.txt")).touch()
            (temp_qgen_dir / (Path(prefix).name + "llm_query.txt")).touch()
            
            return MagicMock(returncode=0, stderr="")
        self.mock_subprocess.side_effect = subprocess_side_effect

    def test_happy_path_new_run(self):
        """Verify correct file generation and worker calls for a new run."""
        self._setup_happy_path_mocks()
        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir), '--qgen_base_seed', '123']
        
        with patch.object(sys, 'argv', test_argv):
            build_llm_queries.main()

        queries_dir = self.run_output_dir / "session_queries"
        self.assertEqual(self.mock_subprocess.call_count, 2)
        
        first_call_args = self.mock_subprocess.call_args_list[0].args[0]
        self.assertEqual(int(first_call_args[first_call_args.index('--seed') + 1]), 123)
        
        self.assertTrue((queries_dir / "mappings.txt").is_file())
        self.assertTrue((queries_dir / "used_indices.txt").is_file())
        
        mappings_content = (queries_dir / "mappings.txt").read_text()
        self.assertEqual(len(mappings_content.strip().split('\n')), 3)

    def test_continue_run_starts_from_correct_index(self):
        """Verify a continued run correctly identifies the next start index."""
        queries_dir = self.run_output_dir / "session_queries"
        queries_dir.mkdir()
        (queries_dir / "llm_query_005.txt").touch()

        self._setup_happy_path_mocks()
        
        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir)]
        
        with patch.object(sys, 'argv', test_argv):
            build_llm_queries.main()

        first_call_args = self.mock_subprocess.call_args_list[0].args[0]
        second_call_args = self.mock_subprocess.call_args_list[1].args[0]
        
        self.assertIn("iter_006_", first_call_args[first_call_args.index('--output_basename_prefix') + 1])
        self.assertIn("iter_007_", second_call_args[second_call_args.index('--output_basename_prefix') + 1])

    @patch('src.build_llm_queries.sys.exit')
    def test_insufficient_data_exits_gracefully(self, mock_exit):
        """Verify the script exits if not enough unique personalities are available."""
        mock_df = pd.DataFrame({
            'Index': range(1, 6), 'idADB': range(101, 106), 'Name': ['P1']*5,
            'BirthYearInt': [1950]*5, 'DescriptionText': ['D1']*5
        })
        self.mock_load_df.return_value = (mock_df, "header")
        mock_exit.side_effect = SystemExit  # Make the mock raise the exception

        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir)]

        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                build_llm_queries.main()
        self.mock_subprocess.assert_not_called()
        mock_exit.assert_called_with(1)

    @patch('src.build_llm_queries.sys.exit')
    def test_worker_failure_halts_execution(self, mock_exit):
        """Verify that a failure in the worker script stops the main loop."""
        self._setup_happy_path_mocks()
        self.mock_subprocess.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="Worker failed")
        mock_exit.side_effect = SystemExit  # Make the mock raise the exception

        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir)]

        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                build_llm_queries.main()
        self.mock_subprocess.assert_called_once()
        mock_exit.assert_called_with(1)

    @patch('src.build_llm_queries.sys.exit')
    def test_keyboard_interrupt_exits_gracefully(self, mock_exit):
        """Verify that a KeyboardInterrupt stops the loop and exits."""
        self._setup_happy_path_mocks()
        self.mock_subprocess.side_effect = KeyboardInterrupt
        mock_exit.side_effect = SystemExit  # Make the mock raise the exception

        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir)]

        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                build_llm_queries.main()
        self.mock_subprocess.assert_called_once()
        mock_exit.assert_called_with(1)

    def test_low_personality_pool_warning(self):
        """Verify a warning is logged when the pool of available personalities is low."""
        # Need 2*3=6 personalities. Pool of 7 is < 5 * 6.
        personalities_data = {
            'Index': range(1, 8), 'idADB': range(101, 108), 'Name': ['P1']*7,
            'BirthYearInt': [1950]*7, 'DescriptionText': ['D1']*7
        }
        self.mock_load_df.return_value = (pd.DataFrame(personalities_data), "header")
        self.mock_subprocess.side_effect = MagicMock(returncode=0)

        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir)]
        
        with self.assertLogs(level='WARNING') as cm:
            with patch.object(sys, 'argv', test_argv):
                build_llm_queries.main()
            self.assertTrue(any("Caution: The pool of 7 available personalities is getting low." in log for log in cm.output))

    def test_verbose_flags_are_passed_to_worker(self):
        """Verify that verbosity flags are correctly passed to the worker script."""
        self._setup_happy_path_mocks()
        
        # Test -v
        argv_v = ['script.py', '--run_output_dir', str(self.run_output_dir), '-v']
        with patch.object(sys, 'argv', argv_v):
            build_llm_queries.main()
        first_call_args = self.mock_subprocess.call_args_list[0].args[0]
        self.assertIn('-v', first_call_args)
        self.assertNotIn('-vv', first_call_args)

        # Test -vv
        self.mock_subprocess.reset_mock()
        argv_vv = ['script.py', '--run_output_dir', str(self.run_output_dir), '-vv']
        with patch.object(sys, 'argv', argv_vv):
            build_llm_queries.main()
        first_call_args_vv = self.mock_subprocess.call_args_list[0].args[0]
        self.assertIn('-vv', first_call_args_vv)


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_workflow/test_build_llm_queries.py ===
