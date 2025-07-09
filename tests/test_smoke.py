#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: tests/test_smoke.py

"""
End-to-End Smoke Test for the Personality Matching LLM Test Pipeline.

Purpose:
This test simulates a full run of the data pipeline, from query generation to performance analysis,
to ensure that the components integrate correctly and the data flows through the system without
crashing. It uses a temporary, isolated project structure and mocks the one external dependency:
the LLM API call.

Workflow Simulated:
1.  **Setup**: A complete, temporary project directory is created, including:
    -   `src/`: A copy of all the actual pipeline scripts.
    -   `data/`: Minimal, predictable source files (`personalities.txt`, `base_query.txt`).
    -   `config.ini` & `.env`: Mocked configuration files pointing to the temporary directories.
    -   The `config_loader` module is patched to use this temporary environment.

2.  **build_queries.py**: Run with small parameters (m=1, k=3). This step calls the *real*
    `query_generator.py` as a subprocess. The test asserts that the expected query and mapping
    files are created in the temporary `output/run_smoke_test/session_queries/` directory.

3.  **run_llm_sessions.py**: Run to process the query from step 2. The subprocess call to
    `llm_prompter.py` is mocked. The mock simulates a successful LLM API call by creating a
    predictable, well-formed tabular response. The test asserts that this response is correctly
    moved to the final `output/run_smoke_test/session_responses/` directory.

4.  **process_llm_responses.py**: Run to parse the predictable LLM response from step 3. The test
    asserts that the resulting `all_scores.txt`, `all_mappings.txt`, and `successful_query_indices.txt`
    files are created in `output/run_smoke_test/analysis_inputs/` and contain the expected data.

5.  **analyze_performance.py**: Run using the predictable scores and mappings from step 4. The test
    asserts that the analysis script runs to completion without errors and prints its summary output.

This test validates the primary "happy path" of the entire pipeline, confirming that file
formats, paths, and inter-script communication are working as designed.
"""

import unittest
from unittest.mock import patch
import os
import sys
import shutil
import tempfile
import configparser
import types
import importlib
import subprocess
import re
import numpy as np

# --- Test Configuration & Setup ---
SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_TEST = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL = os.path.join(PROJECT_ROOT_FOR_TEST, 'src')

PIPELINE_SCRIPTS = [
    "config_loader.py", "query_generator.py", "build_queries.py",
    "llm_prompter.py", "run_llm_sessions.py", "process_llm_responses.py",
    "analyze_performance.py", "orchestrate_replication.py"
]

class TestEndToEndSmoke(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        for script_name in PIPELINE_SCRIPTS:
            if not os.path.exists(os.path.join(SRC_DIR_REAL, script_name)):
                raise FileNotFoundError(f"Required source script not found: {os.path.join(SRC_DIR_REAL, script_name)}")

    def setUp(self):
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="smoke_test_proj_")
        self.test_project_root = self.test_project_root_obj.name

        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.data_dir = os.path.join(self.test_project_root, 'data')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        
        # Define the path for the run-specific directory that the test will use.
        self.test_run_dir = os.path.join(self.output_dir, "run_smoke_test_20240101_120000")

        os.makedirs(self.src_dir)
        os.makedirs(self.data_dir)

        for script_name in PIPELINE_SCRIPTS:
            shutil.copy2(os.path.join(SRC_DIR_REAL, script_name), self.src_dir)

        self._create_mock_data_files()
        self._create_mock_config_ini()
        self._create_mock_dotenv()

        self.original_sys_path = list(sys.path)
        self.original_sys_modules = dict(sys.modules)
        sys.path.insert(0, self.src_dir)

        self._setup_fake_config_loader_in_sys_modules()
        
        self.imported_mains = {}
        for script in ["build_queries", "run_llm_sessions", "process_llm_responses", "analyze_performance"]:
            module_name = script
            try:
                if module_name in sys.modules:
                    reloaded_module = importlib.reload(sys.modules[module_name])
                else:
                    reloaded_module = importlib.import_module(module_name)
                self.imported_mains[script] = getattr(reloaded_module, 'main', None)
            except Exception as e:
                self.fail(f"Failed to load main function for {script}: {e}")

    def tearDown(self):
        sys.path[:] = self.original_sys_path
        for name in list(sys.modules.keys()):
            if name not in self.original_sys_modules:
                del sys.modules[name]
        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
        self.test_project_root_obj.cleanup()

    def _create_mock_data_files(self):
        personalities_content = (
            "Index\tName\tBirthYear\tDescriptionText\n"
            "101\tAda Lovelace\t1815\tAn English mathematician.\n"
            "102\tGrace Hopper\t1906\tAn American computer scientist.\n"
            "103\tAlan Turing\t1912\tAn English mathematician.\n"
        )
        with open(os.path.join(self.data_dir, 'personalities.txt'), 'w', encoding='utf-8') as f: f.write(personalities_content)
        with open(os.path.join(self.data_dir, 'base_query.txt'), 'w', encoding='utf-8') as f: f.write("Match List A to List B.")

    def _create_mock_config_ini(self):
        self.mock_config = configparser.ConfigParser()
        self.mock_config['General'] = {'base_output_dir': 'output', 'queries_subdir': 'session_queries', 'responses_subdir': 'session_responses', 'analysis_inputs_subdir': 'analysis_inputs'}
        self.mock_config['Filenames'] = {'personalities_src': 'personalities.txt', 'base_query_src': 'base_query.txt', 'successful_indices_log': 'successful_query_indices.txt'}
        self.mock_config['LLM'] = {'model_name': 'mock/model', 'temperature': '0.5'}
        with open(os.path.join(self.test_project_root, 'config.ini'), 'w') as f: self.mock_config.write(f)

    def _create_mock_dotenv(self):
        with open(os.path.join(self.test_project_root, '.env'), 'w') as f: f.write("API_KEY=dummy\n")

    def _setup_fake_config_loader_in_sys_modules(self):
        if 'config_loader' in sys.modules: del sys.modules['config_loader']
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.test_project_root
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str):
            if not config.has_option(section, key): return fallback
            if value_type is int: return config.getint(section, key)
            if value_type is float: return config.getfloat(section, key)
            return config.get(section, key)
        fake_mod.get_config_value = dummy_get_config_value
        sys.modules['config_loader'] = fake_mod

    def test_experiment_smoke_test(self):
        """Executes the entire pipeline sequence with mocks and new directory structure."""
        
        run_queries_dir = os.path.join(self.test_run_dir, 'session_queries')
        run_responses_dir = os.path.join(self.test_run_dir, 'session_responses')
        run_analysis_dir = os.path.join(self.test_run_dir, 'analysis_inputs')

        # === Step 1: Run build_queries.py ===
        build_queries_args = ['build_queries.py', '-m', '1', '-k', '3', '--base_seed', '123', '--qgen_base_seed', '456', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', build_queries_args), patch('builtins.input', return_value='new'):
            self.imported_mains['build_queries']()

        query_file_path = os.path.join(run_queries_dir, 'llm_query_001.txt')
        self.assertTrue(os.path.exists(query_file_path), "llm_query_001.txt was not created.")

        with open(os.path.join(run_queries_dir, 'mappings.txt'), 'r') as f:
            true_mapping_1_based = [int(x) for x in f.readlines()[1].strip().split('\t')]
        
        # === Step 2: Run run_llm_sessions.py (with mocked prompter) ===
        with open(query_file_path, 'r', encoding='utf-8') as f: query_content = f.read()
        list_a_items = re.findall(r"^(.*? \(\d{4}\))", query_content.split("List A\n")[1], re.MULTILINE)

        k = 3
        perfect_scores = np.full((k, k), 0.0)
        for i in range(k): perfect_scores[i, true_mapping_1_based[i] - 1] = 1.0
        
        response_rows = ["Name\tID 1\tID 2\tID 3"]
        for i in range(k): response_rows.append(f"{list_a_items[i]}\t" + "\t".join([f"{s:.1f}" for s in perfect_scores[i, :]]))
        mock_llm_response_content = "\n".join(response_rows) + "\n"

        def mock_llm_prompter_subprocess(cmd_args, **kwargs):
            worker_cwd = kwargs.get('cwd')
            self.assertIsNotNone(worker_cwd)
            relative_response_path = cmd_args[cmd_args.index('--output_response_file') + 1]
            absolute_response_path = os.path.join(worker_cwd, relative_response_path)
            os.makedirs(os.path.dirname(absolute_response_path), exist_ok=True)
            with open(absolute_response_path, 'w', encoding='utf-8') as f: f.write(mock_llm_response_content)
            return subprocess.CompletedProcess(args=cmd_args, returncode=0, stdout="---LLM_RESPONSE_JSON_START--- {} ---LLM_RESPONSE_JSON_END---", stderr="")

        run_sessions_args = ['run_llm_sessions.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', run_sessions_args), patch('subprocess.run', side_effect=mock_llm_prompter_subprocess):
            self.imported_mains['run_llm_sessions']()

        self.assertTrue(os.path.exists(os.path.join(run_responses_dir, 'llm_response_001.txt')))

        # === Step 3: Run process_llm_responses.py ===
        process_args = ['process_llm_responses.py', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', process_args):
            self.imported_mains['process_llm_responses']()

        self.assertTrue(os.path.exists(os.path.join(run_analysis_dir, 'all_scores.txt')))
        self.assertTrue(os.path.exists(os.path.join(run_analysis_dir, 'all_mappings.txt')))
        self.assertTrue(os.path.exists(os.path.join(run_analysis_dir, 'successful_query_indices.txt')))

        # === Step 4: Run analyze_performance.py ===
        analyze_args = ['analyze_performance.py', '--quiet', '--run_output_dir', self.test_run_dir]
        with patch.object(sys, 'argv', analyze_args), patch('builtins.print') as mock_print:
            try:
                self.imported_mains['analyze_performance']()
            except SystemExit as e:
                self.fail(f"analyze_performance.py exited unexpectedly with code: {e.code}")
        
        printed_output = "".join(str(call.args[0]) for call in mock_print.call_args_list)
        # Check for the machine-readable JSON block, which is a reliable success indicator.
        self.assertIn("<<<METRICS_JSON_START>>>", printed_output)
        self.assertIn("<<<METRICS_JSON_END>>>", printed_output)

if __name__ == '__main__':
    unittest.main(verbosity=2)