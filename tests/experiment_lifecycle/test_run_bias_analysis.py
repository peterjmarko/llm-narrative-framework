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
# Filename: tests/experiment_lifecycle/test_run_bias_analysis.py

"""
Unit Tests for the Diagnostic Bias Analyzer (run_bias_analysis.py).

This script validates the file I/O and metric calculation logic of the
bias analyzer in an isolated environment.
"""

import unittest
from unittest.mock import patch
import sys
import tempfile
import json
from pathlib import Path
import pandas as pd
import numpy as np

# Import the module to test
from src import run_bias_analysis

class TestRunBiasAnalysis(unittest.TestCase):
    """Test suite for run_bias_analysis.py."""

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="bias_analysis_test_")
        self.replication_dir = Path(self.test_dir.name)
        self.analysis_dir = self.replication_dir / "analysis_inputs"
        self.analysis_dir.mkdir(parents=True)

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir.cleanup()

    def _create_happy_path_files(self, k=2):
        """Helper to create a standard set of valid input files."""
        # Trial 1: Scores lean towards correct, but no perfect bias
        (self.analysis_dir / "all_scores.txt").write_text(
            "0.9 0.1\n"  # P1 picks D1 (correct)
            "0.2 0.8\n"  # P2 picks D2 (correct)
            "\n"
            "0.3 0.7\n"  # P1 picks D2 (incorrect)
            "0.6 0.4\n"  # P2 picks D1 (correct)
        )
        (self.analysis_dir / "all_mappings.txt").write_text(
            "1 2\n"  # Trial 1: P1->D1, P2->D2
            "1 2\n"  # Trial 2: P1->D1, P2->D2
        )
        initial_metrics = {"mean_mrr": 0.75}
        with open(self.analysis_dir / "replication_metrics.json", 'w') as f:
            json.dump(initial_metrics, f)

    def test_main_happy_path_updates_metrics(self):
        """Verify main() correctly calculates and injects bias metrics."""
        # --- Arrange ---
        self._create_happy_path_files(k=2)
        test_argv = ['run_bias_analysis.py', str(self.replication_dir), '--k_value', '2']

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            run_bias_analysis.main()

        # --- Assert ---
        metrics_file = self.analysis_dir / "replication_metrics.json"
        self.assertTrue(metrics_file.is_file())
        with open(metrics_file, 'r') as f:
            results = json.load(f)

        self.assertIn("positional_bias_metrics", results)
        bias_metrics = results["positional_bias_metrics"]

        # Expected values:
        # Top-1 choices: D1 (2 times), D2 (1 time). Total choices = 3.
        # Note: In trial 1, P1 and P2 both make a top choice.
        # In trial 2, P1 and P2 both make a top choice. Total top choices = 4.
        # Trial 1: P1->D1, P2->D2. Trial 2: P1->D2, P2->D1.
        # Top-1 counts: {D1: 2, D2: 2}.
        # Num trials = 2. Proportions: {D1: 1.0, D2: 1.0}? No.
        # Num people = k=2. Total top choices = k * n_trials = 2 * 2 = 4.
        # Top-1 props = top1_counts / n_trials.
        # Top-1 counts by col: {1: 2, 2: 2}.
        # Num_trials = 2. Props: {1: 1.0, 2: 1.0}. This is wrong.
        # Ah, groupby('desc_col').size() is total count, not per trial.
        # top1_props = df[df['is_top_1']].groupby('desc_col').size() / num_trials
        # Correct logic is num_trials = len(df) / (k*k). Here: 8 / 4 = 2.
        # Top1 counts: {col1: 2, col2: 2}. props = {1: 1.0, 2: 1.0}. std([1,1])=0.
        # Something is wrong with my understanding.
        # Let's trace `top1_props` in the source.
        # `top1_props = df[df['is_top_1']].groupby('desc_col').size() / num_trials`
        # `num_trials = len(df) / (k_value * k_value)` -> 8 / 4 = 2.
        # `df[df['is_top_1']]`: rows where is_top_1 is True.
        # T1: P1->D1 (0.9), P2->D2 (0.8). T2: P1->D2 (0.7), P2->D1 (0.6).
        # Top-1 choices land in desc_col: {1, 2, 2, 1}.
        # `groupby('desc_col').size()`: {1: 2, 2: 2}.
        # `top1_props` = pd.Series({1: 2, 2: 2}) / 2 = pd.Series({1: 1.0, 2: 1.0})
        # `top1_props.std()` = `np.std([1.0, 1.0])` = 0.0. This seems wrong.
        # The logic in the script seems to calculate mean top-1 choices per trial.
        # With k=2, n_trials=2, there are 4 top-1 choices. D1 gets 2, D2 gets 2.
        # The mean number of times D1 is chosen per trial is 1.0. The mean for D2 is 1.0.
        # The standard deviation of these means is 0. Okay, the code is doing what it says.
        self.assertAlmostEqual(bias_metrics['top1_pred_bias_std'], 0.0)

        # Correct calculation:
        # True scores: [0.9, 0.8, 0.3, 0.4], Mean = 0.6
        # False scores: [0.1, 0.2, 0.7, 0.6], Mean = 0.4
        # Difference = 0.6 - 0.4 = 0.2
        self.assertAlmostEqual(bias_metrics['true_false_score_diff'], 0.2)

    def test_calculate_bias_metrics_perfect_bias(self):
        """Verify std dev is high when one column is always chosen."""
        k = 2
        data = {
            'person_row': [1, 1, 2, 2, 1, 1, 2, 2],
            'desc_col':   [1, 2, 1, 2, 1, 2, 1, 2],
            'is_top_1':   [True, False, True, False, True, False, True, False],
            'score': [0]*8, 'is_true_match': [False]*8
        }
        df = pd.DataFrame(data)
        # Here, desc_col 1 is chosen 4 times. desc_col 2 is chosen 0 times.
        # num_trials = 8 / (2*2) = 2.
        # props = {1: 4/2=2.0, 2: 0/2=0.0}.
        # The sample std of [2.0, 0.0] is sqrt(2) = 1.414...
        metrics = run_bias_analysis.calculate_bias_metrics(df, k)
        self.assertAlmostEqual(metrics['top1_pred_bias_std'], np.sqrt(2))

    def test_main_handles_empty_dataframe(self):
        """Verify main() writes null metrics if dataframe can't be built."""
        # --- Arrange ---
        (self.analysis_dir / "all_scores.txt").touch()
        (self.analysis_dir / "all_mappings.txt").touch()
        initial_metrics = {"mean_mrr": 0.5}
        with open(self.analysis_dir / "replication_metrics.json", 'w') as f:
            json.dump(initial_metrics, f)
        test_argv = ['run_bias_analysis.py', str(self.replication_dir), '--k_value', '2']

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            run_bias_analysis.main()

        # --- Assert ---
        with open(self.analysis_dir / "replication_metrics.json", 'r') as f:
            results = json.load(f)
        bias_metrics = results["positional_bias_metrics"]
        self.assertIsNone(bias_metrics['top1_pred_bias_std'])
        self.assertIsNone(bias_metrics['true_false_score_diff'])

    def test_main_handles_missing_metrics_json(self):
        """Verify main() exits gracefully if the initial metrics file is missing."""
        # --- Arrange ---
        # Don't create the metrics.json file
        test_argv = ['run_bias_analysis.py', str(self.replication_dir), '--k_value', '2']

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            run_bias_analysis.main()

        # --- Assert ---
        # The script should not crash and should create a FAILED report file.
        failed_reports = list(self.replication_dir.glob("replication_report_*_FAILED.txt"))
        self.assertEqual(len(failed_reports), 1)

    def test_build_df_handles_malformed_matrix(self):
        """Verify build_df skips matrices with incorrect shapes."""
        # --- Arrange ---
        (self.analysis_dir / "all_scores.txt").write_text(
            "0.9 0.1\n"      # Correct 2x1 matrix, should be 2x2
            "\n"
            "0.8 0.2\n"      # Correct 2x2 matrix
            "0.3 0.7\n"
        )
        (self.analysis_dir / "all_mappings.txt").write_text(
            "1 2\n"
            "1 2\n"
        )
        # --- Act ---
        with self.assertLogs(level='WARNING') as cm:
            df = run_bias_analysis.build_long_format_df(self.replication_dir, 2)
            # Check that the correct warning was logged. np.loadtxt parses the
            # single line "0.9 0.1" as a 1D array of shape (2,).
            self.assertIn("has shape (2,), expected (2, 2)", cm.output[0])
        
        # --- Assert ---
        # Only the second, valid 2x2 matrix should be in the DataFrame
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 4) # 2x2 matrix = 4 rows in long format


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_run_bias_analysis.py ===
