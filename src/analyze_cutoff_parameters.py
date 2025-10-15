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
from tabulate import tabulate
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


def generate_report(stability_df, best_params, text_report_path):
    """
    Generates a formatted text report for the console (top 10) and a full
    report for a file.
    """
    # --- Shared Report Components ---
    report_header = [
        f"\n{Fore.YELLOW}--- Recommendation ---{Fore.RESET}",
        f"\n\n{Fore.YELLOW}--- Stability Analysis (Top Performers with Error < 50) ---{Fore.RESET}",
        "Showing the most stable results, sorted by neighbor error ('Stability') then self error.\n"
    ]
    
    report_footer = [
        "\nThe most robust parameters (center of the most stable, high-performing cluster) are:",
        f"{Fore.CYAN}  cutoff_search_start_point = {best_params['start_point']}{Fore.RESET}",
        f"{Fore.CYAN}  smoothing_window_size = {best_params['smoothing_window']}{Fore.RESET}",
        "\nThese values are recommended as they are high-performing and surrounded by other",
        "high-performing parameters, indicating a stable and reliable choice."
    ]

    # Define headers for tabulate
    headers = {
        'Start Point': 'Start\nPoint', 'Smoothing Window': 'Smoothing\nWindow',
        'Predicted Cutoff': 'Predicted\nCutoff', 'Ideal Cutoff': 'Ideal\nCutoff',
        'Error': 'Error', 'Stability': 'Stability'
    }
    df_renamed = stability_df.rename(columns=lambda x: headers.get(x, x))

    # Define column-specific number formats for tabulate
    # Integers for all columns except Stability, which gets 2 decimal places.
    col_formats = (".0f", ".0f", ".0f", ".0f", ".0f", ".2f")

    # --- Generate Console Output (Top 10) ---
    console_df = df_renamed.head(10)
    console_table = tabulate(
        console_df, headers="keys", tablefmt="simple", floatfmt=col_formats, numalign="center"
    )
    console_report_parts = report_header + [console_table] + report_footer
    print("\n".join(console_report_parts))

    # --- Generate File Output (Full Report) ---
    file_df = df_renamed
    file_table = tabulate(
        file_df, headers="keys", tablefmt="simple", floatfmt=col_formats, numalign="center"
    )
    
    # Remove ANSI color codes for the file version
    file_footer_clean = [s.split('m', 1)[-1] for s in report_footer]
    file_report_parts = report_header + [file_table] + file_footer_clean
    text_report_path.write_text("\n".join(file_report_parts).replace(Fore.YELLOW, '').replace(Fore.RESET, ''), encoding="utf-8")


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
        
        current_start = int(get_config_value(APP_CONFIG, "DataGeneration", "cutoff_search_start_point", fallback="5000"))
        current_window = int(get_config_value(APP_CONFIG, "DataGeneration", "smoothing_window_size", fallback="2000"))
        
        minimal_df = pd.DataFrame([{'Start Point': current_start, 'Smoothing Window': current_window, 'Predicted Cutoff': len(ocean_df), 'Ideal Cutoff': len(ocean_df), 'Error': 0}])
        
        csv_report_path = Path(get_path("data/foundational_assets/cutoff_parameter_analysis_results.csv"))
        
        try:
            csv_report_path.parent.mkdir(parents=True, exist_ok=True)
            minimal_df.to_csv(csv_report_path, index=False)
            print(f"Minimal results saved to '{csv_report_path}'.")
            print(f"{Fore.YELLOW}Note: These are placeholder values. Parameter optimization requires a larger dataset.{Fore.RESET}")
        except Exception as e:
            print(f"{Fore.RED}Error saving minimal results: {e}{Fore.RESET}")
            sys.exit(1)
        return

    # --- Analyze and Report Results ---
    results_df = pd.DataFrame(results)
    results_df.sort_values(by="Error", ascending=True, inplace=True)
    
    # Define file paths
    csv_report_path = Path(get_path("data/foundational_assets/cutoff_parameter_analysis_results.csv"))
    text_report_path = csv_report_path.with_suffix('.txt')
    full_grid_search_path = csv_report_path.with_name(f"{csv_report_path.stem}_full_grid_search.csv")

    # --- Save the full grid search data for diagnostic purposes ---
    try:
        full_grid_search_path.parent.mkdir(parents=True, exist_ok=True)
        results_df.to_csv(full_grid_search_path, index=False)
        print(f"\nAnalysis results (full grid search) saved to '{full_grid_search_path}'.")
    except Exception as e:
        print(f"\n{Fore.RED}Error saving full grid search results to file: {e}")

    # --- Stability-Based Algorithm: Find the most robust high-performer ---
    error_threshold = 50
    best_cluster_df = results_df[results_df['Error'] < error_threshold].copy()
    
    final_recommendation_df = None

    if not best_cluster_df.empty:
        unique_starts = sorted(list(results_df['Start Point'].unique()))
        unique_windows = sorted(list(results_df['Smoothing Window'].unique()))

        stability_scores = []
        for index, row in best_cluster_df.iterrows():
            current_start, current_window = row['Start Point'], row['Smoothing Window']
            start_idx, window_idx = unique_starts.index(current_start), unique_windows.index(current_window)
            
            neighbor_errors = []
            # Check neighbors in cardinal directions
            for ds, dw in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ni, nj = start_idx + ds, window_idx + dw
                if 0 <= ni < len(unique_starts) and 0 <= nj < len(unique_windows):
                    neighbor_row = results_df[(results_df['Start Point'] == unique_starts[ni]) & (results_df['Smoothing Window'] == unique_windows[nj])]
                    if not neighbor_row.empty: neighbor_errors.append(neighbor_row['Error'].iloc[0])
            
            stability_scores.append(np.mean(neighbor_errors) if neighbor_errors else np.inf)

        best_cluster_df['Stability'] = stability_scores
        best_cluster_df.sort_values(by=['Stability', 'Error'], ascending=[True, True], inplace=True)
        
        # The final recommendation is the single most stable, high-performing parameter set.
        recommended_params_row = best_cluster_df.iloc[[0]]
        final_recommendation_df = recommended_params_row[['Start Point', 'Smoothing Window', 'Predicted Cutoff', 'Ideal Cutoff', 'Error']]
        
        best_params = {
            'start_point': int(recommended_params_row['Start Point'].iloc[0]),
            'smoothing_window': int(recommended_params_row['Smoothing Window'].iloc[0])
        }
        
        # Generate the console and text reports from the full stability analysis
        generate_report(best_cluster_df, best_params, text_report_path)

    else:
        # Fallback to the single best result if no cluster is found
        best_params_row = results_df.iloc[[0]]
        final_recommendation_df = best_params_row[['Start Point', 'Smoothing Window', 'Predicted Cutoff', 'Ideal Cutoff', 'Error']]
        
        print("No high-performing cluster found. Recommending the single best result:")
        print(f"{Fore.CYAN}  cutoff_search_start_point = {int(best_params_row['Start Point'].iloc[0])}{Fore.RESET}")
        print(f"{Fore.CYAN}  smoothing_window_size = {int(best_params_row['Smoothing Window'].iloc[0])}{Fore.RESET}")

    # --- Save the final, single-line recommendation to the main CSV output file ---
    # This ensures the orchestrator reads the correct, stability-analyzed result.
    try:
        csv_report_path.parent.mkdir(parents=True, exist_ok=True)
        final_recommendation_df.to_csv(csv_report_path, index=False)
        print(f"\nAnalysis recommendation saved to '{csv_report_path}'.")
        if text_report_path.exists():
            print(f"Formatted stability analysis saved to '{text_report_path}'.")
    except Exception as e:
        print(f"\n{Fore.RED}Error saving recommendation to file: {e}")
    
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
