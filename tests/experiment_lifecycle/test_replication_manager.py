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
-   **Refactoring for Testability**: The `session_worker` function was extracted
  from `main()` in the production script to allow for direct patching, which
  is simpler and more reliable than mocking the `ThreadPoolExecutor`.
-   **Mocking**:
    -   `replication_manager.session_worker` is mocked directly to test the
      orchestrator's handling of worker failures without executor complexity.
    -   `src.replication_manager.subprocess.run` is mocked to test the overall
      pipeline orchestration and simulate the success of external scripts.
    -   `config_loader` is replaced with a mock to inject test-specific
      configuration and a temporary project root.
-   **Focus**: Tests verify the correct sequence of operations, proper argument
  passing to subprocesses, and graceful handling of failures for both
  "new run" and "reprocess" modes.
"""

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
import tempfile
import configparser
import types
import subprocess
import importlib
from pathlib import Path
from datetime import datetime

# Ensure src is in path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, '..', 'src'))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import the module under test
from src import replication_manager

# Suppress tqdm output during tests by replacing it with a mock class
class MockTqdm:
    def __init__(self, *args, **kwargs): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def update(self, n=1): pass

replication_manager.tqdm = MockTqdm

class TestReplicationManager(unittest.TestCase):
    """Test suite for replication_manager.py."""

    def setUp(self):
        """Set up a temporary project structure and mock configuration for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="orch_test_")
        self.project_root = self.test_dir.name
        self.output_dir = Path(self.project_root) / "output"
        self.output_dir.mkdir()
        
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
        # Reload the module under test to ensure it picks up the mocked config_loader.
        importlib.reload(replication_manager)

        self.subprocess_patcher = patch('src.replication_manager.subprocess.run')
        self.mock_subprocess = self.subprocess_patcher.start()
        
        self.shutil_patcher = patch('src.replication_manager.shutil.copy2')
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

    @patch('sys.exit')
    def test_reprocess_fails_with_invalid_dir(self, mock_exit):
        """Verify reprocess mode exits if --run_output_dir is invalid."""
        dir_to_check = Path('nonexistent_dir')
        try:
            with patch.object(sys, 'argv', ['script.py', '--reprocess', '--run_output_dir', str(dir_to_check)]):
                replication_manager.main()
            mock_exit.assert_called_with(1)
        finally:
            # Clean up the artifact in case the test run creates it.
            if dir_to_check.exists():
                shutil.rmtree(dir_to_check)

    @patch('sys.exit')
    def test_reprocess_fails_with_missing_config(self, mock_exit):
        """Verify reprocess mode exits if config.ini.archived is missing."""
        run_dir = self.output_dir / "run_without_config"
        run_dir.mkdir(parents=True)
        with patch.object(sys, 'argv', ['script.py', '--reprocess', '--run_output_dir', str(run_dir)]):
            replication_manager.main()
        mock_exit.assert_called_with(1)

    @patch('sys.exit')
    @patch('src.replication_manager.session_worker')
    def test_session_worker_failure_in_new_run_is_fatal(self, mock_session_worker, mock_exit):
        """Verify that a failed LLM session aborts a new run."""
        self.mock_subprocess.side_effect = self._mock_subprocess_side_effect
        # Simulate a worker failure by having the patched function return a failure tuple.
        mock_session_worker.return_value = (1, False, "Worker failed", 1.0)

        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
            replication_manager.main()

        mock_exit.assert_called_with(1)
        run_dir_actual = next(self.output_dir.iterdir())
        report_file = next(run_dir_actual.glob('replication_report_*.txt'))
        self.assertIn('Final Status:           FAILED', report_file.read_text())

    @patch('sys.exit')
    @patch('src.replication_manager.session_worker')
    def test_session_worker_failure_in_reprocess_sets_failed_status(self, mock_session_worker, mock_exit):
        """Verify a failed reprocess logs a warning and results in a FAILED status."""
        self.mock_subprocess.side_effect = self._mock_subprocess_side_effect
        # Simulate a worker failure by having the patched function return a failure tuple.
        mock_session_worker.return_value = (1, False, "Worker failed", 1.0)

        run_dir = self.output_dir / "existing_run"
        (run_dir / "session_queries").mkdir(parents=True)
        with (run_dir / "config.ini.archived").open("w") as f:
            f.write("[Study]\nnum_trials = 3\ngroup_size = 4\n")
            f.write("[LLM]\nmax_parallel_sessions=2\n")
            f.write("[General]\nresponses_subdir=session_responses\n")
            f.write("[Filenames]\napi_times_log=api.log\n")

        with self.assertLogs(level='WARNING') as cm:
            with patch.object(sys, 'argv', ['script.py', '--reprocess', '--run_output_dir', str(run_dir)]):
                replication_manager.main()
            self.assertTrue(any("failed to repair" in s for s in cm.output))

        # The pipeline should continue, but the final status should be FAILED
        mock_exit.assert_called_with(1)
        report_file = next(run_dir.glob('replication_report_*.txt'))
        self.assertIn('Final Status:           FAILED', report_file.read_text())
        report_file = next(run_dir.glob('replication_report_*.txt'))
        self.assertIn('Final Status:           FAILED', report_file.read_text())

    def test_keyboard_interrupt_is_handled_gracefully(self):
        """Verify KeyboardInterrupt is handled and sets the report status correctly."""
        # This side effect raises KeyboardInterrupt on the first script call (build),
        # then lets the subsequent call (generate report) succeed.
        def side_effect(command, **kwargs):
            script_name = os.path.basename(command[1])
            if 'build_llm_queries.py' in script_name:
                raise KeyboardInterrupt
            return self._mock_subprocess_side_effect(command, **kwargs)

        self.mock_subprocess.side_effect = side_effect

        # The main() function should catch the KeyboardInterrupt and call sys.exit(1).
        # Our class-level mock for sys.exit raises SystemExit, which we catch here.
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
                replication_manager.main()
        
        self.assertEqual(cm.exception.code, 1)

        # Verify that the final report was created and has the correct status.
        run_dir_actual = next(self.output_dir.iterdir())
        report_file = next(run_dir_actual.glob('replication_report_*.txt'))
        self.assertIn('Final Status:           INTERRUPTED BY USER', report_file.read_text())


class TestSessionWorker(unittest.TestCase):
    """Unit tests for the standalone session_worker function."""
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.test_dir.name) / "run"
        self.responses_dir = self.run_dir / "responses"
        self.src_dir = Path(self.test_dir.name) / "src"
        self.responses_dir.mkdir(parents=True)
        self.src_dir.mkdir()
        (self.run_dir / "session_queries").mkdir()
        (self.run_dir / "session_queries" / "llm_query_001.txt").touch()
        (self.run_dir / "config.ini.archived").touch()

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('src.replication_manager.subprocess.run')
    def test_worker_subprocess_error_with_stderr(self, mock_run):
        """Verify worker handles subprocess failure with stderr."""
        mock_run.return_value = MagicMock(returncode=1, stderr="Some error", stdout="")
        index, success, log, _ = replication_manager.session_worker(
            1, str(self.run_dir), str(self.responses_dir), "prompter.py", str(self.src_dir), False
        )
        self.assertFalse(success)
        self.assertIn("Some error", log)

    @patch('src.replication_manager.subprocess.run')
    def test_worker_orchestrator_exception(self, mock_run):
        """Verify worker handles an exception during subprocess.run."""
        mock_run.side_effect = ValueError("Orchestrator boom")
        index, success, log, _ = replication_manager.session_worker(
            1, str(self.run_dir), str(self.responses_dir), "prompter.py", str(self.src_dir), False
        )
        self.assertFalse(success)
        self.assertIn("Orchestrator boom", log)

class TestReplicationManagerCoverage(TestReplicationManager):
    """Additional tests to increase coverage for replication_manager.py."""

    def setUp(self):
        """Set up mocks for the coverage test suite."""
        super().setUp()
        # Set a default side effect for subprocess calls for all tests in this suite.
        # Individual tests can override this if they need specific mock behavior.
        self.mock_subprocess.side_effect = self._mock_subprocess_side_effect

    def test_generate_run_dir_name_bad_temp(self):
        """Verify generate_run_dir_name handles non-numeric temperature."""
        name = replication_manager.generate_run_dir_name('m', 'bad-temp', 1, 1, 'db', 1, 1, 's')
        self.assertIn('tmp-NA', name)

    @patch('builtins.print')
    def test_verbose_mode_prints_stdout(self, mock_print):
        """Verify --verbose prints subprocess stdout."""
        # Disable the default side_effect from setUp to use a specific return_value.
        self.mock_subprocess.side_effect = None
        self.mock_subprocess.return_value = MagicMock(stdout="Subprocess output", returncode=0)

        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir), '--verbose']):
            replication_manager.main()
        
        mock_print.assert_any_call("Subprocess output")

    @patch('os.path.exists', return_value=True)
    @patch('os.getenv')
    def test_config_override_is_used(self, mock_getenv, mock_exists):
        """Verify that PROJECT_CONFIG_OVERRIDE is used to archive the config."""
        override_path = '/path/to/override.ini'
        mock_getenv.return_value = override_path
        self.mock_subprocess.side_effect = self._mock_subprocess_side_effect

        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
            replication_manager.main()
        
        self.mock_shutil.assert_called_with(override_path, os.path.join(next(self.output_dir.iterdir()), 'config.ini.archived'))

    @patch('os.path.exists', return_value=True)
    def test_skips_sessions_if_responses_exist(self, mock_exists):
        """Verify Stage 2 is skipped if all response files are present."""
        run_dir = self.output_dir / "run_dir"
        (run_dir / "session_queries").mkdir(parents=True)
        (run_dir / "config.ini.archived").open("w").write("[Study]\nnum_trials=3")

        with self.assertLogs(level='INFO') as cm:
            with patch.object(sys, 'argv', ['script.py', '--reprocess', '--run_output_dir', str(run_dir)]):
                replication_manager.main()
            self.assertTrue(any("All required LLM response files already exist" in s for s in cm.output))

    def test_parser_summary_fallback(self):
        """Verify the parser summary regex handles non-matches gracefully."""
        def side_effect(command, **kwargs):
            if 'process_llm_responses.py' in os.path.basename(command[1]):
                return MagicMock(stdout="No summary here", returncode=0)
            return self._mock_subprocess_side_effect(command, **kwargs)
        
        self.mock_subprocess.side_effect = side_effect
        
        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
            replication_manager.main()

        analyze_call = next(c for c in self.mock_subprocess.call_args_list if 'analyze_llm_performance.py' in c.args[0][1])
        self.assertIn('0', analyze_call.args[0])

    @patch('os.remove', side_effect=OSError("Permission denied"))
    @patch('os.path.exists', return_value=True)
    def test_repair_mode_handles_cleanup_error(self, mock_exists, mock_remove):
        """Verify repair mode logs a warning if artifact cleanup fails."""
        run_dir = self.output_dir / "existing_run"
        (run_dir / "session_queries").mkdir(parents=True)
        with (run_dir / "config.ini.archived").open("w") as f:
            f.write("[Study]\nnum_trials=3\n[General]\nresponses_subdir=r")

        with self.assertLogs(level='WARNING') as cm:
            with patch.object(sys, 'argv', ['script.py', '--reprocess', '--run_output_dir', str(run_dir), '--indices', '1']):
                replication_manager.main()
            self.assertTrue(any("Could not remove old artifact" in s for s in cm.output))

    @patch('sys.exit')
    def test_failure_report_generation_failure(self, mock_exit):
        """Verify a failure during failure-report generation is handled."""
        def side_effect(command, **kwargs):
            if 'build_llm_queries.py' in os.path.basename(command[1]):
                raise subprocess.CalledProcessError(1, command, stderr="Build failed")
            if 'generate_replication_report.py' in os.path.basename(command[1]):
                raise Exception("Cannot write report")
            return MagicMock()

        self.mock_subprocess.side_effect = side_effect

        with self.assertLogs(level='ERROR') as cm:
            with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
                replication_manager.main()
            self.assertTrue(any("Could not generate a failure report" in s for s in cm.output))
        
        mock_exit.assert_called_with(1)

    def test_generate_run_dir_name_none_temp(self):
        """Verify generate_run_dir_name handles None temperature to cover TypeError."""
        name = replication_manager.generate_run_dir_name('m', None, 1, 1, 'db', 1, 1, 's')
        self.assertIn('tmp-NA', name)

    def test_new_run_without_base_output_dir(self):
        """Verify a new run works without --base_output_dir, using config fallback."""
        # This test does not pass the --base_output_dir argument.
        with patch.object(sys, 'argv', ['script.py', '--replication_num', '1']):
            replication_manager.main()
        
        # Verify that the output dir was created in the location from the mock config.
        config_output_dir = Path(self.project_root) / self.mock_config['General']['base_output_dir']
        self.assertTrue(config_output_dir.exists())
        self.assertEqual(len(list(config_output_dir.iterdir())), 1)

    def test_new_run_with_seeds(self):
        """Verify --base_seed and --qgen_base_seed are passed to the build script."""
        with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir), '--base_seed', '123', '--qgen_base_seed', '456']):
            replication_manager.main()

        build_call = next(c for c in self.mock_subprocess.call_args_list if 'build_llm_queries.py' in c.args[0][1])
        cmd_list = build_call.args[0]
        self.assertIn('--base_seed', cmd_list)
        self.assertIn('123', cmd_list)
        self.assertIn('--qgen_base_seed', cmd_list)
        self.assertIn('456', cmd_list)

    @patch('os.path.exists')
    def test_api_log_creation_is_skipped(self, mock_exists):
        """Verify api.log is not created if it already exists."""
        # Make os.path.exists return True for the api log, but False for responses.
        def exists_side_effect(path):
            if 'api.log' in str(path):
                return True
            if 'session_responses' in str(path):
                return False
            return True # Default for other paths like directories.
        mock_exists.side_effect = exists_side_effect

        with patch('src.replication_manager.open', new_callable=unittest.mock.mock_open) as mock_file:
            with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
                replication_manager.main()

            # Check that open was NOT called to create/write the header to api.log.
            was_called = any('api.log' in str(call.args[0]) and call.args[1] == 'w' for call in mock_file.call_args_list)
            self.assertFalse(was_called, "api.log should not have been opened in write mode")

    @patch('src.replication_manager.open')
    def test_final_report_update_io_error(self, mock_open_func):
        """Verify an IOError during final report update is logged."""
        # Let the real open work for everything except the final report update.
        original_open = open
        def open_side_effect(path, *args, **kwargs):
            if 'replication_report' in str(path) and args[0] == 'r+':
                raise IOError("Cannot write to report")
            return original_open(path, *args, **kwargs)
        mock_open_func.side_effect = open_side_effect
        
        with self.assertLogs(level='ERROR') as cm:
            # A simple happy path run will trigger the finalization logic.
            with patch.object(sys, 'argv', ['script.py', '--base_output_dir', str(self.output_dir)]):
                replication_manager.main()
            self.assertTrue(any("Could not update final report" in s for s in cm.output))


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_replication_manager.py ===
