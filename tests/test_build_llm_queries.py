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
# Filename: tests/test_build_llm_queries.py

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
from pathlib import Path

# Import the script to test
from src import build_llm_queries

class TestBuildLLMQueries(unittest.TestCase):
    """Test suite for build_llm_queries.py."""

    def setUp(self):
        """Set up a temporary project structure and mock dependencies."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="build_queries_test_")
        self.project_root = self.test_dir.name
        self.run_output_dir = Path(self.project_root) / "run_123"
        self.run_output_dir.mkdir()

        # Mock config_loader
        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {'num_trials': '2', 'group_size': '3'},
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

    def test_happy_path_new_run(self):
        """Verify correct file generation and worker calls for a new run."""
        # --- Arrange ---
        # 1. Mock the return of the data loading helper function
        personalities_data = {
            'Index': range(1, 21), 'idADB': range(101, 121),
            'Name': [f'P_{i}' for i in range(1, 21)], 'BirthYear': ['1950'] * 20,
            'BirthYearInt': [1950] * 20, 'DescriptionText': [f'D_{i}' for i in range(1, 21)]
        }
        mock_df = pd.DataFrame(personalities_data)
        self.mock_load_df.return_value = (mock_df, "header_line")

        # 2. Mock the side effect of the query_generator.py worker script
        def subprocess_side_effect(command, **kwargs):
            script_dir = Path(build_llm_queries.__file__).parent
            prefix_index = command.index('--output_basename_prefix') + 1
            prefix = command[prefix_index]
            
            temp_qgen_dir = script_dir / Path(prefix).parent
            temp_qgen_dir.mkdir(exist_ok=True)
            
            # Simulate worker creating its output files
            (temp_qgen_dir / (Path(prefix).name + "mapping.txt")).write_text("Map_idx1\tMap_idx2\tMap_idx3\n1\t2\t3")
            (temp_qgen_dir / (Path(prefix).name + "manifest.txt")).touch()
            (temp_qgen_dir / (Path(prefix).name + "llm_query.txt")).touch()
            
            return MagicMock(returncode=0, stderr="")
        self.mock_subprocess.side_effect = subprocess_side_effect

        # 3. Mock sys.argv for the main function
        test_argv = ['build_llm_queries.py', '--run_output_dir', str(self.run_output_dir), '--qgen_base_seed', '123']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            build_llm_queries.main()

        # --- Assert ---
        queries_dir = self.run_output_dir / "session_queries"
        
        # Assert worker script was called twice (num_iterations=2 in mock_config)
        self.assertEqual(self.mock_subprocess.call_count, 2)
        
        # Assert seeds were passed and incremented correctly
        first_call_args = self.mock_subprocess.call_args_list[0].args[0]
        second_call_args = self.mock_subprocess.call_args_list[1].args[0]
        self.assertIn('--seed', first_call_args)
        seed1 = int(first_call_args[first_call_args.index('--seed') + 1])
        seed2 = int(second_call_args[second_call_args.index('--seed') + 1])
        self.assertEqual(seed1, 123)  # 123 + 1 - 1
        self.assertEqual(seed2, 124)  # 123 + 2 - 1
        
        # Assert all expected output files were created
        self.assertTrue((queries_dir / "mappings.txt").is_file())
        self.assertTrue((queries_dir / "used_indices.txt").is_file())
        self.assertTrue((queries_dir / "llm_query_001.txt").is_file())
        self.assertTrue((queries_dir / "llm_query_002.txt").is_file())
        
        # Assert content of aggregated mappings file is correct
        mappings_content = (queries_dir / "mappings.txt").read_text()
        lines = mappings_content.strip().split('\n')
        self.assertEqual(lines[0], "Map_idx1\tMap_idx2\tMap_idx3")
        self.assertEqual(len(lines), 3)

        # Assert correct indices were logged as used
        used_indices_content = (queries_dir / "used_indices.txt").read_text()
        used_indices = {int(i) for i in used_indices_content.strip().split('\n')}
        self.assertEqual(len(used_indices), 6) # 2 iterations * 3 subjects

    # @unittest.skip("Not yet implemented")
    # def test_continue_run_starts_from_correct_index(self):
    #     """Verify a continued run correctly identifies the next start index."""
    #     pass

    # @unittest.skip("Not yet implemented")
    # def test_insufficient_data_exits_gracefully(self):
    #     """Verify the script exits if not enough unique personalities are available."""
    #     pass

    # @unittest.skip("Not yet implemented")
    # def test_worker_failure_halts_execution(self):
    #     """Verify that a failure in the worker script stops the main loop."""
    #     pass

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_build_llm_queries.py ===
