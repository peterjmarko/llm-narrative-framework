# Filename: tests/test_replication_manager.py

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
import tempfile
import configparser
import subprocess
import importlib

class TestRunBatch(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and a controlled, in-memory config."""
        self.test_dir = tempfile.mkdtemp(prefix="replication_manager_test_")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {
                'num_replications': '2',
                'group_size': '10' # For fallback_key tests
            },
            'General': {
                'base_output_dir': 'output',
                'new_experiments_subdir': 'new_experiments',
                'experiment_dir_prefix': 'experiment_'
            }
        })
    
    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _get_robust_mock_config_side_effect(self):
        """
        Returns a side effect function that correctly mocks get_config_value
        by reading from this test's self.mock_config object.
        """
        def side_effect_func(config_obj, section, key, **kwargs):
            # This mock ignores the 'config_obj' arg and uses self.mock_config
            # which we can control from within each test.
            value_type = kwargs.get('value_type', str)
            fallback_key = kwargs.get('fallback_key')
            fallback = kwargs.get('fallback')
            
            val = None
            if self.mock_config.has_option(section, key):
                val = self.mock_config.get(section, key)
            elif fallback_key and self.mock_config.has_option(section, fallback_key):
                val = self.mock_config.get(section, fallback_key)
            
            if val is not None:
                try:
                    return value_type(val)
                except (ValueError, TypeError):
                    return fallback
            return fallback
        return side_effect_func

    def test_format_seconds_with_negative_input(self):
        """This test does not need mocks as it tests a pure function."""
        from src import replication_manager
        self.assertEqual(replication_manager.format_seconds(-100), "00:00:00")

    def test_replication_manager_happy_path(self):
        from src import replication_manager
        importlib.reload(replication_manager)

        # Use 'with' statement for patching to avoid issues with importlib.reload
        with patch('src.replication_manager.get_completed_replications', return_value=[]) as mock_get_completed, \
             patch('glob.glob', return_value=['mock_dir/run_..._rep-001_...']) as mock_glob, \
             patch('src.replication_manager.get_config_value') as mock_get_config_value, \
             patch('src.replication_manager.subprocess.run') as mock_subprocess_run:

            mock_get_config_value.side_effect = self._get_robust_mock_config_side_effect()
            mock_subprocess_run.return_value = MagicMock(returncode=0)

            with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir]):
                replication_manager.main()

            orchestrator_calls = [c for c in mock_subprocess_run.call_args_list if 'orchestrate_replication.py' in c.args[0][1]]
            self.assertEqual(len(orchestrator_calls), 2, "Expected orchestrator to be called for 2 replications.")

    def test_handles_keyboard_interrupt(self):
        from src import replication_manager
        importlib.reload(replication_manager)

        with patch('src.replication_manager.get_config_value') as mock_get_config_value, \
             patch('src.replication_manager.logging.warning') as mock_log_warning, \
             patch('src.replication_manager.subprocess.run') as mock_subprocess_run:
            
            mock_get_config_value.side_effect = self._get_robust_mock_config_side_effect()

            def selective_interrupt_side_effect(*args, **kwargs):
                cmd = args[0]
                if 'orchestrate_replication.py' in cmd[1]:
                    raise KeyboardInterrupt
                return MagicMock(returncode=0)
            mock_subprocess_run.side_effect = selective_interrupt_side_effect

            with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir]):
                replication_manager.main()

            mock_log_warning.assert_called_with("\n!!! Batch run interrupted by user during replication 1. Halting... !!!")

    def test_resumes_partially_completed_batch(self):
        from src import replication_manager
        importlib.reload(replication_manager)

        with patch('src.replication_manager.get_completed_replications') as mock_get_completed, \
             patch('src.replication_manager.get_config_value') as mock_get_config_value, \
             patch('src.replication_manager.subprocess.run') as mock_subprocess_run:

            mock_get_config_value.side_effect = self._get_robust_mock_config_side_effect()
            mock_get_completed.return_value = [1] # Simulate replication 1 is already done
            
            with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
                replication_manager.main()

            orchestrator_calls = [c for c in mock_subprocess_run.call_args_list if 'orchestrate_replication.py' in c.args[0][1]]
            self.assertEqual(len(orchestrator_calls), 1, "Should only run one new replication.")
            self.assertIn('2', orchestrator_calls[0].args[0], "Should be running replication 2.")

    def test_final_summary_reports_failures(self):
        from src import replication_manager
        importlib.reload(replication_manager)
        
        with patch('builtins.print') as mock_print, \
             patch('src.replication_manager.get_completed_replications', return_value=[]) as mock_get_completed, \
             patch('src.replication_manager.get_config_value') as mock_get_config_value, \
             patch('src.replication_manager.subprocess.run') as mock_subprocess_run:
            
            mock_get_config_value.side_effect = self._get_robust_mock_config_side_effect()

            def side_effect(*args, **kwargs):
                cmd = args[0]
                if 'orchestrate_replication.py' in cmd[1] and '1' in cmd:
                    raise subprocess.CalledProcessError(1, cmd)
                return MagicMock(returncode=0)
            mock_subprocess_run.side_effect = side_effect

            with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
                replication_manager.main()

            all_print_output = " ".join(str(call.args) for call in mock_print.call_args_list)
            self.assertIn("BATCH RUN COMPLETE WITH 1 FAILURE(S)", all_print_output)
            # More robustly check for the presence of the failed replication number
            self.assertIn("The following replications failed", all_print_output)
            self.assertIn("1", all_print_output)

    def test_reprocess_mode_happy_path(self):
        from src import replication_manager
        importlib.reload(replication_manager)

        with patch('src.replication_manager.find_run_dirs_by_depth') as mock_find_dirs, \
             patch('src.replication_manager.get_config_value') as mock_get_config_value, \
             patch('src.replication_manager.subprocess.run') as mock_subprocess_run:

            mock_get_config_value.side_effect = self._get_robust_mock_config_side_effect()
            mock_subprocess_run.return_value = MagicMock(returncode=0)
            
            run_dirs = []
            for i in [1, 2]:
                run_dir = os.path.join(self.output_dir, f"run_test_rep-00{i}_stuff")
                os.makedirs(run_dir)
                archived_config_path = os.path.join(run_dir, 'config.ini.archived')
                with open(archived_config_path, 'w') as f:
                    f.write('[Study]\ngroup_size = 10\n')
                run_dirs.append(run_dir)
            mock_find_dirs.return_value = run_dirs

            with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--reprocess']):
                replication_manager.main()

            orchestrator_calls = [c for c in mock_subprocess_run.call_args_list if '--reprocess' in c.args[0]]
            self.assertEqual(len(orchestrator_calls), 2)

if __name__ == '__main__':
    unittest.main(verbosity=2)