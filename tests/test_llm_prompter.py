import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import sys
import json
import subprocess
import shutil
import tempfile
import requests
from pathlib import Path
import importlib

# --- CORRECT PATH DEFINITIONS USING PATHLIB ---
# This ensures all path variables are Path objects, solving the TypeError.
PROJECT_ROOT_TEST = Path(__file__).resolve().parent.parent
SRC_DIR_TEST = PROJECT_ROOT_TEST / "src"
LLM_PROMPTER_SCRIPT_PATH = SRC_DIR_TEST / "llm_prompter.py"

# Modify sys.path using the new Path objects (converted to strings)
if str(SRC_DIR_TEST) not in sys.path:
    sys.path.insert(0, str(SRC_DIR_TEST))
if str(PROJECT_ROOT_TEST) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_TEST))

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
        # Create a single temporary directory for all test I/O files.
        self.test_run_dir_obj = tempfile.TemporaryDirectory(prefix="test_llm_prompter_run_")
        self.test_run_dir = self.test_run_dir_obj.name

        # Define absolute paths for I/O files within the temporary directory.
        self.input_query_file = os.path.join(self.test_run_dir, "test_query_input.txt")
        self.output_response_file = os.path.join(self.test_run_dir, "test_response_output.txt")
        self.output_error_file = os.path.join(self.test_run_dir, "test_error_output.txt")
        
        # We will not create a mock config.ini or .env file in setUp.
        # The subprocess will run from the actual project root and use the real
        # config.ini for its structure, which is more robust.
        # The mock API key for tests will be provided via the environment.

    def tearDown(self):
        self.test_run_dir_obj.cleanup()

    def create_test_input_query_file(self, content="Default test query content."):
        with open(self.input_query_file, "w", encoding='utf-8') as f:
            f.write(content)

    def run_llm_prompter_subprocess(self, query_id, cli_extra_args=None, custom_env=None, cwd_override=None):
        """
        Helper to run llm_prompter.py as a subprocess.
        Allows overriding the environment and working directory for isolation.
        """
        coveragerc_path = PROJECT_ROOT_TEST / ".coveragerc"
        script_to_run_path = LLM_PROMPTER_SCRIPT_PATH

        base_cmd = [
            sys.executable, "-m", "coverage", "run",
            "--rcfile", str(coveragerc_path),
            "--parallel-mode",
            str(script_to_run_path),
            query_id,
            "--input_query_file", self.input_query_file,
            "--output_response_file", self.output_response_file,
            "--output_error_file", self.output_error_file,
        ]

        if cli_extra_args:
            base_cmd.extend(cli_extra_args)

        env_for_subprocess = custom_env if custom_env is not None else os.environ.copy()
        cwd_for_subprocess = cwd_override if cwd_override is not None else str(PROJECT_ROOT_TEST)

        return subprocess.run(
            base_cmd,
            capture_output=True,
            text=True,
            cwd=cwd_for_subprocess,
            encoding='utf-8',
            env=env_for_subprocess,
        )

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

    def test_llm_prompter_input_file_not_found(self):
        if os.path.exists(self.input_query_file):
            os.remove(self.input_query_file)

        query_id = "test_nofile_003"
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

    def test_llm_prompter_api_timeout_scenario(self):
        """Test that the script correctly handles a mocked network timeout."""
        query_content = "This query will simulate a network timeout."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_timeout_004"

        extra_args = ["--test_mock_api_outcome", "api_timeout"]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (API Timeout):\n", result.stdout)
        print("LLM Prompter STDERR (API Timeout):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero on timeout.")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file should be created on timeout.")
        self.assertFalse(os.path.exists(self.output_response_file))
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            error_content = f.read()
            self.assertIn("API call timed out", error_content)
        self.assertIn("API Timeout Error", result.stdout)

    def test_llm_prompter_interactive_mode(self):
        """Test the script's behavior when run in standalone interactive test mode."""
        # For this test, we must run from the src directory. We create a temporary .env there.
        temp_src_dotenv = SRC_DIR_TEST / ".env"
        with open(temp_src_dotenv, "w") as f:
            f.write(MOCK_DOTENV_CONTENT)

        # Define paths for interactive files, which are created relative to the script's location.
        interactive_query_file = SRC_DIR_TEST / "interactive_test_query.txt"
        interactive_response_file = SRC_DIR_TEST / "interactive_test_response.txt"
        interactive_error_file = SRC_DIR_TEST / "interactive_test_error.txt"
        interactive_json_file = SRC_DIR_TEST / "interactive_test_response_full.json"

        # Clean up default interactive files if they exist from a prior run.
        for f_path in [interactive_query_file, interactive_response_file, interactive_error_file, interactive_json_file]:
            if os.path.exists(f_path):
                os.remove(f_path)
        
        cmd = [
            sys.executable,
            str(LLM_PROMPTER_SCRIPT_PATH),
            "--interactive_test_mode",
            "--test_mock_api_outcome", "success",
            "--test_mock_api_content", "Mock content from interactive mode for test."
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(SRC_DIR_TEST), # Must run from src directory
            encoding='utf-8',
        )

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Interactive Mode):\n", result.stdout)
        print("LLM Prompter STDERR (Interactive Mode):\n", result.stderr)

        self.assertEqual(result.returncode, 0, f"Script should exit 0 in interactive mode success. STDERR: {result.stderr}")
        self.assertTrue(os.path.exists(interactive_query_file), "Interactive query file not created.")
        self.assertTrue(os.path.exists(interactive_response_file), "Interactive response file not created.")
        self.assertFalse(os.path.exists(interactive_error_file), "Interactive error file should not be created on success.")
        
        with open(interactive_response_file, "r", encoding='utf-8') as f:
            self.assertEqual(f.read(), "Mock content from interactive mode for test.")
        
        self.assertIn("Running in standalone interactive test mode", result.stdout)
        self.assertIn("Created sample query file", result.stdout)

        # Clean up files created by this specific interactive mode test run
        for f_path in [interactive_query_file, interactive_response_file, interactive_error_file, interactive_json_file, temp_src_dotenv]:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_llm_prompter_empty_input_file(self):
        # Create an empty input file
        self.create_test_input_query_file(content="")
        query_id = "test_emptyfile_005"

        result = self.run_llm_prompter_subprocess(query_id)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Empty Input File):\n", result.stdout)
        print("LLM Prompter STDERR (Empty Input File):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero for empty input file.")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file should be created.")
        self.assertFalse(os.path.exists(self.output_response_file), "Response file should not be created.")
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            self.assertIn("Query file was empty.", f.read())
        self.assertIn("Query file", result.stdout)

    def test_llm_prompter_generic_exception_scenario(self):
        """Test that the script handles a generic unexpected exception."""
        query_content = "This query will cause a generic exception."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_generic_exception_007"

        extra_args = ["--test_mock_api_outcome", "generic_exception_in_api"]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Generic Exception):\n", result.stdout)
        print("LLM Prompter STDERR (Generic Exception):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero for generic exception.")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file should be created.")
        self.assertFalse(os.path.exists(self.output_response_file), "Response file should not be created.")
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            error_content = f.read()
            self.assertIn("Unhandled error in llm_prompter.py", error_content)
            self.assertIn("ValueError: Simulated generic error in API worker", error_content)
        self.assertIn("Unhandled error in llm_prompter.py", result.stdout)

    def test_llm_prompter_keyboard_interrupt_scenario(self):
        """Test that the script handles a KeyboardInterrupt gracefully."""
        query_content = "This query will be interrupted."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_keyboard_interrupt_008"

        extra_args = ["--test_mock_api_outcome", "keyboard_interrupt"]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Keyboard Interrupt):\n", result.stdout)
        print("LLM Prompter STDERR (Keyboard Interrupt):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero on KeyboardInterrupt.")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file should be created.")
        self.assertFalse(os.path.exists(self.output_response_file), "Response file should not be created.")
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            self.assertIn("Processing interrupted by user (Ctrl+C).", f.read())
        self.assertIn("Interrupted by user (Ctrl+C)", result.stdout)

    def test_llm_prompter_api_http_401_scenario(self):
        """Test that the script handles a mocked HTTP 401 Unauthorized error."""
        query_content = "This query will simulate a 401 error."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_http_401_009"

        extra_args = ["--test_mock_api_outcome", "api_http_401"]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (HTTP 401):\n", result.stdout)
        print("LLM Prompter STDERR (HTTP 401):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero on HTTP 401 error.")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file should be created.")
        self.assertFalse(os.path.exists(self.output_response_file), "Response file should not be created.")
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            error_content = f.read()
            self.assertIn("API call failed with HTTP error for query", error_content)
            self.assertIn("Simulated 401 Unauthorized", error_content) # Check for the mock exception's message
        self.assertIn("LLM Prompter: HTTP Error: Simulated 401 Unauthorized", result.stdout)

    def test_llm_prompter_api_http_500_scenario(self):
        """Test that the script handles a mocked HTTP 500 Server Error."""
        query_content = "This query will simulate a 500 error."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_http_500_010"

        extra_args = ["--test_mock_api_outcome", "api_http_500"]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (HTTP 500):\n", result.stdout)
        print("LLM Prompter STDERR (HTTP 500):\n", result.stderr)

        self.assertNotEqual(result.returncode, 0, "Script should exit non-zero on HTTP 500 error.")
        self.assertTrue(os.path.exists(self.output_error_file), "Error file should be created.")
        self.assertFalse(os.path.exists(self.output_response_file), "Response file should not be created.")
        with open(self.output_error_file, "r", encoding='utf-8') as f:
            error_content = f.read()
            self.assertIn("API call failed with HTTP error for query", error_content)
            self.assertIn("Simulated 500 Server Error", error_content) # Check for the mock exception's message
        self.assertIn("LLM Prompter: HTTP Error: Simulated 500 Server Error", result.stdout) # Check for the full log message

    def test_llm_prompter_empty_content_response(self):
        """Test that the script correctly handles an LLM response with empty or whitespace content."""
        query_content = "Test for empty content response."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_empty_content_011"

        mock_response_content = ""
        extra_args = [
            "--test_mock_api_outcome", "success",
            "--test_mock_api_content", mock_response_content
        ]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)

        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Empty Content):\n", result.stdout)
        print("LLM Prompter STDERR (Empty Content):\n", result.stderr)

        self.assertEqual(result.returncode, 0, "Script should exit 0 even for empty content, as it's a valid response.")
        self.assertTrue(os.path.exists(self.output_response_file), "Response file should be created.")
        with open(self.output_response_file, "r", encoding='utf-8') as f:
            self.assertEqual(f.read(), mock_response_content)
        self.assertFalse(os.path.exists(self.output_error_file), "Error file should not be created on empty content.")
        self.assertIn("Response content is empty or whitespace.", result.stdout)

    def test_llm_prompter_quiet_mode_success(self):
        """Test the script in quiet mode for a successful scenario, verifying spinner suppression."""
        query_content = "This query runs in quiet mode."
        self.create_test_input_query_file(content=query_content)
        query_id = "test_quiet_012"
        
        mock_response_content_for_test = "Mocked quiet success."
        extra_args = [
            "--test_mock_api_outcome", "success",
            "--test_mock_api_content", mock_response_content_for_test,
            "--quiet"
        ]
        result = self.run_llm_prompter_subprocess(query_id, extra_args)
        
        print(f"\n--- Test: {self.id()} ---")
        print("LLM Prompter STDOUT (Quiet Mode):\n", result.stdout)
        print("LLM Prompter STDERR (Quiet Mode):\n", result.stderr)

        self.assertEqual(result.returncode, 0, f"Script should exit 0 in quiet mode success. STDERR: {result.stderr}")
        self.assertTrue(os.path.exists(self.output_response_file), "Response file was not created.")
        with open(self.output_response_file, "r", encoding='utf-8') as f:
            self.assertEqual(f.read(), mock_response_content_for_test)
        self.assertFalse(os.path.exists(self.output_error_file), "Error file should not exist on success in quiet mode.")

        self.assertNotIn("Waiting for LLM response", result.stderr)
        self.assertNotIn("LLM Prompter: OPENROUTER_API_KEY loaded", result.stdout)
        self.assertIn("RUNNING IN API MOCK MODE", result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)