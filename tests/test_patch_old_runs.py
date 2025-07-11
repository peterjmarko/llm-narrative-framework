# tests/test_patch_old_runs.py
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.patch_old_runs import main


@pytest.fixture
def temp_study_dir(tmp_path: Path) -> Path:
    """Creates a temporary study directory with sample run folders."""
    study_dir = tmp_path / "study_root"
    study_dir.mkdir()
    (study_dir / "run_01").mkdir()
    (study_dir / "run_02").mkdir()
    (study_dir / "not_a_run_dir").mkdir()  # Should be ignored
    return study_dir


@patch("builtins.print")
@patch("src.patch_old_runs.subprocess.run")
@patch("src.patch_old_runs.os.path.exists", return_value=True)
def test_main_success(
    mock_exists, mock_subprocess_run, mock_print, temp_study_dir
):
    """Test successful patching of multiple directories."""
    # Arrange: Mock subprocess results for two runs
    # First run succeeds and patches a file
    success_result = MagicMock()
    success_result.stdout = "Processing: 'run_01'\n  -> Success: Created '...'"
    # Second run skips because it's already patched
    skip_result = MagicMock()
    skip_result.stdout = "Skipping: 'run_02' already has..."

    mock_subprocess_run.side_effect = [success_result, skip_result]

    # Act
    with patch("sys.argv", ["script_name", str(temp_study_dir)]):
        main()

    # Assert
    assert mock_subprocess_run.call_count == 2
    # Check that the summary prints the correct number of patched directories
    mock_print.assert_any_call("Created new config archives for 1 directories.")


@patch("builtins.print")
@patch("src.patch_old_runs.subprocess.run")
@patch("src.patch_old_runs.os.path.exists", return_value=True)
def test_main_subprocess_fails(
    mock_exists, mock_subprocess_run, mock_print, temp_study_dir
):
    """Test that the script handles a subprocess failure gracefully."""
    # Arrange: Mock a failed subprocess call
    mock_subprocess_run.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="", stderr="Worker script failed."
    )

    # Act
    with patch("sys.argv", ["script_name", str(temp_study_dir)]):
        main()

    # Assert
    # It should try to process both directories
    assert mock_subprocess_run.call_count == 2
    # It should print an error for each failure
    mock_print.assert_any_call(
        "Failed to process 'run_01'. Error:\nWorker script failed."
    )
    mock_print.assert_any_call(
        "Failed to process 'run_02'. Error:\nWorker script failed."
    )
    # The final count of patched directories should be 0
    mock_print.assert_any_call("Created new config archives for 0 directories.")


@patch("builtins.print")
def test_main_root_dir_not_found(mock_print, tmp_path):
    """Test failure when the provided root directory does not exist."""
    non_existent_dir = tmp_path / "non_existent"
    with patch("sys.argv", ["script_name", str(non_existent_dir)]):
        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    mock_print.assert_called_with(
        f"Error: Root directory not found at '{non_existent_dir}'"
    )


@patch("builtins.print")
@patch("src.patch_old_runs.os.path.exists", return_value=False)
def test_main_restore_script_not_found(
    mock_exists, mock_print, temp_study_dir
):
    """Test failure when restore_config.py cannot be found."""
    with patch("sys.argv", ["script_name", str(temp_study_dir)]):
        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    mock_print.assert_called_with(
        "Error: Cannot find 'restore_config.py' in the same directory."
    )


@patch("builtins.print")
def test_main_no_run_dirs_found(mock_print, tmp_path):
    """Test behavior when no 'run_*' directories are found."""
    empty_study_dir = tmp_path / "empty_study"
    empty_study_dir.mkdir()
    with patch("sys.argv", ["script_name", str(empty_study_dir)]):
        main()
    mock_print.assert_any_call(
        f"No directories matching 'run_*' found within '{empty_study_dir}'."
    )


@patch("builtins.print")
def test_main_no_args(mock_print):
    """Test failure when no command-line arguments are provided."""
    with patch("sys.argv", ["script_name"]):
        with pytest.raises(SystemExit) as e:
            main()
    assert e.value.code == 1
    mock_print.assert_called_with(
        "Usage: python patch_old_runs.py <path_to_root_output_directory>"
    )