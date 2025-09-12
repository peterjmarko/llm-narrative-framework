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
# Filename: tests/test_experiment_auditor.py

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
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = mock_app_config
        fake_mod.get_config_value = lambda cfg, sec, key, **kwargs: cfg.get(sec, key, **kwargs)
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


if __name__ == '__main__':
    unittest.main()

# === End of tests/test_experiment_auditor.py ===
