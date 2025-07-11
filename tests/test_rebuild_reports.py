# tests/test_rebuild_reports.py
import configparser
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src import rebuild_reports

# --- Sample Data and Mocks ---
MOCK_CONFIG_INI_ARCHIVED = """
[LLM]
model = mock-model/from-archive
[Study]
num_iterations = 100
k_per_query = 10
mapping_strategy = correct
[Filenames]
personalities_src = personalities_db_1-5000.txt
base_query_src = base_query.txt
"""

MOCK_PROCESS_OUTPUT = "<<<PARSER_SUMMARY:95:100:5>>>"
MOCK_ANALYZE_OUTPUT = """
<<<ANALYSIS_SUMMARY_START>>>
This is the mock analysis summary.
<<<METRICS_JSON_START>>>
{"mean_mrr": 0.9}
<<<METRICS_JSON_END>>>
"""
MOCK_ANALYZE_OUTPUT_VALIDATION = MOCK_ANALYZE_OUTPUT + "ANALYZER_VALIDATION_SUCCESS"
MOCK_PROCESS_OUTPUT_VALIDATION = MOCK_PROCESS_OUTPUT + "PROCESSOR_VALIDATION_SUCCESS"


@pytest.fixture
def temp_study_dir(tmp_path: Path) -> Path:
    """Creates a temporary study directory with a sample run folder."""
    study_dir = tmp_path / "study"
    run_dir = study_dir / "run_20230101_120000_rep-1"
    run_dir.mkdir(parents=True)
    # Create the archived config
    (run_dir / "config.ini.archived").write_text(MOCK_CONFIG_INI_ARCHIVED)
    # Create a dummy old report to be archived
    (run_dir / "replication_report_old.txt").touch()
    return study_dir


@patch("src.rebuild_reports.logging")
class TestRebuildReportWorker:
    """Tests the core rebuild_report_for_run function."""

    @patch("src.rebuild_reports.subprocess.run")
    def test_rebuild_success(self, mock_subprocess_run, mock_logging, temp_study_dir):
        """Test the successful, 'happy path' rebuild of a single report."""
        with patch("src.rebuild_reports.PROJECT_ROOT", temp_study_dir):
            run_dir = temp_study_dir / "run_20230101_120000_rep-1"
            # FIX: Create the parent 'data' directory, not the file itself.
            (temp_study_dir / "data").mkdir(parents=True, exist_ok=True)
            (temp_study_dir / "data" / "base_query.txt").write_text("Mock query")

            mock_subprocess_run.side_effect = [
                MagicMock(stdout=MOCK_PROCESS_OUTPUT_VALIDATION, stderr="", check_returncode=None),
                MagicMock(stdout=MOCK_ANALYZE_OUTPUT_VALIDATION, stderr="", check_returncode=None),
            ]
            compat_map = {
                "model_name": [("LLM", "model")],
                "num_trials": [("Study", "num_iterations")],
                "num_subjects": [("Study", "k_per_query")],
                "mapping_strategy": [("Study", "mapping_strategy")],
                "personalities_db_path": [("Filenames", "personalities_src")],
            }

            result = rebuild_reports.rebuild_report_for_run(str(run_dir), compat_map)

            assert result is True
            assert (run_dir / "replication_report_old.txt.corrupted").exists()
            new_reports = list(run_dir.glob("replication_report_*.txt"))
            assert len(new_reports) == 1
            new_report_content = new_reports[0].read_text()
            assert "REBUILT ON" in new_report_content
            assert "Validation Status: OK (All checks passed)" in new_report_content
            assert "Parsing Status:  95/100 responses parsed (5 warnings)" in new_report_content
            assert "This is the mock analysis summary." in new_report_content
            assert '"mean_mrr": 0.9' in new_report_content

    def test_rebuild_skips_no_archive(self, mock_logging, temp_study_dir):
        """Test that the function skips if config.ini.archived is missing."""
        with patch("src.rebuild_reports.PROJECT_ROOT", temp_study_dir):
            run_dir = temp_study_dir / "run_20230101_120000_rep-1"
            (run_dir / "config.ini.archived").unlink()

            result = rebuild_reports.rebuild_report_for_run(str(run_dir), {})
            assert result is False
            mock_logging.warning.assert_called_with(
                "Skipping: No 'config.ini.archived' found. Please run patcher first."
            )

    @patch("src.rebuild_reports.subprocess.run")
    def test_rebuild_subprocess_fails(self, mock_subprocess_run, mock_logging, temp_study_dir):
        """Test that a subprocess failure is handled and logged."""
        with patch("src.rebuild_reports.PROJECT_ROOT", temp_study_dir):
            run_dir = temp_study_dir / "run_20230101_120000_rep-1"
            # FIX: Use the imported subprocess module
            mock_subprocess_run.side_effect = subprocess.CalledProcessError(
                1, "cmd", "stdout", "stderr"
            )
            compat_map = {
                "model_name": [("LLM", "model")],
                "num_trials": [("Study", "num_iterations")],
                "num_subjects": [("Study", "k_per_query")],
                "mapping_strategy": [("Study", "mapping_strategy")],
                "personalities_db_path": [("Filenames", "personalities_src")],
            }
            result = rebuild_reports.rebuild_report_for_run(str(run_dir), compat_map)

            new_reports = list(run_dir.glob("replication_report_*.txt"))
            content = new_reports[0].read_text()
            assert "STAGE FAILED: Process LLM Responses" in content


@patch("src.rebuild_reports.logging")
@patch("src.rebuild_reports.rebuild_report_for_run")
@patch("src.config_loader.get_config_compatibility_map", return_value={})
class TestRebuildReportsMain:
    """Tests the main orchestration function."""

    def test_main_success(self, mock_map, mock_worker, mock_logging, temp_study_dir):
        """Test main finds and processes directories."""
        mock_worker.return_value = True
        with patch("sys.argv", ["script", str(temp_study_dir)]):
            rebuild_reports.main()

        mock_worker.assert_called_once()
        mock_logging.info.assert_any_call(
            "\nReport rebuilding complete. Successfully processed 1/1 directories."
        )

    def test_main_dir_not_found(self, mock_map, mock_worker, mock_logging, tmp_path):
        """Test main exits if the base directory is not found."""
        non_existent_dir = tmp_path / "non_existent"
        with patch("sys.argv", ["script", str(non_existent_dir)]):
            rebuild_reports.main()
        mock_logging.error.assert_called_with(
            f"Error: Provided directory does not exist: {non_existent_dir}"
        )

    def test_main_no_run_dirs_found(self, mock_map, mock_worker, mock_logging, tmp_path):
        """Test main exits gracefully if no run directories are found."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        with patch("sys.argv", ["script", str(empty_dir)]):
            rebuild_reports.main()
        mock_logging.info.assert_any_call(
            f"No 'run_*' directories found in {empty_dir}."
        )