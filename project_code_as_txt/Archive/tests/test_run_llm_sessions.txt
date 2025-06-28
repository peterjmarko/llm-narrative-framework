import unittest
from unittest.mock import patch, MagicMock # Removed mock_open, call as they are not used
import os
import sys
import shutil # Keep for now, as orchestrator uses it, even if not directly mocked in happy path
import tempfile
import subprocess # For CompletedProcess
import configparser
import importlib 
import types

# Adjust path: This needs to happen at module import time for decorators to find the module
SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_SRC = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL_PROJECT = os.path.join(PROJECT_ROOT_FOR_SRC, 'src')

# Ensure SRC_DIR_REAL_PROJECT is in sys.path when this test module is first loaded
if SRC_DIR_REAL_PROJECT not in sys.path:
    sys.path.insert(0, SRC_DIR_REAL_PROJECT)
    # print(f"DEBUG (Module Level): Added {SRC_DIR_REAL_PROJECT} to sys.path")

# Global to hold the imported main function from the module under test
run_sessions_main_under_test = None

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
            if not config.has_section(section) or not config.has_option(section,key): return fallback
            # Simplified for test; real one handles type conversion
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

    def _worker_run_success_side_effect(self, cmd_list_args, **kwargs):
        query_id_from_cmd = cmd_list_args[2]
        
        # The runner script creates a 'temp' directory inside the REAL project's 'src' folder.
        # The mock must create the temp files there so the runner can find them.
        temp_dir_path = os.path.join(SRC_DIR_REAL_PROJECT, "temp")
        os.makedirs(temp_dir_path, exist_ok=True)
        worker_temp_response_path = os.path.join(temp_dir_path, self.test_temp_response_basename)

        with open(worker_temp_response_path, "w", encoding='utf-8') as f:
            f.write(f"Mocked response for {query_id_from_cmd}")
        
        mock_stdout = "---LLM_RESPONSE_JSON_START---\n{}\n---LLM_RESPONSE_JSON_END---"
        return subprocess.CompletedProcess(args=cmd_list_args, returncode=0, stdout=mock_stdout, stderr=None)

    def _worker_run_failure_side_effect(self, cmd_list_args, **kwargs):
        query_id_from_cmd = cmd_list_args[2]

        # The runner script creates a 'temp' directory inside the REAL project's 'src' folder.
        # The mock must create the temp files there so the runner can find them.
        temp_dir_path = os.path.join(SRC_DIR_REAL_PROJECT, "temp")
        os.makedirs(temp_dir_path, exist_ok=True)
        worker_temp_response_path = os.path.join(temp_dir_path, self.test_temp_response_basename)
        worker_temp_error_path = os.path.join(temp_dir_path, self.test_temp_error_basename)

        if query_id_from_cmd == "002":
            with open(worker_temp_error_path, "w", encoding='utf-8') as f:
                f.write(f"Worker simulated error for {query_id_from_cmd}")
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=1, stdout="", stderr=None)
        else:
            with open(worker_temp_response_path, "w", encoding='utf-8') as f:
                f.write(f"Mocked response for {query_id_from_cmd}")
            mock_stdout = "---LLM_RESPONSE_JSON_START---\n{}\n---LLM_RESPONSE_JSON_END---"
            return subprocess.CompletedProcess(args=cmd_list_args, returncode=0, stdout=mock_stdout, stderr=None)

    # Using string targets for patch decorators
    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_runner_happy_path(self, mock_subprocess_run, mock_orch_logging): # Note arg order
        # Define the unique directory for this test run
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_happy_path")
        
        # Call the cleanup helper for this specific directory (optional but good practice)
        self._clear_test_output_files(test_run_dir)
        
        # Create the necessary input query files for this specific test case
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        for i in range(1, self.num_test_queries + 1):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f:
                f.write(f"Query content for happy path {i:03d}")

        # Set up the mock and CLI arguments
        mock_subprocess_run.side_effect = self._worker_run_success_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')
        self.assertIsNotNone(module_under_test, "Runner module not loaded in setUp")
        
        cli_args = ['run_llm_sessions.py', '--verbose', '--run_output_dir', test_run_dir]

        # Run the main function
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            self.assertEqual(module_under_test.PROJECT_ROOT, self.test_project_root)
            self.assertIs(module_under_test.APP_CONFIG, self.mock_config_parser_obj)
            run_sessions_main_under_test()

        # Assertions
        self.assertEqual(mock_subprocess_run.call_count, self.num_test_queries)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        for i in range(1, self.num_test_queries + 1):
            idx_str = f"{i:03d}"
            expected_response_file = os.path.join(run_responses_dir, f"llm_response_{idx_str}.txt")
            self.assertTrue(os.path.exists(expected_response_file), f"{expected_response_file} not created")


    @patch('run_llm_sessions.logging')
    @patch('run_llm_sessions.subprocess.run')
    def test_runner_worker_failure(self, mock_subprocess_run, mock_orch_logging): # Note arg order
        # Define the unique directory for this test run
        test_run_dir = os.path.join(self.resolved_output_base_dir, "run_test_worker_failure")
        
        # Call the cleanup helper for this specific directory
        self._clear_test_output_files(test_run_dir)
        
        # Create the necessary input query files for this specific test case
        run_queries_dir = os.path.join(test_run_dir, self.cfg_queries_subdir_name)
        os.makedirs(run_queries_dir, exist_ok=True)
        for i in range(1, self.num_test_queries + 1):
            with open(os.path.join(run_queries_dir, f"llm_query_{i:03d}.txt"), "w") as f:
                f.write(f"Query content for failure path {i:03d}")

        # Set up the mock and CLI arguments
        mock_subprocess_run.side_effect = self._worker_run_failure_side_effect
        module_under_test = sys.modules.get('run_llm_sessions')
        self.assertIsNotNone(module_under_test, "Runner module not loaded in setUp")
        
        cli_args = ['run_llm_sessions.py', '--run_output_dir', test_run_dir]

        # Run the main function
        with patch.object(sys, 'argv', cli_args), \
             patch.object(module_under_test, 'LLM_PROMPTER_SCRIPT_NAME', self.dummy_llm_prompter_script_path_in_test_src):
            self.assertEqual(module_under_test.PROJECT_ROOT, self.test_project_root)
            run_sessions_main_under_test()

        # Assertions
        self.assertEqual(mock_subprocess_run.call_count, self.num_test_queries)
        run_responses_dir = os.path.join(test_run_dir, self.cfg_responses_subdir_name)
        for i in [1, 3]:
            idx_str = f"{i:03d}"
            expected_response_file = os.path.join(run_responses_dir, f"llm_response_{idx_str}.txt")
            self.assertTrue(os.path.exists(expected_response_file))
        failed_idx_str = "002"
        expected_error_file = os.path.join(run_responses_dir, f"llm_response_{failed_idx_str}.error.txt")
        self.assertTrue(os.path.exists(expected_error_file))

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

if __name__ == '__main__':
    unittest.main(verbosity=2)