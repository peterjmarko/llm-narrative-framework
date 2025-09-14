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
# Filename: tests/experiment_lifecycle/test_analyze_llm_performance.py

"""
Unit Tests for the Core Performance Analyzer (analyze_llm_performance.py).

This script validates the statistical calculations and file I/O logic of the
performance analyzer in an isolated environment.
"""

import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import configparser
import types
import json
from pathlib import Path
import numpy as np
import importlib
import pytest

# Import the module to test
from src import analyze_llm_performance

class TestAnalyzeLLMPerformance(unittest.TestCase):
    """Test suite for analyze_llm_performance.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        self.test_dir = tempfile.TemporaryDirectory(prefix="analyze_perf_test_")
        self.project_root = self.test_dir.name
        
        self.run_dir = Path(self.project_root) / "run_output"
        self.analysis_dir = self.run_dir / "analysis_inputs"
        self.queries_dir = self.run_dir / "session_queries"
        self.analysis_dir.mkdir(parents=True)
        self.queries_dir.mkdir(parents=True)

        # Mock config_loader
        self.mock_config = configparser.ConfigParser()
        self.mock_config.read_dict({
            'General': {'analysis_inputs_subdir': 'analysis_inputs'},
            'Filenames': {
                'all_scores_file': 'all_scores.txt',
                'all_mappings_file': 'all_mappings.txt',
                'successful_indices_log': 'successful_indices.txt',
                'replication_metrics_json': 'replication_metrics.json'
            }
        })
        
        fake_mod = types.ModuleType("config_loader")
        fake_mod.PROJECT_ROOT = self.project_root
        fake_mod.APP_CONFIG = self.mock_config
        def dummy_get_config_value(config, section, key, fallback=None, **kwargs):
            return config.get(section, key, fallback=fallback)
        fake_mod.get_config_value = dummy_get_config_value
        
        self.config_patcher = patch.dict('sys.modules', {'config_loader': fake_mod})
        self.config_patcher.start()
        importlib.reload(analyze_llm_performance)
        
        self.sys_exit_patcher = patch('src.analyze_llm_performance.sys.exit')
        self.mock_sys_exit = self.sys_exit_patcher.start()

    def tearDown(self):
        """Clean up resources."""
        self.test_dir.cleanup()
        self.config_patcher.stop()
        self.sys_exit_patcher.stop()

    # --- Group 1: Main Orchestrator Tests ---

    def _create_test_input_files(self):
        """Helper to create a standard set of input files for a happy path test."""
        # Trial 1: Perfect match
        (self.analysis_dir / "all_scores.txt").write_text(
            "0.9\t0.1\n"
            "0.2\t0.8\n"
            "\n"
            "0.3\t0.7\n"
            "0.6\t0.4\n"
        )
        (self.analysis_dir / "all_mappings.txt").write_text(
            "Map_idx1\tMap_idx2\n"
            "1\t2\n" # Trial 1 mapping
            "1\t2\n" # Trial 2 mapping
        )
        (self.analysis_dir / "successful_indices.txt").write_text("1\n2\n")
        
        # Manifests for validation
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person A\tDesc A\t1\n"
            "Person B\tDesc B\t2\n"
        )
        (self.queries_dir / "llm_query_002_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person C\tDesc C\t1\n"
            "Person D\tDesc D\t2\n"
        )

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_main_happy_path_calculates_metrics_correctly(self):
        """Verify correct metrics are calculated and saved for a valid run."""
        # --- Arrange ---
        self._create_test_input_files()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir), '--num_valid_responses', '2']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
            
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        
        metrics_file = self.analysis_dir / "replication_metrics.json"
        self.assertTrue(metrics_file.is_file())
        
        with open(metrics_file, 'r') as f:
            results = json.load(f)
            
        # Pre-calculated expected values for the test data
        # Trial 1: Ranks [1, 1] -> MRR 1.0, Top-1 1.0
        # Trial 2: Ranks [2, 2] -> MRR 0.5, Top-1 0.0
        # Mean MRR = (1.0 + 0.5) / 2 = 0.75
        # Mean Top-1 Acc = (1.0 + 0.0) / 2 = 0.5
        self.assertAlmostEqual(results['mean_mrr'], 0.75)
        self.assertAlmostEqual(results['mean_top_1_acc'], 0.5)
        self.assertEqual(results['n_valid_responses'], 2)
        
        # Check that distribution files were created
        self.assertTrue((self.analysis_dir / "mrr_distribution_k2.txt").is_file())

    def test_main_zero_valid_responses_creates_null_report(self):
        """Verify a null JSON report is created when there are no valid responses."""
        # --- Arrange ---
        # Create empty input files
        (self.analysis_dir / "all_scores.txt").touch()
        (self.analysis_dir / "all_mappings.txt").touch()
        # The validation logic requires the manifests directory to exist
        (self.run_dir / "session_queries").mkdir(exist_ok=True)
        
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir), '--num_valid_responses', '0']
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
        
        # --- Assert ---
        self.mock_sys_exit.assert_called_with(0) # Should exit cleanly
        
        metrics_file = self.analysis_dir / "replication_metrics.json"
        self.assertTrue(metrics_file.is_file())
        
        with open(metrics_file, 'r') as f:
            results = json.load(f)
        
        self.assertEqual(results['n_valid_responses'], 0)
        self.assertIsNone(results['mean_mrr'])

    def test_main_validation_failure_exits_with_error(self):
        """Verify the script exits on a manifest vs. mapping mismatch."""
        # --- Arrange ---
        # Create a valid set of files first
        self._create_test_input_files()
        # NOW, intentionally corrupt one of the ground-truth files
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person A\tDesc A\t9\n" # This index mismatches mappings.txt
            "Person B\tDesc B\t9\n"
        )
        
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        # --- Act ---
        # The script should now find the mismatch and call sys.exit(1)
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
                
        # --- Assert ---
        # We assert that our mock of sys.exit was called with the error code.
        # The `assertRaises` is incorrect because the mock prevents the exception.
        self.mock_sys_exit.assert_called_with(1)

    # --- Group 2: Core Statistical Function Tests ---

    def test_evaluate_single_test_handles_ties(self):
        """Test the core evaluation function with tied scores."""
        # --- Arrange ---
        score_matrix = np.array([[0.8, 0.8], [0.1, 0.9]])
        correct_mapping = [1, 2] # Correct for row 0 is ID 1; for row 1 is ID 2
        k = 2
        
        # --- Act ---
        results = analyze_llm_performance.evaluate_single_test(score_matrix, correct_mapping, k)
        
        # --- Assert ---
        # For row 0, score 0.8 is tied for ranks 1 and 2. Average rank is (1+2)/2 = 1.5
        # For row 1, score 0.9 is rank 1.
        # Mean rank = (1.5 + 1.0) / 2 = 1.25
        self.assertAlmostEqual(results['mean_rank_of_correct_id'], 1.25)
        # MRR = (1/1.5 + 1/1.0) / 2 = (0.666 + 1.0) / 2 = 0.8333
        self.assertAlmostEqual(results['mrr'], 0.83333333)
        # Top-1 accuracy: only row 1 has a rank of 1. 1/2 = 0.5
        self.assertAlmostEqual(results['top_1_accuracy'], 0.5)

    def test_evaluate_single_test_invalid_inputs(self):
        """Test that evaluate_single_test returns None for mismatched inputs."""
        # Matrix shape is wrong
        result1 = analyze_llm_performance.evaluate_single_test([[1,2],[3,4]], [1,2], k_val=3)
        self.assertIsNone(result1)
        
        # Mapping length is wrong
        result2 = analyze_llm_performance.evaluate_single_test([[1,2],[3,4]], [1], k_val=2)
        self.assertIsNone(result2)

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_analyze_metric_distribution_edge_cases(self):
        """Test analyze_metric_distribution with various edge-case inputs."""
        # No variance in data (all values same)
        result1 = analyze_llm_performance.analyze_metric_distribution([0.5, 0.5, 0.5], 0.1, "test")
        self.assertIsNotNone(result1['ttest_1samp_p']) # Should run
        self.assertIsNotNone(result1['wilcoxon_signed_rank_p'])
        
        # All differences from chance are zero
        result2 = analyze_llm_performance.analyze_metric_distribution([0.1, 0.1, 0.1], 0.1, "test")
        self.assertEqual(result2['wilcoxon_signed_rank_p'], 1.0) # Should be non-significant
        
        # Empty list
        result3 = analyze_llm_performance.analyze_metric_distribution([], 0.1, "test")
        self.assertEqual(result3['count'], 0)
        self.assertTrue(np.isnan(result3['mean']))

    def test_calculate_positional_bias(self):
        """Test positional bias calculation for valid and invalid inputs."""
        # Valid input with a clear trend
        scores = [1, 2, 3, 4, 5]
        result1 = analyze_llm_performance.calculate_positional_bias(scores)
        self.assertAlmostEqual(result1['bias_slope'], 1.0)
        self.assertAlmostEqual(result1['bias_intercept'], 1.0)
        
        # Insufficient data
        scores_short = [1]
        result2 = analyze_llm_performance.calculate_positional_bias(scores_short)
        self.assertTrue(np.isnan(result2['bias_slope']))

    # --- Group 3: File Parsing Tests ---

    def test_read_score_matrices_markdown_format(self):
        """Verify the parser correctly handles markdown tables."""
        md_content = (
            "| Person ID | Desc 1 | Desc 2 |\n"
            "|-----------|--------|--------|\n"
            "| Person 1  | 0.9    | 0.1    |\n"
            "| Person 2  | 0.2    | 0.8    |\n"
        )
        (self.analysis_dir / "md_scores.txt").write_text(md_content)
        
        matrices = analyze_llm_performance.read_score_matrices(
            self.analysis_dir / "md_scores.txt", expected_k=2
        )
        
        self.assertEqual(len(matrices), 1)
        expected_matrix = np.array([[0.9, 0.1], [0.2, 0.8]])
        np.testing.assert_array_equal(matrices[0], expected_matrix)

    def test_read_score_matrices_with_row_headers(self):
        """Verify the parser correctly handles tables with text row headers."""
        content = (
            "Desc_ID\tID_1\tID_2\n"
            "Desc_1\t0.9\t0.1\n"
            "Desc_2\t0.2\t0.8\n"
        )
        (self.analysis_dir / "header_scores.txt").write_text(content)
        
        matrices = analyze_llm_performance.read_score_matrices(
            self.analysis_dir / "header_scores.txt", expected_k=2, delimiter_char='\t'
        )
        
        self.assertEqual(len(matrices), 1)
        expected_matrix = np.array([[0.9, 0.1], [0.2, 0.8]])
        np.testing.assert_array_equal(matrices[0], expected_matrix)

    def test_read_mappings_auto_detects_delimiter_and_k(self):
        """Verify mapping parser auto-detects comma delimiter and deduces k."""
        content = (
            "header1,header2,header3\n"
            "1,2,3\n"
            "3,1,2\n"
        )
        (self.analysis_dir / "mappings.csv").write_text(content)
        
        mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
            self.analysis_dir / "mappings.csv"
        )
        
        self.assertEqual(k, 3)
        self.assertEqual(delim, ',')
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0], [1, 2, 3])

    # --- Group 4: Helper Function Tests ---

    @patch('src.analyze_llm_performance.logging.error')
    def test_read_successful_indices_happy_path(self, mock_logging_error):
        """Verify successful reading of indices file."""
        indices_path = self.run_dir / "successful_indices.txt"
        indices_path.write_text("1\n\n2\n3\n")
        
        result = analyze_llm_performance.read_successful_indices(indices_path)
        self.assertEqual(result, [1, 2, 3])
        mock_logging_error.assert_not_called()

    @patch('src.analyze_llm_performance.logging.error')
    def test_read_successful_indices_file_not_found(self, mock_logging_error):
        """Verify error handling when indices file is missing."""
        indices_path = self.run_dir / "missing_indices.txt"
        
        result = analyze_llm_performance.read_successful_indices(indices_path)
        self.assertIsNone(result)
        mock_logging_error.assert_called_once()
        self.assertIn("Successful indices file not found", mock_logging_error.call_args[0][0])

    @patch('src.analyze_llm_performance.logging.error')
    def test_read_successful_indices_malformed_content(self, mock_logging_error):
        """Verify error handling for non-integer content in indices file."""
        indices_path = self.run_dir / "malformed_indices.txt"
        indices_path.write_text("1\nnot_an_int\n3\n")
        
        result = analyze_llm_performance.read_successful_indices(indices_path)
        self.assertIsNone(result)
        mock_logging_error.assert_called_once()
        self.assertIn("Could not read or parse successful indices file", mock_logging_error.call_args[0][0])
        self.assertIn("invalid literal for int()", mock_logging_error.call_args[0][0])

    def test_save_metric_distribution_happy_path(self):
        """Verify that metric values are correctly saved to a file."""
        metrics = [0.1, 0.2, 0.3]
        output_subdir = self.analysis_dir / "distros"
        filename = "test_metrics.txt"
        
        analyze_llm_performance.save_metric_distribution(metrics, output_subdir, filename)
        
        filepath = output_subdir / filename
        self.assertTrue(filepath.is_file())
        self.assertEqual(filepath.read_text(), "0.1\n0.2\n0.3\n")

    def test_save_metric_distribution_empty_list(self):
        """Verify that nothing is saved for an empty list and prints info."""
        metrics = []
        output_subdir = self.analysis_dir / "distros"
        filename = "empty_metrics.txt"
        
        with patch('builtins.print') as mock_print:
            analyze_llm_performance.save_metric_distribution(metrics, output_subdir, filename, quiet=False)
            
            mock_print.assert_called_once_with(f"Info: No data to save for {filename}.")
        self.assertFalse((output_subdir / filename).exists())

    @patch('builtins.print')
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_save_metric_distribution_io_error(self, mock_open, mock_print):
        """Verify error handling during file write."""
        metrics = [0.1]
        output_subdir = self.analysis_dir / "distros"
        filename = "error_metrics.txt"
        
        analyze_llm_performance.save_metric_distribution(metrics, output_subdir, filename)
        
        mock_print.assert_called_once()
        self.assertIn("Error: Could not save metric distribution", mock_print.call_args[0][0])


    @patch('src.analyze_llm_performance.logging.warning')
    def test_main_exit_no_mappings_zero_valid_responses_scenario(self, mock_logging_warning):
        """Verify main() exits correctly when no mappings are found and num_valid_responses is 0, logging a warning."""
        # --- Arrange ---
        # No mappings file, simulate empty mappings_list from read_mappings_and_deduce_k
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir), '--num_valid_responses', '0']
        
        # Mock read_mappings_and_deduce_k to return empty list, None, None
        with patch('src.analyze_llm_performance.read_mappings_and_deduce_k', return_value=(None, None, None)):
            # --- Act ---
            with patch.object(sys, 'argv', test_argv):
                analyze_llm_performance.main()
            
            # --- Assert ---
            self.mock_sys_exit.assert_called_with(0)
            mock_logging_warning.assert_called_once()
            self.assertIn("No valid mappings found. This indicates zero valid LLM responses.", mock_logging_warning.call_args[0][0])
            
            # Verify a null JSON report was created
            metrics_file = self.analysis_dir / "replication_metrics.json"
            self.assertTrue(metrics_file.is_file())
            with open(metrics_file, 'r') as f:
                results = json.load(f)
            self.assertEqual(results['n_valid_responses'], 0)


    @patch('src.analyze_llm_performance.logging.error')
    def test_main_exit_no_mappings_non_zero_valid_responses_scenario(self, mock_logging_error):
        """Verify main() exits with error when no mappings are found but num_valid_responses is > 0."""
        # --- Arrange ---
        # No mappings file, simulate empty mappings_list from read_mappings_and_deduce_k
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir), '--num_valid_responses', '10']
        
        # Mock read_mappings_and_deduce_k to return empty list, None, None
        with patch('src.analyze_llm_performance.read_mappings_and_deduce_k', return_value=(None, None, None)):
            # --- Act ---
            with patch.object(sys, 'argv', test_argv):
                analyze_llm_performance.main()
            
            # --- Assert ---
            self.mock_sys_exit.assert_called_with(1)
            mock_logging_error.assert_called_once()
            self.assertIn("Inconsistent state: num_valid_responses is 10 but no mappings found. This indicates a pipeline error.", mock_logging_error.call_args[0][0])


    @patch('src.analyze_llm_performance.logging.error')
    def test_main_exit_k_not_deduced(self, mock_logging_error):
        """Verify main() exits if k cannot be deduced from mappings."""
        # --- Arrange ---
        # Simulate read_mappings_and_deduce_k returning a non-None list but None for k
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        with patch('src.analyze_llm_performance.read_mappings_and_deduce_k', return_value=([], None, None)):
            # --- Act ---
            with patch.object(sys, 'argv', test_argv):
                analyze_llm_performance.main()
            
            # --- Assert ---
            self.mock_sys_exit.assert_called_with(1)
            mock_logging_error.assert_called_once_with("Critical Error: Mappings list is not empty, but could not determine k. Halting.")

    @patch('src.analyze_llm_performance.logging.error')
    def test_main_exit_no_score_matrices(self, mock_logging_error):
        """Verify main() exits if no score matrices are loaded."""
        # --- Arrange ---
        self._create_test_input_files() # Create mappings so we don't exit early on that
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        # Mock read_score_matrices to return None
        with patch('src.analyze_llm_performance.read_score_matrices', return_value=None):
            # --- Act ---
            with patch.object(sys, 'argv', test_argv):
                analyze_llm_performance.main()
            
            # --- Assert ---
            self.mock_sys_exit.assert_called_with(1)
            mock_logging_error.assert_called_once()
            self.assertIn("Halting due to issues reading score matrices.", mock_logging_error.call_args[0][0])

    @patch('src.analyze_llm_performance.logging.error')
    def test_main_exit_mismatched_lengths(self, mock_logging_error):
        """Verify main() exits if number of score matrices != number of mappings."""
        # --- Arrange ---
        self._create_test_input_files()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        # Mock read_score_matrices to return a different number of matrices
        with patch('src.analyze_llm_performance.read_score_matrices', return_value=[np.array([[0,1],[1,0]])]): # Only 1 matrix
            # --- Act ---
            with patch.object(sys, 'argv', test_argv):
                analyze_llm_performance.main()
            
            # --- Assert ---
            self.mock_sys_exit.assert_called_with(1)
            mock_logging_error.assert_called_once()
            self.assertIn("Number of score matrices (1) does not match mappings (2).", mock_logging_error.call_args[0][0])


    def test_evaluate_single_test_index_error_handling(self):
        """Verify evaluate_single_test handles IndexError when a mapping index is out of bounds."""
        score_matrix = np.array([[0.8, 0.2], [0.1, 0.9]])
        # This mapping is valid, but we'll simulate an IndexError in the loop
        correct_mapping = [1, 2]
        k = 2
        
        # Patch rankdata to simulate an out-of-bounds error during ranking
        with patch('src.analyze_llm_performance.rankdata', side_effect=IndexError("Simulated index error")), \
             patch('builtins.print') as mock_print:
            results = analyze_llm_performance.evaluate_single_test(score_matrix, correct_mapping, k)
            
            # The function should still return results, but with NaN for the failed rank
            self.assertIsNotNone(results)
            self.assertTrue(np.isnan(results['mean_rank_of_correct_id']))
            
            # Manually check print calls for the warning message
            warning_found = False
            for call_args, _ in mock_print.call_args_list:
                if call_args and isinstance(call_args[0], str) and "Warning: IndexError during evaluation" in call_args[0]:
                    self.assertRegex(call_args[0], r"Warning: IndexError during evaluation for person index \d+\. Error: Simulated index error\. Skipping rank\.")
                    warning_found = True
                    break
            self.assertTrue(warning_found, "Expected IndexError warning not found in print calls.")

    def test_evaluate_single_test_no_variance_mwu(self):
        """Verify MWU warning when all scores are identical."""
        score_matrix = np.array([[0.5, 0.5], [0.5, 0.5]])
        correct_mapping = [1, 2]
        k = 2
        
        with patch('builtins.print') as mock_print:
            results = analyze_llm_performance.evaluate_single_test(score_matrix, correct_mapping, k)
            self.assertIsNotNone(results)
            self.assertEqual(results['p_value_mwu'], 1.0)
            self.assertEqual(results['effect_size_r'], 0.0)
            mock_print.assert_called_with("Warning: Insufficient variance for Mann-Whitney U test. Assigning non-significant p-value.")

    def test_evaluate_single_test_mwu_value_error(self):
        """Verify MWU ValueError handling (when mannwhitneyu itself raises an error)."""
        score_matrix = np.array([[0.8, 0.2], [0.1, 0.9]]) # Data with variance
        correct_mapping = [1, 2]
        k = 2
        
        # Patch mannwhitneyu to explicitly raise ValueError
        with patch('src.analyze_llm_performance.mannwhitneyu', side_effect=ValueError("Test MWU ValueError")), \
             patch('builtins.print') as mock_print:
            results = analyze_llm_performance.evaluate_single_test(score_matrix, correct_mapping, k)
            self.assertIsNotNone(results)
            self.assertIsNone(results['p_value_mwu']) # Should be None if MWU call failed
            mock_print.assert_called_with("Mann-Whitney U error for a test: Test MWU ValueError.")


    def test_analyze_metric_distribution_ttest_error(self):
        """Verify analyze_metric_distribution handles ttest_1samp errors."""
        metric_values = [0.1, 0.2, 0.3]
        
        with patch('src.analyze_llm_performance.ttest_1samp', side_effect=Exception("Test ttest error")), \
             patch('builtins.print') as mock_print:
            result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
            self.assertIsNotNone(result)
            self.assertIsNone(result['ttest_1samp_p'])
            mock_print.assert_called_with("Error during t-test for test_metric: Test ttest error")

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_analyze_metric_distribution_wilcoxon_error_zero_diff(self):
        """Verify analyze_metric_distribution handles Wilcoxon errors (e.g., all differences are zero)."""
        metric_values = [0.1, 0.1, 0.1, 0.1, 0.1] # All differences from chance are zero
        
        # The script's logic should assign 1.0 for p-value if all differences are 0
        result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
        self.assertIsNotNone(result)
        self.assertEqual(result['wilcoxon_signed_rank_p'], 1.0)
        self.assertEqual(result['wilcoxon_signed_rank_stat'], 0.0)

    def test_analyze_metric_distribution_wilcoxon_error_value_error(self):
        """Verify analyze_metric_distribution handles generic Wilcoxon ValueError (e.g., when `wilcoxon` itself fails)."""
        # Create data that would normally be handled by Wilcoxon, but force an error
        metric_values = [0.2, 0.3, 0.4] 
        
        with patch('src.analyze_llm_performance.wilcoxon', side_effect=ValueError("Test Wilcoxon ValueError")), \
             patch('builtins.print') as mock_print:
            result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
            self.assertIsNotNone(result)
            # Manually check print calls for the error message
            error_found = False
            for call_args, _ in mock_print.call_args_list:
                if call_args and isinstance(call_args[0], str) and "Error during Wilcoxon test for test_metric" in call_args[0]:
                    self.assertRegex(call_args[0], r"Error during Wilcoxon test for test_metric \(data: .*\): Test Wilcoxon ValueError")
                    error_found = True
                    break
            self.assertTrue(error_found, "Expected Wilcoxon error message not found in print calls.")
            self.assertIsNone(result['wilcoxon_signed_rank_p']) # Should be None if the Wilcoxon test itself failed

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_analyze_metric_distribution_wilcoxon_edge_case_positive_diff(self):
        """Verify analyze_metric_distribution's Wilcoxon edge case for all positive differences."""
        metric_values = [0.2, 0.2, 0.2, 0.2, 0.2, 0.2] # All differences from chance are positive non-zero
        result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
        self.assertIsNotNone(result)
        # For N=6, all positive differences (relative to chance) with 'greater' alternative,
        # the Wilcoxon p-value is 0.015625.
        self.assertAlmostEqual(result['wilcoxon_signed_rank_p'], 0.015625)

    def test_analyze_metric_distribution_wilcoxon_edge_case_negative_diff(self):
        """Verify analyze_metric_distribution's Wilcoxon edge case for all negative differences."""
        metric_values = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0] # All differences from chance are negative non-zero
        result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
        self.assertIsNotNone(result)
        self.assertEqual(result['wilcoxon_signed_rank_p'], 1.0) # Should be non-significant


    def test_print_metric_analysis_no_results(self):
        """Verify print_metric_analysis handles None or empty analysis_result."""
        with patch('builtins.print') as mock_print:
            analyze_llm_performance.print_metric_analysis(None, "Test Metric Segment", "%.2f")
            mock_print.assert_called_with("\nTest Metric Segment: Analysis result is None or empty.")

        with patch('builtins.print') as mock_print:
            analyze_llm_performance.print_metric_analysis({'name': 'Test', 'count': 0}, "Test Metric Segment", "%.2f")
            mock_print.assert_called_with("\nTest Metric Segment (Test): No valid values to analyze.")

    def test_print_metric_analysis_chance_format_error(self):
        """Verify print_metric_analysis handles errors in chance_level formatting."""
        analysis_result = {'name': 'Test', 'count': 1, 'type': 'float', 'chance_level': 'not_a_number'}
        
        with patch('builtins.print') as mock_print:
            analyze_llm_performance.print_metric_analysis(analysis_result, "Test Metric Segment", "%.2f")
            
            # Find the warning call in the mocked print history
            warning_call_found = False
            for call_args, _ in mock_print.call_args_list:
                if call_args and len(call_args) > 0 and isinstance(call_args[0], str):
                    if "Warning: Could not format chance_level" in call_args[0]:
                        self.assertRegex(call_args[0], r"Warning: Could not format chance_level \(not_a_number\) with format '%.2f'\. Error: could not convert string to float: 'not_a_number'")
                        warning_call_found = True
                        break
            self.assertTrue(warning_call_found, "Expected warning about chance_level formatting not found in print calls.")
            
            # Ensure it still prints the main header lines
            mock_print.assert_any_call("\nTest Metric Segment (vs Chance=not_a_number):")


    def test_read_score_matrices_invalid_k_value(self):
        """Verify read_score_matrices returns None for an invalid expected_k."""
        result = analyze_llm_performance.read_score_matrices(self.analysis_dir / "any_file.txt", expected_k=0)
        self.assertIsNone(result)

    def test_read_score_matrices_malformed_block(self):
        """Verify read_score_matrices handles malformed blocks (wrong number of rows)."""
        content = (
            "0.9\t0.1\t0.0\n"
            "0.2\t0.8\t0.0\n"
            "\n" # Block of 2 rows, should be skipped for k=3
            "0.3\t0.7\t0.0\n"
            "0.6\t0.4\t0.0\n"
            "0.5\t0.5\t0.0\n" # Block of 3 rows, should be loaded
        )
        (self.analysis_dir / "malformed_block.txt").write_text(content)
        
        with patch('builtins.print') as mock_print:
            matrices = analyze_llm_performance.read_score_matrices(self.analysis_dir / "malformed_block.txt", expected_k=3)
            self.assertEqual(len(matrices), 1) # Should load the valid 3x3 matrix
            
            # Search for the specific warning message in the print calls
            warning_found = False
            for call_args, _ in mock_print.call_args_list:
                if call_args and isinstance(call_args[0], str) and "mat end ~L3): 2 lines, exp 3. Skip." in call_args[0]:
                    self.assertRegex(call_args[0], r"W \(File: .*\.txt, mat end ~L3\): 2 lines, exp 3\. Skip\.")
                    warning_found = True
                    break
            self.assertTrue(warning_found, "Expected malformed block warning not found.")

    def test_read_score_matrices_non_float_data(self):
        """Verify non-float data in a row causes a warning and the block to be skipped."""
        content = "0.9\t0.1\nnot_a_float\t0.8\n\n0.3\t0.7\n0.6\t0.4\n"
        (self.analysis_dir / "non_float.txt").write_text(content)
        
        with patch('builtins.print') as mock_print:
            matrices = analyze_llm_performance.read_score_matrices(self.analysis_dir / "non_float.txt", expected_k=2)
            # The first block is discarded due to the non-float line. The second block is loaded.
            self.assertEqual(len(matrices), 1)
            
            # The logic treats 'not_a_float' as a label, parses the rest ('[0.8]'),
            # which has 1 column, triggering a column-count warning.
            warning_found = any("L2): 1 cols, exp 2." in call.args[0] for call in mock_print.call_args_list)
            self.assertTrue(warning_found, "Expected wrong column count warning (due to non-float line) not found.")

    def test_read_score_matrices_wrong_col_count(self):
        """Verify wrong column count prints a warning and skips the line."""
        content = "0.9\t0.1\n0.2\t0.8\t0.99\n\n0.3\t0.7\n0.6\t0.4\n"
        (self.analysis_dir / "wrong_cols.txt").write_text(content)
        
        with patch('builtins.print') as mock_print:
            matrices = analyze_llm_performance.read_score_matrices(self.analysis_dir / "wrong_cols.txt", expected_k=2)
            self.assertEqual(len(matrices), 1)
            
            # The script should print a warning about the wrong number of columns for the specific line.
            warning_found = any("L2): 3 cols, exp 2." in call.args[0] for call in mock_print.call_args_list)
            self.assertTrue(warning_found, "Expected wrong column count warning not found.")


    def test_read_mappings_auto_detects_delimiter_from_data(self):
        """Verify mapping parser auto-detects delimiter from data lines when header is ambiguous."""
        # This content has no clear text header, forcing the data-sniffing logic
        content = "1\t2\t3\n4\t5\t6\n7\t8\t9\n"
        (self.analysis_dir / "mappings.tsv").write_text(content)
        
        with patch('builtins.print') as mock_print:
            mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
                self.analysis_dir / "mappings.tsv"
            )
        
        self.assertEqual(k, 3)
        self.assertEqual(delim, '\t')
        self.assertEqual(len(mappings), 3)

    # --- Group 5: Meta-Analysis Function Tests ---
    
    def test_combine_p_values_stouffer(self):
        """Test Stouffer's method for combining p-values."""
        p_values = [0.1, 0.05, 0.2]
        # Corrected expected results
        z, p = analyze_llm_performance.combine_p_values_stouffer(p_values)
        self.assertAlmostEqual(z, 2.175, places=3)
        self.assertAlmostEqual(p, 0.0148, places=4)
        
        # Test with empty list
        z_empty, p_empty = analyze_llm_performance.combine_p_values_stouffer([])
        self.assertIsNone(z_empty)
        self.assertIsNone(p_empty)

    def test_combine_p_values_fisher(self):
        """Test Fisher's method for combining p-values."""
        p_values = [0.1, 0.05, 0.2]
        # Corrected expected results
        chi2_stat, p = analyze_llm_performance.combine_p_values_fisher(p_values)
        self.assertAlmostEqual(chi2_stat, 13.82, places=2)
        self.assertAlmostEqual(p, 0.03177, places=5)

        # Test with empty list
        chi2_empty, p_empty = analyze_llm_performance.combine_p_values_fisher([])
        self.assertIsNone(chi2_empty)
        self.assertIsNone(p_empty)


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_lifecycle/test_analyze_llm_performance.py ===
