import unittest
from unittest.mock import patch
import os
import sys
import tempfile
import shutil
import re

# Add src directory to path to allow importing the script under test
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
from verify_pipeline_completeness import main as verify_main, count_matrices_in_file, count_lines_in_file

class TestVerifyPipelineCompleteness(unittest.TestCase):

    def setUp(self):
        """Set up a temporary output directory with mock run folders."""
        self.test_dir_obj = tempfile.TemporaryDirectory(prefix="test_verify_")
        self.test_dir = self.test_dir_obj.name

        # --- Create a COMPLETE run directory ---
        self.complete_run_dir = os.path.join(self.test_dir, "run_20240101_120000_rep-01_model-A_sbj-03_trl-02")
        self.complete_queries_dir = os.path.join(self.complete_run_dir, "session_queries")
        self.complete_responses_dir = os.path.join(self.complete_run_dir, "session_responses")
        self.complete_analysis_dir = os.path.join(self.complete_run_dir, "analysis_inputs")
        os.makedirs(self.complete_queries_dir)
        os.makedirs(self.complete_responses_dir)
        os.makedirs(self.complete_analysis_dir)

        # Create 2 query and 2 response files
        with open(os.path.join(self.complete_queries_dir, "llm_query_001.txt"), "w") as f: f.write("q1")
        with open(os.path.join(self.complete_queries_dir, "llm_query_002.txt"), "w") as f: f.write("q2")
        with open(os.path.join(self.complete_responses_dir, "llm_response_001.txt"), "w") as f: f.write("r1")
        with open(os.path.join(self.complete_responses_dir, "llm_response_002.txt"), "w") as f: f.write("r2")
        
        # Create corresponding analysis files with 2 entries each
        with open(os.path.join(self.complete_analysis_dir, "all_scores.txt"), "w") as f:
            f.write("0 0 0\n0 0 0\n0 0 0\n\n0 0 0\n0 0 0\n0 0 0\n") # 2 matrices of k=3
        with open(os.path.join(self.complete_analysis_dir, "all_mappings.txt"), "w") as f:
            f.write("h1\th2\th3\n1\t2\t3\n3\t2\t1\n") # 2 data lines

        # --- Create an INCOMPLETE run directory ---
        self.incomplete_run_dir = os.path.join(self.test_dir, "run_20240101_130000_rep-02_model-B_sbj-02_trl-03")
        self.incomplete_queries_dir = os.path.join(self.incomplete_run_dir, "session_queries")
        self.incomplete_responses_dir = os.path.join(self.incomplete_run_dir, "session_responses")
        self.incomplete_analysis_dir = os.path.join(self.incomplete_run_dir, "analysis_inputs")
        os.makedirs(self.incomplete_queries_dir)
        os.makedirs(self.incomplete_responses_dir)
        os.makedirs(self.incomplete_analysis_dir)

        # Create 3 query files but only 2 response files (API failure)
        with open(os.path.join(self.incomplete_queries_dir, "llm_query_001.txt"), "w") as f: f.write("q1")
        with open(os.path.join(self.incomplete_queries_dir, "llm_query_002.txt"), "w") as f: f.write("q2")
        with open(os.path.join(self.incomplete_queries_dir, "llm_query_003.txt"), "w") as f: f.write("q3")
        with open(os.path.join(self.incomplete_responses_dir, "llm_response_001.txt"), "w") as f: f.write("r1")
        with open(os.path.join(self.incomplete_responses_dir, "llm_response_002.txt"), "w") as f: f.write("r2")

        # Create analysis files with only 2 entries (one is missing)
        with open(os.path.join(self.incomplete_analysis_dir, "all_scores.txt"), "w") as f:
            f.write("0 0\n0 0\n\n0 0\n0 0\n") # 2 matrices of k=2
        with open(os.path.join(self.incomplete_analysis_dir, "all_mappings.txt"), "w") as f:
            f.write("h1\th2\n1\t2\n2\t1\n") # 2 data lines

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir_obj.cleanup()

    def test_helper_functions(self):
        """Test the file counting helper functions directly."""
        # Test count_matrices_in_file
        scores_path = os.path.join(self.complete_analysis_dir, "all_scores.txt")
        self.assertEqual(count_matrices_in_file(scores_path, k=3), 2)
        self.assertEqual(count_matrices_in_file(scores_path, k=2), 3) # Should be integer division

        # Test count_lines_in_file
        mappings_path = os.path.join(self.complete_analysis_dir, "all_mappings.txt")
        self.assertEqual(count_lines_in_file(mappings_path, skip_header=True), 2)
        self.assertEqual(count_lines_in_file(mappings_path, skip_header=False), 3)

        # Test non-existent file
        self.assertEqual(count_lines_in_file("non_existent_file.txt"), 0)

    def test_main_verification_logic(self):
        """Test the main script logic for finding and reporting completeness."""
        # Arrange: mock the command-line arguments and the logger
        cli_args = ['verify_pipeline_completeness.py', '--parent_dir', self.test_dir]
        
        with patch('logging.info') as mock_log_info, \
             patch.object(sys, 'argv', cli_args):
            # Act
            verify_main()
            
        # Assert: check the captured logging output
        output = "\n".join([call.args[0] for call in mock_log_info.call_args_list])

        # Check for the COMPLETE run
        self.assertIn("run_20240101_120000_rep-01_model-A_sbj-03_trl-02", output)
        self.assertIn("COMPLETE", output)
        self.assertIn("2/2 trials processed", output)

        # Check for the INCOMPLETE run
        self.assertIn("run_20240101_130000_rep-02_model-B_sbj-02_trl-03", output)
        self.assertIn("INCOMPLETE", output)
        # Check for the new detailed failure report
        self.assertIn("Responses: 2/3, Matrices: 2/3, Mappings: 2/3", output)

        # Check the final summary
        self.assertIn("Overall Pipeline Completeness: 80.00%", output) # (2+2) / (2+3) = 4/5 = 80%

if __name__ == '__main__':
    unittest.main()