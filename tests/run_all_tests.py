#!/usr/bin/env python3
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
C_RESET = '\033[0m'

def show_spinner(message, stop_event):
    """Shows a rotating spinner with message until stop_event is set."""
    spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    i = 0
    while not stop_event.is_set():
        print(f"\r{spinner_chars[i % len(spinner_chars)]} {message}", end='', flush=True)
        i += 1
        time.sleep(0.1)
    print(f"\r✓ {message}", end='', flush=True)  # Show checkmark when done

def _clean_parallel_coverage_files(is_start):
    """Finds and deletes only parallel .coverage.* files, leaving .coverage intact."""
    if is_start:
        print(f"{C_CYAN}--- Cleaning up old parallel coverage data... ---{C_RESET}", flush=True)
    else:
        print(f"\n{C_CYAN}--- Cleaning up post-run parallel coverage data... ---{C_RESET}", flush=True)
        
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
    print(f"{C_CYAN}--- Running Python Unit Tests (pytest) ---{C_RESET}")
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

    # --- New Per-File Parsing Logic ---
    file_results = defaultdict(lambda: {'passed': 0, 'failed': 0})
    test_line_re = re.compile(r"^(tests[/\\](test_.+?\.py))::.*?\s+(PASSED|FAILED|SKIPPED)")

    for line in pytest_output.split('\n'):
        match = test_line_re.match(line)
        if match:
            filename = os.path.basename(match.group(1))
            status = match.group(3)
            if status == "PASSED":
                file_results[filename]['passed'] += 1
            elif status == "FAILED":
                file_results[filename]['failed'] += 1

    print(f"\n{C_CYAN}--- Pytest Suite Summary ---{C_RESET}")
    max_len = max((len(f) for f in file_results.keys()), default=25)
    header = f"{'Test Suite':<{max_len}} {'Status':>8} {'Passed':>8} {'Failed':>8} {'Total':>8}"
    print(f"{C_CYAN}{header}{C_RESET}")
    print(f"{C_CYAN}{'-' * len(header)}{C_RESET}")

    overall_passed, overall_failed = 0, 0
    for filename, counts in sorted(file_results.items()):
        passed, failed = counts['passed'], counts['failed']
        total = passed + failed
        overall_passed += passed
        overall_failed += failed
        status_str = f"{C_GREEN}PASS{C_RESET}" if failed == 0 else f"{C_RED}FAIL{C_RESET}"
        print(f"{filename:<{max_len}} {status_str:>8} {passed:>8} {failed:>8} {total:>8}")
    
    print(f"{C_CYAN}{'-' * len(header)}{C_RESET}")
    # Skip Status column, right-align numbers in their proper columns
    print(f"{C_CYAN}{'OVERALL TOTALS':<{max_len}} {' ':>8} {overall_passed:>8} {overall_failed:>8} {overall_passed + overall_failed:>8}{C_RESET}")

    return overall_passed, overall_failed, (overall_passed + overall_failed)

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
    border = "="*62
    print(f"\n{C_CYAN}{border}{C_RESET}", flush=True)
    print(f"{C_CYAN}--- Running PowerShell Script Tests ---{C_RESET}")
    print(f"{C_CYAN}{border}{C_RESET}", flush=True)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ps_script_path = os.path.join(script_dir, 'run_all_ps_tests.ps1')
    
    result = subprocess.run(["pwsh", "-File", ps_script_path], capture_output=True, text=True, encoding='utf-8')
    
    # Add cyan coloring to PowerShell output headers and tables
    ps_output = result.stdout
    colored_lines = []
    for line in ps_output.split('\n'):
        if (line.strip().startswith('--- PowerShell Test Suite Summary ---') or
            line.strip().startswith('Test Suite') and 'Status' in line and 'Passed' in line or
            line.strip().startswith('---') and '---' in line):
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

    if total_failed == 0:
        print(f"{C_GREEN}All Python and PowerShell test suites passed successfully!{C_RESET}")
        sys.exit(0)
    else:
        print(f"{C_RED}One or more test suites failed.{C_RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()