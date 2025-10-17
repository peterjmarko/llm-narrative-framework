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
# Filename: tests/assembly_logic/test_assembly_setup.py

"""
Interactive assembly logic setup script that pauses for manual Solar Fire processing.

This script runs the first 3 steps of the assembly logic validation workflow,
then pauses to allow the user to perform manual processing in Solar Fire,
and finally continues with the remaining steps after user confirmation.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path
from colorama import Fore, Style, init

# Initialize colorama
init(autoreset=True)


def run_script(script_path):
    """Run a Python script as a subprocess and handle errors."""
    project_root = Path(__file__).resolve().parents[2]
    rel_path = script_path.relative_to(project_root)
    
    print(f"\n{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}Running: {rel_path.as_posix()}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    
    try:
        result = subprocess.run([sys.executable, "-u", script_path], check=True, text=True, encoding='utf-8')
        print(f"✅ {rel_path.as_posix()} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{Fore.RED}ERROR: Script {rel_path.as_posix()} failed with exit code {e.returncode}{Style.RESET_ALL}")
        return False


def copy_import_file_to_sf():
    """Copy the import file to the Solar Fire import directory."""
    # Get the user's Documents directory
    documents_dir = Path.home() / "Documents"
    sf_import_dir = documents_dir / "Solar Fire User Files" / "Import"
    
    # Ensure the SF import directory exists
    sf_import_dir.mkdir(parents=True, exist_ok=True)
    
    # Get the import file from the sandbox
    project_root = Path(__file__).resolve().parents[2]
    sandbox_dir = project_root / "temp_assembly_logic_validation"
    import_file = sandbox_dir / "data/intermediate/sf_data_import.assembly_logic.txt"
    
    if not import_file.exists():
        print(f"\n{Fore.RED}ERROR: Import file not found at {import_file}{Style.RESET_ALL}")
        return False
    
    # Copy the file to SF import directory
    sf_import_file = sf_import_dir / import_file.name
    try:
        shutil.copy2(import_file, sf_import_file)
        print(f"\n{Fore.GREEN}✅ Import file copied to: {sf_import_file}{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"\n{Fore.RED}ERROR: Failed to copy import file: {e}{Style.RESET_ALL}")
        return False


def copy_export_file_from_sf():
    """Copy the export file from the Solar Fire export directory to the sandbox."""
    # Get the user's Documents directory
    documents_dir = Path.home() / "Documents"
    sf_export_dir = documents_dir / "Solar Fire User Files" / "Export"
    
    # Get the expected export file name
    export_file_name = "sf_chart_export.assembly_logic.csv"
    sf_export_file = sf_export_dir / export_file_name
    
    if not sf_export_file.exists():
        print(f"\n{Fore.RED}ERROR: Export file not found at {sf_export_file}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please make sure you've exported the file from Solar Fire with the correct name.{Style.RESET_ALL}")
        return False
    
    # Get the sandbox directory
    project_root = Path(__file__).resolve().parents[2]
    sandbox_dir = project_root / "temp_assembly_logic_validation"
    sandbox_export_dir = sandbox_dir / "data/foundational_assets"
    sandbox_export_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy the file from SF export directory to sandbox
    sandbox_export_file = sandbox_export_dir / "sf_chart_export.assembly_logic.csv"
    try:
        shutil.copy2(sf_export_file, sandbox_export_file)
        print(f"\n{Fore.GREEN}✅ Export file copied to: {sandbox_export_file}{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"\n{Fore.RED}ERROR: Failed to copy export file: {e}{Style.RESET_ALL}")
        return False


def copy_raw_reports_from_sf(subject_count):
    """Copy the raw reports directory from the Solar Fire export directory to the sandbox."""
    # Get the user's Documents directory
    documents_dir = Path.home() / "Documents"
    sf_export_dir = documents_dir / "Solar Fire User Files" / "Export"
    
    if not sf_export_dir.exists():
        print(f"\n{Fore.RED}ERROR: Export directory not found at {sf_export_dir}{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please make sure you've exported the interpretation reports from Solar Fire to the Export directory.{Style.RESET_ALL}")
        return False
    
    # Get the sandbox directory
    project_root = Path(__file__).resolve().parents[2]
    sandbox_dir = project_root / "temp_assembly_logic_validation"
    sandbox_raw_reports_dir = sandbox_dir / "data/intermediate/assembly_logic_raw_reports"
    
    # Remove existing directory if it exists
    if sandbox_raw_reports_dir.exists():
        shutil.rmtree(sandbox_raw_reports_dir)
    
    try:
        # Create the target directory
        sandbox_raw_reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy all .txt files that match the naming pattern
        txt_files_copied = 0
        for i in range(1, subject_count + 1):
            source_file = sf_export_dir / f"sf_raw_report.assembly_logic_{i}.txt"
            if source_file.exists():
                shutil.copy2(source_file, sandbox_raw_reports_dir)
                txt_files_copied += 1
            else:
                print(f"\n{Fore.YELLOW}WARNING: Expected file not found: {source_file}{Style.RESET_ALL}")
        
        if txt_files_copied == 0:
            print(f"\n{Fore.RED}ERROR: No sf_raw_report.assembly_logic_*.txt files found in {sf_export_dir}{Style.RESET_ALL}")
            return False
            
        print(f"\n{Fore.GREEN}✅ Copied {txt_files_copied} interpretation reports to: {sandbox_raw_reports_dir}{Style.RESET_ALL}")
        return True
    except Exception as e:
        print(f"\n{Fore.RED}ERROR: Failed to copy interpretation reports: {e}{Style.RESET_ALL}")


def get_user_confirmation(subject_count=17):
    """Get user confirmation that manual step is complete."""
    print(f"\n{Fore.RED}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.RED}{'=========='}                    {Fore.RED}MANUAL STEP REQUIRED{Fore.RED}                    {'=========='}{Style.RESET_ALL}")
    print(f"{Fore.RED}{'='*80}{Style.RESET_ALL}")
    print(f"""
Please execute the following manual procedure:

1. Open Solar Fire software.
2. Import the file that has been copied to your Solar Fire import directory:
   'Documents/Solar Fire User Files/Import/sf_data_import.assembly_logic.txt'.
3. Calculate all imported charts.
4. Export all chart data as 'sf_chart_export.assembly_logic.csv' to your Solar Fire export directory:
   'Documents/Solar Fire User Files/Export/'.
5. Generate and save interpretation reports for all charts ({subject_count} total) using the special procedure
   detailed in the Framework Manual under 'Special Step: Generate Interpretation Reports' of the 
   'Import/Export Workflow' section of the 'Solar Fire Integration and Configuration' chapter.

See the 'Import/Export Workflow' of the 'Solar Fire Integration and Configuration' chapter of the Framework Manual for detailed instructions.

{Fore.YELLOW}This step is critical for generating the ground truth data needed for validation.{Style.RESET_ALL}
""")
    
    while True:
        response = input(f"\nHave you completed the manual Solar Fire processing? (Y/N): ").lower().strip()
        if response in ['y', 'yes']:
            print("\n✅ Continuing with remaining steps...")
            return True
        elif response in ['n', 'no']:
            print(f"\n{Fore.YELLOW}⏸️  Pausing. Please complete the manual step and then run this script again.{Style.RESET_ALL}")
            print("You can also run the remaining steps individually using:")
            print("  pdm run test-assembly-step4")
            print("  pdm run test-assembly-step5")
            return False
        else:
            print("Please enter 'Y' or 'N'")


def main():
    """Main execution function."""
    script_dir = Path(__file__).parent
    project_root = Path(__file__).resolve().parents[2]

    # Add the 'src' and the parent of the assembly logic workflow directory to the path.
    # This allows Python to correctly resolve the module path.
    sys.path.insert(0, str(project_root / "src"))
    sys.path.insert(0, str(script_dir.parent))
    
    from assembly_logic.step_3_prepare_assembly_logic_import import prepare_and_format

    scripts_to_run_as_subprocess = [
        "step_1_generate_coverage_map.py",
        "step_2_select_assembly_logic_subjects.py",
    ]
    
    print("\nStarting assembly logic setup (automated steps)...")

    for script_name in scripts_to_run_as_subprocess:
        if not run_script(script_dir / script_name):
            print(f"\n{Fore.RED}❌ Setup failed at {script_name}. Please fix the issue and try again.{Style.RESET_ALL}")
            sys.exit(1)

    # --- Step 3: Call the refactored function directly ---
    rel_path = (script_dir / "step_3_prepare_assembly_logic_import.py").relative_to(project_root)
    print(f"\n{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}Running: {rel_path.as_posix()}{Style.RESET_ALL}")
    print(f"{Fore.MAGENTA}{'='*80}{Style.RESET_ALL}")

    try:
        final_candidates_path = project_root / "data/intermediate/adb_final_candidates.txt"
        sandbox_dir = project_root / "temp_assembly_logic_validation"
        num_processed, output_path = prepare_and_format(final_candidates_path, sandbox_dir)
        
        print(f"\n{Fore.YELLOW}--- Final Output ---{Fore.RESET}")
        print(f"{Fore.CYAN} - Assembly logic import file saved to: {output_path}{Fore.RESET}")
        key_metric = f"Final Count: {num_processed} subjects"
        print(f"\n{Fore.GREEN}SUCCESS: {key_metric}. Assembly logic import file created successfully.{Fore.RESET}\n")
        print(f"✅ {rel_path.as_posix()} completed successfully")
        subject_count = num_processed
    except Exception as e:
        print(f"\n{Fore.RED}❌ Setup failed at step_3_prepare_assembly_logic_import.py: {e}{Style.RESET_ALL}")
        sys.exit(1)

    # Copy the import file to SF import directory
    if not copy_import_file_to_sf():
        print(f"\n{Fore.RED}❌ Failed to copy import file to Solar Fire directory.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Get user confirmation for manual step, passing the dynamic count
    if not get_user_confirmation(subject_count=subject_count):
        print(f"\n{Fore.YELLOW}Setup paused. Run this script again after completing the manual step.{Style.RESET_ALL}")
        print()
        sys.exit(0)
    
    # Copy the export file from SF export directory
    if not copy_export_file_from_sf():
        print(f"\n{Fore.RED}❌ Failed to copy export file from Solar Fire directory.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Copy the raw reports from SF export directory
    if not copy_raw_reports_from_sf(subject_count=subject_count):
        print(f"\n{Fore.RED}❌ Failed to copy raw reports from Solar Fire directory.{Style.RESET_ALL}")
        sys.exit(1)
    
    # Run the remaining steps
    remaining_scripts = [
        "step_4_extract_assembly_logic_text.py",
        "step_5_validate_assembly_logic_subjects.py"
    ]
    
    print("\nContinuing with remaining steps...")
    
    for script in remaining_scripts:
        script_path = script_dir / script
        if not run_script(script_path):
            print(f"\n{Fore.RED}❌ Setup failed at {script}. Please fix the issue and try again.{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}💡 Tip: Make sure you've completed the manual Solar Fire processing step correctly.{Style.RESET_ALL}\n")
            sys.exit(1)
    
    print(f"\n{Fore.GREEN}{'='*80}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}🎉 Assembly logic setup completed successfully!{Style.RESET_ALL}")
    print(f"{Fore.GREEN}You can now run the validation test with: pdm run test-assembly\n{Style.RESET_ALL}")
    print(f"{Fore.GREEN}{'='*80}{Style.RESET_ALL}")


if __name__ == "__main__":
    main()

# === End of tests/assembly_logic/test_assembly_setup.py ===
