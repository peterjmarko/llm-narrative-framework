#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Filename: tests/test_replication_manager.py

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
import tempfile
import configparser
import subprocess
import time

from src import replication_manager

class TestReplicationManager(unittest.TestCase):
    """Unified test class for replication_manager.py."""

    def setUp(self):
        """Set up a temporary directory and a controlled, in-memory config."""
        self.test_dir = tempfile.mkdtemp(prefix="rep_manager_")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.output_dir, exist_ok=True)

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {'num_replications': '2', 'group_size': '10'},
            'General': {'base_output_dir': self.output_dir, 'new_experiments_subdir': 'new'}
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
        return kwargs.get('fallback')

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run')
    def test_handles_replication_failure(self, mock_subprocess_run, mock_get_config_value):
        """Test that a failure in the orchestrator script is handled gracefully."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        
        def selective_fail_effect(cmd_list, **kwargs):
            if any("orchestrate_replication.py" in s for s in cmd_list):
                raise subprocess.CalledProcessError(1, cmd_list)
            return MagicMock(returncode=0)
        
        mock_subprocess_run.side_effect = selective_fail_effect

        with patch('src.replication_manager.logging.error') as mock_log_error, \
             patch.object(sys, 'argv', ['script.py', self.output_dir]):
            
            replication_manager.main()

        mock_log_error.assert_any_call("!!! Replication 1 failed. Check its report for details. Continuing... !!!")

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run')
    def test_reprocess_happy_path(self, mock_subprocess_run, mock_get_config_value):
        """Test that reprocess mode calls the orchestrator with the --reprocess flag."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        
        run_dir = os.path.join(self.output_dir, "run_1")
        os.makedirs(run_dir)
        with open(os.path.join(run_dir, 'config.ini.archived'), 'w') as f:
            f.write('[Study]\ngroup_size=10\n')

        # The key is to patch find_run_dirs_by_depth to return our controlled directory
        with patch('src.replication_manager.find_run_dirs_by_depth', return_value=[run_dir]):
            cli_args = ['script.py', self.output_dir, '--reprocess']
            with patch.object(sys, 'argv', cli_args):
                replication_manager.main()

        # Verify orchestrate_replication was called with the correct flags
        orchestrator_calls = [c for c in mock_subprocess_run.call_args_list if any("orchestrate_replication.py" in s for s in c.args[0])]
        self.assertEqual(len(orchestrator_calls), 1)
        self.assertIn('--reprocess', orchestrator_calls[0].args[0])
        self.assertIn(run_dir, orchestrator_calls[0].args[0])

    @patch('builtins.print')
    def test_reprocess_mode_no_run_dirs_found(self, mock_print):
        """Test behavior when no 'run_*' directories are found for reprocessing."""
        empty_dir = os.path.join(self.test_dir, "empty")
        os.makedirs(empty_dir)
        with patch.object(sys, 'argv', ['script.py', empty_dir, '--reprocess']):
            replication_manager.main()
        mock_print.assert_any_call("No 'run_*' directories found. Exiting.")

    def test_utility_functions(self):
        """Test utility functions for basic functionality."""
        # Test format_seconds
        self.assertEqual(replication_manager.format_seconds(3661), "1:01:01")
        self.assertEqual(replication_manager.format_seconds(-5), "00:00:00")
        self.assertEqual(replication_manager.format_seconds(0), "0:00:00")
        
        # Test find_latest_report with no reports
        self.assertIsNone(replication_manager.find_latest_report(self.test_dir))
        
        # Test find_latest_report with reports
        report1 = os.path.join(self.test_dir, "replication_report_1.txt")
        report2 = os.path.join(self.test_dir, "replication_report_2.txt")
        with open(report1, 'w') as f:
            f.write("old report")
        time.sleep(0.01)  # Ensure different timestamps
        with open(report2, 'w') as f:
            f.write("new report")
        
        latest = replication_manager.find_latest_report(self.test_dir)
        self.assertEqual(latest, report2)

    def test_get_completed_replications(self):
        """Test identification of completed replications."""
        # Create some run directories with reports
        run1_dir = os.path.join(self.output_dir, "run_rep-001_test")
        run2_dir = os.path.join(self.output_dir, "run_rep-003_test") 
        run3_dir = os.path.join(self.output_dir, "run_rep-005_test")
        
        os.makedirs(run1_dir)
        os.makedirs(run2_dir) 
        os.makedirs(run3_dir)
        
        # Add reports to run1 and run3 only
        with open(os.path.join(run1_dir, "replication_report_001.txt"), 'w') as f:
            f.write("completed")
        with open(os.path.join(run3_dir, "replication_report_005.txt"), 'w') as f:
            f.write("completed")
        
        completed = replication_manager.get_completed_replications(self.output_dir)
        self.assertEqual(completed, {1, 5})

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run')
    @patch('src.replication_manager.glob.glob')
    def test_normal_replication_mode(self, mock_glob, mock_subprocess_run, mock_get_config_value):
        """Test normal replication execution mode."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        
        # Mock no existing runs (so all replications need to run)
        mock_glob.return_value = []
        
        # Mock successful subprocess calls
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        with patch('src.replication_manager.get_completed_replications', return_value=set()), \
            patch('builtins.print') as mock_print:
            
            cli_args = ['script.py', self.output_dir, '--end-rep', '2']
            with patch.object(sys, 'argv', cli_args):
                replication_manager.main()
        
        # Should have called orchestrate_replication twice (for rep 1 and 2)
        orchestrator_calls = [c for c in mock_subprocess_run.call_args_list 
                            if any("orchestrate_replication.py" in str(c) for c in c.args[0])]
        self.assertEqual(len(orchestrator_calls), 2)
        
        # Should have called post-processing scripts
        compile_calls = [c for c in mock_subprocess_run.call_args_list 
                        if any("compile_results.py" in str(c) for c in c.args[0])]
        self.assertTrue(len(compile_calls) >= 1)

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run')
    @patch('src.replication_manager.datetime')
    def test_default_directory_creation(self, mock_datetime, mock_subprocess_run, mock_get_config_value):
        """Test that default directory is created when none specified."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        mock_datetime.datetime.now.return_value.strftime.return_value = "20240101_120000"
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        with patch('src.replication_manager.get_completed_replications', return_value={1, 2}), \
            patch('builtins.print') as mock_print:
            
            # No target_dir specified
            cli_args = ['script.py', '--end-rep', '2']
            with patch.object(sys, 'argv', cli_args):
                replication_manager.main()
        
        # Should print message about using default directory
        default_dir_msgs = [str(call) for call in mock_print.call_args_list 
                        if "No target directory specified" in str(call)]
        self.assertTrue(len(default_dir_msgs) > 0)

    def test_find_run_dirs_by_depth(self):
        """Test finding run directories at different depths."""
        # Create nested structure
        level1_dir = os.path.join(self.test_dir, "run_test1")
        level2_dir = os.path.join(self.test_dir, "subdir", "run_test2") 
        os.makedirs(level1_dir)
        os.makedirs(level2_dir)
        
        # Test depth 0 (only immediate children)
        dirs_depth0 = replication_manager.find_run_dirs_by_depth(self.test_dir, 0)
        self.assertIn(level1_dir, dirs_depth0)
        self.assertNotIn(level2_dir, dirs_depth0)
        
        # Test depth 1 (includes subdirectories)
        dirs_depth1 = replication_manager.find_run_dirs_by_depth(self.test_dir, 1)
        self.assertIn(level1_dir, dirs_depth1)
        self.assertIn(level2_dir, dirs_depth1)
        
        # Test depth -1 (recursive)
        dirs_recursive = replication_manager.find_run_dirs_by_depth(self.test_dir, -1)
        self.assertIn(level1_dir, dirs_recursive)
        self.assertIn(level2_dir, dirs_recursive)

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run')
    def test_keyboard_interrupt_handling(self, mock_subprocess_run, mock_get_config_value):
        """Test keyboard interrupt during replication execution."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        
        def interrupt_on_orchestrator(cmd_list, **kwargs):
            if any("orchestrate_replication.py" in s for s in cmd_list):
                raise KeyboardInterrupt()
            return MagicMock(returncode=0)
        
        mock_subprocess_run.side_effect = interrupt_on_orchestrator
        
        with patch('src.replication_manager.get_completed_replications', return_value=set()), \
            patch('src.replication_manager.logging.warning') as mock_log_warning:
            
            cli_args = ['script.py', self.output_dir, '--end-rep', '2']
            with patch.object(sys, 'argv', cli_args):
                replication_manager.main()  # Should complete normally, not exit
        
        # Should log the interruption
        interrupt_calls = [call for call in mock_log_warning.call_args_list 
                        if "interrupted by user" in str(call)]
        self.assertTrue(len(interrupt_calls) > 0)
        
        # Should only call orchestrator once (for rep 1), not twice (rep 2 skipped due to interrupt)
        orchestrator_calls = [c for c in mock_subprocess_run.call_args_list 
                            if any("orchestrate_replication.py" in str(c) for c in c.args[0])]
        self.assertEqual(len(orchestrator_calls), 1)

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run')
    def test_post_processing_failures(self, mock_subprocess_run, mock_get_config_value):
        """Test handling of post-processing script failures."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        
        def fail_on_compile(cmd_list, **kwargs):
            if any("compile_results.py" in s for s in cmd_list):
                raise subprocess.CalledProcessError(1, cmd_list)
            return MagicMock(returncode=0)
        
        mock_subprocess_run.side_effect = fail_on_compile
        
        with patch('src.replication_manager.get_completed_replications', return_value={1, 2}), \
            patch('src.replication_manager.logging.error') as mock_log_error:
            
            cli_args = ['script.py', self.output_dir, '--end-rep', '2']
            with patch.object(sys, 'argv', cli_args):
                replication_manager.main()
        
        # Should log compilation error
        compile_errors = [call for call in mock_log_error.call_args_list 
                        if "compilation script" in str(call)]
        self.assertTrue(len(compile_errors) > 0)

    @patch('src.replication_manager.get_config_value')
    def test_reprocess_mode_error_target_dir_required(self, mock_get_config_value):
        """Test reprocess mode without target directory fails."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        
        cli_args = ['script.py', '--reprocess']
        with patch.object(sys, 'argv', cli_args):
            with self.assertRaises(SystemExit):
                replication_manager.main()

    @patch('src.replication_manager.get_config_value')
    @patch('src.replication_manager.subprocess.run') 
    def test_verbose_mode(self, mock_subprocess_run, mock_get_config_value):
        """Test verbose mode passes correct flags."""
        mock_get_config_value.side_effect = self._get_config_side_effect
        mock_subprocess_run.return_value = MagicMock(returncode=0)
        
        with patch('src.replication_manager.get_completed_replications', return_value=set()):
            cli_args = ['script.py', self.output_dir, '--end-rep', '1', '--verbose']
            with patch.object(sys, 'argv', cli_args):
                replication_manager.main()
        
        # Check that --quiet is NOT passed when --verbose is used
        orchestrator_calls = [c for c in mock_subprocess_run.call_args_list 
                            if any("orchestrate_replication.py" in str(c) for c in c.args[0])]
        if orchestrator_calls:
            # Verify --quiet is not in the command
            cmd_args = orchestrator_calls[0].args[0]
            self.assertNotIn('--quiet', cmd_args)

    def test_find_run_dirs_edge_cases(self):
        """Test edge cases in find_run_dirs_by_depth."""
        # Test with depth < -1 (should be normalized to -1)
        result = replication_manager.find_run_dirs_by_depth(self.test_dir, -5)
        self.assertIsInstance(result, list)
        
        # Test empty directory
        empty_dir = os.path.join(self.test_dir, "empty")
        os.makedirs(empty_dir)
        result = replication_manager.find_run_dirs_by_depth(empty_dir, 0)
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_replication_manager.py ===