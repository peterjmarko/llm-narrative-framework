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
# Filename: tests/experiment_lifecycle/test_experiment_auditor.py

"""
Unit Tests for the Experiment Auditor.

This script validates the state-detection logic of experiment_auditor.py
in an isolated environment with a mocked file system and configuration.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
from pathlib import Path
import configparser
import types
import importlib
import io
import builtins

# Import the module to test
from src import experiment_auditor

class TestExperimentAuditor(unittest.TestCase):
    """Test suite for experiment_auditor.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="exp_auditor_test_")
        self.exp_dir = Path(self.test_dir.name)
        
        self.sys_exit_patcher = patch('src.experiment_auditor.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()
        
        # A side effect function that correctly propagates the exit code
        def mock_exit(code=None):
            raise SystemExit(code)
        self.mock_sys_exit.side_effect = mock_exit
        
        self._setup_mock_config()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.config_patcher.stop()

    def _setup_mock_config(self):
        """Creates a mock config and applies it to the module."""
        mock_app_config = configparser.ConfigParser()
        mock_app_config.read_dict({
            'Study': {'num_replications': '2'}
        })
        
        self.mock_config = mock_app_config
        
        def dummy_get_config_value(config, section, key, value_type=str, fallback=None, **kwargs):
            if not config.has_option(section, key):
                return fallback
            if value_type is int:
                return config.getint(section, key, fallback=fallback)
            return config.get(section, key, fallback=fallback)

        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = self.mock_config
        fake_mod.get_config_value = dummy_get_config_value
        # Add the missing PROJECT_ROOT attribute to the mock module
        fake_mod.PROJECT_ROOT = str(self.exp_dir.parent)

        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(experiment_auditor)

    def _create_mock_run_dir(self, rep_num, k=10, m=10, is_valid=True, analysis_complete=True, report_complete=True):
        """Helper to create a mock run directory with a specified state of completeness."""
        run_name = f"run_20250101_120000_rep-{rep_num:03d}_sbj-{k:02d}_trl-{m:03d}_model-name"
        run_dir = self.exp_dir / run_name
        run_dir.mkdir()

        # Create config.ini.archived with all required keys
        (run_dir / "config.ini.archived").write_text(f"""
[Study]
group_size = {k}
num_trials = {m}
mapping_strategy = correct
[LLM]
model_name = mock-model
temperature = 0.5
[Filenames]
personalities_src = personalities_db.txt
""")
        # Create directories
        (run_dir / "session_queries").mkdir()
        (run_dir / "session_responses").mkdir()
        (run_dir / "analysis_inputs").mkdir()

        # Create query and response files
        for i in range(1, m + 1):
            (run_dir / "session_queries" / f"llm_query_{i:03d}.txt").touch()
            (run_dir / "session_responses" / f"llm_response_{i:03d}.txt").touch()
            (run_dir / "session_responses" / f"llm_response_{i:03d}_full.json").touch()
        (run_dir / "session_queries" / "mappings.txt").touch()

        if analysis_complete:
            # Create analysis files that are consistent with the report's n_valid_responses
            num_valid = 10 
            # all_scores.txt contains k*k lines per valid response
            scores_content = ("0\n" * k) * num_valid
            (run_dir / "analysis_inputs" / "all_scores.txt").write_text(scores_content)
            # all_mappings.txt contains a header + one line per valid response
            mappings_content = "header\n" + ("map\n" * num_valid)
            (run_dir / "analysis_inputs" / "all_mappings.txt").write_text(mappings_content)
            (run_dir / "REPLICATION_results.csv").touch()
        
        if report_complete:
            # Create a report with all required JSON metrics
            num_valid = 10
            # Construct the nested JSON part separately to avoid f-string parsing issues.
            pos_bias_json = '{"top1_pred_bias_std": 0, "true_false_score_diff": 0}'
            report_content = f"""
<<<METRICS_JSON_START>>>
{{
    "n_valid_responses": {num_valid}, "mwu_stouffer_z": 0, "mwu_stouffer_p": 0, "mwu_fisher_chi2": 0,
    "mwu_fisher_p": 0, "mean_effect_size_r": 0, "effect_size_r_p": 0, "mean_mrr": 0,
    "mrr_p": 0, "mean_top_1_acc": 0, "top_1_acc_p": 0, "mean_top_3_acc": 0,
    "top_3_acc_p": 0, "mean_rank_of_correct_id": 0, "rank_of_correct_id_p": 0,
    "bias_slope": 0, "bias_intercept": 0, "bias_r_value": 0, "bias_p_value": 0, "bias_std_err": 0,
    "mean_mrr_lift": 0, "mean_top_1_acc_lift": 0, "mean_top_3_acc_lift": 0,
    "positional_bias_metrics": {pos_bias_json}
}}
<<<METRICS_JSON_END>>>
"""
            (run_dir / "replication_report_2025-01-01_120000.txt").write_text(report_content)

        return run_dir

    def test_get_experiment_state_new_needed_for_empty_dir(self):
        """Verify that an empty directory is correctly identified as needing a new run."""
        # --- Arrange ---
        expected_reps = 2
        
        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)
        
        # --- Assert ---
        self.assertEqual(state_name, "NEW_NEEDED")
        self.assertEqual(payload, [])

    def test_get_experiment_state_complete(self):
        """Verify a complete experiment with all files present is identified as COMPLETE."""
        # --- Arrange ---
        expected_reps = 2
        self._create_mock_run_dir(rep_num=1)
        self._create_mock_run_dir(rep_num=2)

        # Create top-level summary files
        (self.exp_dir / "EXPERIMENT_results.csv").touch()
        (self.exp_dir / "experiment_log.csv").write_text("header\nBatchSummary,...")

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "COMPLETE")
        self.assertEqual(payload, [])

    def test_get_experiment_state_aggregation_needed(self):
        """Verify that a complete set of runs without top-level files is marked for aggregation."""
        # --- Arrange ---
        expected_reps = 2
        self._create_mock_run_dir(rep_num=1)
        self._create_mock_run_dir(rep_num=2)
        # Note: We do NOT create EXPERIMENT_results.csv or experiment_log.csv

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "AGGREGATION_NEEDED")
        self.assertEqual(payload, [])

    def test_get_experiment_state_new_needed_for_missing_reps(self):
        """Verify an incomplete set of runs is correctly identified as needing new replications."""
        # --- Arrange ---
        expected_reps = 3
        self._create_mock_run_dir(rep_num=1)
        # We only create 1 of the 3 expected runs

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "NEW_NEEDED")
        self.assertEqual(payload, [])

    def test_get_experiment_state_reprocess_needed_for_analysis_issue(self):
        """Verify a run with missing analysis files is marked for reprocessing."""
        # --- Arrange ---
        expected_reps = 1
        run_dir = self._create_mock_run_dir(
            rep_num=1,
            analysis_complete=False, # This is the key change for this test
            report_complete=False
        )

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "REPROCESS_NEEDED")
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['dir'], str(run_dir))

    def test_get_experiment_state_repair_needed_for_response_issue(self):
        """Verify a run with missing response files is marked for repair."""
        # --- Arrange ---
        expected_reps = 1
        run_dir = self._create_mock_run_dir(rep_num=1, m=5) # Create a run with 5 trials

        # Simulate missing responses for trials 3 and 5
        (run_dir / "session_responses" / "llm_response_003.txt").unlink()
        (run_dir / "session_responses" / "llm_response_005.txt").unlink()

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "REPAIR_NEEDED")
        self.assertEqual(len(payload), 1)
        repair_job = payload[0]
        self.assertEqual(repair_job['dir'], str(run_dir))
        self.assertEqual(repair_job['repair_type'], 'session_repair')
        self.assertEqual(repair_job['failed_indices'], [3, 5])

    def test_get_experiment_state_migration_needed_for_corrupted_run(self):
        """Verify a run with multiple error types is marked for migration."""
        # --- Arrange ---
        expected_reps = 1
        run_dir = self._create_mock_run_dir(rep_num=1)

        # Create a corrupted state:
        # 1. Config issue: Delete the archived config file.
        (run_dir / "config.ini.archived").unlink()
        # 2. Response issue: Delete a response file.
        (run_dir / "session_responses" / "llm_response_001.txt").unlink()

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "MIGRATION_NEEDED")
        self.assertEqual(len(payload), 1)
        # The payload should be a tuple of (run_name, (status, details))
        failed_run_name, (status, details) = payload[0]
        self.assertEqual(failed_run_name, run_dir.name)
        self.assertEqual(status, "RUN_CORRUPTED")


    def test_get_experiment_state_repair_needed_for_invalid_run_name(self):
        """Verify a run with an invalid directory name is marked for repair."""
        # --- Arrange ---
        expected_reps = 1
        # The name must start with "run_" to be picked up by the glob.
        # The auditor logic will then identify the malformed name.
        run_dir = self.exp_dir / "run_bad_name_format"
        run_dir.mkdir()

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "REPAIR_NEEDED")
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['repair_type'], 'full_replication_repair')

    def test_get_experiment_state_repair_needed_for_config_mismatch(self):
        """Verify a run with k/m config mismatch is marked for repair."""
        # --- Arrange ---
        expected_reps = 1
        # Create a run directory where the name implies k=10, m=10
        run_dir = self._create_mock_run_dir(rep_num=1, k=10, m=10)
        
        # Overwrite the config with a mismatched k value
        (run_dir / "config.ini.archived").write_text(
            "[Study]\ngroup_size = 5\nnum_trials = 10\n"
        )

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "REPAIR_NEEDED")
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['repair_type'], 'config_repair')

    def test_get_experiment_state_reprocess_needed_for_bad_report(self):
        """Verify a run with an incomplete report is marked for reprocessing."""
        # --- Arrange ---
        expected_reps = 1
        run_dir = self._create_mock_run_dir(rep_num=1, report_complete=False)

        # Create a report with a missing metric
        (run_dir / "replication_report_2025-01-01_120000.txt").write_text(
            '<<<METRICS_JSON_START>>>{"n_valid_responses": 10}<<<METRICS_JSON_END>>>'
        )

        # --- Act ---
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, expected_reps)

        # --- Assert ---
        self.assertEqual(state_name, "REPROCESS_NEEDED")
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]['dir'], str(run_dir))

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_complete_state(self, mock_stdout):
        """Verify the CLI output and exit code for a COMPLETE experiment."""
        # --- Arrange ---
        self._create_mock_run_dir(rep_num=1)
        (self.exp_dir / "EXPERIMENT_results.csv").touch()
        (self.exp_dir / "experiment_log.csv").write_text("BatchSummary")
        self.mock_config.set('Study', 'num_replications', '1')
        test_argv = ['experiment_auditor.py', str(self.exp_dir)]
        
        # --- Act ---
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        
        # --- Assert ---
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_ALL_VALID)
        self.assertIn("PASSED. Experiment is complete and valid.", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_quiet_flag(self, mock_stdout):
        """Verify the --quiet flag suppresses all output."""
        # --- Arrange ---
        test_argv = ['experiment_auditor.py', str(self.exp_dir), '--quiet']
        
        # --- Act ---
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        
        # --- Assert ---
        self.assertEqual(mock_stdout.getvalue(), "")


    def test_repair_needed_for_too_many_files(self):
        """Verify a run with too many response files is marked for repair."""
        run_dir = self._create_mock_run_dir(rep_num=1, m=5)
        # Create an extra response file
        (run_dir / "session_responses" / "llm_response_999.txt").touch()

        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")

    def test_repair_needed_for_query_issue(self):
        """Verify a run with missing query files is marked for repair."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        (run_dir / "session_queries" / "mappings.txt").unlink()

        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")
        self.assertEqual(payload[0]['repair_type'], 'full_replication_repair')

    def test_reprocess_needed_for_bad_nested_report_key(self):
        """Verify reprocess state for a report with a malformed nested dict."""
        run_dir = self._create_mock_run_dir(rep_num=1, report_complete=False)
        # Write a report where the nested key is not a dict
        report_content = (
            '<<<METRICS_JSON_START>>>\n'
            '{"n_valid_responses": 10, "mwu_stouffer_z": 0, "mwu_stouffer_p": 0, "mwu_fisher_chi2": 0, '
            '"mwu_fisher_p": 0, "mean_effect_size_r": 0, "effect_size_r_p": 0, "mean_mrr": 0, "mrr_p": 0, '
            '"mean_top_1_acc": 0, "top_1_acc_p": 0, "mean_top_3_acc": 0, "top_3_acc_p": 0, '
            '"mean_rank_of_correct_id": 0, "rank_of_correct_id_p": 0, "bias_slope": 0, '
            '"bias_intercept": 0, "bias_r_value": 0, "bias_p_value": 0, "bias_std_err": 0, '
            '"mean_mrr_lift": 0, "mean_top_1_acc_lift": 0, "mean_top_3_acc_lift": 0, '
            '"positional_bias_metrics": "this is not a dict"}\n'
            '<<<METRICS_JSON_END>>>'
        )
        (run_dir / "replication_report_2025-01-01_120000.txt").write_text(report_content)

        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    def test_aggregation_needed_for_missing_log(self):
        """Verify aggregation state when experiment_log.csv is missing."""
        self._create_mock_run_dir(rep_num=1)
        (self.exp_dir / "EXPERIMENT_results.csv").touch()
        # Do not create experiment_log.csv
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "AGGREGATION_NEEDED")

    def test_aggregation_needed_for_non_finalized_log(self):
        """Verify aggregation state when experiment_log.csv is not finalized."""
        self._create_mock_run_dir(rep_num=1)
        (self.exp_dir / "EXPERIMENT_results.csv").touch()
        (self.exp_dir / "experiment_log.csv").write_text("header only")
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "AGGREGATION_NEEDED")

    def test_main_cli_with_config_path(self):
        """Verify the CLI uses --config-path and reloads the config module."""
        # Create a temp config file setting reps to 1
        test_config_file = self.exp_dir / "test_config.ini"
        test_config_file.write_text("[Study]\nnum_replications = 1\n")
        
        # Create 1 complete run
        self._create_mock_run_dir(rep_num=1)
        (self.exp_dir / "EXPERIMENT_results.csv").touch()
        (self.exp_dir / "experiment_log.csv").write_text("BatchSummary")

        test_argv = ['auditor.py', str(self.exp_dir), '--config-path', str(test_config_file)]
        
        # This side effect simulates the config being reloaded with the new value.
        def reload_side_effect(module):
            self.mock_config.set('Study', 'num_replications', '1')

        with patch('importlib.reload', side_effect=reload_side_effect) as mock_reload:
            with self.assertRaises(SystemExit) as cm:
                with patch.object(sys, 'argv', test_argv):
                    experiment_auditor.main()
            mock_reload.assert_called_once_with(sys.modules['config_loader'])
        
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_ALL_VALID)

    def test_repair_needed_for_empty_config(self):
        """Verify repair state for a run with an empty config file."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        (run_dir / "config.ini.archived").write_text("")
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")

    def test_repair_needed_for_bad_config_value_type(self):
        """Verify repair state for a config with a bad value type."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        # group_size should be an integer
        (run_dir / "config.ini.archived").write_text("[Study]\ngroup_size=bad_value\n")
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")


    def test_reprocess_needed_for_missing_report(self):
        """Verify reprocess state for a run that is missing its report file."""
        run_dir = self._create_mock_run_dir(rep_num=1, report_complete=False)
        # Ensure the final results CSV is present to distinguish from an analysis issue
        (run_dir / "REPLICATION_results.csv").touch()
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    def test_reprocess_needed_for_bad_nested_sub_key(self):
        """Verify reprocess state for a report with a missing nested sub-key."""
        run_dir = self._create_mock_run_dir(rep_num=1, report_complete=False)
        # Write a report where the nested dict is missing a key
        report_content = (
            '<<<METRICS_JSON_START>>>\n'
            '{"n_valid_responses": 10, "mwu_stouffer_z": 0, "mwu_stouffer_p": 0, "mwu_fisher_chi2": 0, '
            '"mwu_fisher_p": 0, "mean_effect_size_r": 0, "effect_size_r_p": 0, "mean_mrr": 0, "mrr_p": 0, '
            '"mean_top_1_acc": 0, "top_1_acc_p": 0, "mean_top_3_acc": 0, "top_3_acc_p": 0, '
            '"mean_rank_of_correct_id": 0, "rank_of_correct_id_p": 0, "bias_slope": 0, '
            '"bias_intercept": 0, "bias_r_value": 0, "bias_p_value": 0, "bias_std_err": 0, '
            '"mean_mrr_lift": 0, "mean_top_1_acc_lift": 0, "mean_top_3_acc_lift": 0, '
            '"positional_bias_metrics": {"top1_pred_bias_std": 0}}\n' # Missing true_false_score_diff
            '<<<METRICS_JSON_END>>>'
        )
        (run_dir / "replication_report_2025-01-01_120000.txt").write_text(report_content)
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_migration_needed(self, mock_stdout):
        """Verify CLI output and exit code for MIGRATION_NEEDED state."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        (run_dir / "config.ini.archived").unlink() # Config issue
        (run_dir / "session_responses" / "llm_response_001.txt").unlink() # Response issue
        
        test_argv = ['auditor.py', str(self.exp_dir)]
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_NEEDS_MIGRATION)
        self.assertIn("Experiment needs MIGRATION", mock_stdout.getvalue())

    def test_count_lines_in_file_exception_handling(self):
        """Verify _count_lines_in_file returns 0 on exception."""
        with patch('builtins.open', side_effect=IOError("Test error")):
            count = experiment_auditor._count_lines_in_file("dummy_path")
        self.assertEqual(count, 0)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_empty_dir(self, mock_stdout):
        """Verify CLI output for an empty experiment directory."""
        test_argv = ['auditor.py', str(self.exp_dir)]
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_NEEDS_REPAIR)
        self.assertIn("No 'run_*' directories found", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_long_run_name_truncation(self, mock_stdout):
        """Verify CLI truncates very long run directory names."""
        long_name = "run_20250101_120000_rep-001_sbj-10_trl-010_model-a-very-long-model-name-that-will-exceed-the-limit"
        run_dir = self.exp_dir / long_name
        run_dir.mkdir() # create an invalid run to force output
        
        test_argv = ['auditor.py', str(self.exp_dir)]
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        
        output = mock_stdout.getvalue()
        # Max name len is 40. Should be truncated to 37 chars + "..."
        self.assertIn("run_20250101_120000_rep-001_sbj-10_tr...", output)
        self.assertNotIn(long_name, output)


    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_reprocess_needed(self, mock_stdout):
        """Verify CLI output and exit code for REPROCESS_NEEDED state."""
        self._create_mock_run_dir(rep_num=1, analysis_complete=False)
        test_argv = ['auditor.py', str(self.exp_dir)]
        self.mock_config.set('Study', 'num_replications', '1')
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_NEEDS_REPROCESS)
        self.assertIn("Experiment needs an UPDATE", mock_stdout.getvalue())

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_aggregation_needed(self, mock_stdout):
        """Verify CLI output and exit code for AGGREGATION_NEEDED state."""
        self._create_mock_run_dir(rep_num=1) # One complete run
        # Do not create experiment-level files
        self.mock_config.set('Study', 'num_replications', '1')
        test_argv = ['auditor.py', str(self.exp_dir)]
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_NEEDS_AGGREGATION)
        self.assertIn("Experiment needs FINALIZATION", mock_stdout.getvalue())

    def test_reprocess_needed_for_malformed_json_report(self):
        """Verify reprocess state for a report with malformed JSON."""
        run_dir = self._create_mock_run_dir(rep_num=1, report_complete=False)
        # Write a report with invalid JSON between the markers
        (run_dir / "replication_report_2025-01-01_120000.txt").write_text(
            '<<<METRICS_JSON_START>>>{"key": "value", }<<<METRICS_JSON_END>>>'
        )
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    def test_repair_needed_for_index_mismatch(self):
        """Verify repair needed for mismatched query/response file indices."""
        run_dir = self._create_mock_run_dir(rep_num=1, m=3)
        (run_dir / "session_responses" / "llm_response_002.txt").unlink()
        (run_dir / "session_responses" / "llm_response_002_full.json").unlink()
        
        state_name, payload, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")
        self.assertEqual(payload[0]['failed_indices'], [2])

    def test_reprocess_needed_for_analysis_data_inconsistency(self):
        """Verify reprocess state when report's n_valid differs from analysis file counts."""
        run_dir = self._create_mock_run_dir(rep_num=1, k=5, m=10) # n_valid_responses in report will be 10
        # Overwrite scores file to have only 9 matrices
        (run_dir / "analysis_inputs" / "all_scores.txt").write_text(("0\n" * 5) * 9)
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    def test_helper_count_matrices_with_k_zero(self):
        """Verify _count_matrices_in_file returns 0 if k is 0."""
        count = experiment_auditor._count_matrices_in_file("dummy_path", k=0)
        self.assertEqual(count, 0)
        
    def test_helper_count_lines_skip_header_false(self):
        """Verify _count_lines_in_file counts all lines when skip_header is False."""
        file_path = self.exp_dir / "test.txt"
        file_path.write_text("line1\nline2\nline3\n")
        count = experiment_auditor._count_lines_in_file(str(file_path), skip_header=False)
        self.assertEqual(count, 3)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_repair_needed(self, mock_stdout):
        """Verify CLI output and exit code for REPAIR_NEEDED state."""
        self._create_mock_run_dir(rep_num=1, m=2)
        (self.exp_dir / "run_20250101_120000_rep-001_sbj-10_trl-002_model-name" / "session_responses" / "llm_response_001.txt").unlink()
        self.mock_config.set('Study', 'num_replications', '1')
        test_argv = ['auditor.py', str(self.exp_dir)]
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_NEEDS_REPAIR)
        self.assertIn("Experiment needs REPAIR", mock_stdout.getvalue())

    def test_get_file_indices_ignores_non_matching_files(self):
        """Verify _get_file_indices ignores files that glob finds but regex rejects."""
        run_dir = self._create_mock_run_dir(rep_num=1, m=2)
        # This file will be found by the glob `llm_query_*.txt`
        (run_dir / "session_queries" / "llm_query_abc.txt").touch()
        # The regex `llm_query_(\d+).txt` will not match it, so it should be ignored.
        indices = experiment_auditor._get_file_indices(run_dir, experiment_auditor.FILE_MANIFEST["query_files"])
        self.assertEqual(indices, {1, 2})

    def test_count_matrices_in_file_exception_handling(self):
        """Verify _count_matrices_in_file returns 0 on exception."""
        with patch('builtins.open', side_effect=IOError("Test error")):
            count = experiment_auditor._count_matrices_in_file("dummy_path", k=5)
        self.assertEqual(count, 0)

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_force_color(self, mock_stdout):
        """Verify --force-color adds color codes to output."""
        # Note: We don't check if stdout is a TTY, so this forces color on.
        test_argv = ['auditor.py', str(self.exp_dir), '--force-color']
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        self.assertIn('\033[93m', mock_stdout.getvalue()) # Check for yellow color code

    @patch('src.experiment_auditor.get_experiment_state')
    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_unknown_state(self, mock_stdout, mock_get_state):
        """Verify CLI output and exit code for an UNKNOWN state."""
        mock_get_state.return_value = ("UNKNOWN", [], {})
        test_argv = ['auditor.py', str(self.exp_dir)]
        with self.assertRaises(SystemExit) as cm:
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        
        # Unknown state should default to the MIGRATION exit code
        self.assertEqual(cm.exception.code, experiment_auditor.AUDIT_NEEDS_MIGRATION)
        self.assertIn("UNKNOWN STATE", mock_stdout.getvalue())

    def test_repair_needed_for_malformed_config(self):
        """Verify repair state for a config with a syntax error."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        # Malformed config (no section header)
        (run_dir / "config.ini.archived").write_text("group_size=10\n")
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")

    def test_repair_needed_for_incomplete_manifests(self):
        """Verify repair state for a run with an incomplete set of manifests."""
        run_dir = self._create_mock_run_dir(rep_num=1, m=5)
        # Create only one manifest file when 5 are expected (and some exist)
        (run_dir / "session_queries" / "llm_query_001_manifest.txt").touch()
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")

    def test_aggregation_needed_for_unreadable_log(self):
        """Verify aggregation state when experiment_log.csv is unreadable."""
        self._create_mock_run_dir(rep_num=1)
        (self.exp_dir / "EXPERIMENT_results.csv").touch()
        (self.exp_dir / "experiment_log.csv").touch() # File exists
        
        original_open = builtins.open
        def mock_open(file, *args, **kwargs):
            if 'experiment_log.csv' in str(file):
                raise IOError("Permission denied")
            return original_open(file, *args, **kwargs)

        with patch('builtins.open', mock_open):
            state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        
        self.assertEqual(state_name, "AGGREGATION_NEEDED")

    @patch('sys.stdout', new_callable=io.StringIO)
    def test_main_cli_non_interactive_flag(self, mock_stdout):
        """Verify --non-interactive flag suppresses the recommendation line."""
        test_argv = ['auditor.py', str(self.exp_dir), '--non-interactive']
        with self.assertRaises(SystemExit):
            with patch.object(sys, 'argv', test_argv):
                experiment_auditor.main()
        
        output = mock_stdout.getvalue()
        self.assertIn("Audit Result", output)
        self.assertNotIn("Recommendation:", output)

    def test_reprocess_needed_for_report_missing_n_valid(self):
        """Verify reprocess state for a report missing the n_valid_responses key."""
        run_dir = self._create_mock_run_dir(rep_num=1, report_complete=False)
        report_content = (
            '<<<METRICS_JSON_START>>>\n'
            '{"mwu_stouffer_z": 0}\n' # Some other valid key, but n_valid is missing
            '<<<METRICS_JSON_END>>>'
        )
        (run_dir / "replication_report_2025-01-01_120000.txt").write_text(report_content)
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")


    @patch('sys.stderr', new_callable=io.StringIO)
    def test_fatal_error_on_config_loader_import(self, mock_stderr):
        """Verify script exits with a fatal error if config_loader cannot be imported."""
        with patch.dict('sys.modules', {'config_loader': None}):
            with self.assertRaises(SystemExit) as cm:
                importlib.reload(experiment_auditor)
        
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("FATAL: Could not import config_loader.py", mock_stderr.getvalue())

    def test_repair_needed_for_bad_config_float_type(self):
        """Verify repair state for a config with a non-float temperature."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        config_content = (
            "[Study]\ngroup_size = 10\nnum_trials = 10\nmapping_strategy=correct\n"
            "[LLM]\nmodel_name=mock\ntemperature=not-a-float\n"
            "[Filenames]\npersonalities_src=db.txt\n"
        )
        (run_dir / "config.ini.archived").write_text(config_content)
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPAIR_NEEDED")

    @patch('src.experiment_auditor._count_lines_in_file', side_effect=Exception("Read error"))
    def test_reprocess_needed_for_analysis_file_read_error(self, mock_count_lines):
        """Verify reprocess state when analysis files are unreadable."""
        self._create_mock_run_dir(rep_num=1)
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    def test_reprocess_needed_for_report_missing_end_marker(self):
        """Verify reprocess state for a report missing its JSON end marker."""
        run_dir = self._create_mock_run_dir(rep_num=1)
        (run_dir / "replication_report_2025-01-01_120000.txt").write_text(
            '<<<METRICS_JSON_START>>>{"key": "value"}'
        )
        state_name, _, _ = experiment_auditor.get_experiment_state(self.exp_dir, 1)
        self.assertEqual(state_name, "REPROCESS_NEEDED")

    def test_main_cli_loads_config_if_not_in_sys_modules(self):
        """Verify main() loads config_loader if it's not already imported."""
        test_config_file = self.exp_dir / "test_config.ini"
        test_config_file.write_text("[Study]\nnum_replications = 0\n")
        test_argv = ['auditor.py', str(self.exp_dir), '--config-path', str(test_config_file)]
        
        real_config_loader = sys.modules.pop('config_loader', None)
        try:
            with patch('importlib.reload') as mock_reload:
                with self.assertRaises(SystemExit):
                    with patch.object(sys, 'argv', test_argv):
                        experiment_auditor.main()
                mock_reload.assert_not_called()
        finally:
            if real_config_loader:
                sys.modules['config_loader'] = real_config_loader

if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_experiment_auditor.py ===
