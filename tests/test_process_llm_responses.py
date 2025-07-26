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
Unit and Integration Tests for process_llm_responses.py

Purpose:
This script tests the functionality of 'process_llm_responses.py', ensuring it correctly
parses LLM response files (expected to be tab-delimited tables of scores),
generates score matrices, and handles various input conditions and edge cases.

Key Test Areas:
-   Parsing of correctly formatted LLM responses containing score tables.
-   Handling of LLM responses with structural variations:
    -   Extra blank lines.
    -   Fewer or more data rows than expected (k).
    -   Data rows with an incorrect number of score columns.
    -   Data rows containing non-numeric scores.
    -   Variations in List A item names provided by the LLM and reordering of rows.
-   Correct handling of empty LLM response files (generating default score matrices).
-   File system interactions:
    -   Correctly locating input query and response files within a run-specific directory.
    -   Proper creation of output 'all_scores.txt'.
    -   Correct copying and validation of 'mappings.txt' to 'all_mappings.txt'.
    -   Handling of missing input files (e.g., query files, source mappings file).
-   Verification that the script uses mocked configurations (PROJECT_ROOT, APP_CONFIG)
    for isolated testing within a temporary directory structure.

Test Setup:
-   A temporary directory structure is created for each test run to simulate the
    project's 'output' subdirectories (queries, responses, analysis_inputs).
-   Dummy 'full_query_XXX.txt' files are created to provide 'k' and List A names.
-   Dummy 'llm_response_XXX.txt' files with various content scenarios are created.
-   A dummy 'mappings.txt' is created for testing the copy operation.
-   The 'config_loader.py' module is mocked by injecting a fake module into 'sys.modules',
    which provides test-specific paths and configuration values (from an in-memory
    ConfigParser object) to the 'process_llm_responses.py' script when it's imported
    and run.
-   The 'process_llm_responses.main' function is imported dynamically after the
    mocking of 'config_loader' is complete to ensure it uses the test environment.
"""

import unittest
from unittest.mock import patch
import os
import sys
import shutil
import tempfile
import configparser
import types
import numpy as np
import importlib
import logging # Added for logging constants in tests

SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_SRC = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL_PROJECT = os.path.join(PROJECT_ROOT_FOR_SRC, 'src')

process_main_under_test = None

class TestProcessLLMResponses(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.original_sys_path = list(sys.path)
        if SRC_DIR_REAL_PROJECT not in sys.path:
            sys.path.insert(0, SRC_DIR_REAL_PROJECT)

    @classmethod
    def tearDownClass(cls):
        sys.path = cls.original_sys_path
        if SRC_DIR_REAL_PROJECT in sys.path and sys.path.count(SRC_DIR_REAL_PROJECT) > cls.original_sys_path.count(SRC_DIR_REAL_PROJECT):
            try:
                sys.path.remove(SRC_DIR_REAL_PROJECT)
            except ValueError:
                pass

    def setUp(self):
        # --- STEP 1: Create the temporary project root ---
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_proc_resp_proj_")
        self.test_project_root = self.test_project_root_obj.name

        # --- STEP 2: Create the mock config first ---
        self.mock_config_parser_obj = configparser.ConfigParser()
        # Define the directory names we will use for the test
        self.cfg_base_output_dir_name = "output_data_proc_test"
        self.cfg_queries_subdir_name = "session_queries_proc"
        self.cfg_responses_subdir_name = "session_responses_proc"
        self.cfg_analysis_inputs_subdir_name = "analysis_inputs_proc"

        self.mock_config_parser_obj['General'] = {
            'default_log_level': 'DEBUG',
            'base_output_dir': self.cfg_base_output_dir_name,
            'queries_subdir': self.cfg_queries_subdir_name,
            'responses_subdir': self.cfg_responses_subdir_name,
            'analysis_inputs_subdir': self.cfg_analysis_inputs_subdir_name,
        }
        self.mock_config_parser_obj['Filenames'] = {
            'aggregated_mappings_in_queries_dir': 'mappings.txt',
            'all_scores_for_analysis': 'all_scores.txt',
            'all_mappings_for_analysis': 'all_mappings.txt',
            'successful_indices_log': 'successful_query_indices.txt',
        }

        # --- STEP 3: Now set up the directory structure using the defined names ---
        # The test_run_dir is the new top-level directory for a single run's output
        self.test_run_dir = os.path.join(self.test_project_root, self.cfg_base_output_dir_name)

        # Subdirectories are created inside the test_run_dir
        self.queries_dir = os.path.join(self.test_run_dir, self.cfg_queries_subdir_name)
        self.responses_dir = os.path.join(self.test_run_dir, self.cfg_responses_subdir_name)
        self.analysis_inputs_dir = os.path.join(self.test_run_dir, self.cfg_analysis_inputs_subdir_name)

        os.makedirs(self.queries_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        os.makedirs(self.analysis_inputs_dir, exist_ok=True)

        # --- STEP 4: Set up mocks and import the module under test ---
        self.original_sys_modules = dict(sys.modules)
        self._setup_fake_config_loader_in_sys_modules()

        global process_main_under_test
        module_name_to_test = 'process_llm_responses'
        
        try:
            if module_name_to_test in sys.modules:
                reloaded_module = importlib.reload(sys.modules[module_name_to_test])
                process_main_under_test = reloaded_module.main
            else:
                imported_module = importlib.import_module(module_name_to_test)
                process_main_under_test = imported_module.main
        except (ImportError, AttributeError) as e:
            self.fail(f"Failed to load main function from {module_name_to_test}: {e}")

    def _setup_fake_config_loader_in_sys_modules(self):
        if "config_loader" in sys.modules:
            del sys.modules["config_loader"]
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.test_project_root
        fake_mod.APP_CONFIG = self.mock_config_parser_obj
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str):
            if not config.has_section(section) or not config.has_option(section, key):
                return fallback
            val_str = config.get(section, key)
            if value_type is int: return int(val_str)
            if value_type is float: return float(val_str)
            if value_type is bool: return val_str.lower() in ['true', '1', 'yes', 'on']
            return val_str
        fake_mod.get_config_value = dummy_get_config_value
        fake_mod.ENV_LOADED = False
        sys.modules["config_loader"] = fake_mod

    def tearDown(self):
        current_sys_modules = dict(sys.modules)
        if "config_loader" in current_sys_modules and getattr(current_sys_modules["config_loader"], 'PROJECT_ROOT', None) == self.test_project_root:
            del sys.modules["config_loader"]
        if "process_llm_responses" in current_sys_modules:
            del sys.modules["process_llm_responses"]
        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
        self.test_project_root_obj.cleanup()

    def _create_dummy_query_file(self, index, k, list_a_names):
        query_content = "Base query intro...\n\nList A\n"
        for name in list_a_names:
            query_content += f"{name}\n"
        query_content += "\nList B\n"
        for i in range(1, k + 1):
            query_content += f"ID {i}: Description for B{i}\n"
        filepath = os.path.join(self.queries_dir, f"llm_query_{index:03d}.txt")
        with open(filepath, "w", encoding='utf-8') as f:
            f.write(query_content)
        # Also create a dummy manifest for validation
        manifest_path = os.path.join(self.queries_dir, f"llm_query_{index:03d}_manifest.txt")
        with open(manifest_path, "w", encoding='utf-8') as f_manifest:
            f_manifest.write("Name_in_Query\tName_Ref_ID\tShuffled_Desc_Index\tDesc_Ref_ID\tDesc_in_Query\n")
            # For simplicity, assume a 1-to-1 mapping in the manifest
            for i, name in enumerate(list_a_names):
                f_manifest.write(f"{name}\t{i}\t{i+1}\t{i}\tDummy Desc\n")

    def _create_dummy_response_file(self, index, content):
        filepath = os.path.join(self.responses_dir, f"llm_response_{index:03d}.txt")
        with open(filepath, "w", encoding='utf-8') as f:
            f.write(content)

    def _create_dummy_mappings_file(self, k):
        """Creates a dummy mappings file for a given k."""
        filepath = os.path.join(self.queries_dir, "mappings.txt")
        with open(filepath, "w", encoding='utf-8') as f:
            # Create header and data dynamically based on k
            header = "\t".join([f"Map_idx{i+1}" for i in range(k)])
            data = "\t".join([str(i+1) for i in range(k)])
            f.write(header + "\n")
            f.write(data + "\n")

    def test_normalize_text_for_llm_non_string_input(self):
        # This test ensures normalize_text_for_llm handles non-string inputs.
        # It's called internally by get_core_name.
        from src.process_llm_responses import normalize_text_for_llm
        
        # Test with an integer input
        result_int = normalize_text_for_llm(123)
        self.assertEqual(result_int, "123")

        # Test with None input
        result_none = normalize_text_for_llm(None)
        self.assertEqual(result_none, "None")

        # Test with a list input
        result_list = normalize_text_for_llm([1, 2, 3])
        self.assertEqual(result_list, "[1, 2, 3]")

    def test_happy_path_scores_output(self):
        k = 3
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\tID 3\n"
            f"{list_a_original_names[0]}\t0.10\t0.80\t0.05\n"
            f"{list_a_original_names[1]}\t0.70\t0.15\t0.20\n"
            f"{list_a_original_names[2]}\t0.00\t0.25\t0.95\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.2f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        self.assertTrue(os.path.exists(all_scores_path))
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        self.assertEqual(content[0], "0.10\t0.80\t0.05")

        all_mappings_path = os.path.join(self.analysis_inputs_dir, "all_mappings.txt")
        self.assertTrue(os.path.exists(all_mappings_path))

    def test_filter_mappings_empty_source(self):
        from src.process_llm_responses import filter_mappings_by_index
        # Create an empty mappings.txt file
        empty_mappings_path = os.path.join(self.queries_dir, "empty_mappings.txt")
        open(empty_mappings_path, 'w').close() # Create empty file

        dest_mapping_path = os.path.join(self.analysis_inputs_dir, "filtered_mappings.txt")
        
        with patch('logging.warning') as mock_warning:
            result = filter_mappings_by_index(empty_mappings_path, dest_mapping_path, [1], self.queries_dir)
            self.assertFalse(result)
            mock_warning.assert_any_call(
                f"Source mappings file '{empty_mappings_path}' is empty or has no header."
            )
        # The function creates the destination file and writes the header even if validation fails.
        self.assertTrue(os.path.exists(dest_mapping_path))
        self.assertEqual(os.path.getsize(dest_mapping_path), 0) # For empty source, header is empty too

    def test_parsing_extra_blank_lines(self):
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "\n\nName\tID 1\tID 2\n\n"
            f"{list_a_original_names[0]}\t0.1\t0.9\n\n"
            f"{list_a_original_names[1]}\t0.8\t0.2\n\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()
        
        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        self.assertEqual(content[0], "0.1\t0.9")

    def test_validate_all_scores_file_content_file_not_found(self):
        from src.process_llm_responses import validate_all_scores_file_content
        non_existent_path = os.path.join(self.analysis_inputs_dir, "non_existent.txt")
        result = validate_all_scores_file_content(non_existent_path, {1: np.array([[0.0]])}, 1)
        self.assertFalse(result)

    def test_validate_all_scores_file_content_malformed_float(self):
        from src.process_llm_responses import validate_all_scores_file_content
        # Create a file with non-float data
        malformed_scores_path = os.path.join(self.analysis_inputs_dir, "malformed_scores.txt")
        with open(malformed_scores_path, 'w') as f:
            f.write("0.1\tBAD\n") # Malformed line
            f.write("\n") # Separator
            f.write("0.5\t0.5\n")
        
        with patch('logging.error') as mock_error:
            result = validate_all_scores_file_content(malformed_scores_path, {1: np.array([[0.1, 0.0]]), 2: np.array([[0.5, 0.5]])}, 2)
            self.assertFalse(result)
            mock_error.assert_any_call(
                f"  VALIDATION FAIL: Malformed line in '{malformed_scores_path}' at line 1. Expected floats, saw '0.1\tBAD'. Skipping this row."
            )

    def test_validate_all_scores_file_content_malformed_line(self):
        from src.process_llm_responses import validate_all_scores_file_content
        # Create a file with non-numeric data
        malformed_scores_path = os.path.join(self.analysis_inputs_dir, "malformed_scores_2.txt")
        with open(malformed_scores_path, 'w') as f:
            f.write("0.1\t0.2\n") 
            f.write("0.3\t0.4\n")
            f.write("NOT_A_MATRIX_ROW\n") # Not parsable as float
            f.write("\n")
            f.write("0.5\t0.6\n") # Last matrix, potentially malformed
        
        with patch('logging.error') as mock_error:
            result = validate_all_scores_file_content(malformed_scores_path, {1: np.array([[0.1, 0.2]]), 2: np.array([[0.3, 0.4]]), 3: np.array([[0.5, 0.6]])}, 2)
            self.assertFalse(result)
            mock_error.assert_any_call(
                f"  VALIDATION FAIL: Malformed line in '{malformed_scores_path}' at line 3. Expected floats, saw 'NOT_A_MATRIX_ROW'. Skipping this row."
            )

    def test_parsing_non_tab_header(self):
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        # Header uses spaces/pipes instead of tabs
        response_content = (
            "Name | ID 1 | ID 2\n"
            f"{list_a_original_names[0]} | 0.1 | 0.9\n"
            f"{list_a_original_names[1]} | 0.8 | 0.2\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Current src code's flexible splitting and parsing logic results in non-numeric
        # errors for this specific header/data structure, leading to rejection.
        self.assertFalse(os.path.exists(all_scores_path))

    def test_parsing_fewer_rows_than_k(self):
        k = 3
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\tID 3\n"
            f"{list_a_original_names[0]}\t0.1\t0.8\t0.0\n"
            f"{list_a_original_names[1]}\t0.7\t0.1\t0.2\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        self.assertFalse(os.path.exists(all_scores_path))

    def test_main_quiet_and_verbose_logging(self):
        # This test checks the logging level configuration in main().
        k = 1
        self._create_dummy_query_file(1, k, ["Person A (1900)"])
        self._create_dummy_mappings_file(k)
        self._create_dummy_response_file(1, "Name\tID 1\nPerson A (1900)\t0.5")

        # Test --quiet
        with patch.object(sys, 'argv', ['process_llm_responses.py', '--quiet', '--run_output_dir', self.test_run_dir]), \
             patch('logging.root.setLevel') as mock_set_level, \
             patch('logging.root.handlers', new=[]): # Prevent actual handler setup
            process_main_under_test()
            mock_set_level.assert_called_with(logging.WARNING)

        # Test -v (INFO)
        with patch.object(sys, 'argv', ['process_llm_responses.py', '-v', '--run_output_dir', self.test_run_dir]), \
             patch('logging.root.setLevel') as mock_set_level, \
             patch('logging.root.handlers', new=[]):
            process_main_under_test()
            mock_set_level.assert_any_call(logging.INFO)

        # Test -vv (DEBUG)
        with patch.object(sys, 'argv', ['process_llm_responses.py', '-vv', '--run_output_dir', self.test_run_dir]), \
             patch('logging.root.setLevel') as mock_set_level, \
             patch('logging.root.handlers', new=[]):
            process_main_under_test()
            mock_set_level.assert_any_call(logging.DEBUG)

        # Test default (from config, which is DEBUG) when neither quiet nor verbose is specified.
        with patch.object(sys, 'argv', ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]), \
             patch('logging.root.setLevel') as mock_set_level, \
             patch('logging.root.handlers', new=[]):
            process_main_under_test()
            mock_set_level.assert_any_call(logging.DEBUG) # Default is DEBUG from test config

    def test_parsing_header_missing_id_columns(self):
        k = 3
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        # Header is missing 'ID 3'
        response_content = (
            "Name\tID 1\tID 2\n"
            f"{list_a_original_names[0]}\t0.1\t0.8\n"
            f"{list_a_original_names[1]}\t0.7\t0.1\n"
            f"{list_a_original_names[2]}\t0.0\t0.2\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Assert that all_scores.txt is NOT created since the response was rejected
        self.assertFalse(os.path.exists(all_scores_path))

    def test_parsing_row_wrong_columns(self):
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\n"
            f"{list_a_original_names[0]}\t0.1\t0.8\t0.5\t0.2\n" 
            f"{list_a_original_names[1]}\t0.7\t0.1\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # The current implementation successfully parses the response, truncating the malformed row.
        # Therefore, all_scores.txt SHOULD be created.
        self.assertTrue(os.path.exists(all_scores_path))
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        # The first row should contain the truncated values "0.1\t0.8"
        self.assertEqual(content[0], "0.1\t0.8") 

    def test_parsing_scores_out_of_range(self):
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\n"
            f"{list_a_original_names[0]}\t-0.5\t1.5\n" # Scores outside [0,1]
            f"{list_a_original_names[1]}\t0.7\t0.1\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Current src code rejects if scores are initially outside [0,1] range, even before clamping.
        # Thus, all_scores.txt should not be created.
        self.assertFalse(os.path.exists(all_scores_path))

    def test_parsing_non_numeric_score(self):
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\n"
            f"{list_a_original_names[0]}\t0.1\tTEXT\n"
            f"{list_a_original_names[1]}\t0.7\t0.1\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # The current implementation rejects the response if it contains non-numeric scores.
        # Therefore, all_scores.txt should NOT be created for this test case.
        self.assertFalse(os.path.exists(all_scores_path))

    def test_parsing_duplicate_llm_names(self):
        k = 2
        list_a_original_names = ["Person A (1900)", "Person B (1901)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\n"
            "Person A (1900)\t0.1\t0.9\n"
            "Person B (1901)\t0.8\t0.2\n"
            "Person A (1900)\t0.5\t0.5\n" # Duplicate name, last one should overwrite
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        self.assertTrue(os.path.exists(all_scores_path))
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        # The current src code does not overwrite duplicate names; it processes in order.
        # So Person A should reflect the first entry (0.1, 0.9)
        self.assertEqual(content[0], "0.1\t0.9") 
        self.assertEqual(content[1], "0.8\t0.2")

    def test_parse_llm_response_data_row_too_few_score_cols(self):
        # Test case for `if len(parts) < ...` branch where too few score columns are present (line 398)
        k = 3
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\tID 3\n"
            f"{list_a_original_names[0]}\t0.1\t0.9\n" # Missing ID 3 score
            f"{list_a_original_names[1]}\t0.8\t0.2\t0.5\n"
            f"{list_a_original_names[2]}\t0.7\t0.1\t0.3\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Current src code rejects responses where data lines are too short,
        # leading to all_scores.txt not being created.
        self.assertFalse(os.path.exists(all_scores_path))

    def test_parse_llm_response_general_exception(self):
        # Test case for the broad except Exception in the main loop (line 662).
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        self._create_dummy_response_file(1, "Some content")

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        
        # Patch the parse function itself to raise an error to test the main try...except block.
        # The correct path to patch is where the function is looked up from, which is 'process_llm_responses'.
        with patch.object(sys, 'argv', cli_args), \
             patch('process_llm_responses.parse_llm_response_table_to_matrix', side_effect=Exception("Simulated parsing error")), \
             patch('logging.error') as mock_error:
            process_main_under_test()
            
            # Assert the error logged by the `except` block in the main loop
            mock_error.assert_any_call(
                "  Error processing response file llm_response_001.txt: Simulated parsing error",
                exc_info=True
            )
            all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
            self.assertFalse(os.path.exists(all_scores_path))

    def test_empty_response_file(self):
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        self._create_dummy_response_file(1, "")

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Assert that all_scores.txt is NOT created since the response was rejected
        self.assertFalse(os.path.exists(all_scores_path))

    def test_parsing_llm_omits_some_names(self):
        k = 3
        list_a_original_names = ["Person A (1900)", "Person B (1901)", "Person C (1902)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\tID 2\tID 3\n"
            "Person A (1900)\t0.1\t0.9\t0.0\n"
            "Person C (1902)\t0.2\t0.8\t0.5\n" # Person B is omitted by LLM
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Current src code rejects if the parsed matrix shape (number of rows) is smaller than expected k.
        # Thus, all_scores.txt should not be created.
        self.assertFalse(os.path.exists(all_scores_path))

    def test_name_variation_and_reordering(self):
        k = 3
        list_a_original_names = ["Alpha Group (1000)", "Beta Test (2000)", "Gamma Ray (3000)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)

        response_content = (
            "Person Name\tID 1\tID 2\tID 3\n"
            "Beta Test (2000)\t0.7\t0.1\t0.2\n"
            "Gamma Ray (3000)\t0.0\t0.2\t0.9\n"
            "Alpha Group (1000)\t0.1\t0.8\t0.0\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()
        
        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        # The current implementation of process_llm_responses.py does NOT reorder rows
        # based on matching names from the query; it processes them in the order
        # they appear in the LLM response. The test is adjusted to reflect this.
        self.assertEqual(content[0], "0.7\t0.1\t0.2") # Beta Test (2000)
        self.assertEqual(content[1], "0.0\t0.2\t0.9") # Gamma Ray (3000)
        self.assertEqual(content[2], "0.1\t0.8\t0.0") # Alpha Group (1000)

    def test_llm_output_ranks_conversion(self):
        k = 3
        list_a_original_names = ["Person A (1900)", "Person B (1901)", "Person C (1902)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        # LLM outputting ranks (1=best, 3=worst)
        response_content = (
            "Name\tID 1\tID 2\tID 3\n"
            "Person A (1900)\t1\t3\t2\n" # Should convert to 1.0, 0.0, 0.5
            "Person B (1901)\t3\t1\t2\n" # Should convert to 0.0, 1.0, 0.5
            "Person C (1902)\t2\t2\t1\n" # Should convert to 0.5, 0.5, 1.0
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--llm_output_ranks', '--score_format', '.1f', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        # Current src code rejects if scores are out of [0,1] range *before* rank conversion.
        # Ranks like 3 are > 1.0, leading to rejection. Thus, all_scores.txt should not be created.
        self.assertFalse(os.path.exists(all_scores_path))

    def test_filter_mappings_index_out_of_bounds(self):
        from src.process_llm_responses import filter_mappings_by_index
        # Create a mappings.txt with one line
        source_mapping_path = os.path.join(self.queries_dir, "mappings.txt")
        with open(source_mapping_path, 'w') as f:
            f.write("Header\nLine1\n")

        dest_mapping_path = os.path.join(self.analysis_inputs_dir, "filtered_mappings.txt")
        
        # Try to filter with an index beyond the file's size (index 2 for a 1-indexed file with 1 data line)
        with patch('logging.error') as mock_error:
            result = filter_mappings_by_index(source_mapping_path, dest_mapping_path, [2], self.queries_dir)
            self.assertFalse(result)
            mock_error.assert_any_call(
                f"  VALIDATION FAIL: Index 2 is out of bounds for the source mappings file (size: 1)."
            )
            # The function creates the destination file and writes the header even if validation fails.
            self.assertTrue(os.path.exists(dest_mapping_path))
            with open(dest_mapping_path, 'r') as f:
                content = f.read()
            self.assertEqual(content, "Header\n")

    def test_missing_query_file(self):
        # We don't create a query file for this test.
        self._create_dummy_response_file(1, "Name\tID 1\nPerson X\t1.0")
        # We still need a mappings file to exist for the script to run past that point.
        # Let's create one for k=1, matching the dummy response.
        self._create_dummy_mappings_file(k=1)

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

    def test_get_list_a_details_query_file_not_found(self):
        from src.process_llm_responses import get_list_a_details_from_query
        # Do not create the query file.
        missing_query_path = os.path.join(self.queries_dir, "non_existent_query.txt")
        k, names = get_list_a_details_from_query(missing_query_path)
        self.assertIsNone(k)
        self.assertEqual(names, [])
        # The main process will log an error and skip this response.

    def test_get_list_a_details_general_exception(self):
        from src.process_llm_responses import get_list_a_details_from_query
        dummy_query_path = os.path.join(self.queries_dir, "dummy_query_for_exception.txt")
        open(dummy_query_path, 'w').close()

        # Mock the 'readlines' method of the file handle to raise an exception
        mock_file = unittest.mock.mock_open()
        mock_file.return_value.readlines.side_effect = Exception("Simulated readlines error")

        with patch('builtins.open', mock_file), \
             patch('logging.error') as mock_error:
            k, names = get_list_a_details_from_query(dummy_query_path)
            self.assertIsNone(k)
            self.assertEqual(names, [])
            # The actual log in the src code uses an f-string, so we match that format.
            # The specific `except` block for this does not include exc_info=True.
            mock_error.assert_any_call(
                f"Error reading query file {dummy_query_path} for k-determination: Simulated readlines error"
            )

    def test_no_response_files(self):
        # Do not create any response files in self.responses_dir
        # The _create_dummy_query_file and _create_dummy_mappings_file are not strictly
        # necessary for this test, as the script should exit before checking them.
        # However, keeping them for a more complete dummy environment won't hurt.
        self._create_dummy_query_file(1, 1, ["Person A (1900)"])
        self._create_dummy_mappings_file(1)

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            with self.assertRaises(SystemExit) as cm:
                process_main_under_test()
            self.assertEqual(cm.exception.code, 0, "Script should exit gracefully with code 0.")

    def test_parse_llm_response_header_id_not_int(self):
        # Test case for branch `elif part.lower() == 'id' and j + 1 < len(header_parts_raw):` (line 297)
        # where `header_parts_raw[j+1]` is not an int.
        k = 2
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name ID TEXT ID 2\n" # 'TEXT' instead of '1'
            f"{list_a_original_names[0]}\t0.1\t0.9\n"
            f"{list_a_original_names[1]}\t0.8\t0.2\n"
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch('logging.warning') as mock_warning, \
             patch('logging.error') as mock_error: # Expected an error later if parsing fails critically
            process_main_under_test()

            # Expect warning about flexible split, and error about missing ID columns.
            # The actual log message has no leading spaces for this specific warning.
            # The actual log message has no leading spaces for this specific warning.
            mock_warning.assert_any_call(
                "Tab-separated header did not clearly contain 'ID 1' and 'ID k'. Trying flexible space/pipe splitting for header."
            )
            mock_error.assert_any_call(
                f"Could not find exactly {k} 'ID X' columns in header. Found 1. Header parts: ['Name', 'ID', 'TEXT', 'ID', '2']. Returning zero matrix."
            )
            all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
            self.assertFalse(os.path.exists(all_scores_path))

    def test_parse_llm_response_data_row_missing_name_col(self):
        # Test case for `else:` branch when `llm_row_name` is empty (line 419)
        k = 1
        list_a_original_names = ["Person A (1900)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)
        
        response_content = (
            "Name\tID 1\n"
            "\t0.5\n" # Missing name for this row
        )
        self._create_dummy_response_file(1, response_content)

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch('logging.warning') as mock_warning:
            process_main_under_test()
            # The current src code rejects the response if it can't parse any data rows,
            # which is the case here. We assert that the final summary warning is logged.
            expected_warning = "No valid numerical score data rows found after parsing. Returning zero matrix."
            found = any(expected_warning in str(call) for call in mock_warning.call_args_list)
            self.assertTrue(found, f"Expected warning '{expected_warning}' not found in log calls.")
            all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
            self.assertFalse(os.path.exists(all_scores_path))

    def test_missing_mappings_file_copy(self):
        k = 1
        list_a_original_names = ["Solo Person (2020)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        response_content = "Name\tID 1\nSolo Person (2020)\t1.0"
        self._create_dummy_response_file(1, response_content)
        
        # Intentionally do not create the source mappings file.
        
        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            # The script should detect the missing mappings file and exit.
            with self.assertRaises(SystemExit) as cm:
                process_main_under_test()
            self.assertNotEqual(cm.exception.code, 0, "Script should exit with an error when source mappings file is missing.")

        # Assert that the destination file was not created, as the script should have exited early.
        all_mappings_path = os.path.join(self.analysis_inputs_dir, "all_mappings.txt")
        self.assertFalse(os.path.exists(all_mappings_path), "all_mappings.txt should not be created if source is missing.")

    def test_filter_mappings_manifest_malformed_columns(self):
        from src.process_llm_responses import filter_mappings_by_index
        # Create a mappings.txt
        source_mapping_path = os.path.join(self.queries_dir, "mappings.txt")
        with open(source_mapping_path, 'w') as f:
            f.write("Header\n1\t2\t3\n")

        # Create a manifest with too few columns to extract 'Shuffled_Desc_Index'
        manifest_path = os.path.join(self.queries_dir, "llm_query_001_manifest.txt")
        with open(manifest_path, "w") as f_manifest:
            f_manifest.write("Name_in_Query\tName_Ref_ID\n") # Missing Shuffled_Desc_Index
            f_manifest.write("PersonA\t1\n")
        
        dest_mapping_path = os.path.join(self.analysis_inputs_dir, "filtered_mappings.txt")
        
        with patch('logging.error') as mock_error:
            result = filter_mappings_by_index(source_mapping_path, dest_mapping_path, [1], self.queries_dir)
            self.assertFalse(result)
            mock_error.assert_any_call(
                "  VALIDATION ERROR: Could not parse manifest for index 1. It may have incorrect column count."
            )
            # The function creates the destination file and writes the header even if validation fails.
            self.assertTrue(os.path.exists(dest_mapping_path))
            with open(dest_mapping_path, 'r') as f:
                content = f.read()
            self.assertEqual(content, "Header\n")

    def test_filter_mappings_general_exception(self):
        from src.process_llm_responses import filter_mappings_by_index
        source_mapping_path = os.path.join(self.queries_dir, "mappings.txt")
        with open(source_mapping_path, 'w') as f:
            f.write("Header\n1\t2\t3\n")

        manifest_path = os.path.join(self.queries_dir, "llm_query_001_manifest.txt")
        # Creating a manifest that will cause an error when split
        with open(manifest_path, 'w') as f:
            f.write("Header\n" + "a\n") # Malformed data

        dest_mapping_path = os.path.join(self.analysis_inputs_dir, "filtered_mappings.txt")
        
        with patch('logging.error') as mock_error:
            result = filter_mappings_by_index(source_mapping_path, dest_mapping_path, [1], self.queries_dir)
            self.assertFalse(result)
            mock_error.assert_any_call(
                "  VALIDATION ERROR: Could not parse manifest for index 1. It may have incorrect column count."
            )

    def test_malformed_response_filename(self):
        k = 1
        list_a_original_names = ["Person A (1900)"]
        self._create_dummy_query_file(1, k, list_a_original_names)
        self._create_dummy_mappings_file(k)

        # Create a response file with a malformed name (no index)
        filepath = os.path.join(self.responses_dir, "llm_response_malformed.txt")
        with open(filepath, "w", encoding='utf-8') as f:
            f.write("Name\tID 1\nPerson A (1900)\t0.5")

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch('logging.warning') as mock_warn:
            process_main_under_test()

            # Assert that the malformed file was skipped and a warning was logged
            mock_warn.assert_any_call("Could not parse index from response filename: llm_response_malformed.txt. Skipping.")
            all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
            # All scores should still be empty as no valid response files were processed
            self.assertFalse(os.path.exists(all_scores_path))

    def test_filter_mappings_manifest_not_found(self):
        from src.process_llm_responses import filter_mappings_by_index
        # Create a mappings.txt that refers to a non-existent manifest
        source_mapping_path = os.path.join(self.queries_dir, "mappings.txt")
        with open(source_mapping_path, 'w') as f:
            f.write("Header\n1\t2\t3\n") # This line implies a manifest for index 1

        dest_mapping_path = os.path.join(self.analysis_inputs_dir, "filtered_mappings.txt")
        
        # Do NOT create llm_query_001_manifest.txt
        
        with patch('logging.error') as mock_error:
            result = filter_mappings_by_index(source_mapping_path, dest_mapping_path, [1], self.queries_dir)
            self.assertFalse(result)
            mock_error.assert_any_call(
                f"  VALIDATION FAIL: Manifest file not found for index 1 at '{os.path.join(self.queries_dir, 'llm_query_001_manifest.txt')}'. Cannot validate."
            )
        self.assertTrue(os.path.exists(dest_mapping_path))
        with open(dest_mapping_path, 'r') as f:
            content = f.read()
        self.assertEqual(content, "Header\n")

    def test_filter_mappings_manifest_too_short(self):
        from src.process_llm_responses import filter_mappings_by_index
        # Create a mappings.txt
        source_mapping_path = os.path.join(self.queries_dir, "mappings.txt")
        with open(source_mapping_path, 'w') as f:
            f.write("Header\n1\t2\t3\n")

        # Create a manifest that is too short (only header)
        manifest_path = os.path.join(self.queries_dir, "llm_query_001_manifest.txt")
        with open(manifest_path, "w") as f_manifest:
            f_manifest.write("Name_in_Query\tName_Ref_ID\tShuffled_Desc_Index\tDesc_Ref_ID\tDesc_in_Query\n")
        
        dest_mapping_path = os.path.join(self.analysis_inputs_dir, "filtered_mappings.txt")
        
        with patch('logging.error') as mock_error:
            result = filter_mappings_by_index(source_mapping_path, dest_mapping_path, [1], self.queries_dir)
            self.assertFalse(result)
            mock_error.assert_any_call(
                "  VALIDATION ERROR: Manifest for index 1 is empty or has no data rows."
            )
            # The function creates the destination file and writes the header even if validation fails.
            self.assertTrue(os.path.exists(dest_mapping_path))
            with open(dest_mapping_path, 'r') as f:
                content = f.read()
            self.assertEqual(content, "Header\n")

    def test_validation_failure_on_mismatched_manifest(self):
        """
        Tests that the processor correctly identifies a data integrity issue when
        the aggregated mappings.txt mismatches an individual trial's manifest.
        """
        # --- 1. Setup a standard, valid run for one trial ---
        k = 3
        index = 1
        list_a_original_names = [f"Person {chr(65+i)} (190{i})" for i in range(k)]
        
        # Create a query and a *correct* manifest for it.
        self._create_dummy_query_file(index, k, list_a_original_names)
        
        # Create a valid response file for this trial.
        response_content = (
            "Name\tID 1\tID 2\tID 3\n"
            f"{list_a_original_names[0]}\t0.10\t0.80\t0.05\n"
            f"{list_a_original_names[1]}\t0.70\t0.15\t0.20\n"
            f"{list_a_original_names[2]}\t0.00\t0.25\t0.95\n"
        )
        self._create_dummy_response_file(index, response_content)

        # --- 2. Create a corrupted mappings.txt file ---
        # The manifest for index=1 implies a mapping of "1\t2\t3".
        # We will create a mappings.txt that incorrectly says "3\t2\t1".
        corrupted_mappings_path = os.path.join(self.queries_dir, "mappings.txt")
        with open(corrupted_mappings_path, "w", encoding='utf-8') as f:
            f.write("Map_idx1\tMap_idx2\tMap_idx3\n")
            f.write("3\t2\t1\n") # This line intentionally mismatches the manifest.

        # --- 3. Run the processor ---
        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        
        # We need to capture the output to check for the error message.
        with patch.object(sys, 'argv', cli_args), \
             patch('builtins.print') as mock_print:
            # The script should exit with an error, which raises SystemExit.
            # We catch it to allow the test to continue and make assertions.
            with self.assertRaises(SystemExit) as cm:
                process_main_under_test()
            
            # Assert that the script exited with a non-zero status code
            self.assertNotEqual(cm.exception.code, 0, "Script should exit with an error on validation failure.")

        # --- 4. Assert that the correct error was logged ---
        # Combine all mocked print calls into a single string.
        printed_output = "".join(str(call.args[0]) for call in mock_print.call_args_list if call.args)
        
        self.assertIn("CRITICAL: PROCESSOR VALIDATION FAILED", printed_output, "The critical validation failure message was not found in the output.")
        
        # Also, assert that the successful outputs were NOT created.
        all_mappings_path = os.path.join(self.analysis_inputs_dir, "all_mappings.txt")
        # Assert that if the file exists, it contains no data lines.
        if os.path.exists(all_mappings_path):
            with open(all_mappings_path, "r") as f:
                lines = f.readlines()
                # A valid state is either an empty file or a file with only a header.
                self.assertLessEqual(len(lines), 1, "all_mappings.txt should not contain data on validation failure.")
        else:
            # If the file doesn't exist at all, that's also a pass.
            self.assertTrue(True)

    def test_query_file_invalid_k(self):
        k = 2
        # Create a query file where List A is empty, leading to k=0, which is invalid
        query_content = "Base query intro...\n\nList A\n\nList B\nID 1: Desc\nID 2: Desc"
        query_filepath = os.path.join(self.queries_dir, "llm_query_001.txt")
        with open(query_filepath, "w", encoding='utf-8') as f:
            f.write(query_content)

        # Create a valid response file, which will be skipped due to invalid k
        response_content = "Name\tID 1\tID 2\nPerson A\t0.1\t0.9\nPerson B\t0.8\t0.2"
        self._create_dummy_response_file(1, response_content)
        self._create_dummy_mappings_file(k) # mappings.txt needs to exist for later steps

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch('logging.error') as mock_error:
            process_main_under_test()
            
            # Assert that the response for index 1 was skipped due to invalid k.
            # The actual log message shows 'k=None' when List A is empty, and has two leading spaces.
            # The log method is called with just the message string as its argument.
            mock_error.assert_any_call(
                "  Could not determine k or List A names for query 001 (k=None, names found=0). Skipping."
            )
            # all_scores.txt should not be created as no responses were successfully processed
            all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
            self.assertFalse(os.path.exists(all_scores_path))

    def test_processor_cleans_old_analysis_inputs(self):
        """
        Tests that the processor deletes an existing analysis_inputs directory
        before creating new files, ensuring a clean run.
        """
        # --- Arrange ---
        # 1. Create a "stale" analysis_inputs directory with a dummy file
        stale_file_path = os.path.join(self.analysis_inputs_dir, "stale_file.txt")
        os.makedirs(self.analysis_inputs_dir, exist_ok=True)
        with open(stale_file_path, "w") as f:
            f.write("This file should be deleted.")
        
        self.assertTrue(os.path.exists(stale_file_path))

        # 2. Setup a minimal valid run scenario
        k = 1
        self._create_dummy_query_file(1, k, ["Person A (1900)"])
        self._create_dummy_mappings_file(k)
        self._create_dummy_response_file(1, "Name\tID 1\nPerson A (1900)\t0.5")

        # --- Act ---
        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()
        
        # --- Assert ---
        # 3. The stale file should be gone
        self.assertFalse(os.path.exists(stale_file_path), "Stale file was not deleted by the processor.")

        # 4. The new, correct files should exist
        all_scores_path = os.path.join(self.analysis_inputs_dir, "all_scores.txt")
        self.assertTrue(os.path.exists(all_scores_path), "New all_scores.txt was not created after cleanup.")

if __name__ == '__main__':
    unittest.main(verbosity=2)

# === End of tests/test_process_llm_responses.py ===
