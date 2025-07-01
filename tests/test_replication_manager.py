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
        self.src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.src_dir, exist_ok=True)

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {'num_replications': '2'},
            'General': {'base_output_dir': self.output_dir}
        })

        for script in ["orchestrate_replication.py", "log_manager.py", "retry_failed_sessions.py", "compile_results.py"]:
            with open(os.path.join(self.src_dir, script), "w") as f:
                f.write("#!/usr/bin/env python\nimport sys\nsys.exit(0)")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.test_dir)

    def _mock_get_config_value(self, config_obj, section, key, value_type=str, fallback=None):
        """A side_effect function to replace get_config_value."""
        try:
            val = self.mock_config.get(section, key)
            return value_type(val)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback

    # --- The 3 passing tests ---

    # --- CORRECTED TEST ---
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.subprocess.run', side_effect=KeyboardInterrupt)
    def test_handles_keyboard_interrupt(self, mock_subprocess_run, mock_app_config):
        # Configure the mocked APP_CONFIG to use our test config's values
        mock_app_config.get.side_effect = self.mock_config.get
        
        # Import the module inside the test to ensure it sees the patched config
        from src import replication_manager

        # Assert that a SystemExit is raised when a KeyboardInterrupt occurs
        with self.assertRaises(SystemExit) as cm, patch.object(sys, 'argv', ['replication_manager.py']):
            replication_manager.main()
        
        self.assertEqual(cm.exception.code, 1, "Expected SystemExit with code 1 on KeyboardInterrupt")

    @patch('src.replication_manager.get_config_value')
    def test_invalid_run_range_exits(self, mock_get_config_value):
        mock_get_config_value.side_effect = self._mock_get_config_value
        from src import replication_manager
        importlib.reload(replication_manager)
        
        with self.assertRaises(SystemExit) as cm, patch.object(sys, 'argv', ['replication_manager.py', '--start-rep', '2', '--end-rep', '1']):
            replication_manager.main()
        self.assertEqual(cm.exception.code, 1)

    def test_format_seconds_with_negative_input(self):
        from src import replication_manager
        self.assertEqual(replication_manager.format_seconds(-100), "00:00:00")

    # --- REWRITTEN TEST 1 ---
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.subprocess.run')
    def test_replication_manager_happy_path(self, mock_subprocess_run, mock_find_report, mock_app_config):
        # Configure the mocked APP_CONFIG to use our test config's values.
        # The script calls get_config_value(APP_CONFIG,...), so we mock what APP_CONFIG.get() returns.
        mock_app_config.get.side_effect = self.mock_config.get

        # By importing the module *inside* the test, we ensure it sees the patched APP_CONFIG.
        from src import replication_manager

        mock_subprocess_run.return_value = MagicMock(returncode=0)
        with patch.object(sys, 'argv', ['replication_manager.py']):
            replication_manager.main()

        # Expected calls: 2x orchestrate, 2x log_manager update, 1x log_manager finalize, 1x retry, 1x compile
        self.assertEqual(mock_subprocess_run.call_count, 7)

    # --- REWRITTEN TEST 2 ---
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.subprocess.run')
    def test_resumes_partially_completed_batch(self, mock_subprocess_run, mock_find_report, mock_app_config):
        # Use the mock config instead of the real one
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager

        # Simulate that replication 1 is already complete by creating its output directory and report
        completed_run_dir = os.path.join(self.output_dir, "run_prefix_rep-1_")
        os.makedirs(completed_run_dir)
        with open(os.path.join(completed_run_dir, "replication_report_1.txt"), "w") as f:
            f.write("dummy report")

        with patch.object(sys, 'argv', ['replication_manager.py']):
            replication_manager.main()

        # Filter for calls to the orchestrator script
        orchestrator_calls = [c for c in mock_subprocess_run.call_args_list if 'orchestrate_replication.py' in c.args[0][1]]
        
        # Assert that only one new replication was run
        self.assertEqual(len(orchestrator_calls), 1)
        # Assert that the replication that ran was number 2
        self.assertIn('2', orchestrator_calls[0].args[0])

    # --- REWRITTEN TEST 3 ---
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.logging.error')
    @patch('src.replication_manager.subprocess.run')
    def test_handles_failed_replication_and_continues(self, mock_subprocess_run, mock_log_error, mock_find_report, mock_app_config):
        # Use the mock config instead of the real one
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager

        # Simulate a failure only for replication 1
        def side_effect(*args, **kwargs):
            cmd = args[0]  # This is the list of arguments
            # CORRECTED: Check for the script name within the script path (cmd[1])
            if 'orchestrate_replication.py' in cmd[1] and cmd[cmd.index('--replication_num') + 1] == '1':
                raise subprocess.CalledProcessError(1, cmd)
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect

        with patch.object(sys, 'argv', ['replication_manager.py']):
            replication_manager.main()

        # Assert that the failure was logged
        mock_log_error.assert_any_call("!!! Replication 1 failed. See logs above. Continuing with next replication. !!!")
        # Assert that the script continued and tried to run replication 2
        self.assertTrue(any('orchestrate_replication.py' in c.args[0][1] and '2' in c.args[0] for c in mock_subprocess_run.call_args_list))

    # --- REWRITTEN TEST 4 ---
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.logging.error')
    @patch('src.replication_manager.subprocess.run')
    def test_handles_failure_in_post_processing(self, mock_subprocess_run, mock_log_error, mock_find_report, mock_app_config):
        # Use the mock config instead of the real one
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager

        # Simulate a failure during the post-processing 'retry' step
        def side_effect(*args, **kwargs):
            cmd = args[0] # This is the list of arguments
            # CORRECTED: Check for the script name within the script path (cmd[1])
            if 'retry_failed_sessions.py' in cmd[1]:
                raise Exception("Simulated retry failure")
            return MagicMock(returncode=0)
        mock_subprocess_run.side_effect = side_effect

        with patch.object(sys, 'argv', ['replication_manager.py']):
            replication_manager.main()

        # Assert that the post-processing failure was logged
        mock_log_error.assert_any_call("An error occurred while running the retry script: Simulated retry failure")

    # --- NEW TEST FOR COVERAGE ---
    @patch('builtins.print')
    @patch('src.replication_manager.APP_CONFIG')
    @patch('src.replication_manager.find_latest_report', return_value="dummy_report.txt")
    @patch('src.replication_manager.subprocess.run')
    def test_quiet_mode_suppresses_replication_headers(self, mock_subprocess_run, mock_find_report, mock_app_config, mock_print):
        # Configure the mocked APP_CONFIG to use our test config's values
        mock_app_config.get.side_effect = self.mock_config.get
        from src import replication_manager

        mock_subprocess_run.return_value = MagicMock(returncode=0)
        # Run the main function with the --quiet flag
        with patch.object(sys, 'argv', ['replication_manager.py', '--quiet']):
            replication_manager.main()

        # Combine all arguments from all calls to print() into a single string
        all_print_output = " ".join(str(call.args) for call in mock_print.call_args_list)

        # Assert that the per-replication header was never printed
        self.assertNotIn("### RUNNING REPLICATION", all_print_output)

    # We will add the rewritten tests below this line

if __name__ == '__main__':
    unittest.main(verbosity=2)