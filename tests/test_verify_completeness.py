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

    def _create_run(self, base_dir, name, k, m, is_complete):
        """Helper to create a mock run directory with specified parameters."""
        run_dir = os.path.join(base_dir, name)
        queries_dir = os.path.join(run_dir, "session_queries")
        responses_dir = os.path.join(run_dir, "session_responses")
        analysis_dir = os.path.join(run_dir, "analysis_inputs")
        os.makedirs(queries_dir)
        os.makedirs(responses_dir)
        os.makedirs(analysis_dir)

        # A failed run has one less actual trial than expected
        actual_m = m if is_complete else m - 1
        if actual_m < 0: actual_m = 0

        # Create query (always expected number) and response files (actual number)
        for i in range(m):
            with open(os.path.join(queries_dir, f"llm_query_{i+1:03d}.txt"), "w") as f: f.write(f"q{i}")
        for i in range(actual_m):
            with open(os.path.join(responses_dir, f"llm_response_{i+1:03d}.txt"), "w") as f: f.write(f"r{i}")

        # Create analysis files based on the actual number of processed trials
        matrix_line = " ".join(["0"] * k) + "\n"
        matrix_block = (matrix_line * k) + "\n"
        with open(os.path.join(analysis_dir, "all_scores.txt"), "w") as f:
            f.write(matrix_block * actual_m)
        
        mapping_header = "\t".join([f"h{i}" for i in range(k)]) + "\n"
        mapping_line = "\t".join([str(i) for i in range(k)]) + "\n"
        with open(os.path.join(analysis_dir, "all_mappings.txt"), "w") as f:
            f.write(mapping_header)
            f.write(mapping_line * actual_m)
        
        return run_dir

    def setUp(self):
        """Set up a nested temporary directory structure for depth testing."""
        self.test_dir_obj = tempfile.TemporaryDirectory(prefix="test_verify_")
        self.test_dir = self.test_dir_obj.name

        # Create a nested directory structure
        self.level1_dir = os.path.join(self.test_dir, 'level1')
        self.level2_dir = os.path.join(self.level1_dir, 'level2')
        os.makedirs(self.level2_dir)

        # Run 1 (Top-level, COMPLETE)
        self.run1_dir = self._create_run(
            self.test_dir, "run_A_sbj-03_trl-02", k=3, m=2, is_complete=True
        )
        # Run 2 (Level 1, INCOMPLETE)
        self.run2_dir = self._create_run(
            self.level1_dir, "run_B_sbj-02_trl-03", k=2, m=3, is_complete=False
        )
        # Run 3 (Level 2, COMPLETE)
        self.run3_dir = self._create_run(
            self.level2_dir, "run_C_sbj-04_trl-01", k=4, m=1, is_complete=True
        )

    def tearDown(self):
        """Clean up the temporary directory."""
        self.test_dir_obj.cleanup()

    def test_helper_functions(self):
        """Test the file counting helper functions directly."""
        # Test count_matrices_in_file
        scores_path = os.path.join(os.path.dirname(self.run1_dir), "run_A_sbj-03_trl-02", "analysis_inputs", "all_scores.txt")
        self.assertEqual(count_matrices_in_file(scores_path, k=3), 2)

        # Test count_lines_in_file
        mappings_path = os.path.join(os.path.dirname(self.run1_dir), "run_A_sbj-03_trl-02", "analysis_inputs", "all_mappings.txt")
        self.assertEqual(count_lines_in_file(mappings_path, skip_header=True), 2)
        self.assertEqual(count_lines_in_file("non_existent_file.txt"), 0)

    def test_depth_0_finds_only_top_level(self):
        """Tests that --depth 0 (default) finds the run in the target directory only."""
        cli_args = ['verify_pipeline_completeness.py', self.test_dir, '--depth', '0']
        
        with patch('logging.info') as mock_log_info, patch.object(sys, 'argv', cli_args):
            verify_main()
            
        output = "\n".join([call.args[0] for call in mock_log_info.call_args_list])
        
        self.assertIn("(Depth: 0)", output)
        self.assertIn("run_A_sbj-03_trl-02", output)
        self.assertNotIn("run_B_sbj-02_trl-03", output)
        self.assertNotIn("run_C_sbj-04_trl-01", output)
        self.assertIn("Overall Pipeline Completeness: 100.00%", output) # 2/2

    def test_depth_1_finds_nested_runs(self):
        """Tests that --depth 1 finds runs at the top level and one level down."""
        cli_args = ['verify_pipeline_completeness.py', self.test_dir, '--depth', '1']
        
        with patch('logging.info') as mock_log_info, patch.object(sys, 'argv', cli_args):
            verify_main()
            
        output = "\n".join([call.args[0] for call in mock_log_info.call_args_list])

        self.assertIn("(Depth: 1)", output)
        self.assertIn("run_A_sbj-03_trl-02", output)
        self.assertIn(os.path.join("level1", "run_B_sbj-02_trl-03"), output)
        self.assertNotIn("run_C_sbj-04_trl-01", output)
        self.assertIn("Overall Pipeline Completeness: 80.00%", output) # (2+2)/(2+3) = 4/5

    def test_depth_minus_1_finds_all_recursively(self):
        """Tests that --depth -1 finds all runs recursively."""
        cli_args = ['verify_pipeline_completeness.py', self.test_dir, '--depth', '-1']
        
        with patch('logging.info') as mock_log_info, patch.object(sys, 'argv', cli_args):
            verify_main()
            
        output = "\n".join([call.args[0] for call in mock_log_info.call_args_list])

        self.assertIn("(Depth: -1)", output)
        self.assertIn("run_A_sbj-03_trl-02", output)
        self.assertIn(os.path.join("level1", "run_B_sbj-02_trl-03"), output)
        self.assertIn(os.path.join("level1", "level2", "run_C_sbj-04_trl-01"), output)
        self.assertIn("Overall Pipeline Completeness: 83.33%", output) # (2+2+1)/(2+3+1) = 5/6

if __name__ == '__main__':
    unittest.main()