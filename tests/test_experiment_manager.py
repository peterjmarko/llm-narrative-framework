#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
# Filename: tests/test_experiment_manager.py

import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import shutil
import tempfile
import configparser
import subprocess

# Ensure src is in path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src import experiment_manager

class TestExperimentManagerState(unittest.TestCase):
    """
    Tests the state-machine logic of experiment_manager.py by mocking
    the state-determination and mode-execution helper functions.
    """

    def setUp(self):
        """Set up a temporary directory and mock configuration."""
        self.test_dir = tempfile.mkdtemp(prefix="exp_manager_state_")
        
        self.mock_config = configparser.ConfigParser()
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir)

        self.mock_config.read_dict({
            'Study': {'num_replications': '1'},
            'General': {
                'base_output_dir': 'output', # Relative path
                'new_experiments_subdir': 'new_exps',
                'experiment_dir_prefix': 'exp_'
            },
            'Filenames': {'batch_run_log': 'batch_run_log.csv'}
        })

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _get_config_side_effect(self, config_obj, section, key, **kwargs):
        """Helper to safely get values from the mock_config."""
        if self.mock_config.has_option(section, key):
            val = self.mock_config.get(section, key)
            value_type = kwargs.get('value_type', str)
            return value_type(val)
        return kwargs.get('fallback', None)

    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager._get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    @patch('src.experiment_manager.subprocess.run')
    def test_new_to_complete_flow(self, mock_subprocess, mock_get_config, mock_get_state, mock_new, mock_repair, mock_reprocess):
        """Tests that state NEW_NEEDED correctly calls the new_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = [
            ("NEW_NEEDED", {"missing_reps": 1}),
            ("COMPLETE", None)
        ]
        
        cli_args = ['script.py', self.test_dir]
        with patch.object(sys, 'argv', cli_args):
            experiment_manager.main()

        mock_new.assert_called_once()
        mock_repair.assert_not_called()
        mock_reprocess.assert_not_called()
        # Check that finalization runs
        self.assertTrue(any("compile_study_results.py" in str(c) for c in mock_subprocess.call_args_list))

    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager._get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    @patch('src.experiment_manager.subprocess.run')
    def test_repair_to_complete_flow(self, mock_subprocess, mock_get_config, mock_get_state, mock_new, mock_repair, mock_reprocess):
        """Tests that state REPAIR_NEEDED correctly calls the repair_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = [
            ("REPAIR_NEEDED", [{"dir": "run_1", "failed_indices": [1]}]),
            ("COMPLETE", None)
        ]
        
        cli_args = ['script.py', self.test_dir]
        with patch.object(sys, 'argv', cli_args):
            experiment_manager.main()

        mock_repair.assert_called_once()
        mock_new.assert_not_called()
        mock_reprocess.assert_not_called()
        self.assertTrue(any("compile_study_results.py" in str(c) for c in mock_subprocess.call_args_list))
    
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager._get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    @patch('src.experiment_manager.subprocess.run')
    def test_reprocess_to_complete_flow(self, mock_subprocess, mock_get_config, mock_get_state, mock_new, mock_repair, mock_reprocess):
        """Tests that state REPROCESS_NEEDED correctly calls the reprocess_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = [
            ("REPROCESS_NEEDED", [{"dir": "run_1"}]),
            ("COMPLETE", None)
        ]

        cli_args = ['script.py', self.test_dir]
        with patch.object(sys, 'argv', cli_args):
            experiment_manager.main()
        
        mock_reprocess.assert_called_once()
        mock_new.assert_not_called()
        mock_repair.assert_not_called()
        self.assertTrue(any("compile_study_results.py" in str(c) for c in mock_subprocess.call_args_list))

    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_max_loops_exceeded(self, mock_get_config, mock_get_state, mock_run_repair):
        """Test that the manager halts if it gets stuck in a loop."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("REPAIR_NEEDED", [{"dir": "run_1", "failed_indices": [1]}])
        
        cli_args = ['script.py', self.test_dir, '--max-loops', '3']
        with patch('sys.exit') as mock_exit, \
             patch('builtins.print') as mock_print:
            with patch.object(sys, 'argv', cli_args):
                experiment_manager.main()
        
        self.assertEqual(mock_run_repair.call_count, 3)
        mock_print.assert_any_call("\033[91m--- Max loop count reached. Halting to prevent infinite loop. ---\033[0m")
        mock_exit.assert_called_with(1)

    @patch('src.experiment_manager._get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_unhandled_state_halts(self, mock_get_config, mock_get_state):
        """
        Test that an INCONSISTENT or UNKNOWN state causes a halt.
        """
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("INCONSISTENT", {"details": "something is wrong"})
        
        cli_args = ['script.py', self.test_dir]
        with patch('sys.exit') as mock_exit, \
             patch('builtins.print') as mock_print:
            with patch.object(sys, 'argv', cli_args):
                experiment_manager.main()
                
        mock_print.assert_any_call("\033[91m--- Unhandled or inconsistent state detected: INCONSISTENT. Halting. ---\033[0m")
        mock_exit.assert_called_with(1)

    @patch('src.experiment_manager._run_new_mode', return_value=False)
    @patch('src.experiment_manager._get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_mode_failure_halts_execution(self, mock_get_config, mock_get_state, mock_new):
        """Tests that if a mode function returns False, the manager halts."""
        mock_get_config.side_effect = self._get_config_side_effect
        # After the first attempt, the state doesn't change, but the loop should exit.
        mock_get_state.side_effect = [
            ("NEW_NEEDED", {}), 
            ("COMPLETE", None) # Lets the loop terminate after failure.
        ]

        cli_args = ['script.py', self.test_dir]
        with patch('sys.exit') as mock_exit, \
             patch('builtins.print') as mock_print:
            with patch.object(sys, 'argv', cli_args):
                experiment_manager.main()

        mock_new.assert_called_once()
        mock_print.assert_any_call("\033[91m--- A step failed. Halting experiment manager. Please review logs. ---\033[0m")
        mock_exit.assert_called_with(1)

    @patch('src.experiment_manager._get_experiment_state', return_value=("COMPLETE", None))
    @patch('src.experiment_manager.get_config_value')
    @patch('src.experiment_manager.datetime')
    @patch('src.experiment_manager.subprocess.run')
    def test_default_directory_creation(self, mock_subprocess, mock_datetime, mock_get_config, mock_get_state):
        """Tests that a default directory is created when none is specified."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_datetime.datetime.now.return_value.strftime.return_value = "20240101_120000"

        # Note: No target_dir in cli_args
        cli_args = ['script.py']
        with patch('sys.exit'), patch('builtins.print') as mock_print, \
             patch.object(sys, 'argv', cli_args):
            # We now mock PROJECT_ROOT to point to our temp dir for this test
            with patch('src.experiment_manager.PROJECT_ROOT', self.test_dir):
                experiment_manager.main()

        # Check if the print call for creating the directory contains the expected path
        found_message = False
        expected_path_fragment = os.path.join(self.test_dir, 'output', 'new_exps', 'exp_20240101_120000')
        for call_args in mock_print.call_args_list:
            if "No target directory specified" in call_args[0][0] and expected_path_fragment in call_args[0][0]:
                found_message = True
                break
        self.assertTrue(found_message, "Default directory creation message not found or incorrect.")

class TestExperimentManagerVerification(unittest.TestCase):
    """
    Tests the verification logic of experiment_manager.py against
    a simulated filesystem to validate edge case handling.
    """
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="exp_manager_verify_")
        # Example run dir with m=3 trials and k=4 subjects per trial
        self.run_dir = os.path.join(self.test_dir, "run_20240101_120000_rep-001_model-x_sbj-04_trl-003")
        os.makedirs(os.path.join(self.run_dir, "session_queries"))
        os.makedirs(os.path.join(self.run_dir, "session_responses"))
        os.makedirs(os.path.join(self.run_dir, "analysis_inputs"))

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _create_files(self, path, prefix, count):
        """Helper to create a number of mock trial files."""
        for i in range(1, count + 1):
            with open(os.path.join(path, f"{prefix}_{i:03d}.txt"), 'w') as f:
                f.write(f"content {i}")
    
    def _create_matrix_file(self, path, num_matrices, k):
        """Helper to create a mock scores file."""
        with open(path, 'w') as f:
            for _ in range(num_matrices):
                for _ in range(k):
                    f.write("\t".join([str(x/10) for x in range(k)]) + "\n")

    def test_verify_state_complete(self):
        """Test verification correctly identifies a complete run."""
        self._create_files(os.path.join(self.run_dir, "session_queries"), "llm_query", 3)
        self._create_files(os.path.join(self.run_dir, "session_responses"), "llm_response", 3)
        self._create_matrix_file(os.path.join(self.run_dir, "analysis_inputs", "all_scores.txt"), 3, 4)
        with open(os.path.join(self.run_dir, "analysis_inputs", "all_mappings.txt"), 'w') as f:
            f.write("header\n" * 4) # 1 header + 3 data lines
        
        result = experiment_manager._verify_single_run_completeness(self.run_dir)
        self.assertEqual(result['status'], 'COMPLETE')

    def test_verify_state_repair_needed(self):
        """Test verification correctly identifies a run needing API call repair."""
        self._create_files(os.path.join(self.run_dir, "session_queries"), "llm_query", 3)
        self._create_files(os.path.join(self.run_dir, "session_responses"), "llm_response", 2) # Missing one response

        result = experiment_manager._verify_single_run_completeness(self.run_dir)
        self.assertEqual(result['status'], 'REPAIR_NEEDED')
        self.assertEqual(result['failed_indices'], [3])

    def test_verify_state_reprocess_needed(self):
        """Test verification correctly identifies a run needing analysis reprocessing."""
        self._create_files(os.path.join(self.run_dir, "session_queries"), "llm_query", 3)
        self._create_files(os.path.join(self.run_dir, "session_responses"), "llm_response", 3)
        self._create_matrix_file(os.path.join(self.run_dir, "analysis_inputs", "all_scores.txt"), 2, 4) # Missing one matrix
        
        result = experiment_manager._verify_single_run_completeness(self.run_dir)
        self.assertEqual(result['status'], 'REPROCESS_NEEDED')

    def test_verify_state_new(self):
        """Test verification correctly identifies a new (empty) run directory."""
        result = experiment_manager._verify_single_run_completeness(self.run_dir)
        self.assertEqual(result['status'], 'NEW')

    def test_verify_state_invalid_name(self):
        """Test verification handles directories with invalid names."""
        invalid_dir = os.path.join(self.test_dir, "not_a_valid_run_dir")
        os.makedirs(invalid_dir)
        result = experiment_manager._verify_single_run_completeness(invalid_dir)
        self.assertEqual(result['status'], 'INVALID_NAME')

    def test_verify_state_inconsistent(self):
        """Test verification correctly identifies an inconsistent run (e.g., more matrices than expected)."""
        # To reach the INCONSISTENT state, all prior checks must pass.
        self._create_files(os.path.join(self.run_dir, "session_queries"), "llm_query", 3)
        self._create_files(os.path.join(self.run_dir, "session_responses"), "llm_response", 3)
        self._create_matrix_file(os.path.join(self.run_dir, "analysis_inputs", "all_scores.txt"), 4, 4) # More matrices
        with open(os.path.join(self.run_dir, "analysis_inputs", "all_mappings.txt"), 'w') as f:
            f.write("header\n" * 5) # More mappings
        
        result = experiment_manager._verify_single_run_completeness(self.run_dir)
        self.assertEqual(result['status'], 'INCONSISTENT')

class TestExperimentManagerModeExecution(unittest.TestCase):
    """
    Tests the mode-execution helper functions (_run_new_mode, etc.)
    to ensure they call subprocesses with the correct arguments.
    """
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="exp_manager_modes_")
        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {'num_replications': '1', 'group_size': '4'},
            'General': {'base_output_dir': self.test_dir}
        })

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _get_config_side_effect(self, config_obj, section, key, **kwargs):
        """Helper to safely get values from the mock_config."""
        if self.mock_config.has_option(section, key):
            val = self.mock_config.get(section, key)
            value_type = kwargs.get('value_type', str)
            return value_type(val)
        return kwargs.get('fallback', None)

    @patch('src.experiment_manager.subprocess.run', return_value=MagicMock(returncode=0))
    def test_run_new_mode_calls_scripts_correctly(self, mock_subprocess):
        """Ensure _run_new_mode calls orchestrator and bias analysis."""

        def glob_side_effect(pattern):
            # This pattern is ONLY used when searching for the run dir for bias analysis
            if 'run_*_rep-001_*' in pattern and 'isdir' not in str(pattern):
                return [os.path.join(self.test_dir, "run_..._rep-001_...")]
            # This is the general pattern for finding completed reps
            elif 'run_*_rep-*' in pattern:
                return []
            return []

        with patch('src.experiment_manager.glob.glob', side_effect=glob_side_effect), \
             patch('src.experiment_manager.get_config_value', side_effect=self._get_config_side_effect), \
             patch('os.path.isdir', return_value=True):
            result = experiment_manager._run_new_mode(self.test_dir, 1, 1, "test_notes", False, "orch.py", "bias.py")

        self.assertTrue(result)
        # Check that orchestrator was called
        orch_call = next((c for c in mock_subprocess.call_args_list if "orch.py" in c.args[0]), None)
        self.assertIsNotNone(orch_call)
        self.assertIn("--replication_num", orch_call.args[0])
        self.assertIn("test_notes", orch_call.args[0])
        # Check that bias analysis was called
        bias_call = next((c for c in mock_subprocess.call_args_list if "bias.py" in c.args[0]), None)
        self.assertIsNotNone(bias_call)

    @patch('src.experiment_manager.subprocess.run', return_value=MagicMock(returncode=0))
    def test_run_reprocess_mode_calls_scripts_correctly(self, mock_subprocess):
        """Ensure _run_reprocess_mode calls orchestrator with --reprocess."""
        run_info = {"dir": self.test_dir}
        # Create a mock archived config for bias analysis to read
        with open(os.path.join(self.test_dir, 'config.ini.archived'), 'w') as f:
            f.write('[Study]\ngroup_size=4\n')

        with patch('src.experiment_manager.get_config_value', side_effect=self._get_config_side_effect):
             result = experiment_manager._run_reprocess_mode([run_info], "test_notes", False, "orch.py", "bias.py")

        self.assertTrue(result)
        # Check that orchestrator was called with reprocess flag
        orch_call = next((c for c in mock_subprocess.call_args_list if "orch.py" in c.args[0]), None)
        self.assertIsNotNone(orch_call)
        self.assertIn("--reprocess", orch_call.args[0])

    @patch('src.experiment_manager.subprocess.run')
    def test_repair_worker_handles_failure(self, mock_subprocess):
        """Ensure the _repair_worker function correctly reports failures."""
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, "cmd", "output", "stderr")
        
        index, success, error_log = experiment_manager._repair_worker("run_dir", "script.py", 1, True)
        
        self.assertEqual(index, 1)
        self.assertFalse(success)
        self.assertIn("REPAIR FAILED", error_log)


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_experiment_manager.py ===
