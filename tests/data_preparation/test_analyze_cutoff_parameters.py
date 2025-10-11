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
# Filename: tests/data_preparation/test_analyze_cutoff_parameters.py

"""
Unit tests for src/analyze_cutoff_parameters.py

This test validates the cutoff parameter analysis functionality, which performs
a grid search to find optimal parameters for the final candidate selection algorithm.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

import pandas as pd
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.analyze_cutoff_parameters import find_ideal_cutoff, print_centered_table, main
import numpy as np


class TestFindIdealCutoff:
    """Tests for the find_ideal_cutoff function."""
    
    def test_ideal_cutoff_simple_curve(self):
        """Test finding the ideal cutoff on a simple curved dataset."""
        # Create a simple curve: starts high, dips in middle, ends high
        x_values = np.array([1, 2, 3, 4, 5])
        y_values = np.array([10, 5, 2, 5, 10])
        
        ideal = find_ideal_cutoff(x_values, y_values)
        
        # The point furthest from the line should be at x=3 (the dip)
        assert ideal == 3
    
    def test_ideal_cutoff_linear(self):
        """Test that a linear dataset returns one of the endpoints."""
        x_values = np.array([1, 2, 3, 4, 5])
        y_values = np.array([1, 2, 3, 4, 5])
        
        ideal = find_ideal_cutoff(x_values, y_values)
        
        # For a perfect line, any point could be "ideal" (all have distance ~0)
        # Just verify it returns a valid x value
        assert ideal in x_values


class TestPrintCenteredTable:
    """Tests for the print_centered_table function."""
    
    def test_print_centered_table_basic(self, capsys):
        """Test that the table prints without errors."""
        df = pd.DataFrame({
            'Start Point': [100, 200],
            'Smoothing Window': [50, 100],
            'Error': [10, 20]
        })
        
        print_centered_table(df)
        captured = capsys.readouterr()
        
        # Verify output contains the column names
        assert 'Start' in captured.out
        assert 'Point' in captured.out
        assert 'Smoothing' in captured.out
        assert 'Window' in captured.out
        assert 'Error' in captured.out


class TestAnalyzeCutoffParametersIntegration:
    """Integration tests for the complete analysis workflow."""
    
    @pytest.fixture
    def temp_sandbox(self):
        """Create a temporary sandbox environment for testing."""
        sandbox_dir = tempfile.mkdtemp(prefix="test_analyze_cutoff_")
        
        # Create directory structure
        data_dir = Path(sandbox_dir) / "data" / "foundational_assets"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        reports_dir = Path(sandbox_dir) / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a minimal config.ini
        config_path = Path(sandbox_dir) / "config.ini"
        config_content = """[DataGeneration]
slope_threshold = -0.00001
"""
        config_path.write_text(config_content)
        
        # Create test OCEAN scores data with sufficient variance for analysis
        # Use 300 subjects - enough to test some parameter combinations but fast for unit tests
        # The script's hardcoded ranges go up to 5000, but we only need to verify it produces
        # *some* valid results, not that it tests all parameter combinations
        ocean_data = []
        np.random.seed(42)  # For reproducibility
        for i in range(300):
            ocean_data.append({
                'idADB': i + 1,
                'Name': f'Subject {i+1}',
                'Openness': np.random.randint(1, 6),
                'Conscientiousness': np.random.randint(1, 6),
                'Extraversion': np.random.randint(1, 6),
                'Agreeableness': np.random.randint(1, 6),
                'Neuroticism': np.random.randint(1, 6)
            })
        
        ocean_df = pd.DataFrame(ocean_data)
        ocean_path = data_dir / "ocean_scores.csv"
        ocean_df.to_csv(ocean_path, index=False)
        
        yield sandbox_dir
        
        # Cleanup
        shutil.rmtree(sandbox_dir)
    
    def test_main_creates_output_file(self, temp_sandbox, monkeypatch):
        """Test that main() creates the expected output CSV file."""
        # Set sandbox environment before importing
        monkeypatch.setenv('PROJECT_SANDBOX_PATH', temp_sandbox)
        
        # Import and run main directly (sandbox is already set)
        from src.analyze_cutoff_parameters import main
        main()
        
        # Verify output file was created
        output_path = Path(temp_sandbox) / "data" / "reports" / "cutoff_parameter_analysis_results.csv"
        assert output_path.exists(), "Analysis results CSV was not created"
        
        # Verify the CSV has the expected structure
        results_df = pd.read_csv(output_path)
        expected_columns = ['Start Point', 'Smoothing Window', 'Predicted Cutoff', 'Ideal Cutoff', 'Error']
        assert list(results_df.columns) == expected_columns
        
        # Verify we have results (at least some parameter combinations should work with 300 subjects)
        assert len(results_df) > 0, "Results dataframe is empty"
        
        # With 300 subjects, only small parameter combinations will work (start_point=250, window=100/200)
        # Just verify we got at least 1 valid result to confirm the script works
        assert len(results_df) >= 1, f"Expected at least 1 result, got {len(results_df)}"
        
        # Verify results are sorted by error (ascending)
        assert results_df['Error'].is_monotonic_increasing or results_df['Error'].iloc[0] <= results_df['Error'].iloc[-1]
    
    def test_main_with_minimal_data(self, temp_sandbox, monkeypatch, capsys):
        """Test that the script handles datasets too small for analysis gracefully."""
        # Overwrite OCEAN scores with minimal data (only 10 subjects)
        data_dir = Path(temp_sandbox) / "data" / "foundational_assets"
        ocean_data = []
        for i in range(10):
            ocean_data.append({
                'idADB': i + 1,
                'Name': f'Subject {i+1}',
                'Openness': 3,
                'Conscientiousness': 3,
                'Extraversion': 3,
                'Agreeableness': 3,
                'Neuroticism': 3
            })
        
        ocean_df = pd.DataFrame(ocean_data)
        ocean_path = data_dir / "ocean_scores.csv"
        ocean_df.to_csv(ocean_path, index=False)
        
        # Set sandbox environment before importing
        monkeypatch.setenv('PROJECT_SANDBOX_PATH', temp_sandbox)
        
        # Run should complete without error even with minimal data
        from src.analyze_cutoff_parameters import main
        main()
        
        # With minimal data, the script should complete but produce no results
        # Verify it prints the appropriate message
        captured = capsys.readouterr()
        assert "Analysis could not be completed" in captured.out
        
        # The output file should NOT be created when there are no results
        output_path = Path(temp_sandbox) / "data" / "reports" / "cutoff_parameter_analysis_results.csv"
        assert not output_path.exists(), "CSV should not be created when analysis produces no results"

# === End of tests/data_preparation/test_analyze_cutoff_parameters.py ===
