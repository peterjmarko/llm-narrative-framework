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
# Filename: tests/test_run_llm_sessions.py

import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import shutil
import tempfile
import subprocess
import configparser
import importlib
import types
import json

# Adjust path: This needs to happen at module import time for decorators to find the module
SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_SRC = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL_PROJECT = os.path.join(PROJECT_ROOT_FOR_SRC, 'src')

# Ensure SRC_DIR_REAL_PROJECT is in sys.path when this test module is first loaded
if SRC_DIR_REAL_PROJECT not in sys.path:
    sys.path.insert(0, SRC_DIR_REAL_PROJECT)

from run_llm_sessions import format_seconds_to_time_str # Import early for decorator

# Global to hold the imported main function from the module under test
run_sessions_main_under_test = None
# run_llm_sessions is no longer needed as a global for patching format_seconds_to_time_str

class TestRunLLMSessions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Store original sys.path at the beginning of the class execution
        cls.class_original_sys_path = list(sys.path)
        # Ensure SRC_DIR_REAL_PROJECT is still at the front if some other class level setup modified it
        if SRC_DIR_REAL_PROJECT not in sys.path:
             sys.path.insert(0, SRC_DIR_REAL_PROJECT)
        elif sys.path[0] != SRC_DIR_REAL_PROJECT : # If it's there but not first
            try: sys.path.remove(SRC_DIR_REAL_PROJECT)
            except ValueError: pass
            sys.path.insert(0, SRC_DIR_REAL_PROJECT)


    @classmethod
    def tearDownClass(cls):
        # Restore sys.path to what it was before this class's setUpClass ran
        sys.path = cls.class_original_sys_path
        # Defensive removal, if it was added by this class specifically and wasn't there before
        if SRC_DIR_REAL_PROJECT in sys.path and SRC_DIR_REAL_PROJECT not in cls.class_original_sys_path:
             try: sys.path.remove(SRC_DIR_REAL_PROJECT)
             except ValueError: pass


    def setUp(self):
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="test_orch_proj_")
        self.test_project_root = self.test_project_root_obj.name

        # --- STEP 1: Create the mock config first ---
        self.mock_config_parser_obj = configparser.ConfigParser()
        # Define the directory names we will use for the test
        self.cfg_base_output_dir_name = "output_data_orch_test"
        self.cfg_queries_subdir_name = "session_queries_orch"
        self.cfg_responses_subdir_name = "session_responses_orch"
        self.test_temp_input_basename = "test_orch_current_query.txt"
        self.test_temp_response_basename = "test_orch_current_response.txt"
        self.test_temp_error_basename = "test_orch_current_error.txt"
        self.test_api_times_log_basename = "api_times_test.log"

        self.mock_config_parser_obj['General'] = {
            'default_log_level': 'DEBUG',
            'base_output_dir': self.cfg_base_output_dir_name,
            'queries_subdir': self.cfg_queries_subdir_name,
            'responses_subdir': self.cfg_responses_subdir_name
        }
        self.mock_config_parser_obj['Filenames'] = {
            'llmprompter_temp_query_in': self.test_temp_input_basename,
            'llmprompter_temp_response_out': self.test_temp_response_basename,
            'llmprompter_temp_error_out': self.test_temp_error_basename,
            'api_times_log': self.test_api_times_log_basename,
        }
        if not self.mock_config_parser_obj.has_section('LLM'): self.mock_config_parser_obj.add_section('LLM')
        if not self.mock_config_parser_obj.has_section('MetaAnalysis'): self.mock_config_parser_obj.add_section('MetaAnalysis')

        # --- STEP 2: Now set up the directory structure using the defined names ---
        self.src_dir_test_temp = os.path.join(self.test_project_root, "src")
        os.makedirs(self.src_dir_test_temp, exist_ok=True)
        
        self.resolved_output_base_dir = os.path.join(self.test_project_root, self.cfg_base_output_dir_name)
        os.makedirs(self.resolved_output_base_dir, exist_ok=True)

        # Path to the DUMMY llm_prompter.py
        self.dummy_llm_prompter_script_path_in_test_src = os.path.join(self.src_dir_test_temp, "llm_prompter.py")
        with open(self.dummy_llm_prompter_script_path_in_test_src, "w") as f:
            f.write("#!/usr/bin/env python3\nimport sys\nsys.exit(0)")
        os.chmod(self.dummy_llm_prompter_script_path_in_test_src, 0o755)
        
        self.num_test_queries = 3

        # --- STEP 3: Set up mocks and import the module under test ---
        self.original_sys_modules = dict(sys.modules)
        self._setup_fake_config_loader_in_sys_modules()

        global run_sessions_main_under_test
        module_name_to_test = 'run_llm_sessions'
        if module_name_to_test in sys.modules:
            reloaded_module = importlib.reload(sys.modules[module_name_to_test])
            run_sessions_main_under_test = reloaded_module.main
        else:
            imported_module = importlib.import_module(module_name_to_test)
            run_sessions_main_under_test = imported_module.main

    def _setup_fake_config_loader_in_sys_modules(self):
        if "config_loader" in sys.modules: del sys.modules["config_loader"]
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.test_project_root
        fake_mod.APP_CONFIG = self.mock_config_parser_obj
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str):
            if not config.has_section(section) or not config.has_option(section,key):
                return fallback # Return fallback if section or key doesn't exist
            val_str = config.get(section, key)
            if value_type is int: return config.getint(section, key, fallback=fallback)
            if value_type is float: return config.getfloat(section, key, fallback=fallback)
            if value_type is bool: return config.getboolean(section, key, fallback=fallback)
            return val_str
        fake_mod.get_config_value = dummy_get_config_value
        fake_mod.ENV_LOADED = False
        sys.modules["config_loader"] = fake_mod

    def tearDown(self):
        current_modules_after_test = dict(sys.modules)
        if "config_loader" in current_modules_after_test and \
           getattr(current_modules_after_test["config_loader"], 'PROJECT_ROOT', None) == self.test_project_root:
            del sys.modules["config_loader"]
        if "run_llm_sessions" in current_modules_after_test:
            del sys.modules["run_llm_sessions"]
        
        # Restore original modules that might have been deleted or replaced
        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
        
        self.test_project_root_obj.cleanup()

    def _clear_test_output_files(self, run_dir):
        """Clears response files from a specific run directory."""
        response_dir = os.path.join(run_dir, self.cfg_responses_subdir_name)
        if os.path.exists(response_dir):
            shutil.rmtree(response_dir) # Just remove the whole subdir
        api_times_log_path = os.path.join(run_dir, self.test_api_times_log_basename)
        if os.path.exists(api_times_log_path):
            os.remove(api_times_log_path)


    def _worker_run_success_side_effect(self, cmd_list_args, **kwargs):
        query_id_from_cmd = cmd_list_args[2]
        
        # The runner script creates a 'temp' directory inside the REAL project's 'src' folder.
        # The mock must create the temp files there so the runner can find them.
        temp_dir_path = os.path.join(SRC_DIR_REAL_PROJECT, "temp")
        os.makedirs(temp_dir_path, exist_ok=True)
        worker_temp_response_path = os.path.join(temp_dir_path, self.test_temp_response_basename)

        with open(worker_temp_response_path, "w", encoding='utf-8') as f:
            f.write(f"Mocked response for {query_id_from_cmd}")
        
        # Simulate JSON output on stdout and empty stderr (or None if the test doesn't capture it)
        mock_stdout_json = json.dumps({"test_key": f"value_{query_id_from_cmd}"})
        mock_stdout = f"---LLM_RESPONSE_JSON_START---\n{mock_stdout_json}\n---LLM_RESPONSE_JSON_END---"
        
        # subprocess.run in run_llm_sessions.py uses stderr=None to print worker's stderr to console
        # So we should return stderr=None here to match that behavior.
        return subprocess.CompletedProcess(args=cmd_list_args, returncode=0, stdout=mock_stdout, stderr=None)

    def _worker_simulated_failures_side_effect(self, cmd_list_args, **kwargs):
        query_id_from_cmd = cmd_list_args[2]

        temp_dir_path = os.path.join(SRC_DIR_REAL_PROJECT, "temp")
        os.makedirs(temp_dir_path, exist_ok=True)
        worker_temp_response_path = os.path.join(temp_dir_path, self.test_temp_response_basename)
        worker_temp_error_path = os.path.join(temp_dir_path, self.test_temp_error_basename)

        if query_id_from_cmd == "002": # Simulate worker creating an error file
            with open(worker_temp_error_path, "w", encoding='utf-8') as f:
                f.write(f"Worker simulated error for {query_id_from_cmd}")
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=1, stdout="Some worker stdout for 002 failure", stderr="Worker error output on stderr for 002")
        elif query_id_from_cmd == "003": # Simulate worker failing without creating error file
            # No temp response or error file created by worker
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=1, stdout="Some stdout from worker 003 failure", stderr="Fatal worker error no temp error file 003")
        else: # Default to success for others (e.g., "001")
            with open(worker_temp_response_path, "w", encoding='utf-8') as f:
                f.write(f"Mocked response for {query_id_from_cmd}")
            mock_stdout_json = json.dumps({"test_key": f"value_{query_id_from_cmd}"})
            mock_stdout = f"---LLM_RESPONSE_JSON_START---\n{mock_stdout_json}\n---LLM_RESPONSE_JSON_END---"
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=0, stdout=mock_stdout, stderr=None)

    def _worker_json_parse_failure_side_effect(self, cmd_list_args, **kwargs):
        query_id_from_cmd = cmd_list_args[2]
        temp_dir_path = os.path.join(SRC_DIR_REAL_PROJECT, "temp")
        os.makedirs(temp_dir_path, exist_ok=True)
        worker_temp_response_path = os.path.join(temp_dir_path, self.test_temp_response_basename)

        with open(worker_temp_response_path, "w", encoding='utf-8') as f:
            f.write(f"Mocked response for {query_id_from_cmd}")
        
        # Return malformed JSON or missing tags
        if query_id_from_cmd == "001": # Missing end tag
            mock_stdout = f"---LLM_RESPONSE_JSON_START---\n{{\"test\": \"data\"}}\n"
        elif query_id_from_cmd == "002": # Malformed JSON
            mock_stdout = f"---LLM_RESPONSE_JSON_START---\n{{NOT_JSON\n---LLM_RESPONSE_JSON_END---"
        else: # Valid JSON, but this is for specific error testing
            mock_stdout = f"---LLM_RESPONSE_JSON_START---\n{{\"test\": \"data\"}}\n---LLM_RESPONSE_JSON_END---"
        
        return subprocess.CompletedProcess(args=cmd_list_args, returncode=0, stdout=mock_stdout, stderr=None)

    def _worker_throws_exception_side_effect(self, cmd_list_args, **kwargs):
        # Simulate subprocess.run raising an exception
        raise OSError("Simulated OSError during worker execution")
    
    def _all_fail_side_effect(self, cmd_list_args, **kwargs):
        query_id_from_cmd = cmd_list_args[2]
        temp_dir_path = os.path.join(SRC_DIR_REAL_PROJECT, "temp")
        os.makedirs(temp_dir_path, exist_ok=True)
        worker_temp_error_path = os.path.join(temp_dir_path, self.test_temp_error_basename)
        with open(worker_temp_error_path, "w", encoding='utf-8') as f:
            f.write(f"Worker simulated error for {query_id_from_cmd}")
        return subprocess.CompletedProcess(args=cmd_list_args, returncode=1, stdout="", stderr="Worker error output")

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_runner_happy_path(self, mock_subprocess_run, mock_orch_logging):
        # Define the unique directory for this test run
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_happy_path")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        for i in range(1, self.num_test_queries + 1):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f:
                f.write(f"Query content for happy path {i:03d}")

        mock_subprocess_run.side_effect = self._worker_run_success_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')
        self.assertIsNotNone(module_under_test, "Runner module not loaded in setUp")
        
        cli_args = ['run_llm_sessions.py', '--verbose', '--run_output_dir', test_run_dir]

        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            self.assertEqual(module_under_test.PROJECT_ROOT, self.test_project_root)
            self.assertIs(module_under_test.APP_CONFIG, self.mock_config_parser_obj)
            run_sessions_main_under_test()

        self.assertEqual(mock_subprocess_run.call_count, self.num_test_queries)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        for i in range(1, self.num_test_queries + 1):
            idx_str = f"{i:03d}"
            expected_response_file = os.path.join(run_responses_dir, f"llm_response_{idx_str}.txt")
            self.assertTrue(os.path.exists(expected_response_file), f"{expected_response_file} not created")
            self.assertTrue(os.path.exists(os.path.join(run_responses_dir, f"llm_response_{idx_str}_full.json")))
        
        # Verify API times log header and content
        api_times_log_path = os.path.join(test_run_dir, self.test_api_times_log_basename)
        self.assertTrue(os.path.exists(api_times_log_path))
        with open(api_times_log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            self.assertIn("Query_ID\tCall_Duration_s\tTotal_Elapsed_s\tEstimated_Time_Remaining_s\n", lines[0])
            self.assertEqual(len(lines), self.num_test_queries + 1) # Header + 3 entries

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_runner_worker_failure(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_worker_failure")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        # Create 3 queries to cover different failure types
        for i in range(1, 4):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f:
                f.write(f"Query content for failure path {i:03d}")

        mock_subprocess_run.side_effect = self._worker_simulated_failures_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')
        
        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]

        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()

        self.assertEqual(mock_subprocess_run.call_count, 3)

        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        
        # Query 001 should succeed
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, f"llm_response_001.txt")))
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, f"llm_response_001.error.txt")))
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, f"llm_response_001_full.json")))

        # Query 002 should fail and create an error file by worker
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, f"llm_response_002.txt")))
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, f"llm_response_002_full.json")))
        expected_error_file_002 = os.path.join(run_responses_dir, f"llm_response_002.error.txt")
        self.assertTrue(os.path.exists(expected_error_file_002))
        with open(expected_error_file_002, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Worker simulated error for 002", content) # From worker's error file
        
        # Query 003 should fail and error file created by orchestrator
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, f"llm_response_003.txt")))
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, f"llm_response_003_full.json")))
        expected_error_file_003 = os.path.join(run_responses_dir, f"llm_response_003.error.txt")
        self.assertTrue(os.path.exists(expected_error_file_003))
        with open(expected_error_file_003, 'r', encoding='utf-8') as f:
            content = f.read()
            self.assertIn("Orchestrator noted worker script failed with exit code: 1.", content)
            self.assertIn("WORKER STDOUT:\nSome stdout from worker 003 failure", content)
            self.assertIn("WORKER STDERR:\nFatal worker error no temp error file 003", content)

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_runner_force_rerun_overwrites_error(self, mock_subprocess_run, mock_orch_logging):
        """
        Tests that the --force-rerun flag correctly deletes a pre-existing
        error file and creates a new success file.
        """
        # --- Arrange ---
        # 1. Define the unique directory for this test run
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_force_rerun")
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        os.makedirs(run_responses_dir, exist_ok=True)
        
        # 2. Create the query and a pre-existing ERROR file for index 1
        query_index = 1
        with open(os.path.join(run_queries_dir, f"llm_query_{query_index:03d}.txt"), "w") as f:
            f.write(f"Query content for force-rerun test")
        
        error_file_path = os.path.join(run_responses_dir, f"llm_response_{query_index:03d}.error.txt")
        with open(error_file_path, "w") as f:
            f.write("This is a pre-existing error.")
            
        self.assertTrue(os.path.exists(error_file_path))

        # 3. Set up the mock to simulate a SUCCESSFUL worker run
        mock_subprocess_run.side_effect = self._worker_run_success_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        # --- Act ---
        # 4. Run the orchestrator with --force-rerun targeting the failed index
        cli_args = [
            'run_llm_sessions.py', 
            '--run_output_dir', test_run_dir,
            '--start_index', str(query_index),
            '--end_index', str(query_index),
            '--force-rerun'
        ]
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()

        # --- Assert ---
        # 5. Check the final state of the files
        self.assertEqual(mock_subprocess_run.call_count, 1)
        
        # The original error file should be gone
        self.assertFalse(os.path.exists(error_file_path), "The pre-existing error file was not deleted.")
        
        # A new success file should have been created
        success_file_path = os.path.join(run_responses_dir, f"llm_response_{query_index:03d}.txt")
        self.assertTrue(os.path.exists(success_file_path), "A new success response file was not created on retry.")
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, f"llm_response_{query_index:03d}_full.json")))

    @patch('run_llm_sessions.logging')
    def test_temp_dir_creation_failure(self, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_temp_dir_fail")
        self._clear_test_output_files(test_run_dir) # Ensure clean slate

        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True) # Create this so script doesn't exit early
        # Add a dummy query file so the script doesn't exit due to no query files found
        with open(os.path.join(run_queries_dir, "llm_query_001.txt"), "w") as f: f.write("dummy query")

        # Mock os.makedirs from within run_llm_sessions module
        module_under_test = sys.modules.get('run_llm_sessions')
        with patch.object(module_under_test.os, 'makedirs', wraps=os.makedirs) as mock_os_makedirs:
            # Configure mock_os_makedirs to fail on the second call (which is for the 'temp' dir)
            # The first call to makedirs in run_llm_sessions.py is for the response_dir_abs
            mock_os_makedirs.side_effect = [
                None, # First call: for response_dir_abs - succeeds
                OSError("Simulated OSError creating temp dir") # Second call: for temp_dir_path - fails
            ]

            cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
            with self.assertRaises(SystemExit) as cm:
                with patch.object(sys, 'argv', cli_args), \
                     patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
                    run_sessions_main_under_test()
            
            self.assertEqual(cm.exception.code, 1)
            mock_orch_logging.error.assert_any_call(f"Could not create or clean temporary directory at {os.path.join(SRC_DIR_REAL_PROJECT, 'temp')}: Simulated OSError creating temp dir")
    
    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_no_query_files_found(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_no_queries")
        self._clear_test_output_files(test_run_dir)
        # Don't create run_queries_dir or create it empty
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True) # Ensure dir exists but leave it empty
        
        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
        module_under_test = sys.modules.get('run_llm_sessions')

        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        mock_subprocess_run.assert_not_called()
        mock_orch_logging.info.assert_any_call(f"No query files matching '{os.path.join(run_queries_dir, 'llm_query_[0-9][0-9][0-9].txt')}' found in '{run_queries_dir}'. Nothing to do.")

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_filtering_with_indices(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_indices_filter")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        # Create 5 query files
        for i in range(1, 6):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f:
                f.write(f"Query content {i:03d}")

        mock_subprocess_run.side_effect = self._worker_run_success_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        # Target only indices 2 and 4
        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir, '--indices', '2', '4']
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        self.assertEqual(mock_subprocess_run.call_count, 2)
        # Verify specific calls were made
        mock_subprocess_run.assert_any_call(
            [sys.executable, self.dummy_llm_prompter_script_path_in_test_src, "002",
             "--input_query_file", os.path.join("temp", self.test_temp_input_basename),
             "--output_response_file", os.path.join("temp", self.test_temp_response_basename),
             "--output_error_file", os.path.join("temp", self.test_temp_error_basename)],
            check=False, cwd=self.src_dir_test_temp, stdout=subprocess.PIPE, stderr=None, text=True, encoding='utf-8', errors='replace'
        )
        mock_subprocess_run.assert_any_call(
            [sys.executable, self.dummy_llm_prompter_script_path_in_test_src, "004",
             "--input_query_file", os.path.join("temp", self.test_temp_input_basename),
             "--output_response_file", os.path.join("temp", self.test_temp_response_basename),
             "--output_error_file", os.path.join("temp", self.test_temp_error_basename)],
            check=False, cwd=self.src_dir_test_temp, stdout=subprocess.PIPE, stderr=None, text=True, encoding='utf-8', errors='replace'
        )
        
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_002.txt")))
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_004.txt")))
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, "llm_response_001.txt")))
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, "llm_response_003.txt")))
        self.assertFalse(os.path.exists(os.path.join(run_responses_dir, "llm_response_005.txt")))

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_continue_run_skips_existing_success(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_continue_success")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        os.makedirs(run_responses_dir, exist_ok=True)

        # Create 3 queries
        for i in range(1, 4):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f: f.write(f"Query {i}")
        
        # Simulate index 1 and 2 already having successful responses
        with open(os.path.join(run_responses_dir, "llm_response_001.txt"), "w") as f: f.write("Response 1")
        with open(os.path.join(run_responses_dir, "llm_response_002.txt"), "w") as f: f.write("Response 2")
        
        mock_subprocess_run.side_effect = self._worker_run_success_side_effect # Worker always succeeds
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir, '--continue-run']
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        self.assertEqual(mock_subprocess_run.call_count, 1) # Only index 3 should be run
        mock_subprocess_run.assert_called_once_with(
            [sys.executable, self.dummy_llm_prompter_script_path_in_test_src, "003",
             "--input_query_file", os.path.join("temp", self.test_temp_input_basename),
             "--output_response_file", os.path.join("temp", self.test_temp_response_basename),
             "--output_error_file", os.path.join("temp", self.test_temp_error_basename)],
            check=False, cwd=self.src_dir_test_temp, stdout=subprocess.PIPE, stderr=None, text=True, encoding='utf-8', errors='replace'
        )
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_003.txt")))
        mock_orch_logging.info.assert_any_call(f"  Final response file 'llm_response_001.txt' already exists. Skipping.")
        mock_orch_logging.info.assert_any_call(f"  Final response file 'llm_response_002.txt' already exists. Skipping.")
        
    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_continue_run_skips_existing_error(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_continue_error")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        os.makedirs(run_responses_dir, exist_ok=True)

        # Create 3 queries
        for i in range(1, 4):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f: f.write(f"Query {i}")
        
        # Simulate index 1 having a successful response, index 2 having an error
        with open(os.path.join(run_responses_dir, "llm_response_001.txt"), "w") as f: f.write("Response 1")
        with open(os.path.join(run_responses_dir, "llm_response_002.error.txt"), "w") as f: f.write("Error 2")
        
        mock_subprocess_run.side_effect = self._worker_run_success_side_effect # Worker always succeeds
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir, '--continue-run']
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        self.assertEqual(mock_subprocess_run.call_count, 1) # Only index 3 should be run
        mock_subprocess_run.assert_called_once_with(
            [sys.executable, self.dummy_llm_prompter_script_path_in_test_src, "003",
             "--input_query_file", os.path.join("temp", self.test_temp_input_basename),
             "--output_response_file", os.path.join("temp", self.test_temp_response_basename),
             "--output_error_file", os.path.join("temp", self.test_temp_error_basename)],
            check=False, cwd=self.src_dir_test_temp, stdout=subprocess.PIPE, stderr=None, text=True, encoding='utf-8', errors='replace'
        )
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_003.txt")))
        mock_orch_logging.info.assert_any_call(f"  Final response file 'llm_response_001.txt' already exists. Skipping.")
        mock_orch_logging.warning.assert_any_call(f"  Final error file 'llm_response_002.error.txt' exists. Skipping.")

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_orchestrator_subprocess_exception(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_orch_exception")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        with open(os.path.join(run_queries_dir, f"llm_query_001.txt"), "w") as f: f.write("Query 1")

        mock_subprocess_run.side_effect = self._worker_throws_exception_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        mock_subprocess_run.assert_called_once()
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        expected_error_file = os.path.join(run_responses_dir, "llm_response_001.error.txt")
        self.assertTrue(os.path.exists(expected_error_file))
        with open(expected_error_file, 'r', encoding='utf-8') as f:
            content = f.read()
        self.assertIn("Orchestrator error managing worker: Simulated OSError during worker execution", content)
        mock_orch_logging.exception.assert_called_once() # Checks that logging.exception was called

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_json_parsing_failure(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_json_failure")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        for i in range(1, 3): # Two queries, one with missing tag, one with bad JSON
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f: f.write(f"Query {i}")

        mock_subprocess_run.side_effect = self._worker_json_parse_failure_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        self.assertEqual(mock_subprocess_run.call_count, 2)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_001.txt")))
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_002.txt")))

        # Check for specific warning messages from logging
        mock_orch_logging.warning.assert_any_call(f"  Could not find JSON delimiters in worker stdout for index 1.")
        mock_orch_logging.warning.assert_any_call(f"  Could not extract or save full JSON from worker stdout: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)")

    @patch('sys.stdout', new_callable=MagicMock)
    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_quiet_mode_output(self, mock_subprocess_run, mock_orch_logging, mock_stdout):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_quiet_mode")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        for i in range(1, 3):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f: f.write(f"Query {i}")

        mock_subprocess_run.side_effect = self._worker_run_success_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir, '--quiet']
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        self.assertEqual(mock_subprocess_run.call_count, 2)
        
        # Verify that logging.info/debug were NOT called by the orchestrator (only warning/error are allowed in quiet mode)
        for call_arg_list, _ in mock_orch_logging.info.call_args_list:
            # The only INFO calls allowed would be from the initial setup before quiet mode takes full effect
            # and the final summary (which is a print, not logging.info).
            # The key is to check that the per-iteration progress logs are not made via logging.info.
            self.assertFalse("Orchestrating query" in str(call_arg_list))
            self.assertFalse("LLM session for index" in str(call_arg_list))

        # Check stdout for progress messages using end="\r"
        captured_output = "".join([call.args[0] for call in mock_stdout.write.call_args_list])
        
        self.assertIn("Trial 001/2: Completed", captured_output)
        self.assertIn("Trial 002/2: Completed", captured_output)
        self.assertTrue(captured_output.count('\r') >= 2) # At least two carriage returns for updates
        self.assertIn("LLM session orchestration complete or terminated.", captured_output) # Final summary

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.format_seconds_to_time_str', wraps=format_seconds_to_time_str) # Use directly imported function
    def test_format_seconds_to_time_str_function(self, mock_format_func, mock_orch_logging):
        # Test cases for format_seconds_to_time_str
        self.assertEqual(format_seconds_to_time_str(0), "00:00")
        self.assertEqual(format_seconds_to_time_str(59), "00:59")
        self.assertEqual(format_seconds_to_time_str(60), "01:00")
        self.assertEqual(format_seconds_to_time_str(3599), "59:59")
        self.assertEqual(format_seconds_to_time_str(3600), "01:00:00")
        self.assertEqual(format_seconds_to_time_str(3661), "01:01:01")
        self.assertEqual(format_seconds_to_time_str(36000), "10:00:00")
        self.assertEqual(format_seconds_to_time_str(-10), "00:00") # Negative input
        # Note: No calls to mock_orch_logging are expected for this utility function itself.

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_temp_file_cleanup(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_cleanup")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        with open(os.path.join(run_queries_dir, f"llm_query_001.txt"), "w") as f: f.write("Query 1")
        
        temp_dir_path = os.path.join(self.src_dir_test_temp, "temp")
        os.makedirs(temp_dir_path, exist_ok=True) # Ensure it exists for test

        mock_subprocess_run.side_effect = self._worker_run_success_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        # After run, the temp directory should be empty of the specific temporary files
        self.assertFalse(os.path.exists(os.path.join(temp_dir_path, self.test_temp_input_basename)))
        self.assertFalse(os.path.exists(os.path.join(temp_dir_path, self.test_temp_response_basename)))
        self.assertFalse(os.path.exists(os.path.join(temp_dir_path, self.test_temp_error_basename)))
        
        # Check that the temp directory itself might still exist but is empty (or almost empty)
        # It's better to check for the specific files, as the dir itself might not be removed.
        # The script only removes content, not the 'temp' dir itself.
        self.assertTrue(os.path.exists(temp_dir_path))
        self.assertEqual(len(os.listdir(temp_dir_path)), 0)

    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run', side_effect=KeyboardInterrupt)
    def test_keyboard_interrupt_handling(self, mock_subprocess_run, mock_orch_logging):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_keyboard_interrupt")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        with open(os.path.join(run_queries_dir, f"llm_query_001.txt"), "w") as f: f.write("Query 1")
        
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        mock_subprocess_run.assert_called_once()
        mock_orch_logging.info.assert_any_call("\nOrchestration interrupted by user (Ctrl+C).")
        # The primary goal is to ensure graceful exit and logging on KeyboardInterrupt.
        # Temp file cleanup is verified by test_temp_file_cleanup.

    @patch('sys.stdout', new_callable=MagicMock)
    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_all_queries_fail(self, mock_subprocess_run, mock_orch_logging, mock_stdout):
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_all_fail")
        self._clear_test_output_files(test_run_dir)
        
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        # Create 2 queries, both will fail
        for i in range(1, 3):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f:
                f.write(f"Query content {i:03d}")

        mock_subprocess_run.side_effect = self._all_fail_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')

        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            run_sessions_main_under_test()
        
        self.assertEqual(mock_subprocess_run.call_count, 2)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_001.error.txt")))
        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, "llm_response_002.error.txt")))
        
        # Check that the division by zero was avoided. It should log error for each.
        mock_orch_logging.error.assert_called()
        # The summary print should indicate 0 successful sessions.
        captured_output_summary = "".join([call.args[0] for call in mock_stdout.write.call_args_list])
        self.assertIn("Summary for this run: 0 sessions got responses, 2 resulted in errors. 0 were skipped (pre-existing).", captured_output_summary)

# === End of tests/test_run_llm_sessions.py ===
