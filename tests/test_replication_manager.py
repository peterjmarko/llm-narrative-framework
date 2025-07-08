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
import re

class TestRunBatch(unittest.TestCase):

    def setUp(self):
        """Set up a temporary directory and a controlled, in-memory config."""
        self.test_dir = tempfile.mkdtemp(prefix="replication_manager_test_")
        self.output_dir = os.path.join(self.test_dir, "output")
        self.src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.src_dir, exist_ok=True)

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {'num_replications': '2'},
            'General': {
                'base_output_dir': self.output_dir,
                'new_experiments_subdir': 'new_experiments',
                'experiment_dir_prefix': 'experiment_'
            }
        })

        for script in ["orchestrate_replication.py", "log_manager.py", "retry_failed_sessions.py", "compile_results.py"]:
            with open(os.path.join(self.src_dir, script), "w") as f:
                f.write("#!/usr/bin/env python\nimport sys\nsys.exit(0)")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _mock_get_config_value(self, config_obj, section, key, value_type=str, fallback=None, **kwargs):
        """A more robust side_effect to replace get_config_value that handles incorrect positional args."""
        # This logic handles the case where the fallback is accidentally passed as the value_type
        if not isinstance(value_type, type):
            fallback = value_type
            value_type = str
        
        try:
            val = self.mock_config.get(section, key)
            if value_type is not None:
                return value_type(val)
            return val
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    # --- The 3 passing tests ---

    @patch('src.replication_manager.logging.warning')
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.subprocess.run')
    def test_handles_keyboard_interrupt(self, mock_subprocess_run, mock_app_config, mock_log_warning):
        """Tests that a KeyboardInterrupt is caught, logged, and halts the loop."""
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Define a side effect that only raises on the orchestrator call
        def selective_interrupt_side_effect(*args, **kwargs):
            cmd = args[0]
            if 'orchestrate_replication.py' in cmd[1]:
                raise KeyboardInterrupt
            # For other calls (like log_manager), return a successful mock process
            return MagicMock(returncode=0)

        mock_subprocess_run.side_effect = selective_interrupt_side_effect

        # Run main() and expect it to handle the interrupt without crashing the test
        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir]):
            replication_manager.main()

        # Assert that the correct warning was logged
        mock_log_warning.assert_called_with("\n!!! Batch run interrupted by user during replication 1. Halting... !!!")

    def test_format_seconds_with_negative_input(self):
        from src import replication_manager
        self.assertEqual(replication_manager.format_seconds(-100), "00:00:00")

    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.subprocess.run')
    def test_replication_manager_happy_path(self, mock_subprocess_run, mock_find_report, mock_app_config):
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Make the mock create the directories the main script expects to find
        def side_effect_create_dir(*args, **kwargs):
            cmd = args[0]
            if 'orchestrate_replication.py' in cmd[1]:
                rep_num_index = cmd.index('--replication_num') + 1
                rep_num = cmd[rep_num_index]
                run_dir = os.path.join(self.output_dir, f'run_test_rep-{int(rep_num):03d}_seed123')
                os.makedirs(run_dir, exist_ok=True)
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect_create_dir

        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
            replication_manager.main()

        # Expected calls for 2 reps: 1 log_start, 2 orchestrate, 2 bias, 1 log_rebuild, 1 compile, 1 finalize = 8
        self.assertEqual(mock_subprocess_run.call_count, 8)

    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.subprocess.run')
    def test_resumes_partially_completed_batch(self, mock_subprocess_run, mock_find_report, mock_app_config):
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Simulate that replication 1 is already complete by creating a correctly named directory
        completed_run_dir = os.path.join(self.output_dir, "run_test_rep-001_seed123")
        os.makedirs(completed_run_dir)
        with open(os.path.join(completed_run_dir, "replication_report_1.txt"), "w") as f:
            f.write("dummy report")

        # Mock the creation of the directory for the second run
        def side_effect_create_dir(*args, **kwargs):
            cmd = args[0]
            if 'orchestrate_replication.py' in cmd[1]:
                run_dir = os.path.join(self.output_dir, f'run_test_rep-002_seed456')
                os.makedirs(run_dir, exist_ok=True)
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect_create_dir
        
        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
            replication_manager.main()

        orchestrator_calls = [c for c in mock_subprocess_run.call_args_list if 'orchestrate_replication.py' in c.args[0][1]]
        self.assertEqual(len(orchestrator_calls), 1)
        self.assertIn('2', orchestrator_calls[0].args[0])

    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.logging.error')
    @patch('src.replication_manager.subprocess.run')
    def test_handles_failed_replication_and_continues(self, mock_subprocess_run, mock_log_error, mock_find_report, mock_app_config):
        # Use the mock config instead of the real one
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Simulate a failure only for replication 1
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if 'orchestrate_replication.py' in cmd[1] and '1' in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect

        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
            replication_manager.main()

        # Assert that the failure was logged
        mock_log_error.assert_any_call("!!! Replication 1 failed. Check its report for details. Continuing... !!!")
        # Assert that the script continued and tried to run replication 2
        self.assertTrue(any('orchestrate_replication.py' in c.args[0][1] and '2' in c.args[0] for c in mock_subprocess_run.call_args_list))

    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.logging.error')
    @patch('src.replication_manager.subprocess.run')
    def test_handles_failure_in_post_processing(self, mock_subprocess_run, mock_log_error, mock_find_report, mock_app_config):
        # Use the mock config instead of the real one
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Simulate a failure during the final compilation step
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if 'compile_results.py' in cmd[1]:
                raise Exception("Simulated compilation failure")
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect

        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
            replication_manager.main()
    
        # Assert that the post-processing failure was logged
        mock_log_error.assert_any_call("An error occurred while running the final compilation script: Simulated compilation failure")

    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.subprocess.run')
    def test_default_mode_is_quiet(self, mock_subprocess_run, mock_app_config):
        """Tests that the default mode correctly passes --quiet to the orchestrator."""
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager) # Reload to apply patches

        mock_subprocess_run.return_value = MagicMock(returncode=0)
        # Run the main function with default arguments (no --verbose)
        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
            replication_manager.main()

        # Find calls to the orchestrator script
        orchestrator_calls = [
            c.args[0] for c in mock_subprocess_run.call_args_list
            if 'orchestrate_replication.py' in c.args[0][1]
        ]
        # Assert that the orchestrator was called at least once
        self.assertGreater(len(orchestrator_calls), 0, "Orchestrator script was not called")
        # Assert that the --quiet flag was included in the command
        self.assertIn('--quiet', orchestrator_calls[0])

    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.subprocess.run')
    def test_reprocess_mode_happy_path(self, mock_subprocess_run, mock_app_config):
        """Tests the --reprocess flag with depth=0."""
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Create two fake run directories to be "found"
        # and create the necessary archived config file inside each.
        for i in [1, 2]:
            run_dir = os.path.join(self.output_dir, f"run_test_rep-00{i}_stuff")
            os.makedirs(run_dir)
            archived_config_path = os.path.join(run_dir, 'config.ini.archived')
            with open(archived_config_path, 'w') as f:
                f.write('[Study]\ngroup_size = 10\n')

        # Make the mock create the directories the main script expects to find
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        # Run with --reprocess and --depth 0
        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--reprocess', '--depth', '0']):
            replication_manager.main()

        # Expected calls: 2x orchestrate, 2x bias, 1x log_rebuild, 1x compile, 1x finalize = 7
        self.assertEqual(mock_subprocess_run.call_count, 7)
        
        # Check that orchestrator was called with --reprocess
        orchestrator_calls = [
            c.args[0] for c in mock_subprocess_run.call_args_list
            if 'orchestrate_replication.py' in c.args[0][1]
        ]
        self.assertIn('--reprocess', orchestrator_calls[0])

    @patch('builtins.print')
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.subprocess.run')
    def test_no_target_dir_creates_default(self, mock_subprocess_run, mock_app_config, mock_print):
        """Tests that a default directory is created when none is specified."""
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        mock_subprocess_run.return_value = MagicMock(returncode=0)

        # Run with no target_dir argument, which forces default creation
        with patch.object(sys, 'argv', ['replication_manager.py', '--end-rep', '1']):
            replication_manager.main()

        # Check that the print output contains the expected message
        self.assertTrue(any("No target directory specified." in str(call.args) for call in mock_print.call_args_list))
        # Check that the newly created default path exists
        # This requires finding the generated path from the print statements
        printed_output = "".join(str(call.args) for call in mock_print.call_args_list)
        path_match = re.search(r"Using default from config: (.+?)\\x1b", printed_output)
        self.assertIsNotNone(path_match, "Could not find default path in print output.")
        created_path = path_match.group(1).strip()
        self.assertTrue(os.path.isdir(created_path))

    @patch('builtins.print')
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.subprocess.run')
    def test_final_summary_reports_failures(self, mock_subprocess_run, mock_app_config, mock_print):
        """Tests that the final summary correctly lists failed replications."""
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager
        importlib.reload(replication_manager)

        # Simulate a failure for replication 1
        def side_effect(*args, **kwargs):
            cmd = args[0]
            if 'orchestrate_replication.py' in cmd[1] and '1' in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            # Create the directory for the successful run
            elif 'orchestrate_replication.py' in cmd[1] and '2' in cmd:
                run_dir = os.path.join(self.output_dir, f'run_test_rep-002_seed456')
                os.makedirs(run_dir, exist_ok=True)
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect

        with patch.object(sys, 'argv', ['replication_manager.py', self.output_dir, '--end-rep', '2']):
            replication_manager.main()

        # Check that the final print output includes the failure summary
        all_print_output = " ".join(str(call.args) for call in mock_print.call_args_list)
        self.assertIn("BATCH RUN COMPLETE WITH 1 FAILURE(S)", all_print_output)
        self.assertIn("- 1", all_print_output)


if __name__ == '__main__':
    unittest.main(verbosity=2)

# === End of tests/test_replication_manager.py ===