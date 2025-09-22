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
# Filename: tests/experiment_lifecycle/test_analyze_study_results.py

"""
Unit Tests for the Final Study Results Analyzer.

This script validates the data handling, control flow, and output generation of
analyze_study_results.py in an isolated environment with mocked dependencies.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import tempfile
from pathlib import Path
import pandas as pd
import configparser
import types
import importlib
import io
import logging
import numpy as np

# Import the module to test
from src import analyze_study_results


class TestHelperFunctions(unittest.TestCase):
    """Tests for helper functions in analyze_study_results."""

    def test_interpret_bf_covers_all_cases(self):
        """Verify Bayes Factor interpretations are correct."""
        test_cases = {
            150: "Extreme evidence for H1", 50: "Very Strong evidence for H1",
            20: "Strong evidence for H1", 5: "Moderate evidence for H1",
            2: "Anecdotal evidence for H1", 1: "No evidence",
            0.5: "Anecdotal evidence for H0", 0.2: "Moderate evidence for H0",
            0.05: "Strong evidence for H0", 0.01: "Very Strong evidence for H0",
            0.005: "Extreme evidence for H0",
        }
        for bf, expected in test_cases.items():
            with self.subTest(bf=bf):
                self.assertEqual(analyze_study_results.interpret_bf(bf), expected)

    def test_find_master_csv_fallback_logic(self):
        """Verify find_master_csv finds files in the correct fallback order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "STUDY_results.csv").touch()
            (tmp_path / "final_summary_results.csv").touch()
            (tmp_path / "EXPERIMENT_results.csv").touch()

            self.assertIn("STUDY_results.csv", analyze_study_results.find_master_csv(tmpdir))
            (tmp_path / "STUDY_results.csv").unlink()

            self.assertIn("final_summary_results.csv", analyze_study_results.find_master_csv(tmpdir))
            (tmp_path / "final_summary_results.csv").unlink()

            self.assertIn("EXPERIMENT_results.csv", analyze_study_results.find_master_csv(tmpdir))

    def test_color_stripping_formatter(self):
        """Verify the formatter removes ANSI color codes."""
        formatter = analyze_study_results.ColorStrippingFormatter()
        record = logging.LogRecord('test', logging.INFO, '', 0, '\x1b[32mHello\x1b[0m', None, None)
        self.assertEqual(formatter.format(record), 'Hello')

    def test_color_formatter(self):
        """Verify the formatter adds ANSI color codes."""
        formatter = analyze_study_results.ColorFormatter()
        record_sig = logging.LogRecord('test', logging.INFO, '', 0, 'Conclusion: Significant effect found', None, None)
        record_warn = logging.LogRecord('test', logging.WARNING, '', 0, 'A warning', None, None)
        record_err = logging.LogRecord('test', logging.ERROR, '', 0, 'An error', None, None)
        
        self.assertIn(formatter.GREEN, formatter.format(record_sig))
        self.assertIn(formatter.YELLOW, formatter.format(record_warn))
        self.assertIn(formatter.RED, formatter.format(record_err))


class TestAnalyzeStudyResults(unittest.TestCase):
    """Test suite for analyze_study_results.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="analyze_study_test_")
        self.study_dir = Path(self.test_dir.name)
        self.anova_dir = self.study_dir / "anova"

        # 1. Set up the mock config and reload the module FIRST.
        # This ensures all subsequent patches are applied to the reloaded module.
        self._setup_mock_config()

        # 2. Now, patch the reloaded module's dependencies.
        self.sys_exit_patcher = patch('src.analyze_study_results.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

        self.plt_patcher = patch('src.analyze_study_results.plt')
        self.mock_plt = self.plt_patcher.start()

        self.shutil_patcher = patch('src.analyze_study_results.shutil')
        self.mock_shutil = self.shutil_patcher.start()

        self._setup_statistical_mocks()
        self._setup_additional_mocks()

        # 3. Set up logging capture.
        self.log_stream = io.StringIO()
        self.mock_file_handler = logging.StreamHandler(self.log_stream)
        
        self.file_handler_patcher = patch('logging.FileHandler', return_value=self.mock_file_handler)
        self.file_handler_patcher.start()
        
        self.stream_handler_patcher = patch('logging.StreamHandler', return_value=self.mock_file_handler)
        self.stream_handler_patcher.start()
        
        self.basicConfig_patcher = patch('logging.basicConfig')
        self.mock_basicConfig = self.basicConfig_patcher.start()

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        root_logger.addHandler(self.mock_file_handler)
        root_logger.setLevel(logging.INFO)

    def _setup_statistical_mocks(self):
        """Set up mocks for statistical analysis functions."""
        mock_model = MagicMock()
        mock_model.resid = pd.Series([0.1, -0.2, 0.15, -0.1, 0.05, -0.08, 0.12, -0.03])
        
        self.ols_patcher = patch('src.analyze_study_results.ols')
        self.mock_ols = self.ols_patcher.start()
        self.mock_ols.return_value.fit.return_value = mock_model
        
        mock_anova_table = pd.DataFrame({
            'sum_sq': [0.5, 0.3, 0.2, 0.1], 'df': [1, 1, 1, 4],
            'F': [20.0, 12.0, 8.0, np.nan], 'PR(>F)': [0.001, 0.02, 0.04, np.nan]
        }, index=['C(model)', 'C(mapping_strategy)', 'C(model):C(mapping_strategy)', 'Residual'])
        
        self.anova_patcher = patch('src.analyze_study_results.sm.stats.anova_lm')
        self.mock_anova = self.anova_patcher.start()
        self.mock_anova.return_value = mock_anova_table
        
        mock_tukey = MagicMock()
        mock_tukey._results_table.data = [
            ['group1', 'group2', 'meandiff', 'p-adj', 'lower', 'upper', 'reject'],
            ['google_gemini_flash_1_5', 'anthropic_claude_3', 0.1, 0.05, 0.01, 0.19, True]
        ]
        mock_tukey.__str__ = lambda self: "Mock Tukey Results"
        
        self.tukey_patcher = patch('src.analyze_study_results.pairwise_tukeyhsd')
        self.mock_tukey = self.tukey_patcher.start()
        self.mock_tukey.return_value = mock_tukey
        
        self.sns_patcher = patch('src.analyze_study_results.sns')
        self.mock_sns = self.sns_patcher.start()
        
        self.qqplot_patcher = patch('src.analyze_study_results.sm.qqplot')
        self.mock_qqplot = self.qqplot_patcher.start()

    def _setup_additional_mocks(self):
        """Set up additional mocks for dependencies."""
        self.nx_patcher = patch('src.analyze_study_results.nx')
        self.mock_nx = self.nx_patcher.start()
        self.mock_nx.find_cliques.return_value = [['Gemini Flash 1.5'], ['Claude 3']]
        
        self.pg_patcher = patch('src.analyze_study_results.pg')
        self.mock_pg = self.pg_patcher.start()
        mock_bf_result = pd.DataFrame({'BF10': [3.5]})
        self.mock_pg.ttest.return_value = mock_bf_result
        self.mock_pg.pairwise_gameshowell = MagicMock()
        
        self.anova_dir.mkdir(exist_ok=True)
        (self.anova_dir / "diagnostics").mkdir(exist_ok=True)
        
        # Create boxplot subdirectories to prevent FileNotFoundError during tests
        boxplot_base_dir = self.anova_dir / 'boxplots'
        boxplot_base_dir.mkdir(exist_ok=True)
        for factor in ['model', 'mapping_strategy']: # From mock config
            (boxplot_base_dir / factor).mkdir(exist_ok=True)

        # NOTE: We do NOT mock os.makedirs because the script needs to create
        # subdirectories for plots and archives within the temporary test directory.
        # Mocking it causes a RecursionError.
        self.makedirs_patcher = None
        
        self.listdir_patcher = patch('src.analyze_study_results.os.listdir')
        self.mock_listdir = self.listdir_patcher.start()
        self.mock_listdir.return_value = []
        
        mock_fig = MagicMock()
        self.mock_plt.figure.return_value = mock_fig
        self.mock_plt.gca.return_value = MagicMock()
        self.mock_plt.tight_layout = MagicMock()
        self.mock_plt.close = MagicMock()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.sys_exit_patcher.stop()
        self.plt_patcher.stop()
        self.shutil_patcher.stop()
        self.ols_patcher.stop()
        self.anova_patcher.stop()
        self.tukey_patcher.stop()
        self.sns_patcher.stop()
        self.qqplot_patcher.stop()
        self.nx_patcher.stop()
        self.pg_patcher.stop()
        if self.makedirs_patcher:
            self.makedirs_patcher.stop()
        self.listdir_patcher.stop()
        self.config_patcher.stop()
        self.file_handler_patcher.stop()
        self.stream_handler_patcher.stop()
        self.basicConfig_patcher.stop()
        self.log_stream.close()

        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

    def _setup_mock_config(self):
        """Creates a mock config and applies it to the module."""
        mock_app_config = configparser.ConfigParser()
        mock_app_config.read_dict({
            'Analysis': {'min_valid_response_threshold': '25'},
            'ModelNormalization': {
                'google/gemini-flash-1.5': 'google/gemini-flash-1.5',
                'anthropic/claude-3': 'anthropic/claude-3'
            },
            'ModelDisplayNames': {
                'google/gemini-flash-1.5': 'Gemini Flash 1.5',
                'anthropic/claude-3': 'Claude 3'
            },
            'MetricDisplayNames': {'mean_mrr': 'Mean Reciprocal Rank (MRR)'},
            'FactorDisplayNames': {'model': 'Model', 'mapping_strategy': 'Mapping Strategy'},
            'Schema': {
                'factors': 'model, mapping_strategy',
                'metrics': 'mean_mrr, n_valid_responses'
            }
        })
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.APP_CONFIG = mock_app_config
        fake_mod.get_config_list = lambda cfg, sec, key: [v.strip() for v in cfg.get(sec, key).split(',')]
        fake_mod.get_config_section_as_dict = lambda cfg, sec: dict(cfg.items(sec))

        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(analyze_study_results)

    def _create_mock_csv(self, data, filename="STUDY_results.csv"):
        """Helper to create a mock CSV file."""
        df = pd.DataFrame(data)
        csv_path = str(self.study_dir / filename)
        df.to_csv(csv_path, index=False)

    def test_main_happy_path_runs_analysis(self):
        """Verify the script runs end-to-end with valid data."""
        mock_data = {
            'model': ['google/gemini-flash-1.5'] * 4 + ['anthropic/claude-3'] * 4,
            'mapping_strategy': ['correct', 'correct', 'random', 'random'] * 2,
            'mean_mrr': [0.8, 0.82, 0.1, 0.12, 0.85, 0.87, 0.15, 0.17],
            'n_valid_responses': [30, 31, 29, 30, 30, 31, 29, 30]
        }
        self._create_mock_csv(mock_data)
        test_argv = ['analyze_study_results.py', str(self.study_dir)]

        with patch.object(sys, 'argv', test_argv):
            analyze_study_results.main()

        log_content = self.log_stream.getvalue()
        self.assertIn("ANALYSIS FOR METRIC", log_content)
        self.assertIn("Descriptive Statistics", log_content)
        self.assertIn("ANOVA Summary", log_content)
        self.assertIn("Post-Hoc Analysis", log_content)
        self.assertIn("Generating Interaction Plot", log_content)
        self.assertEqual(self.mock_plt.savefig.call_count, 8)

    def test_main_handles_missing_csv(self):
        """Verify the script exits with an error if summary CSV is missing."""
        test_argv = ['analyze_study_results.py', str(self.study_dir)]
        with patch.object(sys, 'argv', test_argv):
            analyze_study_results.main()
        self.assertIn("ERROR: No summary CSV file found", self.log_stream.getvalue())

    def test_main_handles_filtering_all_data(self):
        """Verify the script handles the case where all models are filtered out."""
        mock_data = {
            'model': ['google/gemini-flash-1.5'], 'mapping_strategy': ['correct'],
            'mean_mrr': [0.8], 'n_valid_responses': [10]
        }
        self._create_mock_csv(mock_data)
        test_argv = ['analyze_study_results.py', str(self.study_dir)]
        with patch.object(sys, 'argv', test_argv):
            analyze_study_results.main()
        log_content = self.log_stream.getvalue()
        self.assertIn("Excluding 1 model(s)", log_content)
        self.assertIn("WARNING: All models were filtered out.", log_content)

    def test_main_handles_no_variance_in_metric(self):
        """Verify the script skips analysis for metrics with zero variance."""
        # Data must have >1 row to avoid the 'single group' check, but the metric
        # must have identical values to trigger the 'zero variance' check.
        mock_data = {
            'model': ['google/gemini-flash-1.5', 'anthropic/claude-3'],
            'mapping_strategy': ['correct', 'random'],
            'mean_mrr': [0.5, 0.5], # Zero variance
            'n_valid_responses': [30, 30]
        }
        self._create_mock_csv(mock_data)
        test_argv = ['analyze_study_results.py', str(self.study_dir)]
        with patch.object(sys, 'argv', test_argv):
            analyze_study_results.main()
        self.assertIn("zero variance. Skipping all analysis.", self.log_stream.getvalue())

    def test_perform_analysis_tukey_fallback_to_games_howell(self):
        """Verify the analysis falls back to Games-Howell if Tukey HSD fails."""
        self.mock_tukey.side_effect = ValueError("Tukey failed")
        self.mock_pg.pairwise_gameshowell.return_value = pd.DataFrame()
        mock_data = {
            'model': ['m1', 'm2', 'm3'], # Must have > 2 levels for post-hoc
            'mapping_strategy': ['correct', 'random', 'correct'],
            'mean_mrr': [0.8, 0.1, 0.5], 'n_valid_responses': [30, 30, 30]
        }
        self._create_mock_csv(mock_data)
        with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
            analyze_study_results.main()
        log_content = self.log_stream.getvalue()
        self.assertIn("Tukey HSD failed", log_content)
        self.assertIn("Falling back to Games-Howell test", log_content)

    def test_perform_analysis_handles_no_active_factors(self):
        """Verify analysis handles data with no variation in factors."""
        mock_data = {
            'model': ['google/gemini-flash-1.5'] * 2, 'mapping_strategy': ['correct'] * 2,
            'mean_mrr': [0.8, 0.82], 'n_valid_responses': [30, 30]
        }
        self._create_mock_csv(mock_data)
        with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
            analyze_study_results.main()
        self.assertIn("Only one experimental group found.", self.log_stream.getvalue())
        self.assertTrue(self.mock_plt.savefig.called)

    def test_main_exits_gracefully_on_config_error(self):
        """Verify graceful exit if config sections are missing."""
        with patch('src.analyze_study_results.get_config_list', return_value=None):
            self._create_mock_csv({'model': ['test']})
            with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
                analyze_study_results.main()
            self.assertIn("FATAL: Could not load required sections", self.log_stream.getvalue())

    def test_main_archives_old_results(self):
        """Verify that previous analysis results are archived."""
        self.mock_listdir.return_value = ['old_file.txt']
        (self.anova_dir / 'old_file.txt').touch()
        # Mock CSV must contain all factor columns to avoid KeyError
        self._create_mock_csv({
            'model': ['test'], 'mapping_strategy': ['c'],
            'mean_mrr': [1], 'n_valid_responses': [30]
        })
        with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
            analyze_study_results.main()
        self.mock_shutil.move.assert_called_once()
        self.assertIn("Archiving 1 file(s)", self.log_stream.getvalue())

    def test_create_diagnostic_plot_handles_no_residuals(self):
        """Verify Q-Q plot generation fails gracefully if residuals are missing."""
        with patch('src.analyze_study_results.ols') as mock_ols_no_resid:
            mock_model_no_resid = MagicMock()
            mock_model_no_resid.resid = pd.Series([], dtype=float)
            mock_ols_no_resid.return_value.fit.return_value = mock_model_no_resid
            # Mock CSV must contain all factor columns to avoid KeyError
            self._create_mock_csv({
                'model': ['a', 'b'], 'mapping_strategy': ['c', 'd'],
                'mean_mrr': [1, 2], 'n_valid_responses': [30, 30]
            })
            with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
                analyze_study_results.main()
            self.assertIn("No residuals found", self.log_stream.getvalue())

    def test_bayesian_analysis_enhanced_error_handling(self):
        """Verify enhanced error handling in Bayesian analysis."""
        # Test data structure error (missing BF10 column)
        mock_bad_result = pd.DataFrame({'t-stat': [2.5], 'p-val': [0.02]})  # Missing BF10
        self.mock_pg.ttest.return_value = mock_bad_result
        
        mock_data = {
            'model': ['google/gemini-flash-1.5'] * 2 + ['anthropic/claude-3'] * 2,
            'mapping_strategy': ['correct', 'random'] * 2,
            'mean_mrr': [0.8, 0.1, 0.85, 0.15],
            'n_valid_responses': [30, 30, 30, 30]
        }
        self._create_mock_csv(mock_data)
        
        with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
            analyze_study_results.main()
        
        log_content = self.log_stream.getvalue()
        self.assertIn("Bayesian analysis failed due to statistical issues", log_content)

    def test_games_howell_fallback_enhanced_error_handling(self):
        """Verify enhanced error handling in Games-Howell fallback."""
        # Make Tukey fail, then make Games-Howell also fail
        self.mock_tukey.side_effect = ValueError("Tukey statistical error")
        self.mock_pg.pairwise_gameshowell.side_effect = Exception("Games-Howell failed")
        
        mock_data = {
            'model': ['m1', 'm2', 'm3'],  # Must have > 2 levels for post-hoc
            'mapping_strategy': ['correct', 'random', 'correct'],
            'mean_mrr': [0.8, 0.1, 0.5], 'n_valid_responses': [30, 30, 30]
        }
        self._create_mock_csv(mock_data)
        
        with patch.object(sys, 'argv', ['py', str(self.study_dir)]):
            analyze_study_results.main()
        
        log_content = self.log_stream.getvalue()
        self.assertIn("Tukey HSD failed due to statistical issues", log_content)
        self.assertIn("Games-Howell test also failed", log_content)
        self.assertIn("Skipping post-hoc analysis for factor", log_content)


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_analyze_study_results.py ===
