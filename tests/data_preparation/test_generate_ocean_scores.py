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
# Filename: tests/data_preparation/test_generate_ocean_scores.py

"""
Unit tests for the OCEAN score generation script (src/generate_ocean_scores.py).

This test suite validates the critical offline logic of the script. It focuses
on key areas such as:
1.  Parsing the structured JSON response from the LLM.
2.  The main processing loop, including batching and resuming.
3.  Correctly handling the 'bypass_candidate_selection' mode.
4.  The offline summary regeneration feature and stale file detection.
5.  Robust error handling for incomplete LLM responses.
"""

import json
import re
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from src.generate_ocean_scores import parse_batch_response


def test_parse_batch_response():
    """Tests the parsing of JSON responses from the LLM."""
    # Case 1: Valid JSON
    response_text = """
    Some introductory text from the model.
    [
      {"idADB": "101", "Name": "A", "Openness": 5.0, "Conscientiousness": 5.0, "Extraversion": 5.0, "Agreeableness": 5.0, "Neuroticism": 5.0},
      {"idADB": "102", "Name": "B", "Openness": 6.0, "Conscientiousness": 6.0, "Extraversion": 6.0, "Agreeableness": 6.0, "Neuroticism": 6.0}
    ]
    Some trailing text.
    """
    result = parse_batch_response(response_text)
    assert len(result) == 2
    assert result[0]['idADB'] == "101"

    # Case 2: Malformed JSON
    assert parse_batch_response("[{'idADB': '101'}]") == []  # Invalid JSON quotes
    # Case 3: No JSON array
    assert parse_batch_response("Just some text.") == []


@pytest.fixture
def mock_sandbox_with_bypass_config(tmp_path: Path) -> Path:
    """Creates a mock sandbox with a config.ini for bypass mode testing."""
    (tmp_path / "data" / "foundational_assets").mkdir(parents=True, exist_ok=True)
    
    (tmp_path / "config.ini").write_text(
        "[DataGeneration]\nbypass_candidate_selection = true\n"
    )
    
    (tmp_path / "data" / "foundational_assets" / "eminence_scores.csv").write_text("idADB,EminenceScore\n101,90.0\n")
    return tmp_path


def test_ocean_scores_warns_in_bypass_mode(mock_sandbox_with_bypass_config):
    """
    Tests that the script warns the user and exits if bypass is active
    and the user declines to proceed.
    """
    sandbox_path = mock_sandbox_with_bypass_config
    
    from src import generate_ocean_scores
    with patch("builtins.input", return_value="n"), \
         patch("sys.stdout.isatty", return_value=True):
        test_args = ["script.py", "--sandbox-path", str(sandbox_path)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                generate_ocean_scores.main()
            assert e.value.code == 0


@pytest.fixture
def mock_sandbox_for_main_tests(tmp_path: Path) -> dict:
    """Creates a mock sandbox with inputs for testing the main processing loop."""
    data_dir = tmp_path / "data" / "foundational_assets"
    reports_dir = tmp_path / "data" / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    (tmp_path / "config.ini").write_text("[DataGeneration]\n" "bypass_candidate_selection = false\n")
    
    eminence_content = "Index,idADB,Name,BirthYear,EminenceScore\n" + "\n".join(
        [f"{i},{100+i},Person {i},{1950+i},90.0" for i in range(1, 6)]
    )
    (data_dir / "eminence_scores.csv").write_text(eminence_content)

    return { "sandbox_path": tmp_path, "output_path": data_dir / "ocean_scores.csv",
             "summary_path": reports_dir / "ocean_scores_summary.txt",
             "missing_path": reports_dir / "missing_ocean_scores.txt" }


class MockLLMWorker:
    """A mock for subprocess.run that simulates the llm_prompter.py worker."""
    def __init__(self, ids_to_miss=None):
        self.ids_to_miss = ids_to_miss or set()

    def run(self, cmd, check, **kwargs):
        # A more robust parser that handles flags without values (like --quiet)
        args = {}
        i = 1
        while i < len(cmd):
            if cmd[i].startswith('--'):
                key = cmd[i].lstrip('-')
                if i + 1 < len(cmd) and not cmd[i+1].startswith('--'):
                    args[key] = cmd[i+1]
                    i += 2
                else:
                    args[key] = True  # Handle flag
                    i += 1
            else:
                i += 1  # Skip positional args

        query_file = Path(args['input_query_file'])
        response_file = Path(args['output_response_file'])
        
        query_text = query_file.read_text()
        requested = re.findall(r'(\w+\s\d+)\s\(\d+\),\sID\s(\d+)', query_text)
        
        response_data = []
        for name, id_adb in requested:
            if id_adb not in self.ids_to_miss:
                response_data.append({ "idADB": id_adb, "Name": name, "Openness": 5.0, "Conscientiousness": 5.0,
                                        "Extraversion": 5.0, "Agreeableness": 5.0, "Neuroticism": 5.0 })
        response_file.write_text(json.dumps(response_data, indent=2))


def test_full_run_success(mock_sandbox_for_main_tests):
    """Tests a full, successful run from scratch."""
    paths = mock_sandbox_for_main_tests
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--batch-size", "2"]
    
    mock_worker = MockLLMWorker()
    with patch("sys.argv", test_args), patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
        from src import generate_ocean_scores
        generate_ocean_scores.main()

    assert paths["output_path"].exists()
    df = pd.read_csv(paths["output_path"])
    assert len(df) == 5
    assert "SUCCESS" in paths["summary_path"].read_text()
    assert "None" in paths["missing_path"].read_text()


def test_resume_from_partial_file(mock_sandbox_for_main_tests, capsys):
    """Tests that the script correctly resumes from a partially completed file."""
    paths = mock_sandbox_for_main_tests
    
    # Pre-populate the output file with 2 of the 5 subjects, ensuring names are quoted
    # and there is a trailing newline to prevent corruption on append.
    cols = "Index,idADB,Name,BirthYear,Openness,Conscientiousness,Extraversion,Agreeableness,Neuroticism"
    content = f"{cols}\n" + "\n".join([f'{i},{100+i},"Person {i}",{1950+i},5,5,5,5,5' for i in range(1, 3)]) + "\n"
    paths["output_path"].write_text(content)

    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--batch-size", "2"]
    mock_worker = MockLLMWorker()
    with patch("sys.argv", test_args), patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
        from src import generate_ocean_scores
        generate_ocean_scores.main()

    captured = capsys.readouterr()
    assert "Processing 3 new subjects" in captured.out
    df = pd.read_csv(paths["output_path"])
    assert len(df) == 5


def test_llm_misses_subjects_halts_execution(mock_sandbox_for_main_tests):
    """Tests that the script halts with an error if the LLM misses a subject."""
    paths = mock_sandbox_for_main_tests
    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"])]

    # Configure the mock to miss subject '103'
    mock_worker = MockLLMWorker(ids_to_miss={'103'})
    with patch("sys.argv", test_args), \
         patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
        from src import generate_ocean_scores
        with pytest.raises(SystemExit) as e:
            generate_ocean_scores.main()
        assert e.value.code == 1

    assert "Person 3 (idADB: 103)" in paths["missing_path"].read_text()
    df = pd.read_csv(paths["output_path"])
    assert len(df) == 4


def test_stale_input_triggers_rerun(mock_sandbox_for_main_tests, capsys):
    """Tests that a stale output file triggers an automatic re-run."""
    paths = mock_sandbox_for_main_tests
    
    # Run once to create an output file
    with patch("sys.argv", ["s.py", "--sandbox-path", str(paths["sandbox_path"])]), \
         patch("src.generate_ocean_scores.subprocess.run", side_effect=MockLLMWorker().run):
        from src import generate_ocean_scores
        generate_ocean_scores.main()

    # Make the input file newer
    (paths["sandbox_path"] / "data/foundational_assets/eminence_scores.csv").touch()
    
    with patch("sys.argv", ["s.py", "--sandbox-path", str(paths["sandbox_path"])]), \
         patch("src.generate_ocean_scores.subprocess.run", side_effect=MockLLMWorker().run):
        generate_ocean_scores.main()
    
    captured = capsys.readouterr()
    assert "Stale data detected" in captured.out


def test_regenerate_summary_mode_runs_offline(tmp_path: Path):
    """Tests that the --regenerate-summary flag runs without making API calls."""
    data_dir = tmp_path / "data" / "foundational_assets"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Create dummy files for the test
    (data_dir / "eminence_scores.csv").write_text("idADB\n1\n2")
    (data_dir / "ocean_scores.csv").write_text("idADB\n1")
    (tmp_path / "config.ini").write_text("[DataGeneration]\n")

    from src import generate_ocean_scores
    with patch("src.generate_ocean_scores.subprocess.run") as mock_subprocess, \
         patch("src.generate_ocean_scores.generate_summary_report") as mock_summary:
        
        test_args = [ "script.py", "--sandbox-path", str(tmp_path), "--regenerate-summary" ]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                generate_ocean_scores.main()
            assert e.value.code == 0
    
    mock_subprocess.assert_not_called()
    mock_summary.assert_called_once()

# === End of tests/data_preparation/test_generate_ocean_scores.py ===
