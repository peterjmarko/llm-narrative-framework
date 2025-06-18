# Filename: tests/test_run_batch.py

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
import tempfile
import configparser
import types
import importlib

class TestRunBatch(unittest.TestCase):

    def setUp(self):
        """Set up a temporary project structure with mock scripts."""
        self.test_project_root_obj = tempfile.TemporaryDirectory(prefix="run_batch_test_")
        self.test_project_root = self.test_project_root_obj.name

        self.src_dir = os.path.join(self.test_project_root, 'src')
        self.output_dir = os.path.join(self.test_project_root, 'output')
        os.makedirs(self.src_dir)
        os.makedirs(self.output_dir)

        # Create mock config.ini
        self.mock_config = configparser.ConfigParser()
        self.mock_config['Study'] = {'num_replications': '2'} # Test with 2 reps
        self.mock_config['General'] = {'base_output_dir': 'output'}
        with open(os.path.join(self.test_project_root, 'config.ini'), 'w') as f:
            self.mock_config.write(f)

        # Define the real source directory to copy from
        src_dir_real = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')

        # Copy the REAL script under test into the mock src directory
        shutil.copy2(os.path.join(src_dir_real, 'run_batch.py'), self.src_dir)

        # Create DUMMY versions of the scripts that run_batch.py CALLS
        scripts_to_mock = [
            "orchestrate_experiment.py",
            "retry_failed_sessions.py",
            "compile_results.py"
        ]
        for script in scripts_to_mock:
            with open(os.path.join(self.src_dir, script), 'w') as f:
                f.write(f"#!/usr/bin/env python3\nprint('Mock {script} executed')")

        # Mock the config_loader module to use our temporary environment
        self.original_sys_path = list(sys.path)
        sys.path.insert(0, self.src_dir)
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback=None, value_type=str):
            if not config.has_option(section, key): return fallback
            if value_type is int: return config.getint(section, key)
            return config.get(section, key)
        fake_mod.get_config_value = dummy_get_config_value
        sys.modules['config_loader'] = fake_mod

        # Import the REAL script under test, now that it's in the path
        self.run_batch_module = importlib.import_module("run_batch")

    def tearDown(self):
        """Clean up the temporary directory."""
        sys.path[:] = self.original_sys_path
        self.test_project_root_obj.cleanup()

    @patch('run_batch.subprocess.run')
    def test_run_batch_happy_path(self, mock_subprocess_run):
        """
        Tests that run_batch.py reads config, loops correctly, and calls
        all required downstream scripts with the correct arguments.
        """
        # Arrange: Mock a successful subprocess run for all calls
        mock_subprocess_run.return_value = MagicMock(returncode=0)

        # Act: Run the main function of run_batch.py
        self.run_batch_module.main()

        # Assert: Check the calls to subprocess.run
        # Expected calls: 2 for orchestrator, 1 for retry, 1 for compile
        self.assertEqual(mock_subprocess_run.call_count, 4)

        calls = mock_subprocess_run.call_args_list

        # --- Assert Replication 1 Call ---
        cmd1 = calls[0].args[0]
        self.assertIn("orchestrate_experiment.py", cmd1[1])
        self.assertIn("--replication_num", cmd1)
        self.assertEqual(cmd1[cmd1.index("--replication_num") + 1], "1")
        self.assertIn("--base_seed", cmd1)
        self.assertEqual(cmd1[cmd1.index("--base_seed") + 1], "1000")
        self.assertIn("--qgen_base_seed", cmd1)
        self.assertEqual(cmd1[cmd1.index("--qgen_base_seed") + 1], "1500")

        # --- Assert Replication 2 Call ---
        cmd2 = calls[1].args[0]
        self.assertIn("orchestrate_experiment.py", cmd2[1])
        self.assertIn("--replication_num", cmd2)
        self.assertEqual(cmd2[cmd2.index("--replication_num") + 1], "2")
        self.assertIn("--base_seed", cmd2)
        self.assertEqual(cmd2[cmd2.index("--base_seed") + 1], "2000")
        self.assertIn("--qgen_base_seed", cmd2)
        self.assertEqual(cmd2[cmd2.index("--qgen_base_seed") + 1], "2500")

        # --- Assert Retry Script Call ---
        cmd3 = calls[2].args[0]
        self.assertIn("retry_failed_sessions.py", cmd3[1])
        self.assertEqual(cmd3[2], self.output_dir) # Check it passes the output dir

        # --- Assert Compile Script Call ---
        cmd4 = calls[3].args[0]
        self.assertIn("compile_results.py", cmd4[1])
        self.assertEqual(cmd4[2], self.output_dir) # Check it passes the output dir

if __name__ == '__main__':
    unittest.main(verbosity=2)