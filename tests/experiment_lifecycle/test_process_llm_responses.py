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
# Filename: tests/experiment_lifecycle/test_process_llm_responses.py

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
import io
import builtins
import re

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

    def _setup_common_files_k1(self):
        """Helper to create common input files for a k=1 test run."""
        (self.queries_dir / "llm_query_001.txt").write_text(
            "LIST A\nPerson A (1900)\n\nLIST B\nDesc 1"
        )
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person A (1900)\tDesc_1\t1\n"
        )
        (self.queries_dir / "mappings.txt").write_text("Map_idx1\n1\n")

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

    def test_handles_rank_based_output(self):
        """Verify --llm_output_ranks correctly converts ranks to scores."""
        self._setup_common_files(k=2)
        # Ranks: 1 is best, 2 is worst
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t1\t2\nPerson B (1910)\t2\t1\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir), '--llm_output_ranks']
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        content = (self.analysis_dir / "all_scores.txt").read_text().strip()
        # For k=2, Rank 1 -> (2-1)/(2-1) = 1.0. Rank 2 -> (2-2)/(2-1) = 0.0.
        self.assertEqual(content, "1.00\t0.00\n0.00\t1.00")
        self.mock_sys_exit.assert_not_called()

    def test_score_out_of_range_rejects_response(self):
        """Verify scores outside [0, 1] reject the response."""
        self._setup_common_files()
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t1.5\t-0.2\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        # The scores file should be empty as the response is rejected
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertEqual((self.analysis_dir / "successful_indices.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    def test_incomplete_matrix_rejects_response(self):
        """Verify a response with fewer than k data rows is rejected."""
        self._setup_common_files(k=2)
        # Only one data row for a k=2 query
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertEqual((self.analysis_dir / "successful_indices.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    def test_empty_response_file_is_skipped(self):
        """Verify that an empty response file is handled and skipped."""
        self._setup_common_files(k=2)
        # Create an empty response file
        (self.responses_dir / "llm_response_001.txt").touch()
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertEqual((self.analysis_dir / "successful_indices.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    def test_file_content_validation_failure_exits(self):
        """Verify that a failure in all_scores.txt validation causes sys.exit(1)."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)

        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        
        # Patch the validation function to simulate a failure
        with patch('src.process_llm_responses.validate_all_scores_file_content', return_value=False):
            with self.assertRaises(SystemExit):
                with patch.object(sys, 'argv', test_argv):
                    process_llm_responses.main()
        
        self.mock_sys_exit.assert_called_with(1)

    def test_validation_fails_if_manifest_is_missing(self):
        """Verify script exits if a manifest file is missing."""
        self._setup_common_files()
        # The response is fine
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        # But the manifest is missing
        (self.queries_dir / "llm_query_001_manifest.txt").unlink()
        
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()

        self.mock_sys_exit.assert_called_with(1)
        # The filtered mappings file should only contain the header because validation failed for the only entry.
        content = (self.analysis_dir / "all_mappings.txt").read_text().strip()
        self.assertEqual(content, "Map_idx1\tMap_idx2")

    def test_cleans_up_existing_analysis_dir(self):
        """Verify that an existing analysis directory is removed before processing."""
        self._setup_common_files()
        # Create the analysis dir and a dummy file inside
        self.analysis_dir.mkdir(exist_ok=True)
        (self.analysis_dir / "stale_file.txt").write_text("old data")
        
        # A valid response to trigger a full run
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")

        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()

        # Assert the stale file is gone, but the new output files exist
        self.assertFalse((self.analysis_dir / "stale_file.txt").exists())
        self.assertTrue((self.analysis_dir / "all_scores.txt").exists())

    def test_parses_split_id_header(self):
        """Verify it correctly parses headers where 'ID' and number are separate tokens."""
        self._setup_common_files()
        response_content = (
            "Name | ID | 1 | ID | 2\n"
            "Person A (1900) | 0.9 | 0.1\n"
            "Person B (1910) | 0.2 | 0.8"
        )
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        content = (self.analysis_dir / "all_scores.txt").read_text().strip()
        self.assertEqual(content, "0.90\t0.10\n0.20\t0.80")
        self.mock_sys_exit.assert_not_called()

    def test_handles_no_response_files(self):
        """Verify the script exits gracefully when no response files are found."""
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()

        self.mock_sys_exit.assert_called_with(0)
        self.assertTrue(self.analysis_dir.is_dir())
        # The script exits before writing any analysis files
        self.assertEqual(len(list(self.analysis_dir.iterdir())), 0)

    def test_validation_fails_on_empty_manifest(self):
        """Verify script exits if a manifest file has only a header."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
        )
        
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()

        self.mock_sys_exit.assert_called_with(1)
        content = (self.analysis_dir / "all_mappings.txt").read_text().strip()
        self.assertEqual(content, "Map_idx1\tMap_idx2")

    def test_quiet_mode_suppresses_info_logs(self):
        """Verify --quiet flag suppresses INFO and DEBUG level logs."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text(
            "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```"
        )
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir), '--quiet']
        
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()
            
            output = mock_stdout.getvalue()
            self.assertNotIn(" - INFO - ", output)
            self.assertIn("PROCESSOR_VALIDATION_SUCCESS", output)
            self.assertIn("<<<PARSER_SUMMARY", output)
    
    def test_skips_file_if_k_is_not_determinable(self):
        """Verify a response is skipped if its query file is malformed."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        (self.queries_dir / "llm_query_001.txt").write_text("This is not a valid query format.")

        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()

        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertEqual((self.analysis_dir / "successful_indices.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    def test_normalize_text_for_llm_handles_non_string(self):
        """Verify normalize_text_for_llm returns string representation for non-strings."""
        result = process_llm_responses.normalize_text_for_llm(123)
        self.assertEqual(result, "123")
        result = process_llm_responses.normalize_text_for_llm(None)
        self.assertEqual(result, "None")

    def test_exits_if_source_mappings_file_is_missing(self):
        """Verify script exits if source mappings.txt is not found."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        (self.queries_dir / "mappings.txt").unlink()

        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()
        
        self.mock_sys_exit.assert_called_with(1)

    def test_rejects_response_with_incomplete_header(self):
        """Verify a response is rejected if the header has fewer than k ID columns."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID 1\nPerson A (1900)\t0.9\nPerson B (1910)\t0.2\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertEqual((self.analysis_dir / "successful_indices.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    def test_validate_all_scores_file_content_handles_corrupt_data(self):
        """Verify the content validator correctly identifies malformed float data."""
        k = 2
        expected_matrix = np.array([[0.9, 0.1], [0.2, 0.8]])
        expected_map = {1: expected_matrix}
        
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        corrupt_file_path = self.analysis_dir / "corrupt_scores.txt"
        corrupt_file_path.write_text("0.9\tnot-a-number\n0.2\t0.8")

        result = process_llm_responses.validate_all_scores_file_content(
            str(corrupt_file_path), expected_map, k
        )
        self.assertFalse(result)

    def test_exits_on_io_error_writing_scores(self):
        """Verify script exits with 1 on IOError when writing all_scores.txt."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]

        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            if 'all_scores.txt' in str(file):
                raise IOError("Permission denied")
            return original_open(file, *args, **kwargs)

        with self.assertRaises(SystemExit):
            with patch('builtins.open', mock_open):
                with patch.object(sys, 'argv', test_argv):
                    process_llm_responses.main()
        
        self.mock_sys_exit.assert_called_with(1)

    def test_handles_empty_mappings_file(self):
        """Verify script exits if source mappings.txt is empty."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        (self.queries_dir / "mappings.txt").write_text("")

        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()
        
        self.mock_sys_exit.assert_called_with(1)

    def test_rejects_response_with_malformed_header_id(self):
        """Verify a response is rejected if header contains e.g., 'ID A'."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID 1\tID A\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    def test_rejects_row_with_too_few_score_columns(self):
        """Verify response is rejected if a row has fewer than k score columns."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    @patch('src.process_llm_responses.logging.error')
    def test_handles_io_error_writing_indices_file(self, mock_logging_error):
        """Verify script logs an error but completes on IOError for successful_indices.txt."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        indices_filepath = self.analysis_dir / "successful_indices.txt"

        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            if 'successful_indices.txt' in str(file):
                raise IOError("Disk full")
            return original_open(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()
        
        self.mock_sys_exit.assert_not_called()
        mock_logging_error.assert_called_with(f"Error writing successful indices file to {indices_filepath}: Disk full")

    def test_debug_log_level_is_set(self):
        """Verify -vv sets the log level to DEBUG."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir), '-vv']
        
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()
            
            output = mock_stdout.getvalue()
            self.assertIn(" - DEBUG - ", output)
            self.assertIn("Found table in markdown code block.", output)

    def test_handles_rank_based_output_for_k1(self):
        """Verify rank conversion works for k=1."""
        self._setup_common_files_k1()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\nPerson A (1900)\t1\n```")
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir), '--llm_output_ranks']
        with patch.object(sys, 'argv', test_argv):
            process_llm_responses.main()
            
        content = (self.analysis_dir / "all_scores.txt").read_text().strip()
        self.assertEqual(content, "1.00")

    def test_validation_fails_on_malformed_manifest(self):
        """Verify script exits if a manifest line has too few columns."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        (self.queries_dir / "llm_query_001_manifest.txt").write_text("Header\nJust one column\n")

        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()
        self.mock_sys_exit.assert_called_with(1)

    def test_skips_file_if_k_is_zero(self):
        """Verify a response is skipped if its query has no List A items."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("valid response")
        (self.queries_dir / "llm_query_001.txt").write_text("LIST A\n\nLIST B\nDesc 1\n")

        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    def test_skips_response_file_with_invalid_name(self):
        """Verify a response file is skipped if its name doesn't contain an index."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_noname.txt").write_text("valid response")
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    def test_info_log_level_is_set(self):
        """Verify -v or default sets log level to INFO."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\n```")
        
        for flag in [['-v'], []]:
            test_argv = ['script.py', '--run_output_dir', str(self.run_dir)] + flag
            with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
                with patch.object(sys, 'argv', test_argv):
                    process_llm_responses.main()
                output = mock_stdout.getvalue()
                self.assertIn(" - INFO - ", output)
                self.assertNotIn(" - DEBUG - ", output)

    def test_validator_fails_on_shape_mismatch(self):
        """Verify content validator fails if matrix shape differs from k."""
        self.analysis_dir.mkdir(exist_ok=True)
        scores_file = self.analysis_dir / "scores.txt"
        scores_file.write_text("0.9\t0.1\n0.2\t0.8")
        
        expected_map = {1: np.array([[0.9, 0.1], [0.2, 0.8]])}
        # Mismatch k value
        result = process_llm_responses.validate_all_scores_file_content(str(scores_file), expected_map, k_value=3)
        self.assertFalse(result)
        
    def test_writes_empty_file_when_all_responses_rejected(self):
        """Verify an empty scores file is created if all responses are rejected."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("non-numeric response")
        
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()
            output = mock_stdout.getvalue()
            self.assertIn("No score matrices were successfully parsed", output)
        
        scores_content = (self.analysis_dir / "all_scores.txt").read_text()
        self.assertEqual(scores_content, "")

    def test_validator_fails_on_content_mismatch(self):
        """Verify content validator fails if matrix data differs."""
        self.analysis_dir.mkdir(exist_ok=True)
        scores_file = self.analysis_dir / "scores.txt"
        scores_file.write_text("0.9\t0.1\n0.2\t0.7")  # Correct is 0.8
        
        expected_map = {1: np.array([[0.9, 0.1], [0.2, 0.8]])}
        result = process_llm_responses.validate_all_scores_file_content(str(scores_file), expected_map, k_value=2)
        self.assertFalse(result)

    def test_validator_handles_generic_exception(self):
        """Verify content validator handles a generic exception during file read."""
        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            raise Exception("Test exception")
        
        with patch('builtins.open', mock_open):
            result = process_llm_responses.validate_all_scores_file_content("dummy_path", {1: np.array([])}, k_value=1)
            self.assertFalse(result)

    def test_fallback_parser_with_too_few_lines(self):
        """Verify fallback parser handles responses with fewer than k+1 lines."""
        self._setup_common_files(k=2)
        # No markdown, and only 2 lines total (less than k+1=3)
        response_content = "Name\tID 1\tID 2\nPerson A (1900)\t0.7\t0.3\n"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        # The response is incomplete and should be rejected.
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    @patch('src.process_llm_responses.logging.error')
    def test_handles_generic_exception_reading_query(self, mock_logging_error):
        """Verify script skips a response if its query file causes a generic error."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("valid response")

        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            if 'llm_query_001.txt' in str(file):
                raise Exception("Cannot read query")
            return original_open(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertTrue(any("Cannot read query" in call[0][0] for call in mock_logging_error.call_args_list))

    def test_rejects_row_with_too_many_score_columns(self):
        """Verify response is rejected if a row has more scores than header IDs."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\t0.5\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    def test_log_level_from_config(self):
        """Verify log level is taken from config if no flags are present."""
        self.mock_config.set('General', 'default_log_level', 'WARNING')
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        test_argv = ['script.py', '--run_output_dir', str(self.run_dir)]
        
        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
            with patch.object(sys, 'argv', test_argv):
                process_llm_responses.main()
            output = mock_stdout.getvalue()
            self.assertNotIn("Response Processor log level set to", output)
            self.assertNotIn("Found 1 LLM response files to process", output)

    def test_rejects_response_with_non_numeric_header_id(self):
        """Verify response is rejected if header ID number is not an int."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID\t1\tID\tB\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.mock_sys_exit.assert_not_called()

    @patch('src.process_llm_responses.logging.error')
    def test_handles_generic_exception_processing_response(self, mock_logging_error):
        """Verify script skips a response if a generic error occurs during processing."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("valid response")

        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            if 'llm_response_001.txt' in str(file):
                raise Exception("Cannot read response")
            return original_open(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        self.assertTrue(any("Cannot read response" in call[0][0] for call in mock_logging_error.call_args_list))

    @patch('src.process_llm_responses.unicodedata.normalize')
    def test_normalize_text_for_llm_handles_normalize_exception(self, mock_normalize):
        """Verify normalize_text_for_llm handles exceptions from unicodedata."""
        mock_normalize.side_effect = TypeError("Mocked TypeError")
        result = process_llm_responses.normalize_text_for_llm("some text")
        self.assertEqual(result, "some text")

    def test_validation_fails_on_manifest_index_error(self):
        """Verify script exits if a manifest line causes an IndexError."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        # Malformed manifest line with too few columns to cause IndexError on split
        (self.queries_dir / "llm_query_001_manifest.txt").write_text("Header\nCol1\tCol2\n")

        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()
        self.mock_sys_exit.assert_called_with(1)

    @patch('src.process_llm_responses.logging.error')
    def test_handles_exception_reading_manifest(self, mock_logging_error):
        """Verify script exits if a manifest file causes a generic error."""
        self._setup_common_files()
        # Provide a valid response so successful_indices is not empty
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\nPerson B (1910)\t0.2\t0.8\n```")
        
        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            if 'manifest.txt' in str(file):
                raise Exception("Cannot read manifest")
            return original_open(file, *args, **kwargs)

        with self.assertRaises(SystemExit):
            with patch('builtins.open', mock_open):
                with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                    process_llm_responses.main()
        
        self.mock_sys_exit.assert_called_with(1)
        self.assertTrue(any("Cannot read manifest" in str(call) for call in mock_logging_error.call_args_list))

    def test_skips_response_if_query_file_missing(self):
        """Verify script skips a response if its query file is missing."""
        # Create response and mappings.txt, but no query file.
        (self.responses_dir / "llm_response_001.txt").write_text("valid response")
        (self.queries_dir / "mappings.txt").write_text("Map_idx1\n1\n")
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    def test_handles_response_with_only_separators(self):
        """Verify a response with only markdown separators is rejected."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("---\n---\n")
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
    
    def test_rejects_row_with_extra_unmapped_columns(self):
        """Verify response is rejected if a row has more columns than header IDs."""
        self._setup_common_files(k=2)
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\t0.1\tEXTRA\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    def test_rejects_response_if_all_rows_are_invalid(self):
        """Verify response is rejected if all data rows are malformed."""
        self._setup_common_files(k=2)
        # No (YYYY) anchor in any row
        response_content = "```\nName\tID 1\tID 2\nPerson A\t0.9\t0.1\nPerson B\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    @patch('src.process_llm_responses.re.search')
    def test_handles_generic_exception_in_parser(self, mock_re_search):
        """Verify a generic exception in the parser rejects the response."""
        # This side effect lets the filename parse in main() succeed,
        # then raises an exception on the first call inside the parser.
        mock_re_search.side_effect = [
            re.search(r"llm_response_(\d+)\.txt", "llm_response_001.txt"),
            Exception("Regex engine failure")
        ]
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("valid response")
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")
        
    def test_validator_fails_on_matrix_count_mismatch(self):
        """Verify content validator fails if file has fewer matrices than expected."""
        self.analysis_dir.mkdir(exist_ok=True)
        scores_file = self.analysis_dir / "scores.txt"
        scores_file.write_text("0.9\t0.1\n0.2\t0.8")
        
        expected_map = {1: np.array([]), 2: np.array([])} # Expect 2 matrices
        result = process_llm_responses.validate_all_scores_file_content(str(scores_file), expected_map, k_value=2)
        self.assertFalse(result)

    def test_validation_fails_on_out_of_bounds_index(self):
        """Verify script exits if a successful index is out of bounds for mappings.txt."""
        # Setup files for index 1, but mappings.txt will be too short
        (self.queries_dir / "llm_query_001.txt").write_text("LIST A\nPerson A (1900)\n\nLIST B\nDesc 1")
        (self.queries_dir / "llm_query_001_manifest.txt").write_text("Header\nPerson A (1900)\tDesc_1\t1")
        (self.responses_dir / "llm_response_001.txt").write_text("```\nName\tID 1\nPerson A (1900)\t0.9\n```")
        # Empty mappings file (only a header)
        (self.queries_dir / "mappings.txt").write_text("Map_idx1\n")

        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
                process_llm_responses.main()
        
        self.mock_sys_exit.assert_called_with(1)

    def test_validator_handles_no_trailing_newline_and_corruption(self):
        """Verify validator handles a corrupt last matrix with no trailing newline."""
        self.analysis_dir.mkdir(exist_ok=True)
        scores_file = self.analysis_dir / "scores.txt"
        # First matrix is fine, second is corrupt and at EOF
        scores_file.write_text("0.9\t0.1\n\n0.2\tbad-data")
        
        expected_map = {1: np.array([[0.9, 0.1]]), 2: np.array([[0.2, 0.8]])}
        result = process_llm_responses.validate_all_scores_file_content(str(scores_file), expected_map, k_value=1)
        self.assertFalse(result)

    @patch('src.process_llm_responses.open', side_effect=Exception("Generic open error"))
    def test_filter_mappings_by_index_generic_exception(self, mock_open):
        """Verify filter_mappings_by_index handles a generic exception."""
        result = process_llm_responses.filter_mappings_by_index(
            "dummy_source", "dummy_dest", [1], "dummy_queries"
        )
        self.assertFalse(result)

    def test_handles_empty_markdown_block(self):
        """Verify a response with an empty markdown block is rejected."""
        self._setup_common_files()
        (self.responses_dir / "llm_response_001.txt").write_text("```\n```")
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
        self.assertEqual((self.analysis_dir / "all_scores.txt").read_text(), "")

    def test_parser_converts_nan_values(self):
        """Verify parser converts 'nan' to 0.0 and does not reject the response."""
        self._setup_common_files()
        response_content = "```\nName\tID 1\tID 2\nPerson A (1900)\t0.9\tnan\nPerson B (1910)\t0.2\t0.8\n```"
        (self.responses_dir / "llm_response_001.txt").write_text(response_content)
        
        with patch.object(sys, 'argv', ['script.py', '--run_output_dir', str(self.run_dir)]):
            process_llm_responses.main()
            
        content = (self.analysis_dir / "all_scores.txt").read_text().strip()
        self.assertEqual(content, "0.90\t0.00\n0.20\t0.80")
        self.mock_sys_exit.assert_not_called()

    def test_validator_fails_on_expected_matrix_shape_mismatch(self):
        """Verify validator fails if a loaded matrix shape mismatches the expected matrix shape."""
        self.analysis_dir.mkdir(exist_ok=True)
        scores_file = self.analysis_dir / "scores.txt"
        scores_file.write_text("0.9\t0.1\n0.2\t0.8") # 2x2 matrix

        # Expected map contains a 1x2 matrix, which is a shape mismatch
        expected_map = {1: np.array([[0.9, 0.1]])}
        result = process_llm_responses.validate_all_scores_file_content(str(scores_file), expected_map, k_value=2)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_process_llm_responses.py ===
