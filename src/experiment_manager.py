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
# Filename: src/experiment_manager.py

"""
State-Machine Controller for a Single Experiment.

This script is the high-level, intelligent controller for managing an entire
experiment. It operates as a state machine, verifying the experiment's status
and automatically taking the correct action (`NEW`, `REPAIR`, `REPROCESS`, or
`MIGRATE`) until the experiment is fully complete.

Its core function is to orchestrate `orchestrate_replication.py` to create or
repair individual replication runs. Once all replications are valid, it performs
a finalization step by calling `compile_experiment_results.py` to generate the
top-level summary CSV for the experiment.

It supports several modes:
- **Default (State Machine)**: Intelligently runs, resumes, or repairs an experiment.
- **`--reprocess`**: Forces a full re-processing of all analysis artifacts.
- **`--migrate`**: Transforms a legacy experiment into the modern format.
- **`--verify-only`**: Performs a read-only audit and prints a detailed report.

Usage examples are provided in the main project `DOCUMENTATION.md`.
"""

import sys
import os
import subprocess
import logging
import glob
import time
import datetime
import argparse
import json
import re
import shutil
import configparser
from configparser import ConfigParser
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial
from pathlib import Path

# tqdm is a library that provides a clean progress bar.
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs): return iterable

def _prompt_for_confirmation(prompt_text: str) -> bool:
    """Prompts the user for a Y/N confirmation and loops until valid input is received."""
    while True:
        choice = input(prompt_text).strip().lower()
        if choice == 'y':
            return True
        if choice == 'n':
            return False
        # If input is invalid, the loop continues, effectively re-prompting.

def _format_header(message, total_width=80):
    """Formats a message into a symmetrical header line with ### bookends."""
    prefix = "###"
    suffix = "###"
    # Center the message with a space on each side within the available space.
    content = f" {message} ".center(total_width - len(prefix) - len(suffix), ' ')
    return f"{prefix}{content}{suffix}"

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

# This will be set based on command-line args later in the script
_FORCE_COLOR = False

# ANSI color constants, will be defined in main() after arg parsing
C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = '', '', '', '', ''

# Audit exit codes for --verify-only mode and internal signals
AUDIT_ALL_VALID = 0
AUDIT_NEEDS_REPROCESS = 1
AUDIT_NEEDS_REPAIR = 2
AUDIT_NEEDS_MIGRATION = 3
AUDIT_ABORTED_BY_USER = 99 # Specific exit code when user aborts via prompt

#==============================================================================
#   CENTRAL FILE MANIFEST & REPORT CRITERIA
#==============================================================================
FILE_MANIFEST = {
    "config": {
        "path": "config.ini.archived",
        "type": "config_file",
        "required_keys": {
            # canonical_name: [(section, key), (fallback_section, fallback_key), ...]
            "model_name": [("LLM", "model_name"), ("LLM", "model")],
            "temperature": [("LLM", "temperature")],
            "mapping_strategy": [("Study", "mapping_strategy")],
            "num_subjects": [("Study", "group_size"), ("Study", "k_per_query")],
            "num_trials": [("Study", "num_trials"), ("Study", "num_iterations")],
            "personalities_db_path": [("Filenames", "personalities_src")],
        },
    },
    "queries_dir":   {"path": "session_queries"},
    "query_files":   {"path": "session_queries/llm_query_*.txt", "pattern": r"llm_query_(\d+)\.txt"},
    "trial_manifests": {"path": "session_queries/llm_query_*_manifest.txt", "pattern": r"llm_query_(\d+)_manifest\.txt"},
    "aggregated_mappings_file": {"path": "session_queries/mappings.txt"},
    "responses_dir": {"path": "session_responses"},
    "response_files":{"path": "session_responses/llm_response_*.txt", "pattern": r"llm_response_(\d+)\.txt"},
    "analysis_dir":  {"path": "analysis_inputs"},
    "scores_file":   {"path": "analysis_inputs/all_scores.txt"},
    "mappings_file": {"path": "analysis_inputs/all_mappings.txt"},
    "replication_report": {"pattern": r"replication_report_\d{4}-\d{2}-\d{2}.*\.txt"},
}

REPORT_REQUIRED_METRICS = {
    "n_valid_responses", "mwu_stouffer_z", "mwu_stouffer_p", "mwu_fisher_chi2",
    "mwu_fisher_p", "mean_effect_size_r", "effect_size_r_p", "mean_mrr",
    "mrr_p", "mean_top_1_acc", "top_1_acc_p", "mean_top_3_acc",
    "top_3_acc_p", "mean_rank_of_correct_id", "rank_of_correct_id_p",
    "bias_slope", "bias_intercept", "bias_r_value", "bias_p_value", "bias_std_err",
    "mean_mrr_lift", "mean_top_1_acc_lift", "mean_top_3_acc_lift"
}

# Define required nested dictionaries and the keys they must contain
REPORT_REQUIRED_NESTED_KEYS = {
    "positional_bias_metrics": {"top1_pred_bias_std", "true_false_score_diff"}
}

# --- Verification Helper Functions ---

def _get_file_indices(run_path: Path, spec: dict) -> set[int]:
    """Extracts the numerical indices from a set of files using regex."""
    indices = set()
    regex = re.compile(spec["pattern"])
    files = run_path.glob(spec["path"])
    for f in files:
        match = regex.match(os.path.basename(f))
        if match:
            indices.add(int(match.group(1)))
    return indices

def _count_lines_in_file(filepath: str, skip_header: bool = True) -> int:
    """Counts data lines in a file, optionally skipping a header."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        start_index = 1 if skip_header and lines else 0
        return len([line for line in lines[start_index:] if line.strip()])
    except Exception:
        return 0

def _count_matrices_in_file(filepath: str, k: int) -> int:
    """Counts how many k x k matrices are in a file."""
    if not os.path.exists(filepath) or k <= 0:
        return 0
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line for line in f.read().splitlines() if line.strip()]
        return len(lines) // k
    except Exception:
        return 0

# ------------------------------------------------------------------ helpers
def _check_config_manifest(run_path: Path, k_expected: int, m_expected: int):
    cfg_path = run_path / FILE_MANIFEST["config"]["path"]
    required_keys_map = FILE_MANIFEST["config"]["required_keys"]

    try:
        cfg = ConfigParser()
        # Use a `with open` block to ensure the file handle is always closed, preventing file locks.
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg.read_file(f)
        if not cfg.sections():
            return "CONFIG_MALFORMED"
    except Exception:
        return "CONFIG_MALFORMED"

    # Generic function to find a key's value using the fallback map
    def _get_value(canonical_name, value_type=str):
        for section, key in required_keys_map[canonical_name]:
            if cfg.has_option(section, key):
                try:
                    if value_type is int:
                        return cfg.getint(section, key)
                    if value_type is float:
                        return cfg.getfloat(section, key)
                    return cfg.get(section, key)
                except (configparser.Error, ValueError):
                    continue  # Try next fallback
        return None

    # Check for presence of all required keys
    missing_keys = [name for name in required_keys_map if _get_value(name) is None]
    if missing_keys:
        return f"CONFIG_MISSING_KEYS: {', '.join(missing_keys)}"

    # Validate k and m values against directory name
    k_cfg = _get_value("num_subjects", value_type=int)
    m_cfg = _get_value("num_trials", value_type=int)

    mismatched = []
    if k_cfg != k_expected:
        mismatched.append(f"k (expected {k_expected}, found {k_cfg})")
    if m_cfg != m_expected:
        mismatched.append(f"m (expected {m_expected}, found {m_cfg})")

    if mismatched:
        return f"CONFIG_MISMATCH: {', '.join(mismatched)}"

    return "VALID"

def _check_file_set(run_path: Path, spec: dict, expected_count: int):
    glob_pattern = spec["path"]
    regex_pattern = spec.get("pattern")

    all_files_in_dir = list(run_path.glob(glob_pattern))

    # If a specific regex pattern is provided, filter the glob results for a more precise count.
    if regex_pattern:
        regex = re.compile(regex_pattern)
        actual = [f for f in all_files_in_dir if regex.match(os.path.basename(f))]
    else:
        # If no regex is provided, use the glob results directly.
        actual = all_files_in_dir

    label = glob_pattern.split("/", 1)[0]  # e.g. session_queries
    if not actual:
        return f"{label.upper()}_MISSING"

    count = len(actual)
    if count < expected_count:
        return f"{label.upper()}_INCOMPLETE"
    if count > expected_count:
        return f"{label.upper()}_TOO_MANY"
    return "VALID"


def _check_analysis_files(run_path: Path, expected_entries: int, k_value: int):
    scores_p = run_path / FILE_MANIFEST["scores_file"]["path"]
    mappings_p = run_path / FILE_MANIFEST["mappings_file"]["path"]
    for p in (scores_p, mappings_p):
        if not p.exists():
            return "ANALYSIS_FILES_MISSING"
    try:
        # Mappings are simple line-delimited files; we assume a potential header.
        n_mappings = _count_lines_in_file(mappings_p, skip_header=True)
        # The number of score matrices depends on 'k' (group size).
        n_scores = _count_matrices_in_file(scores_p, k_value)
    except Exception:
        return "ANALYSIS_DATA_MALFORMED"
    if n_scores != expected_entries or n_mappings != expected_entries:
        return "ANALYSIS_DATA_INCOMPLETE"
    return "VALID"


def _check_report(run_path: Path):
    reports = sorted(run_path.glob("replication_report_*.txt"))
    if not reports:
        return "REPORT_MISSING"
    latest = reports[-1]
    try:
        text = latest.read_text(encoding="utf-8")
    except Exception:
        return "REPORT_MALFORMED"
    if "<<<METRICS_JSON_START>>>" not in text or "<<<METRICS_JSON_END>>>" not in text:
        return "REPORT_MALFORMED"
    try:
        start = text.index("<<<METRICS_JSON_START>>>")
        end = text.index("<<<METRICS_JSON_END>>>")
        j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
    except Exception:
        return "REPORT_MALFORMED"

    # Check for required top-level metric keys
    missing_metrics = REPORT_REQUIRED_METRICS - j.keys()
    if missing_metrics:
        return f"REPORT_INCOMPLETE_METRICS: {', '.join(sorted(missing_metrics))}"

    # Check for required nested dictionaries and their internal keys
    for nested_key, required_sub_keys in REPORT_REQUIRED_NESTED_KEYS.items():
        nested_dict = j.get(nested_key)
        if not isinstance(nested_dict, dict):
            return f"REPORT_MISSING_NESTED_DICT: {nested_key}"

        missing_sub_keys = required_sub_keys - nested_dict.keys()
        if missing_sub_keys:
            return f"REPORT_INCOMPLETE_NESTED_KEYS ({nested_key}): {', '.join(sorted(missing_sub_keys))}"

    return "VALID"

def _verify_single_run_completeness(run_path: Path) -> tuple[str, list[str]]:
    status_details = []

    # 1. name validity
    # This regex now correctly handles the new format without a trailing '$' to allow for the new parts.
    name_match = re.search(r"sbj-(\d+)_trl-(\d+)", run_path.name)
    if not run_path.name.startswith("run_") or not name_match:
        status_details = [f"{run_path.name} does not match required run_*_sbj-NN_trl-NNN* pattern"]
        return "INVALID_NAME", status_details
    k_expected, m_expected = int(name_match.group(1)), int(name_match.group(2))

    # 2. config
    stat_cfg = _check_config_manifest(run_path, k_expected, m_expected)
    if stat_cfg != "VALID":
        status_details.append(stat_cfg)
    else:
        status_details.append("config OK")

    # 3. queries
    stat_q = _check_file_set(run_path, FILE_MANIFEST["query_files"], m_expected)
    if stat_q != "VALID":
        status_details.append(stat_q)
    else:
        status_details.append("queries OK")

    # 4. Check for mappings file and optional trial manifests
    aggregated_mappings_path = run_path / FILE_MANIFEST["aggregated_mappings_file"]["path"]
    if not aggregated_mappings_path.exists():
        status_details.append("AGGREGATED_MAPPINGS_MISSING")

    # Conditionally check for trial manifests, as they may not exist in legacy runs.
    # First, do a quick check to see if ANY manifest files are present.
    manifest_spec = FILE_MANIFEST["trial_manifests"]
    if list(run_path.glob(manifest_spec["path"])):
        # If manifests are found, then perform the full, strict check for completeness.
        stat_q_manifests = _check_file_set(run_path, manifest_spec, m_expected)
        if stat_q_manifests != "VALID":
            status_details.append("MANIFESTS_INCOMPLETE")

    # 5. Check response files
    expected_responses = m_expected
    stat_r = _check_file_set(run_path, FILE_MANIFEST["response_files"], expected_responses)
    if stat_r != "VALID":
        status_details.append(stat_r)
    else:
        # If counts are OK, perform a deeper check for index consistency
        query_indices = _get_file_indices(run_path, FILE_MANIFEST["query_files"])
        response_indices = _get_file_indices(run_path, FILE_MANIFEST["response_files"])
        if query_indices != response_indices:
            status_details.append("QUERY_RESPONSE_INDEX_MISMATCH")
        else:
            status_details.append("responses OK")

    # 6. analysis files
    if (run_path / FILE_MANIFEST["analysis_dir"]["path"]).exists():
        # The true number of expected entries in analysis files is not the
        # count of response files (some may be invalid), but the
        # 'n_valid_responses' metric stored in the replication report's JSON.
        expected_entries = None
        try:
            latest_report = sorted(run_path.glob("replication_report_*.txt"))[-1]
            text = latest_report.read_text(encoding="utf-8")
            start = text.index("<<<METRICS_JSON_START>>>")
            end = text.index("<<<METRICS_JSON_END>>>")
            j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
            expected_entries = j.get("n_valid_responses")
        except (IndexError, ValueError, KeyError):
            # This will be caught by the report check later.
            # We set a placeholder to allow the analysis check to proceed.
            expected_entries = -1 # An impossible value to ensure failure

        if expected_entries is not None and expected_entries >= 0:
            stat_a = _check_analysis_files(run_path, expected_entries, k_expected)
            if stat_a != "VALID":
                status_details.append(stat_a)
            else:
                status_details.append("analysis OK")
        else:
            # This branch handles cases where the report is missing or lacks the key.
            status_details.append("ANALYSIS_SKIPPED_BAD_REPORT")
    else:
        status_details.append("ANALYSIS_FILES_MISSING")

    # 7. report
    stat_rep = _check_report(run_path)
    if stat_rep != "VALID":
        status_details.append(stat_rep)
    else:
        status_details.append("report OK")

    # 8. replication-level summary file
    if not (run_path / "REPLICATION_results.csv").exists():
        status_details.append("REPLICATION_RESULTS_MISSING")

    # roll up
    if all(d.endswith(" OK") for d in status_details):
        return "VALIDATED", status_details
    if any("INVALID_NAME" in d for d in status_details):
        return "INVALID_NAME", status_details
    if any("CONFIG" in d for d in status_details):
        return "CONFIG_ISSUE", status_details
    # Check for fundamental query file corruption.
    if any("SESSION_QUERIES" in d or "MAPPINGS_MISSING" in d or "MANIFESTS_INCOMPLETE" in d for d in status_details):
        return "QUERY_ISSUE", status_details

    # Check for response file corruption. An index mismatch is a symptom of a response problem if queries are OK.
    if any("SESSION_RESPONSES" in d or "QUERY_RESPONSE_INDEX_MISMATCH" in d for d in status_details):
        return "RESPONSE_ISSUE", status_details

    # Any other non-fatal issue is a less severe ANALYSIS_ISSUE that can be reprocessed.
    return "ANALYSIS_ISSUE", status_details

def _get_experiment_state(target_dir: Path, expected_reps: int, verbose=False) -> tuple[str, list, dict]:
    """
    High-level state machine driver with correct state priority.

    Returns:
        A tuple containing:
        - str: The high-level state of the experiment (e.g., "REPAIR_NEEDED").
        - list: The detailed payload for the action (e.g., list of failed runs).
        - dict: A granular map of {run_name: (status, details)} for every run.
    """
    run_dirs = sorted([p for p in target_dir.glob("run_*") if p.is_dir()])
    
    # Handle the brand-new experiment case first.
    if not run_dirs:
        return "NEW_NEEDED", [], {}

    run_paths_by_name = {p.name: p for p in run_dirs}
    granular = {p.name: _verify_single_run_completeness(p) for p in run_dirs}
    fails = {n: (s, d) for n, (s, d) in granular.items() if s != "VALIDATED"}

    # --- State Priority 1: REPAIR_NEEDED ---
    # Check for critical issues that require re-running parts of the pipeline.
    runs_needing_session_repair = []
    runs_needing_full_replication_repair = []
    for run_name, (status, details_list) in fails.items():
        if status == "RESPONSE_ISSUE":
            run_path = run_paths_by_name[run_name]
            query_indices = _get_file_indices(run_path, FILE_MANIFEST["query_files"])
            response_indices = _get_file_indices(run_path, FILE_MANIFEST["response_files"])
            failed_indices = sorted(list(query_indices - response_indices))
            if failed_indices:
                runs_needing_session_repair.append({"dir": str(run_path), "failed_indices": failed_indices, "repair_type": "session_repair"})
        elif status in {"QUERY_ISSUE", "CONFIG_ISSUE", "INVALID_NAME"}:
            runs_needing_full_replication_repair.append({"dir": str(run_paths_by_name[run_name]), "repair_type": "full_replication_repair"})

    if runs_needing_full_replication_repair:
        return "REPAIR_NEEDED", runs_needing_full_replication_repair, granular
    if runs_needing_session_repair:
        return "REPAIR_NEEDED", runs_needing_session_repair, granular

    # --- State Priority 2: REPROCESS_NEEDED ---
    # If no critical repairs are needed, check for analysis issues.
    if any(status == "ANALYSIS_ISSUE" for status, _ in fails.values()):
        analysis_fails = [
            {"dir": str(run_paths_by_name[name])}
            for name, (status, _) in fails.items()
            if status == "ANALYSIS_ISSUE"
        ]
        return "REPROCESS_NEEDED", analysis_fails, granular

    # --- State Priority 3: NEW_NEEDED ---
    # If all existing runs are valid but there are not enough of them.
    if not fails and len(run_dirs) < expected_reps:
        return "NEW_NEEDED", [], granular

    # --- State Priority 4: COMPLETE ---
    # If all existing runs are valid and the count is correct.
    if not fails and len(run_dirs) >= expected_reps:
        return "COMPLETE", [], granular
        
    # Fallback for any unhandled state.
    return "UNKNOWN", [], granular

# --- Mode Execution Functions ---

def _verify_experiment_level_files(target_dir: Path) -> tuple[bool, list[str]]:
    """Checks for top-level summary files for the entire experiment."""
    is_complete = True
    details = []
    
    # These consolidated summary files should exist in the experiment's root directory.
    required_files = [
        "batch_run_log.csv",
        "EXPERIMENT_results.csv"
    ]

    for filename in required_files:
        if not (target_dir / filename).exists():
            is_complete = False
            details.append(f"MISSING: {filename}")

    # Check if the batch log is finalized (contains a summary line)
    log_path = target_dir / "batch_run_log.csv"
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                content = f.read()
            if "BatchSummary" not in content:
                is_complete = False
                details.append("batch_run_log.csv NOT FINALIZED")
        except Exception:
            is_complete = False
            details.append("batch_run_log.csv UNREADABLE")

    return is_complete, details

def _run_verify_only_mode(target_dir: Path, expected_reps: int, suppress_exit: bool = False, print_report: bool = True, is_verify_only_cli: bool = False, suppress_external_recommendation: bool = False) -> int:
    """
    Runs a read-only verification and prints a detailed summary table.
    Can suppress exiting for internal use by the state machine.

    Args:
        target_dir (Path): The root directory of the experiment to verify.
        expected_reps (int): The number of expected replications for the experiment.
        suppress_exit (bool): If True, prevents the function from calling sys.exit().
                              Useful when called internally by the state machine.
        print_report (bool): If True, prints the detailed audit report to console.
        is_verify_only_cli (bool): True if the function was called directly via --verify-only CLI arg.
        suppress_external_recommendation (bool): If True, suppresses the "Please run X" message
                                                 when called internally by a wrapper script.

    Returns:
        int: An audit exit code (AUDIT_ALL_VALID, AUDIT_NEEDS_REPROCESS, etc.).
    """
    if print_report:
        print(f"\n--- Verifying Data Completeness in: ---")
        print(f"{target_dir}")
    run_dirs = sorted([p for p in glob.glob(os.path.join(target_dir, 'run_*')) if os.path.isdir(p)])

    if not run_dirs:
        if print_report:
            print("No 'run_*' directories found. Nothing to verify.")
            print(f"{C_YELLOW}Cannot determine status. This may be a new or empty experiment directory.{C_RESET}")
        return AUDIT_NEEDS_MIGRATION

    all_runs_data = []
    total_expected_trials = 0
    total_valid_responses = 0
    total_complete_runs = 0

    for run_dir_path in run_dirs:
        run_dir = Path(run_dir_path)
        status, details = _verify_single_run_completeness(run_dir)

        if status == "VALIDATED":
            total_complete_runs += 1

        # Get total expected trials and actual valid responses for the summary
        try:
            # Total possible trials is still derived from the folder name
            total_expected_trials += int(re.match(r".*_trl-(\d+)$", run_dir.name).group(1))
            
            # Actual valid responses comes from the JSON report, the single source of truth
            n_valid_in_run = 0
            latest_report = sorted(run_dir.glob("replication_report_*.txt"))[-1]
            text = latest_report.read_text(encoding="utf-8")
            start = text.index("<<<METRICS_JSON_START>>>")
            end = text.index("<<<METRICS_JSON_END>>>")
            j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
            n_valid_in_run = j.get("n_valid_responses", 0)
            total_valid_responses += n_valid_in_run
            
        except (AttributeError, ValueError, IndexError, json.JSONDecodeError):
            # If anything goes wrong (bad name, no report, bad JSON),
            # we just skip adding to the totals for this run.
            pass

        all_runs_data.append({
            "name": run_dir.name,
            "status": status,
            "details": "; ".join(details)
        })

    # Set a max width for the directory name column to keep the table compact
    MAX_NAME_WIDTH = 65
    max_name_len = min(max(len(run['name']) for run in all_runs_data), MAX_NAME_WIDTH) if all_runs_data else 20

    print(f"\n{'Run Directory':<{max_name_len}} {'Status':<20} {'Details'}")
    print(f"{'-'*max_name_len} {'-'*20} {'-'*45}")
    for run in all_runs_data:
        display_name = run['name']
        if len(display_name) > max_name_len:
            display_name = display_name[:max_name_len - 3] + "..."

        status_color = C_GREEN if run['status'] == "VALIDATED" else C_RED
        print(f"{display_name:<{max_name_len}} {status_color}{run['status']:<20}{C_RESET} {run['details']}")

    # --- Determine result code based on findings from individual runs ---
    run_statuses = {run['status'] for run in all_runs_data}

    if "INVALID_NAME" in run_statuses or "CONFIG_ISSUE" in run_statuses:
        audit_result_code = AUDIT_NEEDS_MIGRATION
    elif "QUERY_ISSUE" in run_statuses or "RESPONSE_ISSUE" in run_statuses:
        audit_result_code = AUDIT_NEEDS_REPAIR
    elif "ANALYSIS_ISSUE" in run_statuses:
        audit_result_code = AUDIT_NEEDS_REPROCESS
    else:  # All individual replications are valid.
        audit_result_code = AUDIT_ALL_VALID

    # --- Now check for experiment-level summary files ---
    exp_complete, exp_details = _verify_experiment_level_files(Path(target_dir))

    # --- Determine final messages and colors based on the combined state ---
    exp_status_str_base = "COMPLETE" if exp_complete else "INCOMPLETE"
    exp_status_suffix = ""
    
    if exp_complete:
        exp_status_color = C_GREEN
        if audit_result_code == AUDIT_NEEDS_REPROCESS:
            exp_status_color = C_YELLOW
            exp_status_suffix = " (Outdated)"
    elif audit_result_code == AUDIT_ALL_VALID:
        exp_status_color = C_YELLOW
    else:
        exp_status_color = C_RED

    # Determine the final audit message and recommendation
    if audit_result_code == AUDIT_NEEDS_MIGRATION:
        audit_message = "FAILED. Legacy or malformed runs detected."
        audit_recommendation = "Migrate experiment for further processing (run 'migrate_experiment.ps1' with the directory path of the experiment)."
        audit_color = C_RED
    elif audit_result_code == AUDIT_NEEDS_REPAIR:
        audit_message = "FAILED. Critical data is missing or corrupt (queries/responses)."
        if is_verify_only_cli:
            # Direct recommendation for standalone audit
            audit_recommendation = "Run 'run_experiment.ps1' on the target directory to automatically repair the experiment."
        else:
            # Contextual recommendation for internal audit (when a prompt will follow)
            audit_recommendation = "Proceed with automatic repair when prompted. If this fails, re-run 'run_experiment.ps1' on the target directory."
        audit_color = C_RED
    elif audit_result_code == AUDIT_NEEDS_REPROCESS:
        audit_message = "UPDATE RECOMMENDED. Experiment analysis needs refreshing."
        audit_recommendation = "Update experiment to fix analysis files and summaries (run 'update_experiment.ps1' with the directory path)."
        audit_color = C_YELLOW
    elif audit_result_code == AUDIT_ALL_VALID:
        if exp_complete:
            audit_message = "PASSED. Experiment is complete and valid."
            audit_recommendation = "No further action is required."
        else:
            audit_message = "PASSED. All replications are valid."
            audit_recommendation = "Experiment is ready for finalization. Note: this final step is automatic."
        audit_color = C_GREEN

    if print_report:
        if total_expected_trials > 0:
            completeness = (total_valid_responses / total_expected_trials) * 100
            print("\n--- Overall Summary ---")
            print(f"Experiment Directory: {target_dir}")
            print(f"Replication Status:")
            print(f"  - Total Runs Verified:          {len(run_dirs)}")
            print(f"  - Total Runs Complete (Pipeline): {total_complete_runs}/{len(run_dirs)}")
            print(f"  - Total Valid LLM Responses:      {total_valid_responses}/{total_expected_trials} ({completeness:.2f}%)")
            
            print(f"Experiment Aggregation Status: {exp_status_color}{exp_status_str_base}{exp_status_suffix}{C_RESET}")
            
            if not exp_complete:
                for detail in exp_details:
                    print(f"  - {exp_status_color}{detail}{C_RESET}")
        
        print(f"\n{audit_color}Audit Result: {audit_message}{C_RESET}")
        print(f"{audit_color}Recommendation: {audit_recommendation}{C_RESET}")

    # When called from the CLI, exit with the true audit code so wrapper scripts can react.
    if not suppress_exit and is_verify_only_cli:
        sys.exit(audit_result_code)

    # When called internally, return the true code.
    return audit_result_code

def _run_replication_worker(rep_num, orchestrator_script, target_dir, notes, quiet, bias_script):
    """Worker function to execute one full replication using the orchestrator."""
    try:
        # Step 1: Run the main orchestrator for the replication
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", target_dir]
        if notes: cmd_orch.extend(["--notes", notes])
        if quiet: cmd_orch.append("--quiet")
        subprocess.run(cmd_orch, check=True, capture_output=True, text=True)
        
        # Step 2: Run bias analysis
        # Find the newly created directory to pass to the bias script
        run_dir_pattern = os.path.join(target_dir, f"run_*_rep-{rep_num:02d}_*")
        run_dirs = glob.glob(run_dir_pattern)
        if not run_dirs:
            return rep_num, False, f"Could not find run directory for rep {rep_num} after orchestration."
        
        run_dir = run_dirs[0]
        k_val = get_config_value(APP_CONFIG, 'Study', 'group_size', value_type=int, fallback_key='k_per_query', fallback=10)
        cmd_bias = [sys.executable, bias_script, run_dir, "--k_value", str(k_val)]
        if not quiet: cmd_bias.append("--verbose")
        subprocess.run(cmd_bias, check=True, capture_output=True, text=True)
        
        return rep_num, True, None
    except subprocess.CalledProcessError as e:
        error_details = f"Replication {rep_num} worker failed.\nSTDOUT:\n{e.stdout}\nSTDERR:\n{e.stderr}"
        return rep_num, False, error_details
    except Exception as e:
        return rep_num, False, f"An unexpected error occurred in replication worker {rep_num}: {e}"

def _run_new_mode(target_dir, start_rep, end_rep, notes, quiet, orchestrator_script):
    """Executes 'NEW' mode by calling orchestrator, which is now parallelized."""
    print(f"{C_CYAN}--- Entering NEW Mode: Creating missing replications ---{C_RESET}")
    
    completed_reps = {int(re.search(r'_rep-(\d+)_', os.path.basename(d)).group(1))
                      for d in glob.glob(os.path.join(target_dir, 'run_*_rep-*'))
                      if re.search(r'_rep-(\d+)_', os.path.basename(d))}
                      
    reps_to_run = [r for r in range(start_rep, end_rep + 1) if r not in completed_reps]
    if not reps_to_run:
        print("All replications exist. Nothing to do in NEW mode.")
        return True

    print(f"Will create {len(reps_to_run)} new replication(s).")
    batch_start_time = time.time()
    
    for i, rep_num in enumerate(reps_to_run):
        header_text = f" RUNNING REPLICATION {rep_num} of {end_rep} "
        print("\n" + "="*80)
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print("="*80)
        
        # The orchestrator is now responsible for the entire replication lifecycle, including parallel sessions.
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", target_dir]
        if notes: cmd_orch.extend(["--notes", notes])
        if quiet: cmd_orch.append("--quiet")
        
        try:
            subprocess.run(cmd_orch, check=True)
            # Bias analysis is now handled inside the orchestrator after Stage 4.

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Replication {rep_num} failed or was interrupted.")
            if isinstance(e, KeyboardInterrupt): sys.exit(1)
            return False # Indicate failure

        elapsed = time.time() - batch_start_time
        avg_time = elapsed / (i + 1)
        remaining_reps = len(reps_to_run) - (i + 1)
        time_remaining = remaining_reps * avg_time
        eta = datetime.datetime.now() + datetime.timedelta(seconds=time_remaining)
        print(f"\n{C_GREEN}Time Elapsed: {str(datetime.timedelta(seconds=int(elapsed)))} | Time Remaining: {str(datetime.timedelta(seconds=int(time_remaining)))} | ETA: {eta.strftime('%H:%M:%S')}{C_RESET}")

    return True

# This '_session_worker' function is no longer needed here and has been moved into orchestrate_replication.py's logic.

def _run_repair_mode(runs_to_repair, orchestrator_script_path, quiet):
    """Delegates repair work to the orchestrator for each failed run."""
    print(f"{C_YELLOW}--- Entering REPAIR Mode: Fixing {len(runs_to_repair)} run(s) with missing responses ---{C_RESET}")

    for run_info in runs_to_repair:
        run_dir = run_info["dir"]
        failed_indices = run_info.get("failed_indices", [])
        if not failed_indices:
            continue

        print(f"\n--- Repairing {len(failed_indices)} session(s) in: {os.path.basename(run_dir)} ---")
        
        # Call the orchestrator in --reprocess mode and pass the specific indices to fix.
        # The orchestrator is now responsible for the parallel execution.
        cmd = [
            sys.executable, orchestrator_script_path,
            "--reprocess",
            "--run_output_dir", run_dir,
            "--indices"
        ] + [str(i) for i in failed_indices]
        
        if quiet:
            cmd.append("--quiet")

        try:
            # The orchestrator will now handle its own progress display.
            subprocess.run(cmd, check=True)
        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Repair failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(AUDIT_ABORTED_BY_USER)
            return False # A single failure halts the entire repair operation.
            
    return True

def _run_full_replication_repair(runs_to_repair, orchestrator_script, quiet):
    """Deletes and fully regenerates runs with critical issues (e.g., missing queries, config issues)."""
    print(f"{C_RED}--- Entering FULL REPLICATION REPAIR Mode: Deleting and regenerating {len(runs_to_repair)} run(s) with critical issues ---{C_RESET}")

    for i, run_info in enumerate(runs_to_repair):
        run_dir_path_str = run_info["dir"]
        run_dir_path = Path(run_dir_path_str)
        run_basename = os.path.basename(run_dir_path_str)
        
        # Initialize capture_output_flag here to ensure it's always defined.
        capture_output_flag = False 

        header_text = f" REGENERATING REPLICATION {run_basename} ({i+1}/{len(runs_to_repair)}) "
        print("\n" + "="*80)
        print(f"{C_RED}{header_text.center(78)}{C_RESET}")
        print("="*80)

        # Step 1: Extract replication number from directory name
        rep_num_match = re.search(r'_rep-(\d+)_', run_basename)
        if not rep_num_match:
            logging.error(f"Could not extract replication number from '{run_basename}'. Skipping repair for this run.")
            continue # Skip to the next run

        rep_num = int(rep_num_match.group(1))
        
        # Step 2: Delete the corrupted run directory
        try:
            print(f"Deleting corrupted directory: {run_dir_path_str}")
            shutil.rmtree(run_dir_path_str)
        except OSError as e:
            logging.error(f"Failed to delete directory {run_dir_path_str}: {e}")
            continue # Skip to the next run
            
        # Step 3: Regenerate the run from scratch using its replication number
        base_output_dir = os.path.dirname(run_dir_path_str)
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", base_output_dir]
        
        # Configure output capture based on the 'quiet' flag.
        if quiet:
            cmd_orch.append("--quiet")
            capture_output_flag = True # Capture output if quiet mode is active
        else:
            cmd_orch.append("--verbose") # Pass verbose flag to sub-script if not quiet
            capture_output_flag = False # Let output stream directly to console
        
        try:
            # Execute orchestrate_replication.py. 
            # If not capturing, output streams directly to console (fixing spinner).
            result = subprocess.run(cmd_orch, check=True, capture_output=capture_output_flag, text=capture_output_flag)
            
            # Log captured output if in quiet mode
            if capture_output_flag:
                if result.stdout:
                    logging.info(f"Orchestrate Replication STDOUT for {run_basename}:\n{result.stdout}")
                if result.stderr:
                    logging.error(f"Orchestrate Replication STDERR for {run_basename}:\n{result.stderr}")

            # The orchestrator is responsible for the full lifecycle, including bias analysis.
            # No further steps are needed here.

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Full replication repair failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(AUDIT_ABORTED_BY_USER)
            return False # Indicate failure
    return True

def _run_migrate_mode(target_dir, patch_script, orchestrator_script, verbose=False):
    """
    Executes a one-time migration process for a legacy experiment directory.
    This mode is destructive and will delete old artifacts.
    """
    print(f"{C_YELLOW}--- Entering MIGRATE Mode: Transforming experiment at: ---{C_RESET}")
    print(f"{C_YELLOW}{target_dir}{C_RESET}")
    run_dirs = sorted([p for p in target_dir.glob("run_*") if p.is_dir()])

    # Sub-step 1: Clean Artifacts (Run this first to remove corrupt files)
    print("\n- Cleaning old summary files and corrupted analysis artifacts...")
    try:
        files_to_delete = ["final_summary_results.csv", "batch_run_log.csv", "EXPERIMENT_results.csv"]
        for file in files_to_delete:
            file_path = target_dir / file
            if file_path.exists():
                print(f"  - Deleting old '{file_path.name}'")
                file_path.unlink()

        for run_dir in run_dirs:
            for corrupted_file in run_dir.glob("*.txt.corrupted"):
                corrupted_file.unlink()
            analysis_inputs_path = run_dir / "analysis_inputs"
            if analysis_inputs_path.is_dir():
                shutil.rmtree(analysis_inputs_path)
        print("  - Cleaning complete.")
    except Exception as e:
        logging.error(f"Failed to clean artifacts: {e}")
        return False

    # Sub-step 2: Patch Configs
    print("\n- Patching legacy configuration files...")
    try:
        subprocess.run([sys.executable, patch_script, str(target_dir)], check=True, capture_output=True, text=True)
        print("  - Patching complete.")
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to patch configs. Stderr:\n{e.stderr}")
        return False

    # Sub-step 3: Reprocess Each Replication
    print(f"\n- Reprocessing {len(run_dirs)} individual runs to generate modern reports...")
    try:
        for run_dir in tqdm(run_dirs, desc="Reprocessing Runs", ncols=80):
            cmd = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", str(run_dir)]
            if not verbose: cmd.append("--quiet")
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Failed to reprocess {run_dir.name}. Stderr:\n{result.stderr}")
                return False
        print("  - Reprocessing complete.")
    except Exception as e:
        logging.error(f"An unexpected error occurred during reprocessing: {e}")
        return False

    print(f"\n{C_GREEN}--- Migration pre-processing complete. ---{C_RESET}")
    print("The manager will now proceed with final checks to finalize the migration.")
    return True

def _run_reprocess_mode(runs_to_reprocess, notes, quiet, orchestrator_script, compile_script, target_dir, log_manager_script):
    """Executes 'REPROCESS' mode to fix corrupted analysis files."""
    print(f"{C_YELLOW}--- Entering REPROCESS Mode: Fixing {len(runs_to_reprocess)} run(s) with corrupt analysis ---{C_RESET}")

    for i, run_info in enumerate(runs_to_reprocess):
        run_dir = run_info["dir"]
        header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(runs_to_reprocess)}) "
        print("\n" + "="*80)
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print("="*80)

        cmd_orch = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", run_dir]
        if quiet: cmd_orch.append("--quiet")
        if notes: cmd_orch.extend(["--notes", notes])

        try:
            # The orchestrator is now responsible for the entire reprocessing lifecycle,
            # including calling the bias analysis script.
            subprocess.run(cmd_orch, check=True)
        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Reprocessing failed for {os.path.basename(run_dir)}.")
            if isinstance(e, KeyboardInterrupt): sys.exit(1)
            return False

    # After all runs are reprocessed, perform a full and final aggregation.
    print(f"\n{C_CYAN}--- Finalizing experiment summaries... ---{C_RESET}")
    try:
        # Rebuild the batch log from the newly updated reports
        cmd_log_rebuild = [sys.executable, log_manager_script, "rebuild", target_dir]
        subprocess.run(cmd_log_rebuild, check=True, capture_output=True)
        
        # Re-compile the hierarchical results
        cmd_compile = [sys.executable, compile_script, target_dir]
        subprocess.run(cmd_compile, check=True, capture_output=quiet, text=True)
        
        # Finalize the batch log with a summary line
        cmd_log_finalize = [sys.executable, log_manager_script, "finalize", target_dir]
        subprocess.run(cmd_log_finalize, check=True, capture_output=True)

    except (subprocess.CalledProcessError, Exception) as e:
        logging.error(f"Failed during final aggregation. Error: {e}")
        return False

    return True

def main():
    parser = argparse.ArgumentParser(description="State-machine controller for running experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="Optional. The target directory for the experiment. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1, help="First replication number for new runs.")
    parser.add_argument('--end-rep', type=int, default=None, help="Last replication number for new runs.")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the reports.')
    parser.add_argument('--max-loops', type=int, default=10, help="Safety limit for state-machine loops.")
    parser.add_argument('--verify-only', action='store_true', help="Run in read-only diagnostic mode and print a detailed completeness report.")
    parser.add_argument('--migrate', action='store_true', help="Run a one-time migration workflow for a legacy experiment directory.")
    parser.add_argument('--reprocess', action='store_true', help="Force reprocessing of all runs in an experiment, then finalize.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS) # Hidden from user help
    args = parser.parse_args()

    # Define color constants based on TTY status or the --force-color flag
    use_color = sys.stdout.isatty() or args.force_color
    if use_color:
        global C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET
        C_CYAN = '\033[96m'
        C_GREEN = '\033[92m'
        C_YELLOW = '\033[93m'
        C_RED = '\033[91m'
        C_RESET = '\033[0m'

    # --- Script Paths ---
    # Define src_dir relative to the project root for robustness.
    src_dir = os.path.join(PROJECT_ROOT, "src")
    orchestrator_script = os.path.join(src_dir, "orchestrate_replication.py")
    process_script = os.path.join(src_dir, 'process_llm_responses.py')
    analyze_script = os.path.join(src_dir, 'analyze_llm_performance.py')
    bias_script = os.path.join(src_dir, 'run_bias_analysis.py')
    # Script to compile results for a single experiment.
    compile_experiment_script = os.path.join(src_dir, 'compile_experiment_results.py')
    log_manager_script = os.path.join(src_dir, 'replication_log_manager.py')
    patch_script = os.path.join(src_dir, "patch_old_experiment.py")
    rebuild_script = os.path.join(src_dir, "rebuild_reports.py")

    try:
        if args.target_dir:
            final_output_dir = os.path.abspath(args.target_dir)
        else:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            base_output = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
            new_exp_subdir = get_config_value(APP_CONFIG, 'General', 'new_experiments_subdir', fallback='new_experiments')
            exp_prefix = get_config_value(APP_CONFIG, 'General', 'experiment_dir_prefix', fallback='experiment_')
            base_path = os.path.join(PROJECT_ROOT, base_output, new_exp_subdir)
            final_output_dir = os.path.join(base_path, f"{exp_prefix}{timestamp}")
            print(f"{C_CYAN}No target directory specified. Creating default:{C_RESET}\n{final_output_dir}")

        if not os.path.exists(final_output_dir):
            if args.verify_only:
                print(f"\nDirectory not found:\n{final_output_dir}")
                sys.exit(1)
            os.makedirs(final_output_dir)
            print(f"\nCreated target directory:\n{final_output_dir}")

        config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int, fallback=30)
        end_rep = args.end_rep if args.end_rep is not None else config_num_reps

        if args.verify_only:
            _run_verify_only_mode(Path(final_output_dir), end_rep, suppress_exit=False, print_report=True, is_verify_only_cli=True)
            return

        if args.migrate:
            if not _run_migrate_mode(Path(final_output_dir), patch_script, rebuild_script, args.verbose):
                print(f"{C_RED}--- Migration pre-processing failed. Please review logs. ---{C_RESET}")
                sys.exit(1)

        is_migration_run = args.migrate
        force_reprocess_once = args.reprocess

        loop_count = 0
        while loop_count < args.max_loops:
            loop_count += 1
            line_separator = "#" * 80
            print(f"\n{C_CYAN}{line_separator}{C_RESET}")
            verification_header = _format_header(f"VERIFICATION CYCLE {loop_count}/{args.max_loops}")
            print(f"{C_CYAN}{verification_header}{C_RESET}")
            print(f"{C_CYAN}{line_separator}{C_RESET}")

            # Determine the state based on the most up-to-date audit.
            state_overall_status, payload_details, granular_audit_results = _get_experiment_state(Path(final_output_dir), end_rep, verbose=False)
            
            # --- Handle state transitions and user prompts ---
            current_action_taken = False # Flag to track if an action was attempted this cycle.
            audit_result_code = AUDIT_ALL_VALID # Initialize, will be set by _run_verify_only_mode if called

            if state_overall_status == "NEW_NEEDED":
                print(f"{C_CYAN}--- Experiment is NEW. Proceeding to create replications. ---{C_RESET}")
                success = _run_new_mode(final_output_dir, args.start_rep, end_rep, args.notes, not args.verbose, orchestrator_script)
                current_action_taken = True
            else: # If not NEW_NEEDED, then the directory is not empty, so it's safe to run a proper audit.
                # Always run and print the audit report for existing experiments to ensure consistent user feedback.
                audit_result_code = _run_verify_only_mode(Path(final_output_dir), end_rep, suppress_exit=True, print_report=True, is_verify_only_cli=False, suppress_external_recommendation=is_migration_run)

                if audit_result_code == AUDIT_NEEDS_MIGRATION:
                    # The audit report provides the full recommendation.
                    # We halt the state machine and exit with the specific code so calling
                    # scripts (like analyze_study.ps1) can react appropriately.
                    print(f"\n{C_RED}Halting due to MIGRATION required status.{C_RESET}")
                    sys.exit(AUDIT_NEEDS_MIGRATION)

                elif audit_result_code == AUDIT_NEEDS_REPAIR:
                    # Distinguish between session-level repair (missing responses) and full replication repair (missing queries, config issues).
                    full_replication_repairs = [d for d in payload_details if d.get("repair_type") == "full_replication_repair"]
                    session_repairs = [d for d in payload_details if d.get("repair_type") == "session_repair"]

                    if full_replication_repairs:
                        repair_type_message = "critical issues (e.g., missing queries/configs). This may involve re-running entire replications."
                    elif session_repairs:
                        repair_type_message = "missing LLM responses. This involves re-running specific LLM sessions."
                    else:
                        repair_type_message = "unspecified issues requiring repair."

                    # Construct the informational message, which will be colored
                    info_message = f"The experiment requires repair due to {repair_type_message}"
                    if is_migration_run:
                        info_message = f"Migration has uncovered issues requiring repair due to {repair_type_message}"

                    # Print the colored message, then the uncolored prompt on a new line after a blank line
                    print(f"\n{C_YELLOW}{info_message}{C_RESET}\n")
                    if _prompt_for_confirmation("Do you wish to proceed? (Y/N): "):
                        if full_replication_repairs:
                            success = _run_full_replication_repair(full_replication_repairs, orchestrator_script, not args.verbose)
                        elif session_repairs: # Only run session repairs if no full replication repairs are needed/attempted
                            success = _run_repair_mode(session_repairs, orchestrator_script, not args.verbose)
                        current_action_taken = True
                    else:
                        print(f"\n{C_RED}Repair aborted by user. Exiting.{C_RESET}")
                        sys.exit(AUDIT_ABORTED_BY_USER)

                elif audit_result_code == AUDIT_NEEDS_REPROCESS or force_reprocess_once:
                    # If forcing a reprocess on a clean experiment, the payload will be empty.
                    # We must populate it with all run directories to ensure they are processed.
                    if force_reprocess_once and not payload_details:
                        print(f"\n{C_YELLOW}Forcing reprocess on a VALIDATED experiment. All runs will be updated.{C_RESET}")
                        all_run_dirs = sorted([p for p in Path(final_output_dir).glob("run_*") if p.is_dir()])
                        payload_details = [{"dir": str(run_dir)} for run_dir in all_run_dirs]

                    confirm = 'Y'
                    # The PowerShell wrappers already prompt the user. This prompt is for direct script execution.
                    proceed = False
                    if not (is_migration_run or force_reprocess_once):
                        # The preceding audit report has already provided context.
                        if _prompt_for_confirmation("\nDo you wish to proceed? (Y/N): "):
                            proceed = True
                    else:
                        # When called by a wrapper with --reprocess or during migration, we proceed automatically.
                        print(f"\n{C_YELLOW}Automatically proceeding with update as part of migration or a forced reprocess run.{C_RESET}")
                        proceed = True
                    
                    if force_reprocess_once: force_reprocess_once = False # Only force once

                    if proceed:
                        success = _run_reprocess_mode(payload_details, args.notes, not args.verbose, orchestrator_script, compile_experiment_script, final_output_dir, log_manager_script)
                        current_action_taken = True
                    else:
                        print(f"\n{C_RED}Update aborted by user. Exiting.{C_RESET}")
                        sys.exit(AUDIT_ABORTED_BY_USER)
                
                elif audit_result_code == AUDIT_ALL_VALID:
                    # If no specific action was triggered and audit is clean, we can finalize.
                    print(f"{C_GREEN}--- Experiment is COMPLETE. Proceeding to finalization. ---{C_RESET}")
                    break # Exit the loop cleanly

                else: # Fallback for unhandled states or logic inconsistencies
                     print(f"{C_RED}--- Unhandled state or inconsistent audit result detected: OverallStatus={state_overall_status}, AuditCode={audit_result_code}. Halting. ---{C_RESET}")
                     sys.exit(1)

            # After attempting an action, check its success and then re-evaluate the state.
            if not success:
                print(f"{C_RED}--- A step failed. Halting experiment manager. Please review logs. ---{C_RESET}")
                sys.exit(1)
            
            # If an action was taken AND it was successful, re-check the state to see if we should break.
            if current_action_taken and success:
                # After a successful action, always run a new audit to show the result.
                print(f"\n{C_CYAN}--- Verifying results after action... ---{C_RESET}")
                final_audit_code = _run_verify_only_mode(Path(final_output_dir), end_rep, suppress_exit=True, print_report=True, is_verify_only_cli=False, suppress_external_recommendation=is_migration_run)

                if final_audit_code == AUDIT_ALL_VALID:
                    print(f"\n{C_GREEN}--- Action successful. The experiment is now complete and will be finalized. ---{C_RESET}")
                    break
                else:
                    # Re-get the text status for the log message, as the audit may have found other issues.
                    new_state_overall_status, _, _ = _get_experiment_state(Path(final_output_dir), end_rep, verbose=False)
                    print(f"\n{C_YELLOW}--- Action successful, but issues persist (Current state: {new_state_overall_status}). Continuing to next verification cycle. ---{C_RESET}")


        if loop_count >= args.max_loops:
            print(f"{C_RED}--- Max loop count reached. Halting to prevent infinite loop. ---{C_RESET}")
            sys.exit(1)

        # --- Finalization Stage ---
        finalization_message = "ALL TASKS COMPLETE. BEGINNING FINALIZATION."
        print("\n" + "#" * 80)
        print(_format_header(finalization_message))
        print("#" * 80)
        
        try:
            log_file_path = os.path.join(final_output_dir, get_config_value(APP_CONFIG, 'Filenames', 'batch_run_log', fallback='batch_run_log.csv'))
            log_message = "Rebuilding batch log..." if os.path.exists(log_file_path) else "Building batch log..."
            
            print(f"\n--- {log_message} ---")
            subprocess.run([sys.executable, log_manager_script, "rebuild", final_output_dir], check=True, capture_output=True)
            
            print("--- Compiling final experiment summary... ---")
            subprocess.run([sys.executable, compile_experiment_script, final_output_dir], check=True, capture_output=True)
            
            print("--- Finalizing batch log with summary... ---")
            subprocess.run([sys.executable, log_manager_script, "finalize", final_output_dir], check=True, capture_output=True)
        except Exception as e:
            logging.error(f"An error occurred during finalization: {e}")
            sys.exit(1)

        print(f"\n{C_GREEN}Experiment run finished successfully for:{C_RESET}")
        print(f"{C_GREEN}{final_output_dir}{C_RESET}")

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}--- Operation interrupted by user (Ctrl+C). Exiting gracefully. ---{C_RESET}", file=sys.stderr)
        sys.exit(AUDIT_ABORTED_BY_USER)

if __name__ == "__main__":
    main()

# === End of src/experiment_manager.py ===
