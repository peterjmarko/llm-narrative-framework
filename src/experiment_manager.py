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
Backend State-Machine Controller for a Single Experiment.

This script is the high-level, action-oriented backend controller for managing
the lifecycle of a single experiment. It is invoked by user-facing PowerShell
wrappers (e.g., `new_experiment.ps1`, `repair_experiment.ps1`).

It operates as a state machine: it determines an experiment's status by
importing and calling the `get_experiment_state` function from the
`experiment_auditor` module, and then automatically takes the correct action
(e.g., creating, repairing, or reprocessing runs) to bring the experiment to
completion.

Its core function is to orchestrate `orchestrate_replication.py` to execute
the required changes for individual replication runs.
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

def _create_new_experiment_directory(colors):
    """Generates a unique name and creates a new experiment directory."""
    C_CYAN = colors['cyan']
    C_RESET = colors['reset']
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    base_output = get_config_value(APP_CONFIG, 'General', 'base_output_dir', fallback='output')
    new_exp_subdir = get_config_value(APP_CONFIG, 'General', 'new_experiments_subdir', fallback='new_experiments')
    exp_prefix = get_config_value(APP_CONFIG, 'General', 'experiment_dir_prefix', fallback='experiment_')
    base_path = os.path.join(PROJECT_ROOT, base_output, new_exp_subdir)
    final_output_dir = os.path.join(base_path, f"{exp_prefix}{timestamp}")
    
    os.makedirs(final_output_dir)
    # This message is now clearer for the new_experiment.ps1 workflow.
    relative_path = os.path.relpath(final_output_dir, PROJECT_ROOT)
    print(f"{C_CYAN}New experiment directory created:\n{relative_path}{C_RESET}\n")
    
    return final_output_dir

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
except ImportError as e:
    print(f"FATAL: Could not import config_loader.py. Error: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from config_loader import APP_CONFIG, get_config_value, PROJECT_ROOT
    from experiment_auditor import get_experiment_state, _get_file_indices, FILE_MANIFEST
except ImportError as e:
    print(f"FATAL: Could not import a required module. Error: {e}", file=sys.stderr)
    sys.exit(1)

# This constant is specific to the manager's internal flow when a user aborts.
AUDIT_ABORTED_BY_USER = 99

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

def _run_new_mode(target_dir, start_rep, end_rep, notes, verbose, orchestrator_script, colors):
    """Executes 'NEW' mode by calling the orchestrator for each replication."""
    C_CYAN, C_YELLOW, C_RESET = colors['cyan'], colors['yellow'], colors['reset']

    run_dirs = glob.glob(os.path.join(target_dir, 'run_*_rep-*'))
    completed_reps = {int(re.search(r'_rep-(\d+)_', os.path.basename(d)).group(1))
                      for d in run_dirs if re.search(r'_rep-(\d+)_', os.path.basename(d))}
                      
    reps_to_run = [r for r in range(start_rep, end_rep + 1) if r not in completed_reps]
    if not reps_to_run:
        print("All required replications already exist. Nothing to do in NEW mode.")
        return True

    print(f"Will create {len(reps_to_run)} new replication(s), from {min(reps_to_run)} to {max(reps_to_run)}.")
    batch_start_time = time.time()
    
    for i, rep_num in enumerate(reps_to_run):
        header_text = f" RUNNING REPLICATION {rep_num} ({i + 1} of {len(reps_to_run)} in this batch) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")
        
        cmd_orch = [sys.executable, orchestrator_script, "--replication_num", str(rep_num), "--base_output_dir", target_dir]
        if notes: cmd_orch.extend(["--notes", notes])
        if verbose: cmd_orch.append("--verbose")
        
        try:
            # Use Popen to stream stdout in real-time while capturing stderr.
            proc = subprocess.Popen(cmd_orch, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', errors='replace')
            
            # Stream and print stdout line by line as it comes in.
            for line in proc.stdout:
                print(line, end='', flush=True)

            # Wait for the process to complete and get the final return code and any stderr output.
            proc.wait()
            stderr_output = proc.stderr.read()

            if proc.returncode != 0:
                # If the process failed, manually raise a CalledProcessError with the captured stderr.
                raise subprocess.CalledProcessError(proc.returncode, proc.args, stderr=stderr_output)

        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Orchestrator for replication {rep_num} failed or was interrupted.")
            if isinstance(e, subprocess.CalledProcessError):
                # Print the captured stderr from the failed orchestrator process.
                # This will contain the full traceback from the underlying script.
                if e.stderr:
                    print(e.stderr, file=sys.stderr)
            if isinstance(e, KeyboardInterrupt):
                # If interrupted, exit the manager immediately.
                sys.exit(1)
            # For any failure, immediately stop the batch.
            return False

        elapsed = time.time() - batch_start_time
        avg_time = elapsed / (i + 1)
        remaining_reps = len(reps_to_run) - (i + 1)
        time_remaining = remaining_reps * avg_time
        eta = datetime.datetime.now() + datetime.timedelta(seconds=time_remaining)
        print(f"\n{C_YELLOW}Time Elapsed: {str(datetime.timedelta(seconds=int(elapsed)))} | Time Remaining: {str(datetime.timedelta(seconds=int(time_remaining)))} | ETA: {eta.strftime('%H:%M:%S')}{C_RESET}")

    return True

# This '_session_worker' function is no longer needed here and has been moved into orchestrate_replication.py's logic.

def _run_repair_mode(runs_to_repair, orchestrator_script_path, verbose, colors):
    """Delegates repair work to the orchestrator for each failed run."""
    C_YELLOW = colors['yellow']
    C_CYAN = colors['cyan']
    C_RESET = colors['reset']
    print(f"{C_YELLOW}--- Entering REPAIR Mode: Fixing {len(runs_to_repair)} run(s) with missing responses ---{C_RESET}")

    for i, run_info in enumerate(runs_to_repair):
        run_dir = run_info["dir"]
        failed_indices = run_info.get("failed_indices", [])
        if not failed_indices:
            continue

        header_text = f" REPAIRING REPLICATION {os.path.basename(run_dir)} ({i+1}/{len(runs_to_repair)}) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")
        
        # Call the orchestrator in --reprocess mode and pass the specific indices to fix.
        # The orchestrator is now responsible for the parallel execution.
        cmd = [
            sys.executable, orchestrator_script_path,
            "--reprocess",
            "--run_output_dir", run_dir,
            "--indices"
        ] + [str(i) for i in failed_indices]
        
        if verbose:
            cmd.append("--verbose")

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', errors='replace')
            for line in proc.stdout:
                print(line, end='', flush=True)
            proc.wait()
            stderr_output = proc.stderr.read()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, proc.args, stderr=stderr_output)
        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Repair failed for {os.path.basename(run_dir)}.")
            if isinstance(e, subprocess.CalledProcessError) and e.stderr:
                print(e.stderr, file=sys.stderr)
            if isinstance(e, KeyboardInterrupt):
                sys.exit(AUDIT_ABORTED_BY_USER)
            return False # A single failure halts the entire repair operation.
            
    return True

def _run_full_replication_repair(runs_to_repair, orchestrator_script, quiet, colors):
    """Deletes and fully regenerates runs with critical issues (e.g., missing queries, config issues)."""
def _run_config_repair(runs_to_repair, restore_config_script, colors):
    """Repairs missing or malformed config.ini.archived files by restoring them from reports."""
    C_CYAN, C_YELLOW, C_RESET = colors['cyan'], colors['yellow'], colors['reset']
    print(f"{C_YELLOW}--- Entering CONFIG REPAIR Mode: Restoring config for {len(runs_to_repair)} run(s) ---{C_RESET}")
    
    for run_info in runs_to_repair:
        run_dir_path = run_info["dir"]
        print(f"\n- Restoring config for {os.path.basename(run_dir_path)}...")
        try:
            cmd = [sys.executable, restore_config_script, run_dir_path]
            # Capture output unless there's an error, to keep the log clean.
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  {C_CYAN}Success.{C_RESET}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to restore config for {os.path.basename(run_dir_path)}.")
            logging.error(f"Stderr:\n{e.stderr}")
            return False # Halt on failure
    return True

def _run_full_replication_repair(runs_to_repair, orchestrator_script, quiet, colors):
    """Deletes and fully regenerates runs with critical issues (e.g., missing queries, config issues)."""
    C_YELLOW = colors['yellow']
    C_RED = colors['red']
    C_CYAN = colors['cyan']
    C_RESET = colors['reset']
    print(f"{C_YELLOW}--- Entering FULL REPLICATION REPAIR Mode: Deleting and regenerating {len(runs_to_repair)} run(s) with critical issues ---{C_RESET}")

    for i, run_info in enumerate(runs_to_repair):
        run_dir_path_str = run_info["dir"]
        run_dir_path = Path(run_dir_path_str)
        run_basename = os.path.basename(run_dir_path_str)
        
        # Initialize capture_output_flag here to ensure it's always defined.
        capture_output_flag = False 

        header_text = f" REGENERATING REPLICATION {run_basename} ({i+1}/{len(runs_to_repair)}) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")

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

def _is_patching_needed(run_dirs):
    """Checks if any run is missing an archived config, indicating a legacy experiment."""
    for run_dir in run_dirs:
        if not (run_dir / "config.ini.archived").exists():
            return True
    return False

def _run_migrate_mode(target_dir, patch_script, orchestrator_script, colors, verbose=False):
    """
    Executes a one-time migration process for a legacy experiment directory.
    This mode is destructive and will delete old artifacts.
    """
    C_GREEN = colors['green']
    C_YELLOW = colors['yellow']
    C_RESET = colors['reset']
    relative_path = os.path.relpath(target_dir, PROJECT_ROOT)
    print(f"{C_YELLOW}--- Entering MIGRATE Mode: Upgrading experiment at: ---{C_RESET}")
    print(f"{C_YELLOW}{relative_path}{C_RESET}")
    run_dirs = sorted([p for p in target_dir.glob("run_*") if p.is_dir()])

    # Sub-step 1: Clean Artifacts (Run this first to remove corrupt files)
    print("\n- Cleaning old summary files and analysis artifacts...")
    try:
        files_to_delete = ["final_summary_results.csv", "batch_run_log.csv", "EXPERIMENT_results.csv"]
        for file in files_to_delete:
            file_path = target_dir / file
            if file_path.exists():
                print(f"  - Deleting old '{file_path.name}'")
                file_path.unlink()

        for run_dir in run_dirs:
            # Clean analysis_inputs to force full regeneration
            analysis_inputs_path = run_dir / "analysis_inputs"
            if analysis_inputs_path.is_dir():
                shutil.rmtree(analysis_inputs_path)
        print("  - Cleaning complete.")
    except Exception as e:
        logging.error(f"Failed to clean artifacts: {e}")
        return False

    # Sub-step 2: Conditionally Patch Configs
    if _is_patching_needed(run_dirs):
        print("\n- Legacy experiment detected. Patching configuration files...")
        try:
            subprocess.run([sys.executable, patch_script, str(target_dir)], check=True, capture_output=True, text=True)
            print("  - Patching complete.")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to patch configs. Stderr:\n{e.stderr}")
            return False
    else:
        print("\n- Modern experiment format detected. Skipping config patching.")


    # Sub-step 3: Reprocess Each Replication
    print(f"\n- Reprocessing {len(run_dirs)} individual runs to generate modern reports...")
    all_reprocessed_successfully = True
    for run_dir in tqdm(run_dirs, desc="Reprocessing Runs", ncols=80):
        cmd = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", str(run_dir)]
        if verbose: cmd.append("--verbose")
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Failed to reprocess {run_dir.name}. Stderr:\n{result.stderr}")
            all_reprocessed_successfully = False
            break # Exit the loop immediately on first failure

    if not all_reprocessed_successfully:
        return False # Signal failure to the main manager loop
    
    print("  - Reprocessing complete.")

    print(f"\n{C_GREEN}--- Migration pre-processing complete. Proceeding to finalization. ---{C_RESET}")
    return True

def _run_finalization(final_output_dir, script_paths, colors):
    """Compiles all results and finalizes logs for a complete experiment."""
    C_CYAN, _, _, _, C_RESET = colors.values()

    finalization_message = "ALL TASKS COMPLETE. BEGINNING FINALIZATION."
    print(f"\n{C_CYAN}{'#' * 80}{C_RESET}")
    print(f"{C_CYAN}{_format_header(finalization_message)}{C_RESET}")
    print(f"{C_CYAN}{'#' * 80}{C_RESET}")
    
    try:
        log_file_path = os.path.join(final_output_dir, get_config_value(APP_CONFIG, 'Filenames', 'batch_run_log', fallback='batch_run_log.csv'))
        log_message = "Rebuilding batch log..." if os.path.exists(log_file_path) else "Building batch log..."
        
        print(f"\n--- {log_message} ---")
        subprocess.run([sys.executable, script_paths['log_manager'], "rebuild", final_output_dir], check=True, capture_output=True)
        
        print("--- Compiling final experiment summary... ---")
        subprocess.run([sys.executable, script_paths['compile_experiment'], final_output_dir], check=True, capture_output=True)
        
        print("--- Finalizing batch log with summary... ---")
        subprocess.run([sys.executable, script_paths['log_manager'], "finalize", final_output_dir], check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        # Provide more context on subprocess failures
        logging.error("A child process failed during the finalization stage.")
        # Use os.path.basename to keep the command clean and readable
        command_str = " ".join([os.path.basename(arg) if i == 1 else arg for i, arg in enumerate(e.cmd)])
        logging.error(f"Command: {command_str}")
        if e.stderr:
            logging.error(f"Stderr:\n{e.stderr}")
        if e.stdout:
            logging.error(f"Stdout:\n{e.stdout}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred during finalization: {e}")
        sys.exit(1)

def _run_reprocess_mode(runs_to_reprocess, notes, verbose, orchestrator_script, compile_script, target_dir, log_manager_script, colors):
    """Executes 'REPROCESS' mode to update analysis artifacts for specified runs."""
    C_CYAN = colors['cyan']
    C_YELLOW = colors['yellow']
    C_RESET = colors['reset']
    C_GREEN = colors['green']
    print(f"{C_YELLOW}--- Entering REPROCESS Mode: Updating analysis for {len(runs_to_reprocess)} replication(s) ---{C_RESET}")

    for i, run_info in enumerate(runs_to_reprocess):
        run_dir = run_info["dir"]
        header_text = f" RE-PROCESSING {os.path.basename(run_dir)} ({i+1}/{len(runs_to_reprocess)}) "
        print(f"\n{C_CYAN}{'='*80}{C_RESET}")
        print(f"{C_CYAN}{header_text.center(78)}{C_RESET}")
        print(f"{C_CYAN}{'='*80}{C_RESET}")

        cmd_orch = [sys.executable, orchestrator_script, "--reprocess", "--run_output_dir", run_dir]
        if verbose: cmd_orch.append("--verbose")
        if notes: cmd_orch.extend(["--notes", notes])

        try:
            proc = subprocess.Popen(cmd_orch, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', errors='replace')
            for line in proc.stdout:
                print(line, end='', flush=True)
            proc.wait()
            stderr_output = proc.stderr.read()
            if proc.returncode != 0:
                raise subprocess.CalledProcessError(proc.returncode, proc.args, stderr=stderr_output)
        except (subprocess.CalledProcessError, KeyboardInterrupt) as e:
            logging.error(f"Reprocessing failed for {os.path.basename(run_dir)}.")
            if isinstance(e, subprocess.CalledProcessError) and e.stderr:
                print(e.stderr, file=sys.stderr)
            if isinstance(e, KeyboardInterrupt):
                sys.exit(AUDIT_ABORTED_BY_USER)
            return False

    # The main loop will handle the final aggregation.
    print(f"\n{C_GREEN}--- All replications reprocessed successfully. ---{C_RESET}")
    return True

def _setup_environment_and_paths():
    """Parses args, sets up colors, paths, and the experiment directory."""
    parser = argparse.ArgumentParser(description="State-machine controller for running experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="Optional. The target directory for the experiment. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1, help="First replication number for new runs.")
    parser.add_argument('--end-rep', type=int, default=None, help="Last replication number for new runs.")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the reports.')
    parser.add_argument('--max-loops', type=int, default=10, help="Safety limit for state-machine loops.")
    parser.add_argument('--migrate', action='store_true', help="Run a one-time migration workflow for a legacy experiment directory.")
    parser.add_argument('--reprocess', action='store_true', help="Force reprocessing of all runs in an experiment, then finalize.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS) # Hidden from user help
    args = parser.parse_args()

    # --- Color setup ---
    use_color = sys.stdout.isatty() or args.force_color
    C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = ('', '', '', '', '')
    if use_color:
        C_CYAN = '\033[96m'
        C_GREEN = '\033[92m'
        C_YELLOW = '\033[93m'
        C_RED = '\033[91m'
        C_RESET = '\033[0m'
    colors = { 'cyan': C_CYAN, 'green': C_GREEN, 'yellow': C_YELLOW, 'red': C_RED, 'reset': C_RESET }

    # --- Script path setup ---
    script_paths = {
        'orchestrator': os.path.join(PROJECT_ROOT, "src", "orchestrate_replication.py"),
        'compile_experiment': os.path.join(PROJECT_ROOT, "src", 'compile_experiment_results.py'),
        'log_manager': os.path.join(PROJECT_ROOT, "src", 'replication_log_manager.py'),
        'patch': os.path.join(PROJECT_ROOT, "src", "patch_old_experiment.py"),
        'restore_config': os.path.join(PROJECT_ROOT, "src", "restore_config.py")
    }

    # --- Directory setup ---
    if args.target_dir:
        final_output_dir = os.path.abspath(args.target_dir)
        if not os.path.exists(final_output_dir):
            if args.verify_only or args.reprocess or args.migrate:
                print(f"\n{C_RED}Directory not found:{C_RESET}\n{final_output_dir}")
                sys.exit(1)
            os.makedirs(final_output_dir)
            print(f"\nCreated specified target directory:\n{final_output_dir}")
    else:
        if args.verify_only or args.reprocess or args.migrate:
            print(f"\n{C_RED}Error: --verify_only, --reprocess, and --migrate flags require a target directory.{C_RESET}")
            sys.exit(1)
        # Pass the individual color vars for now to avoid breaking _create_new_experiment_directory's signature
        final_output_dir = _create_new_experiment_directory(C_CYAN, C_RESET)

    # --- Config value setup ---
    config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int, fallback=30)
    end_rep = args.end_rep if args.end_rep is not None else config_num_reps

    return args, final_output_dir, script_paths, colors, end_rep

def main():
    """
    Main entry point for the experiment manager script.

    Orchestrates the entire experiment lifecycle by:
    1. Setting up the environment, paths, and arguments.
    2. Running the main state-machine loop to create, repair, or update the experiment.
    3. Finalizing the experiment by compiling results and logs.
    """
    parser = argparse.ArgumentParser(description="State-machine controller for running experiments.")
    parser.add_argument('target_dir', nargs='?', default=None,
                        help="Optional. The target directory for the experiment. If not provided, a unique directory will be created.")
    parser.add_argument('--start-rep', type=int, default=1, help="First replication number for new runs.")
    parser.add_argument('--end-rep', type=int, default=None, help="Last replication number for new runs.")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose per-replication status updates.')
    parser.add_argument('--notes', type=str, help='Optional notes for the reports.')
    parser.add_argument('--max-loops', type=int, default=10, help="Safety limit for state-machine loops.")
    parser.add_argument('--migrate', action='store_true', help="Run a one-time migration workflow for a legacy experiment directory.")
    parser.add_argument('--reprocess', action='store_true', help="Force reprocessing of all runs in an experiment, then finalize.")
    parser.add_argument('--force-color', action='store_true', help=argparse.SUPPRESS) # Hidden from user help
    parser.add_argument('--non-interactive', action='store_true', help="Run in non-interactive mode, suppressing user prompts for confirmation.")
    parser.add_argument('--quiet', action='store_true', help="Suppress all non-essential output from the audit. Used for scripting.")
    args = parser.parse_args()

    # Define color constants, defaulting to empty strings
    C_CYAN, C_GREEN, C_YELLOW, C_RED, C_RESET = ('', '', '', '', '')
    use_color = sys.stdout.isatty() or args.force_color
    if use_color:
        C_CYAN = '\033[96m'
        C_GREEN = '\033[92m'
        C_YELLOW = '\033[93m'
        C_RED = '\033[91m'
        C_RESET = '\033[0m'

    # --- Script Paths ---
    # --- Bundle script paths and colors for cleaner function calls ---
    script_paths = {
        'orchestrator': os.path.join(PROJECT_ROOT, "src", "orchestrate_replication.py"),
        'auditor': os.path.join(PROJECT_ROOT, "src", "experiment_auditor.py"),
        'compile_experiment': os.path.join(PROJECT_ROOT, "src", 'compile_experiment_results.py'),
        'log_manager': os.path.join(PROJECT_ROOT, "src", 'replication_log_manager.py'),
        'patch': os.path.join(PROJECT_ROOT, "src", "patch_old_experiment.py"),
        'restore_config': os.path.join(PROJECT_ROOT, "src", "restore_config.py")
    }
    colors = {
        'cyan': C_CYAN, 'green': C_GREEN, 'yellow': C_YELLOW, 'red': C_RED, 'reset': C_RESET
    }

    try:
        if args.target_dir:
            final_output_dir = os.path.abspath(args.target_dir)
            if not os.path.exists(final_output_dir):
                # Cannot reprocess or migrate a non-existent directory.
                if args.reprocess or args.migrate:
                    print(f"\n{C_RED}Directory not found:{C_RESET}\n{final_output_dir}")
                    sys.exit(1)
                # If a specific target is given but doesn't exist, create it.
                os.makedirs(final_output_dir)
                relative_path = os.path.relpath(final_output_dir, PROJECT_ROOT)
                print(f"\nCreated specified target directory:\n{relative_path}")
        else:
            # If no target is given, we are explicitly in "new experiment" mode.
            # This mode is incompatible with flags that operate on existing data.
            if args.reprocess or args.migrate:
                print(f"\n{C_RED}Error: --reprocess, and --migrate flags require a target directory.{C_RESET}")
                sys.exit(1)
            final_output_dir = _create_new_experiment_directory(colors)

        config_num_reps = get_config_value(APP_CONFIG, 'Study', 'num_replications', value_type=int, fallback=30)
        end_rep = args.end_rep if args.end_rep is not None else config_num_reps

        # --- Workflow Branching: Handle --migrate as a special one-shot process ---
        if args.migrate:
            # The migrate workflow is a single pass: preprocess, then finalize.
            if not _run_migrate_mode(Path(final_output_dir), script_paths['patch'], script_paths['orchestrator'], colors, args.verbose):
                print(f"{C_RED}--- Migration pre-processing failed. Please review logs. ---{C_RESET}")
                sys.exit(1)
            # After migration, the only remaining step is finalization.
            _run_finalization(final_output_dir, script_paths, colors)

        else:
            # --- For all other modes, use the iterative state-machine loop ---
            force_reprocess_once = args.reprocess
            loop_count = 0
            pipeline_successful = True
            while loop_count < args.max_loops:
                loop_count += 1
                action_taken = False
                success = True

                state_name, payload_details, _ = get_experiment_state(Path(final_output_dir), end_rep)

                if state_name == "NEW_NEEDED":
                    success = _run_new_mode(final_output_dir, args.start_rep, end_rep, args.notes, args.verbose, script_paths['orchestrator'], colors)
                    action_taken = True

                elif state_name == "REPAIR_NEEDED":
                    config_repairs = [d for d in payload_details if d.get("repair_type") == "config_repair"]
                    full_rep_repairs = [d for d in payload_details if d.get("repair_type") == "full_replication_repair"]
                    session_repairs = [d for d in payload_details if d.get("repair_type") == "session_repair"]
                    
                    if config_repairs:
                        success = _run_config_repair(config_repairs, script_paths['restore_config'], colors)
                    if success and full_rep_repairs:
                        success = _run_full_replication_repair(full_rep_repairs, script_paths['orchestrator'], not args.verbose, colors)
                    if success and session_repairs:
                        success = _run_repair_mode(session_repairs, script_paths['orchestrator'], args.verbose, colors)
                    action_taken = True

                elif state_name == "REPROCESS_NEEDED" or force_reprocess_once:
                    if force_reprocess_once and not payload_details:
                        all_run_dirs = sorted([p for p in Path(final_output_dir).glob("run_*") if p.is_dir()])
                        payload_details = [{"dir": str(run_dir)} for run_dir in all_run_dirs]
                    
                    success = _run_reprocess_mode(payload_details, args.notes, args.verbose, script_paths['orchestrator'], script_paths['compile_experiment'], final_output_dir, script_paths['log_manager'], colors)
                    action_taken = True
                    force_reprocess_once = False

                elif state_name == "COMPLETE" or state_name == "AGGREGATION_NEEDED":
                    print(f"{C_GREEN}--- Experiment is VALIDATED. Proceeding to finalization. ---{C_RESET}")
                    break

                if not success:
                    print(f"{C_RED}--- A step failed. Halting experiment manager. Please review logs. ---{C_RESET}")
                    pipeline_successful = False
                    break

            if loop_count >= args.max_loops:
                print(f"{C_RED}--- Max loop count reached. Halting to prevent infinite loop. ---{C_RESET}")
                pipeline_successful = False
            
            if pipeline_successful:
                _run_finalization(final_output_dir, script_paths, colors)
                relative_path = os.path.relpath(final_output_dir, PROJECT_ROOT)
                print(f"\n{C_GREEN}Experiment run finished successfully for:{C_RESET}")
                print(f"{C_GREEN}{relative_path}{C_RESET}")
                print()
            else:
                sys.exit(1)

    except KeyboardInterrupt:
        print(f"\n{C_YELLOW}--- Operation interrupted by user (Ctrl+C). Exiting gracefully. ---{C_RESET}", file=sys.stderr)
        sys.exit(AUDIT_ABORTED_BY_USER)

if __name__ == "__main__":
    main()

# === End of src/experiment_manager.py ===
