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
# Filename: tests/algorithm_validation/calculate_k_specific_stats.py

"""
Calculate K-specific Wilcoxon tests using framework's analyze_metric_distribution function.
This ensures the validation uses the exact same code as the experiment lifecycle.
"""

import sys
import os
import pandas as pd

# Add src to path to import framework functions
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from analyze_llm_performance import analyze_metric_distribution

def calculate_k_specific_wilcoxon(csv_path: str, chance_level: float, metric_column: str, metric_name: str) -> dict:
    """
    Calculate Wilcoxon test using framework's analyze_metric_distribution function.
    
    Args:
        csv_path: Path to K-specific CSV file
        chance_level: Null hypothesis value
        metric_column: Column name (MRR, Top1Accuracy, Top3Accuracy)
        metric_name: Display name for the metric
    
    Returns:
        Dictionary with n, median, p_value
    """
    df = pd.read_csv(csv_path)
    metric_values = df[metric_column].dropna().tolist()
    
    # Use the EXACT same function the framework uses for replication analysis
    result = analyze_metric_distribution(metric_values, chance_level, metric_name)
    
    return {
        'n': result['count'],
        'median': result['median'],
        'p_value': result['wilcoxon_signed_rank_p']
    }

if __name__ == '__main__':
    if len(sys.argv) != 5:
        print("Usage: calculate_k_specific_stats.py <csv_path> <chance_level> <metric_column> <metric_name>")
        sys.exit(1)
    
    result = calculate_k_specific_wilcoxon(
        csv_path=sys.argv[1],
        chance_level=float(sys.argv[2]),
        metric_column=sys.argv[3],
        metric_name=sys.argv[4]
    )
    
    # Output for PowerShell parsing
    print(f"{result['n']},{result['median']:.6f},{result['p_value']:.6f}")

# === End of tests/algorithm_validation/calculate_k_specific_stats.py ===
