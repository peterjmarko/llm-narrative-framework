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
# Filename: tests/test_experiment_manager.py

import unittest
from unittest.mock import patch, MagicMock, call
import os
import sys
import shutil
import tempfile
import configparser
import subprocess
from pathlib import Path

# Ensure src is in path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from src import experiment_manager

class TestExperimentManagerStateTransitions(unittest.TestCase):
    """
    Tests the main state-machine loop of experiment_manager.py by mocking
    the get_experiment_state function and all _run_* helper functions.
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
                'base_output_dir': 'output',
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

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_new_needed_calls_new_mode(self, mock_get_config, mock_get_state, mock_new, mock_session_repair, mock_config_repair, mock_full_repair, mock_reprocess, mock_finalize):
        """Tests that state NEW_NEEDED correctly calls the _run_new_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = [("NEW_NEEDED", {}, ""), ("COMPLETE", {}, "")]
        
        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_new.assert_called_once()
        mock_session_repair.assert_not_called()
        mock_reprocess.assert_not_called()
        mock_finalize.assert_called_once()

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_repair_needed_calls_session_repair(self, mock_get_config, mock_get_state, mock_new, mock_session_repair, mock_config_repair, mock_full_repair, mock_reprocess, mock_finalize):
        """Tests that REPAIR_NEEDED with 'session_repair' calls the correct helper."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [{"repair_type": "session_repair", "dir": "run_1"}]
        mock_get_state.side_effect = [("REPAIR_NEEDED", payload, ""), ("COMPLETE", {}, "")]
        
        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_session_repair.assert_called_once()
        mock_config_repair.assert_not_called()
        mock_full_repair.assert_not_called()
        mock_finalize.assert_called_once()

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_repair_needed_calls_config_repair(self, mock_get_config, mock_get_state, mock_new, mock_session_repair, mock_config_repair, mock_full_repair, mock_reprocess, mock_finalize):
        """Tests that REPAIR_NEEDED with 'config_repair' calls the correct helper."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [{"repair_type": "config_repair", "dir": "run_1"}]
        mock_get_state.side_effect = [("REPAIR_NEEDED", payload, ""), ("COMPLETE", {}, "")]
        
        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_config_repair.assert_called_once()
        mock_session_repair.assert_not_called()
        mock_full_repair.assert_not_called()
        mock_finalize.assert_called_once()

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_repair_needed_calls_full_repair(self, mock_get_config, mock_get_state, mock_new, mock_session_repair, mock_config_repair, mock_full_repair, mock_reprocess, mock_finalize):
        """Tests that REPAIR_NEEDED with 'full_replication_repair' calls the correct helper."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [{"repair_type": "full_replication_repair", "dir": "run_1"}]
        mock_get_state.side_effect = [("REPAIR_NEEDED", payload, ""), ("COMPLETE", {}, "")]
        
        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_full_repair.assert_called_once()
        mock_session_repair.assert_not_called()
        mock_config_repair.assert_not_called()
        mock_finalize.assert_called_once()
    
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_reprocess_needed_calls_reprocess_mode(self, mock_get_config, mock_get_state, mock_new, mock_reprocess, mock_finalize):
        """Tests that state REPROCESS_NEEDED correctly calls the reprocess_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = [("REPROCESS_NEEDED", [{"dir": "run_1"}], ""), ("COMPLETE", {}, "")]

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()
        
        mock_reprocess.assert_called_once()
        mock_new.assert_not_called()
        mock_finalize.assert_called_once()

    @patch('pathlib.Path.glob', return_value=[MagicMock(is_dir=lambda: True, name='run_001')])
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_reprocess_flag_forces_reprocessing_on_complete_state(self, mock_get_config, mock_get_state, mock_reprocess, mock_finalize, mock_glob):
        """Tests that the --reprocess flag forces reprocessing even if state is COMPLETE."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("COMPLETE", [], "")

        with patch.object(sys, 'argv', ['script.py', self.test_dir, '--reprocess']):
            experiment_manager.main()

        mock_reprocess.assert_called_once()
        mock_finalize.assert_called_once()

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_new_mode', return_value=False) # Simulate failure
    @patch('src.experiment_manager.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_main_loop_halts_on_mode_failure(self, mock_get_config, mock_get_state, mock_new_mode, mock_finalize):
        """Tests that the main loop exits if a helper function returns False."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("NEW_NEEDED", {}, "")

        with patch('sys.exit') as mock_exit, \
             patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_new_mode.assert_called_once()
        mock_finalize.assert_not_called() # Crucial: finalization should NOT run on failure
        mock_exit.assert_called_with(1)


class TestModeExecutionHelpers(unittest.TestCase):
    """
    Tests the individual _run_* helper functions to ensure they call
    subprocesses with the correct arguments and logic.
    """
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="exp_manager_modes_")
        self.colors = {'cyan': '', 'green': '', 'yellow': '', 'red': '', 'reset': ''}
        # Create a dummy orchestrator script path for the functions to use
        self.orchestrator_script = os.path.join(self.test_dir, "orchestrate_replication.py")
        Path(self.orchestrator_script).touch()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.experiment_manager.subprocess.Popen')
    @patch('glob.glob', return_value=[])
    def test_run_new_mode_constructs_correct_command(self, mock_glob, mock_popen):
        """Ensure _run_new_mode calls orchestrator with correct base arguments."""
        mock_proc = MagicMock()
        mock_proc.stdout = []
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        # Call the function under test
        success = experiment_manager._run_new_mode(
            target_dir=self.test_dir,
            start_rep=1,
            end_rep=1,
            notes="test notes",
            verbose=True,
            orchestrator_script=self.orchestrator_script,
            colors=self.colors
        )

        self.assertTrue(success)
        mock_popen.assert_called_once()
        args, _ = mock_popen.call_args
        command_list = args[0]

        # Verify the command arguments
        self.assertIn(sys.executable, command_list)
        self.assertIn(self.orchestrator_script, command_list)
        self.assertIn("--replication_num", command_list)
        self.assertIn("1", command_list)
        self.assertIn("--base_output_dir", command_list)
        self.assertIn(self.test_dir, command_list)
        self.assertIn("--notes", command_list)
        self.assertIn("test notes", command_list)
        self.assertIn("--verbose", command_list)

    @patch('src.experiment_manager.subprocess.run')
    def test_run_reprocess_mode_constructs_correct_command(self, mock_subprocess):
        """Ensure _run_reprocess_mode calls orchestrator with the --reprocess flag."""
        run_info = [{"dir": self.test_dir}]
        
        # Call the function under test
        success = experiment_manager._run_reprocess_mode(
            runs_to_reprocess=run_info,
            notes="reprocess notes",
            verbose=True,
            orchestrator_script=self.orchestrator_script,
            compile_script=None, # Not used in the refactored function
            target_dir=self.test_dir,
            log_manager_script=None, # Not used
            colors=self.colors
        )
        
        self.assertTrue(success)
        mock_subprocess.assert_called_once()
        args, _ = mock_subprocess.call_args
        command_list = args[0]
        
        # Verify the command arguments
        self.assertIn(self.orchestrator_script, command_list)
        self.assertIn("--reprocess", command_list)
        self.assertIn("--run_output_dir", command_list)
        self.assertIn(self.test_dir, command_list)
        self.assertIn("--verbose", command_list)
        self.assertIn("--notes", command_list)
        self.assertIn("reprocess notes", command_list)


    @patch('src.experiment_manager.subprocess.run')
    def test_run_repair_mode_constructs_correct_command(self, mock_subprocess):
        """Ensure _run_repair_mode calls orchestrator with --reprocess and indices."""
        run_info = [{"dir": self.test_dir, "failed_indices": [1, 5, 10]}]
        
        success = experiment_manager._run_repair_mode(
            runs_to_repair=run_info,
            orchestrator_script_path=self.orchestrator_script,
            verbose=True,
            colors=self.colors
        )
        
        self.assertTrue(success)
        mock_subprocess.assert_called_once()
        args, _ = mock_subprocess.call_args
        command_list = args[0]
        
        # Verify the command arguments
        self.assertIn("--reprocess", command_list)
        self.assertIn("--run_output_dir", command_list)
        self.assertIn(self.test_dir, command_list)
        self.assertIn("--indices", command_list)
        self.assertIn("1", command_list)
        self.assertIn("5", command_list)
        self.assertIn("10", command_list)
        self.assertIn("--verbose", command_list)

    @patch('shutil.rmtree')
    @patch('src.experiment_manager.subprocess.run')
    def test_run_full_replication_repair_deletes_and_recreates(self, mock_subprocess, mock_rmtree):
        """Ensure _run_full_replication_repair deletes the old dir and calls the orchestrator."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        
        success = experiment_manager._run_full_replication_repair(
            runs_to_repair=run_info,
            orchestrator_script=self.orchestrator_script,
            quiet=False,
            colors=self.colors
        )
        
        self.assertTrue(success)
        # Verify that the corrupted directory was deleted
        mock_rmtree.assert_called_with(run_dir)
        
        # Verify that the orchestrator was called to regenerate it
        mock_subprocess.assert_called_once()
        args, _ = mock_subprocess.call_args
        command_list = args[0]
        
        self.assertIn("--replication_num", command_list)
        self.assertIn("7", command_list) # Check for the correct rep number
        self.assertIn("--base_output_dir", command_list)
        self.assertIn(self.test_dir, command_list)

    @patch('src.experiment_manager.subprocess.run')
    def test_run_finalization_calls_all_scripts(self, mock_subprocess):
        """Ensure _run_finalization calls log manager and compiler in the correct order."""
        script_paths = {
            'log_manager': 'log_manager.py',
            'compile_experiment': 'compile_experiment.py'
        }
        
        experiment_manager._run_finalization(
            final_output_dir=self.test_dir,
            script_paths=script_paths,
            colors=self.colors
        )
        
        # Verify that three subprocess calls were made in the correct order
        self.assertEqual(mock_subprocess.call_count, 3)
        calls = mock_subprocess.call_args_list
        
        # Call 1: Rebuild the log
        self.assertIn('log_manager.py', calls[0].args[0])
        self.assertIn('rebuild', calls[0].args[0])
        self.assertIn(self.test_dir, calls[0].args[0])
        
        # Call 2: Compile experiment results
        self.assertIn('compile_experiment.py', calls[1].args[0])
        self.assertIn(self.test_dir, calls[1].args[0])
        
        # Call 3: Finalize the log
        self.assertIn('log_manager.py', calls[2].args[0])
        self.assertIn('finalize', calls[2].args[0])
        self.assertIn(self.test_dir, calls[2].args[0])


    @patch('src.experiment_manager.subprocess.run')
    @patch('src.experiment_manager._is_patching_needed', return_value=True)
    @patch('pathlib.Path.exists', return_value=True)
    @patch('pathlib.Path.unlink')
    @patch('pathlib.Path.glob')
    def test_run_migrate_mode_calls_all_steps(self, mock_glob, mock_unlink, mock_exists, mock_patching_needed, mock_subprocess):
        """Ensure _run_migrate_mode calls cleaning, patching, and reprocessing."""
        # Mock glob to return a single directory for reprocessing
        mock_run_dir = Path(self.test_dir) / "run_001"
        # Create the directory structure the function expects to clean up
        (mock_run_dir / "analysis_inputs").mkdir(parents=True)
        mock_glob.return_value = [mock_run_dir]
        
        # Mock subprocess to avoid actual calls
        mock_subprocess.return_value = MagicMock(returncode=0, stderr="")
        
        success = experiment_manager._run_migrate_mode(
            target_dir=Path(self.test_dir),
            patch_script="patch.py",
            orchestrator_script=self.orchestrator_script,
            colors=self.colors,
            verbose=False
        )
        
        self.assertTrue(success)
        
        # Verify that patch_script was called
        self.assertTrue(any("patch.py" in c.args[0] for c in mock_subprocess.call_args_list))
        
        # Verify that the orchestrator was called in reprocess mode on the run directory
        reprocess_call = next((c for c in mock_subprocess.call_args_list if self.orchestrator_script in c.args[0]), None)
        self.assertIsNotNone(reprocess_call)
        self.assertIn("--reprocess", reprocess_call.args[0])
        self.assertIn(str(mock_run_dir), reprocess_call.args[0])


    @patch('src.experiment_manager.subprocess.run')
    def test_run_config_repair_calls_restore_script(self, mock_subprocess):
        """Ensure _run_config_repair calls the restore_config.py script for each run."""
        run_info = [{"dir": "/path/to/run_1"}, {"dir": "/path/to/run_2"}]
        restore_script_path = "restore_config.py"
        
        success = experiment_manager._run_config_repair(
            runs_to_repair=run_info,
            restore_config_script=restore_script_path,
            colors=self.colors
        )
        
        self.assertTrue(success)
        # Check that the restore script was called for each of the two runs
        self.assertEqual(mock_subprocess.call_count, 2)
        
        # Verify the arguments for the first call
        first_call_args = mock_subprocess.call_args_list[0].args[0]
        self.assertIn(restore_script_path, first_call_args)
        self.assertIn("/path/to/run_1", first_call_args)
        
        # Verify the arguments for the second call
        second_call_args = mock_subprocess.call_args_list[1].args[0]
        self.assertIn(restore_script_path, second_call_args)
        self.assertIn("/path/to/run_2", second_call_args)


    @patch('src.experiment_manager.subprocess.run')
    @patch('src.experiment_manager._is_patching_needed', return_value=False) # Key change: no patching needed
    @patch('pathlib.Path.glob')
    def test_run_migrate_mode_skips_patching_for_modern_experiments(self, mock_glob, mock_patching_needed, mock_subprocess):
        """Ensure migrate mode skips patching when _is_patching_needed is False."""
        mock_run_dir = Path(self.test_dir) / "run_001"
        # Create the directory structure the function expects to clean up
        (mock_run_dir / "analysis_inputs").mkdir(parents=True)
        mock_glob.return_value = [mock_run_dir]
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        success = experiment_manager._run_migrate_mode(
            target_dir=Path(self.test_dir),
            patch_script="patch.py",
            orchestrator_script=self.orchestrator_script,
            colors=self.colors,
            verbose=False
        )
        
        self.assertTrue(success)
        
        # Verify that patch_script was NOT called
        was_patch_called = any("patch.py" in c.args[0] for c in mock_subprocess.call_args_list)
        self.assertFalse(was_patch_called, "Patch script was called when it should have been skipped.")
        
        # Verify that reprocessing was still called
        self.assertTrue(any(self.orchestrator_script in c.args[0] for c in mock_subprocess.call_args_list))

    @patch('src.experiment_manager.subprocess.run', side_effect=subprocess.CalledProcessError(1, "cmd"))
    @patch('src.experiment_manager._is_patching_needed', return_value=True)
    def test_run_migrate_mode_returns_false_on_failure(self, mock_patching_needed, mock_subprocess):
        """Ensure migrate mode returns False if any subprocess call fails."""
        # Create a mock directory structure so the initial cleanup step can pass
        mock_run_dir = Path(self.test_dir) / "run_001"
        (mock_run_dir / "analysis_inputs").mkdir(parents=True)
        
        # Mock glob to find our created directory.
        with patch('pathlib.Path.glob', return_value=[mock_run_dir]):
            # The function should fail on the patching step and return immediately
            success = experiment_manager._run_migrate_mode(
                target_dir=Path(self.test_dir),
            patch_script="patch.py",
            orchestrator_script=self.orchestrator_script,
            colors=self.colors,
            verbose=False
        )
        
        self.assertFalse(success)
        # Ensure it failed early, on the patch script call
        mock_subprocess.assert_called_once_with([sys.executable, "patch.py", self.test_dir], check=True, capture_output=True, text=True)


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_experiment_manager.py ===
