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
# Filename: src/experiment_auditor.py

"""
Read-Only Auditor for a Single Experiment.

This script performs a comprehensive, read-only audit of a single experiment
directory. It is designed to be the single source of truth for determining the
status of an experiment for user-facing reports.

It checks all expected files, validates data integrity, and compares results
against manifests. Based on its findings, it prints a detailed, colored report
to the console and exits with a specific status code that can be interpreted by
wrapper scripts.

It is invoked by `audit_experiment.ps1` and `repair_experiment.ps1`.
"""

import sys
import os
import logging
import glob
import json
import re
import configparser
from configparser import ConfigParser
from pathlib import Path
import argparse

# --- Setup ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

# Audit exit codes for wrapper scripts to interpret
AUDIT_ALL_VALID = 0
AUDIT_NEEDS_REPROCESS = 1
AUDIT_NEEDS_REPAIR = 2
AUDIT_NEEDS_MIGRATION = 3
AUDIT_NEEDS_AGGREGATION = 4

#==============================================================================
#   CENTRAL FILE MANIFEST & REPORT CRITERIA
#==============================================================================
FILE_MANIFEST = {
    "config": {
        "path": "config.ini.archived",
        "type": "config_file",
        "required_keys": {
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
    "response_json_files": {"path": "session_responses/llm_response_*_full.json", "pattern": r"llm_response_(\d+)_full\.json"},
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

REPORT_REQUIRED_NESTED_KEYS = {
    "positional_bias_metrics": {"top1_pred_bias_std", "true_false_score_diff"}
}

# --- Verification Helper Functions ---

def _format_header(message, total_width=80):
    """Formats a message into a symmetrical header line with ### bookends."""
    prefix = "###"
    suffix = "###"
    content = f" {message} ".center(total_width - len(prefix) - len(suffix), ' ')
    return f"{prefix}{content}{suffix}"

def _get_file_indices(run_path: Path, spec: dict) -> set[int]:
    """Extracts the numerical indices from a set of files using regex."""
    indices = set()
    regex = re.compile(spec["pattern"])
    files = run_path.glob(spec["path"])
    for f in files:
        match = regex.match(f.name)
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

def _check_config_manifest(run_path: Path, k_expected: int, m_expected: int):
    cfg_path = run_path / FILE_MANIFEST["config"]["path"]
    required_keys_map = FILE_MANIFEST["config"]["required_keys"]

    try:
        cfg = ConfigParser()
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg.read_file(f)
        if not cfg.sections():
            return "CONFIG_MALFORMED"
    except Exception:
        return "CONFIG_MALFORMED"

    def _get_value(canonical_name, value_type=str):
        for section, key in required_keys_map[canonical_name]:
            if cfg.has_option(section, key):
                try:
                    if value_type is int: return cfg.getint(section, key)
                    if value_type is float: return cfg.getfloat(section, key)
                    return cfg.get(section, key)
                except (configparser.Error, ValueError):
                    continue
        return None

    missing_keys = [name for name in required_keys_map if _get_value(name) is None]
    if missing_keys:
        return f"CONFIG_MISSING_KEYS: {', '.join(missing_keys)}"

    k_cfg = _get_value("num_subjects", value_type=int)
    m_cfg = _get_value("num_trials", value_type=int)

    mismatched = []
    if k_cfg != k_expected: mismatched.append(f"k (expected {k_expected}, found {k_cfg})")
    if m_cfg != m_expected: mismatched.append(f"m (expected {m_expected}, found {m_cfg})")
    if mismatched: return f"CONFIG_MISMATCH: {', '.join(mismatched)}"
    return "VALID"

def _check_file_set(run_path: Path, spec: dict, expected_count: int):
    glob_pattern = spec["path"]
    regex_pattern = spec.get("pattern")
    all_files_in_dir = list(run_path.glob(glob_pattern))
    
    if regex_pattern:
        regex = re.compile(regex_pattern)
        actual = [f for f in all_files_in_dir if regex.match(f.name)]
    else:
        actual = all_files_in_dir

    label = glob_pattern.split("/", 1)[0]
    if not actual: return f"{label.upper()}_MISSING"
    count = len(actual)
    if count < expected_count: return f"{label.upper()}_INCOMPLETE"
    if count > expected_count: return f"{label.upper()}_TOO_MANY"
    return "VALID"

def _check_analysis_files(run_path: Path, expected_entries: int, k_value: int):
    scores_p = run_path / FILE_MANIFEST["scores_file"]["path"]
    mappings_p = run_path / FILE_MANIFEST["mappings_file"]["path"]
    if not all(p.exists() for p in [scores_p, mappings_p]):
        return "ANALYSIS_FILES_MISSING"
    try:
        n_mappings = _count_lines_in_file(mappings_p, skip_header=True)
        n_scores = _count_matrices_in_file(scores_p, k_value)
    except Exception:
        return "ANALYSIS_DATA_MALFORMED"
    if n_scores != expected_entries or n_mappings != expected_entries:
        return "ANALYSIS_DATA_INCOMPLETE"
    return "VALID"

def _check_report(run_path: Path):
    reports = sorted(run_path.glob("replication_report_*.txt"))
    if not reports: return "REPORT_MISSING"
    latest = reports[-1]
    try:
        text = latest.read_text(encoding="utf-8")
        if "<<<METRICS_JSON_START>>>" not in text or "<<<METRICS_JSON_END>>>" not in text:
            return "REPORT_MALFORMED"
        start = text.index("<<<METRICS_JSON_START>>>")
        end = text.index("<<<METRICS_JSON_END>>>")
        j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
    except Exception:
        return "REPORT_MALFORMED"
    missing_metrics = REPORT_REQUIRED_METRICS - j.keys()
    if missing_metrics:
        return f"REPORT_INCOMPLETE_METRICS: {', '.join(sorted(missing_metrics))}"
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

    name_match = re.search(r"sbj-(\d+)_trl-(\d+)", run_path.name)
    if not run_path.name.startswith("run_") or not name_match:
        status_details = [f"{run_path.name} does not match required run_*_sbj-NN_trl-NNN* pattern"]
        return "INVALID_NAME", status_details
    k_expected, m_expected = int(name_match.group(1)), int(name_match.group(2))

    stat_cfg = _check_config_manifest(run_path, k_expected, m_expected)
    if stat_cfg != "VALID": status_details.append(stat_cfg)
    else: status_details.append("config OK")

    stat_q = _check_file_set(run_path, FILE_MANIFEST["query_files"], m_expected)
    if stat_q != "VALID": status_details.append(stat_q)
    else: status_details.append("queries OK")

    aggregated_mappings_path = run_path / FILE_MANIFEST["aggregated_mappings_file"]["path"]
    if not aggregated_mappings_path.exists():
        status_details.append("AGGREGATED_MAPPINGS_MISSING")

    manifest_spec = FILE_MANIFEST["trial_manifests"]
    if list(run_path.glob(manifest_spec["path"])):
        stat_q_manifests = _check_file_set(run_path, manifest_spec, m_expected)
        if stat_q_manifests != "VALID": status_details.append("MANIFESTS_INCOMPLETE")

    response_details = []
    stat_r_txt = _check_file_set(run_path, FILE_MANIFEST["response_files"], m_expected)
    stat_r_json = _check_file_set(run_path, FILE_MANIFEST["response_json_files"], m_expected)

    if stat_r_txt != "VALID": response_details.append(f"TXT: {stat_r_txt}")
    if stat_r_json != "VALID": response_details.append(f"JSON: {stat_r_json}")

    if not response_details:
        query_indices = _get_file_indices(run_path, FILE_MANIFEST["query_files"])
        response_txt_indices = _get_file_indices(run_path, FILE_MANIFEST["response_files"])
        response_json_indices = _get_file_indices(run_path, FILE_MANIFEST["response_json_files"])
        mismatches = []
        if query_indices != response_txt_indices: mismatches.append("txt")
        if query_indices != response_json_indices: mismatches.append("json")
        if mismatches: response_details.append(f"QUERY_RESPONSE_INDEX_MISMATCH ({','.join(mismatches)})")

    if response_details: status_details.append(f"SESSION_RESPONSES_ISSUE: {'; '.join(response_details)}")
    else: status_details.append("responses OK")

    analysis_ok = True
    if not (run_path / "REPLICATION_results.csv").exists():
        status_details.append("REPLICATION_RESULTS_MISSING")
        analysis_ok = False
    
    stat_rep = _check_report(run_path)
    if stat_rep != "VALID":
        status_details.append(stat_rep)
        analysis_ok = False

    if analysis_ok:
        try:
            latest_report = sorted(run_path.glob("replication_report_*.txt"))[-1]
            text = latest_report.read_text(encoding="utf-8")
            start = text.index("<<<METRICS_JSON_START>>>")
            end = text.index("<<<METRICS_JSON_END>>>")
            j = json.loads(text[start + len("<<<METRICS_JSON_START>>>"):end])
            expected_entries = j.get("n_valid_responses")
            if expected_entries is not None and expected_entries >= 0:
                stat_a = _check_analysis_files(run_path, expected_entries, k_expected)
                if stat_a != "VALID":
                    status_details.append(stat_a)
                    analysis_ok = False
            else:
                status_details.append("ANALYSIS_SKIPPED_BAD_REPORT")
                analysis_ok = False
        except (IndexError, ValueError, KeyError):
            status_details.append("ANALYSIS_SKIPPED_BAD_REPORT")
            analysis_ok = False
    if analysis_ok:
        status_details.append("analysis OK")

    failures = [d for d in status_details if not d.endswith(" OK")]
    if not failures:
        return "VALIDATED", status_details
    if len(failures) >= 2:
        return "RUN_CORRUPTED", status_details

    failure = failures[0]
    if "INVALID_NAME" in failure: return "INVALID_NAME", status_details
    if "CONFIG" in failure: return "CONFIG_ISSUE", status_details
    if any(err in failure for err in ["SESSION_QUERIES", "MAPPINGS_MISSING", "MANIFESTS_INCOMPLETE"]):
        return "QUERY_ISSUE", status_details
    if any(err in failure for err in ["SESSION_RESPONSES", "QUERY_RESPONSE_INDEX_MISMATCH"]):
        return "RESPONSE_ISSUE", status_details
    
    return "ANALYSIS_ISSUE", status_details

def _verify_experiment_level_files(target_dir: Path) -> tuple[bool, list[str]]:
    is_complete = True
    details = []
    required_files = ["batch_run_log.csv", "EXPERIMENT_results.csv"]
    for filename in required_files:
        if not (target_dir / filename).exists():
            is_complete = False
            details.append(f"MISSING: {filename}")
    log_path = target_dir / "batch_run_log.csv"
    if log_path.exists():
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                if "BatchSummary" not in f.read():
                    is_complete = False
                    details.append("batch_run_log.csv NOT FINALIZED")
        except Exception:
            is_complete = False
            details.append("batch_run_log.csv UNREADABLE")
    return is_complete, details

def main():
    parser = argparse.ArgumentParser(description="Read-only auditor for experiments.")
    parser.add_argument('target_dir', help="The target directory for the experiment.")
    parser.add_argument('--non-interactive', action='store_true', help="Suppress user-facing recommendation text.")
    parser.add_argument('--quiet', action='store_true', help="Suppress all non-essential output. For scripting.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()

    use_color = sys.stdout.isatty() or args.force_color
    C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = ('','','','','')
    if use_color:
        C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = '\033[96m', '\033[92m', '\033[93m', '\033[91m', '\033[0m'

    target_dir = Path(args.target_dir)
    if not args.quiet:
        relative_path = os.path.relpath(target_dir, PROJECT_ROOT)
        if not args.non_interactive:
            print(f"\n{C_CYAN}{'#'*80}{C_RESET}")
            print(f"{C_CYAN}{_format_header('Running Experiment Audit')}{C_RESET}")
            print(f"{C_CYAN}{'#'*80}{C_RESET}")
        print(f"\n--- Verifying Data Completeness in: ---\n{relative_path}")

    run_dirs = sorted([p for p in target_dir.glob("run_*") if p.is_dir()])
    audit_result_code = AUDIT_ALL_VALID

    if not run_dirs:
        if not args.quiet:
            print(f"\n{C_YELLOW}Diagnosis: No 'run_*' directories found.{C_RESET}")
        sys.exit(AUDIT_NEEDS_MIGRATION)

    all_runs_data = [
        {"name": run.name, "status": status, "details": "; ".join(details)}
        for run in run_dirs
        for status, details in [_verify_single_run_completeness(run)]
    ]
    
    unique_statuses = {run['status'] for run in all_runs_data}
    
    critical_errors = {"INVALID_NAME", "CONFIG_ISSUE", "QUERY_ISSUE", "RESPONSE_ISSUE"}
    found_critical_types = unique_statuses.intersection(critical_errors)

    if "RUN_CORRUPTED" in unique_statuses or len(found_critical_types) > 1:
        audit_result_code = AUDIT_NEEDS_MIGRATION
    elif len(found_critical_types) == 1:
        audit_result_code = AUDIT_NEEDS_REPAIR
    elif "ANALYSIS_ISSUE" in unique_statuses:
        audit_result_code = AUDIT_NEEDS_REPROCESS
    
    exp_complete, _ = _verify_experiment_level_files(target_dir)
    if audit_result_code == AUDIT_ALL_VALID and not exp_complete:
        audit_result_code = AUDIT_NEEDS_AGGREGATION

    if not args.quiet:
        MAX_NAME_WIDTH = 40
        max_name_len = min(max((len(run['name']) for run in all_runs_data), default=20), MAX_NAME_WIDTH)
        print(f"\n{'Run Directory':<{max_name_len}} {'Status':<20} {'Details'}")
        print(f"{'-'*max_name_len} {'-'*20} {'-'*45}")
        for run in all_runs_data:
            display_name = run['name'] if len(run['name']) <= max_name_len else run['name'][:max_name_len-3] + "..."
            status_color = C_GREEN if run['status'] == "VALIDATED" else C_RED
            print(f"{display_name:<{max_name_len}} {status_color}{run['status']:<20}{C_RESET} {run['details']}")

        messages = {
            AUDIT_NEEDS_MIGRATION: ("Experiment needs MIGRATION.", "Run `migrate_experiment.ps1` to create an upgraded copy."),
            AUDIT_NEEDS_REPAIR: ("Experiment needs REPAIR.", "Run `repair_experiment.ps1` to fix the experiment."),
            AUDIT_NEEDS_REPROCESS: ("Experiment needs UPDATE.", "Run `repair_experiment.ps1` to update the experiment."),
            AUDIT_NEEDS_AGGREGATION: ("Experiment needs FINALIZATION.", "Run `repair_experiment.ps1` to finalize it."),
            AUDIT_ALL_VALID: ("PASSED. Experiment is complete and valid.", "No further action is required.")
        }
        color_map = {0: C_GREEN, 1: C_RED, 2: C_RED, 3: C_RED, 4: C_YELLOW}
        
        audit_message, audit_recommendation = messages[audit_result_code]
        audit_color = color_map[audit_result_code]

        line = audit_color + ("#" * 80) + C_RESET
        print(f"\n{line}")
        print(f"{audit_color}{_format_header(f'Audit Result: {audit_message}')}{C_RESET}")
        if not args.non_interactive:
            print(f"{audit_color}{_format_header(f'Recommendation: {audit_recommendation}')}{C_RESET}")
        print(f"{line}\n")

    sys.exit(audit_result_code)

if __name__ == "__main__":
    main()

# === End of src/experiment_auditor.py ===
