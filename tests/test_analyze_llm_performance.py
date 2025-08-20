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
# Filename: tests/test_analyze_llm_performance.py

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

if __name__ == '__main__':
    unittest.main()

# === End of tests/test_analyze_llm_performance.py ===
