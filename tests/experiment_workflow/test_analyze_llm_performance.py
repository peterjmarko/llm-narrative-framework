#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: tests/experiment_workflow/test_analyze_llm_performance.py

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
import builtins
# Import the module to test
from src import analyze_llm_performance

class TestAnalyzeLLMPerformance(unittest.TestCase):
    """Test suite for analyze_llm_performance.py."""

    def setUp(self):
        """Set up a temporary directory and mock dependencies for each test."""
        # Backup sys.modules to ensure test isolation
        self.sys_modules_backup = sys.modules.copy()

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
        
        # Restore sys.modules to its state before the test ran
        sys.modules.clear()
        sys.modules.update(self.sys_modules_backup)

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

        # Verify that the value from a NumPy operation (np.mean) is a standard Python float
        self.assertIsInstance(results['mean_mrr'], float)
        
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

    # --- Group 9: Validation Logic Tests ---

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch('builtins.print')
    @patch('src.analyze_llm_performance.logging.error')
    def test_main_completes_but_suppresses_success_on_validation_mismatch(self, mock_log_error, mock_print):
        """Verify script completes but suppresses success marker if a manifest mismatches."""
        # --- Arrange ---
        self._create_test_input_files()
        # Intentionally corrupt a manifest file to cause a validation mismatch
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person A\tDesc A\t9\n"
            "Person B\tDesc B\t9\n"
        )
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]

        # --- Act ---
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
        
        # --- Assert ---
        self.mock_sys_exit.assert_not_called()
        mock_log_error.assert_any_call("CRITICAL: ANALYZER VALIDATION FAILED WITH 1 ERRORS. Analysis will complete, but the run is marked as invalid.")
        success_message_found = any("ANALYZER_VALIDATION_SUCCESS" in call.args[0] for call in mock_print.call_args_list if call.args)
        self.assertFalse(success_message_found)

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch('builtins.print')
    def test_main_zero_responses_path_does_not_print_success(self, mock_print):
        """Verify the 'zero valid responses' path exits cleanly without printing a success message."""
        (self.analysis_dir / "all_mappings.txt").touch()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir), '--num_valid_responses', '0']
        
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()

        self.mock_sys_exit.assert_called_with(0)
        success_message_found = any("ANALYZER_VALIDATION_SUCCESS" in call.args[0] for call in mock_print.call_args_list if call.args)
        self.assertFalse(success_message_found, "Validation success message should not be printed for zero responses.")

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch('builtins.print')
    @patch('src.analyze_llm_performance.logging.critical')
    def test_main_completes_but_suppresses_success_if_indices_file_is_missing(self, mock_log_critical, mock_print):
        """Verify the script completes but suppresses the success marker if successful_indices.txt is missing."""
        self._create_test_input_files()
        (self.analysis_dir / "successful_indices.txt").unlink()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]

        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
            self.mock_sys_exit.assert_not_called()
            mock_log_critical.assert_called_once()
            self.assertIn("Could not perform final validation", mock_log_critical.call_args[0][0])
            success_message_found = any("ANALYZER_VALIDATION_SUCCESS" in call.args[0] for call in mock_print.call_args_list if call.args)
            self.assertFalse(success_message_found)

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch('builtins.print')
    @patch('src.analyze_llm_performance.logging.critical')
    def test_main_completes_but_suppresses_success_on_length_mismatch(self, mock_log_critical, mock_print):
        """Verify script completes but suppresses success on indices/mappings length mismatch."""
        self._create_test_input_files()
        # Add an extra line to cause a length mismatch
        with open(self.analysis_dir / "successful_indices.txt", "a") as f:
            f.write("3\n")
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]

        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
            self.mock_sys_exit.assert_not_called()
            mock_log_critical.assert_called_once()
            self.assertIn("Could not perform final validation", mock_log_critical.call_args[0][0])
            success_message_found = any("ANALYZER_VALIDATION_SUCCESS" in call.args[0] for call in mock_print.call_args_list if call.args)
            self.assertFalse(success_message_found)

    # --- Group 2: Core Statistical Function Tests ---

    def test_evaluate_single_test_unbiased_tie_breaking(self):
        """Verify that tie-breaking for chosen_positions is unbiased."""
        # --- Arrange ---
        # Row 0 has a tie for the top score at indices 0 and 2.
        # Row 1 has a clear winner at index 1.
        # Row 2 is padding to make the matrix 3x3 as required by k=3.
        score_matrix = np.array([
            [0.9, 0.1, 0.9], 
            [0.2, 0.8, 0.3],
            [0.4, 0.5, 0.6]
        ])
        correct_mapping = [1, 2, 3]
        k = 3
        
        # --- Act ---
        # Run many times to check the distribution of random choices
        choices = []
        for _ in range(1000):
            # Seed random for reproducibility within the test
            np.random.seed(_)
            results = analyze_llm_performance.evaluate_single_test(score_matrix, correct_mapping, k)
            # We only care about the choice for the first person (row 0)
            choices.append(results['raw_chosen_positions'][0])

        # --- Assert ---
        # Check that both tied indices (0 and 2) were chosen
        self.assertIn(0, choices)
        self.assertIn(2, choices)
        # Check that the non-tied index (1) was never chosen
        self.assertNotIn(1, choices)

        # Check that the choices are approximately evenly distributed
        counts = {i: choices.count(i) for i in set(choices)}
        self.assertAlmostEqual(counts[0] / 1000, 0.5, delta=0.1)
        self.assertAlmostEqual(counts[2] / 1000, 0.5, delta=0.1)

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

    def test_analyze_metric_distribution_uses_correct_hypothesis_for_rank(self):
        """Verify the t-test uses alternative='less' for rank-based metrics."""
        # --- Arrange ---
        # This data has a mean rank of 2.0, which is significantly *less* than chance (5.5)
        ranks = [1, 1, 2, 2, 3, 3]
        chance_level = 5.5
        
        # --- Act ---
        # The metric_name contains "rank", which should trigger the 'less' hypothesis.
        results = analyze_llm_performance.analyze_metric_distribution(ranks, chance_level, "Mean Rank of Correct ID")
        
        # --- Assert ---
        # If alternative='less' was used correctly, the p-value should be very small.
        # If the incorrect 'greater' was used, the p-value would be close to 1.0.
        self.assertLess(results['ttest_1samp_p'], 0.05)


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

    def test_calculate_mean_rank_chance(self):
        """Test mean rank chance calculation for various k values."""
        # For k=2, expected rank = (2+1)/2 = 1.5
        self.assertAlmostEqual(analyze_llm_performance.calculate_mean_rank_chance(2), 1.5)
        
        # For k=4, expected rank = (4+1)/2 = 2.5
        self.assertAlmostEqual(analyze_llm_performance.calculate_mean_rank_chance(4), 2.5)
        
        # For k=10, expected rank = (10+1)/2 = 5.5
        self.assertAlmostEqual(analyze_llm_performance.calculate_mean_rank_chance(10), 5.5)
        
        # Edge case: k=0 should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_mean_rank_chance(0), 0.0)
        
        # Edge case: negative k should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_mean_rank_chance(-1), 0.0)

    def test_calculate_mrr_chance_edge_cases(self):
        """Test MRR chance calculation with edge case inputs."""
        # k=0 should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_mrr_chance(0), 0.0)
        
        # negative k should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_mrr_chance(-5), 0.0)
        
        # k=1 should return 1.0 (only one position, reciprocal rank = 1/1)
        self.assertEqual(analyze_llm_performance.calculate_mrr_chance(1), 1.0)

    def test_calculate_top_k_accuracy_chance_edge_cases(self):
        """Test Top-K accuracy chance calculation with edge case inputs."""
        # K=0, k=5 should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_top_k_accuracy_chance(0, 5), 0.0)
        
        # K=3, k=0 should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_top_k_accuracy_chance(3, 0), 0.0)
        
        # K > k: should cap at k/k = 1.0
        self.assertEqual(analyze_llm_performance.calculate_top_k_accuracy_chance(10, 5), 1.0)
        
        # negative values should return 0.0
        self.assertEqual(analyze_llm_performance.calculate_top_k_accuracy_chance(-1, 5), 0.0)
        self.assertEqual(analyze_llm_performance.calculate_top_k_accuracy_chance(3, -5), 0.0)

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

    def test_read_mappings_auto_detects_delimiter_from_header(self):
        """Test lines 313-315: Verify delimiter detection from header structure."""
        # Test tab-delimited header detection
        tab_content = "Header1\tHeader2\tHeader3\n1\t2\t3\n3\t1\t2\n"
        (self.analysis_dir / "tab_mappings.txt").write_text(tab_content)
        
        mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
            self.analysis_dir / "tab_mappings.txt"
        )
        
        self.assertEqual(k, 3)
        self.assertEqual(delim, '\t')
        self.assertEqual(len(mappings), 2)
        
        # Test comma-delimited header detection
        comma_content = "Header1,Header2,Header3\n1,2,3\n3,1,2\n"
        (self.analysis_dir / "comma_mappings.txt").write_text(comma_content)
        
        mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
            self.analysis_dir / "comma_mappings.txt"
        )
        
        self.assertEqual(k, 3)
        self.assertEqual(delim, ',')
        self.assertEqual(len(mappings), 2)
        
    def test_read_mappings_falls_back_to_whitespace_when_detection_fails(self):
        """Test lines 406-412: Verify fallback to whitespace when delimiter auto-detection fails."""
        # Ambiguous content that won't trigger tab or comma detection
        ambiguous_content = "1 2 3\n3 1 2\n"
        (self.analysis_dir / "space_mappings.txt").write_text(ambiguous_content)
        
        with patch('builtins.print') as mock_print:
            mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
                self.analysis_dir / "space_mappings.txt"
            )
            
            # Should fall back to None (whitespace splitting)
            self.assertIsNone(delim)
            self.assertEqual(k, 3)
            self.assertEqual(len(mappings), 2)
            
            # Verify the fallback message was printed
            print_calls = [str(call) for call in mock_print.call_args_list]
            fallback_message_found = any("Could not auto-detect comma or tab" in call for call in print_calls)
            self.assertTrue(fallback_message_found, "Expected fallback message not found")

    def test_read_mappings_and_deduce_k_skips_non_permutations(self):
        """Verify the mapping parser skips lines that are not valid permutations."""
        content = (
            "1,2,3\n"  # Valid
            "1,1,2\n"  # Invalid (duplicate)
            "3,1,2\n"  # Valid
            "1,2,4\n"  # Invalid (out of range)
        )
        (self.analysis_dir / "mappings.csv").write_text(content)
        
        with patch('src.analyze_llm_performance.logging.warning') as mock_log_warning:
            mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
                self.analysis_dir / "mappings.csv", k_override=3
            )

        # Assert that only the two valid permutations were loaded
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0], [1, 2, 3])
        self.assertEqual(mappings[1], [3, 1, 2])
        
        # Assert that warnings were logged for the two invalid lines
        self.assertEqual(mock_log_warning.call_count, 2)
        self.assertIn("not a valid permutation", mock_log_warning.call_args_list[0].args[0])
        self.assertIn("not a valid permutation", mock_log_warning.call_args_list[1].args[0])


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

    def test_analyze_metric_distribution_ttest_error(self):
        """Verify analyze_metric_distribution handles ttest_1samp errors."""
        metric_values = [0.1, 0.2, 0.3]
        
        with patch('src.analyze_llm_performance.ttest_1samp', side_effect=Exception("Test ttest error")), \
             patch('src.analyze_llm_performance.logging.error') as mock_log_error:
            result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
            self.assertIsNotNone(result)
            self.assertIsNone(result['ttest_1samp_p'])
            mock_log_error.assert_called_with("Error during t-test for test_metric: Test ttest error")

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
             patch('src.analyze_llm_performance.logging.warning') as mock_log_warning:
            result = analyze_llm_performance.analyze_metric_distribution(metric_values, 0.1, "test_metric")
            self.assertIsNotNone(result)
            mock_log_warning.assert_called_once_with("Wilcoxon test failed for test_metric: Test Wilcoxon ValueError")
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

    @patch('src.analyze_llm_performance.logging.warning')
    def test_read_score_matrices_parser_robustness(self, mock_log_warning):
        """Verify the parser correctly handles row labels, malformed data, and incorrect column counts."""
        content = (
            "RowA 0.9 0.1\n"
            "RowB 0.2 0.8\n"
            "\n"
            "1.0 NOT_A_FLOAT\n"
            "3.0 4.0\n"
            "\n"
            "5.0 6.0 7.0\n"
            "8.0 9.0\n"
            "\n"
            "1.1 2.2\n"
            "3.3 4.4\n"
        )
        path = self.analysis_dir / "robustness_test.txt"
        path.write_text(content)

        matrices = analyze_llm_performance.read_score_matrices(path, expected_k=2)

        # Should load the first and fourth blocks, skipping the two invalid ones.
        self.assertEqual(len(matrices), 2)
        expected_matrix_1 = np.array([[0.9, 0.1], [0.2, 0.8]])
        expected_matrix_4 = np.array([[1.1, 2.2], [3.3, 4.4]])
        np.testing.assert_array_equal(matrices[0], expected_matrix_1)
        np.testing.assert_array_equal(matrices[1], expected_matrix_4)

        # Check that the correct warnings were logged for the two bad rows.
        self.assertEqual(mock_log_warning.call_count, 2)
        all_log_calls = [call.args[0] for call in mock_log_warning.call_args_list]
        log_text = "\n".join(all_log_calls)

        # Check for malformed data warning from the "NOT_A_FLOAT" row
        self.assertIn("Malformed score line", log_text)
        self.assertIn("1.0 NOT_A_FLOAT", log_text)

        # Check for wrong column count warning from the "5.0 6.0 7.0" row
        self.assertIn("3 cols, exp 2", log_text)


    def test_read_mappings_auto_detects_delimiter_from_data(self):
        """Verify mapping parser auto-detects delimiter from data lines when header is ambiguous."""
        # This content has no clear text header, forcing the data-sniffing logic.
        # All lines are valid permutations of [1,2,3].
        content = "1\t2\t3\n3\t1\t2\n2\t3\t1\n"
        (self.analysis_dir / "mappings.tsv").write_text(content)
        
        with patch('builtins.print') as mock_print:
            mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
                self.analysis_dir / "mappings.tsv"
            )
        
        self.assertEqual(k, 3)
        self.assertEqual(delim, '\t')
        self.assertEqual(len(mappings), 3)

    # --- Group 5: Meta-Analysis Function Tests ---
    

    # --- Group 6: Additional Coverage Tests ---

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_main_config_loader_import_failure_uses_fallback(self):
        """Test lines 50-57: Verify fallback configuration is used when import fails."""
        # Unload the target module to force a re-import under the patch
        if 'src.analyze_llm_performance' in sys.modules:
            del sys.modules['src.analyze_llm_performance']

        # Temporarily make 'config_loader' un-importable.
        with patch.dict('sys.modules', {'config_loader': None}):
            # Re-importing the module now triggers the 'except ImportError' block
            from src import analyze_llm_performance as reloaded_analyze

            # --- Arrange ---
            self._create_test_input_files()
            test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir), '--num_valid_responses', '2']

            # --- Act & Assert ---
            with patch.object(sys, 'argv', test_argv):
                reloaded_analyze.main()
                # A successful run with data does not call sys.exit; it just finishes.
                self.mock_sys_exit.assert_not_called()

        # No manual cleanup needed; tearDown now handles restoring sys.modules.


    @patch('src.analyze_llm_performance.print')
    def test_evaluate_single_test_wrong_matrix_shape(self, mock_print):
        """Test line 105: Verify error return for wrong matrix shape."""
        # Matrix is 2x2, but k is 3
        result = analyze_llm_performance.evaluate_single_test([[1, 2], [3, 4]], [1, 2, 3], k_val=3)
        self.assertIsNone(result)
        mock_print.assert_any_call("Warning: evaluate_single_test received matrix with incorrect shape (2, 2), expected (3,3). Skipping this test.")

    @patch('src.analyze_llm_performance.print')
    def test_evaluate_single_test_wrong_mapping_length(self, mock_print):
        """Test line 108: Verify error return for wrong mapping length."""
        # Matrix is 2x2, k is 2, but mapping length is 1
        result = analyze_llm_performance.evaluate_single_test([[1, 2], [3, 4]], [1], k_val=2)
        self.assertIsNone(result)
        mock_print.assert_any_call("Warning: correct_mapping_indices_1_based has 1 elements, expected 2. Skipping this test.")

    @patch('src.analyze_llm_performance.print')
    def test_evaluate_single_test_invalid_mapping_value(self, mock_print):
        """Test line 118: Verify error return for mapping index out of 1-based range."""
        # Matrix is 2x2, k is 2, mapping index 3 is > 2
        result = analyze_llm_performance.evaluate_single_test([[1, 2], [3, 4]], [1, 3], k_val=2)
        self.assertIsNone(result)
        mock_print.assert_any_call("Warning: Invalid value in correct_mapping_indices_1_based (not between 1 and 2). Skipping this test.")

    @patch('src.analyze_llm_performance.print')
    def test_read_mappings_and_deduce_k_empty_or_non_data_file_failure(self, mock_print):
        """Test lines 387-389, 423-425: Verify logic for empty file and failure to deduce k."""
        
        # Test empty file (lines 387-389)
        (self.analysis_dir / "empty_map.txt").write_text("")
        mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
            self.analysis_dir / "empty_map.txt", k_override=None
        )
        self.assertIsNone(mappings)
        self.assertIsNone(k)
        mock_print.assert_any_call(f"Error: Mappings file {self.analysis_dir / 'empty_map.txt'} is empty.")
        
        # Test file that contains only text/non-numeric content (should fail to deduce k > 0)
        (self.analysis_dir / "non_numeric_map.txt").write_text("a b c\nd e f\n")
        mappings, k, delim = analyze_llm_performance.read_mappings_and_deduce_k(
            self.analysis_dir / "non_numeric_map.txt", k_override=None
        )
        self.assertIsNone(mappings)
        self.assertIsNone(k)
        # The code falls back to the default delimiter (None), so the error message prints repr(None)
        mock_print.assert_any_call(f"Error: Could not deduce a valid k > 0 from {self.analysis_dir / 'non_numeric_map.txt'} with delimiter '{repr(None)}'.")
        

    @patch('src.analyze_llm_performance.print')
    def test_read_score_matrices_file_not_found_error(self, mock_print):
        """Test line 581: Verify error handling when score file is missing."""
        path = self.analysis_dir / "missing_scores.txt"
        matrices = analyze_llm_performance.read_score_matrices(path, expected_k=2)
        self.assertIsNone(matrices)
        mock_print.assert_any_call(f"Error: Score matrices file not found at {path}")

    @patch('src.analyze_llm_performance.print')
    def test_read_score_matrices_non_float_in_row_makes_block_malformed(self, mock_print):
        """Verify a row with non-float data is skipped, causing a block size error at EOF."""
        # The line with "FAIL" will be skipped by the line-by-line parser.
        # This leaves a final block of only 1 row, which is incorrect for k=2.
        content = (
            "1.0\t0.0\n"
            "0.0\tFAIL\n"
        )
        path = self.analysis_dir / "non_float_matrix_eof.txt"
        path.write_text(content)

        matrices = analyze_llm_performance.read_score_matrices(path, expected_k=2, delimiter_char='\t')

        # No matrices should be loaded because the only block is malformed (1 row instead of 2).
        self.assertEqual(len(matrices), 0)

        # The warning should be about the final block having the wrong number of lines.
        warning_found = any("Last mat block 1 lines, exp 2. Skip." in call.args[0] for call in mock_print.call_args_list)
        self.assertTrue(warning_found, "Expected wrong line count warning at EOF not found.")

    @patch('src.analyze_llm_performance.read_score_matrices', return_value=None)
    @patch('src.analyze_llm_performance.read_mappings_and_deduce_k', return_value=([1], 1, ' '))
    def test_main_exit_on_score_matrices_read_failure(self, mock_read_mappings, mock_read_scores):
        """Test line 932->exit: Verify main exits with error code 1 if score matrices read returns None."""
        # --- Arrange ---
        self._create_test_input_files()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        # --- Act ---
        with patch.object(sys, 'argv', test_argv), \
             patch('src.analyze_llm_performance.logging.error') as mock_log_error:
            analyze_llm_performance.main()
            
        # --- Assert ---
            self.mock_sys_exit.assert_called_with(1)
            mock_log_error.assert_called_once_with("Halting due to issues reading score matrices.")


    # --- Group 7: Final Coverage Push (80%+) ---

    def _run_space_delimiter_test(self, delimiter_arg):
        """Helper function to run the core logic for space delimiter tests."""
        # Create files with irregular whitespace that would fail a simple line.split(' ')
        (self.analysis_dir / "all_scores.txt").write_text("0.9  0.1\n0.2\t0.8\n") # multiple spaces, tab
        (self.analysis_dir / "all_mappings.txt").write_text("h1 h2\n1   2\n") # multiple spaces
        (self.analysis_dir / "successful_indices.txt").write_text("1\n")
        (self.queries_dir / "llm_query_001_manifest.txt").write_text(
            "Shuffled_Name\tShuffled_Desc_Text\tShuffled_Desc_Index\n"
            "Person A\tDesc A\t1\n"
            "Person B\tDesc B\t2\n"
        )
        test_argv = [
            'analyze_llm_performance.py',
            '--run_output_dir', str(self.run_dir),
            '--delimiter', delimiter_arg,
            '-k', '2',
            '--num_valid_responses', '1'
        ]
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()

        # A successful run (no sys.exit call) is the primary validation.
        self.mock_sys_exit.assert_not_called()
        metrics_file = self.analysis_dir / "replication_metrics.json"
        self.assertTrue(metrics_file.is_file())
        with open(metrics_file, 'r') as f:
            results = json.load(f)
        self.assertEqual(results['n_valid_responses'], 1)

    def test_main_handles_space_delimiter_keyword(self):
        """Verify the script correctly parses irregular whitespace for the 'space' keyword."""
        self._run_space_delimiter_test('space')

    def test_main_handles_space_delimiter_literal(self):
        """Verify the script correctly parses irregular whitespace for the ' ' literal."""
        self._run_space_delimiter_test(' ')

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch('builtins.print')
    @patch('src.analyze_llm_performance.logging.error')
    def test_main_validation_fails_if_manifest_is_missing(self, mock_log_error, mock_print):
        """Verify script completes but suppresses success if a manifest is missing."""
        # --- Arrange ---
        self._create_test_input_files()
        # Delete one of the required manifests
        (self.queries_dir / "llm_query_002_manifest.txt").unlink()

        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        # --- Act & Assert ---
        with patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()
            
            # The script should NOT exit
            self.mock_sys_exit.assert_not_called()
            
            # It should log the specific error
            mock_log_error.assert_any_call(f"  VALIDATION FAIL: Manifest for original index 2 not found at '{self.queries_dir / 'llm_query_002_manifest.txt'}'")
            
            # It should suppress the final success marker
            success_message_found = any("ANALYZER_VALIDATION_SUCCESS" in call.args[0] for call in mock_print.call_args_list if call.args)
            self.assertFalse(success_message_found)

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    @patch('builtins.print')
    @patch('src.analyze_llm_performance.logging.error')
    def test_main_validation_fails_on_manifest_read_error(self, mock_log_error, mock_print):
        """Verify script completes but suppresses success if a manifest cannot be read."""
        # --- Arrange ---
        self._create_test_input_files()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]

        original_open = builtins.open
        def open_side_effect(file, *args, **kwargs):
            if "llm_query_002_manifest.txt" in str(file):
                raise IOError("Test IO Error")
            return original_open(file, *args, **kwargs)

        # --- Act & Assert ---
        with patch('builtins.open', side_effect=open_side_effect), \
             patch.object(sys, 'argv', test_argv):
            analyze_llm_performance.main()

            # The script should NOT exit
            self.mock_sys_exit.assert_not_called()

            # It should log the specific error with enhanced error handling
            mock_log_error.assert_any_call("  VALIDATION ERROR: Unexpected error processing manifest for index 2: Test IO Error")
            
            # It should suppress the final success marker
            success_message_found = any("ANALYZER_VALIDATION_SUCCESS" in call.args[0] for call in mock_print.call_args_list if call.args)
            self.assertFalse(success_message_found)

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_main_io_error_on_final_metrics_save(self):
        """Test lines 850-853: Verify an error is printed if final JSON save fails."""
        # --- Arrange ---
        self._create_test_input_files()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        original_open = builtins.open
        def open_side_effect(file, *args, **kwargs):
            # Only fail when trying to write the final metrics file
            if "replication_metrics.json" in str(file):
                raise IOError("Permission denied")
            return original_open(file, *args, **kwargs)

        # --- Act & Assert ---
        with patch('builtins.open', side_effect=open_side_effect), \
             patch.object(sys, 'argv', test_argv), \
             patch('builtins.print') as mock_print:
            
            analyze_llm_performance.main()
            metrics_filepath = self.analysis_dir / "replication_metrics.json"
            mock_print.assert_any_call(f"Error: Could not write metrics to {metrics_filepath}. Reason: Permission denied")

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_main_wilcoxon_value_error_in_mean_rank_analysis(self):
        """Test lines 809-815: Verify the except block for wilcoxon ValueError is hit gracefully."""
        # --- Arrange ---
        self._create_test_input_files()
        test_argv = ['analyze_llm_performance.py', '--run_output_dir', str(self.run_dir)]
        
        # --- Act & Assert ---
        # Patch wilcoxon to raise a ValueError, simulating a failure condition
        with patch.object(sys, 'argv', test_argv), \
             patch('src.analyze_llm_performance.wilcoxon', side_effect=ValueError("Test wilcoxon error")), \
             patch('src.analyze_llm_performance.logging.warning') as mock_log_warning:
            
            analyze_llm_performance.main()
            
            # Verify the enhanced error logging was called
            mock_log_warning.assert_called_with("Wilcoxon test failed for Mean Rank of Correct ID: Test wilcoxon error")
            
            # The script should complete successfully, but the p-value will be None
            metrics_file = self.analysis_dir / "replication_metrics.json"
            self.assertTrue(metrics_file.is_file())
            with open(metrics_file, 'r') as f:
                results = json.load(f)
            self.assertIsNone(results['rank_of_correct_id_p'])

    def test_read_score_matrices_skips_markdown_separator(self):
        """Test line 452: Verify the parser correctly handles and skips markdown table separator lines."""
        md_content = (
            "| Person 1  | 0.9    | 0.1    |\n"
            "|-----------|--------|--------|\n" # This should be skipped
            "| Person 2  | 0.2    | 0.8    |\n"
        )
        (self.analysis_dir / "md_scores_sep.txt").write_text(md_content)
        
        matrices = analyze_llm_performance.read_score_matrices(
            self.analysis_dir / "md_scores_sep.txt", expected_k=2
        )
        
        self.assertEqual(len(matrices), 1)
        expected_matrix = np.array([[0.9, 0.1], [0.2, 0.8]])
        np.testing.assert_array_equal(matrices[0], expected_matrix)


    # --- Group 8: Serialization and Data Type Tests ---
    
    def test_numpy_converter_handles_numpy_types(self):
        """Verify the _numpy_converter correctly converts NumPy scalars."""
        # Test np.float64
        np_float = np.float64(3.14)
        py_float = analyze_llm_performance._numpy_converter(np_float)
        self.assertIsInstance(py_float, float)
        self.assertAlmostEqual(py_float, 3.14)

        # Test np.int64
        np_int = np.int64(42)
        py_int = analyze_llm_performance._numpy_converter(np_int)
        self.assertIsInstance(py_int, int)
        self.assertEqual(py_int, 42)

    def test_numpy_converter_raises_type_error_for_unhandled_types(self):
        """Verify the _numpy_converter raises TypeError for non-NumPy objects."""
        with self.assertRaises(TypeError):
            analyze_llm_performance._numpy_converter({1, 2, 3}) # A set is not serializable


    def test_read_score_matrices_markdown_with_numeric_first_column(self):
        """Verify the parser does not drop the first column if it's numeric."""
        # This content would fail with the old logic, which would incorrectly
        # drop the first column (e.g., '1.0', '2.0'). This test provides a
        # valid 3x3 matrix to the k=3 parser.
        md_content = (
            "| 1.0 | 0.9 | 0.1 |\n"
            "| 2.0 | 0.2 | 0.8 |\n"
            "| 3.0 | 0.3 | 0.7 |\n"
        )
        (self.analysis_dir / "md_scores_numeric.txt").write_text(md_content)
        
        matrices = analyze_llm_performance.read_score_matrices(
            self.analysis_dir / "md_scores_numeric.txt", expected_k=3
        )
        
        self.assertEqual(len(matrices), 1)
        expected_matrix = np.array([[1.0, 0.9, 0.1], [2.0, 0.2, 0.8], [3.0, 0.3, 0.7]])
        np.testing.assert_array_equal(matrices[0], expected_matrix)


if __name__ == '__main__':
    unittest.main()

# === End of tests/experiment_workflow/test_analyze_llm_performance.py ===
