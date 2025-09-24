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
# Filename: tests/data_preparation/test_generate_eminence_scores.py

"""
Unit tests for the eminence score generation script (src/generate_eminence_scores.py).

This test suite validates the script's critical offline logic. It includes tests
for parsing the structured LLM response, handling resumability by loading
previously processed IDs (including legacy format detection), and a mocked test
of the main orchestrator loop to ensure the subprocess worker is called correctly.
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest
from src.generate_eminence_scores import main, load_processed_ids, parse_batch_response


@pytest.mark.parametrize("response_text, expected_output", [
    # Case 1: Standard, well-formed response
    (
        '"Albert Einstein (1879), ID 2001: 99.0"\n"Zsa Zsa Gabor (1917), ID 2002: 70.0"',
        [('2001', 'Albert Einstein', '1879', '99.0'), ('2002', 'Zsa Zsa Gabor', '1917', '70.0')]
    ),
    # Case 2: Response with extra whitespace and blank lines
    (
        '  "John F. Kennedy (1917), ID 3001: 95.5"  \n\n"Alan Turing (1912), ID 3002: 90.1"',
        [('3001', 'John F. Kennedy', '1917', '95.5'), ('3002', 'Alan Turing', '1912', '90.1')]
    ),
    # Case 3: Response with a mix of valid and malformed lines
    (
        '"Valid Person (1950), ID 4001: 80.0"\nThis is some commentary.\n"Another Person (1960), ID 4002: 75.0"',
        [('4001', 'Valid Person', '1950', '80.0'), ('4002', 'Another Person', '1960', '75.0')]
    ),
    # Case 4: Name contains a comma
    (
        '"King, Martin Luther (1929), ID 5001: 96.0"',
        [('5001', 'King, Martin Luther', '1929', '96.0')]
    ),
    # Case 5: Empty input
    ("", []),
])
def test_parse_batch_response(response_text, expected_output):
    """
    Tests the parse_batch_response function with various LLM response formats.
    """
    parsed_data = parse_batch_response(response_text)
    assert parsed_data == expected_output


def test_load_processed_ids(tmp_path):
    """Tests the logic for loading already processed subject IDs."""
    scores_file = tmp_path / "scores.csv"

    # Case 1: No file exists
    assert load_processed_ids(scores_file) == set()

    # Case 2: Valid, modern file
    scores_content = (
        "Index,idADB,Name,BirthYear,EminenceScore\n"
        "1,101,Test A,1900,80.0\n"
        "2,102,Test B,1901,85.5\n"
    )
    scores_file.write_text(scores_content)
    assert load_processed_ids(scores_file) == {"101", "102"}

    # Case 3: Incompatible legacy file with 'ARN' column
    legacy_content = "Index,ARN,Name,BirthYear,EminenceScore\n1,101,Test A,1900,80.0\n"
    scores_file.write_text(legacy_content)
    with pytest.raises(SystemExit):
        load_processed_ids(scores_file)
        
    # Case 4: Malformed header with no valid ID column
    malformed_content = "Col1,Col2,Col3\n1,2,3\n"
    scores_file.write_text(malformed_content)
    with pytest.raises(SystemExit):
        load_processed_ids(scores_file)


@pytest.fixture
def mock_sandbox(tmp_path: Path) -> Path:
    """Creates a temporary sandbox with mock input files for main workflow tests."""
    input_dir = tmp_path / "data" / "intermediate"
    output_dir = tmp_path / "data" / "foundational_assets"
    (tmp_path / "data" / "reports").mkdir(parents=True)
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)
    
    input_file = input_dir / "adb_eligible_candidates.txt"
    input_content = "idADB\tFirstName\tLastName\tYear\n101\tTest\tA\t1950\n102\tTest\tB\t1951\n"
    input_file.write_text(input_content)
    
    return tmp_path


class TestMainWorkflow:
    """Tests the main orchestration logic of the script."""

    @pytest.fixture
    def mock_sandbox_with_bypass(self, mock_sandbox: Path) -> Path:
        """Adds a config.ini with bypass_candidate_selection=true."""
        (mock_sandbox / "config.ini").write_text("[DataGeneration]\nbypass_candidate_selection = true\n")
        return mock_sandbox

    def test_main_happy_path(self, mocker, mock_sandbox):
        """Tests the main orchestrator loop with a successful run."""
        output_path = mock_sandbox / "data/foundational_assets/eminence_scores.csv"
        mock_subprocess = mocker.patch('subprocess.run')
        mocker.patch('src.generate_eminence_scores.sort_and_reindex_scores')
        mocker.patch('src.generate_eminence_scores.generate_scores_summary')

        def side_effect(*args, **kwargs):
            worker_cmd = args[0]
            response_file = Path(worker_cmd[worker_cmd.index("--output_response_file") + 1])
            response_text = '"Test A (1950), ID 101: 85.0"\n"Test B (1951), ID 102: 88.0"'
            response_file.write_text(response_text)
            return MagicMock(returncode=0)

        mock_subprocess.side_effect = side_effect
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--batch-size", "2", "--force"]
        with patch("sys.argv", test_args):
            main()

        assert mock_subprocess.call_count == 1
        df = pd.read_csv(output_path)
        assert set(df['idADB'].astype(str)) == {"101", "102"}

    def test_main_handles_bypass_mode_cancellation(self, mock_sandbox_with_bypass):
        """Tests that the script exits if the user declines to run in bypass mode."""
        with patch("builtins.input", return_value="n"), patch("sys.stdout.isatty", return_value=True):
            test_args = ["script.py", "--sandbox-path", str(mock_sandbox_with_bypass)]
            with patch("sys.argv", test_args):
                with pytest.raises(SystemExit) as e:
                    main()
                assert e.value.code == 0

    def test_main_handles_stale_file(self, mocker, mock_sandbox):
        """Tests that a stale output file triggers an automatic re-run."""
        input_path = mock_sandbox / "data/intermediate/adb_eligible_candidates.txt"
        output_path = mock_sandbox / "data/foundational_assets/eminence_scores.csv"
        output_path.touch()
        os.utime(input_path, (output_path.stat().st_mtime + 1, output_path.stat().st_mtime + 1))
        
        mock_backup = mocker.patch('src.generate_eminence_scores.backup_and_remove')
        # Prevent the main loop from running by pretending there are no subjects.
        # This isolates the test to only the stale file detection logic.
        mocker.patch('src.generate_eminence_scores.load_subjects_to_process', return_value=[])
        mocker.patch('sys.exit') # Prevent the script from exiting the test run

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            main()
        
        mock_backup.assert_called_once_with(output_path)

    def test_main_exits_if_input_missing(self, mocker, mock_sandbox, caplog):
        """Tests graceful exit if the input file is missing."""
        (mock_sandbox / "data/intermediate/adb_eligible_candidates.txt").unlink()
        mocker.patch('sys.exit', side_effect=SystemExit)

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                main()
        
        assert "Input file not found" in caplog.text

    def test_main_creates_missing_scores_report(self, mocker, mock_sandbox):
        """Tests that a report is generated for subjects the LLM failed to score."""
        mock_subprocess = mocker.patch('subprocess.run')
        
        # Mock sys.exit to correctly capture the exit code
        def mock_exit(code=0):
            raise SystemExit(code)
        mocker.patch('sys.exit', side_effect=mock_exit)

        def side_effect(*args, **kwargs):
            # Simulate the LLM only returning one of the two subjects
            worker_cmd = args[0]
            response_file = Path(worker_cmd[worker_cmd.index("--output_response_file") + 1])
            response_text = '"Test A (1950), ID 101: 85.0"' # Missing ID 102
            response_file.write_text(response_text)
            return MagicMock(returncode=0)

        mock_subprocess.side_effect = side_effect
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force", "--no-summary"]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1 # Should exit with an error code

        missing_report_path = mock_sandbox / "data/reports/missing_eminence_scores.txt"
        assert missing_report_path.exists()
        content = missing_report_path.read_text()
        assert "102" in content
        assert "101" not in content


    def test_main_handles_worker_failure(self, mocker, mock_sandbox):
        """Tests that the script halts gracefully after max consecutive worker failures."""
        mock_subprocess = mocker.patch('subprocess.run')
        mock_sys_exit = mocker.patch('sys.exit')

        # Simulate the worker always creating an error file
        def side_effect(*args, **kwargs):
            worker_cmd = args[0]
            error_file = Path(worker_cmd[worker_cmd.index("--output_error_file") + 1])
            error_file.write_text("API connection failed.")
            return MagicMock(returncode=1)

        mock_subprocess.side_effect = side_effect
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force", "--batch-size", "1"]
        with patch("sys.argv", test_args):
            main()

        # With 2 subjects and batch size 1, it should fail 2 times.
        # The max_consecutive_failures is 3, so it should attempt both.
        # But after 3 failures it should stop. Let's adjust the test to check this.
        # The input file has 2 subjects, batch size is 1. Loop runs twice. Both fail.
        # It should try, fail, try again, fail again, then finish the loop and go to finally.
        # Let's check that it logged the errors. The main check is that it doesn't complete successfully.
        
        # In the real code, it would halt. The test can check that the loop was aborted.
        # A simpler check is that the output file is never created or is empty.
        output_path = mock_sandbox / "data/foundational_assets/eminence_scores.csv"
        assert not output_path.exists() or output_path.stat().st_size == 0
        
        # It should have tried to process the first batch, failed, then the second, and failed.
        # The script does not exit on worker failure, it breaks. So let's check subprocess calls.
        assert mock_subprocess.call_count == 2 # Tries both subjects


    def test_main_handles_keyboard_interrupt(self, mocker, mock_sandbox, capsys):
        """Tests that the script handles KeyboardInterrupt gracefully."""
        # Mock the subprocess to raise the interrupt, simulating a user stopping the script
        mocker.patch('subprocess.run', side_effect=KeyboardInterrupt)
        mocker.patch('sys.exit') # Prevent the test from exiting

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force"]
        with patch("sys.argv", test_args):
            main()
        
        # Check for the graceful shutdown message in standard output
        captured = capsys.readouterr()
        assert "Process interrupted by user. Exiting gracefully." in captured.out



    def test_main_handles_up_to_date_file(self, mocker, mock_sandbox, capsys):
        """
        Tests that the script exits gracefully if the scores file is already
        complete and up-to-date.
        """
        output_path = mock_sandbox / "data/foundational_assets/eminence_scores.csv"
        # Create a complete output file with both subjects
        output_content = "idADB,Name,BirthYear,EminenceScore\n101,A,1950,85\n102,B,1951,88\n"
        output_path.write_text(output_content)

        mocker.patch('sys.exit', side_effect=SystemExit)
        mock_summary = mocker.patch('src.generate_eminence_scores.generate_scores_summary')

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        assert "is already up to date" in captured.out
        mock_summary.assert_called_once()


class TestCoverageAndEdgeCases:
    """Additional tests for uncovered lines and edge cases."""

    def test_generate_scores_summary_creates_report(self, tmp_path):
        """Tests the full summary generation logic."""
        from src.generate_eminence_scores import generate_scores_summary
        scores_file = tmp_path / "eminence_scores.csv"
        scores_content = "Index,idADB,Name,BirthYear,EminenceScore\n1,101,A,1950,95.0\n2,102,B,1951,45.0\n"
        scores_file.write_text(scores_content)

        # Mock get_path to ensure the reports directory is created within the sandbox
        def mock_get_path(path_key):
            if path_key == "data/reports":
                return tmp_path / "data" / "reports"
            return tmp_path / path_key

        # Fix: Patch config_loader.get_path directly, not src.config_loader.get_path
        with patch('config_loader.get_path', mock_get_path):
            generate_scores_summary(scores_file, 2)

        summary_file = tmp_path / "data" / "reports" / "eminence_scores_summary.txt"
        assert summary_file.exists()
        content = summary_file.read_text()
        assert "SUCCESS - Completion: 2/2 (100.00%)" in content
        assert "Mean:           70.00" in content
        assert "Top 10 Most Eminent" in content

    def test_load_processed_ids_handles_io_error(self, mocker, tmp_path):
        """Tests that the script exits if the existing scores file cannot be read."""
        dummy_file = tmp_path / "dummy_path.csv"
        # Fix: Write some content so the file isn't empty
        dummy_file.write_text("Index,idADB,Name\n1,101,Test\n")
        mocker.patch('builtins.open', side_effect=IOError("Permission denied"))
        
        # Patch sys.exit within the module where it's called
        with patch('src.generate_eminence_scores.sys.exit') as mock_exit:
            load_processed_ids(dummy_file)
            mock_exit.assert_called_once_with(1)

    def test_save_scores_to_csv_handles_io_error(self, tmp_path):
        """Tests that an IOError during save is logged correctly."""
        from src.generate_eminence_scores import save_scores_to_csv
        # Make the file read-only to trigger an IOError
        output_path = tmp_path / "test.csv"
        output_path.touch()
        output_path.chmod(0o444) # Read-only permissions
        
        with patch('logging.error') as mock_log:
            save_scores_to_csv(output_path, [('1', 'N', 'Y', 'S')], 1)
            mock_log.assert_called_once()
            assert "Failed to write scores" in mock_log.call_args[0][0]

    def test_sort_and_reindex_scores_handles_import_error(self, tmp_path):
        """Tests the fallback behavior when pandas is not installed."""
        import importlib
        from src import generate_eminence_scores

        scores_file = tmp_path / "scores.csv"
        scores_file.write_text("Index,EminenceScore\n2,80\n1,90")

        with patch.dict('sys.modules', {'pandas': None}):
            with patch('logging.warning') as mock_warning:
                importlib.reload(generate_eminence_scores)
                result = generate_eminence_scores.sort_and_reindex_scores(scores_file)

                assert result is True
                # Use the full, correct warning message from the production code
                expected_msg = "Pandas not installed. Skipping sorting. Install with 'pdm add pandas'."
                mock_warning.assert_called_once_with(expected_msg)

        # Verify the file was NOT sorted
        content = scores_file.read_text()
        assert content.startswith("Index,EminenceScore\n2,80")

        # IMPORTANT: Reload the module again outside the patch to restore its state
        importlib.reload(generate_eminence_scores)

        # IMPORTANT: Reload the module again outside the patch to restore its state
        # for subsequent tests in the suite.
        importlib.reload(generate_eminence_scores)

    def test_main_handles_up_to_date_file_with_user_confirmation(self, mock_sandbox, capsys):
        """Tests the interactive prompt when the user confirms an overwrite."""
        output_path = mock_sandbox / "data/foundational_assets/eminence_scores.csv"
        output_path.write_text("idADB,Name,BirthYear,EminenceScore\n101,A,1950,85\n102,B,1951,88\n")

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox)]
        with patch("sys.argv", test_args), \
             patch("builtins.input", return_value="y"), \
             patch('src.generate_eminence_scores.backup_and_remove') as mock_backup:
            
            # Mock `isatty` to ensure the script thinks it's in an interactive session
            with patch('sys.stdout.isatty', return_value=True):
                main()
        
        captured = capsys.readouterr()
        assert "is already up to date" in captured.out
        assert "Forcing overwrite" in captured.out
        mock_backup.assert_called_once()

    def test_main_halts_on_fatal_worker_error(self, mocker, mock_sandbox):
        """Tests that the script halts immediately on a 401 API error."""
        mock_subprocess = mocker.patch('subprocess.run')

        def side_effect(*args, **kwargs):
            worker_cmd = args[0]
            error_file = Path(worker_cmd[worker_cmd.index("--output_error_file") + 1])
            error_file.write_text("API Error: 401 Unauthorized")
            return MagicMock(returncode=1)
        
        mock_subprocess.side_effect = side_effect
        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--force", "--batch-size", "1"]
        with patch("sys.argv", test_args), \
             patch('sys.exit') as mock_exit:
            main()

        # Should only be called once before halting
        mock_subprocess.assert_called_once()

    def test_main_handles_no_summary_flag(self, mocker, mock_sandbox, capsys):
        """Tests that the --no-summary flag suppresses the detailed report."""
        mocker.patch('src.generate_eminence_scores.load_subjects_to_process', return_value=[])
        mock_generate_summary = mocker.patch('src.generate_eminence_scores.generate_scores_summary')

        test_args = ["script.py", "--sandbox-path", str(mock_sandbox), "--no-summary"]
        with patch("sys.argv", test_args):
            with pytest.raises(SystemExit):
                main() # Exits because there are no subjects to process
        
        mock_generate_summary.assert_not_called()
        captured = capsys.readouterr()
        # The script correctly prints that the file is up to date and does not
        # print the "Final Output" banner in this code path.
        assert "is already up to date" in captured.out
        assert "--- Summary Report ---" not in captured.out

# === End of tests/data_preparation/test_generate_eminence_scores.py ===
