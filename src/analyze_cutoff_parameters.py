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
# Filename: src/analyze_cutoff_parameters.py

"""
Performs a sensitivity analysis to find the optimal parameters for the
final candidate selection algorithm.

This is a one-off utility script designed to help set the ideal values for
'cutoff_search_start_point' and 'smoothing_window_size' in config.ini.

The script operates by:
1.  Defining a grid of parameter values to test.
2.  For each combination, it calculates the cutoff point using the standard
    slope-based algorithm from the main pipeline.
3.  It then calculates the "ideal" cutoff point. The ideal point is defined
    as the point on the smoothed variance curve that has the maximum distance
    from a straight line drawn from the start to the end of the analysis window.
4.  It measures the "error" as the difference between the algorithm's result
    and the ideal result.
5.  Finally, it presents a ranked list of the parameter combinations that
    produced the lowest error, giving a data-driven recommendation for the
    best parameters to use in the project configuration.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from colorama import Fore, init
from tqdm import tqdm

# Initialize colorama
init(autoreset=True, strip=False)

# Ensure the src directory is in the Python path
sys.path.append(str(Path(__file__).resolve().parents[1]))
# Note: config_loader imports are deferred to main() to allow sandbox path to be set first


def find_ideal_cutoff(x_values, y_values):
    """
    Finds the point on the curve with the maximum distance from a line
    connecting the first and last points. Uses 3D vectors to avoid
    NumPy 2.0 deprecation warnings.
    """
    # Convert 2D points to 3D by adding a zero z-coordinate
    p1 = np.array([x_values[0], y_values[0], 0])
    p2 = np.array([x_values[-1], y_values[-1], 0])
    
    line_vec = p2 - p1
    line_vec_norm = np.linalg.norm(line_vec)
    
    distances = []
    for i in range(len(x_values)):
        p3 = np.array([x_values[i], y_values[i], 0])
        point_vec = p1 - p3
        
        # Calculate distance using the magnitude of the cross product
        cross_product_norm = np.linalg.norm(np.cross(line_vec, point_vec))
        distance = cross_product_norm / line_vec_norm
        distances.append(distance)
        
    max_dist_index = np.argmax(distances)
    return x_values[max_dist_index]


def print_centered_table(df):
    """Formats and prints a DataFrame with centered, two-line headers."""
    headers = [col.split() for col in df.columns]
    header_line1 = [h[0] if len(h) > 0 else "" for h in headers]
    header_line2 = [h[1] if len(h) > 1 else "" for h in headers]

    # Calculate column widths
    col_widths = {}
    for col in df.columns:
        max_len1 = len(col.split()[0]) if len(col.split()) > 0 else 0
        max_len2 = len(col.split()[1]) if len(col.split()) > 1 else 0
        max_header_width = max(max_len1, max_len2)
        max_data_width = df[col].astype(str).str.len().max()
        col_widths[col] = max(max_header_width, max_data_width) + 2

    # Print Header
    print(" ".join(h.center(col_widths[df.columns[i]]) for i, h in enumerate(header_line1)))
    print(" ".join(h.center(col_widths[df.columns[i]]) for i, h in enumerate(header_line2)))
    print(" ".join("-" * col_widths[col] for col in df.columns))

    # Print Data
    for _, row in df.iterrows():
        print(" ".join(str(row[col]).center(col_widths[col]) for col in df.columns))


def run_analysis(sandbox_path=None):
    """
    Core logic for the sensitivity analysis. Separated from main() for testability.
    
    Args:
        sandbox_path (str, optional): Path to a sandbox directory. Defaults to None.
    """
    import os
    
    # If a sandbox path is provided, set the environment variable
    if sandbox_path:
        os.environ['PROJECT_SANDBOX_PATH'] = os.path.abspath(sandbox_path)
    
    # Import here to allow sandbox path to be set first
    from config_loader import APP_CONFIG, get_config_value, get_path
    from select_final_candidates import calculate_average_variance
    
    print(f"\n{Fore.YELLOW}--- Starting Cutoff Parameter Sensitivity Analysis ---")

    # --- Parameters to Test ---
    start_points = [250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2250, 2500, 2750, 3000, 3250, 3500, 3750, 4000, 4250, 4500, 4750, 5000]
    smoothing_windows = [100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000]
    slope_threshold = get_config_value(APP_CONFIG, "DataGeneration", "slope_threshold", -0.00001, float)

    # --- Load Data ---
    ocean_path = Path(get_path("data/foundational_assets/ocean_scores.csv"))
    print(f"Loading data from '{ocean_path}'...")
    try:
        ocean_df = pd.read_csv(ocean_path)
    except FileNotFoundError:
        print(f"ERROR: Could not find the required data file at '{ocean_path}'.")
        sys.exit(1)
        
    # Calculate the raw variance curve once to avoid redundant calculations.
    print(f"\nCalculating variance curve for {len(ocean_df)} subjects...")
    x_values = np.array(range(2, len(ocean_df) + 1))
    variances = np.array([calculate_average_variance(ocean_df.head(i)) for i in tqdm(x_values, desc="Computing Variances", ncols=80)])
    print() # Add blank line after progress bar
    
    results = []
    total_iterations = len(start_points) * len(smoothing_windows)
    
    print(f"Determining optimal cutoff parameters for {total_iterations} combinations...")

    with tqdm(total=total_iterations, desc="Analyzing Parameters", ncols=80) as pbar:
        for start_point in start_points:
            for window in smoothing_windows:
                if len(variances) < window or len(variances) < start_point:
                    pbar.update(1)
                    continue

                # Smooth the curve
                smoothed = pd.Series(variances).rolling(window=window, center=True).mean().bfill().ffill().to_numpy()
                
                # --- 1. Get the algorithm's predicted cutoff ---
                predicted_cutoff = len(ocean_df) # Default
                try:
                    start_idx = np.where(x_values >= start_point)[0][0]
                except IndexError:
                    # This happens if start_point > max(x_values)
                    pbar.update(1)
                    continue

                gradient = np.gradient(smoothed, x_values)
                
                cutoff_idx = -1
                for i in range(start_idx, len(gradient)):
                    if gradient[i] > slope_threshold:
                        cutoff_idx = i
                        break
                if cutoff_idx != -1:
                    predicted_cutoff = x_values[cutoff_idx]
                
                # --- 2. Get the "ideal" geometric cutoff ---
                search_x = x_values[start_idx:]
                search_y = smoothed[start_idx:]
                ideal_cutoff = find_ideal_cutoff(search_x, search_y)
                
                # --- 3. Calculate error and store ---
                error = abs(predicted_cutoff - ideal_cutoff)
                results.append({
                    "Start Point": start_point,
                    "Smoothing Window": window,
                    "Predicted Cutoff": predicted_cutoff,
                    "Ideal Cutoff": ideal_cutoff,
                    "Error": error
                })
                pbar.update(1)

    if not results:
        print(f"{Fore.YELLOW}WARNING: Dataset too small for meaningful parameter analysis.{Fore.RESET}")
        print(f"{Fore.CYAN}Creating minimal output file to allow pipeline to continue.{Fore.RESET}")
        
        # Create a minimal CSV with current config values as placeholder
        current_start = int(get_config_value(APP_CONFIG, "DataGeneration", "cutoff_search_start_point", fallback="5000"))
        current_window = int(get_config_value(APP_CONFIG, "DataGeneration", "smoothing_window_size", fallback="2000"))
        
        minimal_df = pd.DataFrame([{
            "Start Point": current_start,
            "Smoothing Window": current_window,
            "Predicted Cutoff": len(ocean_df),
            "Ideal Cutoff": len(ocean_df),
            "Error": 0
        }])
        
        # Define the output path
        minimal_report_path = Path(get_path("data/foundational_assets/cutoff_parameter_analysis_results.csv"))
        
        try:
            minimal_report_path.parent.mkdir(parents=True, exist_ok=True)
            minimal_df.to_csv(minimal_report_path, index=False)
            print(f"Minimal results saved to '{minimal_report_path}'.")
            print(f"{Fore.YELLOW}Note: These are placeholder values. Parameter optimization requires a larger dataset.{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}Error saving minimal results: {e}{Fore.RESET}")
            sys.exit(1)
        return

    # --- Display Results ---
    results_df = pd.DataFrame(results)
    results_df.sort_values(by="Error", ascending=True, inplace=True)
    
    # Full results table is suppressed for pipeline runs (saved to CSV instead)
    # Uncomment the lines below to see the full table during standalone analysis:
    # print(f"\n\n{Fore.YELLOW}--- Parameter Analysis Results (Full Grid Search) ---")
    # print("The best parameters are those with the lowest 'Error' value.")
    # print("This means the algorithm's result was closest to the geometrically ideal cutoff point.\n")
    # print_centered_table(results_df)

    # Save the results to a CSV file
    report_path = Path(get_path("data/foundational_assets/cutoff_parameter_analysis_results.csv"))
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(report_path, index=False)
        print(f"\nAnalysis results saved to '{report_path}'.")
    except Exception as e:
        print(f"\n{Fore.RED}Error saving results to file: {e}")
    
    print(f"\n{Fore.YELLOW}--- Recommendation ---")
    
    # --- Stability-Based Algorithm: Find the most robust high-performer ---
    error_threshold = 50
    best_cluster_df = results_df[results_df['Error'] < error_threshold].copy()

    if not best_cluster_df.empty:
        # Get the unique values for start points and windows that were tested
        unique_starts = sorted(list(results_df['Start Point'].unique()))
        unique_windows = sorted(list(results_df['Smoothing Window'].unique()))

        stability_scores = []
        for index, row in best_cluster_df.iterrows():
            current_start = row['Start Point']
            current_window = row['Smoothing Window']
            
            # Find indices of neighbors in the parameter grid
            start_idx = unique_starts.index(current_start)
            window_idx = unique_windows.index(current_window)
            
            neighbor_errors = []
            
            # Check neighbor in each cardinal direction of the grid
            if start_idx > 0: # Neighbor Up
                neighbor_row = results_df[(results_df['Start Point'] == unique_starts[start_idx - 1]) & (results_df['Smoothing Window'] == current_window)]
                if not neighbor_row.empty: neighbor_errors.append(neighbor_row['Error'].iloc[0])
            if start_idx < len(unique_starts) - 1: # Neighbor Down
                neighbor_row = results_df[(results_df['Start Point'] == unique_starts[start_idx + 1]) & (results_df['Smoothing Window'] == current_window)]
                if not neighbor_row.empty: neighbor_errors.append(neighbor_row['Error'].iloc[0])
            if window_idx > 0: # Neighbor Left
                neighbor_row = results_df[(results_df['Start Point'] == current_start) & (results_df['Smoothing Window'] == unique_windows[window_idx - 1])]
                if not neighbor_row.empty: neighbor_errors.append(neighbor_row['Error'].iloc[0])
            if window_idx < len(unique_windows) - 1: # Neighbor Right
                neighbor_row = results_df[(results_df['Start Point'] == current_start) & (results_df['Smoothing Window'] == unique_windows[window_idx + 1])]
                if not neighbor_row.empty: neighbor_errors.append(neighbor_row['Error'].iloc[0])

            # The stability score is the average error of its neighbors.
            stability_score = np.mean(neighbor_errors) if neighbor_errors else np.inf
            stability_scores.append(stability_score)

        best_cluster_df['Stability'] = stability_scores
        
        # Sort by stability, then by original error as a tie-breaker.
        best_cluster_df.sort_values(by=['Stability', 'Error'], ascending=[True, True], inplace=True)
        
        print(f"\n\n{Fore.YELLOW}--- Stability Analysis (Top Performers with Error < {error_threshold}) ---")
        print("Showing the most stable results, sorted by neighbor error ('Stability') then self error.\n")
        
        # Format for printing
        display_df = best_cluster_df.copy()
        display_df['Stability'] = display_df['Stability'].map('{:.2f}'.format)
        print_centered_table(display_df)

        recommended_params = best_cluster_df.iloc[0]
        recommended_start = int(recommended_params['Start Point'])
        recommended_window = int(recommended_params['Smoothing Window'])

        print("\nThe most robust parameters (center of the most stable, high-performing cluster) are:")
        print(f"{Fore.CYAN}  cutoff_search_start_point = {recommended_start}{Fore.RESET}")
        print(f"{Fore.CYAN}  smoothing_window_size = {recommended_window}{Fore.RESET}")
        print("\nThese values are recommended as they are high-performing and surrounded by other")
        print("high-performing parameters, indicating a stable and reliable choice.")

    else:
        # Fallback to the single best result if no cluster is found
        best_params = results_df.iloc[0]
        print("No high-performing cluster found. Recommending the single best result:")
        print(f"{Fore.CYAN}  cutoff_search_start_point = {int(best_params['Start Point'])}{Fore.RESET}")
        print(f"{Fore.CYAN}  smoothing_window_size = {int(best_params['Smoothing Window'])}{Fore.RESET}")

    print() # Add blank line


def main():
    """Main function to parse arguments and run the sensitivity analysis."""
    import argparse
    import os

    parser = argparse.ArgumentParser(
        description="Performs a sensitivity analysis to find optimal cutoff parameters.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("--sandbox-path", help="Specify a sandbox directory for all file operations.")
    parser.add_argument("--force", action="store_true", help="Force re-run of analysis (included for pipeline compatibility).")
    args = parser.parse_args()

    run_analysis(sandbox_path=args.sandbox_path)


if __name__ == "__main__":
    main()

# === End of src/analyze_cutoff_parameters.py ===
