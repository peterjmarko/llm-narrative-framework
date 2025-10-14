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
# Filename: tests/data_preparation/test_generate_data_preparation_summary.py

import sys
from pathlib import Path

import pytest
from pytest_mock import MockerFixture
from pyfakefs.fake_filesystem import FakeFilesystem

# Add the project's 'src' directory to the Python path to allow imports
# This is necessary for the test runner to find the script we are testing
script_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(script_dir / "src"))

# Now we can import the script's main function
from generate_data_preparation_summary import main as generate_summary_main

# --- Test Data and Helper Functions ---

def setup_fake_filesystem(fs: FakeFilesystem, scenario: str = 'happy_path'):
    """A helper function to create a consistent fake filesystem for tests."""
    
    # Create all necessary directories
    fs.create_dir("data/sources")
    fs.create_dir("data/processed")
    fs.create_dir("data/intermediate")
    fs.create_dir("data/reports")
    fs.create_dir("data/foundational_assets")

    # --- Define baseline for a truly "perfect" run ---
    total_records = 10000
    valid_records = 10000
    failed_records = 0
    eligible_candidates = 10000
    eminence_scored = 10000
    final_candidates = 9000
    final_db_subjects = 9000

    # --- Introduce specific flaws based on the test scenario ---
    if scenario == 'missing_validation_report':
        # Don't create the validation files
        pass
    else:
        # For all other scenarios, create the validation summary
        fs.create_file(
            "data/processed/adb_validation_summary.txt",
            contents=f"""
            Total Records in Report: {total_records}
            Valid Records: {valid_records} ({valid_records/total_records:.1%})
            Failed Records: {failed_records} ({failed_records/total_records:.1%})
            """
        )

    if scenario == 'llm_data_loss':
        eminence_scored = 9995  # 5 subjects missed

    if scenario == 'stage_4_data_loss':
        final_db_subjects = 8998 # 2 subjects lost

    # --- Create all data files based on the (potentially modified) numbers ---
    fs.create_file(
        "data/intermediate/adb_eligible_candidates.txt",
        contents="idADB\tName\n" + "\n".join([f"{i}\tSubject_{i}" for i in range(eligible_candidates)])
    )
    fs.create_file(
        "data/reports/eminence_scores_summary.txt",
        contents=f"Total Scored:     {eminence_scored}\nTotal in Source:  {eligible_candidates}\nMean:             55.12"
    )
    fs.create_file(
        "data/reports/ocean_scores_summary.txt",
        contents=f"Total Scored:     {eminence_scored}\nTotal in Source:  {eligible_candidates}"
    )
    fs.create_file(
        "data/intermediate/adb_final_candidates.txt",
        contents="idADB\tName\n" + "\n".join([f"{i}\tSubject_{i}" for i in range(final_candidates)])
    )
    fs.create_file(
        "data/processed/subject_db.csv",
        contents="idADB,Name\n" + "\n".join([f"{i},Subject_{i}" for i in range(final_db_subjects)])
    )

    # --- Create placeholder files that just need to exist ---
    placeholder_files = [
        "data/sources/adb_raw_export.txt", "data/processed/adb_wiki_links.csv",
        "data/foundational_assets/eminence_scores.csv", "data/foundational_assets/ocean_scores.csv",
        "data/intermediate/sf_data_import.txt", "data/foundational_assets/sf_delineations_library.txt",
        "data/foundational_assets/sf_chart_export.csv", "data/personalities_db.txt"
    ]
    for f in placeholder_files:
        fs.create_file(f)

    # Conditionally create the validation report file
    if scenario != 'missing_validation_report':
        fs.create_file("data/processed/adb_validation_report.csv")


# --- Pytest Tests ---

@pytest.mark.usefixtures('fs') # This decorator injects the fake filesystem
def test_happy_path_perfect_run(fs: FakeFilesystem, mocker: MockerFixture):
    """
    Tests the script's output when all files exist and data is perfectly consistent.
    It should report no issues or recommendations.
    """
    # Arrange: Set up a perfect file system and mock command-line arguments
    setup_fake_filesystem(fs, scenario='happy_path')
    mocker.patch('sys.argv', ['generate_data_preparation_summary.py'])

    # Act: Run the main function of the script
    generate_summary_main()

    # Assert: Check the content of the generated report
    report_path = Path("data/reports/data_preparation_pipeline_summary.txt")
    assert report_path.exists()
    
    report_content = report_path.read_text(encoding='utf-8')
    
    # Check for success messages
    assert "✓ No critical issues detected" in report_content
    assert "✓ No specific issues were detected that require manual review." in report_content
    
    # Check key metrics
    assert "Data Quality Score: 100.0% (10,000/10,000)" in report_content
    assert "Overall Completion Rate: 100.0% (10,000/10,000)" in report_content
    assert "Subjects Missed:     0" in report_content


@pytest.mark.usefixtures('fs')
def test_missing_critical_file(fs: FakeFilesystem, mocker: MockerFixture):
    """
    Tests that a missing validation report is correctly identified as a critical issue
    and that a relevant recommendation is generated.
    """
    # Arrange: Set up a file system with one critical file missing
    setup_fake_filesystem(fs, scenario='missing_validation_report')
    mocker.patch('sys.argv', ['generate_data_preparation_summary.py'])

    # Act
    generate_summary_main()

    # Assert
    report_path = Path("data/reports/data_preparation_pipeline_summary.txt")
    assert report_path.exists()
    report_content = report_path.read_text(encoding='utf-8')

    # Check for the specific issue and recommendation
    assert "⚠️  Missing critical pipeline file: adb_validation_report.csv" in report_content
    assert "• [Stage 2] Re-run Stage 2 to generate the missing validation report." in report_content
    assert "✓ No critical issues detected" not in report_content


@pytest.mark.usefixtures('fs')
def test_llm_scoring_data_loss(fs: FakeFilesystem, mocker: MockerFixture):
    """
    Tests that a discrepancy between eligible and scored subjects is flagged as an
    issue and generates the correct recommendation.
    """
    # Arrange: Set up a file system where fewer subjects were scored than were eligible
    setup_fake_filesystem(fs, scenario='llm_data_loss')
    mocker.patch('sys.argv', ['generate_data_preparation_summary.py'])

    # Act
    generate_summary_main()

    # Assert
    report_path = Path("data/reports/data_preparation_pipeline_summary.txt")
    assert report_path.exists()
    report_content = report_path.read_text(encoding='utf-8')

    # Check for the specific issue and recommendation
    assert "⚠️  5 subjects missed during LLM scoring" in report_content
    assert "• [Stage 3] Investigate the 5 subjects missed during LLM scoring." in report_content
    
    # Check metrics
    assert "Overall Completion Rate: 100.0% (9,995/10,000)" in report_content


@pytest.mark.usefixtures('fs')
def test_stage_4_data_loss(fs: FakeFilesystem, mocker: MockerFixture):
    """
    Tests that a discrepancy between final candidates and the final subject DB
    is flagged as an issue with the correct recommendation.
    """
    # Arrange
    setup_fake_filesystem(fs, scenario='stage_4_data_loss')
    mocker.patch('sys.argv', ['generate_data_preparation_summary.py'])

    # Act
    generate_summary_main()

    # Assert
    report_path = Path("data/reports/data_preparation_pipeline_summary.txt")
    assert report_path.exists()
    report_content = report_path.read_text(encoding='utf-8')

    # Check for the specific recommendation for Stage 4 data loss
    assert "• [Stage 4] Investigate the loss of 2 subjects during the final profile generation stage." in report_content

# === End of tests/data_preparation/test_generate_data_preparation_summary.py ===
