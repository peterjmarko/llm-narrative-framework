#!/usr/bin/env python3
#-*- coding: utf-8 -*-
#
# A Framework for Testing Complex Narrative Systems
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
# Filename: tests/run_all_tests.py

import subprocess
import sys
import os
import glob
import re
from collections import defaultdict
import time
import threading

# ANSI color codes
C_GREEN = '\033[92m'
C_RED = '\033[91m'
C_CYAN = '\033[96m'
C_YELLOW = '\033[93m'
C_BLUE = '\033[94m'
C_MAGENTA = '\033[95m'
C_RESET = '\033[0m'

def show_spinner(message, stop_event):
    """Shows a rotating spinner with message until stop_event is set."""
    spinner_chars = ['|', '/', '-', '\\']
    i = 0
    while not stop_event.is_set():
        print(f"\r{spinner_chars[i % len(spinner_chars)]} {message}", end='', flush=True)
        i += 1
        time.sleep(0.1)
    print(f"\r+ {message}", end='', flush=True)  # Show checkmark when done

def _clean_parallel_coverage_files(is_start):
    """Finds and deletes only parallel .coverage.* files, leaving .coverage intact."""
    if is_start:
        print()
        print(f"{C_MAGENTA}{'#' * 80}{C_RESET}")
        print(f"{C_MAGENTA}#{' RUNNING ALL PYTHON AND POWERSHELL TESTS '.center(78)}#{C_RESET}")
        print(f"{C_MAGENTA}{'#' * 80}{C_RESET}")
        print()
        print(f"{C_YELLOW}--- Cleaning up old parallel coverage data... ---{C_RESET}", flush=True)
    else:
        print(f"\n{C_YELLOW}--- Cleaning up post-run parallel coverage data... ---{C_RESET}", flush=True)
        
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parallel_files = glob.glob(os.path.join(project_root, '.coverage.*'))
    
    if not parallel_files:
        print("No parallel coverage data found to clean.")
        return

    try:
        for f in parallel_files:
            os.remove(f)
        print(f"Successfully removed {len(parallel_files)} parallel file(s).")
    except OSError as e:
        print(f"{C_RED}Error removing coverage files: {e}{C_RESET}", file=sys.stderr)

def run_pytest(args):
    """Runs the Python pytest suite, captures results, and prints a per-file summary."""
    border = "="*62
    print(f"\n{C_CYAN}{border}{C_RESET}", flush=True)
    print(f"{C_CYAN}{' Running Python Unit Tests (pytest) '.center(62)}{C_RESET}")
    print(f"{C_CYAN}{border}{C_RESET}", flush=True)
    
    # Start spinner
    stop_spinner = threading.Event()
    spinner_thread = threading.Thread(target=show_spinner, args=("Collecting tests...", stop_spinner))
    spinner_thread.start()
    
    cmd = [sys.executable, "-m", "coverage", "run", "-m", "pytest", "-v"] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    
    # Stop spinner
    stop_spinner.set()
    spinner_thread.join()
    print()  # New line after spinner

    pytest_output = result.stdout + result.stderr
    
    # Filter output to show only failing tests and summary
    filtered_lines = []
    in_test_output = False
    
    for line in pytest_output.split('\n'):
        # Include collection lines
        if 'collecting' in line or 'collected' in line:
            filtered_lines.append(line)
            in_test_output = True
        # Include only failed tests
        elif in_test_output and ('FAILED' in line or 'ERROR' in line):
            filtered_lines.append(line)
        # Include failure details and summary sections
        elif any(marker in line for marker in ['FAILURES', 'ERRORS', 'short test summary', '====']):
            filtered_lines.append(line)
            in_test_output = False
        # Include lines after summary markers
        elif not in_test_output:
            filtered_lines.append(line)
    
    print('\n'.join(filtered_lines))

    # --- Parse pytest output for total test count ---
    # Look for the "=== X passed in Y.Zs ===" line to get the total count
    total_passed = 0
    total_failed = 0
    
    # First try to get the totals from the final summary line
    for line in pytest_output.split('\n'):
        if " passed in " in line and "s" in line:
            # Example: "=== 621 passed in 28.03s ==="
            match = re.search(r"=== (\d+) passed in", line)
            if match:
                total_passed = int(match.group(1))
                break
    
    # If we didn't find the summary, try to count individual test results
    if total_passed == 0:
        test_line_re = re.compile(r"^(tests[/\\].+?\.py)::.*?\s+(PASSED|FAILED|SKIPPED)")
        for line in pytest_output.split('\n'):
            match = test_line_re.match(line)
            if match:
                status = match.group(2)
                if status == "PASSED":
                    total_passed += 1
                elif status == "FAILED":
                    total_failed += 1
    
    # Print a simple summary
    print(f"\n{C_YELLOW}--- Pytest Suite Summary ---{C_RESET}")
    print(f"{'Test Suite':<25} {'Status':>8} {'Passed':>8} {'Failed':>8} {'Total':>8}")
    print(f"{'-' * 62}")
    status_str = f"{C_GREEN}PASS{C_RESET}" if total_failed == 0 else f"{C_RED}FAIL{C_RESET}"
    print(f"{'Python Tests':<25} {status_str:<15} {total_passed:>8} {total_failed:>8} {total_passed + total_failed:>8}")
    print(f"{'-' * 62}")
    print(f"{'OVERALL TOTALS':<25} {'':>8} {total_passed:>8} {total_failed:>8} {total_passed + total_failed:>8}")

    return total_passed, total_failed, (total_passed + total_failed)

def run_coverage_report():
    """Combines coverage data and prints a summary report."""
    border = "="*62
    print(f"\n{C_CYAN}{border}{C_RESET}", flush=True)
    print(f"{C_CYAN}--- Generating Coverage Report ---{C_RESET}")
    print(f"{C_CYAN}{border}{C_RESET}", flush=True)
    
    combine_cmd = [sys.executable, "-m", "coverage", "combine"]
    subprocess.run(combine_cmd, capture_output=True) # Run silently

    report_cmd = [sys.executable, "-m", "coverage", "report", "-m"]
    subprocess.run(report_cmd)

def run_pwsh_tests():
    """Runs the PowerShell test suite and extracts results."""
    # Let the PowerShell script handle its own headers
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ps_script_path = os.path.join(script_dir, 'run_all_ps_tests.ps1')
    
    result = subprocess.run(["pwsh", "-File", ps_script_path], capture_output=True, text=True, encoding='utf-8')
    
    # Add coloring to PowerShell output headers and tables
    ps_output = result.stdout
    colored_lines = []
    for line in ps_output.split('\n'):
        if line.strip().startswith('======================================================'):
            # This is a suite header line
            colored_lines.append(f"{C_BLUE}{line}{C_RESET}")
        elif line.strip().startswith('  EXECUTING SUITE:'):
            # Center the suite name in 80 columns
            suite_name = line.strip()[17:]  # Remove "  EXECUTING SUITE: "
            centered = f"  EXECUTING SUITE: {suite_name}  ".center(80)
            colored_lines.append(f"{C_BLUE}{centered}{C_RESET}")
        # Skip the duplicate Test Summary headers
        elif line.strip().startswith('--- Test Summary ---'):
            continue
        elif line.strip().startswith('--- PowerShell Test Suite Summary ---'):
            colored_lines.append(f"{C_YELLOW}{line}{C_RESET}")
        elif (line.strip().startswith('Test Suite') and 'Status' in line and 'Passed' in line or
              line.strip().startswith('---') and '---' in line and not line.strip().startswith('--- Test')):
            colored_lines.append(f"{C_CYAN}{line}{C_RESET}")
        elif line.strip().startswith('OVERALL TOTALS'):
            colored_lines.append(f"{C_CYAN}{line}{C_RESET}")
        else:
            colored_lines.append(line)
    
    print('\n'.join(colored_lines))
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    passed, failed, total = 0, 0, 0
    for line in result.stdout.strip().split('\n'):
        match = re.search(r"^OVERALL TOTALS\s+(\d+)\s+(\d+)\s+(\d+)", line)
        if match:
            passed, failed, total = int(match.group(1)), int(match.group(2)), int(match.group(3))
            break
        
    return passed, failed, total

def main():
    """Orchestrates the entire test suite."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)

    _clean_parallel_coverage_files(is_start=True)
    
    cli_args = sys.argv[1:]
    
    py_passed, py_failed, py_total = run_pytest(cli_args)
    
    if py_total > 0:
        run_coverage_report()
        
    ps_passed, ps_failed, ps_total = run_pwsh_tests()
    
    py_status_str = f"{C_GREEN}PASS{C_RESET}" if py_failed == 0 else f"{C_RED}FAIL{C_RESET}"
    ps_status_str = f"{C_GREEN}PASS{C_RESET}" if ps_failed == 0 else f"{C_RED}FAIL{C_RESET}"

    summary_title = " OVERALL TEST SUMMARY "
    border = "#" * 62
    
    print("\n" + C_CYAN + border + C_RESET)
    print(C_CYAN + "###" + summary_title.center(56) + "###" + C_RESET)
    print(C_CYAN + border + C_RESET + "\n")

    header = f"{'Test Suite':<25} {'Status':>8} {'Passed':>8} {'Failed':>8} {'Total':>8}"
    print(f"{C_CYAN}{header}{C_RESET}")
    print(f"{C_CYAN}{'-' * len(header)}{C_RESET}")
    print(f"{'Python Tests':<25} {py_status_str:<15} {py_passed:>8} {py_failed:>8} {py_total:>8}")
    print(f"{'PowerShell Tests':<25} {ps_status_str:<15} {ps_passed:>8} {ps_failed:>8} {ps_total:>8}")
    print(f"{C_CYAN}{'-' * len(header)}{C_RESET}")
    total_passed = py_passed + ps_passed
    total_failed = py_failed + ps_failed
    total_tests = py_total + ps_total
    # Match the exact format: Status column is right-aligned, numbers are right-aligned
    print(f"{C_CYAN}{'OVERALL TOTALS':<25} {'':>8} {total_passed:>8} {total_failed:>8} {total_tests:>8}{C_RESET}\n")

    _clean_parallel_coverage_files(is_start=False)

    print()
    if total_failed == 0:
        print(f"{C_GREEN}{'#' * 80}{C_RESET}")
        print(f"{C_GREEN}#{' ALL PYTHON AND POWERSHELL TEST SUITES PASSED SUCCESSFULLY! '.center(78)}#{C_RESET}")
        print(f"{C_GREEN}{'#' * 80}{C_RESET}")
        print()
        sys.exit(0)
    else:
        print(f"{C_RED}{'#' * 80}{C_RESET}")
        print(f"{C_RED}#{' ONE OR MORE TEST SUITES FAILED. '.center(78)}#{C_RESET}")
        print(f"{C_RED}{'#' * 80}{C_RESET}")
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()

# === End of tests/run_all_tests.py ===
