#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
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
# Filename: tests/experiment_lifecycle/test_replication_manager.py

"""
Unit Tests for the Single Replication Manager.

This script validates the control flow and logic of `replication_manager.py`.
It uses mocking to isolate the manager from its subprocess dependencies
(e.g., `build_llm_queries.py`, `llm_prompter.py`) and the file system.

Test Strategy:
-   **Isolation**: Each test runs in a temporary directory.
-   **Mocking**:
    -   `subprocess.run` and `ThreadPoolExecutor` are mocked to prevent real
      script execution and to simulate success or failure of pipeline stages.
    -   `config_loader` is replaced with a mock to inject test-specific
      configuration and a temporary project root.
    -   `shutil.copy2` and `datetime` are mocked to verify behavior like
      config archival and predictable directory naming.
-   **Focus**: Tests verify the correct sequence of operations, proper argument
  passing to subprocesses, and graceful handling of failures for both
  "new run" and "reprocess" modes.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile
import configparser
import types
import subprocess
from pathlib import Path
from datetime import datetime

# Ensure src is in path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import the module under test
from src import replication_manager

class TestReplicationManager(unittest.TestCase):
    """Test suite for replication_manager.py."""

    def setUp(self):
        """Set up a temporary project structure and mock configuration for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="orch_test_")
        self.project_root = self.test_dir.name
        self.output_dir = Path(self.project_root) / "output"
        # The orchestrator creates the output dir, so we don't do it here.
        
        self.run_dir_actual = None # Will be set by the test runs

        # This more sophisticated side effect will handle different glob patterns
        def glob_side_effect(pattern):
            if "replication_report_" in pattern:
                # Find the report file the subprocess mock created
                run_dir = Path(pattern).parent
                if run_dir.exists():
                    return list(run_dir.glob("replication_report_*.txt"))
                return []
            if "session_queries" in pattern:
                return [
                    str(Path(pattern).parent / 'llm_query_001.txt'),
                    str(Path(pattern).parent / 'llm_query_002.txt'),
                    str(Path(pattern).parent / 'llm_query_003.txt')
                ]
            return []
        self.glob_patcher = patch('replication_manager.glob.glob', side_effect=glob_side_effect)
        self.mock_glob = self.glob_patcher.start()

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Study': {'num_replications': '2', 'num_trials': '3', 'group_size': '4', 'mapping_strategy': 'correct'},
            'LLM': {'model_name': 'test/model', 'temperature': '0.5', 'max_parallel_sessions': '2'},
            'Filenames': {'personalities_src': 'db.txt', 'api_times_log': 'api.log'},
            'General': {'base_output_dir': 'output', 'responses_subdir': 'session_responses'}
        })

        self.config_loader_patcher = patch.dict('sys.modules', {'config_loader': self._create_mock_config_loader()})
        self.mock_config_loader = self.config_loader_patcher.start()

        self.subprocess_patcher = patch('replication_manager.subprocess.run')
        self.mock_subprocess = self.subprocess_patcher.start()
        
        self.shutil_patcher = patch('replication_manager.shutil.copy2')
        self.mock_shutil = self.shutil_patcher.start()

    def tearDown(self):
        """Clean up resources and stop patches after each test."""
        self.test_dir.cleanup()
        self.config_loader_patcher.stop()
        self.subprocess_patcher.stop()
        self.shutil_patcher.stop()
        self.glob_patcher.stop()

    def _create_mock_config_loader(self):
        """Creates a mock module to replace config_loader."""
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.project_root
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback_key=None, fallback=None, value_type=str):
            val = config.get(section, key, fallback=None)
            if val is None and fallback_key: val = config.get(section, fallback_key, fallback=fallback)
            if val is None: return fallback
            return value_type(val)
        fake_mod.get_config_value = dummy_get_config_value
        return fake_mod

    def _mock_subprocess_side_effect(self, command, **kwargs):
        """A general-purpose side effect for successful subprocess runs."""
        script_name = os.path.basename(command[1])
        
        # Default success object
        success_obj = MagicMock(stdout="Success", returncode=0)

        if 'generate_replication_report.py' in script_name:
            run_dir = Path(command[command.index('--run_output_dir') + 1])
            # Use a Windows-compatible timestamp format
            safe_timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
            with (run_dir / f"replication_report_{safe_timestamp}.txt").open("w") as f:
                f.write("Final Status:                  PENDING\n")
            success_obj.stdout = "Report generated."
            return success_obj
            
        if 'process_llm_responses.py' in script_name:
            success_obj.stdout = '<<<PARSER_SUMMARY:3:3:warnings=0>>>'
            return success_obj
            
        return success_obj

    @patch('replication_manager.datetime.datetime')
    def test_generate_run_dir_name(self, mock_datetime_cls):
        """Verify the run directory name is generated correctly."""
        mock_datetime_cls.now.return_value = datetime(2025, 1, 1, 12, 0, 0)
        
        name = replication_manager.generate_run_dir_name(
            'google/test-model', 0.75, 100, 10, 'test_db.txt', 1, 30, 'random'
        )
        self.assertEqual(name, 'run_20250101_120000_rep-001_test-model_tmp-0.75_test_db_sbj-10_trl-100_rps-030_mps-random')

    @patch('replication_manager.ThreadPoolExecutor')
    def test_happy_path_new_run(self, mock_executor):
        """Test a full, successful execution of a new replication."""
        self.mock_subprocess.side_effect = self._mock_subprocess_side_effect

        mock_executor.return_value.__enter__.return_value.submit.side_effect = \
            lambda fn, index: MagicMock(result=lambda: fn(index))
        
        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir), '--replication_num', '1']):
            replication_manager.main()

        # 6 stages + 3 worker calls to llm_prompter
        self.assertEqual(self.mock_subprocess.call_count, 9)
        
        run_dir_actual = next(self.output_dir.iterdir())
        report_file = next(run_dir_actual.glob('replication_report_*.txt'))
        self.assertIn('Final Status:           COMPLETED', report_file.read_text())

    @patch('replication_manager.ThreadPoolExecutor')
    def test_reprocess_path(self, mock_executor):
        """Test a successful run in reprocess mode."""
        self.mock_subprocess.side_effect = self._mock_subprocess_side_effect
        run_dir = self.output_dir / "existing_run"
        (run_dir / "session_queries").mkdir(parents=True)
        
        with (run_dir / "config.ini.archived").open("w") as f:
            f.write("[Study]\nnum_trials = 3\ngroup_size = 4\n") # Matches glob mock
            f.write("[LLM]\nmax_parallel_sessions=2\n")
            f.write("[General]\nresponses_subdir=session_responses\n")
            f.write("[Filenames]\napi_times_log=api.log\n")

        with patch.object(sys, 'argv', ['script.py', '--reprocess', '--run_output_dir', str(run_dir)]):
            replication_manager.main()

        # Reprocess: build is skipped (1), workers are called (3), 5 stages run (5) = 8
        self.assertEqual(self.mock_subprocess.call_count, 8)
        report_file = next(run_dir.glob('replication_report_*.txt'))
        self.assertIn('Final Status:           COMPLETED', report_file.read_text())

    @patch('sys.exit')
    def test_failure_path_aborts_pipeline_and_creates_report(self, mock_exit):
        """Test that a subprocess failure halts execution but still creates a FAILED report."""
        def failure_side_effect(command, **kwargs):
            script_name = os.path.basename(command[1])
            if 'build_llm_queries.py' in script_name:
                raise subprocess.CalledProcessError(1, command, stderr="Build failed")
            if 'generate_replication_report.py' in script_name:
                run_dir = Path(command[command.index('--run_output_dir') + 1])
                # Simulate the report file being created with PENDING status
                safe_timestamp = datetime.now().isoformat().replace(':', '-')
                with (run_dir / f"replication_report_{safe_timestamp}.txt").open("w") as f:
                    f.write("Final Status:                  PENDING\n")
                return MagicMock(stdout="Dummy report created")
            return MagicMock()

        self.mock_subprocess.side_effect = failure_side_effect

        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
            replication_manager.main()

        self.assertEqual(self.mock_subprocess.call_count, 2)
        mock_exit.assert_called_with(1)
        run_dir_actual = next(self.output_dir.iterdir())
        report_files = list(run_dir_actual.glob('replication_report_*.txt'))
        self.assertEqual(len(report_files), 1, "A report file should be created on failure.")
        # The orchestrator's final block updates the file. Check for the correct final state.
        self.assertIn('Final Status:           FAILED', report_files[0].read_text().replace('\r\n', '\n'))

if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_replication_manager.py ===
