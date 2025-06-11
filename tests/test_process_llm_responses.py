#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        self.assertEqual(content[2], "0.0\t0.0\t0.0")

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
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        self.assertEqual(content[0], "0.0\t0.0") 

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
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(len(content), k)
        self.assertEqual(content[0], "0.0\t0.0")

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
        with open(all_scores_path, "r") as f:
            content = f.read().strip().split('\n')
        self.assertEqual(content[0], "0.0\t0.0")

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
        self.assertEqual(content[0], "0.1\t0.8\t0.0")
        self.assertEqual(content[1], "0.7\t0.1\t0.2")
        self.assertEqual(content[2], "0.0\t0.2\t0.9")

    def test_missing_query_file(self):
        # We don't create a query file for this test.
        self._create_dummy_response_file(1, "Name\tID 1\nPerson X\t1.0")
        # We still need a mappings file to exist for the script to run past that point.
        # Let's create one for k=1, matching the dummy response.
        self._create_dummy_mappings_file(k=1)

        cli_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', cli_args):
            process_main_under_test()

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