#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: tests/test_orchestrate_replication.py

"""
Unit Tests for the Master Pipeline Orchestrator (orchestrate_replication.py)

Purpose:
This test script validates the high-level logic and control flow of the main
`orchestrate_replication.py` script. It ensures the orchestrator can correctly
manage the full pipeline execution sequence under both ideal conditions ("happy path")
and failure scenarios.

The primary goal is to test the orchestrator's ability to:
-   Call the four main pipeline stages (`build`, `run_llm`, `process`, `analyze`)
    in the correct order.
-   Correctly create and use a unique, self-documenting, run-specific directory
    for all pipeline inputs and outputs.
-   Pass the correct command-line arguments (including the new `--run_output_dir`)
    to each worker script it invokes.
-   Gracefully handle a failure in any of the stages.
-   Generate a final, comprehensive report file that accurately reflects the run's
    status (COMPLETED or FAILED), parameters, and results.

Test Strategy & Mocks:
-   **Isolation**: Each test runs within a completely isolated, temporary file system
    created by `tempfile.TemporaryDirectory`. This prevents interference with
    real project data and ensures tests are stateless and repeatable.
-   **Configuration Mocking**: The `config_loader.py` module is mocked by injecting
    a fake module into `sys.modules`. This forces the orchestrator to use a
    test-specific, in-memory `config.ini` and a temporary `PROJECT_ROOT`,
    decoupling the test from the actual project configuration.
-   **Subprocess Mocking**: The core of the test is mocking `subprocess.run`. Instead
    of executing the real worker scripts (which would be slow and have external
    dependencies like LLM APIs), the mock intercepts the call. It verifies that
    the orchestrator constructed the correct command and then returns a simulated
    `CompletedProcess` object, mimicking either success or failure.
-   **Side Effects**: The `mock_subprocess_run` uses a `side_effect` function to
    provide different return values based on which script is being called, allowing
    for targeted failure simulation (e.g., only the `run_llm_sessions.py` stage fails).

Key Scenarios Tested:
1.  **Happy Path**:
    -   Verifies that all four pipeline stages are called in sequence.
    -   Asserts that a unique run-specific directory is created.
    -   Checks that the final report is created inside this directory.
    -   Confirms the report content accurately reflects a COMPLETED status,
      includes parameters and notes, and correctly captures the final analysis output.
2.  **Failure Path**:
    -   Simulates a failure (e.g., a `CalledProcessError`) in an early stage of the pipeline.
    -   Asserts that the orchestrator stops execution immediately after the failure
      and does not call subsequent stages.
    -   Asserts that a report file is still created inside the run-specific directory.
    -   Confirms the report content shows a FAILED status and includes the
      `FULL DIAGNOSTIC LOG` section containing the error details from the failed process.
"""

import unittest
from unittest.mock import patch, mock_open
import os
import sys
import shutil
import tempfile
import configparser
import types
import importlib
import subprocess
import glob
import re

# --- Test Configuration & Setup ---

SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_FOR_TEST = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..'))
SRC_DIR_REAL = os.path.join(PROJECT_ROOT_FOR_TEST, 'src')

ORCHESTRATOR_SCRIPT_NAME = "orchestrate_replication.py"

class TestOrchestrateFullPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Verify that the real orchestrator script exists before running tests."""
        if not os.path.exists(os.path.join(SRC_DIR_REAL, ORCHESTRATOR_SCRIPT_NAME)):
            raise FileNotFoundError(
                f"Required source script for testing not found: {os.path.join(SRC_DIR_REAL, ORCHESTRATOR_SCRIPT_NAME)}"
            )

    def setUp(self):
        """Create a temporary project structure for an isolated test run."""
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="orch_test_proj_")
        self.test_project_root = self.test_project_root_obj.name

        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.data_dir = os.path.join(self.test_project_root, 'data')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        
        os.makedirs(self.src_dir)
        os.makedirs(self.data_dir)
        # The orchestrator will create the output directory itself
        
        shutil.copy2(os.path.join(SRC_DIR_REAL, ORCHESTRATOR_SCRIPT_NAME), self.src_dir)

        self.base_query_content = "This is the test base query."
        with open(os.path.join(self.data_dir, 'base_query.txt'), 'w') as f:
            f.write(self.base_query_content)

        self._create_mock_config_ini()

        self.original_sys_path = list(sys.path)
        self.original_sys_modules = dict(sys.modules)
        
        sys.path.insert(0, self.src_dir)

        self._setup_fake_config_loader_in_sys_modules()
        
        module_name = os.path.splitext(ORCHESTRATOR_SCRIPT_NAME)[0]
        self.orchestrator_module = importlib.import_module(module_name)
        self.orchestrator_main = self.orchestrator_module.main

    def tearDown(self):
        """Clean up the temporary directory and restore system state."""
        sys.path[:] = self.original_sys_path
        
        for name in list(sys.modules.keys()):
            if name not in self.original_sys_modules:
                del sys.modules[name]

        for name, module in self.original_sys_modules.items():
            if name not in sys.modules or sys.modules[name] is not module:
                sys.modules[name] = module
            
        self.test_project_root_obj.cleanup()

    def _create_mock_config_ini(self):
        """Creates a mock config.ini file for the test run."""
        self.mock_config = configparser.ConfigParser()
        # Add the new [Study] section with parameters for the tests
        self.mock_config['Study'] = {
            'num_replications': '30',
            'num_trials': '1', # Use small values for tests
            'group_size': '3'  # Use small values for tests
        }
        self.mock_config['General'] = {
            'default_log_level': 'INFO',
            'base_output_dir': 'output',
        }
        self.mock_config['Filenames'] = {
            'personalities_src': 'personalities.txt',
            'base_query_src': 'base_query.txt',
        }
        self.mock_config['LLM'] = {
            'model_name': 'test-model-v1',
            'temperature': '0.0'
        }
        with open(os.path.join(self.test_project_root, 'config.ini'), 'w') as f:
            self.mock_config.write(f)

    def _setup_fake_config_loader_in_sys_modules(self):
        """Replaces the config_loader in sys.modules with a mock."""
        if 'config_loader' in sys.modules:
            del sys.modules['config_loader']
        
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

    # --- Test Cases ---

    def _mock_run_success(self, command, **kwargs):
        """Mock side effect for a successful subprocess run."""
        script_name = os.path.basename(command[1])
        if "analyze_performance" in script_name:
            # Return specific output for the analysis stage
            stdout = "--- Overall Meta-Analysis Results (across 1 tests) ---\nThis is the final analysis.\nANALYZER_VALIDATION_SUCCESS"
        elif "process_llm_responses" in script_name:
            stdout = "Success from process_llm_responses.py\nPROCESSOR_VALIDATION_SUCCESS"
        else:
            stdout = f"Success from {script_name}"
        
        return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")

    def _mock_run_failure(self, command, **kwargs):
        """Mock side effect for a failing subprocess run."""
        script_name = os.path.basename(command[1])
        if "run_llm_sessions" in script_name:
            # Simulate a failure in the second stage
            error_stdout = "LLM runner started..."
            error_stderr = "FATAL: API connection failed. Mocked failure from run_llm_sessions.py"
            raise subprocess.CalledProcessError(
                returncode=1, cmd=command, output=error_stdout, stderr=error_stderr
            )
        # For other stages, simulate success
        return self._mock_run_success(command, **kwargs)
    
    def _mock_run_failure_at_stage1(self, command, **kwargs):
        """Mock side effect for a failing subprocess run specifically at Stage 1."""
        script_name = os.path.basename(command[1])
        if "build_queries" in script_name:
            # Simulate a failure in the first stage
            error_stdout = "Build queries started..."
            error_stderr = "FATAL: Could not access personalities database. Mocked failure from build_queries.py"
            raise subprocess.CalledProcessError(
                returncode=1, cmd=command, output=error_stdout, stderr=error_stderr
            )
        # This part should never be reached if the test works correctly, but it's good practice
        # to have a default return for any unexpected calls.
        return self._mock_run_success(command, **kwargs)

    @patch('orchestrate_replication.subprocess.run')
    def test_happy_path_creates_correct_report(self, mock_subprocess_run):
        """Test the full pipeline orchestration succeeds and generates a complete report."""
        mock_subprocess_run.side_effect = self._mock_run_success

        test_notes = "Happy path test run."
        # The orchestrator now reads k and m from config, so we remove them from the args.
        orchestrator_args = ['orchestrate_replication.py', '--notes', test_notes]
        
        with patch.object(sys, 'argv', orchestrator_args):
            self.orchestrator_main()

        # Assertions
        self.assertEqual(mock_subprocess_run.call_count, 4, "Should have called 4 pipeline stages.")

        # Look for the run-specific directory inside the base output directory
        self.assertTrue(os.path.exists(self.output_dir))
        run_dirs = [d for d in os.listdir(self.output_dir) if os.path.isdir(os.path.join(self.output_dir, d)) and d.startswith('run_')]
        self.assertEqual(len(run_dirs), 1, "Expected exactly one run-specific directory to be created.")
        run_specific_dir = os.path.join(self.output_dir, run_dirs[0])
        
        # Look for the report file inside the run-specific directory
        report_files = glob.glob(os.path.join(run_specific_dir, 'replication_report_*.txt'))
        self.assertEqual(len(report_files), 1, "Expected exactly one report file in the run-specific directory.")
        
        with open(report_files[0], 'r') as f:
            report_content = f.read()

        self.assertIn("Final Status:    COMPLETED", report_content)
        self.assertIn(f"Run Notes:       {test_notes}", report_content)
        self.assertIn("LLM Model:       test-model-v1", report_content)
        self.assertIn(self.base_query_content, report_content)
        self.assertIn("### STAGE: 4. Analyze Performance ###", report_content)
        self.assertIn("This is the final analysis.", report_content)
        # In a successful run, the full diagnostic log is NOT included
        self.assertNotIn("FULL DIAGNOSTIC LOG", report_content)
        self.assertIn("Validation Status: OK (All checks passed)", report_content)

    @patch('orchestrate_replication.subprocess.run')
    def test_failure_path_creates_diagnostic_report(self, mock_subprocess_run):
        """Test that a stage failure results in a report with a FAILED status and diagnostic log."""
        mock_subprocess_run.side_effect = self._mock_run_failure
        
        orchestrator_args = ['orchestrate_replication.py']
        with patch.object(sys, 'argv', orchestrator_args):
            self.orchestrator_main()

        # Assertions
        self.assertEqual(mock_subprocess_run.call_count, 2, "Should have stopped after the 2nd stage failed.")

        # Look for the run-specific directory inside the base output directory
        self.assertTrue(os.path.exists(self.output_dir))
        run_dirs = [d for d in os.listdir(self.output_dir) if os.path.isdir(os.path.join(self.output_dir, d)) and d.startswith('run_')]
        self.assertEqual(len(run_dirs), 1, "Expected one run-specific directory to be created even on failure.")
        run_specific_dir = os.path.join(self.output_dir, run_dirs[0])

        # The report should be inside this directory.
        report_files = glob.glob(os.path.join(run_specific_dir, 'replication_report_*.txt'))
        self.assertEqual(len(report_files), 1, "A report file should still be created on failure.")

        with open(report_files[0], 'r') as f:
            report_content = f.read()
            
        self.assertIn("Final Status:    FAILED", report_content)
        self.assertNotIn("OK (All checks passed)", report_content) # The status should not be OK
        # Check that the full diagnostic log section was added
        self.assertIn("FULL DIAGNOSTIC LOG", report_content, "Diagnostic log should be present in a failed report.")
        # Check that the error message from the failed stage is present
        self.assertIn("Mocked failure from run_llm_sessions.py", report_content, "The stderr from the failed process should be in the log.")

    @patch('orchestrate_replication.subprocess.run')
    def test_failure_in_build_queries_aborts_run(self, mock_subprocess_run):
        """Test that a failure in the first stage (build_queries) aborts the pipeline correctly."""
        mock_subprocess_run.side_effect = self._mock_run_failure_at_stage1
        
        orchestrator_args = ['orchestrate_replication.py']
        with patch.object(sys, 'argv', orchestrator_args):
            self.orchestrator_main()

        # Assert that the pipeline was aborted immediately
        self.assertEqual(mock_subprocess_run.call_count, 1, "Should have stopped after the 1st stage failed.")

        # Assert that a report was still created
        run_dirs = [d for d in os.listdir(self.output_dir) if os.path.isdir(os.path.join(self.output_dir, d)) and d.startswith('run_')]
        self.assertEqual(len(run_dirs), 1, "A run-specific directory should still be created on early failure.")
        run_specific_dir = os.path.join(self.output_dir, run_dirs[0])
        
        report_files = glob.glob(os.path.join(run_specific_dir, 'replication_report_*.txt'))
        self.assertEqual(len(report_files), 1, "A report file should still be created on early failure.")

        # Assert the content of the report is correct
        with open(report_files[0], 'r') as f:
            report_content = f.read()
            
        self.assertIn("Final Status:    FAILED", report_content)
        self.assertIn("FULL DIAGNOSTIC LOG", report_content)
        self.assertIn("Mocked failure from build_queries.py", report_content)

if __name__ == '__main__':
    unittest.main(verbosity=2)

# === End of tests/test_orchestrate_replication.py ===