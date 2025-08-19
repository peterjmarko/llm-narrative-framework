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
# Filename: tests/test_process_llm_responses.py

"""
Unit Tests for the LLM Response Parser (process_llm_responses.py).

This script validates the parsing and validation logic of the response processor,
ensuring it can handle various LLM output formats and correctly validate data.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import configparser
import types
from pathlib import Path
import importlib
import numpy as np

# Import the module to test
from src import process_llm_responses

class TestProcessLLMResponses(unittest.TestCase):
    """Test suite for process_llm_responses.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="proc_resp_test_")
        self.project_root = self.test_dir.name
        
        self.run_dir = Path(self.project_root) / "run_output"
        self.queries_dir = self.run_dir / "session_queries"
        self.responses_dir = self.run_dir / "session_responses"
        self.analysis_dir = self.run_dir / "analysis_inputs"
        
        self.queries_dir.mkdir(parents=True)
        self.responses_dir.mkdir(parents=True)

        # Mock config_loader
        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'General': {
                'queries_subdir': 'session_queries',
                'responses_subdir': 'session_responses',
                'analysis_inputs_subdir': 'analysis_inputs'
            },
            'Filenames': {
                'all_scores_for_analysis': 'all_scores.txt',
                'all_mappings_for_analysis': 'all_mappings.txt',
                'successful_indices_log': 'successful_indices.txt',
                'aggregated_mappings_in_queries_dir': 'mappings.txt'
            }
        })
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.project_root
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback=None, **kwargs):
            return config.get(section, key, fallback=fallback)
        fake_mod.get_config_value = dummy_get_config_value
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(process_llm_responses)
        
        self.sys_exit_patcher = patch('src.process_llm_responses.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()
        self.mock_sys_exit.side_effect = SystemExit

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.config_patcher.stop()
        self.sys_exit_patcher.stop()

    def _setup_common_files(self, k=2):
        """Helper to create common input files for a test run."""
        # Query file (for determining k and List A names)
        (self.queries_dir / "llm_query_001.txt").write_text(
            "LIST A\nPerson A (1900)\nPerson B (1910)\n\nLIST B\nDesc 1\nDesc 2"
        )
        # Ground truth manifest
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person A (1900)\tDesc_1\t1\n"
            "Person B (1910)\tDesc_2\t2\n"
        )
        # Ground truth master mappings file
        (self.queries_dir / "mappings.txt").write_text("Map_idx1\tMap_idx2\n1\t2\n")

    def test_happy_path_with_markdown(self):
        """Verify correct parsing of a clean, markdown-fenced response."""
        # --- Arrange ---
        self._setup_common_files(k=2)
        response_content = (
            "Here is the score table:\n"
            "```\n"
            "Name\tID 1\tID 2\n"
            "Person A (1900)\t0.9\t0.1\n"
            "Person B (1910)\t0.2\t0.8\n"
            "```\n"
            "Thank you."
        )
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        test_argv = ['process_llm_responses.py', '--run_output_dir', str(self.run_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        # --- Assert ---
        scores_file = self.analysis_dir / "all_scores.txt"
        self.assertTrue(scores_file.is_file())
        
        content = scores_file.read_text().strip()
        expected_content = "0.90\t0.10\n0.20\t0.80"
        self.assertEqual(content, expected_content)
        
        self.mock_sys_exit.assert_not_called()

    def test_happy_path_fallback_no_markdown(self):
        """Verify correct parsing of a response without a markdown fence."""
        # --- Arrange ---
        self._setup_common_files(k=2)
        response_content = (
            "Some introductory text from the LLM.\n"
            "I have completed the task. Here are the scores.\n"
            "Name\tID 1\tID 2\n"
            "Person A (1900)\t0.7\t0.3\n"
            "Person B (1910)\t0.4\t0.6\n"
        )
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        test_argv = ['process_llm_responses.py', '--run_output_dir', str(self.run_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        # --- Assert ---
        scores_file = self.analysis_dir / "all_scores.txt"
        self.assertTrue(scores_file.is_file())
        
        content = scores_file.read_text().strip()
        expected_content = "0.70\t0.30\n0.40\t0.60"
        self.assertEqual(content, expected_content)
        
        self.mock_sys_exit.assert_not_called()
        
    def test_parses_flexible_spacing(self):
        """Verify it correctly parses tables with mixed spaces and pipes."""
        self._setup_common_files()
        response_content = (
            "Name     | ID 1 | ID 2\n"
            "Person A (1900) | 0.9  | 0.1\n"
            "Person B (1910) | 0.2  | 0.8"
        )
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        content = (self.analysis_dir / "all_scores.txt").read_text().strip()
        self.assertEqual(content, "0.90\t0.10\n0.20\t0.80")
        self.mock_sys_exit.assert_not_called()

    def test_handles_reordered_columns(self):
        """Verify it correctly reorders columns based on header IDs."""
        self._setup_common_files()
        response_content = (
            "```\n"
            "Name\tID 2\tID 1\n"
            "Person A (1900)\t0.1\t0.9\n"
            "Person B (1910)\t0.8\t0.2\n"
            "```"
        )
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        content = (self.analysis_dir / "all_scores.txt").read_text().strip()
        # The output should be correctly ordered (ID 1, ID 2)
        self.assertEqual(content, "0.90\t0.10\n0.20\t0.80")
        self.mock_sys_exit.assert_not_called()

    def test_validation_fails_on_mapping_mismatch(self):
        """Verify script exits if a mapping mismatches its manifest."""
        self._setup_common_files()
        # Create a bad mapping file
        (self.queries_dir / "mappings.txt").write_text("Map_idx1\tMap_idx2\n9\t9\n")
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()

        self.mock_sys_exit.assert_called_with(1)
        # The filtered mappings file should only contain the header
        content = (self.analysis_dir / "all_mappings.txt").read_text().strip()
        self.assertEqual(content, "Map_idx1\tMap_idx2")

    def test_non_numeric_score_rejects_response(self):
        """Verify a response with non-numeric data is rejected."""
        self._setup_common_files()
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\tN/A\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        # The scores file should be empty as the only response was rejected
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertEqual((self.analysis_dir / "successful_indices.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_process_llm_responses.py ===
