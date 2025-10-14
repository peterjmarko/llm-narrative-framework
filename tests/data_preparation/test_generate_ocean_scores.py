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


@pytest.mark.parametrize("response_text, expected_len", [
    # Case 1: Valid JSON with surrounding text
    ("""
    Some introductory text from the model.
    [
      {"idADB": "101", "Name": "A"},
      {"idADB": "102", "Name": "B"}
    ]
    Some trailing text.
    """, 2),
    # Case 2: Malformed JSON (invalid quotes)
    ("[{'idADB': '101'}]", 0),
    # Case 3: No JSON array in text
    ("Just some text.", 0),
    # Case 4: Valid JSON that is an object, not an array (covers branch)
    ('{"error": "not an array"}', 0),
])
def test_parse_batch_response(response_text, expected_len):
    """Tests the parsing of JSON responses from the LLM."""
    result = parse_batch_response(response_text)
    assert len(result) == expected_len


@pytest.fixture
def mock_sandbox_with_bypass_config(tmp_path: Path) -> Path:
    """Creates a mock sandbox with a config.ini for bypass mode testing."""
    (tmp_path / "data" / "foundational_assets").mkdir(parents=True, exist_ok=True)
    
    (tmp_path / "config.ini").write_text(
        "[DataGeneration]\nbypass_candidate_selection = true\n"
    )
    
    # Create a valid eminence scores file with all required columns
    eminence_content = "Index,idADB,Name,BirthYear,EminenceScore\n1,101,Test Person,1990,90.0\n"
    (tmp_path / "data" / "foundational_assets" / "eminence_scores.csv").write_text(eminence_content)
    return tmp_path


@pytest.fixture
def mock_sandbox_no_config(tmp_path: Path) -> Path:
    """Creates a mock sandbox WITHOUT a config.ini file."""
    (tmp_path / "data" / "foundational_assets").mkdir(parents=True, exist_ok=True)
    eminence_content = "Index,idADB,Name,BirthYear,EminenceScore\n1,101,Test Person,1990,90.0\n"
    (tmp_path / "data" / "foundational_assets" / "eminence_scores.csv").write_text(eminence_content)
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

    def run(self, cmd, **kwargs):
        # Use a robust index-based parser to find file paths.
        query_file = Path(cmd[cmd.index("--input_query_file") + 1])
        response_file = Path(cmd[cmd.index("--output_response_file") + 1])

        query_text = query_file.read_text()
        # Regex to find 'Name (YYYY), ID 1234'. Handles names with parentheses.
        requested = re.findall(r'(.+?)\s\(\d{4}\),\sID\s(\d+)', query_text)

        response_data = []
        for name, id_adb in requested:
            name = name.strip()
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
    
    # Pre-populate the output file with 2 of the 5 subjects. Ensure trailing newline.
    cols = "Index,idADB,Name,BirthYear,Openness,Conscientiousness,Extraversion,Agreeableness,Neuroticism"
    content = f"{cols}\n" + "\n".join([f'{i},{100+i},"Person {i}",{1950+i},5,5,5,5,5' for i in range(1, 3)]) + "\n"
    paths["output_path"].write_text(content)

    test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"]), "--batch-size", "2"]
    mock_worker = MockLLMWorker()
    with patch("sys.argv", test_args), patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
        from src import generate_ocean_scores
        # The script does not exit when processing, only when it finds the file is already complete.
        generate_ocean_scores.main()

    captured = capsys.readouterr()
    assert "Processing 3 new subjects" in captured.out
    df = pd.read_csv(paths["output_path"])
    assert len(df) == 5

    # Now, run it again to test the "already up to date" branch which exits
    with patch("sys.argv", test_args), \
         patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run), \
         pytest.raises(SystemExit) as e:
        generate_ocean_scores.main()
    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "is already up to date" in captured.out


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
        # A successful run does not exit, just completes.
        from src import generate_ocean_scores
        generate_ocean_scores.main()

    # Make the input file newer
    (paths["sandbox_path"] / "data/foundational_assets/eminence_scores.csv").touch()
    
    with patch("sys.argv", ["s.py", "--sandbox-path", str(paths["sandbox_path"])]), \
         patch("src.generate_ocean_scores.subprocess.run", side_effect=MockLLMWorker().run) as mock_run:
        # The second run will also complete successfully after detecting stale data.
        generate_ocean_scores.main()
        # Ensure it ran all 5 subjects again (1 batch with default size 50)
        assert mock_run.call_count == 1
    
    captured = capsys.readouterr()
    # The stale message is printed during the second run.
    assert "Stale data detected" in captured.out


class TestCoverageAndEdgeCases:
    """Additional tests for uncovered lines and edge cases."""

    def test_load_processed_ids_handles_io_error(self, tmp_path):
        """Tests that the script exits if the existing scores file cannot be read."""
        from src.generate_ocean_scores import load_processed_ids
        scores_file = tmp_path / "scores.csv"
        scores_file.write_text("content") # Must not be empty to trigger open
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(SystemExit):
                load_processed_ids(scores_file)

    def test_save_scores_to_csv_handles_io_error(self, tmp_path):
        """Tests that an IOError during save is logged correctly."""
        from src.generate_ocean_scores import save_scores_to_csv
        output_path = tmp_path / "test.csv"
        output_path.touch()
        output_path.chmod(0o444) # Read-only permissions
        
        with patch('logging.error') as mock_log:
            save_scores_to_csv(output_path, [{"idADB": "1"}])
            mock_log.assert_called_once()
            assert "Failed to write scores" in mock_log.call_args[0][0]
    
    def test_generate_summary_handles_empty_input(self, tmp_path, capsys):
        """Tests that the summary generator handles an empty input file."""
        from src.generate_ocean_scores import generate_summary_report
        scores_file = tmp_path / "scores.csv"
        scores_file.touch() # Create an empty file
        generate_summary_report(scores_file, 10)
        captured = capsys.readouterr()
        assert "Output file is empty. No summary to generate." in captured.out

    def test_main_handles_missing_eminence_file(self, mock_sandbox_for_main_tests):
        """Tests graceful exit if eminence_scores.csv is missing."""
        paths = mock_sandbox_for_main_tests
        (paths["sandbox_path"] / "data/foundational_assets/eminence_scores.csv").unlink()
        
        test_args = ["script.py", "--sandbox-path", str(paths["sandbox_path"])]
        with patch("sys.argv", test_args):
            from src import generate_ocean_scores
            with pytest.raises(SystemExit) as e:
                generate_ocean_scores.main()
            assert e.value.code == 1

    def test_validation_discards_mismatched_names(self, mock_sandbox_for_main_tests, capsys):
        """Tests that validation discards records with a correct ID but mismatched name."""
        paths = mock_sandbox_for_main_tests
        
        class MockNameMismatchWorker(MockLLMWorker):
            def run(self, cmd, **kwargs):
                super().run(cmd, **kwargs)
                response_file = Path(cmd[cmd.index("--output_response_file") + 1])
                data = json.loads(response_file.read_text())
                if data:
                    data[0]['Name'] = "Wrong Name" # Mismatch the name
                response_file.write_text(json.dumps(data))
        
        test_args = ["s.py", "--sandbox-path", str(paths["sandbox_path"])]
        with patch("sys.argv", test_args), \
             patch("src.generate_ocean_scores.subprocess.run", side_effect=MockNameMismatchWorker().run), \
             pytest.raises(SystemExit) as e:
            from src import generate_ocean_scores
            generate_ocean_scores.main()
        assert e.value.code == 1

        captured = capsys.readouterr()
        assert "Warning: Discarded 1 invalid records" in captured.out
        df = pd.read_csv(paths["output_path"])
        assert "101" not in df['idADB'].astype(str).values

    def test_validation_discards_extraneous_subjects(self, mock_sandbox_for_main_tests, capsys):
        """Tests that validation discards subjects not in the original request batch."""
        paths = mock_sandbox_for_main_tests
        test_args = ["s.py", "--sandbox-path", str(paths["sandbox_path"]), "--batch-size", "5"]
        
        class MockExtraWorker(MockLLMWorker):
            def run(self, cmd, **kwargs):
                super().run(cmd, **kwargs)
                response_file = Path(cmd[cmd.index("--output_response_file") + 1])
                data = json.loads(response_file.read_text())
                data.append({"idADB": "999", "Name": "Extra Person"})
                response_file.write_text(json.dumps(data))
        
        mock_worker = MockExtraWorker()
        with patch("sys.argv", test_args), patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
            from src import generate_ocean_scores
            generate_ocean_scores.main()

        captured = capsys.readouterr()
        assert "Warning: Discarded 1 invalid records" in captured.out
        df = pd.read_csv(paths["output_path"])
        assert "999" not in df['idADB'].astype(str).values

    def test_main_handles_keyboard_interrupt(self, mock_sandbox_for_main_tests, capsys):
        """Tests graceful exit on KeyboardInterrupt."""
        paths = mock_sandbox_for_main_tests
        
        with patch("src.generate_ocean_scores.subprocess.run", side_effect=KeyboardInterrupt), \
             patch("sys.argv", ["s.py", "--sandbox-path", str(paths["sandbox_path"])]), \
             pytest.raises(SystemExit) as e:
            from src import generate_ocean_scores
            generate_ocean_scores.main()
        assert e.value.code == 1 # Exits 1 because completion is 0%
        
        captured = capsys.readouterr()
        assert "Process interrupted by user." in captured.out
        # The finally block should create a report of unattempted subjects
        content = paths["missing_path"].read_text()
        assert "Subjects Not Attempted (5)" in content

    def test_main_handles_non_interactive_bypass(self, mock_sandbox_with_bypass_config, capsys):
        """Tests that the script runs non-interactively when bypass is active if not a TTY."""
        # This test ensures the `if sys.stdout.isatty():` branch is correctly handled.
        mock_worker = MockLLMWorker()
        with patch("sys.stdout.isatty", return_value=False), \
             patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
            test_args = ["script.py", "--sandbox-path", str(mock_sandbox_with_bypass_config)]
            with patch("sys.argv", test_args):
                from src import generate_ocean_scores
                # Should run to completion without prompting
                generate_ocean_scores.main()
        
        captured = capsys.readouterr()
        assert "BYPASS ACTIVE" in captured.out
        assert "Do you wish to proceed anyway?" not in captured.out

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

def test_regenerate_summary_fails_if_output_missing(tmp_path, caplog):
    """Tests --regenerate-summary exits if the target file is missing."""
    (tmp_path / "config.ini").write_text("[DataGeneration]\n")
    test_args = ["s.py", "--sandbox-path", str(tmp_path), "--regenerate-summary"]
    with patch("sys.argv", test_args), pytest.raises(SystemExit) as e:
        from src import generate_ocean_scores
        generate_ocean_scores.main()
    assert e.value.code == 1
    assert "Cannot regenerate summary" in caplog.text

def test_summary_report_with_few_subjects(tmp_path, capsys):
    """Tests that summary generation works with < 5 subjects (no quintiles)."""
    from src.generate_ocean_scores import generate_summary_report
    scores_file = tmp_path / "scores.csv"
    # Only 4 subjects, so quintile_size will be 0
    cols = "Index,idADB,Name,BirthYear,Openness,Conscientiousness,Extraversion,Agreeableness,Neuroticism"
    content = f"{cols}\n" + "\n".join([f'{i},{100+i},"Person {i}",{1950+i},5,5,5,5,5' for i in range(1, 5)])
    scores_file.write_text(content)
    
    generate_summary_report(scores_file, 4)
    
    captured = capsys.readouterr()
    assert "Quintile Analysis" in captured.out
    assert "Quintile 1" not in captured.out

def test_main_handles_network_error_and_halts(mock_sandbox_for_main_tests, capsys):
    """Tests that 3 consecutive network errors will halt execution."""
    paths = mock_sandbox_for_main_tests
    
    def mock_run_with_network_error(cmd, **kwargs):
        error_file = Path(cmd[cmd.index("--output_error_file") + 1])
        error_file.write_text("API connection timeout")

    test_args = ["s.py", "--sandbox-path", str(paths["sandbox_path"]), "--batch-size", "1"]
    with patch("sys.argv", test_args), \
         patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_run_with_network_error), \
         pytest.raises(SystemExit) as e:
        from src import generate_ocean_scores
        generate_ocean_scores.main()
    assert e.value.code == 1 # Exits 1 because completion is 0%

    captured = capsys.readouterr()
    assert captured.out.count("Network error for batch") == 3
    assert "Halting after 3 consecutive batch failures" in captured.out

def test_main_with_no_subjects_to_process(mock_sandbox_for_main_tests, capsys):
    """Tests the 'already up to date' branch when all subjects are processed."""
    paths = mock_sandbox_for_main_tests
    # Create an output file that contains ALL subjects from the input
    cols = "Index,idADB,Name,BirthYear,Openness,Conscientiousness,Extraversion,Agreeableness,Neuroticism"
    content = f"{cols}\n" + "\n".join([f'{i},{100+i},"Person {i}",{1950+i},5,5,5,5,5' for i in range(1, 6)])
    paths["output_path"].write_text(content)

    test_args = ["s.py", "--sandbox-path", str(paths["sandbox_path"])]
    with patch("sys.argv", test_args), pytest.raises(SystemExit) as e:
        from src import generate_ocean_scores
        generate_ocean_scores.main()
    
    assert e.value.code == 0
    captured = capsys.readouterr()
    assert "is already up to date" in captured.out

def test_main_warns_on_near_complete_run(mock_sandbox_for_main_tests, capsys):
    """Tests the WARNING summary and recommendation for 95-99% completion."""
    paths = mock_sandbox_for_main_tests
    eminence_path = paths["sandbox_path"] / "data/foundational_assets/eminence_scores.csv"
    # Create a larger input file of 100 subjects
    eminence_content = "Index,idADB,Name,BirthYear,EminenceScore\n" + "\n".join(
        [f"{i},{100+i},Person {i},{1950+i},90.0" for i in range(1, 101)]
    )
    eminence_path.write_text(eminence_content)

    # Miss 3 subjects, for a 97% completion rate, which should not halt.
    mock_worker = MockLLMWorker(ids_to_miss={'101', '102', '103'})
    test_args = ["s.py", "--sandbox-path", str(paths["sandbox_path"])]
    with patch("sys.argv", test_args), \
            patch("src.generate_ocean_scores.subprocess.run", side_effect=mock_worker.run):
        from src import generate_ocean_scores
        generate_ocean_scores.main()
    
    captured = capsys.readouterr()
    # Check for the tiered warning and recommended action printout
    assert "WARNING: Failed to retrieve scores for 3 subject(s)" in captured.out
    assert "RECOMMENDED ACTION" in captured.out
    assert "pdm run prep-data -StartWithStep 6" in captured.out

def test_main_debug_mode_from_env(mock_sandbox_for_main_tests, mocker):
    """Tests that the DEBUG_OCEAN environment variable sets the log level."""
    paths = mock_sandbox_for_main_tests
    # Patch the environment for the duration of the test
    mocker.patch.dict('os.environ', {'DEBUG_OCEAN': 'true'})
    mock_log_config = mocker.patch('logging.basicConfig')
    
    test_args = ["s.py", "--sandbox-path", str(paths["sandbox_path"]), "--force"]
    with patch("sys.argv", test_args), \
            patch("src.generate_ocean_scores.subprocess.run", side_effect=MockLLMWorker().run):
        from src import generate_ocean_scores
        # Need to reload the module to re-evaluate the logging config at import time
        import importlib
        importlib.reload(generate_ocean_scores)
        generate_ocean_scores.main()
    
    # Verify that logging was configured with the DEBUG level
    mock_log_config.assert_called_with(level=mocker.ANY, format=mocker.ANY)
    assert mock_log_config.call_args.kwargs['level'] == 10 # logging.DEBUG is 10

# === End of tests/data_preparation/test_generate_ocean_scores.py ===
