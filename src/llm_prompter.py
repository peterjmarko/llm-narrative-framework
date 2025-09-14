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
# Filename: src/llm_prompter.py

"""
LLM Prompter Worker for a Single API Call.

This script is the dedicated worker responsible for sending a single query to the
configured LLM provider. It is designed to be called as a subprocess by the
`run_llm_sessions.py` orchestrator.

Key Features:
-   **Threaded API Call**: Makes the blocking network request in a separate
    thread, allowing the main thread to display a comprehensive status spinner
    on `stderr`. This spinner shows the individual API call timer as well as
    the overall progress for the entire replication batch (Trial X/Y, Elapsed, ETR).
-   **Robust Output Contract**: Communicates results back to the orchestrator via
    a clear contract:
    - On Success: The full, raw JSON response is written to `stdout` between
      delimiters, while the extracted text content is saved to a file.
    - On Failure: A descriptive error message is saved to a file.
-   **Comprehensive Error Handling**: Catches and logs specific network errors
    (timeouts, HTTP errors) and user interruptions.
-   **Designed for Testability**: Includes `--test_mock_api_outcome` hooks to
    allow for simulating various API responses without making live network calls.
"""

# === Start of src/llm_prompter.py ===

import argparse
import os
import sys
import time
import logging
import json
import requests
import threading
import itertools
from dotenv import load_dotenv
from typing import Optional, Dict, List, Tuple, Any

# --- Import from config_loader ---
# Define a fallback class and function in case the real config_loader is not found.
class DummyConfig:
    def has_section(self, section): return False
    def has_option(self, section, key): return False
    def get(self, section, key, fallback=None): return fallback
    def getint(self, section, key, fallback=None): return fallback
    def getfloat(self, section, key, fallback=None): return fallback
    def getboolean(self, section, key, fallback=None): return fallback

def get_config_value_fallback(cfg, section, key, fallback=None, value_type=str):
    return fallback

try:
    # First attempt to import from the standard path
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError:
    # If the first attempt fails, try to fix sys.path and re-import.
    current_script_dir_lprompter = os.path.dirname(os.path.abspath(__file__))
    project_root_for_loader_lprompter = os.path.dirname(current_script_dir_lprompter)
    if current_script_dir_lprompter not in sys.path:
        sys.path.insert(0, current_script_dir_lprompter)
    if project_root_for_loader_lprompter not in sys.path:
        sys.path.insert(0, project_root_for_loader_lprompter)

    try:
        # Second attempt after path correction.
        from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
    except ImportError as e_lprompter:
        # If it still fails, use the fallback configuration.
        APP_CONFIG = DummyConfig()
        get_config_value = get_config_value_fallback
        PROJECT_ROOT = os.getcwd() # Best guess
        print(f"WARNING: llm_prompter.py - Could not import from config_loader.py. Error: {e_lprompter}. "
              "Using minimal fallbacks. This might affect functionality if config is essential.")


# --- Default filenames for standalone interactive test mode ---
INTERACTIVE_TEST_QUERY_FILE = "interactive_test_query.txt"
INTERACTIVE_TEST_RESPONSE_FILE = "interactive_test_response.txt"
INTERACTIVE_TEST_ERROR_FILE = "interactive_test_error.txt"
DEFAULT_QUERY_IDENTIFIER_INTERACTIVE = "interactive_test"

# --- Spinner constants ---
SPINNER_FRAMES = ['-', '\\', '|', '/']
SPINNER_INTERVAL = 0.1 
CLEANUP_DELAY = 0.1

# --- Global CONFIG object & Logging Setup ---
DEFAULT_LOG_LEVEL_STR_PROMPTER = get_config_value(APP_CONFIG, 'General', 'default_log_level', fallback='INFO')
numeric_log_level_prompter = getattr(logging, DEFAULT_LOG_LEVEL_STR_PROMPTER.upper(), logging.INFO)
logging.basicConfig(level=numeric_log_level_prompter,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    stream=sys.stdout) # Send logs to stdout, leaving stderr for the spinner
DOTENV_PATH = ".env"

# Force stdout to use UTF-8 encoding to prevent UnicodeEncodeError on Windows when piping JSON
sys.stdout.reconfigure(encoding='utf-8')

def format_seconds_to_time_str(seconds: float) -> str:
    """Formats seconds into [HH:]MM:SS string, showing hours only if non-zero."""
    if seconds < 0: return "00:00"
    total_seconds = round(seconds)
    hours, rem = total_seconds // 3600, total_seconds % 3600
    minutes, secs = rem // 60, rem % 60
    return f"{int(hours):02d}:{int(minutes):02d}:{int(secs):02d}" if hours > 0 else f"{int(minutes):02d}:{int(secs):02d}"

# --- Helper: Spinner Animation ---
def animate_spinner(stop_event, query_identifier: str):
    start_time = time.time()
    for c in itertools.cycle(SPINNER_FRAMES):
        if stop_event.is_set(): break
        api_elapsed = time.time() - start_time
        
        # Write spinner to stderr to keep stdout clean for data
        status_line = f'\r{c} Query {query_identifier}: LLM Thinking... [{api_elapsed:.1f}s]'
        sys.stderr.write(status_line)
        sys.stderr.flush()
        time.sleep(SPINNER_INTERVAL)
    # Clear the spinner line from stderr
    sys.stderr.write('\r' + ' ' * 120 + '\r')
    sys.stderr.flush()

# --- Helper: LLM API Call ---
def call_openrouter_api(query_text: str, model_name: str, api_key: str, api_endpoint: str,
                        referer: str, timeout_seconds: int, query_identifier: str,
                        max_tokens: Optional[int] = None, temperature: Optional[float] = None,
                        quiet: bool = False
                       ) -> Tuple[Optional[Dict[str, Any]], float]:

    result_container = {"data": None, "duration": 0.0, "exception": None}

    def _api_worker():
        """This function runs in a separate thread to make the blocking API call."""
        api_start_time = time.time()
        try:
            messages = [{"role": "user", "content": query_text}]
            payload: Dict[str, Any] = {"model": model_name, "messages": messages}
            if max_tokens is not None: payload["max_tokens"] = max_tokens
            if temperature is not None: payload["temperature"] = temperature

            headers = {"Authorization": f"Bearer {api_key}", "HTTP-Referer": referer, "Content-Type": "application/json"}
            logging.debug(f"API Request Payload for Query {query_identifier}: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            logging.info(f"  Query {query_identifier}: Calling API with model='{model_name}', "
                         f"max_tokens={payload.get('max_tokens')}, temperature={payload.get('temperature')}")

            response = requests.post(api_endpoint, headers=headers, json=payload, timeout=timeout_seconds)
            response.raise_for_status()
            
            # Attempt to parse JSON with robust error handling for malformed responses
            try:
                result_container["data"] = response.json()
                logging.info(f"  Query {query_identifier}: API call successful.")
            except requests.exceptions.JSONDecodeError as json_exc:
                error_details = (f"Failed to decode JSON from LLM response. Error: {json_exc}. "
                                 f"Raw response text received:\n---\n{response.text.strip()}\n---")
                # Store the CLEAN error message and set status, do not store an exception
                result_container["error"] = error_details
                result_container["status"] = "error"

        except Exception as e:
            # Capture any other exception to be re-raised in the main thread
            result_container["exception"] = e
        finally:
            # Always record the duration
            result_container["duration"] = time.time() - api_start_time

    # --- Threading setup ---
    stop_event = threading.Event()
    spinner_args = (stop_event, query_identifier)
    spinner_thread = threading.Thread(target=animate_spinner, args=spinner_args, daemon=True)
    api_thread = threading.Thread(target=_api_worker, daemon=True)

    # Start threads
    if not quiet:
        spinner_thread.start()
    api_thread.start()

    # --- Interruptible wait loop ---
    # The main thread now waits in this loop, which can be interrupted by Ctrl+C.
    while api_thread.is_alive():
        api_thread.join(timeout=0.1)

    # --- Cleanup and return results ---
    if not quiet:
        stop_event.set()
        if spinner_thread.is_alive():
            spinner_thread.join()
        time.sleep(CLEANUP_DELAY)

    # Handle exceptions that occurred in the worker thread
    if result_container["exception"]:
        # Re-raise exceptions for critical errors like timeouts or HTTP failures
        raise result_container["exception"]
    
    if result_container.get("status") == "error":
        # For handled errors like JSONDecode, the error message is in the 'error' key
        # Return it so the main function can write it to the error file
        return result_container["error"], result_container["duration"]

    # Return successful data
    return result_container["data"], result_container["duration"]

def main():
    parser = argparse.ArgumentParser(description="Worker/Standalone Test: Sends a single query to LLM.")
    parser.add_argument("query_identifier", nargs='?', default=DEFAULT_QUERY_IDENTIFIER_INTERACTIVE,
                        help=f"Identifier for this query (e.g., '001'). Default for standalone: '{DEFAULT_QUERY_IDENTIFIER_INTERACTIVE}'.")
    parser.add_argument("--input_query_file", default=None,
                        help=f"Path to the input query file. Default for standalone use only: '{INTERACTIVE_TEST_QUERY_FILE}'.")
    parser.add_argument("--output_response_file", default=None,
                        help=f"Path for the output response file. Default for standalone use only: '{INTERACTIVE_TEST_RESPONSE_FILE}'.")
    parser.add_argument("--output_error_file", default=None,
                        help=f"Path for the output error file. Default for standalone use only: '{INTERACTIVE_TEST_ERROR_FILE}'.")
    parser.add_argument("--output_json_file", default=None,
                        help="Path for the raw JSON output file. If not provided, no JSON file will be saved.")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity level (-v for INFO, -vv for DEBUG).")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress non-essential info logs and the console spinner.")
    parser.add_argument("--interactive_test_mode", action="store_true",
                        help="Force use of default filenames and create sample query for interactive testing.")
    # Test hook arguments
    parser.add_argument("--test_mock_api_outcome", type=str, default=None,
                        choices=['success', 'api_returns_none', 'api_timeout', 'api_http_401', 'api_http_500', 'keyboard_interrupt', 'generic_exception_in_api'],
                        help="FOR TESTING ONLY: Simulate API outcome instead of making a real call.")
    parser.add_argument("--test_mock_api_content", type=str, default="Default mock content from prompter.",
                        help="FOR TESTING ONLY: String content for a 'success' mock API response.")
    parser.add_argument("--config_path", default=None,
                        help="Path to a specific config.ini.archived file for this run.")
    args = parser.parse_args()

    # --- Adjust Log Level FIRST ---
    if args.quiet:
        log_level_str = "WARNING"
    elif args.verbose >= 2:
        log_level_str = "DEBUG"
    elif args.verbose == 1:
        log_level_str = "INFO"
    else:
        log_level_str = DEFAULT_LOG_LEVEL_STR_PROMPTER
    
    numeric_log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logging.basicConfig(level=numeric_log_level,
                        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        force=True,
                        stream=sys.stdout) # Send logs to stdout, leaving stderr for the spinner

    # --- Now continue with the rest of the script ---
    script_dir_worker = os.path.dirname(os.path.abspath(__file__))

    is_worker_provided_paths = (args.input_query_file is not None and
                                args.output_response_file is not None and
                                args.output_error_file is not None)
    run_as_interactive_test = args.interactive_test_mode or not is_worker_provided_paths

    if run_as_interactive_test:
        logging.info("Running in standalone interactive test mode with default file names.")
        if is_worker_provided_paths and args.interactive_test_mode:
            logging.warning("--interactive_test_mode flag is set, but specific file paths were also provided. Default interactive filenames will be used.")

        input_query_file_abs = os.path.join(script_dir_worker, INTERACTIVE_TEST_QUERY_FILE)
        output_response_file_abs = os.path.join(script_dir_worker, INTERACTIVE_TEST_RESPONSE_FILE)
        output_error_file_abs = os.path.join(script_dir_worker, INTERACTIVE_TEST_ERROR_FILE)

        debug_json_filename_default = os.path.splitext(output_response_file_abs)[0] + "_full.json"
        files_to_clear_interactive = [output_response_file_abs, output_error_file_abs, debug_json_filename_default]
        for f_path in files_to_clear_interactive:
            if os.path.exists(f_path):
                try:
                    os.remove(f_path)
                    logging.info(f"  Interactive mode: Cleared old file: {os.path.basename(f_path)}")
                except OSError as e:
                    logging.warning(f"  Interactive mode: Could not clear old file {os.path.basename(f_path)}: {e}")

    else: # Worker mode (paths provided)
        logging.info("Running in worker mode (paths provided by orchestrator or user).")
        input_query_file_abs = os.path.abspath(args.input_query_file)
        output_response_file_abs = os.path.abspath(args.output_response_file)
        output_error_file_abs = os.path.abspath(args.output_error_file)
    
    logging.info(f"LLM Prompter for ID '{args.query_identifier}' started. Log level: {log_level_str}")
    logging.info(f"  Input query file: {input_query_file_abs}")
    logging.info(f"  Output response file: {output_response_file_abs}")
    logging.info(f"  Output error file: {output_error_file_abs}")

    # Load .env
    dotenv_paths_to_try = [
        os.path.join(script_dir_worker, DOTENV_PATH), # Alongside script
        os.path.join(os.getcwd(), DOTENV_PATH)        # In CWD
    ]
    if 'PROJECT_ROOT' in globals() and PROJECT_ROOT:
        dotenv_paths_to_try.insert(0, os.path.join(PROJECT_ROOT, DOTENV_PATH))

    env_loaded_path = None
    for d_path in dotenv_paths_to_try:
        if os.path.exists(d_path) and load_dotenv(d_path):
            env_loaded_path = d_path
            break
            
    # In interactive mode, create the sample query *before* checking for the API key.
    if run_as_interactive_test and not os.path.exists(input_query_file_abs):
        try:
            with open(input_query_file_abs, 'w', encoding='utf-8') as f_iq:
                f_iq.write("This is an interactive test query.\nWhat is the capital of the Moon?")
            logging.info(f"Created sample query file: {input_query_file_abs}")
        except IOError as e: logging.error(f"Error creating sample query file {input_query_file_abs}: {e}"); sys.exit(1)

    if env_loaded_path:
        logging.info(f"LLM Prompter: Loaded .env from: {env_loaded_path}")
    else:
        logging.warning("LLM Prompter: .env file not found in typical locations. API key must be in environment.")

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logging.error("LLM Prompter: OPENROUTER_API_KEY not found.")
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err: f_err.write("OPENROUTER_API_KEY not set.")
        sys.exit(1)
    logging.info("LLM Prompter: OPENROUTER_API_KEY loaded.")

    # If a specific config path is given, load it. Otherwise, use the global APP_CONFIG.
    run_specific_config = APP_CONFIG
    if args.config_path:
        if not os.path.exists(args.config_path):
            logging.error(f"FATAL: Provided config path does not exist: {args.config_path}")
            sys.exit(1)
        # Use a new ConfigParser instance to load the run-specific config
        from configparser import ConfigParser
        run_specific_config = ConfigParser()
        run_specific_config.read(args.config_path)
        logging.info(f"Loaded run-specific configuration from: {args.config_path}")

    # If a specific config path is given, load it. Otherwise, use the global APP_CONFIG.
    run_specific_config = APP_CONFIG
    if args.config_path:
        if not os.path.exists(args.config_path):
            logging.error(f"FATAL: Provided config path does not exist: {args.config_path}")
            sys.exit(1)
        # Use a new ConfigParser instance to load the run-specific config
        from configparser import ConfigParser
        run_specific_config = ConfigParser()
        run_specific_config.read(args.config_path)
        logging.info(f"Loaded run-specific configuration from: {args.config_path}")

    # Get LLM parameters from the appropriate config
    model_name_cfg = get_config_value(run_specific_config, 'LLM', 'model_name', fallback_key='model', fallback="google/gemini-1.5-pro-latest")
    api_endpoint_cfg = get_config_value(run_specific_config, 'LLM', 'api_endpoint', fallback='https://openrouter.ai/api/v1/chat/completions')
    api_timeout_cfg = get_config_value(run_specific_config, 'LLM', 'api_timeout_seconds', fallback=120, value_type=int)
    referer_header_cfg = get_config_value(run_specific_config, 'LLM', 'referer_header', fallback="http://localhost:3000")
    max_tokens_cfg = get_config_value(run_specific_config, 'LLM', 'max_tokens', fallback=1000, value_type=int)
    temperature_cfg = get_config_value(run_specific_config, 'LLM', 'temperature', fallback=None, value_type=float)

    try:
        if not os.path.exists(input_query_file_abs):
            raise FileNotFoundError(f"Input query file not found: {input_query_file_abs}")

        with open(input_query_file_abs, 'r', encoding='utf-8') as f_query:
            query_text_content = f_query.read()

        if not query_text_content.strip():
            logging.warning(f"  Query file '{os.path.basename(input_query_file_abs)}' is empty.")
            with open(output_error_file_abs, 'w', encoding='utf-8') as f_err: f_err.write("Query file was empty.")
            sys.exit(1)

        api_result = None
        # ---- MOCKING BLOCK FOR TESTING: Simulates `call_openrouter_api` outcomes ----
        if args.test_mock_api_outcome:
            logging.warning(f"!!! RUNNING IN API MOCK MODE: {args.test_mock_api_outcome} FOR QUERY {args.query_identifier} !!!")
            logging.info(f"  MOCK API: Outcome for query {args.query_identifier} set to '{args.test_mock_api_outcome}'.")
            
            if args.test_mock_api_outcome == 'success':
                api_result = {"choices": [{"message": {"content": args.test_mock_api_content}}]}
            elif args.test_mock_api_outcome == 'api_returns_none':
                api_result = None # This will trigger the generic "None" failure path below
            # For simulating exceptions, we raise them here so the main `except` blocks can catch them
            elif args.test_mock_api_outcome == 'api_timeout':
                raise requests.exceptions.Timeout("Simulated timeout via --test_mock_api_outcome")
            elif args.test_mock_api_outcome == 'api_http_401':
                raise requests.exceptions.HTTPError("Simulated 401 Unauthorized via --test_mock_api_outcome")
            elif args.test_mock_api_outcome == 'api_http_500':
                 raise requests.exceptions.HTTPError("Simulated 500 Server Error via --test_mock_api_outcome")
            elif args.test_mock_api_outcome == 'keyboard_interrupt':
                raise KeyboardInterrupt("Simulated KeyboardInterrupt via --test_mock_api_outcome")
            elif args.test_mock_api_outcome == 'generic_exception_in_api':
                raise ValueError("Simulated generic error in API worker via --test_mock_api_outcome") # Or any other generic Exception
            # All other mock outcomes result in `raw_llm_response_json` being None, leading to a generic failure.
        else:
            # ---- REAL API CALL ----
            api_result, _ = call_openrouter_api(
                query_text=query_text_content, model_name=model_name_cfg,
                api_key=api_key, api_endpoint=api_endpoint_cfg,
                referer=referer_header_cfg, timeout_seconds=api_timeout_cfg,
                query_identifier=args.query_identifier,
                max_tokens=max_tokens_cfg, temperature=temperature_cfg,
                quiet=args.quiet
            )

        # ---- Process the result (real or mocked) ----
        # Check if the result is a string, which indicates a handled error message
        if isinstance(api_result, str):
            logging.error(f"  LLM Prompter: LLM call failed for '{os.path.basename(input_query_file_abs)}'.")
            with open(output_error_file_abs, 'w', encoding='utf-8') as f_err:
                f_err.write(api_result)
            sys.exit(1)

        raw_llm_response_json = api_result

        if raw_llm_response_json:
            # If an output path is provided, save the full JSON response there.
            if args.output_json_file:
                try:
                    output_json_file_abs = os.path.abspath(args.output_json_file)
                    with open(output_json_file_abs, 'w', encoding='utf-8') as f_json:
                        json.dump(raw_llm_response_json, f_json, indent=2, ensure_ascii=False)
                    logging.info(f"  LLM Prompter: Wrote full JSON to '{os.path.basename(output_json_file_abs)}'.")
                except IOError as e:
                    logging.error(f"  LLM Prompter: Failed to write JSON file: {e}")

            response_content_to_save = ""
            try:
                if isinstance(raw_llm_response_json.get('choices'), list) and raw_llm_response_json['choices']:
                    message = raw_llm_response_json['choices'][0].get('message', {})
                    response_content_to_save = message.get('content', '')
                if not response_content_to_save.strip():
                     logging.info("  LLM Prompter: Response content is empty or whitespace.")
            except Exception as e_parse:
                logging.warning(f"  LLM Prompter: Error extracting message content from LLM JSON: {e_parse}. Saving empty response.")

            with open(output_response_file_abs, 'w', encoding='utf-8') as f_response:
                f_response.write(response_content_to_save)

            logging.info(f"  LLM Prompter: Success. Wrote response to '{os.path.basename(output_response_file_abs)}'.")
            sys.exit(0)
        else:
            # This block now correctly handles the `api_returns_none` mock and other non-exception failures.
            logging.error(f"  LLM Prompter: LLM call failed for '{os.path.basename(input_query_file_abs)}'. No response data.")
            with open(output_error_file_abs, 'w', encoding='utf-8') as f_err:
                f_err.write("LLM API call returned None or failed (see worker log).")
            sys.exit(1)

    # ---- CENTRALIZED EXCEPTION HANDLING ----
    except requests.exceptions.Timeout as e_timeout:
        # THIS BLOCK WILL NOW CATCH THE TIMEOUT
        logging.error(f"  LLM Prompter: API Timeout Error: {e_timeout}")
        err_message = f"API call timed out for query {args.query_identifier}."
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err:
            f_err.write(err_message)
        sys.exit(1)
    except requests.exceptions.HTTPError as e_http:
        # THIS BLOCK WILL CATCH 4xx/5xx ERRORS
        logging.error(f"  LLM Prompter: HTTP Error: {e_http}")
        err_message = f"API call failed with HTTP error for query {args.query_identifier}. Details: {e_http}"
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err:
            f_err.write(err_message)
        sys.exit(1)
    except FileNotFoundError as e_fnf:
        logging.error(f"  LLM Prompter: File error: {e_fnf}")
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err: f_err.write(str(e_fnf))
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("\nLLM Prompter: Interrupted by user (Ctrl+C).")
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err: f_err.write("Processing interrupted by user (Ctrl+C).")
        sys.exit(1)
    except Exception as e:
        # Generic catch-all for truly unexpected errors
        err_message = f"Unhandled error in llm_prompter.py for query {args.query_identifier}: {type(e).__name__}: {e}"
        with open(output_error_file_abs, 'w', encoding='utf-8') as f_err:
            f_err.write(err_message)
        logging.exception(f"  LLM Prompter: {err_message}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of src/llm_prompter.py ===
