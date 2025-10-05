#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: tests/experiment_lifecycle/test_experiment_manager.py

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
src_dir = os.path.abspath(os.path.join(current_dir, '..', '..', 'src'))
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
            'Experiment': {'num_replications': '1'},
            'General': {
                'base_output_dir': 'output',
                'new_experiments_subdir': 'new_exps',
                'experiment_dir_prefix': 'exp_'
            },
            'Filenames': {'batch_run_log': 'experiment_log.csv'}
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

    def _create_state_side_effect(self, states):
        """Helper to create a side effect that cycles through states"""
        def side_effect(*args, **kwargs):
            if not hasattr(side_effect, 'call_count'):
                side_effect.call_count = 0
            if side_effect.call_count < len(states):
                result = states[side_effect.call_count]
                side_effect.call_count += 1
                return result
            else:
                return states[-1]  # Return the last state for any additional calls
        return side_effect

    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_new_needed_calls_new_mode(self, mock_get_config, mock_get_state, mock_new, mock_finalize, mock_exit):
        """Tests that state NEW_NEEDED correctly calls the _run_new_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = self._create_state_side_effect([
            ("NEW_NEEDED", {}, ""), 
            ("COMPLETE", {}, "")
        ])

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_new.assert_called_once()
        mock_finalize.assert_called_once()

    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_repair_needed_calls_session_repair(self, mock_get_config, mock_get_state, mock_session_repair, mock_config_repair, mock_full_repair, mock_finalize, mock_exit):
        """Tests that REPAIR_NEEDED with 'session_repair' calls the correct helper."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [{"repair_type": "session_repair", "dir": "run_1", "failed_indices": [1]}]
        mock_get_state.side_effect = self._create_state_side_effect([
            ("REPAIR_NEEDED", payload, ""), 
            ("COMPLETE", {}, "")
        ])

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_session_repair.assert_called_once()
        mock_config_repair.assert_not_called()
        mock_full_repair.assert_not_called()
        mock_finalize.assert_called_once()

    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_repair_needed_calls_config_repair(self, mock_get_config, mock_get_state, mock_session_repair, mock_config_repair, mock_full_repair, mock_finalize, mock_exit):
        """Tests that REPAIR_NEEDED with 'config_repair' calls the correct helper."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [{"repair_type": "config_repair", "dir": "run_1"}]
        mock_get_state.side_effect = self._create_state_side_effect([
            ("REPAIR_NEEDED", payload, ""), 
            ("COMPLETE", {}, "")
        ])

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_config_repair.assert_called_once()
        mock_session_repair.assert_not_called()
        mock_full_repair.assert_not_called()
        mock_finalize.assert_called_once()

    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_repair_needed_calls_full_repair(self, mock_get_config, mock_get_state, mock_session_repair, mock_config_repair, mock_full_repair, mock_finalize, mock_exit):
        """Tests that REPAIR_NEEDED with 'full_replication_repair' calls the correct helper."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [{"repair_type": "full_replication_repair", "dir": "run_1"}]
        mock_get_state.side_effect = self._create_state_side_effect([
            ("REPAIR_NEEDED", payload, ""), 
            ("COMPLETE", {}, "")
        ])

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_full_repair.assert_called_once()
        mock_session_repair.assert_not_called()
        mock_config_repair.assert_not_called()
        mock_finalize.assert_called_once()
    
    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_reprocess_needed_calls_reprocess_mode(self, mock_get_config, mock_get_state, mock_reprocess, mock_finalize, mock_exit):
        """Tests that state REPROCESS_NEEDED correctly calls the reprocess_mode function."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.side_effect = self._create_state_side_effect([
            ("REPROCESS_NEEDED", [{"dir": "run_1"}], ""), 
            ("COMPLETE", {}, "")
        ])

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_reprocess.assert_called_once()
        mock_finalize.assert_called_once()

    @patch('src.experiment_manager._run_finalization')
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_aggregation_needed_breaks_loop_and_finalizes(self, mock_get_config, mock_get_state, mock_finalize):
        """Tests that AGGREGATION_NEEDED state breaks the loop and proceeds to finalization."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("AGGREGATION_NEEDED", {}, "")

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_get_state.assert_called_once()
        mock_finalize.assert_called_once()

    @patch('sys.exit')
    @patch('pathlib.Path.glob')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_reprocess_flag_forces_reprocessing_on_complete_state(self, mock_get_config, mock_get_state, mock_reprocess, mock_finalize, mock_glob, mock_exit):
        """Tests that the --reprocess flag forces reprocessing even if state is COMPLETE."""
        mock_get_config.side_effect = self._get_config_side_effect
        # Use the side effect helper to ensure proper state transitions
        mock_get_state.side_effect = self._create_state_side_effect([
            ("COMPLETE", [], ""),  # Initial state
            ("COMPLETE", [], "")   # State after reprocessing
        ])

        # Create a mock Path object that behaves correctly when stringified
        mock_run_dir = MagicMock(spec=Path)
        mock_run_dir.is_dir.return_value = True
        # Add a .name attribute that the auditor can parse with regex
        mock_run_dir.name = 'run_20250101_120000_rep-001_model_tmp-1.00_db_sbj-10_trl-100_rps-001_mps-correct'
        mock_run_dir.__str__.return_value = os.path.join(self.test_dir, mock_run_dir.name)
        mock_glob.return_value = [mock_run_dir]

        with patch.object(sys, 'argv', ['script.py', self.test_dir, '--reprocess']):
            experiment_manager.main()

        mock_reprocess.assert_called_once()
        mock_finalize.assert_called_once()

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_new_mode', return_value=False) # Simulate failure
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_main_loop_halts_on_mode_failure(self, mock_get_config, mock_get_state, mock_new_mode, mock_finalize):
        """Tests that the main loop exits if a helper function returns False."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("NEW_NEEDED", {}, "")

        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', self.test_dir]):
                experiment_manager.main()

        self.assertEqual(cm.exception.code, 1)
        mock_new_mode.assert_called_once()
        mock_finalize.assert_not_called() # Crucial: finalization should NOT run on failure

    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_full_replication_repair', return_value=True)
    @patch('src.experiment_manager._run_config_repair', return_value=True)
    @patch('src.experiment_manager._run_repair_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_multi_step_repair_sequence(self, mock_get_config, mock_get_state, mock_session_repair, mock_config_repair, mock_full_repair, mock_finalize, mock_exit):
        """Tests that the state machine correctly handles a sequence of different repairs."""
        mock_get_config.side_effect = self._get_config_side_effect
        
        config_payload = [{"repair_type": "config_repair", "dir": "run_1"}]
        session_payload = [{"repair_type": "session_repair", "dir": "run_1", "failed_indices": [1]}]
        
        mock_get_state.side_effect = self._create_state_side_effect([
            ("REPAIR_NEEDED", config_payload, ""),   # First, it needs a config repair
            ("REPAIR_NEEDED", session_payload, ""), # Then, it needs a session repair
            ("COMPLETE", {}, "")                    # Finally, it's complete
        ])

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        # Verify each repair type was called exactly once in sequence
        mock_config_repair.assert_called_once()
        mock_session_repair.assert_called_once()
        mock_full_repair.assert_not_called()
        
        # Verify finalization was called at the end
        mock_finalize.assert_called_once()

    @patch('sys.exit')
    @patch('experiment_auditor.get_experiment_state', side_effect=KeyboardInterrupt)
    def test_main_exits_gracefully_on_keyboard_interrupt(self, mock_get_state, mock_exit):
        """Verify the main loop catches KeyboardInterrupt and exits with the correct code."""
        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()
        
        # Verify it exits with the specific code for a user-initiated abort
        mock_exit.assert_called_once_with(experiment_manager.AUDIT_ABORTED_BY_USER)

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_new_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    def test_main_loop_halts_on_max_loops(self, mock_get_state, mock_new_mode, mock_finalize):
        """Tests that the main loop exits if it exceeds the max_loops count."""
        # Force the state to always be NEW_NEEDED to create a loop
        mock_get_state.return_value = ("NEW_NEEDED", {}, "")
        
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', self.test_dir, '--max-loops=3']):
                experiment_manager.main()
        
        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(mock_new_mode.call_count, 3)
        mock_finalize.assert_not_called()

    @patch('sys.exit')
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_migrate_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    def test_migrate_flag_runs_migrate_workflow(self, mock_get_state, mock_migrate, mock_finalize, mock_exit):
        """Tests that --migrate flag correctly runs the migration workflow and finalizes."""
        with patch.object(sys, 'argv', ['script.py', self.test_dir, '--migrate']):
            experiment_manager.main()

        mock_migrate.assert_called_once()
        mock_get_state.assert_not_called() # Should not enter the main state loop
        mock_finalize.assert_called_once()
        mock_exit.assert_not_called()

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_migrate_mode', return_value=False) # Simulate failure
    def test_migrate_flag_halts_on_failure(self, mock_migrate, mock_finalize):
        """Tests that a failed migration halts execution and does not finalize."""
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', self.test_dir, '--migrate']):
                experiment_manager.main()

        self.assertEqual(cm.exception.code, 1)
        mock_migrate.assert_called_once()
        mock_finalize.assert_not_called()

    @patch('sys.exit')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=False)
    @patch('experiment_auditor.get_experiment_state', return_value=("COMPLETE", {}, ""))
    @patch('src.experiment_manager.get_config_value')
    def test_main_creates_nonexistent_target_dir(self, mock_get_config, mock_get_state, mock_exists, mock_makedirs, mock_exit):
        """Verify main() creates a target directory if it doesn't exist."""
        mock_get_config.side_effect = self._get_config_side_effect
        non_existent_dir = os.path.join(self.test_dir, "new_dir")

        with patch('src.experiment_manager._run_finalization'):
            with patch.object(sys, 'argv', ['script.py', non_existent_dir]):
                experiment_manager.main()

        mock_makedirs.assert_called_once_with(non_existent_dir)

    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_full_replication_repair')
    @patch('src.experiment_manager._run_config_repair', return_value=False) # Simulate failure
    @patch('src.experiment_manager._run_repair_mode')
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_repair_sequence_halts_on_failure(self, mock_get_config, mock_get_state, mock_session_repair, mock_config_repair, mock_full_repair, mock_finalize):
        """Tests that a failure in one repair step prevents subsequent repairs."""
        mock_get_config.side_effect = self._get_config_side_effect
        payload = [
            {"repair_type": "config_repair", "dir": "run_1"},
            {"repair_type": "full_replication_repair", "dir": "run_2"},
            {"repair_type": "session_repair", "dir": "run_3", "failed_indices": [1]}
        ]
        mock_get_state.return_value = ("REPAIR_NEEDED", payload, "")

        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', self.test_dir, '--max-loops=3']):
                experiment_manager.main()

        self.assertEqual(cm.exception.code, 1)
        self.assertEqual(mock_config_repair.call_count, 3)  # Called 3 times before max_loops
        mock_full_repair.assert_not_called()  # Never called due to config repair failure
        mock_session_repair.assert_not_called()  # Never called due to config repair failure
        mock_finalize.assert_not_called()


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
    def test_run_new_mode_does_nothing_if_all_reps_exist(self, mock_popen):
        """Ensure _run_new_mode does nothing if all replications already exist."""
        # Mock glob to find existing directories for reps 1 and 2
        with patch('glob.glob', return_value=[
            os.path.join(self.test_dir, 'run_abc_rep-1_xyz'),
            os.path.join(self.test_dir, 'run_abc_rep-2_xyz')
        ]):
            success = experiment_manager._run_new_mode(
                target_dir=self.test_dir,
                start_rep=1,
                end_rep=2,
                notes=None,
                verbose=False,
                orchestrator_script=self.orchestrator_script,
                colors=self.colors
            )
        
        self.assertTrue(success)
        mock_popen.assert_not_called()

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_new_mode_does_nothing_if_all_reps_exist(self, mock_popen):
        """Ensure _run_new_mode does nothing if all replications already exist."""
        # Mock glob to find existing directories for reps 1 and 2
        with patch('glob.glob', return_value=[
            os.path.join(self.test_dir, 'run_abc_rep-1_xyz'),
            os.path.join(self.test_dir, 'run_abc_rep-2_xyz')
        ]):
            success = experiment_manager._run_new_mode(
                target_dir=self.test_dir,
                start_rep=1,
                end_rep=2,
                notes=None,
                verbose=False,
                orchestrator_script=self.orchestrator_script,
                colors=self.colors
            )
        
        self.assertTrue(success)
        mock_popen.assert_not_called()

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_new_mode_skips_existing_replications(self, mock_popen):
        """Ensure _run_new_mode correctly skips replications that already exist."""
        # Mock glob to find an existing directory for rep 1
        with patch('glob.glob', return_value=[os.path.join(self.test_dir, 'run_abc_rep-1_xyz')]):
            mock_proc = MagicMock(stdout=[], returncode=0)
            mock_proc.wait.return_value = 0
            mock_popen.return_value = mock_proc
            
            experiment_manager._run_new_mode(
                target_dir=self.test_dir,
                start_rep=1,
                end_rep=2,
                notes=None,
                verbose=False,
                orchestrator_script=self.orchestrator_script,
                colors=self.colors
            )
        
        # Should only be called once, for replication #2
        mock_popen.assert_called_once()
        args, _ = mock_popen.call_args
        command_list = args[0]
        self.assertIn("--replication_num", command_list)
        self.assertIn("2", command_list)

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

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_reprocess_mode_constructs_correct_command(self, mock_popen):
        """Ensure _run_reprocess_mode calls orchestrator with the --reprocess flag."""
        run_info = [{"dir": self.test_dir}]
        mock_proc = MagicMock(stdout=[], stderr=MagicMock(read=lambda: ''))
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        # Call the function under test
        success = experiment_manager._run_reprocess_mode(
            runs_to_reprocess=run_info,
            notes="reprocess notes",
            verbose=True,
            orchestrator_script=self.orchestrator_script,
            compile_script=None,
            target_dir=self.test_dir,
            log_manager_script=None,
            colors=self.colors
        )
        
        self.assertTrue(success)
        mock_popen.assert_called_once()
        args, _ = mock_popen.call_args
        command_list = args[0]
        
        # Verify the command arguments
        self.assertIn(self.orchestrator_script, command_list)
        self.assertIn("--reprocess", command_list)
        self.assertIn("--run_output_dir", command_list)
        self.assertIn(self.test_dir, command_list)
        self.assertIn("--verbose", command_list)
        self.assertIn("--notes", command_list)
        self.assertIn("reprocess notes", command_list)

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_reprocess_mode_returns_false_on_failure(self, mock_popen):
        """Ensure _run_reprocess_mode returns False if the subprocess fails."""
        mock_proc = MagicMock(stdout=[], stderr=MagicMock(read=lambda: ''), returncode=1)
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc

        run_info = [{"dir": self.test_dir}]
        with patch('src.experiment_manager.logging.error'):
            success = experiment_manager._run_reprocess_mode(
                runs_to_reprocess=run_info,
                notes=None,
                verbose=False,
                orchestrator_script=self.orchestrator_script,
                compile_script=None,
                target_dir=self.test_dir,
                log_manager_script=None,
                colors=self.colors
            )
        self.assertFalse(success)


    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_repair_mode_skips_runs_with_no_failed_indices(self, mock_popen):
        """Ensure _run_repair_mode does nothing if a run has no failed indices."""
        run_info = [{"dir": self.test_dir, "failed_indices": []}]
        
        success = experiment_manager._run_repair_mode(
            runs_to_repair=run_info,
            orchestrator_script_path=self.orchestrator_script,
            verbose=False,
            colors=self.colors
        )
        
        self.assertTrue(success)
        mock_popen.assert_not_called()

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_repair_mode_constructs_correct_command(self, mock_popen):
        """Ensure _run_repair_mode calls orchestrator with --reprocess and indices."""
        run_info = [{"dir": self.test_dir, "failed_indices": [1, 5, 10]}]
        mock_proc = MagicMock(stdout=[], stderr=MagicMock(read=lambda: ''))
        mock_proc.wait.return_value = 0
        mock_proc.returncode = 0
        mock_popen.return_value = mock_proc

        success = experiment_manager._run_repair_mode(
            runs_to_repair=run_info,
            orchestrator_script_path=self.orchestrator_script,
            verbose=True,
            colors=self.colors
        )
        
        self.assertTrue(success)
        mock_popen.assert_called_once()
        args, _ = mock_popen.call_args
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
    def test_run_full_replication_repair_with_quiet_flag(self, mock_subprocess, mock_rmtree):
        """Ensure the quiet flag is passed correctly for full repair."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        
        experiment_manager._run_full_replication_repair(
            runs_to_repair=run_info,
            orchestrator_script=self.orchestrator_script,
            quiet=True, # Test the quiet path
            colors=self.colors
        )
        
        mock_subprocess.assert_called_once()
        args, kwargs = mock_subprocess.call_args
        command_list = args[0]

        self.assertIn("--quiet", command_list)
        self.assertTrue(kwargs.get('capture_output'))

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


    @patch('pathlib.Path.unlink', side_effect=OSError("Permission denied"))
    def test_run_migrate_mode_fails_on_cleaning_error(self, mock_unlink):
        """Ensure migrate mode returns False if initial artifact cleaning fails."""
        # Create a mock file for the cleanup to find
        (Path(self.test_dir) / "EXPERIMENT_results.csv").touch()

        with patch('pathlib.Path.exists', return_value=True), \
             patch('src.experiment_manager.logging.error'):
            success = experiment_manager._run_migrate_mode(
                target_dir=Path(self.test_dir),
                patch_script="patch.py",
                orchestrator_script=self.orchestrator_script,
                colors=self.colors,
                verbose=False
            )
        self.assertFalse(success)

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


    @patch('src.experiment_manager.logging.error')
    @patch('src.experiment_manager.subprocess.run')
    def test_run_config_repair_logs_and_returns_false_on_failure(self, mock_subprocess, mock_log_error):
        """Ensure _run_config_repair logs stderr and returns False on failure."""
        error = subprocess.CalledProcessError(1, "cmd", stderr="config error")
        mock_subprocess.side_effect = error
        run_info = [{"dir": "/path/to/run_1"}]
        
        success = experiment_manager._run_config_repair(
            runs_to_repair=run_info,
            restore_config_script="restore.py",
            colors=self.colors
        )
        
        self.assertFalse(success)
        mock_log_error.assert_called_with("Stderr:\nconfig error")

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


class TestHelperFunctions(unittest.TestCase):
    """Tests for standalone helper functions in experiment_manager.py."""

    def setUp(self):
        """Set up a temporary directory for tests that need it."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="exp_manager_helpers_")
        self.project_root = self.test_dir.name
        
        # Patch PROJECT_ROOT directly in the experiment_manager namespace
        self.project_root_patcher = patch('src.experiment_manager.PROJECT_ROOT', self.project_root)
        self.mock_project_root = self.project_root_patcher.start()

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir.cleanup()
        self.project_root_patcher.stop()

    def test_format_header(self):
        """Verify that _format_header correctly formats a message."""
        message = "TEST MESSAGE"
        expected = "###" + f" {message} ".center(74) + "###"
        result = experiment_manager._format_header(message)
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 80)

    @patch('builtins.print')
    @patch('src.experiment_manager.os.makedirs')
    @patch('src.experiment_manager.get_config_value')
    @patch('src.experiment_manager.datetime')
    def test_create_new_experiment_directory(self, mock_datetime, mock_get_config, mock_makedirs, mock_print):
        """Verify _create_new_experiment_directory constructs path, creates it, and prints."""
        # Mock dependencies
        mock_datetime.datetime.now.return_value.strftime.return_value = "20250101_120000"
        mock_get_config.side_effect = lambda cfg, sec, key, fallback: {
            'base_output_dir': 'output',
            'new_experiments_subdir': 'new_exps',
            'experiment_dir_prefix': 'exp_'
        }.get(key, fallback)
        
        colors = {'cyan': 'CYAN', 'reset': 'RESET'}
        
        # Call the function
        result_dir = experiment_manager._create_new_experiment_directory(colors)
        
        # Verify path construction and directory creation
        expected_dir = os.path.join(self.project_root, 'output', 'new_exps', 'exp_20250101_120000')
        self.assertEqual(result_dir, expected_dir)
        mock_makedirs.assert_called_once_with(expected_dir)
        
        # Verify print output
        relative_path = os.path.relpath(expected_dir, self.project_root)
        mock_print.assert_called_once_with(f"CYANNew experiment directory created:\n{relative_path}RESET\n")

    @patch('builtins.open')
    @patch('pathlib.Path.exists')
    def test_verify_experiment_level_files(self, mock_exists, mock_open):
        """Verify the logic for checking top-level experiment files."""
        target_dir = Path(self.test_dir.name)
        
        # --- Test Success Case ---
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Header\nBatchSummary"
        
        is_complete, details = experiment_manager._verify_experiment_level_files(target_dir)
        self.assertTrue(is_complete)
        self.assertEqual(details, [])
        
        # --- Test Failure Case: Missing File ---
        mock_exists.return_value = False
        is_complete, details = experiment_manager._verify_experiment_level_files(target_dir)
        self.assertFalse(is_complete)
        self.assertIn("MISSING: experiment_log.csv", details)
        self.assertIn("MISSING: EXPERIMENT_results.csv", details)
        
        # --- Test Failure Case: Unfinalized Log ---
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Header\nNoSummary"
        is_complete, details = experiment_manager._verify_experiment_level_files(target_dir)
        self.assertFalse(is_complete)
        self.assertEqual(details, ["experiment_log.csv NOT FINALIZED"])

        # --- Test Failure Case: Unreadable Log ---
        mock_exists.return_value = True
        mock_open.side_effect = IOError("Cannot read file")
        is_complete, details = experiment_manager._verify_experiment_level_files(target_dir)
        self.assertFalse(is_complete)
        self.assertEqual(details, ["experiment_log.csv UNREADABLE"])

class TestMigrationHelpers(unittest.TestCase):
    """Tests for the migration-related helper functions."""

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="exp_manager_migrate_")
        self.target_dir = Path(self.test_dir.name)
        self.colors = {'green': '', 'yellow': '', 'reset': ''}
        self.orchestrator_script = "orchestrator.py"
        self.patch_script = "patch.py"

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir.cleanup()

    def test_is_patching_needed(self):
        """Verify logic for detecting legacy experiments."""
        run1_dir = self.target_dir / "run_1"
        run2_dir = self.target_dir / "run_2"
        run1_dir.mkdir()
        run2_dir.mkdir()
        
        # Case 1: Legacy experiment (missing config)
        self.assertTrue(experiment_manager._is_patching_needed([run1_dir, run2_dir]))
        
        # Case 2: Modern experiment (all configs present)
        (run1_dir / "config.ini.archived").touch()
        (run2_dir / "config.ini.archived").touch()
        self.assertFalse(experiment_manager._is_patching_needed([run1_dir, run2_dir]))

    @patch('src.experiment_manager.subprocess.run')
    def test_run_migrate_mode_calls_patch_and_reprocess_for_legacy(self, mock_subprocess):
        """Ensure migrate mode calls patching and reprocessing for legacy experiments."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        run_dir = self.target_dir / "run_001"
        run_dir.mkdir() # Missing config.ini.archived

        success = experiment_manager._run_migrate_mode(
            self.target_dir, self.patch_script, self.orchestrator_script, self.colors, False
        )
        self.assertTrue(success)
        
        # Check that both patch and reprocess were called
        patch_call = call([sys.executable, self.patch_script, str(self.target_dir)], check=True, capture_output=True, text=True)
        reprocess_call = call([sys.executable, self.orchestrator_script, "--reprocess", "--run_output_dir", str(run_dir)], check=False, capture_output=True, text=True)
        mock_subprocess.assert_has_calls([patch_call, reprocess_call], any_order=False)

    @patch('src.experiment_manager.subprocess.run')
    def test_run_migrate_mode_skips_patch_for_modern(self, mock_subprocess):
        """Ensure migrate mode skips patching for modern experiments."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        run_dir = self.target_dir / "run_001"
        run_dir.mkdir()
        (run_dir / "config.ini.archived").touch() # Config is present

        success = experiment_manager._run_migrate_mode(
            self.target_dir, self.patch_script, self.orchestrator_script, self.colors, False
        )
        self.assertTrue(success)
        
        # Check that reprocess was called but patch was not
        for sub_call in mock_subprocess.call_args_list:
            self.assertNotIn(self.patch_script, sub_call.args[0])
        
        reprocess_call = call([sys.executable, self.orchestrator_script, "--reprocess", "--run_output_dir", str(run_dir)], check=False, capture_output=True, text=True)
        mock_subprocess.assert_has_calls([reprocess_call])

class TestFailureScenarios(unittest.TestCase):
    """Tests the failure paths of the individual _run_* helper functions."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="exp_manager_failures_")
        self.colors = {'cyan': '', 'green': '', 'yellow': '', 'red': '', 'reset': ''}
        self.orchestrator_script = "replication_manager.py"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    @patch('src.experiment_manager.logging.error')
    def test_full_repair_handles_bad_dir_name(self, mock_log_error):
        """Ensure full repair gracefully handles a malformed directory name."""
        run_info = [{"dir": os.path.join(self.test_dir, "run_without_rep_num")}]
        
        success = experiment_manager._run_full_replication_repair(
            runs_to_repair=run_info,
            orchestrator_script=self.orchestrator_script,
            quiet=True,
            colors=self.colors
        )
        
        self.assertTrue(success) 
        mock_log_error.assert_called_with("Could not extract replication number from 'run_without_rep_num'. Skipping repair for this run.")

    @patch('src.experiment_manager.logging.error')
    @patch('shutil.rmtree', side_effect=OSError("Test permission error"))
    def test_full_repair_handles_deletion_failure(self, mock_rmtree, mock_log_error):
        """Ensure full repair gracefully handles a failure to delete the old directory."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-001_...")
        run_info = [{"dir": run_dir}]
        
        success = experiment_manager._run_full_replication_repair(
            runs_to_repair=run_info,
            orchestrator_script=self.orchestrator_script,
            quiet=True,
            colors=self.colors
        )
        
        self.assertTrue(success)
        mock_rmtree.assert_called_with(run_dir)
        mock_log_error.assert_called_with(f"Failed to delete directory {run_dir}: Test permission error")

    @patch('shutil.rmtree')
    @patch('src.experiment_manager.subprocess.run', side_effect=subprocess.CalledProcessError(1, "cmd", stderr="Subprocess failed"))
    def test_full_repair_returns_false_on_subprocess_failure(self, mock_subprocess, mock_rmtree):
        """Ensure full repair returns False if the recreation subprocess fails."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        
        with patch('src.experiment_manager.logging.error'): # Suppress error logging for clean test output
            success = experiment_manager._run_full_replication_repair(
                runs_to_repair=run_info,
                orchestrator_script=self.orchestrator_script,
                quiet=True,
                colors=self.colors
            )
        
        self.assertFalse(success)
        mock_rmtree.assert_called_with(run_dir)
        mock_subprocess.assert_called_once()

    @patch('src.experiment_manager.subprocess.run', side_effect=subprocess.CalledProcessError(1, "cmd", stderr="Finalization failed"))
    def test_run_finalization_exits_on_failure(self, mock_subprocess):
        """Ensure _run_finalization exits with sys.exit(1) on subprocess failure."""
        script_paths = {'log_manager': 'log.py', 'compile_experiment': 'compile.py'}
        
        with self.assertRaises(SystemExit) as cm, \
             patch('src.experiment_manager.logging.error'): # Suppress error logging
            experiment_manager._run_finalization(
                final_output_dir=self.test_dir,
                script_paths=script_paths,
                colors=self.colors
            )
        
        self.assertEqual(cm.exception.code, 1)

    @patch('src.experiment_manager.subprocess.Popen', side_effect=KeyboardInterrupt)
    def test_run_repair_mode_exits_on_keyboard_interrupt(self, mock_popen):
        """Ensure _run_repair_mode exits on KeyboardInterrupt."""
        run_info = [{"dir": self.test_dir, "failed_indices": [1]}]
        with self.assertRaises(SystemExit) as cm:
            experiment_manager._run_repair_mode(
                run_info, self.orchestrator_script, False, self.colors
            )
        self.assertEqual(cm.exception.code, experiment_manager.AUDIT_ABORTED_BY_USER)

    @patch('shutil.rmtree')
    @patch('src.experiment_manager.subprocess.run', side_effect=KeyboardInterrupt)
    def test_full_repair_exits_on_keyboard_interrupt(self, mock_subprocess, mock_rmtree):
        """Ensure _run_full_replication_repair exits on KeyboardInterrupt."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        with self.assertRaises(SystemExit) as cm:
            experiment_manager._run_full_replication_repair(
                run_info, self.orchestrator_script, True, self.colors
            )
        self.assertEqual(cm.exception.code, experiment_manager.AUDIT_ABORTED_BY_USER)

    @patch('src.experiment_manager.subprocess.Popen', side_effect=KeyboardInterrupt)
    def test_run_repair_mode_exits_on_keyboard_interrupt(self, mock_popen):
        """Ensure _run_repair_mode exits on KeyboardInterrupt."""
        run_info = [{"dir": self.test_dir, "failed_indices": [1]}]
        with self.assertRaises(SystemExit) as cm:
            experiment_manager._run_repair_mode(
                run_info, self.orchestrator_script, False, self.colors
            )
        self.assertEqual(cm.exception.code, experiment_manager.AUDIT_ABORTED_BY_USER)

    @patch('shutil.rmtree')
    @patch('src.experiment_manager.subprocess.run', side_effect=KeyboardInterrupt)
    def test_full_repair_exits_on_keyboard_interrupt(self, mock_subprocess, mock_rmtree):
        """Ensure _run_full_replication_repair exits on KeyboardInterrupt."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        with self.assertRaises(SystemExit) as cm:
            experiment_manager._run_full_replication_repair(
                run_info, self.orchestrator_script, True, self.colors
            )
        self.assertEqual(cm.exception.code, experiment_manager.AUDIT_ABORTED_BY_USER)
        mock_subprocess.assert_called_once()

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_new_mode_returns_false_on_failure(self, mock_popen):
        """Ensure _run_new_mode returns False if the replication subprocess fails."""
        mock_proc = MagicMock(stdout=[], returncode=1) # Simulate failure
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc
        
        with patch('src.experiment_manager.logging.error'):
            success = experiment_manager._run_new_mode(
                self.test_dir, 1, 1, None, False, self.orchestrator_script, self.colors
            )
        
        self.assertFalse(success)
        mock_popen.assert_called_once()

    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_repair_mode_returns_false_on_failure(self, mock_popen):
        """Ensure _run_repair_mode returns False if the repair subprocess fails."""
        mock_proc = MagicMock(stdout=[], stderr=MagicMock(read=lambda: ''), returncode=1)
        mock_proc.wait.return_value = 0
        mock_popen.return_value = mock_proc
        
        run_info = [{"dir": self.test_dir, "failed_indices": [1]}]
        
        with patch('src.experiment_manager.logging.error'):
            success = experiment_manager._run_repair_mode(
                run_info, self.orchestrator_script, False, self.colors
            )
        
        self.assertFalse(success)
        mock_popen.assert_called_once()

    @patch('src.experiment_manager.subprocess.Popen', side_effect=KeyboardInterrupt)
    def test_run_new_mode_exits_on_keyboard_interrupt(self, mock_popen):
        """Ensure _run_new_mode exits cleanly on KeyboardInterrupt."""
        with self.assertRaises(SystemExit) as cm, \
             patch('src.experiment_manager.logging.error'):
            experiment_manager._run_new_mode(
                self.test_dir, 1, 1, None, False, self.orchestrator_script, self.colors
            )
        
        # In the context of a child process interrupt, the manager should exit
        self.assertEqual(cm.exception.code, 1)

    @patch('builtins.print')
    @patch('src.experiment_manager.subprocess.Popen')
    def test_run_repair_mode_prints_stderr_on_failure(self, mock_popen, mock_print):
        """Ensure _run_repair_mode prints stderr from a CalledProcessError."""
        # Simulate a process that fails and has stderr content
        error = subprocess.CalledProcessError(1, "cmd", stderr="error message")
        mock_popen.side_effect = error
        
        run_info = [{"dir": self.test_dir, "failed_indices": [1]}]
        
        with patch('src.experiment_manager.logging.error'):
            success = experiment_manager._run_repair_mode(
                run_info, self.orchestrator_script, False, self.colors
            )
        
        self.assertFalse(success)
        # Verify that the stderr content was printed
        mock_print.assert_called_with("error message", file=sys.stderr)

    @patch('src.experiment_manager.subprocess.Popen', side_effect=KeyboardInterrupt)
    def test_run_reprocess_mode_exits_on_keyboard_interrupt(self, mock_popen):
        """Ensure _run_reprocess_mode exits on KeyboardInterrupt."""
        run_info = [{"dir": self.test_dir}]
        with self.assertRaises(SystemExit) as cm:
            with patch('src.experiment_manager.logging.error'):
                experiment_manager._run_reprocess_mode(
                    run_info, None, False, self.orchestrator_script, None,
                    self.test_dir, None, self.colors
                )
        self.assertEqual(cm.exception.code, experiment_manager.AUDIT_ABORTED_BY_USER)

    @patch('shutil.rmtree')
    @patch('src.experiment_manager.subprocess.run')
    @patch('src.experiment_manager.logging.error')
    def test_full_repair_logs_stderr_on_failure(self, mock_log_error, mock_subprocess, mock_rmtree):
        """Ensure full repair logs stderr from the orchestrator on failure."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="out", stderr="err")
        
        experiment_manager._run_full_replication_repair(
            run_info, self.orchestrator_script, True, self.colors
        )
        
        self.assertTrue(any("Orchestrate Replication STDERR" in c.args[0] and "err" in c.args[0]
                            for c in mock_log_error.call_args_list))

    @patch('src.experiment_manager.subprocess.run')
    @patch('src.experiment_manager.logging.error')
    def test_finalization_logs_details_on_failure(self, mock_log_error, mock_subprocess):
        """Ensure _run_finalization logs stdout and stderr on subprocess failure."""
        error = subprocess.CalledProcessError(1, "cmd", output="out", stderr="err")
        mock_subprocess.side_effect = error
        script_paths = {'log_manager': 'log.py', 'compile_experiment': 'compile.py'}
        
        with self.assertRaises(SystemExit):
            experiment_manager._run_finalization(self.test_dir, script_paths, self.colors)
        
        self.assertTrue(any("Stderr" in c.args[0] and "err" in c.args[0]
                            for c in mock_log_error.call_args_list))
        self.assertTrue(any("Stdout" in c.args[0] and "out" in c.args[0]
                            for c in mock_log_error.call_args_list))

    @patch('src.experiment_manager.subprocess.run')
    @patch('src.experiment_manager.logging.error')
    def test_finalization_logs_stdout_only_on_failure(self, mock_log_error, mock_subprocess):
        """Ensure _run_finalization logs stdout when stderr is empty on failure."""
        error = subprocess.CalledProcessError(1, "cmd", output="stdout only")
        # Explicitly set stderr to None or empty string
        error.stderr = None
        mock_subprocess.side_effect = error
        script_paths = {'log_manager': 'log.py', 'compile_experiment': 'compile.py'}
        
        with self.assertRaises(SystemExit):
            experiment_manager._run_finalization(self.test_dir, script_paths, self.colors)
        
        self.assertTrue(any("Stdout" in c.args[0] and "stdout only" in c.args[0]
                            for c in mock_log_error.call_args_list))
        # Verify that Stderr was not logged
        self.assertFalse(any("Stderr" in c.args[0] for c in mock_log_error.call_args_list))

    @patch('shutil.rmtree')
    @patch('src.experiment_manager.subprocess.run')
    @patch('src.experiment_manager.logging.info')
    def test_full_repair_logs_stdout_only(self, mock_log_info, mock_subprocess, mock_rmtree):
        """Ensure full repair logs only stdout when stderr is empty."""
        run_dir = os.path.join(self.test_dir, "run_..._rep-007_...")
        run_info = [{"dir": run_dir}]
        # Simulate a successful run with stdout but no stderr
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="out", stderr=None)
        
        experiment_manager._run_full_replication_repair(
            run_info, self.orchestrator_script, True, self.colors
        )
        
        self.assertTrue(any("Orchestrate Replication STDOUT" in c.args[0] and "out" in c.args[0]
                            for c in mock_log_info.call_args_list))

    @patch('src.experiment_manager.subprocess.run', side_effect=Exception("Generic error"))
    @patch('src.experiment_manager.logging.error')
    def test_finalization_handles_generic_exception(self, mock_log_error, mock_subprocess):
        """Ensure _run_finalization catches and logs generic exceptions."""
        script_paths = {'log_manager': 'log.py', 'compile_experiment': 'compile.py'}
        
        with self.assertRaises(SystemExit):
            experiment_manager._run_finalization(self.test_dir, script_paths, self.colors)
        
        mock_log_error.assert_called_with("An unexpected error occurred during finalization: Generic error")


class TestModuleSetup(unittest.TestCase):
    """Tests for module-level setup like optional imports."""

    def test_tqdm_fallback_works(self):
        """Verify the script doesn't crash if tqdm is not installed."""
        # Hide the real tqdm and reload the module to trigger the fallback
        with patch.dict('sys.modules', {'tqdm': None}):
            import importlib
            importlib.reload(experiment_manager)
            
            # Check that the fallback function was created and is callable
            self.assertTrue(callable(experiment_manager.tqdm))
            # Call it to ensure it doesn't crash
            self.assertEqual(list(experiment_manager.tqdm([1, 2])), [1, 2])
        
        # Restore the original module to not affect other tests
        import importlib
        importlib.reload(experiment_manager)


class TestMainFunctionEdgeCases(unittest.TestCase):
    """Tests for edge cases and argument parsing in the main() function."""
    def setUp(self):
        """Set up a temporary directory and mock configuration."""
        self.test_dir = tempfile.mkdtemp(prefix="exp_manager_main_")
        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Experiment': {'num_replications': '1'},
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

    @patch('src.experiment_manager._create_new_experiment_directory')
    def test_main_fails_with_action_flag_and_no_dir(self, mock_create):
        """Verify main() exits if action flags are used without a target directory."""
        for flag in ['--reprocess', '--migrate']:
            with self.subTest(flag=flag):
                with self.assertRaises(SystemExit) as cm:
                    with patch.object(sys, 'argv', ['script.py', flag]):
                        experiment_manager.main()
                self.assertEqual(cm.exception.code, 1)
                mock_create.assert_not_called()

    @patch('experiment_auditor.get_experiment_state', side_effect=KeyboardInterrupt)
    def test_main_exits_gracefully_on_keyboard_interrupt(self, mock_get_state):
        """Verify the main loop catches KeyboardInterrupt and exits correctly."""
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', self.test_dir]):
                experiment_manager.main()
        self.assertEqual(cm.exception.code, experiment_manager.AUDIT_ABORTED_BY_USER)

    @patch('pathlib.Path.glob', return_value=[]) # No run dirs found
    @patch('src.experiment_manager._run_finalization')
    @patch('src.experiment_manager._run_reprocess_mode', return_value=True)
    @patch('experiment_auditor.get_experiment_state')
    def test_reprocess_flag_on_empty_dir(self, mock_get_state, mock_reprocess, mock_finalize, mock_glob):
        """Verify --reprocess on an empty dir calls reprocess mode with an empty list."""
        # The state machine will see it as complete, but the reprocess flag forces one run.
        mock_get_state.return_value = ("COMPLETE", [], "")
        
        with patch.object(sys, 'argv', ['script.py', self.test_dir, '--reprocess']):
            experiment_manager.main()
        
        # It should find no runs, and therefore the payload passed to reprocess should be empty.
        mock_reprocess.assert_called_once()
        args, _ = mock_reprocess.call_args
        self.assertEqual(args[0], []) # The payload should be an empty list.
        mock_finalize.assert_called_once()

    @patch('experiment_auditor.get_experiment_state')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=False)
    def test_main_exits_if_reprocess_dir_not_found(self, mock_exists, mock_makedirs, mock_get_state):
        """Verify main() exits if --reprocess is used with a non-existent directory."""
        non_existent_dir = os.path.join(self.test_dir, "non_existent")
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', non_existent_dir, '--reprocess']):
                experiment_manager.main()
        
        self.assertEqual(cm.exception.code, 1)
        mock_makedirs.assert_not_called()
        # Verify the main loop was never entered, ensuring the test is fast.
        mock_get_state.assert_not_called()

    @patch('src.experiment_manager._run_finalization')
    @patch('experiment_auditor.get_experiment_state')
    @patch('src.experiment_manager.get_config_value')
    def test_state_aggregation_needed_breaks_loop_and_finalizes(self, mock_get_config, mock_get_state, mock_finalize):
        """Tests that AGGREGATION_NEEDED state breaks the loop and proceeds to finalization."""
        mock_get_config.side_effect = self._get_config_side_effect
        mock_get_state.return_value = ("AGGREGATION_NEEDED", {}, "")

        with patch.object(sys, 'argv', ['script.py', self.test_dir]):
            experiment_manager.main()

        mock_get_state.assert_called_once()
        mock_finalize.assert_called_once()

    @patch('sys.exit')
    @patch('os.environ', {})
    def test_main_uses_config_path_override(self, mock_exit):
        """Verify --config-path sets environ variable before module import."""
        # Create a dummy config file
        config_path = os.path.join(self.test_dir, 'test_config.ini')
        with open(config_path, 'w') as f:
            f.write('[Experiment]\nnum_replications = 5\n')
        
        # Reload the experiment_manager module to test the early parsing logic
        import importlib
        with patch.object(sys, 'argv', ['script.py', self.test_dir, f'--config-path={config_path}']):
            importlib.reload(experiment_manager)
        
        # Check that the environment variable was set correctly during module import
        self.assertIn('PROJECT_CONFIG_OVERRIDE', os.environ)
        self.assertEqual(os.environ['PROJECT_CONFIG_OVERRIDE'], os.path.abspath(config_path))
        
        # Clean up by reloading without the config override
        with patch.object(sys, 'argv', ['script.py']):
            importlib.reload(experiment_manager)

    @patch('sys.exit')
    @patch('importlib.reload')
    @patch('os.environ', {})
    def test_main_skips_reload_if_modules_not_present(self, mock_reload, mock_exit):
        """Verify main() does not try to reload modules that aren't in sys.modules."""
        
        # Create a mock dictionary that intercepts the 'in' operator for our specific modules,
        # forcing the 'if ... in sys.modules' check to be False.
        class MockModules(dict):
            def __contains__(self, key):
                if key in ['config_loader', 'experiment_auditor']:
                    return False
                return super().__contains__(key)

        mock_modules_dict = MockModules(sys.modules)

        config_path = os.path.join(self.test_dir, 'test_config.ini')
        with open(config_path, 'w') as f:
            f.write('[Experiment]\nnum_replications = 5\n')
        
        # Patch sys.modules with our mock. The 'from' imports will still work because
        # they use __getitem__, which is handled by the base dict.
        with patch('sys.modules', mock_modules_dict), \
             patch('experiment_auditor.get_experiment_state', return_value=("COMPLETE", {}, "")), \
             patch('src.experiment_manager._run_finalization'), \
             patch.object(sys, 'argv', ['script.py', self.test_dir, f'--config-path={config_path}']):
            
            experiment_manager.main()
        
        mock_reload.assert_not_called()


    @patch('src.experiment_manager._run_finalization')
    @patch('experiment_auditor.get_experiment_state', return_value=("COMPLETE", {}, ""))
    def test_main_with_force_color_flag(self, mock_get_state, mock_finalize):
        """Verify --force-color flag enables color constants."""
        with patch.object(sys, 'argv', ['script.py', self.test_dir, '--force-color']):
            experiment_manager.main()
        
        mock_finalize.assert_called_once()
        args, _ = mock_finalize.call_args
        colors_dict = args[2] # colors is the 3rd argument
        
        self.assertNotEqual(colors_dict['cyan'], '')
        self.assertNotEqual(colors_dict['reset'], '')


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_experiment_manager.py ===
