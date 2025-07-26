#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# Personality Matching Experiment Framework
# Copyright (C) 2025 [Your Name/Institution]
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
# Filename: tests/test_study_analyzer.py

import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import shutil
import tempfile
import pandas as pd
import logging
import configparser
import io
import numpy as np

import src.study_analyzer as run_anova_module

class TestStudyAnalyzerScript(unittest.TestCase):
    """Tests for the main orchestration and helper functions of study_analyzer.py."""

    def setUp(self):
        """Set up a temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp()
        self.master_csv_path = os.path.join(self.test_dir, 'STUDY_results.csv')
        self.anova_output_dir = os.path.join(self.test_dir, 'anova')
        os.makedirs(self.anova_output_dir, exist_ok=True)

        self.base_df = pd.DataFrame({
            'model': ['model_a', 'model_b', 'model_a', 'model_b'],
            'n_valid_responses': [30, 35, 28, 32],
            'mapping_strategy': ['correct', 'correct', 'random', 'random'],
            'mean_top_1_acc': [0.85, 0.90, 0.60, 0.65],
            'mean_mrr': [0.75, 0.80, 0.50, 0.55]
        })
        self.base_df.to_csv(self.master_csv_path, index=False)

        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'Schema': {'factors': "model,mapping_strategy", 'metrics': "mean_top_1_acc,mean_mrr"},
            'Analysis': {'min_valid_response_threshold': "10"},
            'ModelDisplayNames': {'model_a': 'Model A', 'model_b': 'Model B', 'model_c': 'Model C', 'a': 'Model A', 'b': 'Model B', 'c': 'Model C'},
            'FactorDisplayNames': {'model': 'Model Name', 'mapping_strategy': 'Mapping Strategy'},
            'MetricDisplayNames': {'mean_top_1_acc': 'Top-1 Accuracy', 'mean_mrr': 'Mean Reciprocal Rank'},
            'ModelNormalization': {'model_a': 'model_a', 'model_b': 'model_b', 'model_c': 'model_c', 'a':'a', 'b':'b', 'c':'c'}
        })
        
        # This setup will patch the functions for ALL tests in the class.
        self.patch_get_config_list = patch('src.study_analyzer.get_config_list')
        self.mock_get_config_list = self.patch_get_config_list.start()
        self.mock_get_config_list.side_effect = lambda _, section, option: self.mock_config.get(section, option).split(',')

        self.patch_get_config_section_as_dict = patch('src.study_analyzer.get_config_section_as_dict')
        self.mock_get_config_section_as_dict = self.patch_get_config_section_as_dict.start()
        self.mock_get_config_section_as_dict.side_effect = lambda _, section: dict(self.mock_config.items(section))

        self.patch_app_config = patch('src.study_analyzer.APP_CONFIG', new=MagicMock())
        self.mock_app_config = self.patch_app_config.start()
        self.mock_app_config.getint.side_effect = self.mock_config.getint
        self.mock_app_config.get.side_effect = self.mock_config.get

    def tearDown(self):
        """Clean up the temporary directory."""
        self.patch_get_config_list.stop()
        self.patch_get_config_section_as_dict.stop()
        self.patch_app_config.stop()
        logging.shutdown()
        try:
            shutil.rmtree(self.test_dir)
        except OSError:
            pass # Ignore errors if dir is already gone

    def _run_main_and_capture_output(self, args):
        """Helper to run main and capture all stdout/stderr."""
        # Ensure logging is completely reset for this run, removing all existing handlers
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
        logging.root.setLevel(logging.NOTSET) # Reset level to capture all messages

        with patch('sys.stdout', new_callable=io.StringIO) as mock_stdout, \
             patch('sys.stderr', new_callable=io.StringIO) as mock_stderr, \
             patch('src.study_analyzer.plt'), \
             patch('src.study_analyzer.sns'), \
             patch('src.study_analyzer.nx'), \
             patch('src.study_analyzer.sm'): # Patching sm here for consistency in main() tests

            # Intercept StreamHandler initialization to redirect output to our mocks
            def mock_stream_handler_init(self_obj, stream=None, *args, **kwargs):
                if stream is sys.stdout:
                    stream = mock_stdout
                elif stream is sys.stderr:
                    stream = mock_stderr
                # Call the original __init__ with the redirected stream
                original_stream_handler_init(self_obj, stream, *args, **kwargs)

            original_stream_handler_init = logging.StreamHandler.__init__
            with patch('logging.StreamHandler.__init__', autospec=True, side_effect=mock_stream_handler_init):
                with patch.object(sys, 'argv', ['study_analyzer.py'] + args):
                    exit_code = 0
                    try:
                        run_anova_module.main()
                    except SystemExit as e:
                        exit_code = e.code
                    return mock_stdout.getvalue(), mock_stderr.getvalue(), exit_code

    def test_find_master_csv(self):
        self.assertEqual(run_anova_module.find_master_csv(self.test_dir), self.master_csv_path)
        os.remove(self.master_csv_path)
        path_final = os.path.join(self.test_dir, 'final_summary_results.csv')
        open(path_final, 'a').close()
        self.assertEqual(run_anova_module.find_master_csv(self.test_dir), path_final)
        os.remove(path_final)
        with self.assertLogs('root', level='ERROR'):
            self.assertIsNone(run_anova_module.find_master_csv(self.test_dir))

    def test_main_happy_path(self):
        with patch('src.study_analysis.perform_analysis') as mock_perform_analysis:
            stdout, stderr, exit_code = self._run_main_and_capture_output([self.test_dir])
            self.assertEqual(exit_code, 0)
            self.assertIn("Successfully loaded", stdout)
            self.assertIn("Model name normalization and sanitization complete", stdout)
            self.assertEqual(mock_perform_analysis.call_count, 2)

    def test_main_no_csv_found_exit(self):
        os.remove(self.master_csv_path)
        stdout, stderr, exit_code = self._run_main_and_capture_output([self.test_dir])
        self.assertEqual(exit_code, 1)
        self.assertIn("ERROR: No summary CSV file found", stdout + stderr)

    def test_main_archive_failure(self):
        """Test main gracefully handles failure during archiving of previous results."""
        dummy_file = os.path.join(self.anova_output_dir, "old_plot.png")
        open(dummy_file, 'a').close()

        with patch('shutil.move', side_effect=IOError("Permission denied")):
            stdout, stderr, exit_code = self._run_main_and_capture_output([self.test_dir])
        
        captured_output = stdout + stderr
        self.assertEqual(exit_code, 0)
        self.assertIn("Could not archive previous results. Reason: Permission denied", captured_output)
        self.assertIn("Successfully loaded", captured_output)

    def test_perform_analysis_zero_variance(self):
        df = pd.DataFrame({'model': ['a', 'b'], 'metric': [1, 1]})
        with self.assertLogs('root', level='WARNING') as cm:
            run_anova_module.perform_analysis(df, 'metric', ['model'], self.test_dir, {}, {'metric':'Metric'}, {})
            self.assertTrue(any("has zero variance. Skipping all analysis" in log for log in cm.output))

    def test_main_missing_metric_column(self):
        self.mock_config.set('Schema', 'metrics', 'mean_top_1_acc,missing_metric')
        stdout, stderr, exit_code = self._run_main_and_capture_output([self.test_dir])
        self.assertEqual(exit_code, 0)
        self.assertIn("Warning: Metric column 'missing_metric' not found. Skipping analysis.", stdout)

    def test_create_diagnostic_plot_no_residuals(self):
        mock_model = MagicMock()
        mock_model.resid = pd.Series([], dtype=float)
        with patch('src.study_analyzer.plt') as mock_plt, \
             self.assertLogs('root', level='WARNING') as cm:
            run_anova_module.create_diagnostic_plot(mock_model, 'Test', self.test_dir, 'key')
            self.assertIn("Could not generate Q-Q plot for 'Test': No residuals found.", cm.output[0])
            mock_plt.savefig.assert_not_called()

    def test_perform_analysis_single_factor_no_variation(self):
        df = pd.DataFrame({'model': ['a']*4, 'metric':[1,2,3,4]})
        with patch('src.study_analyzer.create_and_save_plot') as mock_plot, \
             self.assertLogs('root', level='INFO') as cm:
            run_anova_module.perform_analysis(df, 'metric', ['model'], self.test_dir, {}, {}, {})
            self.assertTrue(any("Only one experimental group found. No analysis possible." in log for log in cm.output))
            mock_plot.assert_called_once()

    def test_perform_analysis_games_howell_fallback(self):
        df = pd.DataFrame({
            'model': ['a']*3 + ['b']*3 + ['c']*3,  # 3 levels to trigger Tukey HSD
            'mean_top_1_acc': list(range(9)),
            'n_valid_responses': [30]*9,
            'mapping_strategy': ['const_strat']*9 # Ensure mapping_strategy is present but constant
        })
        
        with patch('src.study_analyzer.sm') as mock_sm, \
             patch('src.study_analyzer.pg') as mock_pg, \
             patch('statsmodels.stats.multicomp.pairwise_tukeyhsd', side_effect=ValueError("Tukey failed intentionally")), \
             patch('src.study_analyzer.generate_performance_tiers') as mock_generate_tiers, \
             patch('logging.warning') as mock_log_warning, \
             patch('logging.info') as mock_log_info, \
             patch('src.study_analyzer.create_diagnostic_plot'), \
             patch('src.study_analyzer.create_and_save_plot'): # Patch plotting functions to prevent FileNotFoundError

            mock_model = MagicMock()
            mock_model.resid = pd.Series(range(9), dtype=float)  # Match DataFrame size
            mock_sm.ols.return_value.fit.return_value = mock_model
            # ANOVA table should only contain 'C(model)' and 'Residual' because 'mapping_strategy' has no variance in df
            mock_sm.stats.anova_lm.return_value = pd.DataFrame({
                'sum_sq': [1.0, 0.5],
                'PR(>F)': [0.01, 0.1]
            }, index=['C(model)', 'Residual']) # Only model and residual as factors based on df variance

            run_anova_module.perform_analysis(df, 'mean_top_1_acc', ['model', 'mapping_strategy'], # Pass all possible factors
                                              self.test_dir, {'a':'A', 'b':'B', 'c':'C'}, {'mean_top_1_acc':'Top-1 Acc'}, {'model':'Model', 'mapping_strategy': 'Mapping Strategy'})

    def test_perform_analysis_exception_handling(self):
        with patch('src.study_analyzer.ols', side_effect=Exception("OLS error")), \
             self.assertLogs('root', level='ERROR') as cm:
            run_anova_module.perform_analysis(self.base_df, 'mean_top_1_acc', ['model'], self.test_dir, {}, {}, {})
            self.assertIn("ERROR: Could not perform analysis for metric 'mean_top_1_acc'. Reason: OLS error", cm.output[0])

    def test_main_data_cleaning_db_column(self):
        df_with_old_db = pd.DataFrame({
            'model': ['a', 'b'], 'n_valid_responses': [30, 30],
            'mapping_strategy': ['c', 'c'], 'mean_top_1_acc': [0.9, 0.8], 'mean_mrr': [0.8, 0.7],
            'db': ['personalities_db_1-5000.jsonl', 'personalities_db_1-5000.txt']
        })
        df_with_old_db.to_csv(self.master_csv_path, index=False)
        stdout, _, _ = self._run_main_and_capture_output([self.test_dir])
        self.assertIn("Performed data cleaning on 'db' column", stdout)
        self.assertIn("-> Original unique values: ['personalities_db_1-5000.jsonl' 'personalities_db_1-5000.txt']", stdout)
        self.assertIn("-> Cleaned unique values:  ['personalities_db_1-5000.txt']", stdout)

    def test_main_min_valid_response_threshold_filter(self):
        df_mixed = pd.DataFrame({
            'model': ['a']*2 + ['b']*2 + ['c']*2,
            'n_valid_responses': [20, 22, 30, 32, 5, 8],
            'mapping_strategy': ['c']*6, 'mean_top_1_acc': [0.1, 0.2, 0.3, 0.4, 0.5, 0.6], 'mean_mrr': [1]*6
        })
        df_mixed.to_csv(self.master_csv_path, index=False)
        self.mock_config.set('Analysis', 'min_valid_response_threshold', '25')
        stdout, _, _ = self._run_main_and_capture_output([self.test_dir])
        self.assertIn("Excluding 2 model(s) due to low valid response rates: a, c", stdout)
        self.assertIn("Analysis will proceed with 2 rows from 1 models", stdout)

    def test_perform_analysis_tukey_success_and_tiers(self):
        df = pd.DataFrame({'model': ['a']*3 + ['b']*3 + ['c']*3, 'mean_top_1_acc': range(9)})
        with patch('src.study_analyzer.sm') as mock_sm, \
             patch('statsmodels.stats.multicomp.pairwise_tukeyhsd') as mock_tukey, \
             patch('src.study_analyzer.generate_performance_tiers') as mock_tiers, \
             patch('src.study_analyzer.create_diagnostic_plot'), \
             patch('src.study_analyzer.create_and_save_plot'), \
             self.assertLogs('root', level='INFO') as cm:
            mock_sm.ols().fit().resid = pd.Series(range(9))
            mock_sm.stats.anova_lm.return_value = pd.DataFrame({
                'sum_sq': [1.0, 0.5], 
                'PR(>F)': [0.01, float('nan')]
            }, index=['C(model)', 'Residual'])
            mock_tukey.return_value._results_table.data = [[]]
            run_anova_module.perform_analysis(df, 'mean_top_1_acc', ['model'], self.test_dir, {}, {}, {})
            log_output = " ".join(cm.output)
            self.assertIn("Attempting Tukey HSD", log_output)
            self.assertIn("Conclusion: Significant effect found for factor(s): model", log_output)
            mock_tiers.assert_called_once()

    def test_perform_analysis_no_significant_factors(self):
        df = self.base_df.copy()
        df['n_valid_responses'] = [30]*len(df)

        # Create necessary subdirectories that perform_analysis expects
        os.makedirs(os.path.join(self.test_dir, 'diagnostics'), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, 'boxplots', 'model'), exist_ok=True)

        with patch('src.study_analyzer.sm') as mock_sm, \
             patch('src.study_analyzer.generate_performance_tiers') as mock_tiers, \
             patch('src.study_analyzer.logging.info') as mock_log_info, \
             patch('src.study_analyzer.create_diagnostic_plot'), \
             patch('src.study_analyzer.create_and_save_plot'): # Patch plotting functions

            mock_model = MagicMock()
            mock_model.resid = pd.Series(np.random.rand(len(df)) - 0.5, dtype=float)
            mock_sm.ols.return_value.fit.return_value = mock_model
            mock_sm.stats.anova_lm.return_value = pd.DataFrame({
                'sum_sq': [1.0, 0.5], 
                'PR(>F)': [0.1, float('nan')]
            }, index=['C(model)', 'Residual'])
            
            run_anova_module.perform_analysis(df, 'mean_top_1_acc', ['model'], self.test_dir, {}, {'mean_top_1_acc': 'Top-1 Accuracy'}, {'model': 'Model'})
            
            mock_log_info.assert_any_call("\nConclusion: No factors had a statistically significant effect on this metric.")
            mock_tiers.assert_not_called()

    def test_perform_analysis_two_level_significant_factor(self):
        with patch('src.study_analyzer.sm') as mock_sm, \
             patch('statsmodels.stats.multicomp.pairwise_tukeyhsd') as mock_tukey, \
             patch('src.study_analyzer.create_diagnostic_plot'), \
             patch('src.study_analyzer.create_and_save_plot'), \
             self.assertLogs('root', level='INFO') as cm:
            mock_sm.ols().fit().resid = self.base_df['mean_top_1_acc']
            mock_sm.stats.anova_lm.return_value = pd.DataFrame({
                'sum_sq': [1.0, 0.5], 
                'PR(>F)': [0.01, float('nan')]
            }, index=['C(model)', 'Residual'])
            run_anova_module.perform_analysis(self.base_df, 'mean_top_1_acc', ['model'], self.test_dir, {}, {}, {})
            self.assertTrue(any("Factor 'model' has only two levels and is significant" in log for log in cm.output))
            mock_tukey.assert_not_called()

    def test_generate_performance_tiers_no_cliques(self):
        with patch('src.study_analyzer.nx') as mock_nx, self.assertLogs('root', level='INFO') as cm:
            mock_nx.find_cliques.return_value = []
            run_anova_module.generate_performance_tiers(pd.DataFrame(), '', pd.DataFrame(), {})
            self.assertTrue(any("No distinct performance groups found" in log for log in cm.output))

    def test_generate_performance_tiers_empty_cliques(self):
        with patch('src.study_analyzer.nx') as mock_nx, self.assertLogs('root', level='INFO') as cm:
            mock_nx.find_cliques.return_value = [[]]
            run_anova_module.generate_performance_tiers(pd.DataFrame(), '', pd.DataFrame({'group1':[],'group2':[],'reject':[]}), {})
            self.assertTrue(any("No distinct performance groups found" in log for log in cm.output))

    def test_main_argparse_help(self):
        """Test argparse help message for completeness."""
        stdout, stderr, exit_code = self._run_main_and_capture_output(['-h'])
        self.assertEqual(exit_code, 0)
        help_output = stdout + stderr
        self.assertIn("Example Usage:", help_output)
        self.assertIn("python src/study_analyzer.py path/to/your/study_folder/", help_output)

# === End of tests/test_study_analyzer.py ===
