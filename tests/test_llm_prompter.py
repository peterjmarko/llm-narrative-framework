import unittest
from unittest.mock import patch, mock_open, MagicMock # mock_open is not used here, but good to have if needed
import os
import sys
import json
import subprocess 
import shutil
import tempfile   

# Adjust path to make llm_prompter.py and config_loader.py importable
# This assumes test_llm_prompter.py is in tests/ and llm_prompter.py/config_loader.py are in ../src/
SCRIPT_DIR_TEST = os.path.dirname(os.path.abspath(__file__)) 
PROJECT_ROOT_TEST = os.path.abspath(os.path.join(SCRIPT_DIR_TEST, '..')) 
SRC_DIR_TEST = os.path.join(PROJECT_ROOT_TEST, 'src')

if SRC_DIR_TEST not in sys.path:
    sys.path.insert(0, SRC_DIR_TEST)
if PROJECT_ROOT_TEST not in sys.path: # If config_loader was at project_root
    sys.path.insert(0, PROJECT_ROOT_TEST)


LLM_PROMPTER_SCRIPT_PATH = os.path.join(SRC_DIR_TEST, "llm_prompter.py")

# Mock config.ini content for llm_prompter.py to load
MOCK_CONFIG_INI_CONTENT = """
[General]
default_log_level = DEBUG
base_output_dir = ./output
responses_subdir = session_responses_test_dir

[LLM]
model_name = mock-model/from-config-for-prompter
api_endpoint = https://this.is.a.mock.endpoint.com/api/v1
api_timeout_seconds = 10
referer_header = http://prompter-config-referer
max_tokens = 80
temperature = 0.6

[Filenames]
# Ensure these keys exist if get_config_value in llm_prompter tries to read them
personalities_src = personalities_test.txt
base_query_src = base_query_test.txt
temp_subset_personalities = temp_subset_test.txt
used_indices_log = used_indices_test.log
aggregated_mappings_in_queries_dir = mappings_agg_test.txt
all_scores_for_analysis = scores_final_test.txt
all_mappings_for_analysis = mappings_final_test.txt
qgen_temp_prefix = ""
"""

MOCK_DOTENV_CONTENT = "OPENROUTER_API_KEY=env_mock_api_key_for_prompter_tests\n"

class TestLLMPrompterEndToEnd(unittest.TestCase):
    
    def setUp(self):
        self.test_run_dir_obj = tempfile.TemporaryDirectory(prefix="test_llm_prompter_run_")
        self.test_run_dir = self.test_run_dir_obj.name 
        
        self.config_file = os.path.join(self.test_run_dir, "config.ini")
        self.dotenv_file = os.path.join(self.test_run_dir, ".env")
        self.input_query_file = os.path.join(self.test_run_dir, "test_query_input.txt")
        self.output_response_file = os.path.join(self.test_run_dir, "test_response_output.txt")
        self.output_error_file = os.path.join(self.test_run_dir, "test_error_output.txt")
        # Define the path where the test expects the log file to be created.
        self.api_times_log_file = os.path.join(self.test_run_dir, "api_times_test.log")
        self.api_times_log_expected_base_dir = os.path.join(self.test_run_dir, "output")
        self.api_times_log_expected_responses_subdir = os.path.join(self.api_times_log_expected_base_dir, "session_responses_test_dir")
        os.makedirs(self.api_times_log_expected_responses_subdir, exist_ok=True)
        self.api_times_log_file = os.path.join(self.api_times_log_expected_responses_subdir, "api_times.log")

        with open(self.config_file, "w", encoding='utf-8') as f:
            f.write(MOCK_CONFIG_INI_CONTENT)
        with open(self.dotenv_file, "w", encoding='utf-8') as f:
            f.write(MOCK_DOTENV_CONTENT)
        
        config_loader_src_path = os.path.join(SRC_DIR_TEST, "config_loader.py")
        if os.path.exists(config_loader_src_path):
            shutil.copy2(config_loader_src_path, self.test_run_dir)
        else:
            self.fail(f"Critical test setup error: config_loader.py not found at {config_loader_src_path}")

    def tearDown(self):
        self.test_run_dir_obj.cleanup()

    def create_test_input_query_file(self, content="Default test query content."):
        with open(self.input_query_file, "w", encoding='utf-8') as f:
            f.write(content)

    def run_llm_prompter_subprocess(self, query_id, cli_extra_args=None):
        """Helper to run llm_prompter.py as a subprocess."""
        base_cmd = [
            sys.executable, LLM_PROMPTER_SCRIPT_PATH,
            query_id,
            "--input_query_file", self.input_query_file,
            "--output_response_file", self.output_response_file,
            "--output_error_file", self.output_error_file,
        ]
        if cli_extra_args:
            base_cmd.extend(cli_extra_args)
        
        # The CWD for the subprocess is self.test_run_dir.
        # llm_prompter.py will find its copied config_loader.py, and mock config.ini/.env there.
        return subprocess.run(base_cmd, capture_output=True, text=True, cwd=self.test_run_dir, encoding='utf-8')

    def test_llm_prompter_success_scenario(self):
        query_content = "This is a query for the successful scenario."
        self.create_test_input_query_file(content=query_content)
        mock_response_content_for_test = "Mocked success via CLI flag."
        query_id = "test_success_001"
        
        extra_args = [
            "--test_mock_api_outcome", "success",
            "--test_mock_api_content", mock_response_content_for_test,
            "-vv"
        ]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)
        
        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT:\n", result.stdout)
        print("LLM Prompter STDERR:\n", result.stderr)

        self.assertEqual(result.returncode, 0, f"Script should exit 0. STDERR: {result.stderr}")
        self.assertTrue(os.path.exists(self.output_response_file), "Response file was not created.")
        with open(self.output_response_file, "r", encoding='utf-8') as f:
            self.assertEqual(f.read(), mock_response_content_for_test)
        self.assertFalse(os.path.exists(self.output_error_file), "Error file should not exist on success.")
        
        # Prompter is no longer responsible for this log file.
        self.assertFalse(os.path.exists(self.api_times_log_file))

    def test_llm_prompter_api_failure_scenario(self):
        query_content = "This query will simulate an API failure (mocked)."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_fail_002"

        extra_args = ["--test_mock_api_outcome", "api_returns_none"]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (API Failure):\n", result.stdout)
        print("LLM Prompter STDERR (API Failure):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, f"Script should exit non-zero. STDERR: {result.stderr}")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file was not created on API failure.")
        self.assertFalse(os.path.exists(self.output_response_file))
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            self.assertIn("LLM API call returned None or failed", f.read())
        
        # Prompter is no longer responsible for this log file.
        self.assertFalse(os.path.exists(self.api_times_log_file))


    def test_llm_prompter_input_file_not_found(self):
        # Ensure the input file does NOT exist for this test
        if os.path.exists(self.input_query_file):
            os.remove(self.input_query_file)

        query_id = "test_nofile_003"
        # No extra args needed, it will try to read default which doesn't exist
        result = self.run_llm_prompter_subprocess(query_id) 

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Input File Not Found):\n", result.stdout)
        print("LLM Prompter STDERR (Input File Not Found):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero if input file not found.")
        self.assertTrue(os.path.exists(self.output_error_file))
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            error_content = f.read()
            self.assertIn("Input query file not found", error_content)
            self.assertIn(os.path.basename(self.input_query_file), error_content)

if __name__ == '__main__':
    # This allows running tests from this file directly using: python tests/test_llm_prompter.py
    # For more complex setups, use a test runner like 'pytest' or 'python -m unittest discover tests'
    unittest.main(verbosity=2)