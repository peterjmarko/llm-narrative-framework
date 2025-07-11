#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import sys
import tempfile
import numpy as np
from scipy.stats import norm 

# Adjust path to import analyze_performance and potentially config_loader
SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__))
SRC_DIR_REAL_PROJECT = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..', 'src'))

if SRC_DIR_REAL_PROJECT not in sys.path:
    sys.path.insert(0, SRC_DIR_REAL_PROJECT)

from analyze_llm_performance import (
    evaluate_single_test,
    combine_p_values_stouffer,
    combine_p_values_fisher,
    analyze_metric_distribution,
    calculate_mrr_chance,
    calculate_top_k_accuracy_chance,
    read_mappings_and_deduce_k,
    read_score_matrices,
    read_successful_indices,
    main as analyze_main 
)

class TestAnalyzePerformance(unittest.TestCase):

    def setUp(self):
        self.test_dir_obj = tempfile.TemporaryDirectory(prefix="test_analyze_perf_")
        self.test_dir = self.test_dir_obj.name
        self.original_sys_argv = list(sys.argv)

    def tearDown(self):
        self.test_dir_obj.cleanup()
        sys.argv = self.original_sys_argv

    def test_evaluate_single_test_perfect_scores(self):
        k = 6 # Increased k
        # Correct mapping is identity [1,2,3,4,5,6]
        # Highest score on diagonal, lower scores elsewhere
        score_matrix = np.diag([10]*k) + np.random.rand(k,k) # Add small noise to off-diagonals
        np.fill_diagonal(score_matrix, 10) # Ensure diagonal is highest
        for r in range(k): # Ensure diagonal is strictly greater
            for c in range(k):
                if r != c and score_matrix[r,c] >= 10:
                    score_matrix[r,c] = np.random.uniform(0,9)


        correct_mapping = list(range(1, k + 1)) # 1-based [1,2,3,4,5,6]
        top_k_val_for_acc = 3 # Test Top-3

        results = evaluate_single_test(score_matrix, correct_mapping, k, top_k_val_for_acc)

        self.assertIsNotNone(results)
        self.assertEqual(results['k_val'], k)
        self.assertTrue(0 <= results['p_value_mwu'] <= 0.05) 
        self.assertTrue(results['effect_size_r'] > 0.5) 
        self.assertEqual(results['mrr'], 1.0)
        self.assertEqual(results['top_1_accuracy'], 1.0)
        self.assertEqual(results[f'top_{top_k_val_for_acc}_accuracy'], 1.0)

    def test_evaluate_single_test_worst_scores(self):
        k = 6 # Increased k
        # Correct mapping is identity [1,2,3,4,5,6]
        # Lowest score on diagonal
        score_matrix = np.ones((k,k)) * 10 # High scores off-diagonal
        np.fill_diagonal(score_matrix, 1) # Low scores on diagonal

        correct_mapping = list(range(1, k + 1))
        results = evaluate_single_test(score_matrix, correct_mapping, k, k) # Top-K where K=k

        self.assertIsNotNone(results)
        self.assertTrue(results['p_value_mwu'] > 0.95 or np.isnan(results['p_value_mwu']))
        if not np.isnan(results['effect_size_r']):
             self.assertTrue(results['effect_size_r'] < -0.5) 

        self.assertAlmostEqual(results['mrr'], 1.0 / k) # All correct items are rank k
        self.assertEqual(results['top_1_accuracy'], 0.0)
        self.assertEqual(results[f'top_{k}_accuracy'], 1.0)

    def test_evaluate_single_test_no_variance(self):
        k = 6 # Increased k
        score_matrix = np.full((k, k), 5.0) 
        correct_mapping = list(range(1, k + 1))
        results = evaluate_single_test(score_matrix, correct_mapping, k, k)
        
        self.assertIsNotNone(results)
        self.assertEqual(results['p_value_mwu'], 1.0) 
        self.assertEqual(results['effect_size_r'], 0.0)
        
        # With rankdata(method='average'), all tied items get the average rank.
        # For k items, the ranks are 1..k, the average is (k+1)/2.
        # The MRR for every row will be 1/((k+1)/2).
        expected_mrr = 2.0 / (k + 1)
        self.assertAlmostEqual(results['mrr'], expected_mrr)
        # Since the average rank for k>1 will be > 1, no item is ranked first. Top-1 is 0.
        self.assertAlmostEqual(results['top_1_accuracy'], 0.0)


    def test_combine_p_values(self):
        p_values = [0.01, 0.04, 0.005, 0.1, 0.02, 0.03] # k=6 p-values
        stouffer_z, stouffer_p = combine_p_values_stouffer(p_values)
        fisher_chi2, fisher_p = combine_p_values_fisher(p_values)
        self.assertIsNotNone(stouffer_p)
        self.assertIsNotNone(fisher_p)
        self.assertTrue(0 <= stouffer_p <= 0.001) # Expect combined p to be very small
        self.assertTrue(0 <= fisher_p <= 0.001)
        self.assertIsNone(combine_p_values_stouffer([])[1])
        self.assertIsNone(combine_p_values_fisher([])[1])
        self.assertIsNone(combine_p_values_stouffer([None, np.nan])[1])

    def test_analyze_metric_distribution(self):
        metric_values = [0.8, 0.9, 0.7, 0.85, 0.92, 0.75, 0.88, 0.65] # More values
        chance_level = 0.5 # For k=6, 1/k = 0.166 chance for Top-1
        analysis = analyze_metric_distribution(metric_values, chance_level, "Test Metric k6")
        
        self.assertEqual(analysis['count'], 8)
        self.assertAlmostEqual(analysis['mean'], np.mean(metric_values))
        self.assertAlmostEqual(analysis['median'], np.median(metric_values))
        self.assertTrue(analysis['ttest_1samp_p'] < 0.05) 
        self.assertTrue(analysis['wilcoxon_signed_rank_p'] < 0.05)

    def test_chance_level_calculations(self):
        k = 6 # Increased k
        self.assertAlmostEqual(calculate_mrr_chance(k), sum(1/i for i in range(1, k + 1)) / k)
        self.assertAlmostEqual(calculate_top_k_accuracy_chance(1, k), 1/k)
        self.assertAlmostEqual(calculate_top_k_accuracy_chance(3, k), 3/k) # Test for Top-3
        self.assertAlmostEqual(calculate_top_k_accuracy_chance(k, k), 1.0)
        self.assertAlmostEqual(calculate_top_k_accuracy_chance(k + 1, k), 1.0)

    def test_read_mappings_and_deduce_k_simple_tab(self):
        k = 6 # Increased k
        header = "\t".join([f"Map_idx{i+1}" for i in range(k)])
        map_line1 = "\t".join(map(str, list(range(1, k + 1)))) # 1 2 3 4 5 6
        map_line2 = "\t".join(map(str, [2,1,4,3,6,5]))       # Swapped pairs
        content = f"{header}\n{map_line1}\n{map_line2}"
        map_filepath = os.path.join(self.test_dir, "map_k6.txt")
        with open(map_filepath, "w") as f:
            f.write(content)
        
        mappings, deduced_k, delim = read_mappings_and_deduce_k(map_filepath, specified_delimiter_keyword='tab')
        self.assertEqual(deduced_k, k)
        self.assertEqual(delim, '\t')
        self.assertEqual(len(mappings), 2)
        self.assertEqual(mappings[0], list(range(1, k + 1)))
        self.assertEqual(mappings[1], [2,1,4,3,6,5])

    def test_read_mappings_auto_detect_comma_deduce_k(self):
        k = 6 # Increased k
        header = ",".join([f"H{i+1}" for i in range(k)])
        map_line1 = ",".join(map(str, list(range(1, k + 1))))
        map_line2 = ",".join(map(str, [6,5,4,3,2,1])) # Reversed
        content = f"{header}\n{map_line1}\n{map_line2}" 
        map_filepath = os.path.join(self.test_dir, "map_comma_k6.txt")
        with open(map_filepath, "w") as f: f.write(content)
        
        mappings, deduced_k, delim = read_mappings_and_deduce_k(map_filepath) 
        self.assertEqual(deduced_k, k)
        self.assertEqual(delim, ',')
        self.assertEqual(mappings[0], list(range(1, k + 1)))
        self.assertEqual(mappings[1], [6,5,4,3,2,1])


    def test_read_score_matrices_simple_tab(self):
        k = 6 # Increased k
        matrix1_rows = ["\t".join([f"{r*k+c+0.1:.1f}" for c in range(k)]) for r in range(k)]
        matrix2_rows = ["\t".join([f"{(r*k+c+0.1)*2:.1f}" for c in range(k)]) for r in range(k)]
        content = "\n".join(matrix1_rows) + "\n\n" + "\n".join(matrix2_rows)
        
        scores_filepath = os.path.join(self.test_dir, "scores_k6.txt")
        with open(scores_filepath, "w") as f:
            f.write(content)
            
        matrices = read_score_matrices(scores_filepath, k, delimiter_char='\t')
        self.assertEqual(len(matrices), 2)
        self.assertEqual(matrices[0].shape, (k,k))
        self.assertEqual(matrices[1].shape, (k,k))
        self.assertAlmostEqual(matrices[0][0,0], 0.1)
        self.assertAlmostEqual(matrices[1][k-1,k-1], (( (k-1)*k + (k-1) + 0.1)*2))


    @patch('builtins.print')
    def test_main_function_runs_simple_case(self, mock_print):
        k = 6 
        m = 3 # Number of matrices/test sets
        
        # Test Set 1: Perfect
        map1 = list(range(1, k+1)) # [1,2,3,4,5,6]
        scores1_list = []
        for r_idx in range(k):
            row = [f"{0.1 + (i*0.05):.2f}" for i in range(k)] # Base scores
            row[map1[r_idx]-1] = "1.00" # Perfect score for the correct item
            scores1_list.append("\t".join(row))
        scores_matrix1_str = "\n".join(scores1_list)
        # MRR=1.0, Top1=1.0, Top3=1.0 for Test Set 1

        # Test Set 2: Mixed (first half Top1, second half correct at Rank 2)
        map2 = list(range(1, k+1)) # [1,2,3,4,5,6]
        scores2_list = []
        for r_idx in range(k):
            true_col_idx = map2[r_idx]-1
            row_scores_vals = [np.random.uniform(0,0.5) for _ in range(k)] # Base low scores
            if r_idx < k // 2: # First 3 items: correct is Top1
                row_scores_vals[true_col_idx] = 0.90 
            else: # Last 3 items: correct is Rank 2
                row_scores_vals[true_col_idx] = 0.70 
                alt_high_idx = (true_col_idx + 1) % k
                while alt_high_idx == true_col_idx : # Ensure different column for highest
                    alt_high_idx = (alt_high_idx +1) % k
                row_scores_vals[alt_high_idx] = 0.80
            scores2_list.append("\t".join([f"{val:.2f}" for val in row_scores_vals]))
        scores_matrix2_str = "\n".join(scores2_list)
        # MRR for Test Set 2 = ( (1/1)*3 + (1/2)*3 ) / 6 = (3 + 1.5) / 6 = 4.5 / 6 = 0.75
        # Top1 for Test Set 2 = 3/6 = 0.5
        # Top3 for Test Set 2 = 6/6 = 1.0 (all correct are within Rank 1 or 2)

        # Test Set 3: Poor performance. Aim for some correct items to be Rank > 3.
        map3 = list(range(1, k+1)) # Keep mapping simple for predictability: [1,2,3,4,5,6]
        # np.random.shuffle(map3) # Shuffling makes it harder to control ranks precisely for test
        scores3_list = []
        top3_hits_test3 = 0
        for r_idx in range(k): # Iterate through persons P0 to P5
            true_col_idx = map3[r_idx]-1 # Correct description index for this person
            row_scores_vals = [np.random.uniform(0.0, 0.3) for _ in range(k)] # Base low scores

            if r_idx < k // 2: # For first 3 persons, make correct item Rank 3
                row_scores_vals[true_col_idx] = 0.5 # Correct item's score
                # Need two other scores > 0.5
                others_higher_count = 0
                for c_idx in range(k):
                    if c_idx == true_col_idx: continue
                    if others_higher_count < 2:
                        row_scores_vals[c_idx] = np.random.uniform(0.6, 0.8)
                        others_higher_count += 1
                    if others_higher_count == 2: break
            else: # For last 3 persons, make correct item Rank 4 (or worse)
                row_scores_vals[true_col_idx] = 0.4 # Correct item's score
                # Need three other scores > 0.4
                others_higher_count = 0
                for c_idx in range(k):
                    if c_idx == true_col_idx: continue
                    if others_higher_count < 3:
                        row_scores_vals[c_idx] = np.random.uniform(0.5, 0.8)
                        others_higher_count += 1
                    if others_higher_count == 3: break
            
            # Check if this correct item is within Top-3 for accuracy calculation
            sorted_score_indices_desc = np.argsort(-np.array(row_scores_vals))
            rank_of_correct_item = np.where(sorted_score_indices_desc == true_col_idx)[0][0] + 1
            if rank_of_correct_item <= 3: # Using the test's top_k_acc value of 3
                top3_hits_test3 +=1

            scores3_list.append("\t".join([f"{val:.2f}" for val in row_scores_vals]))
        scores_matrix3_str = "\n".join(scores3_list)
        # Expected Top-3 Acc for Test Set 3: (k/2) / k = 0.5 if first half Rank 3, second half Rank >3
        # With the logic above: first 3 items will be rank 3. Last 3 items will be rank 4.
        # So, top3_hits_test3 should be 3. Top-3 Accuracy = 3/6 = 0.5.

        scores_content_varied = f"{scores_matrix1_str}\n\n{scores_matrix2_str}\n\n{scores_matrix3_str}"
        all_mappings = [map1, map2, map3]

        # ---- New Setup for main() function to match new arg requirements ----
        analysis_inputs_dir = os.path.join(self.test_dir, "analysis_inputs")
        session_queries_dir = os.path.join(self.test_dir, "session_queries")
        os.makedirs(analysis_inputs_dir, exist_ok=True)
        os.makedirs(session_queries_dir, exist_ok=True)
        
        scores_filepath = os.path.join(analysis_inputs_dir, "all_scores.txt")
        mappings_filepath = os.path.join(analysis_inputs_dir, "all_mappings.txt")

        with open(scores_filepath, "w") as f: f.write(scores_content_varied)

        mappings_header = "\t".join([f"Map{i+1}" for i in range(k)])
        mappings_content = f"{mappings_header}\n" + "\n".join(["\t".join(map(str, m)) for m in all_mappings])
        with open(mappings_filepath, "w") as f: f.write(mappings_content)
        
        # Create dummy validation files that the script now requires
        indices_filepath = os.path.join(analysis_inputs_dir, "successful_query_indices.txt")
        with open(indices_filepath, "w") as f:
            for i in range(1, m + 1): f.write(f"{i}\n")

        for i, mapping in enumerate(all_mappings):
            manifest_idx = i + 1
            manifest_path = os.path.join(session_queries_dir, f"llm_query_{manifest_idx:03d}_manifest.txt")
            manifest_content = "Col1\tCol2\tTrue_Map_ID\n"
            manifest_lines = [f"P_{j+1}\tD_{j+1}\t{mapping[j]}" for j in range(k)]
            manifest_content += "\n".join(manifest_lines)
            with open(manifest_path, "w") as f: f.write(manifest_content)

        test_args = [
            'analyze_llm_performance.py', 
            '--run_output_dir', self.test_dir,
            '--k_value', str(k),
            '--delimiter', 'tab',
            '--top_k_acc', '3' 
        ]
        with patch.object(sys, 'argv', test_args):
            try: analyze_main()
            except SystemExit as e: self.assertTrue(e.code is None or e.code == 0, f"analyze_main exited: {e.code}")
        
        printed_output = "".join([call_args[0][0] for call_args in mock_print.call_args_list if call_args[0]])
        # Check for the machine-readable summary tags and content
        self.assertIn("<<<METRICS_JSON_START>>>", printed_output)
        self.assertIn("<<<METRICS_JSON_END>>>", printed_output)
        self.assertIn(f'"mean_top_{3}_acc"', printed_output) # Check for Top-K metric in JSON
        self.assertNotIn("Halting due to issues", printed_output)


    @patch('builtins.print')
    def test_main_function_k_deduction_and_autodelim(self, mock_print_auto):
        k = 6 
        m = 3 # Number of matrices

        # Test Set 1 (Perfect) - Comma Delimited
        map1 = list(range(1, k+1))
        s1_list_comma = []
        for r_idx in range(k):
            row = [f"{0.1 + (i*0.01):.2f}" for i in range(k)]
            row[map1[r_idx]-1] = "1.00"
            s1_list_comma.append(",".join(row))
        scores_m1_comma = "\n".join(s1_list_comma)

        # Test Set 2 (Imperfect: half Top1, half Rank 2) - Comma Delimited
        map2 = list(range(1, k+1))
        s2_list_comma = []
        for r_idx in range(k):
            true_col_idx = map2[r_idx]-1
            row_scores_vals = [np.random.uniform(0,0.5) for _ in range(k)]
            if r_idx < k // 2: 
                row_scores_vals[true_col_idx] = 0.95
            else: 
                row_scores_vals[true_col_idx] = 0.75
                alt_high_idx = (true_col_idx + 1) % k
                while alt_high_idx == true_col_idx: alt_high_idx = (alt_high_idx+1)%k
                row_scores_vals[alt_high_idx] = 0.85
            s2_list_comma.append(",".join([f"{val:.2f}" for val in row_scores_vals]))
        scores_m2_comma = "\n".join(s2_list_comma)

        # Test Set 3 (Poor performance) - Comma Delimited
        map3 = [(i % k) + 1 for i in range(k)] 
        np.random.shuffle(map3)
        s3_list_comma = []
        for r_idx in range(k):
            true_col_idx = map3[r_idx]-1
            row_scores_vals = [np.random.uniform(0,0.3) for _ in range(k)]
            row_scores_vals[true_col_idx] = 0.4 # Correct item score
            # Ensure at least two others have higher scores
            higher_score_indices = []
            while len(higher_score_indices) < 2:
                idx = np.random.randint(0,k)
                if idx != true_col_idx and idx not in higher_score_indices:
                    higher_score_indices.append(idx)
            row_scores_vals[higher_score_indices[0]] = 0.6
            if k > 1: row_scores_vals[higher_score_indices[1]] = 0.5
            s3_list_comma.append(",".join([f"{val:.2f}" for val in row_scores_vals]))
        scores_m3_comma = "\n".join(s3_list_comma)

        scores_content_varied_comma = f"{scores_m1_comma}\n\n{scores_m2_comma}\n\n{scores_m3_comma}"
        all_mappings_comma = [map1, map2, map3]

        # ---- New Setup for main() function ----
        analysis_inputs_dir = os.path.join(self.test_dir, "analysis_inputs")
        session_queries_dir = os.path.join(self.test_dir, "session_queries")
        os.makedirs(analysis_inputs_dir, exist_ok=True)
        os.makedirs(session_queries_dir, exist_ok=True)

        scores_filepath = os.path.join(analysis_inputs_dir, "all_scores.txt")
        mappings_filepath = os.path.join(analysis_inputs_dir, "all_mappings.txt")
        with open(scores_filepath, "w") as f: f.write(scores_content_varied_comma)

        mappings_header_comma = ",".join([f"H{i+1}" for i in range(k)])
        mappings_content_comma = f"{mappings_header_comma}\n" + "\n".join([",".join(map(str, m)) for m in all_mappings_comma])
        with open(mappings_filepath, "w") as f: f.write(mappings_content_comma)

        # Create dummy validation files that the script now requires
        indices_filepath = os.path.join(analysis_inputs_dir, "successful_query_indices.txt")
        with open(indices_filepath, "w") as f:
            for i in range(1, m + 1): f.write(f"{i}\n")

        for i, mapping in enumerate(all_mappings_comma):
            manifest_idx = i + 1
            manifest_path = os.path.join(session_queries_dir, f"llm_query_{manifest_idx:03d}_manifest.txt")
            manifest_content = "Col1\tCol2\tTrue_Map_ID\n"
            manifest_lines = [f"P_{j+1}\tD_{j+1}\t{mapping[j]}" for j in range(k)]
            manifest_content += "\n".join(manifest_lines)
            with open(manifest_path, "w") as f: f.write(manifest_content)

        test_args = [
            'analyze_llm_performance.py',
            '--run_output_dir', self.test_dir,
            # No -k, should deduce k=6
            # No -d, should deduce comma
            '--top_k_acc', '2' # Test with Top-2 for this auto-detect case
        ]
        with patch.object(sys, 'argv', test_args), \
             patch('builtins.print') as mock_print_auto:
            try: analyze_main()
            except SystemExit as e: self.assertTrue(e.code is None or e.code == 0, f"analyze_main exited: {e.code}")
        
        printed_output = "".join([call_args[0][0] for call_args in mock_print_auto.call_args_list if call_args[0]])
        self.assertIn(f"Deduced k as {k}", printed_output)
        self.assertIn(f"Deduced delimiter '{repr(',')}'", printed_output)
        self.assertNotIn("Halting due to issues", printed_output)
        # Check for the machine-readable summary tags and content
        self.assertIn("<<<METRICS_JSON_START>>>", printed_output)
        self.assertIn("<<<METRICS_JSON_END>>>", printed_output)
        self.assertIn(f'"mean_top_{2}_acc"', printed_output) # Check for the specified Top-K


    def test_read_score_matrices_markdown_table(self):
        """Tests that the script can parse a Markdown table, skipping headers and separators."""
        k = 3
        content = """
        | Name (Year)        | ID 1 | ID 2 | ID 3 |
        |--------------------|------|------|------|
        | Person A (1900)    | 0.1  | 0.2  | 0.3  |
        | Person B (1910)    | 0.4  | 0.5  | 0.6  |
        | Person C (1920)    | 0.7  | 0.8  | 0.9  |
        """
        scores_filepath = os.path.join(self.test_dir, "scores_markdown.txt")
        with open(scores_filepath, "w") as f:
            f.write(content)

        matrices = read_score_matrices(scores_filepath, k)
        self.assertEqual(len(matrices), 1)
        self.assertEqual(matrices[0].shape, (k, k))
        self.assertAlmostEqual(matrices[0][0, 0], 0.1)
        self.assertAlmostEqual(matrices[0][2, 2], 0.9)

    def test_read_score_matrices_tab_with_header_column(self):
        """Tests parsing a tab-delimited file with a non-numeric first column (row labels)."""
        k = 3
        content = (
            "Name\tID 1\tID 2\tID 3\n"
            "Person A (1900)\t0.1\t0.2\t0.3\n"
            "Person B (1910)\t0.4\t0.5\t0.6\n"
            "Person C (1920)\t0.7\t0.8\t0.9\n"
        )
        scores_filepath = os.path.join(self.test_dir, "scores_header_col.txt")
        with open(scores_filepath, "w") as f:
            f.write(content)

        # Using delimiter='\t' to correctly parse the tab-separated data.
        matrices = read_score_matrices(scores_filepath, k, delimiter_char='\t')
        self.assertEqual(len(matrices), 1)
        self.assertEqual(matrices[0].shape, (k, k))
        self.assertAlmostEqual(matrices[0][0, 0], 0.1)
        self.assertAlmostEqual(matrices[0][2, 2], 0.9)

    def test_evaluate_single_test_error_conditions(self):
        k = 5
        matrix_ok = np.eye(k)
        mapping_ok = list(range(1, k + 1))

        with patch('builtins.print') as mock_print:
            # Test with matrix of wrong shape
            matrix_bad_shape = np.eye(k, k + 1)
            self.assertIsNone(evaluate_single_test(matrix_bad_shape, mapping_ok, k))
            mock_print.assert_called_with(f"Warning: evaluate_single_test received matrix with incorrect shape {(k, k+1)}, expected ({k},{k}). Skipping this test.")

            # Test with mapping of wrong length
            mapping_bad_len = list(range(1, k))
            self.assertIsNone(evaluate_single_test(matrix_ok, mapping_bad_len, k))
            mock_print.assert_called_with(f"Warning: correct_mapping_indices_1_based has {len(mapping_bad_len)} elements, expected {k}. Skipping this test.")

            # Test with invalid values in mapping (e.g., > k)
            mapping_bad_val = list(range(1, k)) + [k + 1]
            self.assertIsNone(evaluate_single_test(matrix_ok, mapping_bad_val, k))
            mock_print.assert_called_with(f"Warning: Invalid value in correct_mapping_indices_1_based (not between 1 and {k}). Skipping this test.")

    def test_read_files_error_conditions(self):
        # Test read_mappings with non-existent file
        mappings, k, delim = read_mappings_and_deduce_k("non_existent_file.txt")
        self.assertIsNone(mappings)

        # Test read_mappings with empty file
        empty_filepath = os.path.join(self.test_dir, "empty.txt")
        open(empty_filepath, 'a').close()
        mappings, k, delim = read_mappings_and_deduce_k(empty_filepath)
        self.assertIsNone(mappings)
        
        # Test read_score_matrices with invalid k
        self.assertIsNone(read_score_matrices("any_file.txt", expected_k=0))
        
        # Test read_successful_indices with non-existent file
        self.assertIsNone(read_successful_indices("non_existent_file.txt"))

        # Test read_successful_indices with bad data
        bad_indices_path = os.path.join(self.test_dir, "bad_indices.txt")
        with open(bad_indices_path, 'w') as f: f.write("1\ntwo\n3")
        self.assertIsNone(read_successful_indices(bad_indices_path))

    def test_main_validation_failure(self):
        k = 3
        # Setup the necessary file structure for main()
        analysis_inputs_dir = os.path.join(self.test_dir, "analysis_inputs")
        session_queries_dir = os.path.join(self.test_dir, "session_queries")
        os.makedirs(analysis_inputs_dir, exist_ok=True)
        os.makedirs(session_queries_dir, exist_ok=True)

        # Create scores file
        scores_content = "1,0,0\n0,1,0\n0,0,1"
        scores_filepath = os.path.join(analysis_inputs_dir, "all_scores.txt")
        with open(scores_filepath, 'w') as f: f.write(scores_content)
        
        # Create mappings file
        mappings_content = "1,2,3" # This is what we will test against
        mappings_filepath = os.path.join(analysis_inputs_dir, "all_mappings.txt")
        with open(mappings_filepath, 'w') as f: f.write(mappings_content)

        # Create successful indices file
        indices_filepath = os.path.join(analysis_inputs_dir, "successful_query_indices.txt")
        with open(indices_filepath, 'w') as f: f.write("1\n")

        # Create a MISMATCHED manifest file
        manifest_path = os.path.join(session_queries_dir, f"llm_query_001_manifest.txt")
        manifest_content = "Col1\tCol2\tTrue_Map_ID\n"
        manifest_content += "P1\tD1\t3\n" # Mismatch here
        manifest_content += "P2\tD2\t2\n"
        manifest_content += "P3\tD3\t1\n"
        with open(manifest_path, 'w') as f: f.write(manifest_content)

        test_args = ['analyze_llm_performance.py', '--run_output_dir', self.test_dir, '--k_value', str(k), '--delimiter', ',']
        
        with patch.object(sys, 'argv', test_args), \
             patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit) as cm:
                analyze_main()
            self.assertEqual(cm.exception.code, 1) # Should exit with error code
            printed_output = "".join([call.args[0] for call in mock_print.call_args_list if call.args])
            # The detailed "Mismatch" message goes to the logger, not stdout.
            # We only need to check for the final critical message that is printed to stdout.
            self.assertIn("CRITICAL: ANALYZER VALIDATION FAILED", printed_output)

    def test_main_verbose_and_quiet_flags(self):
        # Create a minimal valid run setup
        k = 3
        analysis_inputs_dir = os.path.join(self.test_dir, "analysis_inputs")
        session_queries_dir = os.path.join(self.test_dir, "session_queries")
        os.makedirs(analysis_inputs_dir, exist_ok=True)
        os.makedirs(session_queries_dir, exist_ok=True)
        
        scores_filepath = os.path.join(analysis_inputs_dir, "all_scores.txt")
        with open(scores_filepath, 'w') as f: f.write("1,0,0\n0,1,0\n0,0,1")
        mappings_filepath = os.path.join(analysis_inputs_dir, "all_mappings.txt")
        with open(mappings_filepath, 'w') as f: f.write("1,2,3")
        indices_filepath = os.path.join(analysis_inputs_dir, "successful_query_indices.txt")
        with open(indices_filepath, 'w') as f: f.write("1\n")
        manifest_path = os.path.join(session_queries_dir, f"llm_query_001_manifest.txt")
        with open(manifest_path, 'w') as f: f.write("Col1\tCol2\tTrue_Map_ID\nP1\tD1\t1\nP2\tD2\t2\nP3\tD3\t3")

        # Test with --verbose_per_test
        args_verbose = ['prog', '--run_output_dir', self.test_dir, '-k', str(k), '--delimiter', ',', '--verbose_per_test']
        with patch.object(sys, 'argv', args_verbose), patch('builtins.print') as mock_print:
            try: analyze_main()
            except SystemExit: pass
            printed_output = "".join([call.args[0] for call in mock_print.call_args_list if call.args])
            self.assertIn("Test 1 MWU p-value:", printed_output)

        # Test with --quiet
        args_quiet = ['prog', '--run_output_dir', self.test_dir, '-k', str(k), '--delimiter', ',', '--quiet']
        with patch.object(sys, 'argv', args_quiet), patch('builtins.print') as mock_print:
            try: analyze_main()
            except SystemExit: pass
            printed_output = "".join([call.args[0] for call in mock_print.call_args_list if call.args])
            self.assertNotIn("Successfully loaded", printed_output) # Suppressed info message
            self.assertIn("ANALYZER_VALIDATION_SUCCESS", printed_output) # Critical messages still print
            self.assertIn("<<<METRICS_JSON_START>>>", printed_output)

    def test_print_metric_analysis_edge_cases(self):
        from analyze_llm_performance import print_metric_analysis
        with patch('builtins.print') as mock_print:
            # Test with None input
            print_metric_analysis(None, "Test Metric", "%.4f")
            mock_print.assert_called_with("\nTest Metric: Analysis result is None or empty.")
            
            # Test with zero count
            result_zero_count = {'name': 'Empty Metric', 'count': 0}
            print_metric_analysis(result_zero_count, "Test Metric", "%.4f")
            mock_print.assert_called_with("\nTest Metric (Empty Metric): No valid values to analyze.")
            
            # Test with invalid chance level formatting
            result_bad_chance = {'count': 1, 'chance_level': 'not-a-number'}
            print_metric_analysis(result_bad_chance, "Test Metric", "%.2f")
            printed_output = "".join(call.args[0] for call in mock_print.call_args_list)
            self.assertIn("Warning: Could not format chance_level", printed_output)

    def test_evaluate_single_test_k1(self):
        """Test the edge case where k=1, so there are no incorrect scores."""
        k = 1
        score_matrix = np.array([[10]])
        correct_mapping = [1]
        results = evaluate_single_test(score_matrix, correct_mapping, k, 1)

        self.assertIsNotNone(results)
        self.assertIsNone(results['p_value_mwu']) # No incorrect scores, so MWU can't run
        self.assertEqual(results['mrr'], 1.0)
        self.assertEqual(results['top_1_accuracy'], 1.0)

    def test_calculate_positional_bias(self):
        """Tests the linear regression for positional bias."""
        from analyze_llm_performance import calculate_positional_bias

        # Test with a clear downward trend
        performance_scores = [0.9, 0.8, 0.8, 0.7, 0.6]
        bias_metrics = calculate_positional_bias(performance_scores)
        self.assertIsNotNone(bias_metrics)
        self.assertLess(bias_metrics['bias_slope'], 0) # Expect a negative slope
        self.assertTrue(0 < bias_metrics['bias_p_value'] < 0.1) # Should be significant or near-significant

        # Test with insufficient data
        bias_metrics_insufficient = calculate_positional_bias([0.9])
        self.assertTrue(np.isnan(bias_metrics_insufficient['bias_slope']))

    def test_main_mismatched_file_lengths(self):
        """Tests main() when the number of score matrices and mappings are different."""
        k = 3
        analysis_inputs_dir = os.path.join(self.test_dir, "analysis_inputs")
        os.makedirs(analysis_inputs_dir, exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, "session_queries"), exist_ok=True) # For validation

        # 2 score matrices
        scores_content = "1,0,0\n0,1,0\n0,0,1\n\n1,0,0\n0,1,0\n0,0,1"
        with open(os.path.join(analysis_inputs_dir, "all_scores.txt"), 'w') as f: f.write(scores_content)
        
        # 1 mapping
        with open(os.path.join(analysis_inputs_dir, "all_mappings.txt"), 'w') as f: f.write("1,2,3")
        with open(os.path.join(analysis_inputs_dir, "successful_query_indices.txt"), 'w') as f: f.write("1\n") # Match mapping count

        test_args = ['prog', '--run_output_dir', self.test_dir, '-k', str(k), '--delimiter', ',']
        with patch.object(sys, 'argv', test_args), patch('builtins.print') as mock_print:
            with self.assertRaises(SystemExit):
                analyze_main()
            printed_output = "".join([call.args[0] for call in mock_print.call_args_list if call.args])
            self.assertIn("Error: Number of score matrices (2) does not match mappings (1)", printed_output)

    def test_read_mappings_inconsistent_lines(self):
        """Tests that read_mappings handles files with inconsistent numbers of columns."""
        k = 3
        # First line is valid (k=3), second is not
        content = "1,2,3\n4,5"
        map_filepath = os.path.join(self.test_dir, "map_inconsistent.txt")
        with open(map_filepath, "w") as f: f.write(content)

        with patch('builtins.print') as mock_print:
            mappings, deduced_k, delim = read_mappings_and_deduce_k(map_filepath, specified_delimiter_keyword=',')
            self.assertEqual(deduced_k, k)
            self.assertEqual(len(mappings), 1) # Should only parse the valid line
            self.assertEqual(mappings[0], [1, 2, 3])
            
            printed_output = "".join([call.args[0] for call in mock_print.call_args_list if call.args])
            self.assertIn(f"Parsed with 2 elements, expected k={k}", printed_output)

    def test_read_score_matrices_malformed_block(self):
        """Tests that a malformed matrix block is skipped entirely."""
        k = 3
        # Middle block has only 2 columns, should be skipped
        content = "1\t2\t3\n4\t5\t6\n7\t8\t9\n\n1\t2\n3\t4\n5\t6\n\n10\t11\t12\n13\t14\t15\n16\t17\t18"
        scores_filepath = os.path.join(self.test_dir, "scores_malformed.txt")
        with open(scores_filepath, "w") as f: f.write(content)

        with patch('builtins.print') as mock_print:
            matrices = read_score_matrices(scores_filepath, k, delimiter_char='\t')
            self.assertEqual(len(matrices), 2) # Should find the first and third matrices
            self.assertAlmostEqual(matrices[0][0, 0], 1.0)
            self.assertAlmostEqual(matrices[1][2, 2], 18.0)
            
            printed_output = "".join([call.args[0] for call in mock_print.call_args_list if call.args])
            self.assertIn(f"2 cols, exp {k}", printed_output)

if __name__ == '__main__':
    unittest.main(verbosity=2)

# === End of tests/test_analyze_llm_performance.py ===
