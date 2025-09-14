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
# Filename: tests/experiment_lifecycle/test_query_generator.py

import csv
import sys
from unittest.mock import patch

import pytest

# Since this is a script, we import the main function
from query_generator import main as query_generator_main

# Mock content for our test files
MOCK_PERSONALITIES_CONTENT = (
    "Index\tName\tBirthYear\tDescriptionText\tidADB\n"
    "1\tPerson A\t1990\tDescription for A.\t101\n"
    "2\tPerson B\t1991\tDescription for B.\t102\n"
    "3\tPerson C\t1992\tDescription for C.\t103\n"
    "4\tPerson D\t1993\tDescription for D.\t104\n"
)

MOCK_BASE_QUERY_CONTENT = "Base query for k={k} subjects."


@pytest.fixture
def setup_test_environment(tmp_path, monkeypatch):
    """Set up a mock project environment for testing the script."""
    # Create mock data directory and files
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    personalities_file = data_dir / "personalities_db.txt"
    personalities_file.write_text(MOCK_PERSONALITIES_CONTENT, encoding="utf-8")

    base_query_file = data_dir / "base_query.txt"
    base_query_file.write_text(MOCK_BASE_QUERY_CONTENT, encoding="utf-8")

    # The script imports PROJECT_ROOT into its own namespace. We must patch it
    # there to ensure the change is visible during the test run.
    monkeypatch.setattr('query_generator.PROJECT_ROOT', str(tmp_path))

    # The script calls sys.exit on error. We patch it to raise an exception
    # that pytest can catch, preventing the test run from stopping.
    monkeypatch.setattr(sys, 'exit', lambda code: (_ for _ in ()).throw(SystemExit(code)))

    return tmp_path


def run_script(monkeypatch, args):
    """Helper function to run the script's main function with mocked args."""
    # Prepend a dummy script name to match sys.argv's structure
    full_args = ['query_generator.py'] + args
    monkeypatch.setattr(sys, 'argv', full_args)
    query_generator_main()


def test_happy_path_correct_mapping(setup_test_environment, monkeypatch):
    """
    Tests the script's main functionality with a 'correct' mapping strategy.
    """
    tmp_path = setup_test_environment
    output_dir = tmp_path / "output" / "qgen_standalone_output"

    # Run the script with specific arguments
    run_script(monkeypatch, [
        "-k", "3",
        "--seed", "42",
        "--mapping_strategy", "correct",
        "--personalities_file", "personalities_db.txt"
    ])

    # 1. Verify all output files were created
    assert (output_dir / "llm_query.txt").exists()
    assert (output_dir / "mapping.txt").exists()
    assert (output_dir / "manifest.txt").exists()

    # 2. Verify manifest content for 'correct' mapping
    with open(output_dir / "manifest.txt", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            assert row['Name_Ref_ID'] == row['Desc_Ref_ID'], "Manifest should show correct mapping"

    # 3. Verify llm_query.txt content
    query_content = (output_dir / "llm_query.txt").read_text(encoding='utf-8')
    assert "Base query for k=3 subjects." in query_content
    assert query_content.count('\n') > 5  # Check it has content beyond the header


def test_happy_path_random_mapping(setup_test_environment, monkeypatch):
    """
    Tests the script's main functionality with a 'random' mapping strategy.
    """
    tmp_path = setup_test_environment
    output_dir = tmp_path / "output" / "qgen_standalone_output"

    run_script(monkeypatch, [
        "-k", "3",
        "--seed", "42",
        "--mapping_strategy", "random",
        "--personalities_file", "personalities_db.txt"
    ])

    # Verify manifest content for 'random' mapping
    with open(output_dir / "manifest.txt", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)
        name_ref_ids = [row['Name_Ref_ID'] for row in rows]
        desc_ref_ids = [row['Desc_Ref_ID'] for row in rows]

        # With a random mapping, the lists of IDs should not be identical.
        assert name_ref_ids != desc_ref_ids, "Manifest should show a random mapping"
        # However, they should contain the same set of IDs, just in a different order.
        assert sorted(name_ref_ids) == sorted(desc_ref_ids), "ID sets should be the same"


def test_edge_case_k_equals_total_subjects(setup_test_environment, monkeypatch):
    """
    Tests the script when k is the total number of available subjects.
    """
    tmp_path = setup_test_environment
    output_dir = tmp_path / "output" / "qgen_standalone_output"

    # Our mock file has 4 subjects.
    run_script(monkeypatch, ["-k", "4", "--seed", "1"])

    # We just need to check if it ran without error and created the files.
    assert (output_dir / "manifest.txt").exists()
    with open(output_dir / "manifest.txt", 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        next(reader)  # skip header
        assert len(list(reader)) == 4, "Manifest should have 4 rows for k=4"


def test_error_handling_personalities_file_not_found(setup_test_environment, monkeypatch):
    """
    Tests that the script exits if the personalities file is not found.
    """
    with pytest.raises(SystemExit) as e:
        run_script(monkeypatch, ["--personalities_file", "non_existent_file.txt"])
    assert e.value.code == 1, "Should exit with code 1 for file not found"


def test_error_handling_not_enough_subjects(setup_test_environment, monkeypatch):
    """
    Tests that the script exits if k is larger than the number of available subjects.
    """
    with pytest.raises(SystemExit) as e:
        # Our mock file has 4 subjects
        run_script(monkeypatch, ["-k", "5"])
    assert e.value.code == 1, "Should exit with code 1 for insufficient subjects"


def test_error_handling_empty_personalities_file(setup_test_environment, monkeypatch):
    """
    Tests that the script exits gracefully for an empty personalities file.
    """
    tmp_path = setup_test_environment
    # Overwrite the file with just a header
    (tmp_path / "data" / "personalities_db.txt").write_text("Index\tName\tBirthYear\tDescriptionText\tidADB\n")

    with pytest.raises(SystemExit) as e:
        run_script(monkeypatch, ["-k", "2"])
    assert e.value.code == 1, "Should exit with code 1 for empty subject file"

# === End of tests/experiment_lifecycle/test_query_generator.py ===
